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

### Decisión (sesión 2026-06-24): quedarse en memoria por ahora

Ya existe una base de datos Jelou provisionada (`jelou-espol`, plan NANO,
~$7.50/mes) con una colección `aulavirtualespol` (campos `user`, `token`)
que casi calza con `_UserTokenState`, pero le faltan dos campos para ser
1:1: `fallback_token_id` (number) y `refreshed_at` (number/date).

Recomendación: **no migrar todavía**. Mover `get_active_token()` de un
dict en memoria a la DB convierte un lookup gratis e in-process en un
round-trip de red en *cada* llamada a una tool MCP (se invoca por cada
request de cualquier usuario), y agrega un nuevo modo de falla: si la DB
duerme/tiene un hiccup, se rompe la resolución de token para todos en vez
de simplemente caer al token original. Migrar tiene sentido recién
cuando: (a) Railway corre más de una réplica, o (b) los redeploys son
frecuentes y algún usuario reporta tener que reenviar el token después de
uno — el trigger que ya menciona el TODO arriba.

Si llega ese momento, el mapeo sería:
- `user` (ya existe) = `sha256(canvas_token original)` (la `key` actual)
- `token` (ya existe) = `fallback_token`
- agregar `fallback_token_id` (number) y `refreshed_at` (number/date) vía
  `jelou databases collections update jelou-espol aulavirtualespol`
- reemplazar `self._states: dict` por lecturas/escrituras async contra el
  REST API de Datum (`https://gateway.jelou.ai/datum-db/jelou-espol-zegrvw/api`),
  manteniendo el `asyncio.Lock` por usuario para evitar regeneraciones
  concurrentes.

Nota: la restricción "No uses la base de datos" en `VALIDADOR_JELOU.md`
es sobre el flujo de validación inicial de Jelou (ese skill no debe tocar
Datum directamente) — no bloquea que `TokenManager` persista ahí como
otro proceso/propósito distinto.

### Descartado (sesión 2026-06-25): OAuth2 con refresh token

Se evaluó reemplazar el hack de regenerate-cada-5-min por el flujo OAuth2
nativo de Canvas (access token corto + refresh token de larga duración),
que es el mecanismo "correcto" para esto. Requiere una Developer Key
registrada en el Canvas de ESPOL por un admin de su TI — no se tiene ese
contacto, así que la puerta queda cerrada por ahora. **Se sigue con
PAT + fallback token regenerado cada 5 min en memoria**, sin cambios.
Si en algún momento aparece un contacto de TI/admin de Canvas en ESPOL,
retomar esta opción antes que migrar a BD — resuelve el problema de raíz
en vez de parchearlo.

Pendiente de explorar (no descartado, solo no abordado aún): ajustar el
intervalo de refresh fijo de 5 min — ver si se puede leer el `expires_at`
real que Canvas le pone al token, o cambiar a refresh perezoso (solo al
recibir 401), para reducir llamadas innecesarias a Canvas/BD.
