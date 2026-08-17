# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Unreleased]

### Added

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

- **FIX-001** — `test_config_falla_sin_database_url` no detectaba la ausencia real de
  `DATABASE_URL`: `Settings` (pydantic-settings) seguía leyendo el valor desde `backend/.env`
  aunque el test lo borrara de `os.environ`. Se agrega `_reload_config_sin_env_file()`, que
  instancia `Settings` con `_env_file=None` para simular correctamente la ausencia de la
  variable.
