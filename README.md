## Pre-Requisitos:
0. Aunque en el .env hay algo que dice Anthropic Key este NO ES NECESARIO solo era para pruebas.
1. Crearse una cuenta con la capa gratuita en Jelou https://jelou.ai/es/brain-studio  
2. Clonar el Repositorio https://github.com/CrisIntriago/aulavirtual-ia-taws 
3. Generar un token de Canva LMS en su cuenta de aula virtual para pruebas https://www.youtube.com/watch?v=cZ5cn8stjM0 (SOLO SE MUESTRA UNA VEZ COPIAR Y GUARDAR EN LUGAR SEGURO)
4. Descargar y configurar ngrok (el plan free) https://dashboard.ngrok.com/get-started/setup/windows

## Levantamiento del proyecto
1. Con el repositorio ya clonada ejecutar los siguientes comandos:
```
uv sync

uv run uvicorn main:app --reload
```

2. En otro terminal mientras el anterior se está ejecutando ejecutar (8000 ES EL MISMO PUERTO QUE SALE DE EJECUTAR EL COMANDO ANTERIOR POR DEFECTO FASTMCP USA EL PUERTO 8000, consultar el terminal):
```
ngrok http 8000
```

3. Esto creará un link a la derecha donde dice Forwarding       https://un-nombre-super-largo-en-ingles.ngrok.free.dev  -> http://localhost:8000, copiar ese link
4. En la plataforma de Jelou acceder a la herramienta Brain y arrastrar un nodo "AI Agent" a un workflow nuevo
5. Hacer click en el nodo y copiar y pegar el prompt que está en el repositorio clonado en el archivo AGENTE_JELOU.md  
6. Activar "Fecha y Hora Actual" en la sección "Herramientas"
7. En la misma sección hacer click donde dice "URL MCP" y pegar la url del paso 3 y agrgarle /mcp al final. EJ.: https://un-nombre-super-largo-en-ingles.ngrok.free.dev/mcp