# Spec FEAT-001a: Gestión del pool de vehículos

| Field | Value |
|-------|-------|
| Ticket | FEAT-001a |
| PRD | docs/daw/prd/prd-FEAT-001a.md |
| Tier | FEATURE |
| Date | 2026-08-02 |
| Spec loops | 0 |

## Summary

Backend FastAPI (capas router → service → repository, SQLAlchemy síncrono) que expone 6 endpoints de
administración del pool de vehículos, todos protegidos con HTTP Basic + rate limiting. Modelo de
datos `Vehiculo` con patente única y una máquina de estados (`activo` / `baja_temporal` /
`baja_definitiva`). Panel de administración en React + Vite que consume esa API. Repo greenfield: no
existe `backend/` ni `frontend/` todavía (confirmado en el Impact Check de PLAN).

## Coverage: PRD → blocks

| Requirement | Covered by |
|---|---|
| FR-01 (alta) | Block 1, Block 2, Block 3, Block 4 |
| FR-02 (modificar) | Block 1, Block 2, Block 3, Block 4 |
| FR-03 (baja temporal) | Block 2, Block 3, Block 4 |
| FR-04 (baja definitiva) | Block 2, Block 3, Block 4 |
| FR-05 (auth HTTP Basic) | Block 3 |
| FR-06 (reactivar) | Block 2, Block 3, Block 4 |
| FR-07 (no reactivar baja definitiva) | Block 2, Block 3 |
| FR-08 (patente única — alta) | Block 1 (constraint), Block 2 |
| FR-09 (patente única — modificación) | Block 2 |
| FR-10 (tipo válido — alta) | Block 2 |
| FR-11 (tipo válido — modificación) | Block 2 |
| — (listado admin, technical enabler, sin FR directo) | Block 3, Block 4 — ver nota en Block 3 |

## Dependencies between blocks

`1 → 2 → 3 → 4` (secuencial: cada capa necesita la anterior; el frontend necesita el contrato de API
de Block 3).

---

## Block 1 — Scaffolding backend + modelo + migración

**Files**
- `backend/requirements.txt` (new) — fastapi, uvicorn, sqlalchemy, psycopg2-binary, alembic,
  pydantic, python-dotenv, passlib[bcrypt], slowapi, pytest, httpx.
- `backend/.env.example` (new) — `DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`,
  `FRONTEND_ORIGIN`.
- `backend/alembic.ini` (new)
- `backend/alembic/env.py` (new) — lee `DATABASE_URL` desde el entorno.
- `backend/alembic/versions/0001_create_vehiculos.py` (new) — migración inicial.
- `backend/app/__init__.py`, `backend/app/core/__init__.py`,
  `backend/app/features/__init__.py`, `backend/app/features/vehiculos/__init__.py` (new, vacíos)
- `backend/app/main.py` (new) — instancia FastAPI mínima (se completa en Block 3).
- `backend/app/core/config.py` (new) — carga de variables de entorno (`pydantic-settings` o
  equivalente).
- `backend/app/core/database.py` (new) — engine y `SessionLocal` de SQLAlchemy (síncrono).
- `backend/app/features/vehiculos/models.py` (new) — modelo `Vehiculo`.
- `.gitignore` (modified) — agregar `venv/`, `backend/venv/`, `node_modules/`, `.env`,
  `frontend/dist/`, `.pytest_cache/`.

**Logic**

`config.py` expone `DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `FRONTEND_ORIGIN`
leídos con `python-dotenv`/`pydantic-settings`, sin defaults para secretos (falla al arrancar si
faltan). `database.py` crea el engine síncrono (`psycopg2`) y una función `get_db()` (dependency de
FastAPI que abre/cierra sesión por request). `models.py` define `Vehiculo` con
`TipoVehiculo(str, Enum)` = `auto|camioneta` y `EstadoVehiculo(str, Enum)` =
`activo|baja_temporal|baja_definitiva`.

**Data model**

Entidad `Vehiculo` (tabla `vehiculos`):

| Campo | Tipo | Constraints |
|---|---|---|
| `id` | `INTEGER` | PK, autoincrement |
| `patente` | `VARCHAR(10)` | NOT NULL, UNIQUE, índice |
| `tipo` | `VARCHAR(10)` (Enum `auto`/`camioneta`) | NOT NULL |
| `estado` | `VARCHAR(20)` (Enum `activo`/`baja_temporal`/`baja_definitiva`) | NOT NULL, DEFAULT `activo` |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, DEFAULT `now()` |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, DEFAULT `now()`, actualizado en cada UPDATE |

Índice explícito en `patente` (además del UNIQUE) porque es la columna por la que se busca en el
chequeo de unicidad de Block 2.

**Error handling**

Si `DATABASE_URL` u otra variable requerida falta al arrancar, la app debe fallar de forma explícita
(excepción al importar `config.py`), nunca arrancar con un default silencioso.

**Required tests**
- [ ] `test_config_carga_variables_requeridas` — con las env vars seteadas, `config.py` las expone
      correctamente.
- [ ] `test_config_falla_sin_database_url` — sin `DATABASE_URL`, falla al importar/instanciar.
- [ ] `test_migracion_crea_tabla_vehiculos` — `alembic upgrade head` contra una DB de test crea la
      tabla `vehiculos` con las columnas y constraints declaradas (incluye verificar el UNIQUE de
      `patente`).

**Completion criterion**

`alembic upgrade head` corre limpio contra una base de test; la tabla `vehiculos` existe con todas
las columnas, el `UNIQUE` en `patente` y el `DEFAULT` de `estado`. Los 3 tests de arriba pasan.

---

## Block 2 — Servicio + repositorio + schemas + errores tipados

**Files**
- `backend/app/features/vehiculos/schemas.py` (new) — `VehiculoCreate`, `VehiculoUpdate`,
  `VehiculoOut` (Pydantic).
- `backend/app/features/vehiculos/exceptions.py` (new) — `PatenteYaExisteError`,
  `TipoInvalidoError`, `TransicionEstadoInvalidaError`, `VehiculoNoEncontradoError` (excepciones de
  dominio, no HTTP).
- `backend/app/features/vehiculos/repository.py` (new) — acceso a datos.
- `backend/app/features/vehiculos/service.py` (new) — lógica de negocio.

**Logic**

`schemas.py`: `VehiculoCreate`/`VehiculoUpdate` validan `patente` (string, 1–10 caracteres, no
vacío) y `tipo` (`Literal["auto", "camioneta"]` — Pydantic ya rechaza cualquier otro valor, cubre
FR-10/FR-11 a nivel de esquema). `VehiculoOut` expone `id, patente, tipo, estado, created_at,
updated_at`.

`repository.py`: `crear(db, data)`, `obtener_por_id(db, id)`, `obtener_por_patente(db, patente)`,
`listar(db)`, `actualizar(db, vehiculo, data)`, `guardar(db, vehiculo)`. **`crear` y `actualizar`
capturan `sqlalchemy.exc.IntegrityError` en el `commit()` y la traducen a `PatenteYaExisteError`**
(mitigación TM-03 del threat model — cierra la condición de carrera TOCTOU entre el chequeo de
`service.py` y el `INSERT`/`UPDATE`: si dos altas concurrentes con la misma patente llegan a la DB,
la que pierde la carrera contra el `UNIQUE` constraint recibe el mismo error de dominio que el
chequeo preventivo, nunca un `IntegrityError` crudo).

`service.py`, un método por FR:
- `crear_vehiculo(db, data)` → valida patente única (`obtener_por_patente`, FR-08) antes de llamar a
  `repository.crear` (que además está protegido por la traducción de `IntegrityError` de arriba).
- `modificar_vehiculo(db, id, data)` → `obtener_por_id` (404 si no existe), valida patente única
  excluyendo el propio id (FR-09), llama a `repository.actualizar`.
- `dar_de_baja_temporal(db, id)` → solo si `estado == activo` (transición válida; si el vehículo
  tiene reservas activas, esa validación la agrega FEAT-001b sobre este mismo método — ver
  "Nota de dependencia" abajo).
- `dar_de_baja_definitiva(db, id)` → solo si `estado in (activo, baja_temporal)`.
- `reactivar(db, id)` → solo si `estado == baja_temporal`; si `estado == baja_definitiva` →
  `TransicionEstadoInvalidaError` (FR-07).
- `listar_vehiculos(db)` → `repository.listar`.

Cada método de escritura (`crear_vehiculo`, `modificar_vehiculo`, `dar_de_baja_temporal`,
`dar_de_baja_definitiva`, `reactivar`) loguea al final (nivel INFO) `{operación, vehiculo_id,
resultado, timestamp}` — **nunca** el header `Authorization` ni ningún dato de credenciales
(mitigación TM-04 del threat model: trazabilidad básica de operaciones administrativas; no requiere
atribución por persona porque hay una sola credencial compartida, fuera de alcance de este
sub-ticket).

> **Nota de dependencia (documentada también en el PRD):** `dar_de_baja_temporal` y
> `dar_de_baja_definitiva` en este ticket NO verifican reservas activas, porque el modelo de
> reservas no existe todavía. FEAT-001b, al construirse sobre este servicio, agrega esa validación
> (su FR-08) antes de llamar a estos mismos métodos. No es un gap de este spec: es el límite de
> alcance ya declarado en el PRD.

**Input validation**

Ver `schemas.py` arriba: `patente` no vacía, máx. 10 caracteres; `tipo` restringido a
`auto`/`camioneta` por `Literal`.

**Error handling**

| Error | Cuándo | Manejo |
|---|---|---|
| `PatenteYaExisteError` | Alta/modificación con patente duplicada (chequeo previo o `IntegrityError` traducido) | Propaga a Block 3, que la mapea a 409 |
| `TipoInvalidoError` | Defensivo — en la práctica Pydantic ya lo bloquea en `schemas.py`, pero `service.py` la lanza igual si algún caller interno pasa un tipo crudo no validado | Propaga a Block 3 → 400 |
| `TransicionEstadoInvalidaError` | Baja sobre estado que no lo permite, o reactivar una baja definitiva | Propaga a Block 3 → 409 |
| `VehiculoNoEncontradoError` | Operar sobre un id inexistente | Propaga a Block 3 → 404 |

**Required tests**
- [ ] `test_crear_vehiculo_ok` — AC-01
- [ ] `test_crear_vehiculo_patente_duplicada` — AC-08, incluye un test que fuerza el `IntegrityError`
      (dos inserts concurrentes o insert directo bypasseando el chequeo previo) y confirma que
      `repository.py` lo traduce a `PatenteYaExisteError`, no a una excepción cruda.
- [ ] `test_crear_vehiculo_tipo_invalido` — AC-10
- [ ] `test_modificar_vehiculo_ok` — AC-02
- [ ] `test_modificar_vehiculo_patente_duplicada` — AC-09
- [ ] `test_modificar_vehiculo_tipo_invalido` — AC-11
- [ ] `test_modificar_vehiculo_inexistente` — 404 de dominio
- [ ] `test_baja_temporal_ok` — AC-03
- [ ] `test_baja_definitiva_ok` — AC-04
- [ ] `test_reactivar_ok` — AC-06
- [ ] `test_reactivar_baja_definitiva_rechazado` — AC-07
- [ ] `test_listar_vehiculos` — soporte de Block 3/4

**Completion criterion**

Los 12 tests de servicio pasan; cada FR-01 a FR-11 tiene al menos un test cubriendo su AC
correspondiente (AC-01 a AC-11 del PRD).

---

## Block 3 — Router + autenticación HTTP Basic + wiring de FastAPI

**Files**
- `backend/app/core/security.py` (new) — dependency `HTTPBasic` de FastAPI.
- `backend/app/features/vehiculos/router.py` (new) — 6 endpoints.
- `backend/app/main.py` (modified) — incluye el router, configura CORS y el exception handler
  genérico.

**Logic**

`security.py`: dependency `verificar_admin(credentials: HTTPBasicCredentials = Depends(HTTPBasic()))`
que compara `credentials.username` contra `ADMIN_USERNAME` y `credentials.password` contra
`ADMIN_PASSWORD_HASH` con `bcrypt.checkpw`. **Si cualquiera de las dos falla, levanta el mismo
`HTTPException(401, detail="Credenciales inválidas", headers={"WWW-Authenticate": "Basic"})`** —
nunca un mensaje distinto según cuál fue el campo incorrecto (mitigación TM-05: evita enumeración de
usuario). Envuelto además con el rate limiter de `slowapi` (mitigación TM-02): máximo 5 intentos
fallidos por IP por minuto sobre cualquiera de los 6 endpoints; al superarlo, `429 Too Many
Requests`.

`router.py`: cada endpoint llama al método de `service.py` correspondiente dentro de un `try/except`
que mapea las excepciones de dominio de Block 2 a HTTP:

| Excepción de dominio | HTTP |
|---|---|
| `PatenteYaExisteError` | 409 |
| `TipoInvalidoError` | 400 |
| `TransicionEstadoInvalidaError` | 409 |
| `VehiculoNoEncontradoError` | 404 |

`main.py`: registra un `@app.exception_handler(Exception)` genérico que, para cualquier error no
capturado por el router, loguea el detalle completo del lado del servidor y responde
`{"detail": "Internal server error"}` con status 500 — **sin** volcar el mensaje de la excepción ni
el traceback al cliente (mitigación TM-03, complementa la traducción de `IntegrityError` en
Block 2). CORS: `allow_origins=[FRONTEND_ORIGIN]` (una sola URL desde env var, nunca `["*"]`).

> **Precondición de despliegue (mitigación TM-01, no es código — es un requisito documentado):**
> todo entorno que no sea desarrollo local **debe** servir el backend detrás de TLS. HTTP Basic
> envía la contraseña en Base64, que es trivialmente reversible — sin TLS equivale a texto plano en
> la red. Esto queda como precondición de infraestructura (relacionada con D-02 del PRD, todavía sin
> definir) y debe documentarse en el README de despliegue cuando D-02 se resuelva.

**API contract**

| Método + path | Auth | Request | Response éxito | Errores |
|---|---|---|---|---|
| `POST /vehiculos` | HTTP Basic | `VehiculoCreate` (`patente: str`, `tipo: "auto"\|"camioneta"`) | `201`, `VehiculoOut` | 400, 401, 409, 429 |
| `PUT /vehiculos/{id}` | HTTP Basic | `VehiculoUpdate` (mismos campos) | `200`, `VehiculoOut` | 400, 401, 404, 409, 429 |
| `PATCH /vehiculos/{id}/baja-temporal` | HTTP Basic | — | `200`, `VehiculoOut` | 401, 404, 409, 429 |
| `PATCH /vehiculos/{id}/baja-definitiva` | HTTP Basic | — | `200`, `VehiculoOut` | 401, 404, 409, 429 |
| `PATCH /vehiculos/{id}/reactivar` | HTTP Basic | — | `200`, `VehiculoOut` | 401, 404, 409, 429 |
| `GET /vehiculos` | HTTP Basic | — | `200`, `list[VehiculoOut]` | 401, 429 |

> `GET /vehiculos` no corresponde a ningún FR del PRD-FEAT-001a: es un habilitador técnico para que
> el panel admin (Block 4) pueda listar qué vehículos editar/dar de baja. El listado público para
> empleados es FR-01 de FEAT-001b, un endpoint distinto sin autenticación. Documentado explícitamente
> aquí para que `daw-module-verifier` no lo marque como scope creep (W-SPEC-01 esperado y
> justificado).

**Error handling**

Ver tabla de mapeo arriba, más el exception handler genérico de `main.py` para cualquier error no
anticipado, más el `429` del rate limiter.

**Required tests**
- [ ] `test_post_vehiculo_sin_credenciales_401`
- [ ] `test_post_vehiculo_credenciales_invalidas_401_mensaje_generico` — confirma que el mensaje es
      idéntico si falla el usuario o la contraseña
- [ ] `test_post_vehiculo_ok_201` — AC-01
- [ ] `test_post_vehiculo_patente_duplicada_409` — AC-08
- [ ] `test_post_vehiculo_tipo_invalido_400` — AC-10
- [ ] `test_put_vehiculo_ok_200` — AC-02
- [ ] `test_put_vehiculo_inexistente_404`
- [ ] `test_baja_temporal_200` — AC-03
- [ ] `test_baja_definitiva_200` — AC-04
- [ ] `test_reactivar_200` — AC-06
- [ ] `test_reactivar_baja_definitiva_409` — AC-07
- [ ] `test_get_vehiculos_200`
- [ ] `test_rate_limit_429_tras_intentos_fallidos` — TM-02
- [ ] `test_cors_solo_origen_configurado`
- [ ] `test_error_no_anticipado_500_sin_detalle_interno` — TM-03, fuerza una excepción no mapeada y
      confirma que la respuesta no incluye el mensaje interno

**Completion criterion**

Los 15 tests de endpoint pasan; cada AC-01 a AC-11 del PRD tiene al menos un test pasando en esta
capa (además del de Block 2); las 5 mitigaciones del threat model (TM-01 a TM-05) están reflejadas
en código o documentadas como precondición de despliegue (TM-01).

---

## Block 4 — Panel de administración (React + Vite)

**Files**
- `frontend/package.json`, `frontend/vite.config.js` (new)
- `frontend/.env.example` (new) — `VITE_API_URL`
- `frontend/src/main.jsx`, `frontend/src/App.jsx` (new)
- `frontend/src/api/client.js` (new) — instancia de axios; adjunta el header `Authorization: Basic
  ...` a partir de un estado de sesión en memoria (React state/context — **nunca**
  `localStorage`/`sessionStorage`).
- `frontend/src/features/vehiculos/LoginAdmin.jsx` (new) — formulario de usuario/contraseña que
  puebla la sesión en memoria que usa `client.js`.
- `frontend/src/features/vehiculos/VehiculosAdminPage.jsx` (new) — lista de vehículos + acciones
  (baja temporal, baja definitiva, reactivar).
- `frontend/src/features/vehiculos/VehiculoForm.jsx` (new) — alta/edición.
- `frontend/src/features/vehiculos/vehiculosApi.js` (new) — llamadas a los 6 endpoints de Block 3.

**Logic**

`App.jsx` mantiene el estado de sesión admin (`{username, password} | null`) en memoria (p. ej.
`useState` en el componente raíz, pasado por contexto). Sin sesión, se muestra `LoginAdmin.jsx`; con
sesión, `VehiculosAdminPage.jsx`. `client.js` lee la sesión del contexto y agrega el header
`Authorization` a cada request; si una respuesta es 401, limpia la sesión y vuelve a
`LoginAdmin.jsx`.

**Validaciones cliente** (no reemplazan al backend, que ya las re-valida — AGENTS.md): `patente`
requerida, `tipo` restringido a los dos valores permitidos (select, no input libre).

**Estados de UI explícitos** (todas las acciones async de `VehiculosAdminPage.jsx` y
`VehiculoForm.jsx`): loading (spinner/botón deshabilitado mientras la request está en curso), éxito
(mensaje o toast tras completar), error (mensaje legible mapeado desde la respuesta del backend:
400/401/404/409/429), nunca una falla silenciosa o una UI bloqueada.

**Error handling**

`vehiculosApi.js` propaga el error de axios con el `status` y el `detail` del backend;
`VehiculosAdminPage.jsx`/`VehiculoForm.jsx` lo traducen a un mensaje visible según el código (409
patente duplicada, 400 tipo inválido, 404 no encontrado, 401 sesión inválida → vuelve a login, 429
demasiados intentos).

**Required tests**
- [ ] `LoginAdmin.test.jsx` — envía credenciales, puebla la sesión; en 401 muestra el error y no
      puebla la sesión
- [ ] `VehiculoForm.test.jsx` — no envía si falta `patente`; `tipo` solo permite los 2 valores;
      muestra el error del backend si la request falla
- [ ] `VehiculosAdminPage.test.jsx` — renderiza la lista desde `GET /vehiculos`; dispara baja
      temporal/definitiva/reactivar; muestra loading mientras la acción está en curso y error si
      falla

**Completion criterion**

Los tests de componente pasan. Smoke test manual del camino feliz (login → alta → edición → baja
temporal → reactivar → baja definitiva) contra el backend de Block 3 corriendo localmente.

---

## Final verification

- `alembic upgrade head` aplica limpio; los 4 bloques tienen sus tests pasando (12 + 15 + 3 archivos
  de test de componente, más los 3 de Block 1).
- Cada FR-01 a FR-11 del PRD mapea a al menos un bloque (tabla de cobertura arriba); cada AC-01 a
  AC-11 tiene al menos un test pasando.
- Las 5 mitigaciones del threat model (`docs/daw/security/threat-FEAT-001a.md`) están implementadas
  o documentadas como precondición (TM-01).
- `daw-security-sast` corre limpio sobre el código de los 4 bloques antes de pasar a VERIFY.
- Rollback: `alembic downgrade -1` revierte la migración de Block 1; no hay migración de datos
  (tabla nueva, sin datos previos que preservar).
