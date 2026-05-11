from fastapi import FastAPI
from mcp_server import mcp

app = FastAPI(
    title="Canvas LMS MCP Server",
    description="Servidor MCP para interactuar con Canvas LMS de la ESPOL",
    version="0.1.0",
)

app.mount("/mcp", mcp.streamable_http_app())


@app.get("/health")
async def health():
    return {"status": "ok", "server": "canvas-lms-espol"}
    