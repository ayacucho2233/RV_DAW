# Spec FEAT-005: Estado "Caducada" para reservas vencidas automáticamente

| Field | Value |
|-------|-------|
| Ticket | FEAT-005 |
| PRD | docs/daw/prd/prd-FEAT-005.md |
| Tier | FEATURE |
| Date | 2026-08-18 |
| Spec loops | 0 |

## Summary

Se agrega `caducada` a `EstadoReserva`, junto con una migración que amplía el CHECK constraint
`estado_reserva` y agrega un índice `(estado, fecha_fin)`. Un nuevo endpoint público
`POST /reservas/caducar-vencidas` ejecuta un `UPDATE` masivo (`activa` + `fecha_fin < ahora` →
`caducada`), disparado por el frontend una sola vez al montar `App.jsx` — "cuando se ingresa al
programa desde el explorador", por decisión del usuario en PLAN. Nada de lo que hoy filtra por
`estado == activa` (solapamiento, disponibilidad, baja de vehículo, `cancelar_reserva`) necesita
cambios: `caducada` queda excluido por construcción, igual que `cancelada`.

## Coverage: PRD → blocks

| Requirement | Covered by |
|---|---|
| FR-01 | Block 1 |
| FR-02 | Block 1, Block 2, Block 3, Block 4 |
| FR-03 | Strategy: ya cubierto — `service.cancelar_reserva` rechaza cualquier `estado != activa` (ver Block 2, nota) |
| FR-04 | Strategy: ya cubierto — toda query existente filtra positivamente por `estado == activa` |
| FR-05 | Block 3 |
| NFR-01 | Block 2 (el `UPDATE` corre en la misma transacción que lo comitea antes de que el endpoint responda) |
| NFR-02 | Block 1 (la migración no reescribe filas, solo amplía el CHECK) |

## Dependencies between blocks

Block 1 → Block 2 → Block 3 → Block 4 (orden secuencial estricto: el modelo/columna tiene que
existir antes del repository, el repository antes del router, y el backend completo antes de que el
frontend pueda llamarlo).

## Block 1 — Modelo, migración e índice

**Files**
- `backend/app/features/reservas/models.py` (modified) — agrega `caducada = "caducada"` a
  `EstadoReserva(str, enum.Enum)`.
- `backend/alembic/versions/0004_estado_caducada.py` (new) — migración.

**Logic**

`models.py`: el tercer valor del enum. La columna (`Enum(EstadoReserva, name="estado_reserva",
native_enum=False, length=10, values_callable=lambda enum_cls: [m.value for m in enum_cls], ...)`)
no necesita ningún otro cambio — `values_callable` ya deriva la lista de valores válidos del propio
enum, y `"caducada"` (8 caracteres) entra en el `length=10` existente sin ampliarlo.

Migración `0004` (`down_revision = "0003"`):
- `upgrade()`:
  1. `op.drop_constraint("estado_reserva", "reservas", type_="check")` — el nombre real del
     constraint, confirmado contra la base (`\d reservas` → `"estado_reserva" CHECK (...)`), NO
     `ck_reservas_estado_reserva`.
  2. `op.create_check_constraint("estado_reserva", "reservas", "estado IN ('activa', 'cancelada', 'caducada')")`.
  3. `op.create_index("ix_reservas_estado_fecha_fin", "reservas", ["estado", "fecha_fin"])` —
     mitigación M-01 del threat model (`docs/daw/security/threat-FEAT-005.md`): sin este índice,
     `caducar_vencidas` (Block 2) hace full scan en cada llamada.
- `downgrade()`: los 3 pasos en orden inverso, restaurando el CHECK de 2 valores. **Caveat
  documentado en el propio archivo** (comentario, mismo estilo que `0003`): el `downgrade()` falla
  si ya existen filas `caducada` en la tabla — aceptable porque los tests de migración
  (`test_migration_reservas.py` y los otros dos `test_migration*.py`) corren la cadena completa
  contra una base vacía.

**Data model**

- `reservas.estado`: sin cambio de tipo/longitud, solo el CHECK amplía sus valores válidos
  (`'activa'|'cancelada'|'caducada'`).
- Nuevo índice `ix_reservas_estado_fecha_fin` sobre `(estado, fecha_fin)` — no único, no reemplaza
  al índice existente `ix_reservas_vehiculo_fechas`.

**Error handling**

N/A — cambio de esquema puro, sin lógica de negocio que pueda fallar en runtime.

**Required tests**

- [ ] `test_migracion_agrega_caducada_al_check` (nuevo, en `test_migration_reservas.py`) — tras
  `upgrade head`, un `UPDATE reservas SET estado='caducada' WHERE id=...` sobre una fila de prueba
  no viola el CHECK; un valor inválido (`'inexistente'`) sí lo viola.
- [ ] `test_migracion_no_reescribe_filas_existentes` (nuevo) — AC-06: insertar una reserva `activa`
  con `fecha_fin` en el pasado, aplicar la migración, verificar que sigue en `activa` inmediatamente
  después (la migración no la toca).
- [ ] `test_migracion_crea_indice_estado_fecha_fin` (nuevo) — confirma la existencia del índice vía
  `pg_indexes`.
- [ ] La suite existente de `test_migration.py`/`test_migration_reservas.py`/
  `test_migration_patente_unique_ci.py` (que corre `upgrade head` → `downgrade base`) sigue en
  verde con la migración nueva incluida en la cadena.

**Completion criterion**

`alembic upgrade head` aplica limpio sobre la base de test; los 4 tests de arriba pasan; el
`downgrade` completo de la cadena (`test_migration*.py`) sigue en verde.

## Block 2 — Repository y Service

**Files**
- `backend/app/features/reservas/repository.py` (modified) — nueva función `caducar_vencidas`.
- `backend/app/features/reservas/service.py` (modified) — nueva función
  `caducar_reservas_vencidas`.

**Logic**

`repository.caducar_vencidas(db: Session, ahora: datetime) -> int`: `UPDATE` masivo vía SQLAlchemy
Core (`from sqlalchemy import update`), parametrizado (`Reserva.estado == EstadoReserva.activa`,
`Reserva.fecha_fin < ahora` → `estado = EstadoReserva.caducada`), sin cargar filas a Python. **Comitea
él mismo** (`db.commit()`), replicando el patrón de `crear`/`guardar` en este mismo archivo y en
`vehiculos/repository.py` (corrección del FAIL #1 de `daw-arch-auditor` en PLAN: el commit nunca vive
en `service.py`). Devuelve `result.rowcount`.

`service.caducar_reservas_vencidas(db: Session, ip_origen: str) -> int`: llama a
`repository.caducar_vencidas(db, datetime.now(timezone.utc))` y loguea la operación —
`logger.info("operacion=caducar_vencidas count=%s resultado=ok ip_origen=%s timestamp=%s", ...)`,
mitigación M-02 del threat model (sin este log, el sweep masivo no dejaba rastro, a diferencia de
`crear_reserva`/`cancelar_reserva`). **Sin** `legajo`/`vehiculo_id` — no aplican a una operación
masiva, mismo criterio de mínima PII en logs ya documentado en el resto de `service.py`.

**Nota — FR-03/FR-04 ya cubiertos, sin cambios de código:** `service.cancelar_reserva` ya rechaza
cualquier `estado != EstadoReserva.activa` con `ReservaYaCanceladaError` (mismo código/mensaje) —
una reserva `caducada` cae ahí sin tocar esa función. Toda query de `repository.py` que filtra
`Reserva.estado == EstadoReserva.activa` (solapamiento, disponibilidad, `existe_activa_para_vehiculo`)
excluye `caducada` por construcción. Esto se verifica con tests de regresión (abajo), no con código
nuevo.

**Error handling**

N/A — sin input de usuario, sin excepciones de dominio nuevas.

**Required tests**

- [ ] `test_caducar_vencidas_transiciona_activa_vencida_a_caducada` — AC-01: una reserva `activa`
  con `fecha_fin` estrictamente en el pasado pasa a `caducada`.
- [ ] `test_caducar_vencidas_no_toca_activa_vigente` — AC-02: una reserva `activa` con
  `fecha_fin >= ahora` permanece `activa`.
- [ ] `test_caducar_vencidas_no_toca_ya_cancelada_ni_ya_caducada` — idempotencia: reservas que ya
  están en `cancelada`/`caducada` no se tocan ni se cuentan de nuevo.
- [ ] `test_caducar_vencidas_devuelve_cantidad_correcta` — el `int` devuelto coincide con la
  cantidad real de filas transicionadas.
- [ ] `test_caducar_reservas_vencidas_loguea_operacion` (usa `caplog`) — el log contiene
  `operacion=caducar_vencidas` y el `count` correcto, sin `legajo` ni `nombre_empleado`.
- [ ] `test_cancelar_reserva_caducada_rechaza_con_mismo_error_que_cancelada` — AC-05: regresión
  sobre `cancelar_reserva` (sin cambiar su código) confirmando que una reserva `caducada` dispara
  `ReservaYaCanceladaError` igual que una `cancelada`.

**Completion criterion**

Los 6 tests pasan; ningún test existente de `test_reservas_service.py` se rompe.

## Block 3 — Router y Schema

**Files**
- `backend/app/features/reservas/schemas.py` (modified) — nuevo `CaducarVencidasOut`.
- `backend/app/features/reservas/router.py` (modified) — nuevo endpoint.

**Logic**

`schemas.py`: `CaducarVencidasOut(BaseModel)` con un único campo `caducadas: int`.

`router.py`: `POST /reservas/caducar-vencidas`, público (sin `Depends(verificar_admin)`, mismo
criterio que los 6 endpoints existentes de este router), sin body. Aplica
`_aplicar_rate_limit(request, _LIMITE_LECTURA, "reservas-caducar-vencidas")` (balde propio, 60/min)
**antes** de delegar a `service.caducar_reservas_vencidas`. Actualiza el docstring del módulo
(líneas 32-40) agregando, junto a la tabla ya existente de altas/lecturas, la justificación explícita
de por qué este endpoint —siendo un `POST` que muta— se clasifica bajo el balde de lectura: se
dispara automáticamente en cada carga de página del frontend, y clasificarlo bajo el balde de
mutaciones (10/hora) lo dejaría inoperante en la mayoría de esas cargas — corrección del WARN de
`daw-arch-auditor` en PLAN (documentar la excepción, no dejarla implícita).

**API contract**

- Method + path: `POST /reservas/caducar-vencidas`
- Request: sin body, sin query params.
- Response `200 OK`: `{"caducadas": <int>}`
- Error codes: `429` (rate limit, mismo `HTTPException`/mensaje que los otros 6 endpoints).
- Auth: ninguna — público, mismo criterio que el resto de `/reservas`.

**Error handling**

Solo el `429` de rate limit (mismo mecanismo ya existente, `_DEMASIADAS_REQUESTS`). No hay
excepciones de dominio nuevas que traducir en `_a_http`.

**Required tests**

- [ ] `test_post_caducar_vencidas_devuelve_200_y_cantidad_correcta` (TestClient, `test_reservas_router.py`) —
  crea una reserva `activa` vencida, llama al endpoint, verifica `200` y `{"caducadas": 1}`, y que la
  fila en base efectivamente quedó en `caducada`.
- [ ] `test_post_caducar_vencidas_respeta_rate_limit` — 61 llamadas en la ventana devuelven `429` en
  la última, mismo patrón que los tests de rate limit existentes de este router.
- [ ] `test_post_caducar_vencidas_no_requiere_auth` — sin header `Authorization`, responde `200`
  (no `401`).
- [ ] `test_get_reservas_devuelve_caducada_como_estado_valido` — AC-07: tras el sweep, `GET
  /reservas` devuelve `"estado": "caducada"` para la reserva afectada, sin error de validación de
  Pydantic.
- [ ] `test_crear_reserva_no_bloqueada_por_reserva_caducada_solapada` — AC-03: una reserva
  `caducada` con fechas que solaparían si estuviera `activa` NO bloquea una reserva nueva sobre el
  mismo rango.
- [ ] `test_baja_vehiculo_no_bloqueada_por_reserva_caducada` — AC-04: un vehículo con solo reservas
  `caducada` (ninguna `activa`) puede darse de baja (temporal o definitiva).

**Completion criterion**

Los 6 tests pasan; los tests existentes de `test_reservas_router.py` (los 6 endpoints previos) siguen
en verde sin modificación.

## Block 4 — Frontend

**Files**
- `frontend/src/features/reservas/reservasApi.js` (modified) — nueva función
  `caducarReservasVencidas`.
- `frontend/src/App.jsx` (modified) — dispara el sweep al montar.
- `frontend/src/App.test.jsx` (modified) — actualiza el mock de `./api/client`.

**Logic**

`reservasApi.js`: `caducarReservasVencidas()` → `apiClient.post("/reservas/caducar-vencidas")`,
mismo patrón `try/catch → propagarError` que las 6 funciones existentes del archivo.

`App.jsx`: nuevo `useEffect(() => { ... }, [])` al principio de `App()`, que llama a
`caducarReservasVencidas()` una sola vez al montar — "cuando se ingresa al programa desde el
explorador" (decisión del usuario en PLAN). Fire-and-forget: no bloquea el render de
`MenuPrincipal`. El `.catch` **incluye un comentario explícito** justificando la excepción a "Nunca
captura silenciosa" de AGENTS.md (corrección del FAIL #2 de `daw-arch-auditor`): es una llamada de
mantenimiento en background sin acción de usuario que traducir a un mensaje visible, y un fallo acá
no degrada la app (una reserva que no caducó todavía lo hace en el próximo mount). Loguea a
`console.error` para no perder la señal por completo.

`App.test.jsx`: el `vi.mock("./api/client", ...)` existente solo expone `setAuthSession`/
`setUnauthorizedHandler` (con nombre) — el `useEffect` nuevo llama a `apiClient.post` (vía
`reservasApi.js`, que importa el `default` de `client.js`), así que el mock necesita agregar
`default: { post: vi.fn().mockResolvedValue({ data: { caducadas: 0 } }) }` junto a los exports ya
mockeados. Sin este cambio, cualquier test que monte `<App/>` revienta con `TypeError: Cannot read
properties of undefined (reading 'post')` (gap detectado por `daw-impact-scanner` en PLAN).

**Error handling**

`propagarError` en `reservasApi.js` (igual que el resto del archivo — nunca falla en silencio a
nivel de esa capa). La decisión de no propagar el error a la UI es específica de `App.jsx` y está
documentada ahí (ver Logic).

**Required tests**

- [ ] `caducarReservasVencidas llama a POST /reservas/caducar-vencidas y devuelve data` (nuevo, en
  el test file de `reservasApi`) — mismo patrón que las funciones existentes.
- [ ] `caducarReservasVencidas propaga error tipado ante fallo de red` — mismo patrón que las
  funciones existentes.
- [ ] `App llama a caducarReservasVencidas una vez al montar` (`App.test.jsx`, mockeando
  `./features/reservas/reservasApi` en vez de `./api/client` para este assert puntual).
- [ ] `App no falla si caducarReservasVencidas rechaza` — mock que rechaza la promesa, confirma que
  `<MenuPrincipal>` igual se renderiza sin throw.

**Completion criterion**

Los 4 tests nuevos pasan; toda la suite existente de `App.test.jsx` (que monta `<App/>` en distintos
escenarios) sigue en verde con el mock de `./api/client` actualizado.

## Final verification

- Suite completa backend (`pytest`) y frontend (`npm test`) en verde.
- `ruff check .` (backend) y `npm run lint` (frontend) en 0 errores.
- Manual: abrir el frontend, confirmar en la pestaña de red que `POST /reservas/caducar-vencidas` se
  dispara una vez al cargar la página, y que una reserva de prueba vencida aparece como `caducada`
  en el listado tras el reload.
