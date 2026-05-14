## Pre-Requisitos:
0. Aunque en el .env hay algo que dice Anthropic Key este NO ES NECESARIO solo era para pruebas.
1. Crearse una cuenta con la capa gratuita en Jelou https://jelou.ai/es/brain-studio  
2. Hacer fork del Repositorio https://github.com/CrisIntriago/aulavirtual-ia-taws
	- Si nunca has realizado un fork: https://www.youtube.com/watch?v=b1s0_xcF9pk
	- Una vez hecho el fork clonar TU VERSIÓN DEL FORK del repositorio en local
	- Como el repositorio local está trackeando tu repositorio forkeado necesitarás configurar un upstream para halar los cambios de los demás
```
git remote add upstream https://github.com/CrisIntriago/aulavirtual-ia-taws
```

3. Generar un token de Canva LMS en su cuenta de aula virtual para pruebas https://www.youtube.com/watch?v=cZ5cn8stjM0 (SOLO SE MUESTRA UNA VEZ COPIAR Y GUARDAR EN LUGAR SEGURO)
4. Descargar y configurar ngrok (el plan free) https://dashboard.ngrok.com/get-started/setup/windows

## IMPORTANTE
Como se está trabajando en un fork SIEMPRE que vayas a comenzar a trabajar y SIEMPRE que vayas a subir cambio IMPORTANTE HACER LO SIGUIENTE (esto sincronizará tu repositorio con el repositorio original, nota que upstream/main es la rama objetivo del repo original y main a secas es la rama que sea que estes usando para sincronizarte con esta)
```
git fetch upstream
git checkout main
git merge upstream/main
git push origin main 
```

## Levantamiento del proyecto
1. Con el repositorio ya clonado y sincronizado ejecutar los siguientes comandos:
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

## Para subir los cambios
1. Se hace un push a tu repositorio forkeado con $ git push
2. En chrome en el repositorio original https://github.com/CrisIntriago/aulavirtual-ia-taws hacer click donde dice "Pull Requests" y click al boton para crear uno nuevo
3. Debajo del título hay subtítulo que indica que se puede "comparar entre forks o bifurcaciones" hacer click ahí
4. Del lado derecho seleccionar el repositorio que forkeaste con la rama que contiene los cambios que vas a subir
