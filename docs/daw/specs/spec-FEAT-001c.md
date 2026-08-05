# Spec FEAT-001c: Consulta y creación de reservas

| Field | Value |
|-------|-------|
| Ticket | FEAT-001c |
| PRD | docs/daw/prd/prd-FEAT-001c.md |
| Tier | FEATURE |
| Date | 2026-08-05 |
| Spec loops | 1 |

## Summary

Nuevo feature `reservas` en backend (FastAPI, capas router → service → repository, SQLAlchemy
síncrono, sin autenticación) que expone 3 endpoints públicos: listar vehículos del pool, consultar
disponibilidad para un rango de fechas, y crear una reserva. Modelo `Reserva` con FK a
`Vehiculo.id`, campo `estado` (`activa`/`cancelada`) para soportar ya la definición de "reserva
activa" que usará FEAT-001d/e, e índice compuesto `(vehiculo_id, fecha_inicio, fecha_fin)`. La
prevención de solapamientos concurrentes usa `SELECT ... FOR UPDATE` sobre las reservas activas del
vehículo dentro de la misma transacción del alta (mandato explícito de AGENTS.md), no el patrón de
`IntegrityError` de FEAT-001a (que resuelve igualdad, no solapamiento de rangos). Vista pública en
React sin librería de ruteo: `App.jsx` agrega un tercer estado de vista junto a
login/panel-admin, mostrado por defecto sin sesión.

## Coverage: PRD → blocks

| Requirement | Covered by |
|---|---|
| FR-01 (listado de vehículos) | Block 1, Block 3, Block 4 |
| FR-02 (crear reserva) | Block 1, Block 2, Block 3, Block 4 |
| FR-03 (validar solapamiento) | Block 1, Block 2, Block 3 |
| FR-04 (consultar disponibilidad) | Block 2, Block 3, Block 4 |
| FR-05 (rechazar reserva sobre vehículo no activo) | Block 2, Block 3 |
| NFR-01 (reserva en <1 min, sin capacitación) | Strategy: formulario de un solo paso, campos mínimos, sin flujo de autenticación previo (Block 4) |
| NFR-02 (disponibilidad <2s p95) | Strategy: consulta indexada por `(vehiculo_id, fecha_inicio, fecha_fin)` (Block 1), sin joins innecesarios (Block 2) |
| NFR-03 (prevenir race conditions) | Block 1 (índice), Block 2 (`SELECT FOR UPDATE`), Block 3 (test de concurrencia) |

## Dependencies between blocks

`1 → 2 → 3 → 4` (secuencial: cada capa necesita la anterior; el frontend necesita el contrato de API
de Block 3).

---

## Block 1 — Modelo `Reserva` + migración

**Files**
- `backend/app/features/reservas/__init__.py` (new, vacío)
- `backend/app/features/reservas/models.py` (new) — modelo `Reserva` + enum `EstadoReserva`.
- `backend/app/features/reservas/exceptions.py` (new) — jerarquía de excepciones de dominio (solo
  la clase base y las que este bloque necesita declarar; Block 2 agrega el resto).
- `backend/alembic/versions/0002_create_reservas.py` (new) — migración.
- `backend/alembic/env.py` (modified) — agrega `import app.features.reservas.models  # noqa: F401`
  junto al import ya existente de `vehiculos.models`, tal como anticipa el comentario de
  `backend/app/core/database.py`.

**Logic**

`models.py` define `EstadoReserva(str, Enum)` = `activa|cancelada`, siguiendo el mismo estilo que
`TipoVehiculo`/`EstadoVehiculo` de `vehiculos/models.py` (`Enum(..., native_enum=False,
create_constraint=True)`: CHECK constraint en vez de tipo nativo de Postgres, para mantener
consistencia de convención en todo el proyecto). El campo `estado` existe desde este ticket aunque
el endpoint de cancelación sea de FEAT-001d — es lo que hace evaluable la definición de "reserva
activa" del PRD (período futuro/en curso y `estado == activa`) ya en este sub-ticket.

`exceptions.py`: clase base `ReservaDomainError(Exception)`, sin conocer HTTP (mismo patrón que
`vehiculos/exceptions.py`).

**Data model**

Entidad `Reserva` (tabla `reservas`):

| Campo | Tipo | Constraints |
|---|---|---|
| `id` | `INTEGER` | PK, autoincrement |
| `vehiculo_id` | `INTEGER` | NOT NULL, FK → `vehiculos.id` |
| `nombre_empleado` | `VARCHAR(200)` | NOT NULL |
| `legajo` | `VARCHAR(20)` | NOT NULL |
| `licencia` | `VARCHAR(20)` | NOT NULL |
| `fecha_inicio` | `TIMESTAMP WITH TIME ZONE` | NOT NULL |
| `fecha_fin` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, CHECK `fecha_fin > fecha_inicio` |
| `destino` | `VARCHAR(200)` | NOT NULL |
| `estado` | `VARCHAR(10)` (Enum `activa`/`cancelada`) | NOT NULL, DEFAULT `activa` |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, DEFAULT `now()` |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, DEFAULT `now()`, actualizado en cada UPDATE |

Índice compuesto explícito `(vehiculo_id, fecha_inicio, fecha_fin)` — es la combinación de columnas
por la que se consulta tanto el chequeo de solapamiento (Block 2) como la disponibilidad (Block 2),
mandato explícito de AGENTS.md ("crear índices en... vehículo + fechas para las búsquedas de
disponibilidad").

**Error handling**

Ninguno propio de este bloque (sin lógica ejecutable todavía, solo modelo + migración). La
migración debe poder aplicarse limpio sobre una base que ya tiene la tabla `vehiculos` (Block 1 de
FEAT-001a), sin romperla.

**Required tests**
- [ ] `test_migracion_crea_tabla_reservas` — `alembic upgrade head` contra una DB de test crea la
      tabla `reservas` con todas las columnas, el CHECK `fecha_fin > fecha_inicio`, la FK a
      `vehiculos.id`, y el índice compuesto `(vehiculo_id, fecha_inicio, fecha_fin)`.
- [ ] `test_migracion_reservas_requiere_vehiculo_existente` — insertar una reserva con
      `vehiculo_id` inexistente viola la FK a nivel de base (confirma que la constraint está
      activa, no solo declarada).

**Completion criterion**

`alembic upgrade head` corre limpio partiendo de la migración `0001` de FEAT-001a; la tabla
`reservas` existe con todas las columnas, el CHECK, la FK y el índice compuesto. Los 2 tests de
arriba pasan.

---

## Block 2 — Servicio + repositorio + schemas + prevención de solapamientos

**Files**
- `backend/app/features/reservas/schemas.py` (new) — `ReservaCreate`, `ReservaOut`,
  `VehiculoPublico`, `DisponibilidadOut` (Pydantic).
- `backend/app/features/reservas/exceptions.py` (modified) — agrega
  `VehiculoNoEncontradoError`, `VehiculoNoActivoError`, `ReservaSolapadaError`.
- `backend/app/features/reservas/repository.py` (new) — acceso a datos.
- `backend/app/features/reservas/service.py` (new) — lógica de negocio.

**Logic**

`schemas.py`:
- `ReservaCreate` valida: `nombre_empleado`/`legajo`/`licencia`/`destino` (string, 1–200 u 1–20
  caracteres según campo, no vacíos), `vehiculo_id` (int, > 0), `fecha_inicio`/`fecha_fin`
  (datetime, **timezone-aware obligatorio** — mitigación TM-C-03 del threat model: un
  `field_validator` rechaza explícitamente cualquier datetime naive, con un mensaje descriptivo
  ("fecha_inicio/fecha_fin deben incluir zona horaria"), para que la comparación de solapamiento en
  `repository.py` nunca compare un naive contra un aware ni se preste a confusión de zona horaria).
  Un `model_validator(mode="after")` rechaza si `fecha_fin <= fecha_inicio`, levantando un
  `ValueError` con mensaje descriptivo — Pydantic lo traduce a 422 con el detalle del campo, mismo
  criterio ya documentado en FEAT-001a para validaciones a nivel de schema (AC-04 queda cubierto en
  esta capa, sin necesitar una excepción de dominio propia).
- `ReservaOut` expone `id, vehiculo_id, nombre_empleado, legajo, licencia, fecha_inicio, fecha_fin,
  destino, estado, created_at, updated_at`.
- `VehiculoPublico` expone solo `patente, tipo` (FR-01/AC-01 no piden más que eso; evita filtrar el
  campo `estado` administrativo a la vista pública).
- `DisponibilidadOut` expone `vehiculo_id, patente, tipo, disponible: bool`.

`repository.py`: `crear(db, data)` (INSERT + commit + refresh, sin traducción de `IntegrityError`
porque acá no hay ningún `UNIQUE` que pueda violarse — la protección contra solapamiento ya se hizo
antes de llegar a este método, ver más abajo), `listar_activas_solapadas_con_lock(db, vehiculo_id,
fecha_inicio, fecha_fin)` (ejecuta `SELECT ... FROM reservas WHERE vehiculo_id = :id AND estado =
'activa' AND fecha_inicio < :fecha_fin AND fecha_fin > :fecha_inicio FOR UPDATE` — el `FOR UPDATE`
bloquea las filas de reservas activas solapables de ESE vehículo hasta que la transacción que las
lee haga commit o rollback, cerrando la ventana de carrera; mitigación NFR-03/AC-06, mandato
explícito de AGENTS.md), `listar_solapadas_en_rango(db, fecha_inicio, fecha_fin)` (sin `FOR UPDATE`,
de solo lectura, usada por el endpoint de disponibilidad — no participa de ninguna escritura).

`service.py`:
- `listar_vehiculos_pool(db)` → llama a `vehiculos.repository.listar(db)` (import de solo lectura
  entre features, ya declarado como dependencia D-01 del PRD) y proyecta a `VehiculoPublico`
  (FR-01).
- `crear_reserva(db, data)` → dentro de la misma transacción de sesión: (1) `vehiculo =
  vehiculos.repository.obtener_por_id(db, data.vehiculo_id)`; si es `None` →
  `VehiculoNoEncontradoError`. (2) si `vehiculo.estado != EstadoVehiculo.activo` →
  `VehiculoNoActivoError` (decisión de esta spec, ver nota abajo). (3)
  `repository.listar_activas_solapadas_con_lock(...)`; si la lista no está vacía →
  `ReservaSolapadaError` (FR-03/AC-05). (4) si no hay solapamiento, `repository.crear(db, data)`
  (FR-02/AC-02), que hace el `INSERT` y el `commit` dentro de la misma transacción que sostenía el
  lock — el `FOR UPDATE` se libera recién en ese commit, así que una segunda solicitud concurrente
  que estaba bloqueada en el paso (3) reevalúa la lista de solapadas DESPUÉS de ver la fila recién
  insertada y encuentra el conflicto (AC-06).
- `consultar_disponibilidad(db, fecha_inicio, fecha_fin)` → `vehiculos.repository.listar(db)` +
  `repository.listar_solapadas_en_rango(db, fecha_inicio, fecha_fin)`; por cada vehículo, marca
  `disponible = vehiculo.id no está entre los solapados` (FR-04/AC-07).

Cada llamada a `crear_reserva` loguea al final (nivel INFO, tras el resultado, sea éxito o rechazo)
`{operación="crear_reserva", vehiculo_id, legajo, resultado, ip_origen, timestamp}` — mitigación
TM-C-04 del threat model: sin autenticación, es el único rastro disponible para investigar abusos o
disputas; `ip_origen` se agrega acá a diferencia del logging de FEAT-001a porque ahí sí había una
credencial que identificaba al actor. **Nunca** loguea `nombre_empleado`/`licencia` (dato de más
detalle del que hace falta para trazabilidad operativa, y reduce la superficie de PII en los logs).

> **FR-05/AC-08:** `crear_reserva` rechaza vehículos que no estén en estado `activo`
> (`baja_temporal`/`baja_definitiva` quedan fuera). Agregado al PRD en un corrective loop durante
> PLAN (PRD loops 1): un vehículo dado de baja no debería poder reservarse aunque todavía no tenga
> reservas activas bloqueándolo — la protección inversa (bloquear la baja si hay reservas activas)
> es FEAT-001e, pero esta dirección (no reservar un vehículo ya de baja) le corresponde a este
> ticket porque es quien crea la reserva.

**Input validation**

Ver `schemas.py` arriba: todos los campos de texto no vacíos con longitud máxima; `fecha_fin >
fecha_inicio` a nivel de schema; `vehiculo_id` debe ser un entero positivo (validación de tipo; la
existencia real se valida en `service.py`, no es responsabilidad de Pydantic).

**Error handling**

| Error | Cuándo | Manejo |
|---|---|---|
| `VehiculoNoEncontradoError` | `vehiculo_id` no corresponde a ningún vehículo | Propaga a Block 3 → 404 |
| `VehiculoNoActivoError` | El vehículo existe pero no está `activo` (FR-05/AC-08) | Propaga a Block 3 → 409 |
| `ReservaSolapadaError` | Existe otra reserva activa solapada (chequeo previo o carrera resuelta por el lock) | Propaga a Block 3 → 409 |
| Validación de schema (campo faltante, `fecha_fin <= fecha_inicio`) | Pydantic, antes de llegar a `service.py` | 422 automático de FastAPI, con el detalle del campo — mismo criterio documentado en FEAT-001a para `tipo` inválido |

**Required tests**
- [ ] `test_listar_vehiculos_pool` — FR-01/AC-01, devuelve solo `patente`/`tipo`
- [ ] `test_crear_reserva_ok` — AC-02
- [ ] `test_crear_reserva_vehiculo_inexistente` — 404 de dominio
- [ ] `test_crear_reserva_vehiculo_no_activo` — AC-08, vehículo en `baja_temporal`, rechazado
- [ ] `test_reserva_create_rechaza_fecha_fin_menor_o_igual` — F-SPEC-16: instancia `ReservaCreate`
      directamente con `fecha_fin <= fecha_inicio` y confirma que Pydantic lo rechaza a nivel de
      schema (`ValidationError`), sin necesidad de levantar el servidor — evidencia de que la
      validación de AC-04 vive en la capa correcta y es alcanzable sin pasar por HTTP
- [ ] `test_reserva_create_rechaza_fecha_naive` — TM-C-03, instancia `ReservaCreate` con
      `fecha_inicio`/`fecha_fin` sin timezone y confirma el rechazo explícito
- [ ] `test_crear_reserva_loguea_operacion_sin_pii` — TM-C-04, confirma que el log de
      `crear_reserva` incluye `vehiculo_id`/`legajo`/`resultado`/`ip_origen` y **no** incluye
      `nombre_empleado` ni `licencia`
- [ ] `test_crear_reserva_solapada_rechazada` — AC-05, dos reservas para el mismo vehículo con
      períodos que se cruzan
- [ ] `test_crear_reserva_periodos_no_solapados_ok` — dos reservas para el mismo vehículo con
      períodos disjuntos, ambas se crean (evita un falso positivo del chequeo de solapamiento)
- [ ] `test_crear_reserva_concurrencia_solo_una_confirmada` — AC-06/NFR-03, dispara dos
      `crear_reserva` concurrentes (dos sesiones/threads o conexiones separadas) para el mismo
      vehículo y período solapado; confirma que solo una persiste en la tabla y la otra levanta
      `ReservaSolapadaError`. Es la evidencia de que el `SELECT FOR UPDATE` efectivamente serializa
      el acceso, no solo que el chequeo lógico existe.
- [ ] `test_consultar_disponibilidad` — FR-04/AC-07, un vehículo con reserva solapando el rango
      consultado aparece `disponible=False`, uno sin solapamiento aparece `disponible=True`

**Completion criterion**

Los 11 tests de servicio pasan; FR-01 a FR-05 y NFR-03 tienen al menos un test cubriendo su AC
correspondiente (AC-01, AC-02, AC-05, AC-06, AC-07, AC-08 del PRD; AC-04 tiene evidencia tanto acá
—`test_reserva_create_rechaza_fecha_fin_menor_o_igual`— como en Block 3 a nivel HTTP; AC-03 se
cubre a nivel de schema en Block 3, ver ahí); las mitigaciones TM-C-03 y TM-C-04 del threat model
tienen su test correspondiente.

---

## Block 3 — Router + wiring de FastAPI

**Files**
- `backend/app/features/reservas/router.py` (new) — 3 endpoints.
- `backend/app/main.py` (modified) — incluye el nuevo router.

**Logic**

`router.py`: `APIRouter(prefix="/reservas", tags=["reservas"])`, **sin** `Depends(verificar_admin)`
en ningún endpoint (a diferencia de `vehiculos.router`, que sí lo usa en los 6 suyos) — este feature
es público por diseño del PRD (FR-01 a FR-04 no mencionan autenticación, y el PRD marca
"Autenticación... cubierto por FEAT-001a" como Out of Scope). Diccionario `_MAPEO_ERRORES_HTTP` que
traduce `VehiculoNoEncontradoError`→404, `VehiculoNoActivoError`→409, `ReservaSolapadaError`→409,
mismo patrón `_a_http` que `vehiculos.router`.

**Rate limiting general (mitigación TM-C-02 del threat model):** los 3 endpoints usan el mismo
`slowapi`/`limits` ya presente en el proyecto (`backend/app/core/security.py` lo usa para
`vehiculos`), pero acá limita TODAS las requests por IP, no solo los intentos fallidos (no hay
"fallos de auth" en un feature sin auth). Un `Limiter` propio en `reservas/router.py` (o compartido
vía `backend/app/core/rate_limit.py` si se prefiere extraer, a criterio del implementador):
`POST /reservas` máx. 10 altas por IP por hora (`10/hour`); `GET /reservas/disponibilidad` y
`GET /reservas/vehiculos` con un límite más laxo de solo lectura (`60/minute`). Al superarse,
`429 Too Many Requests`, mismo `HTTPException` de status y mensaje que el patrón ya usado en
`vehiculos`.

`main.py`: agrega `from app.features.reservas.router import router as reservas_router` y
`app.include_router(reservas_router)` junto al de `vehiculos`. El exception handler genérico y el
CORS ya configurados en FEAT-001a cubren este router nuevo sin cambios.

> **Precondición de despliegue (mitigación TM-C-01, no es código — misma precondición que TM-01 de
> FEAT-001a):** todo entorno que no sea desarrollo local debe servir el backend detrás de TLS. Acá
> el dato en juego es PII de empleados (legajo, licencia), no solo una credencial administrativa —
> el requisito es el mismo, pero el impacto de incumplirlo es mayor. No se duplica el mecanismo, se
> reafirma la misma precondición ya declarada en `docs/daw/security/threat-FEAT-001a.md`.

**API contract**

| Método + path | Auth | Request | Response éxito | Errores |
|---|---|---|---|---|
| `GET /reservas/vehiculos` | Ninguna | — | `200`, `list[VehiculoPublico]` | `429` |
| `GET /reservas/disponibilidad` | Ninguna | Query params `desde: datetime`, `hasta: datetime` | `200`, `list[DisponibilidadOut]` | `422` si faltan/son inválidos los query params; `429` |
| `POST /reservas` | Ninguna | `ReservaCreate` (`nombre_empleado, legajo, licencia, vehiculo_id, fecha_inicio, fecha_fin, destino`) | `201`, `ReservaOut` | `404, 409, 422, 429` |

> `GET /reservas/vehiculos` es un endpoint DISTINTO de `GET /vehiculos` (Block 3 de FEAT-001a, que
> exige HTTP Basic). Coexisten sin colisión porque tienen paths distintos (`/reservas/vehiculos` vs
> `/vehiculos`) — documentado así desde el PRD de FEAT-001a (nota en su spec, Block 3) para que
> `daw-module-verifier` no lo marque como scope creep ni como duplicado.

**Error handling**

Ver tabla de mapeo arriba; los 422 de validación de schema (campo faltante en `POST /reservas`,
`fecha_fin <= fecha_inicio`, query params inválidos en `/disponibilidad`) los genera FastAPI/Pydantic
automáticamente, antes de que el código de `router.py` se ejecute — cubre AC-03 y AC-04 del PRD. El
`429` de rate limiting (TM-C-02) aplica a los 3 endpoints por igual, con el límite específico de
cada uno documentado en **Logic** arriba.

**Required tests**
- [ ] `test_get_vehiculos_pool_200` — AC-01
- [ ] `test_post_reserva_ok_201` — AC-02
- [ ] `test_post_reserva_campo_faltante_422` — AC-03
- [ ] `test_post_reserva_fecha_fin_menor_o_igual_422` — AC-04
- [ ] `test_post_reserva_vehiculo_inexistente_404`
- [ ] `test_post_reserva_vehiculo_no_activo_409` — AC-08
- [ ] `test_post_reserva_solapada_409` — AC-05
- [ ] `test_get_disponibilidad_200` — AC-07
- [ ] `test_get_disponibilidad_query_invalido_422`
- [ ] `test_post_reserva_rate_limit_429` — TM-C-02, tras 10 altas en la misma hora desde la misma
      IP, la 11ª devuelve 429
- [ ] `test_get_disponibilidad_rate_limit_429` — TM-C-02, tras 60 consultas en el mismo minuto
      desde la misma IP, la 61ª devuelve 429

**Completion criterion**

Los 11 tests de endpoint pasan; cada AC-01 a AC-08 del PRD tiene al menos un test pasando en esta
capa (sumado a los de Block 2 para AC-06); las 4 mitigaciones del threat model (TM-C-01 a TM-C-04)
están reflejadas en código o documentadas como precondición de despliegue (TM-C-01); no se rompe
ningún test existente de `vehiculos` (el `GET /vehiculos` administrativo sigue exigiendo HTTP Basic
sin cambios).

---

## Block 4 — Vista pública de reservas (React + Vite)

**Files**
- `frontend/src/features/reservas/reservasApi.js` (new) — llamadas a los 3 endpoints de Block 3.
- `frontend/src/features/reservas/ReservasPublicPage.jsx` (new) — listado de vehículos + formulario
  de reserva + resultado de disponibilidad.
- `frontend/src/features/reservas/ReservaForm.jsx` (new) — formulario de alta de reserva.
- `frontend/src/App.jsx` (modified) — agrega la vista pública sin librería de ruteo (decisión de
  PLAN, ver nota abajo).

**Logic**

`App.jsx`: hoy alterna únicamente entre `LoginAdmin`/`VehiculosAdminPage` según `session`. Se agrega
un tercer estado local, p. ej. `const [vista, setVista] = useState("reservas")`, con un control
simple (un par de links/botones "Reservar un vehículo" / "Acceso administrador") para alternar entre
`ReservasPublicPage` (vista pública, sin sesión) y el flujo existente de login/panel admin. La vista
pública es la que se muestra por defecto al entrar sin sesión — el login de admin pasa a estar detrás
de un botón explícito, no en la vista inicial. Sin `react-router` ni ninguna dependencia nueva
(decisión tomada en PLAN: proyecto chico, agregar una librería de ruteo para dos pantallas es
sobre-ingeniería; si FEAT-001d/e necesitan más pantallas, se reevalúa ahí).

`reservasApi.js`: mismo patrón que `vehiculosApi.js` (`propagarError` tipado con `.status`/`.detail`
sobre `apiClient` de `client.js` — SIN el header `Authorization`, porque estos 3 endpoints no lo
requieren; `apiClient` ya no agrega el header si `sesionActual` es `null`, que es el caso normal
para un empleado sin loguearse).

`ReservasPublicPage.jsx`: al montar, pide `GET /reservas/vehiculos` y los muestra en una lista;
permite elegir un vehículo y un rango de fechas para consultar `GET /reservas/disponibilidad` antes
de abrir `ReservaForm.jsx` con ese vehículo/rango precargado (mejora de UX no exigida por AC, pero
consistente con NFR-01 de completar la reserva en <1 minuto: evita reservar sobre un vehículo que ya
se sabe no disponible).

`ReservaForm.jsx`: campos `nombre_empleado, legajo, licencia, vehiculo_id (select), fecha_inicio,
fecha_fin, destino`; validación cliente de campos requeridos y `fecha_fin > fecha_inicio` (AGENTS.md:
"verificar que la fecha/hora de fin sea posterior a la de inicio antes de enviar el formulario" —
no reemplaza la validación del backend, que se re-verifica igual). Estados explícitos de loading/
éxito/error en el envío (mismo patrón ya usado en `VehiculoForm.jsx`: `role="status"` para éxito,
`role="alert"` para error, spinner/disabled durante el request). Mapea 404/409/422 del backend a
mensajes legibles (`MENSAJES_ERROR`, mismo patrón que `vehiculos`).

**Error handling**

`reservasApi.js` propaga `status`/`detail`; `ReservaForm.jsx` los traduce: 404 (vehículo no existe,
caso raro en la práctica porque el select solo ofrece vehículos ya listados, pero puede pasar por
una carrera con una baja de admin), 409 con dos causas distintas (vehículo no activo / solapamiento
— el mensaje usa el `detail` del backend, que ya distingue cuál de las dos fue, en vez de un genérico
"conflicto"), 422 (validación de campos, incluida la de fecha).

**Required tests**
- [ ] `ReservasPublicPage.test.jsx` — renderiza la lista desde `GET /reservas/vehiculos`; consulta
      disponibilidad y refleja `disponible`/`no disponible` por vehículo; abre `ReservaForm` con el
      vehículo elegido
- [ ] `ReservaForm.test.jsx` — no envía si falta un campo obligatorio; no envía si `fecha_fin <=
      fecha_inicio` (validación cliente); muestra el mensaje de éxito tras `201`; muestra el error
      correspondiente ante 404/409/422 del backend

**Completion criterion**

Los tests de componente pasan. Smoke test manual del camino feliz (abrir la app sin sesión → ver
vista pública de reservas → elegir vehículo → consultar disponibilidad → completar y enviar reserva
→ ver confirmación) contra el backend de Block 3 corriendo localmente.

---

## Final verification

- `alembic upgrade head` aplica limpio sobre la migración `0001` de FEAT-001a; los 4 bloques tienen
  sus tests pasando (2 de Block 1 + 11 de Block 2 + 11 de Block 3, más los de componente de Block
  4).
- Cada FR-01 a FR-05 y NFR-01 a NFR-03 del PRD mapea a al menos un bloque (tabla de cobertura
  arriba); cada AC-01 a AC-08 tiene al menos un test pasando.
- El test de concurrencia (`test_crear_reserva_concurrencia_solo_una_confirmada`) demuestra que el
  `SELECT FOR UPDATE` serializa correctamente dos altas simultáneas sobre el mismo vehículo/período,
  no solo que el chequeo lógico de solapamiento existe.
- Las 6 mitigaciones del threat model (`docs/daw/security/threat-FEAT-001c.md`) están implementadas
  o documentadas como precondición (TM-C-01), o aceptadas explícitamente con los 3 campos de F-TM-04
  (TM-C-05, TM-C-06).
- `daw-security-sast` corre limpio sobre el código de los 4 bloques antes de pasar a VERIFY.
- Rollback: `alembic downgrade -1` revierte la migración de `reservas` sin afectar `vehiculos`; no
  hay migración de datos (tabla nueva, sin datos previos que preservar).
