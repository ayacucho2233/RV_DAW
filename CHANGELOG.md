# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Unreleased]

### Added

- **FEAT-001c** — Consulta y creación de reservas: endpoints públicos (`GET /reservas/vehiculos`,
  `GET /reservas/disponibilidad`, `POST /reservas`), prevención de solapamientos con
  `SELECT ... FOR UPDATE`, rechazo de reservas sobre vehículos no activos, y vista pública en React
  para listar el pool, consultar disponibilidad y dar de alta una reserva.
- **FEAT-001a** — Gestión del pool de vehículos: alta, modificación, baja temporal/definitiva y
  reactivación de vehículos, protegidos con HTTP Basic para el administrador, y el panel de
  administración correspondiente en React (PR #1, en revisión).
