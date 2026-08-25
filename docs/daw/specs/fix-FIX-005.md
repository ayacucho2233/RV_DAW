# Fix-plan FIX-005: Hardening de la búsqueda de patente

| Field | Value |
|-------|-------|
| Ticket | FIX-005 |
| Tier | FIX |
| RCA | docs/daw/specs/rca-FIX-005.md |
| Date | 2026-08-18 |
| Spec loops | 0 |

## Problem

3 gaps de robustez detectados en una review manual del diff de FEAT-004 (ya con su hallazgo
bloqueante corregido en FIX-004): (A) la consulta de reservas por patente no valida el formato de
forma independiente del router; (B) la búsqueda case-insensitive de patente no es realmente
determinística sin `ORDER BY`; (C) la migración que crea el índice único no chequea duplicados
existentes antes de intentar crearlo, fallando con un error críptico si los hay.

## Root cause

Ver `docs/daw/specs/rca-FIX-005.md`. Resumen: (A) la validación de formato se puso solo en la capa
HTTP al diseñar FEAT-004, sin replicarla en el service — a diferencia de los otros 2 callers de
`obtener_por_patente_normalizada`, que sí reciben input ya validado por Pydantic; (B) se conflacionó
"no explota" (`.limit(1)`) con "es determinístico" (requiere `ORDER BY`); (C) el chequeo de
duplicados se documentó como paso manual en el PRD de FEAT-004, nunca se convirtió en código.

## Solution — steps

1. `backend/app/features/vehiculos/schemas.py` — extraer el patrón `r"^[A-Za-z0-9]+$"` (hoy un
   literal en `VehiculoBase.patente`) a una constante módulo-level `PATENTE_PATTERN`, y usarla en
   `VehiculoBase.patente = Field(..., min_length=1, max_length=10, pattern=PATENTE_PATTERN)`.
2. `backend/app/features/reservas/exceptions.py` — agregar `PatenteFormatoInvalidoError(ReservaDomainError)`,
   mismo estilo que las excepciones existentes del archivo (constructor recibe `patente: str`,
   mensaje descriptivo). Sigue el precedente de `TipoInvalidoError` en `vehiculos/exceptions.py`: una
   excepción nueva por tipo de fallo, no la reutilización de `VehiculoNoEncontradoError` (que
   significa otra cosa: "no existe", no "formato inválido").
3. `backend/app/features/reservas/service.py:180` (`consultar_reservas_activas_por_patente`) — al
   inicio de la función, antes de llamar a `vehiculos_repository.obtener_por_patente_normalizada`,
   validar `patente` contra `PATENTE_PATTERN` (importada de `vehiculos.schemas`, solo lectura entre
   features — mismo patrón cruzado ya usado por este archivo) y longitud 1-10; si no matchea,
   levantar `PatenteFormatoInvalidoError(patente)`.
4. `backend/app/features/reservas/router.py` — importar `PATENTE_PATTERN` de `vehiculos.schemas` y
   usarla en el `Path(pattern=PATENTE_PATTERN)` del endpoint `GET /reservas/vehiculo/{patente}` (en
   vez del literal actual, cerrando el magic-string drift entre las 2 copias ya existentes antes de
   este fix); agregar `PatenteFormatoInvalidoError: status.HTTP_422_UNPROCESSABLE_ENTITY` a
   `_MAPEO_ERRORES_HTTP`; agregar `PatenteFormatoInvalidoError` al `except` del endpoint
   `consultar_reservas_por_patente`.
5. `backend/app/features/vehiculos/repository.py:56` (`obtener_por_patente_normalizada`) — agregar
   `.order_by(Vehiculo.id)` a la query, mismo criterio ya usado en `obtener_por_id`/
   `obtener_por_id_con_lock` (ordenar sobre la PK). Corregir el docstring: `.limit(1)` por sí solo
   evita `MultipleResultsFound`, pero NO garantiza determinismo entre llamadas si hubiera más de una
   fila candidata — el determinismo real lo da el `ORDER BY`.
6. `backend/alembic/versions/0003_patente_unique_case_insensitive.py::upgrade()` — antes de
   `op.create_index(...)`, ejecutar vía `op.get_bind()` la query
   `SELECT lower(patente), COUNT(*) FROM vehiculos GROUP BY lower(patente) HAVING COUNT(*) > 1`; si
   devuelve filas, levantar `RuntimeError` listando las patentes en conflicto (agrupadas por su forma
   en minúscula), antes de intentar crear el índice. Agregar un comentario documentando la ventana
   TOCTOU aceptada (riesgo aceptado del threat model, `docs/daw/security/threat-FIX-005.md`): este
   chequeo no es atómico con la creación del índice, asume una ventana de mantenimiento sin
   escritura concurrente.

## Dependencies between steps

- Paso 1 (constante `PATENTE_PATTERN`) debe ir antes que 3 y 4, que la importan.
- Pasos 2 y 3 están acoplados (la excepción nueva se usa en el mismo paso que valida el formato).
- Paso 5 y 6 son independientes entre sí y del resto de los pasos.
- Orden de implementación sugerido: 1 → 2 → 3 → 4 → 5 → 6 (5 y 6 podrían ir en paralelo si se
  prefiere, no cambia el resultado).

## Error handling

- `patente` con formato inválido en `consultar_reservas_activas_por_patente`: `PatenteFormatoInvalidoError`
  → 422, sin llegar a tocar la base de datos (a diferencia de hoy, donde igual se ejecuta la query y
  termina en `VehiculoNoEncontradoError` → 404 — el comportamiento HTTP observable no cambia para
  ningún caller vía el router, porque el `Path()` de FastAPI ya rechaza esos casos con 422 antes de
  llegar al service; el fix es defensa en profundidad para callers directos del service).
- Duplicados detectados en la migración: `RuntimeError` con las patentes en conflicto listadas, en
  vez de dejar que Postgres levante `duplicate key value violates unique constraint` sin contexto —
  la migración se detiene antes de intentar `CREATE UNIQUE INDEX`.
- Los otros 2 callers de `obtener_por_patente_normalizada` (`crear_vehiculo`, `modificar_vehiculo`)
  no cambian su manejo de errores — siguen recibiendo `patente` pre-validada por Pydantic, Fix A no
  los toca.

## Tests

- [ ] **Regression test A1** (`test_reservas_service.py`): `consultar_reservas_activas_por_patente`
      con una patente que contiene un carácter no alfanumérico (ej. `"AB-123"`) levanta
      `PatenteFormatoInvalidoError` **sin invocar**
      `vehiculos_repository.obtener_por_patente_normalizada` (verificado con un spy/mock) — falla
      antes del fix (no existe esa excepción todavía; llamando a la función tal como está hoy,
      terminaría en `VehiculoNoEncontradoError` en vez de `PatenteFormatoInvalidoError`), pasa
      después.
- [ ] **Regression test A2** (`test_reservas_router.py`): `GET /reservas/vehiculo/{patente}` sigue
      devolviendo 422 para una patente inválida — regresión explícita sobre
      `test_router_get_reservas_vehiculo_patente_invalida_422` (ya existente de FEAT-004), que debe
      seguir pasando con el nuevo `_MAPEO_ERRORES_HTTP` y el `Path(pattern=PATENTE_PATTERN)`.
- [ ] **Regression test B1** (`test_migration_patente_unique_ci.py`): con 2 filas insertadas
      directamente (bypaseando `service.py`, mismo patrón que el test de migración ya existente) con
      patentes que difieren solo en casing, confirmar que la query compilada por
      `obtener_por_patente_normalizada` incluye `ORDER BY vehiculos.id` (inspeccionando el SQL
      generado, no solo el resultado — un resultado que "por casualidad" coincide no prueba
      determinismo real) — falla antes del fix (sin `ORDER BY` en la query), pasa después.
- [ ] **Regression test C1** (`test_migration_patente_unique_ci.py`): aplicar migraciones hasta
      `0002` (sin el índice único todavía), insertar 2 filas con patentes duplicadas en distinto
      casing directamente, y luego intentar `alembic upgrade head` (hacia `0003`) — debe fallar con
      un `RuntimeError` de Python (no un `IntegrityError`/error crudo de Postgres) que mencione
      ambas patentes en conflicto — falla antes del fix (hoy fallaría con el error crudo de
      Postgres, sin ese mensaje), pasa después.
- [ ] **Regresión general**: la suite completa de backend (FEAT-001a/c/d/e, FEAT-002, FEAT-003,
      FEAT-004, FIX-001..FIX-004) sigue pasando sin modificaciones.

## Regression risk

Bajo. Los 3 fixes son aditivos o correctivos sobre comportamiento no observado externamente hoy: el
resultado del flujo HTTP normal no cambia (el `Path()` del router ya rechazaba con 422 los formatos
inválidos antes de que existiera Fix A). El único cambio de comportamiento observable real es Fix C,
que solo se activa si ya existen duplicados case-insensitive en la tabla `vehiculos` — no debería
aplicar en ningún ambiente donde la migración `0003` ya se haya aplicado exitosamente (como `main`,
donde FEAT-004/FIX-004 ya están mergeados sin que la migración fallara).

## Rollback plan

- **Fix A, B**: trivial — revertir el commit. Sin migraciones, sin cambios de datos, sin estado
  persistente involucrado.
- **Fix C**: revertir el commit no afecta ningún ambiente donde `0003` ya se aplicó exitosamente,
  porque el pre-chequeo solo corre durante un `upgrade()` nuevo, no es una migración de datos
  retroactiva. El `downgrade()` de la migración (ya existente desde FEAT-004, sin cambios en este
  fix) sigue funcionando igual.
- **Indicadores para aplicar el rollback**: si alguno de los 3 fixes causa una regresión visible —
  ningún escenario de este tipo es esperable dado el análisis de impacto (0 gaps del impact-scan, 0
  FAILs del arch-audit), pero queda como criterio de reversión si apareciera uno.
