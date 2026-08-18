# RCA FIX-005: Hardening de la búsqueda de patente

| Field | Value |
|-------|-------|
| Ticket | FIX-005 |
| Date | 2026-08-18 |
| Origen | Security/edge-case review manual del diff de FEAT-004 (no un gate automático) |
| PRD asociado | Ninguno — hardening transversal sobre código ya mergeado, no una feature nueva (mismo criterio que FIX-003) |

## Contexto

FEAT-004 (consulta de reservas activas por patente + unicidad case-insensitive de vehículos) ya está
mergeado a `main`. FIX-004, mergeado después, corrigió el hallazgo bloqueante de esa review (mismatch
`upper()`/`lower()` entre la query y el índice). Quedan 3 hallazgos adicionales, todos nivel
"debería" (no bloqueantes, pero reales), en el mismo área de código.

## Hallazgo A — Validación de patente ausente en la capa de servicio

**Síntoma:** `consultar_reservas_activas_por_patente` (`backend/app/features/reservas/service.py`)
no valida el formato de `patente` por su cuenta. Depende enteramente de que quien la llame ya haya
pasado por el `Path(pattern=r"^[A-Za-z0-9]+$", min_length=1, max_length=10)` del router
(`GET /reservas/vehiculo/{patente}`).

**Causa raíz:** al diseñar Block 2 de FEAT-004, la validación de formato se puso únicamente en la
capa HTTP (FastAPI `Path(...)`) porque es el único caller hoy. No se replicó en `service.py` como sí
ocurre, por contraste, en `crear_vehiculo`/`modificar_vehiculo` (`vehiculos/service.py`), que reciben
`patente` ya validada por Pydantic (`VehiculoCreate`/`VehiculoUpdate` → `VehiculoBase.patente`,
mismo patrón `^[A-Za-z0-9]+$`) antes de llegar a esa capa — es decir, dos de los tres call sites de
`obtener_por_patente_normalizada` sí tienen defensa en profundidad; el tercero (la consulta de
reservas) no.

**Impacto:** hoy, ninguno (el único caller real es el router, que ya valida). El riesgo es a futuro:
un caller interno nuevo (script, job, otro endpoint) que invoque `consultar_reservas_activas_por_patente`
directo, sin pasar por FastAPI, no tendría ninguna barrera de formato.

## Hallazgo B — `.limit(1)` sin `ORDER BY` no es realmente determinístico

**Síntoma:** el docstring de `obtener_por_patente_normalizada`
(`backend/app/features/vehiculos/repository.py`) y el threat model de FEAT-004 afirman que
`.limit(1)` hace la búsqueda "determinística". Es impreciso: `.limit(1)` sin `ORDER BY` solo
garantiza que la query nunca levante `MultipleResultsFound` — no garantiza **cuál** fila devuelve si
hubiera más de una candidata. Postgres no promete ningún orden estable sin un `ORDER BY` explícito.

**Causa raíz:** al escribir la mitigación en PLAN de FEAT-004, se conflacionó "no explota" con
"es determinístico" — son garantías distintas. El índice único de FIX-004/FEAT-004 hace que hoy no
puedan existir duplicados *después* de la migración, pero la propia query no depende de esa garantía
externa para ser determinística por sí misma.

**Impacto:** bajo hoy (el índice único ya impide la ambigüedad en la práctica). El riesgo es en
ambientes donde la migración `0003` todavía no se aplicó, o con datos heredados de antes de que
existiera: dos llamadas sucesivas a `obtener_por_patente_normalizada` con el mismo `patente` podrían
devolver vehículos distintos entre sí.

## Hallazgo C — La migración no chequea duplicados existentes antes de crear el índice único

**Síntoma:** `backend/alembic/versions/0003_patente_unique_case_insensitive.py::upgrade()` intenta
crear el índice único funcional directamente. Si ya existen en la tabla dos filas con la misma
patente en distinto casing, `CREATE UNIQUE INDEX` falla con un error crudo de Postgres
(`duplicate key value violates unique constraint`), sin ningún mensaje que indique cuáles patentes
están en conflicto.

**Causa raíz:** el PRD de FEAT-004 (sección "Risks and Mitigations") documentó la verificación
previa como un **paso operativo manual** ("correr `SELECT lower(patente), COUNT(*)...` antes de
migrar") — nunca se convirtió en código. La migración confía en que quien despliegue haya leído y
seguido esa instrucción en un documento aparte.

**Impacto:** si alguien aplica `alembic upgrade head` en un ambiente con datos reales sin haber
corrido el chequeo manual, el deploy falla a mitad de camino con un error que no dice qué patentes
hay que resolver — hay que investigarlo aparte, potencialmente durante una ventana de mantenimiento.

## Alcance del fix

Los 3 hallazgos se resuelven en un único ticket porque comparten área de código
(`vehiculos/repository.py`, `reservas/service.py`, la migración `0003`) y ninguno requiere decisiones
de producto — son correcciones de robustez con comportamiento visible sin cambios para el flujo
normal (HTTP ya validado, datos sin duplicados). El diseño técnico de cada uno se detalla en el
fix-plan de PLAN.

## Regresión

No aplica un único "bug reproducible" como en FIX-004 — son 3 gaps de robustez distintos, cada uno
con su propio test de regresión, detallados en el fix-plan.
