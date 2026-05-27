import asyncio
import getpass
import logging
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx
from config import settings

logger = logging.getLogger("canvas")
FALLBACK_TOKEN_REFRESH_SECONDS = 300
FALLBACK_TOKEN_PURPOSE = "aulavirtual-taws-mcp-fallback"


def prompt_canvas_token() -> str:
    if settings.canvas_api_token:
        return settings.canvas_api_token
    if not sys.stdin.isatty():
        token = input("Ingresa tu Canvas API token: ").strip()
    else:
        try:
            token = getpass.getpass("Ingresa tu Canvas API token: ").strip()
        except (EOFError, OSError):
            token = input("Ingresa tu Canvas API token: ").strip()
    if not token:
        raise RuntimeError("El Canvas API token es obligatorio para iniciar la app")
    return token


class CanvasClient:
    def __init__(self):
        self.base_url = settings.canvas_base_url.rstrip("/")
        self._bootstrap_token = prompt_canvas_token()
        self._fallback_token_id: int | None = None
        self._fallback_token: str | None = None
        self._fallback_refreshed_at = 0.0
        self._fallback_refresh_task: asyncio.Task | None = None
        self._using_fallback_token = False
        self._token_lock = asyncio.Lock()
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._bootstrap_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._token_client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._bootstrap_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def aclose(self):
        if self._fallback_refresh_task is not None:
            self._fallback_refresh_task.cancel()
            try:
                await self._fallback_refresh_task
            except asyncio.CancelledError:
                pass
        await self._client.aclose()
        await self._token_client.aclose()

    async def ensure_controlled_token(self) -> None:
        if self._fallback_refresh_task is None:
            self._fallback_refresh_task = asyncio.create_task(self._fallback_refresh_loop())
        await self._ensure_fallback_token()

    async def _fallback_refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(FALLBACK_TOKEN_REFRESH_SECONDS)
            await self._ensure_fallback_token(force=True)

    async def _ensure_fallback_token(self, force: bool = False) -> None:
        now = time.monotonic()
        if (
            not force
            and self._fallback_token is not None
            and now - self._fallback_refreshed_at < FALLBACK_TOKEN_REFRESH_SECONDS
        ):
            return

        async with self._token_lock:
            now = time.monotonic()
            if (
                not force
                and self._fallback_token is not None
                and now - self._fallback_refreshed_at < FALLBACK_TOKEN_REFRESH_SECONDS
            ):
                return

            try:
                if self._fallback_token_id is None:
                    await self._create_controlled_token()
                else:
                    await self._regenerate_controlled_token()
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("No se pudo refrescar TOKEN_FALLBACK: %s", exc)

    async def _create_controlled_token(self) -> None:
        response = await self._token_client.post(
            f"{self.base_url}/api/v1/users/self/tokens",
            json={"token": {"purpose": FALLBACK_TOKEN_PURPOSE}},
        )
        response.raise_for_status()
        self._apply_controlled_token(response.json())

    async def _regenerate_controlled_token(self) -> None:
        if self._fallback_token_id is None:
            await self._create_controlled_token()
            return
        response = await self._token_client.put(
            f"{self.base_url}/api/v1/users/self/tokens/{self._fallback_token_id}",
            json={"token": {"regenerate": 1}},
        )
        response.raise_for_status()
        self._apply_controlled_token(response.json())

    def _find_token_id(self, payload: object) -> int | None:
        if isinstance(payload, dict):
            for key in ("id", "token_id", "access_token_id"):
                value = payload.get(key)
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.isdigit():
                    return int(value)
            for key in ("token", "access_token"):
                token_id = self._find_token_id(payload.get(key))
                if token_id is not None:
                    return token_id
            for value in payload.values():
                token_id = self._find_token_id(value)
                if token_id is not None:
                    return token_id
        elif isinstance(payload, list):
            for item in payload:
                token_id = self._find_token_id(item)
                if token_id is not None:
                    return token_id
        return None

    def _find_token_value(self, payload: object) -> str | None:
        token_keys = {
            "token",
            "access_token",
            "visible_token",
            "plain_text_token",
            "full_token",
        }
        if isinstance(payload, dict):
            for key in token_keys:
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, dict):
                    token_value = self._find_token_value(value)
                    if token_value is not None:
                        return token_value
            for value in payload.values():
                token_value = self._find_token_value(value)
                if token_value is not None:
                    return token_value
        elif isinstance(payload, list):
            for item in payload:
                token_value = self._find_token_value(item)
                if token_value is not None:
                    return token_value
        return None

    def _payload_shape(self, payload: object) -> str:
        if isinstance(payload, dict):
            keys = ", ".join(sorted(str(key) for key in payload.keys()))
            return f"dict keys=[{keys}]"
        if isinstance(payload, list):
            return f"list len={len(payload)}"
        return type(payload).__name__

    def _apply_controlled_token(self, payload: dict) -> None:
        token_id = self._find_token_id(payload)
        token_value = self._find_token_value(payload)
        if token_id is None or not token_value:
            raise ValueError(
                "Canvas no devolvio id/token al crear o regenerar el token "
                f"({self._payload_shape(payload)})"
            )

        self._fallback_token_id = token_id
        self._fallback_token = token_value
        self._fallback_refreshed_at = time.monotonic()
        if self._using_fallback_token:
            self._client.headers["Authorization"] = f"Bearer {token_value}"
            self._token_client.headers["Authorization"] = f"Bearer {token_value}"
        print(f"TOKEN_FALLBACK creado/regenerado", flush=True)

    async def _refresh_controlled_token(self) -> None:
        if self._fallback_token is None:
            await self._ensure_fallback_token(force=True)
        if self._fallback_token is None:
            raise RuntimeError("El token original caduco y no existe TOKEN_FALLBACK en memoria")

        self._using_fallback_token = True
        self._client.headers["Authorization"] = f"Bearer {self._fallback_token}"
        self._token_client.headers["Authorization"] = f"Bearer {self._fallback_token}"
        print("TOKEN original caducado; usando TOKEN_FALLBACK en memoria", flush=True)

    async def _request_json(self, method: str, path: str, **kwargs) -> dict | list:
        await self.ensure_controlled_token()
        url = f"{self.base_url}/api/v1{path}"
        response = await self._client.request(method, url, **kwargs)
        if response.status_code == 401:
            await self._refresh_controlled_token()
            response = await self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    async def _get(self, path: str, params: dict = None) -> dict | list:
        await self.ensure_controlled_token()
        url = f"{self.base_url}/api/v1{path}"
        t0 = time.perf_counter()
        response = await self._client.get(url, params=params or {})
        elapsed = (time.perf_counter() - t0) * 1000
        status = response.status_code
        logger.info("[Canvas] GET %s → %s (%.0fms)", path, status, elapsed)
        if not response.is_success:
            logger.warning("[Canvas] ERROR %s %s — body: %s", status, path, response.text[:200])
        if response.status_code == 401:
            await self._refresh_controlled_token()
            response = await self._client.get(url, params=params or {})
            status = response.status_code
            logger.info("[Canvas] GET %s -> %s (retry)", path, status)
            if not response.is_success:
                logger.warning("[Canvas] ERROR %s %s - body: %s", status, path, response.text[:200])
        response.raise_for_status()
        data = response.json()
        count = len(data) if isinstance(data, list) else "object"
        logger.debug("[Canvas] %s → %s items", path, count)
        return data

    async def _post(self, path: str, data: dict = None) -> dict:
        return await self._request_json("POST", path, json=data or {})

    async def get_courses(self, enrollment_type: str = None) -> list:
        params = {"per_page": 50}
        if enrollment_type:
            params["enrollment_type"] = enrollment_type
        return await self._get("/courses", params)

    async def get_course(self, course_id: int) -> dict:
        return await self._get(f"/courses/{course_id}")

    async def get_active_course_ids(self) -> list[tuple[int, str]]:
        courses = await self._get(
            "/courses",
            {
                "enrollment_state": "active",
                "state[]": ["available"],
                "per_page": 100,
            },
        )
        if not courses:
            return []
        return [
            (c["id"], c["name"])
            for c in courses
            if c.get("id") is not None and c.get("name") is not None
        ]

    async def get_assignments(
        self,
        course_ids: list[int] | None = None,
        active_courses: list[tuple[int, str]] | None = None,
        days_ahead: int = 7,
        per_page: int = 20,
    ):
        if active_courses is None:
            active_courses = await self.get_active_course_ids()
        if not course_ids:
            course_ids = [cid for (cid, _) in active_courses]

        now = datetime.now(timezone.utc)
        end_week = now + timedelta(days=days_ahead)

        async def fetch(course_id: int) -> list:
            try:
                assignments = await self._get(
                    f"/courses/{course_id}/assignments",
                    {"per_page": per_page, "bucket": "upcoming"},
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (403, 404):
                    return []
                raise
            result = []
            for a in assignments:
                a["course_id"] = course_id
                due_at = a.get("due_at")
                if not due_at:
                    result.append(a)
                    continue
                due_date = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
                if now <= due_date <= end_week:
                    result.append(a)
            return result

        per_course = await asyncio.gather(*[fetch(cid) for cid in course_ids])
        all_assignments = [a for batch in per_course for a in batch]
        all_assignments.sort(
            key=lambda a: (
                a.get("due_at") is None,
                a.get("due_at") or "9999-12-31T23:59:59Z",
            )
        )
        return {
            "assignments": all_assignments,
            "course_names": [name for (_, name) in active_courses],
        }

    async def get_assignment(self, course_id: int, assignment_id: int) -> dict:
        return await self._get(f"/courses/{course_id}/assignments/{assignment_id}")

    async def get_submissions(self, course_id: int, assignment_id: int) -> list:
        return await self._get(
            f"/courses/{course_id}/assignments/{assignment_id}/submissions",
            {"per_page": 50, "include[]": "user"},
        )

    async def get_students(self, course_id: int) -> list:
        return await self._get(
            f"/courses/{course_id}/users",
            {"enrollment_type[]": "student", "per_page": 50},
        )

    async def get_enrollments(self, course_id: int) -> list:
        return await self._get(f"/courses/{course_id}/enrollments", {"per_page": 50})

    async def get_modules(self, course_id: int) -> list:
        return await self._get(f"/courses/{course_id}/modules", {"per_page": 50})

    async def get_announcements(
        self,
        course_ids: list[int] | None = None,
        active_courses: list[tuple[int, str]] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        latest_only: bool = False,
        active_only: bool = True,
        per_page: int = 20,
    ):
        if active_courses is None:
            active_courses = await self.get_active_course_ids()

        params = {
            "per_page": per_page,
            "active_only": active_only,
            "latest_only": latest_only,
        }
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        params["context_codes[]"] = (
            [f"course_{cid}" for cid in course_ids]
            if course_ids
            else [f"course_{cid}" for (cid, _) in active_courses]
        )

        announcements = await self._get("/announcements", params)
        return {
            "announcements": announcements,
            "course_names": [name for (_, name) in active_courses],
        }

    async def get_discussions(self, course_id: int) -> list:
        return await self._get(f"/courses/{course_id}/discussion_topics", {"per_page": 50})

    async def get_grades(self, course_id: int, student_id: int) -> dict:
        return await self._get(
            f"/courses/{course_id}/enrollments",
            {"user_id": student_id, "include[]": "grades"},
        )

    async def get_current_user(self) -> dict:
        return await self._get("/users/self")

    async def get_quiz_list(self, course_id: int) -> list:
        return await self._get(f"/courses/{course_id}/quizzes", {"per_page": 50})

    async def get_quiz(self, course_id: int, quiz_id: int) -> dict:
        return await self._get(f"/courses/{course_id}/quizzes/{quiz_id}")


canvas = CanvasClient()
