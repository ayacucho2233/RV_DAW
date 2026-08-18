# Spec FEAT-004: Consulta de reservas activas por patente

| Field | Value |
|-------|-------|
| Ticket | FEAT-004 |
| PRD | docs/daw/prd/prd-FEAT-004.md |
| Tier | FEATURE |
| Date | 2026-08-17 |
| Spec loops | 0 |

## Summary

Tres bloques. Block 1 cierra el hueco de unicidad de patente detectado en PLAN: agrega un índice
único case-insensitive en la base y reutiliza la ruta de error ya existente
(`IntegrityError` → `PatenteYaExisteError`). Block 2 agrega la consulta pública
`GET /reservas/vehiculo/{patente}`, reutilizando el lookup case-insensitive de Block 1 y el schema
`ReservaListItem` ya existente. Block 3 agrega la UI de búsqueda por patente, montada sobre el
listado de reservas ya existente, sin acoplarse a su estado.

## Coverage: PRD → blocks

| Requirement | Covered by |
|---|---|
| FR-01 | Block 2, Block 3 |
| FR-02 | Block 2 |
| FR-03 | Block 2 |
| FR-04 | Block 2 |
| FR-05 | Block 1 |
| NFR-01 | Strategy: el lookup por patente usa el índice único ya existente (case-sensitive) más el nuevo índice único funcional (case-insensitive) de Block 1 — ambos son lookups indexados, O(log n). El filtro de reservas activas por vehículo usa el índice compuesto ya existente `ix_reservas_vehiculo_fechas` (`vehiculo_id`, `fecha_inicio`, `fecha_fin`). Ninguna de las dos queries nuevas requiere un índice adicional. |

## Dependencies between blocks

- Block 2 depende de Block 1: `consultar_reservas_activas_por_patente` (Block 2) llama a
  `vehiculos_repository.obtener_por_patente_normalizada` (Block 1).
- Block 3 depende de Block 2: consume el endpoint `GET /reservas/vehiculo/{patente}`.
- Orden de implementación: Block 1 → Block 2 → Block 3.

## Block 1 — Unicidad de patente case-insensitive

**Files**
- `backend/alembic/versions/0003_patente_unique_case_insensitive.py` (new) — migración que agrega
  un índice único funcional sobre `lower(patente)`.
- `backend/app/features/vehiculos/repository.py` (modified) — nueva función
  `obtener_por_patente_normalizada`.
- `backend/app/features/vehiculos/service.py` (modified) — `crear_vehiculo` y `modificar_vehiculo`
  cambian su pre-chequeo de `repository.obtener_por_patente` (exact-match) a
  `repository.obtener_por_patente_normalizada` (case-insensitive).

**Logic**

`obtener_por_patente_normalizada(db, patente)`:
```python
def obtener_por_patente_normalizada(db: Session, patente: str) -> Vehiculo | None:
    """Búsqueda case-insensitive (FR-05). A diferencia de `obtener_por_patente`
    (exact-match, se deja intacta para no alterar comportamiento existente),
    usa func.upper() de ambos lados y `.limit(1)` — nunca
    `scalar_one_or_none()`, por la mitigación del threat model: aunque el
    índice único de la migración impida duplicados a futuro, esta query no
    debe poder levantar `MultipleResultsFound` bajo ningún escenario."""
    stmt = (
        select(Vehiculo)
        .where(func.upper(Vehiculo.patente) == patente.strip().upper())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()
```

`crear_vehiculo`/`modificar_vehiculo` en `service.py`: reemplazar la llamada a
`repository.obtener_por_patente(db, data.patente)` por
`repository.obtener_por_patente_normalizada(db, data.patente)` en ambas funciones — el resto de la
lógica (levantar `PatenteYaExisteError`, comparar `.id != vehiculo_id` en la modificación) no
cambia. `obtener_por_patente` (exact-match) queda intacta en el archivo — no se borra, no tiene otros
call sites fuera de estas dos funciones (verificado en el impact scan) pero se conserva por si algún
consumidor futuro necesita explícitamente un match exacto.

Migración `0003_patente_unique_case_insensitive.py`:
```python
def upgrade():
    op.execute(
        "CREATE UNIQUE INDEX ix_vehiculos_patente_lower_unique "
        "ON vehiculos (lower(patente))"
    )

def downgrade():
    op.execute("DROP INDEX ix_vehiculos_patente_lower_unique")
```
No se toca el `UNIQUE` exacto ya existente (`0001_create_vehiculos.py`) — queda redundante pero
inofensivo (el índice case-insensitive es un superconjunto estricto de esa restricción). El
`IntegrityError` que dispare cualquiera de los dos índices ya lo captura
`vehiculos/repository.py::crear`/`actualizar`, que lo traduce a `PatenteYaExisteError` sin
distinguir cuál constraint lo originó — no requiere cambios.

**Error handling**

- `crear_vehiculo`/`modificar_vehiculo` con patente duplicada en cualquier casing: el pre-chequeo de
  `service.py` la detecta primero (UX: mensaje inmediato, sin ida y vuelta a la base) y levanta
  `PatenteYaExisteError` → 409 (mapeo ya existente en `vehiculos/router.py`).
- Si el pre-chequeo no alcanza a detectar la duplicación (condición de carrera: dos altas
  concurrentes), el `UNIQUE` de la migración la rechaza a nivel de base; `repository.py::crear`
  atrapa el `IntegrityError` resultante y levanta `PatenteYaExisteError` igual — mismo resultado para
  quien llama, sin importar por qué camino se detectó.
- **Antes de aplicar la migración en cualquier ambiente**: correr
  `SELECT lower(patente), COUNT(*) FROM vehiculos GROUP BY lower(patente) HAVING COUNT(*) > 1;` — si
  devuelve filas, resolver esos duplicados manualmente antes de migrar (la migración fallaría si no).
  Es un paso operativo, no de código; se documenta acá porque el spec es donde vive la instrucción
  para quien despliegue.

**Required tests**

- [ ] `test_crear_vehiculo_rechaza_patente_duplicada_otro_casing` — alta con patente que ya existe
      en otro casing → `PatenteYaExisteError` — valida AC-05.
- [ ] `test_modificar_vehiculo_rechaza_patente_duplicada_otro_casing` — modificación asignando una
      patente que ya existe en otro vehículo, en otro casing → `PatenteYaExisteError` — valida AC-06.
- [ ] `test_crear_vehiculo_patente_distinta_sigue_funcionando` — regresión: alta con patente nueva,
      sin relación de casing con ninguna existente, sigue creando el vehículo normalmente.
- [ ] `test_obtener_por_patente_normalizada_encuentra_por_cualquier_casing` — test de repository:
      busca con mayúsculas/minúsculas distintas a como se guardó, encuentra el mismo vehículo.
- [ ] `test_indice_unico_case_insensitive_a_nivel_db` — test de integración: dos `INSERT` directos
      (bypaseando `service.py`) con patentes que solo difieren en casing → el segundo falla con
      `IntegrityError` — confirma que la migración realmente creó el índice (no solo que el
      pre-chequeo de service.py funciona).

**Completion criterion**

Las 5 tests pasan; `alembic upgrade head` aplica la migración sin error sobre la base de test (que
no tiene duplicados); `crear_vehiculo`/`modificar_vehiculo` siguen pasando sus tests existentes de
FEAT-001a sin modificarlos.

## Block 2 — Consulta de reservas activas por patente

**Files**
- `backend/app/features/reservas/repository.py` (modified) — nueva función
  `listar_activas_por_vehiculo`.
- `backend/app/features/reservas/service.py` (modified) — nueva función
  `consultar_reservas_activas_por_patente`.
- `backend/app/features/reservas/exceptions.py` (modified) — generaliza
  `VehiculoNoEncontradoError`.
- `backend/app/features/reservas/router.py` (modified) — nuevo endpoint
  `GET /reservas/vehiculo/{patente}`.

**Logic**

`listar_activas_por_vehiculo(db, vehiculo_id, ahora)` en `repository.py`:
```python
def listar_activas_por_vehiculo(
    db: Session, vehiculo_id: int, ahora: datetime
) -> list[Reserva]:
    """Reservas 'activas' de un vehículo puntual (FR-02): estado == activa y
    no finalizadas (fecha_fin >= ahora) — mismo criterio de 'reserva activa'
    de FEAT-001c, sin FOR UPDATE (solo lectura, no participa de ninguna
    escritura)."""
    stmt = (
        select(Reserva)
        .where(
            Reserva.vehiculo_id == vehiculo_id,
            Reserva.estado == EstadoReserva.activa,
            Reserva.fecha_fin >= ahora,
        )
        .order_by(Reserva.fecha_inicio)
    )
    return list(db.execute(stmt).scalars().all())
```

`consultar_reservas_activas_por_patente(db, patente)` en `service.py`:
```python
def consultar_reservas_activas_por_patente(db: Session, patente: str) -> list[ReservaListItem]:
    """FR-01/FR-02/FR-03: reservas activas de un vehículo dado por patente
    (búsqueda case-insensitive, Block 1), o VehiculoNoEncontradoError si la
    patente no existe en el pool."""
    vehiculo = vehiculos_repository.obtener_por_patente_normalizada(db, patente)
    if vehiculo is None:
        raise VehiculoNoEncontradoError(patente)

    ahora = datetime.now(timezone.utc)
    reservas = repository.listar_activas_por_vehiculo(db, vehiculo.id, ahora)

    return [
        ReservaListItem(
            id=r.id, vehiculo_id=r.vehiculo_id, nombre_empleado=r.nombre_empleado,
            fecha_inicio=r.fecha_inicio, fecha_fin=r.fecha_fin, destino=r.destino,
            estado=r.estado, created_at=r.created_at, updated_at=r.updated_at,
            patente=vehiculo.patente, tipo=vehiculo.tipo,
        )
        for r in reservas
    ]
```

`VehiculoNoEncontradoError` en `exceptions.py` — generalizar:
```python
class VehiculoNoEncontradoError(ReservaDomainError):
    """No existe ningún vehículo con el identificador solicitado (id o patente)."""

    def __init__(self, identificador: int | str):
        self.identificador = identificador
        if isinstance(identificador, str):
            mensaje = f"No se encontró el vehículo con patente {identificador!r}."
        else:
            mensaje = f"No se encontró el vehículo con id {identificador}."
        super().__init__(mensaje)
```
El atributo se llama `identificador` (no `vehiculo_id`) a propósito — recomendación del arch-auditor
en PLAN: reusar el nombre `vehiculo_id` para un valor que puede ser un `int` o un `str` es una trampa
de mantenibilidad para un caller futuro que asuma el tipo por el nombre. Único call site existente
(`reservas/service.py:94`, dentro de `crear_reserva`) sigue funcionando sin cambios — pasa un `int`
posicional, la generalización es compatible hacia atrás.

`router.py` — nuevo endpoint:
```python
@router.get("/vehiculo/{patente}", response_model=list[ReservaListItem])
def consultar_reservas_por_patente(
    request: Request,
    patente: str = Path(..., min_length=1, max_length=10, pattern=r"^[A-Za-z0-9]+$"),
    db: Session = Depends(get_db),
) -> list[ReservaListItem]:
    """FR-01/FR-02/FR-03/FR-04: reservas activas de un vehículo por patente."""
    _aplicar_rate_limit(request, _LIMITE_LECTURA, "reservas-por-patente")
    try:
        return service.consultar_reservas_activas_por_patente(db, patente)
    except VehiculoNoEncontradoError as exc:
        raise _a_http(exc) from exc
```
`_MAPEO_ERRORES_HTTP` ya mapea `VehiculoNoEncontradoError` → 404 (usado por `crear_reserva`); no
requiere una entrada nueva, la existente cubre ambos usos de la excepción generalizada. La constante
`Path(..., pattern=...)` usa el mismo patrón que `VehiculoBase.patente` en `vehiculos/schemas.py`,
por consistencia. El path `/reservas/vehiculo/{patente}` (singular) es deliberadamente distinto de
`/reservas/vehiculos` (plural, ya existente, lista todo el pool) — no colisiona a nivel de ruteo de
FastAPI (segmentos literales distintos en la segunda posición).

**API contract**

- Method + path: `GET /reservas/vehiculo/{patente}`
- Request: `patente` (path param, string, `min_length=1`, `max_length=10`, `pattern=^[A-Za-z0-9]+$`)
- Response: `200` con `list[ReservaListItem]` (schema ya existente: `id`, `vehiculo_id`,
  `nombre_empleado`, `fecha_inicio`, `fecha_fin`, `destino`, `estado`, `created_at`, `updated_at`,
  `patente`, `tipo` — sin `legajo` ni `licencia`)
- Error codes: `404` (patente inexistente), `422` (formato de patente inválido, validado por
  FastAPI antes de llegar al handler), `429` (rate limit, 60/min por IP)
- Auth: ninguna — endpoint público, mismo criterio que los otros 4 endpoints de `/reservas`

**Error handling**

- Patente que no corresponde a ningún vehículo del pool: `VehiculoNoEncontradoError` → 404 (AC-03).
- Patente válida sin reservas activas: no es un error — `consultar_reservas_activas_por_patente`
  devuelve una lista vacía, el router responde 200 con `[]` (AC-02).
- Más de 60 consultas por minuto desde la misma IP: 429 (mismo mecanismo que los otros 4 endpoints
  de este router).
- Patente con formato inválido (no alfanumérico, o más de 10 caracteres): FastAPI la rechaza en la
  validación del `Path(...)` con 422, antes de llegar a `service.py`.

**Required tests**

- [ ] `test_consultar_reservas_activas_por_patente_con_activas` — patente con reservas activas →
      devuelve exactamente esas reservas — valida AC-01.
- [ ] `test_consultar_reservas_activas_por_patente_sin_activas` — patente sin reservas activas →
      lista vacía, no error — valida AC-02.
- [ ] `test_consultar_reservas_activas_por_patente_excluye_pasadas_y_canceladas` — un vehículo con
      una reserva pasada y otra cancelada (ambas con `estado`/fechas fuera de la ventana "activa") no
      las incluye en el resultado — valida AC-02 (semántica de "activa", no solo la lista vacía).
- [ ] `test_consultar_reservas_activas_por_patente_incluye_campos_requeridos` — cada ítem devuelto
      trae nombre del empleado, fecha_inicio, fecha_fin y destino — valida AC-04.
- [ ] `test_consultar_reservas_activas_patente_inexistente` — patente que no existe en el pool →
      `VehiculoNoEncontradoError` — valida AC-03.
- [ ] `test_consultar_reservas_activas_patente_case_insensitive` — consulta con casing distinto al
      guardado, igual encuentra el vehículo (usa Block 1) — valida AC-01/AC-02 junto con FR-05.
- [ ] `test_router_get_reservas_vehiculo_200` — integración: `GET /reservas/vehiculo/{patente}` con
      patente existente → 200, body con la forma de `ReservaListItem`.
- [ ] `test_router_get_reservas_vehiculo_404` — patente inexistente → 404 con `detail` descriptivo.
- [ ] `test_router_get_reservas_vehiculo_rate_limit` — más de 60 requests/minuto → 429, mismo patrón
      que los tests de rate limit ya existentes para los otros endpoints del router.
- [ ] `test_router_get_reservas_vehiculo_patente_invalida_422` — patente con caracteres no
      alfanuméricos o de más de 10 caracteres → 422, sin llegar a `service.py`.

**Completion criterion**

Las 10 tests pasan; `GET /reservas/vehiculo/{patente}` responde 200 con las reservas activas
correctas, 200 con `[]` cuando no hay activas, y 404 cuando la patente no existe, incluyendo cuando
se la escribe con un casing distinto al guardado.

## Block 3 — UI de búsqueda por patente

**Files**
- `frontend/src/features/reservas/reservasApi.js` (modified) — nueva función
  `consultarReservasActivasPorVehiculo`.
- `frontend/src/features/reservas/ConsultaPorPatente.jsx` (new).
- `frontend/src/features/reservas/ConsultaPorPatente.test.jsx` (new).
- `frontend/src/features/reservas/ReservasListado.jsx` (modified) — monta `ConsultaPorPatente` al
  inicio de la página.
- `frontend/src/features/reservas/ReservasListado.test.jsx` (modified) — agrega el mock de la nueva
  función de API.

**Logic**

`reservasApi.js` — nueva función, mismo patrón que las 5 existentes:
```js
export async function consultarReservasActivasPorVehiculo(patente) {
  try {
    const { data } = await apiClient.get(`/reservas/vehiculo/${patente}`);
    return data;
  } catch (error) {
    return propagarError(error);
  }
}
```

`ConsultaPorPatente.jsx`: un `<input>` controlado + botón "Buscar". Al enviar el formulario (no al
montar el componente — a diferencia de `ReservasListado`, esta consulta es on-demand), llama a
`consultarReservasActivasPorVehiculo(patente)` y renderiza:
- si hay resultados: la lista de reservas activas (mismos campos que `ReservasListado` ya muestra
  por fila: patente, nombre, fechas, destino — sin patente/tipo repetidos ya que el usuario los
  acaba de tipear).
- si la respuesta es `[]`: un mensaje "Este vehículo no tiene reservas activas." (`role="status"`).
- si la respuesta es un 404: un mensaje "No se encontró ningún vehículo con esa patente."
  (`role="alert"`), usando el mismo patrón `mensajeDeError`/`MENSAJES_ERROR` que ya usa
  `ReservasListado.jsx` (se define localmente en este componente, con la entrada `404` propia de este
  contexto — el `404` de `ReservasListado.jsx` significa "la reserva ya no existe", un mensaje
  distinto para el mismo código HTTP en un contexto distinto, así que no se comparte el diccionario).

**Desacoplamiento explícito (resuelve el WARN del arch-auditor):** `ConsultaPorPatente` NO recibe
props de `ReservasListado` ni le notifica nada al encontrar resultados. Es un panel de búsqueda
independiente montado arriba del listado general — no refresca ni filtra el listado general, no
comparte estado. Un desarrollador que revise el componente no debe esperar ningún efecto sobre
`ReservasListado` más allá de aparecer visualmente antes en la misma página.

`ReservasListado.jsx`: agregar `<ConsultaPorPatente />` como primer elemento dentro del `<div>` raíz,
antes del `<h1>Reservas</h1>` existente (o inmediatamente después — decisión de UI menor, no afecta
comportamiento). Ningún otro cambio a este archivo.

`ReservasListado.test.jsx`: el `vi.mock("./reservasApi", ...)` factory debe agregar
`consultarReservasActivasPorVehiculo: vi.fn()` (aunque los tests existentes de este archivo no la
invoquen) — de lo contrario, montar `<ReservasListado />` en esos tests rompe porque
`ConsultaPorPatente` importa una función que el mock no expone.

**Error handling**

- Patente vacía enviada: el `<input required>` nativo del formulario bloquea el submit — sin
  necesidad de un mensaje de validación propio en JS.
- Error de red (`error.status === null`, mismo patrón que `propagarError`): mensaje genérico "No se
  pudo conectar con el servidor." (ya lo provee `mensajeDeError`/`error.message`).
- 429 (rate limit): mismo mensaje ya usado en `ReservasListado.jsx`
  ("Demasiadas solicitudes. Esperá unos minutos e intentá de nuevo.") — se reutiliza el texto, cada
  componente define su propio diccionario de mensajes.

**Required tests**

- [ ] `renderiza el formulario de búsqueda` — input + botón presentes al montar.
- [ ] `busca y muestra reservas activas al enviar una patente con resultados` — mock de
      `consultarReservasActivasPorVehiculo` resuelve con reservas, se muestran tras el submit.
- [ ] `muestra mensaje de "sin reservas activas" cuando la respuesta es una lista vacía`.
- [ ] `muestra mensaje de error cuando la patente no existe (404)`.
- [ ] `no llama a la API antes de que el usuario envíe el formulario` — confirma que es on-demand,
      no on-mount (a diferencia de `ReservasListado`).
- [ ] `muestra mensaje de rate limit cuando la API responde 429` — mismo texto ya usado en
      `ReservasListado.jsx`, confirmando que este componente también lo maneja.
- [ ] `ReservasListado.test.jsx` sigue pasando con el mock actualizado — regresión, confirma que
      montar `ConsultaPorPatente` dentro de `ReservasListado` no rompe sus tests existentes.

**Completion criterion**

Las 6 tests nuevos de `ConsultaPorPatente.test.jsx` pasan; los tests existentes de
`ReservasListado.test.jsx` siguen pasando con el mock actualizado; `npm run lint` sin errores.

## Final verification

- Los 3 bloques implementados y sus tests en verde: 5 (Block 1) + 10 (Block 2) + 7 (Block 3,
  incluyendo la regresión de `ReservasListado.test.jsx`) = 22 tests nuevos/actualizados.
- `alembic upgrade head` aplica limpio sobre la base de test.
- `GET /reservas/vehiculo/{patente}` responde correctamente en los 3 casos (activas, vacío, 404),
  incluyendo con casing distinto al guardado.
- `crear_vehiculo`/`modificar_vehiculo` rechazan patentes duplicadas en cualquier casing, tanto por
  el pre-chequeo de `service.py` como, en el límite, por el índice único de la base.
- Ningún test preexistente de FEAT-001a/b/c/d/e se rompe.
