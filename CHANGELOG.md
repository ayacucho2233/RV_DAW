# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Unreleased]

### Added

- **FEAT-005** — Estado `caducada` para reservas activas vencidas: `POST /reservas/caducar-vencidas`
  transiciona en un `UPDATE` masivo toda reserva `activa` con `fecha_fin` ya pasada, disparado
  automáticamente por el frontend una sola vez al cargar la página. Equivalente a `cancelada`
  para toda la lógica existente (solapamiento, disponibilidad, baja de vehículo, cancelación) sin
  tocar ese código — queda excluida por construcción, igual que `cancelada`.
- **FEAT-004** — Consulta de reservas activas por patente: `GET /reservas/vehiculo/{patente}`
  devuelve las reservas activas de un vehículo puntual (búsqueda case-insensitive), con panel de
  búsqueda en el frontend independiente del listado general. De paso, cierra un hueco de FEAT-001a:
  la unicidad de patente ahora es case-insensitive (índice único de base), no solo exacta.
- **FEAT-003** — CI en GitHub Actions: workflow `.github/workflows/ci.yml` que en cada Pull Request
  instala dependencias, corre la suite de tests (pytest + vitest) y el linter (ruff + eslint) de
  backend y frontend en paralelo, contra un servicio PostgreSQL efímero para los tests del backend.
- **FEAT-002** — Menú principal y rediseño visual del frontend: nueva pantalla de menú con
  navegación a las 3 áreas de la app (Administrador, Gestionar reservas, Consultar), botones
  "Volver al menú"/"Cerrar sesión", y una paleta de colores + set de íconos SVG consistente en
  toda la aplicación, sin modificar la lógica de negocio de ninguna pantalla existente.
- **FEAT-001e** — Integración con el ciclo de vida del vehículo: dar de baja (temporal o
  definitiva) un vehículo con reservas activas ahora se rechaza con 409, usando el mismo lock
  (`SELECT ... FOR UPDATE`) que ya usa la creación de reservas para prevenir condiciones de
  carrera. Las reservas pasadas de un vehículo dado de baja siguen visibles en el listado.
- **FEAT-001d** — Listado, filtros y cancelación de reservas: endpoint público `GET /reservas`
  (filtro opcional por período `futuras`/`en_curso`/`pasadas`) y `PATCH /reservas/{id}/cancelar`
  (valida que el legajo coincida con el de la reserva), con rate limiting independiente por
  endpoint y vista de listado en React con cancelación inline por fila.
- **FEAT-001c** — Consulta y creación de reservas: endpoints públicos (`GET /reservas/vehiculos`,
  `GET /reservas/disponibilidad`, `POST /reservas`), prevención de solapamientos con
  `SELECT ... FOR UPDATE`, rechazo de reservas sobre vehículos no activos, y vista pública en React
  para listar el pool, consultar disponibilidad y dar de alta una reserva.
- **FEAT-001a** — Gestión del pool de vehículos: alta, modificación, baja temporal/definitiva y
  reactivación de vehículos, protegidos con HTTP Basic para el administrador, y el panel de
  administración correspondiente en React (PR #1, en revisión).

### Fixed

- **FIX-004** — `obtener_por_patente_normalizada` comparaba con `func.upper()`, pero el índice
  único de la migración de FEAT-004 está construido sobre `lower(patente)` — Postgres no usaba ese
  índice (confirmado con `EXPLAIN`: `Seq Scan` en vez de `Index Scan`), afectando cada alta,
  modificación y consulta por patente. El resultado ya era correcto; ahora también está indexado.
- **FIX-001** — `test_config_falla_sin_database_url` no detectaba la ausencia real de
  `DATABASE_URL`: `Settings` (pydantic-settings) seguía leyendo el valor desde `backend/.env`
  aunque el test lo borrara de `os.environ`. Se agrega `_reload_config_sin_env_file()`, que
  instancia `Settings` con `_env_file=None` para simular correctamente la ausencia de la
  variable.
- **FIX-003** — `ruff` (backend) y `eslint` (frontend) quedan configurados correctamente:
  `backend/ruff.toml` reconoce el patrón de inyección de dependencias de FastAPI
  (`Depends`/`Query`/`Path`/etc.) en vez de marcarlo como bug, y se desactiva la regla
  `react-hooks/set-state-in-effect` de eslint por conflictuar con el patrón "fetch on mount"
  ya establecido en el proyecto. Se corrigen además 24 hallazgos reales de estilo (imports sin
  ordenar, `dict()` reescrito como literal, `with` anidados combinados, código muerto en
  `client.js`, variables sin usar en tests), sin cambios de comportamiento.
