# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Canvas LMS MCP Server for ESPOL (Escuela Superior Politécnica del Litoral). Exposes Canvas LMS data via the Model Context Protocol (MCP) over HTTP. El consumidor principal es el **Jelou Agent** — el agente de IA de la plataforma [Jelou](https://jelou.ai) que se conecta al endpoint `/mcp` para responder preguntas académicas de los usuarios vía WhatsApp u otros canales de Jelou.

## Commands

This project uses `uv` for dependency management.

```bash
# Install dependencies
uv sync

# Run the MCP HTTP server (production/integration mode)
uvicorn main:app --reload

# Run the standalone CLI agent (interactive terminal chatbot)
uv run python agent.py

# Run MCP dev inspector
mcp dev mcp_server.py
```

## Environment Variables

Required in `.env`:

```
CANVAS_BASE_URL=    # Canvas instance URL (e.g. https://espol.instructure.com)
ANTHROPIC_API_KEY=  # Only needed for agent.py
```

`CANVAS_API_TOKEN` is requested from the CLI when the app starts. It is not read from `.env` and is not persisted by the app.

## Architecture

The project has two independent execution modes that share the same Canvas data layer:

```
token_manager.py          TokenManager (in-memory, per-process)
      │                   Mints + auto-rotates a "fallback" Canvas access token per user
      │
canvas_client.py          CanvasClient (async httpx)
      │                   Raw Canvas REST API v1 calls
      │
mcp_server.py             FastMCP instance
      │                   @mcp.tool() wrappers that format responses as strings
      │                   _client() resolves canvas_token → TokenManager.get_active_token() first
      │
      ├── main.py          FastAPI app → mounts MCP at /mcp (streamable HTTP)
      │                    Used by external integrations (Jelou, Claude Desktop, etc.)
      │
      └── agent.py         Standalone Anthropic SDK loop
                           Re-imports the same tool functions from mcp_server.py
                           Used for local CLI testing
```

### Key design decisions

- `mcp_server.py` tools return **formatted strings** (not JSON) — the MCP protocol serializes them, and the LLM reads them as plain text.
- `agent.py` duplicates the tool definitions (TOOLS list + TOOL_MAP) to drive its own `client.messages.create()` loop. It directly calls the same async functions from `mcp_server.py` via `call_tool()`.
- `canvas_client.py` always creates a new `httpx.AsyncClient` per request (no persistent connection pool). All methods use `per_page=50` by default; Canvas paginates beyond that.
- `config.py` uses `pydantic-settings` — env vars are automatically loaded from `.env` and validated at import time.

- The Canvas token is requested by CLI at runtime, not loaded from `.env`.

### Token lifecycle (`token_manager.py`)

Canvas personal access tokens have no OAuth refresh flow, but a valid token can regenerate itself via `PUT /api/v1/users/self/tokens/{id}` (`{"regenerate": 1}`), which resets any expiration Canvas attached to it. `TokenManager` exploits this so a user only has to paste a token once:

- Each MCP tool call passes `canvas_token` (the token Jelou has saved for that user, the `api-aula` variable). `mcp_server._client()` resolves it through `token_manager.get_active_token(canvas_token)` *before* constructing `CanvasClient`.
- On first use for a given token, `TokenManager` mints a sibling "fallback" token (`POST /api/v1/users/self/tokens`) and stores it **in memory only**, keyed by `sha256(original_token)`.
- A background `asyncio.Task` regenerates that fallback token every 5 minutes (`REFRESH_INTERVAL_SECONDS`) for as long as the process is alive, so it never goes stale.
- State is per-process and not persisted to disk/DB — a redeploy/restart on Railway clears it and the next call re-mints a fallback from whatever `canvas_token` Jelou still has saved. Entries idle for >24h (`IDLE_TTL_SECONDS`) are pruned to bound memory growth.
- This assumes Jelou keeps sending the *same* original token string per user across calls (it does, via `saveInMemory`/`api-aula`) — that string is the lookup key into the in-memory store.

**Known limitation**: in-memory storage doesn't survive a Railway redeploy/restart and doesn't share state across multiple instances. See [TODO.md](TODO.md) for the plan to move this to a database when that becomes a real problem.

### MCP server endpoint

When running via `uvicorn main:app`, the MCP server is available at:
- `http://localhost:8000/mcp` — streamable HTTP transport
- `http://localhost:8000/health` — health check

## Integración con Jelou

El Jelou Agent se conecta al endpoint `/mcp` usando el transporte HTTP streamable de MCP. Jelou gestiona su propio historial de conversación (`messageHistory`) y llama a las tools de este servidor cuando el agente lo decide.

**Comportamiento esperado del agente Jelou:**
- Debe llamar herramientas Canvas (ej. `get_current_user`) *antes* de llamar `end_function`
- Cuando `end_function` se llama sin texto de respuesta, Jelou reporta `endFunctionFallback: "empty_output"` y no envía nada al usuario — esto indica que el agente terminó prematuramente
- El `saveInMemory` del JSON de Jelou guarda variables en su contexto; si contiene datos placeholder (`usuario@ejemplo.com`) significa que las tools Canvas nunca se ejecutaron

**Token de Canvas:**
- El token ingresado por CLI debe corresponder al usuario autenticado en Canvas para que `get_current_user` retorne datos reales
