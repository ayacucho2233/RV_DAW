# Spec FEAT-001d: Listado, filtros y cancelación de reservas

| Field | Value |
|-------|-------|
| Ticket | FEAT-001d |
| PRD | docs/daw/prd/prd-FEAT-001d.md |
| Tier | FEATURE |
| Date | 2026-08-07 |
| Spec loops | 0 |

## Summary

Extiende el feature `reservas` (FastAPI, capas router → service → repository, ya creado por
FEAT-001c) con dos endpoints públicos nuevos: listar reservas con filtro opcional por período
(`futuras`/`en_curso`/`pasadas`, calculado por fecha contra `datetime.now(timezone.utc)`, **no** por
el campo `estado` del modelo) y cancelar una reserva propia validando el `legajo` de quien la creó.
No hay cambios de modelo ni migración: el campo `estado` (`activa`/`cancelada`) ya existe desde
FEAT-001c precisamente para este ticket. El enriquecimiento con `patente`/`tipo` del vehículo en el
listado se resuelve en `service.py` combinando `vehiculos_repository.listar(db)` en Python — mismo
patrón que ya usa `consultar_disponibilidad` — para preservar el invariante "un repository, una
tabla" que `reservas/repository.py` ya declara en su docstring. Vista pública en React: un tercer
listado/formulario dentro del área pública, sin librería de ruteo (misma decisión de FEAT-001c).

## Coverage: PRD → blocks

| Requirement | Covered by |
|---|---|
| FR-01 (listar reservas) | Block 1, Block 2, Block 3 |
| FR-02 (filtrar por período) | Block 1, Block 2, Block 3 |
| FR-03 (cancelar indicando legajo) | Block 1, Block 2, Block 3 |
| FR-04 (rechazar cancelación con legajo distinto) | Block 1, Block 2, Block 3 |
| NFR-01 (listado/filtrado <2s p95) | Strategy: sin joins en SQL (Block 1), reuso de `vehiculos_repository.listar` ya cacheable por el ORM en la misma request (Block 1) |

## Dependencies between blocks

`1 → 2 → 3` (secuencial: cada capa necesita la anterior; el frontend necesita el contrato de API de
Block 2).

---

## Block 1 — Servicio, repositorio, excepciones y schemas

**Files**
- `backend/app/features/reservas/schemas.py` (modified) — agrega `FiltroPeriodoReserva`,
  `CancelarReservaRequest`, `ReservaListItem`.
- `backend/app/features/reservas/exceptions.py` (modified) — agrega `ReservaNoEncontradaError`,
  `ReservaYaCanceladaError`, `LegajoNoCoincideError`.
- `backend/app/features/reservas/repository.py` (modified) — agrega `listar_todas(db)`,
  `obtener_por_id(db, id)`, `guardar(db, reserva)`.
- `backend/app/features/reservas/service.py` (modified) — parametriza `_log_operacion`; agrega
  `listar_reservas(db, periodo=None)` y `cancelar_reserva(db, reserva_id, legajo, ip_origen)`.
- `backend/tests/test_reservas_service.py` (modified) — tests de este bloque.

**Logic**

`schemas.py`:
- `FiltroPeriodoReserva = Literal["futuras", "en_curso", "pasadas"]` — tipo del query param
  `periodo` de Block 2. Nombre elegido deliberadamente distinto de `estado` (el campo real del
  modelo, `activa`/`cancelada`) para no confundir "clasificación temporal calculada" con "estado
  persistido" en la misma respuesta.
- `CancelarReservaRequest(BaseModel)`: `legajo: str = Field(..., min_length=1, max_length=20)` (mismo
  límite que `Reserva.legajo`).
- `ReservaListItem(BaseModel)`: `id, vehiculo_id, nombre_empleado, fecha_inicio, fecha_fin, destino,
  estado, created_at, updated_at`, más `patente: str` y `tipo: TipoVehiculo` — mejora de UX no
  exigida por los AC del PRD, mismo criterio ya usado en `DisponibilidadOut` de FEAT-001c (evita que
  el empleado tenga que interpretar un `vehiculo_id` crudo). **Deliberadamente NO incluye `legajo` ni
  `licencia`** (a diferencia de `ReservaOut`) — mitigación TM-D-01 del threat model: FR-01/AC-01
  exigen mostrar "todas las reservas existentes" sin restricción de visibilidad, pero no exigen
  exponer el legajo/licencia de cada solicitante; hacerlo convertiría el propio listado público en un
  oráculo que anula la protección de FR-04/AC-06 (cualquiera podría leer el legajo de otro empleado
  acá mismo y usarlo para cancelar su reserva). El legajo sigue siendo necesario para cancelar, pero
  se **provee** por el cliente en `PATCH /reservas/{id}/cancelar` (Block 2), nunca se **lee** desde
  el listado.

`exceptions.py`, las 3 nuevas heredan de `ReservaDomainError` (ya existente), mismo patrón que las 3
de FEAT-001c:
- `ReservaNoEncontradaError(reserva_id)`.
- `ReservaYaCanceladaError(reserva_id)` — decisión de diseño confirmada con el usuario en PLAN:
  cancelar una reserva ya cancelada se rechaza explícitamente (409), en vez de responder éxito de
  forma idempotente, consistente con el patrón `TransicionEstadoInvalidaError` que `vehiculos`
  aplica a sus propias transiciones de estado.
- `LegajoNoCoincideError(reserva_id)` — mensaje que **no** revela el legajo real de la reserva (evita
  filtrar el dato por el camino de un mensaje de error).

`repository.py`:
- `listar_todas(db)` → `SELECT * FROM reservas` sin filtros ni joins (respeta "un repository, una
  tabla"; el enriquecimiento con datos de `vehiculos` se resuelve en `service.py`, no acá).
- `obtener_por_id(db, id)` → `SELECT` por PK, `None` si no existe (mismo patrón que
  `vehiculos_repository.obtener_por_id`).
- `guardar(db, reserva)` → `db.add(reserva); db.commit(); db.refresh(reserva)` — persiste una
  instancia ya mutada por el caller, mismo patrón que `vehiculos_repository.guardar`, reusado por
  `dar_de_baja_temporal`/`dar_de_baja_definitiva`/`reactivar`.

`service.py`:
- `_log_operacion` pasa a recibir `operacion: str` como primer parámetro (en vez de tener
  `"crear_reserva"` hardcodeado en el `logger.info`); el call site existente dentro de
  `crear_reserva` pasa a llamarla con `"crear_reserva"` explícito — sin cambio de comportamiento
  observable (mismo test `test_crear_reserva_loguea_operacion_sin_pii` sigue pasando, valida
  substrings del mensaje, no la firma de la función). Esto alinea `reservas/service.py` con el
  patrón ya usado en `vehiculos/service.py`, donde `_log_operacion` ya toma `operacion` como
  argumento.
- `listar_reservas(db, periodo=None)` → `repository.listar_todas(db)` +
  `vehiculos_repository.listar(db)` (ya existente, solo lectura entre features, dependencia D-02 del
  PRD), combina ambos por `vehiculo_id` en Python para construir `list[ReservaListItem]` (mismo
  patrón que `consultar_disponibilidad`). Si `periodo` no es `None`, filtra en Python contra
  `datetime.now(timezone.utc)`:
  - `"futuras"`: `fecha_inicio > ahora`.
  - `"en_curso"`: `fecha_inicio <= ahora <= fecha_fin`.
  - `"pasadas"`: `fecha_fin < ahora`.
  El filtro es puramente temporal — no excluye reservas `cancelada` (AC-02 a AC-04 del PRD no piden
  excluirlas; son criterios sobre fechas, no sobre `estado`).
- `cancelar_reserva(db, reserva_id, legajo, ip_origen)`:
  1. `reserva = repository.obtener_por_id(db, reserva_id)`; `None` → `ReservaNoEncontradaError`.
  2. `reserva.estado != EstadoReserva.activa` → `ReservaYaCanceladaError` (decisión confirmada con
     el usuario).
  3. `reserva.legajo != legajo` → `LegajoNoCoincideError` (AC-06).
  4. `reserva.estado = EstadoReserva.cancelada`; `repository.guardar(db, reserva)` (AC-05: el
     vehículo queda disponible para ese período porque
     `listar_activas_solapadas_con_lock`/`listar_solapadas_en_rango` ya filtran por
     `estado == activa` — no hace falta ningún paso adicional).
  5. `_log_operacion("cancelar_reserva", reserva.vehiculo_id, legajo, resultado, ip_origen)` — mismo
     criterio de PII que `crear_reserva` (nunca `nombre_empleado`/`licencia`).

**API contract**

Ninguno en este bloque (los endpoints son Block 2). Los métodos de `service.py` son la interfaz que
Block 2 consume.

**Data model**

Sin cambios de modelo ni migración — reusa `Reserva`/`EstadoReserva` de FEAT-001c tal cual.

**Input validation**

`CancelarReservaRequest.legajo`: string no vacío, máximo 20 caracteres (Pydantic, mismo límite que
`Reserva.legajo`). `periodo` se valida en Block 2 (es un query param, no un body).

**Error handling**

| Error | Cuándo | Manejo |
|---|---|---|
| `ReservaNoEncontradaError` | `reserva_id` no existe | Propaga a Block 2 → 404 |
| `ReservaYaCanceladaError` | La reserva ya tiene `estado == cancelada` | Propaga a Block 2 → 409 |
| `LegajoNoCoincideError` | El `legajo` no coincide con el de la reserva | Propaga a Block 2 → 403 |

**Required tests**
- [ ] `test_listar_reservas_sin_filtro` — AC-01, devuelve todas las reservas con patente/tipo
- [ ] `test_listar_reservas_filtro_futuras` — AC-02
- [ ] `test_listar_reservas_filtro_en_curso` — AC-03
- [ ] `test_listar_reservas_filtro_pasadas` — AC-04
- [ ] `test_listar_reservas_filtro_incluye_canceladas_en_su_periodo` — confirma que el filtro es
      puramente temporal, no excluye `estado == cancelada` (evita un falso supuesto)
- [ ] `test_listar_reservas_no_expone_legajo_ni_licencia` — TM-D-01, confirma que `ReservaListItem`
      no tiene los atributos `legajo`/`licencia` aunque la `Reserva` origen sí los tenga
- [ ] `test_cancelar_reserva_ok` — AC-05, `estado` pasa a `cancelada`
- [ ] `test_cancelar_reserva_libera_vehiculo` — AC-05, tras cancelar, una nueva reserva solapada
      sobre el mismo vehículo/período ya no choca contra `ReservaSolapadaError`
- [ ] `test_cancelar_reserva_inexistente` — 404 de dominio
- [ ] `test_cancelar_reserva_ya_cancelada` — 409, decisión de diseño confirmada
- [ ] `test_cancelar_reserva_legajo_no_coincide` — AC-06, 403, mensaje no revela el legajo real
- [ ] `test_cancelar_reserva_loguea_operacion_sin_pii` — TM-C-04 (mismo criterio que `crear_reserva`)

**Completion criterion**

Los 12 tests de servicio pasan; AC-01 a AC-06 del PRD tienen al menos un test cubriendo su caso; no
se rompe ningún test existente de `crear_reserva`/`consultar_disponibilidad`/`listar_vehiculos_pool`
(la parametrización de `_log_operacion` no cambia su comportamiento observable); `ReservaListItem`
nunca expone `legajo`/`licencia` (TM-D-01).

---

## Block 2 — Router

**Files**
- `backend/app/features/reservas/router.py` (modified) — agrega 2 endpoints.
- `backend/tests/test_reservas_router.py` (modified) — tests de este bloque.

**Logic**

`router.py`: sin `Depends(verificar_admin)` (feature público por diseño, igual que los 3 endpoints
existentes). Se agregan 2 entradas a `_MAPEO_ERRORES_HTTP`:
`ReservaNoEncontradaError`→404, `ReservaYaCanceladaError`→409, `LegajoNoCoincideError`→403.

Rate limiting (mismo mecanismo `_aplicar_rate_limit` ya existente, TM-C-02): cada endpoint con su
propia clave de contador, **no** reusa `"reservas-post"` ni las claves de lectura existentes
(hallazgo del arch-auditor en PLAN — un abuso de un endpoint no debe descontar cupo de otro):
- `GET /reservas`: `_LIMITE_LECTURA` (60/min), clave `"reservas-listado"`.
- `PATCH /reservas/{id}/cancelar`: `_LIMITE_ALTAS` (10/hora, mismo límite que `POST /reservas` — es
  una mutación sin autenticación), clave `"reservas-cancelar"`.

**API contract**

| Método + path | Auth | Request | Response éxito | Errores |
|---|---|---|---|---|
| `GET /reservas` | Ninguna | Query param opcional `periodo: "futuras"\|"en_curso"\|"pasadas"` | `200`, `list[ReservaListItem]` | `422` si `periodo` tiene un valor fuera del enum; `429` |
| `PATCH /reservas/{id}/cancelar` | Ninguna | `CancelarReservaRequest` (`legajo`) | `200`, `ReservaOut` (con `estado="cancelada"`) | `403, 404, 409, 422, 429` |

**Error handling**

Ver tabla de mapeo arriba; el 422 de `periodo` inválido lo genera FastAPI automáticamente (Pydantic
valida el `Literal` del query param); el 422 de `legajo` faltante/vacío en el body, ídem. El 403 de
`LegajoNoCoincideError` usa el mismo `HTTPException` de status/mensaje que el resto del mapeo — no
distingue "reserva inexistente" (404) de "legajo no coincide" (403) más allá de lo que el PRD ya
acepta como riesgo conocido (R-01: sin autenticación real, la distinción 403 vs. 404 permite inferir
existencia probando legajos — documentado, no es un hallazgo nuevo de este bloque).

**Required tests**
- [ ] `test_get_reservas_sin_filtro_200` — AC-01
- [ ] `test_get_reservas_filtro_futuras_200` — AC-02
- [ ] `test_get_reservas_filtro_en_curso_200` — AC-03
- [ ] `test_get_reservas_filtro_pasadas_200` — AC-04
- [ ] `test_get_reservas_periodo_invalido_422`
- [ ] `test_patch_cancelar_reserva_ok_200` — AC-05
- [ ] `test_patch_cancelar_reserva_inexistente_404`
- [ ] `test_patch_cancelar_reserva_ya_cancelada_409`
- [ ] `test_patch_cancelar_reserva_legajo_no_coincide_403` — AC-06
- [ ] `test_patch_cancelar_reserva_legajo_faltante_422`
- [ ] `test_get_reservas_rate_limit_429` — TM-C-02, clave `"reservas-listado"` independiente de
      `"reservas-vehiculos"`/`"reservas-disponibilidad"`
- [ ] `test_patch_cancelar_rate_limit_429` — TM-C-02, clave `"reservas-cancelar"` independiente de
      `"reservas-post"` (confirma que agotar el cupo de alta no afecta el de cancelación y viceversa)

**Completion criterion**

Los 12 tests de endpoint pasan; AC-01 a AC-06 tienen al menos un test pasando en esta capa; las
claves de rate limit de los 2 endpoints nuevos son independientes entre sí y de las 3 ya existentes;
no se rompe ningún test existente de `vehiculos`/Block 3 de FEAT-001c.

---

## Block 3 — Listado y cancelación (React + Vite)

**Files**
- `frontend/src/features/reservas/reservasApi.js` (modified) — agrega `listarReservas(periodo)` y
  `cancelarReserva(id, legajo)`.
- `frontend/src/features/reservas/ReservasListado.jsx` (new) — listado con filtro y cancelación.
- `frontend/src/features/reservas/ReservasListado.test.jsx` (new).
- `frontend/src/App.jsx` (modified) — agrega la navegación hacia la nueva vista.

**Logic**

`reservasApi.js`: mismo patrón `propagarError` ya usado por los 3 métodos existentes.
- `listarReservas(periodo)` → `GET /reservas` con `params: { periodo }` solo si `periodo` no es
  `null`/`undefined` (sin filtro, trae todas).
- `cancelarReserva(id, legajo)` → `PATCH /reservas/${id}/cancelar` con body `{ legajo }`.

`ReservasListado.jsx`: al montar, pide `GET /reservas` sin filtro; un `<select>` controlado
(`futuras`/`en_curso`/`pasadas`/`todas`) dispara una nueva consulta con `periodo` al cambiar. Cada
fila muestra `patente`, `tipo`, `nombre_empleado`, `fecha_inicio`–`fecha_fin`, `destino`, `estado`.
Cada reserva con `estado === "activa"` tiene una acción "Cancelar" que despliega un `<form>` inline
con un `<input>` controlado para `legajo` (**no** `window.prompt`/`window.confirm` — hallazgo del
arch-auditor en PLAN: el resto del frontend usa exclusivamente inputs controlados de React, y los
diálogos nativos no son testeables con la config actual de Vitest/Testing Library) y un botón
"Confirmar cancelación". Éxito: `role="status"`, refresca el listado para reflejar `estado
="cancelada"`. Error: `role="alert"`, mapea 403/404/409/422 a mensajes legibles (`MENSAJES_ERROR`,
mismo patrón que `ReservaForm.jsx`).

`App.jsx`: extiende el estado `vista` ya existente (`"reservas" | "login"`) a un tercer valor
(`"listado"`), con un botón adicional en el `<nav>` público ("Ver reservas") junto al de "Acceso
administrador" — no reabre la decisión ya tomada en FEAT-001c de no usar librería de ruteo.

**Error handling**

`reservasApi.js` propaga `status`/`detail`; `ReservasListado.jsx` los traduce: 404 (reserva ya no
existe, carrera improbable pero posible), 409 (ya estaba cancelada), 403 (legajo no coincide, mensaje
distinto de los otros dos), 422 (legajo vacío).

**Required tests**
- [ ] `ReservasListado.test.jsx` — renderiza el listado desde `GET /reservas`
- [ ] `ReservasListado.test.jsx` — cambiar el filtro dispara una nueva consulta con el `periodo`
      correcto
- [ ] `ReservasListado.test.jsx` — cancelar con el legajo correcto muestra éxito (`role="status"`) y
      refleja `estado="cancelada"` tras refrescar
- [ ] `ReservasListado.test.jsx` — cancelar con legajo incorrecto muestra el error 403 sin cancelar
      la reserva
- [ ] `ReservasListado.test.jsx` — cancelar una reserva ya cancelada muestra el error 409
- [ ] `ReservasListado.test.jsx` — cancelar una reserva que el backend responde inexistente (404)
      muestra el mensaje correspondiente
- [ ] `ReservasListado.test.jsx` — enviar el formulario de cancelación con `legajo` vacío no dispara
      la request (validación cliente) o, si se fuerza, muestra el 422 del backend

**Completion criterion**

Los tests de componente pasan. Smoke test manual del camino feliz (abrir la vista pública → "Ver
reservas" → filtrar por período → cancelar una reserva propia indicando el legajo correcto → ver la
reserva reflejada como cancelada) contra el backend de Block 2 corriendo localmente.

---

## Final verification

- Los 3 bloques tienen sus tests pasando (11 de Block 1 + 12 de Block 2 + los de componente de
  Block 3).
- Cada FR-01 a FR-04 y NFR-01 del PRD mapea a al menos un bloque (tabla de cobertura arriba); cada
  AC-01 a AC-06 tiene al menos un test pasando.
- El filtro por período es puramente temporal (no excluye reservas canceladas), confirmado por
  `test_listar_reservas_filtro_incluye_canceladas_en_su_periodo`.
- Cancelar una reserva dos veces devuelve 409 en la segunda, no 200 idempotente (decisión de diseño
  confirmada con el usuario en PLAN).
- Las claves de rate limit de `GET /reservas` y `PATCH /reservas/{id}/cancelar` son independientes
  entre sí y de las 3 ya existentes.
- Las mitigaciones del threat model (`docs/daw/security/threat-FEAT-001d.md`) están implementadas o
  documentadas como precondición/riesgo aceptado, en particular TM-D-01 (el listado nunca expone
  `legajo`/`licencia`).
- `daw-security-sast` corre limpio sobre el código de los 3 bloques antes de pasar a VERIFY.
- Rollback: sin migración nueva, no hay nada de esquema que revertir; revertir el commit de cada
  bloque es suficiente.
