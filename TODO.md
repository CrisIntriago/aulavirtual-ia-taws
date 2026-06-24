# TODO

## Migrar TokenManager de memoria a base de datos

`token_manager.py` mantiene el fallback token (auto-rotado cada 5 min vía
regenerate de Canvas) **solo en memoria del proceso**, keyed por
`sha256(canvas_token original)`.

Limitaciones actuales (ver discusión en sesión 2026-06-24):
- Se pierde en cada redeploy/restart de Railway (incluye scale-to-zero) —
  el usuario vuelve a depender de que su token original siga vivo, o
  tiene que repetir el flujo de `VALIDADOR_JELOU.md`.
- No escala a múltiples instancias/réplicas — cada proceso tiene su
  propio diccionario, puede generar fallback tokens duplicados en Canvas
  para el mismo usuario.
- Memoria crece con el uso (mitigado parcialmente con `IDLE_TTL_SECONDS`).

Para resolverlo: persistir `{key, fallback_token, fallback_token_id,
refreshed_at}` en una base de datos en vez de en `_states` (dict en
memoria). Esto requiere:
1. Decidir motor de DB (¿ya hay algo provisto en Railway?).
2. Reabrir/ajustar la restricción "No uses la base de datos" en
   `VALIDADOR_JELOU.md` — esa restricción es para el flujo de
   *validación inicial* del token, no necesariamente debería bloquear
   que el TokenManager (otro proceso, otro propósito) persista ahí.
3. Migrar `_UserTokenState` a lecturas/escrituras async contra esa DB,
   manteniendo el lock por usuario para evitar regeneraciones
   concurrentes que invaliden el token a mitad de un request.

No es urgente mientras se corra una sola instancia de Railway y los
redeploys sean poco frecuentes — pero es la causa más probable si en el
futuro los usuarios reportan que "se les pide el token de nuevo" después
de un deploy.
