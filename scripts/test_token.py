"""
Prueba manual de un token de Canvas contra /users/self.
Pide el token de forma interactiva (no queda en argv ni en logs del chat).

Uso:
    uv run python scripts/test_token.py
"""
import asyncio
import getpass
import sys

sys.path.insert(0, ".")

from canvas_client import CanvasClient


async def main():
    token = getpass.getpass("Pega el token de Canvas (no se mostrará en pantalla): ").strip()
    if not token:
        print("No se ingresó ningún token.")
        return

    async with CanvasClient(token) as canvas:
        url = f"{canvas.base_url}/api/v1/users/self"
        response = await canvas._client.get(url)

    print(f"\nStatus code: {response.status_code}")
    print(f"Headers relevantes: {dict(response.headers).get('www-authenticate', '(sin header www-authenticate)')}")
    print(f"\nBody:\n{response.text[:1000]}")


if __name__ == "__main__":
    asyncio.run(main())
