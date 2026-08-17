# Threat Model FEAT-004: Consulta de reservas activas por patente

| Field | Value |
|-------|-------|
| Ticket | FEAT-004 |
| Date | 2026-08-17 |
| Design reviewed | 1 bloque: `GET /reservas/vehiculo/{patente}` + unicidad case-insensitive en alta/modificación de vehículos (FR-05) |

## Componentes y superficies de ataque

1. **`GET /reservas/vehiculo/{patente}`** (nuevo, público, sin auth) — recibe `patente` como path
   param de cualquier usuario anónimo.
2. **`obtener_por_patente_normalizada`** (nuevo, en `vehiculos/repository.py`) — query SQL
   case-insensitive contra la tabla `vehiculos`, parametrizada vía SQLAlchemy (sin concatenación de
   strings).
3. **`POST /vehiculos` y `PATCH /vehiculos/{id}`** (existentes, protegidos con HTTP Basic) — su
   validación de unicidad de patente se amplía de exact-match a case-insensitive (FR-05).
4. **Nueva migración Alembic**: índice único funcional case-insensitive sobre `vehiculos.patente`.

## Trust boundaries

- **Usuario anónimo → `GET /reservas/vehiculo/{patente}`**: sin cambios respecto a los otros 4
  endpoints públicos de `/reservas` ya existentes — mismo límite de confianza ya aceptado en
  FEAT-001c/FEAT-001d.
- **Administrador autenticado (HTTP Basic) → alta/modificación de vehículos**: límite ya existente de
  FEAT-001a; este ticket no lo modifica, solo agrega una regla de validación dentro de él.
- **Aplicación → Base de datos**: sin cambios — todo acceso sigue vía SQLAlchemy parametrizado, sin
  SQL crudo.

## Análisis STRIDE

### `GET /reservas/vehiculo/{patente}`

| Categoría | Evaluación |
|---|---|
| Spoofing | N/A — endpoint público por diseño, mismo criterio que sus 4 hermanos. |
| Tampering | Bajo. `patente` se compara vía `func.upper(...)` de SQLAlchemy (parametrizado) — sin concatenación de strings, sin superficie de inyección. |
| Repudiation | Bajo. Es una consulta de solo lectura; ninguno de los otros GETs de este router loguea tampoco (el logging existente solo cubre altas/cancelaciones — mutaciones). Consistente, no es un gap nuevo. |
| Information Disclosure | Bajo. Reutiliza `ReservaListItem`, que ya excluye `legajo`/`licencia` (mitigación TM-D-01 de FEAT-001d). Acotar por vehículo no expone campos nuevos, solo reduce filas frente al listado general ya público. |
| Denial of Service | Bajo. `Path(..., max_length=10)` acota el tamaño del input; rate limit de 60/min con clave propia (`"reservas-por-patente"`), mismo mecanismo ya validado en FEAT-001c/d. |
| Elevation of Privilege | N/A — no hay escalamiento posible en una consulta de solo lectura sin auth de por medio. |

### Unicidad case-insensitive de patente (FR-05)

| Categoría | Evaluación |
|---|---|
| Spoofing / Repudiation | N/A. |
| Tampering | N/A — no se modifican datos ajenos, solo se agrega una regla de validación. |
| Information Disclosure | N/A. |
| Denial of Service | N/A. |
| **Elevation of Privilege / Tampering (carrera)** | 🟡 **MEDIO**: si la unicidad case-insensitive se implementa solo como chequeo previo en `service.py` (sin constraint a nivel de base), dos altas concurrentes con patentes que solo difieren en casing (p. ej. "ABC123" y "abc123") podrían pasar ambas el chequeo antes de que cualquiera termine de insertar — condición de carrera TOCTOU, el mismo patrón que la unicidad exacta de FEAT-001a ya resuelve con un `UNIQUE` de base + `IntegrityError` → `PatenteYaExisteError`. |

## Riesgos clasificados

| Riesgo | STRIDE | Likelihood | Impact | Mitigación |
|---|---|---|---|---|
| Carrera TOCTOU entre dos altas/modificaciones concurrentes con patente duplicada en distinto casing | Tampering/EoP | Baja | Medio | Índice único funcional case-insensitive en `vehiculos.patente` a nivel de base (migración Alembic), con el mismo patrón ya usado para la unicidad exacta: `service.py` hace un chequeo previo (UX, mensaje claro) y `repository.py` traduce el `IntegrityError` del `UNIQUE` de base a `PatenteYaExisteError` — cierra la carrera igual que ya lo hace la unicidad exacta existente. |
| Resultado ambiguo (`MultipleResultsFound`) en `obtener_por_patente_normalizada` si, por cualquier motivo (migración no aplicada aún en un ambiente, dato heredado), existen 2 filas que matchean | Tampering | Baja | Bajo | La query usa `.limit(1)` (no `scalar_one_or_none()`): siempre devuelve un resultado determinístico en vez de levantar una excepción no controlada, incluso en el escenario límite. |
| La migración del índice único falla si ya existen duplicados case-insensitive en los datos actuales | — | Baja | Bajo | Verificar antes de aplicar la migración que no existan duplicados en el pool actual (ya documentado en el PRD, sección Risks). |

Sin riesgos CRITICAL ni HIGH.

## Mitigaciones a incorporar en el spec

1. `obtener_por_patente_normalizada` usa `.limit(1)` / `.first()`, nunca `scalar_one_or_none()`.
2. La unicidad case-insensitive se cierra en dos capas, igual que la unicidad exacta ya existente:
   chequeo previo en `service.py` + índice único funcional en la base (migración Alembic) +
   traducción de `IntegrityError` a `PatenteYaExisteError` en `vehiculos/repository.py`.
3. Antes de aplicar la migración, confirmar que no existan duplicados case-insensitive en los datos
   actuales del pool.

## Resumen

- Superficies de ataque identificadas: 4
- Trust boundaries declaradas: 3 (sin cambios respecto a las ya existentes)
- Riesgos: C:0 H:0 M:1 L:2
- Datos sensibles manejados: ninguno nuevo — `ReservaListItem` ya excluye PII sensible (legajo,
  licencia); la unicidad de patente no maneja datos personales.
