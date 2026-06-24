import asyncio
import hashlib
import logging
import time

import httpx

from config import settings

logger = logging.getLogger("canvas.token_manager")

REFRESH_INTERVAL_SECONDS = 300  # 5 min: keeps the fallback token ahead of any expiry Canvas sets
IDLE_TTL_SECONDS = 86400  # drop a user's fallback state after 24h of no calls, to avoid unbounded memory growth
FALLBACK_TOKEN_PURPOSE = "aulavirtual-taws-mcp-fallback"


class _UserTokenState:
    def __init__(self, original_token: str):
        self.original_token = original_token
        self.fallback_token: str | None = None
        self.fallback_token_id: int | None = None
        self.refreshed_at: float = 0.0
        self.last_used: float = time.monotonic()
        self.lock = asyncio.Lock()
        self.refresh_task: asyncio.Task | None = None


def _find_token_id(payload: object) -> int | None:
    if isinstance(payload, dict):
        for key in ("id", "token_id", "access_token_id"):
            value = payload.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        for key in ("token", "access_token"):
            token_id = _find_token_id(payload.get(key))
            if token_id is not None:
                return token_id
        for value in payload.values():
            token_id = _find_token_id(value)
            if token_id is not None:
                return token_id
    elif isinstance(payload, list):
        for item in payload:
            token_id = _find_token_id(item)
            if token_id is not None:
                return token_id
    return None


def _find_token_value(payload: object) -> str | None:
    token_keys = {"token", "access_token", "visible_token", "plain_text_token", "full_token"}
    if isinstance(payload, dict):
        for key in token_keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                token_value = _find_token_value(value)
                if token_value is not None:
                    return token_value
        for value in payload.values():
            token_value = _find_token_value(value)
            if token_value is not None:
                return token_value
    elif isinstance(payload, list):
        for item in payload:
            token_value = _find_token_value(item)
            if token_value is not None:
                return token_value
    return None


class TokenManager:
    """Keeps a self-rotating Canvas access token per user alive in memory.

    Canvas personal access tokens have no OAuth refresh flow. Instead, the
    Canvas API lets a valid token regenerate itself (or mint a sibling
    token), which resets any expiration Canvas attached to it. We use the
    token the user pasted once to mint a "fallback" token, then keep
    regenerating that fallback token on a timer for as long as this process
    is alive, so the user never has to paste a new token again.
    """

    def __init__(self):
        self._states: dict[str, _UserTokenState] = {}
        self._store_lock = asyncio.Lock()

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.strip().encode()).hexdigest()

    async def get_active_token(self, original_token: str) -> str:
        key = self._key(original_token)
        async with self._store_lock:
            state = self._states.get(key)
            if state is None:
                state = _UserTokenState(original_token)
                self._states[key] = state

        state.last_used = time.monotonic()
        await self._ensure_fallback(state)

        if state.refresh_task is None or state.refresh_task.done():
            state.refresh_task = asyncio.create_task(self._refresh_loop(key, state))

        return state.fallback_token or original_token

    async def _ensure_fallback(self, state: _UserTokenState, force: bool = False) -> None:
        now = time.monotonic()
        if not force and state.fallback_token and now - state.refreshed_at < REFRESH_INTERVAL_SECONDS:
            return

        async with state.lock:
            now = time.monotonic()
            if not force and state.fallback_token and now - state.refreshed_at < REFRESH_INTERVAL_SECONDS:
                return

            auth_token = state.fallback_token or state.original_token
            try:
                if state.fallback_token_id is None:
                    await self._create_fallback_token(state, auth_token)
                else:
                    await self._regenerate_fallback_token(state, auth_token)
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("No se pudo refrescar el fallback token: %s", exc)

    async def _create_fallback_token(self, state: _UserTokenState, auth_token: str) -> None:
        async with httpx.AsyncClient(
            base_url=settings.canvas_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"},
            timeout=15.0,
        ) as client:
            response = await client.post(
                "/api/v1/users/self/tokens",
                json={"token": {"purpose": FALLBACK_TOKEN_PURPOSE}},
            )
            response.raise_for_status()
            self._apply(state, response.json())

    async def _regenerate_fallback_token(self, state: _UserTokenState, auth_token: str) -> None:
        async with httpx.AsyncClient(
            base_url=settings.canvas_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"},
            timeout=15.0,
        ) as client:
            response = await client.put(
                f"/api/v1/users/self/tokens/{state.fallback_token_id}",
                json={"token": {"regenerate": 1}},
            )
            response.raise_for_status()
            self._apply(state, response.json())

    def _apply(self, state: _UserTokenState, payload: dict) -> None:
        token_id = _find_token_id(payload)
        token_value = _find_token_value(payload)
        if token_id is None or not token_value:
            raise ValueError("Canvas no devolvio id/token al crear o regenerar el fallback token")
        state.fallback_token_id = token_id
        state.fallback_token = token_value
        state.refreshed_at = time.monotonic()

    async def _refresh_loop(self, key: str, state: _UserTokenState) -> None:
        try:
            while True:
                await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
                if time.monotonic() - state.last_used > IDLE_TTL_SECONDS:
                    async with self._store_lock:
                        self._states.pop(key, None)
                    return
                await self._ensure_fallback(state, force=True)
        except asyncio.CancelledError:
            pass


token_manager = TokenManager()
