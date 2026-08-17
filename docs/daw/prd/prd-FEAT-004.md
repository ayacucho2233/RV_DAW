# PRD FEAT-004: Consulta de reservas activas por patente

| Field | Value |
|-------|-------|
| Ticket | FEAT-004 |
| Tracker | none |
| Date | 2026-08-17 |
| PRD loops | 0 |

## Context and Problem

El sistema ya permite listar todas las reservas y filtrarlas por estado (futuras / en curso /
pasadas — FEAT-001d), pero no hay forma de consultar directamente las reservas de **un vehículo en
particular**. Alguien que quiere saber "¿este vehículo tiene reservas activas ahora mismo?" tiene
que revisar el listado completo a mano y buscar las filas que correspondan a esa patente.

Este ticket agrega una consulta acotada: dado el número de patente de un vehículo del pool, mostrar
únicamente sus reservas **activas** (mismo criterio ya establecido en FEAT-001c: período futuro o en
curso, y no cancelada).

**Personas:**
- **Empleado o cualquier consultante:** igual que las consultas ya existentes de disponibilidad y
  listado (FEAT-001c, FEAT-001d), esta consulta es pública, sin autenticación.

## Goals

- Permitir saber, para un vehículo puntual, si tiene reservas activas y cuáles son, sin tener que
  revisar el listado completo.
- Reutilizar la definición de "reserva activa" y el modelo de datos ya existentes, sin duplicar
  lógica de negocio.

## Functional Requirements

- FR-01: El sistema debe permitir consultar las reservas de un vehículo específico indicando su
  número de patente.
- FR-02: El sistema debe devolver únicamente las reservas activas del vehículo consultado (período
  futuro o en curso, no cancelada).
- FR-03: El sistema debe informar cuando la patente consultada no corresponde a ningún vehículo del
  pool.
- FR-04: El sistema debe incluir, para cada reserva activa devuelta, al menos: nombre del empleado,
  fecha/hora de inicio, fecha/hora de fin y destino.

## Non-Functional Requirements

- NFR-01: El sistema debe responder la consulta de reservas por patente en menos de 2 segundos,
  medido en el percentil 95 (p95), bajo carga normal esperada.

## Acceptance Criteria

- AC-01: WHEN se consulta con la patente (FR-01) de un vehículo del pool que tiene reservas
  activas, THE sistema SHALL devolver el listado de esas reservas activas (FR-02).
- AC-02: WHEN se consulta con la patente (FR-01) de un vehículo del pool que no tiene reservas
  activas (FR-02), THE sistema SHALL devolver una lista vacía, no un error.
- AC-03: IF la patente consultada (FR-01) no corresponde a ningún vehículo del pool, THEN THE
  sistema SHALL responder con un error 404 informando que el vehículo no existe (FR-03).
- AC-04: WHEN el sistema devuelve las reservas activas de un vehículo (FR-02), THE sistema SHALL
  incluir en cada una el nombre del empleado, la fecha/hora de inicio, la fecha/hora de fin y el
  destino (FR-04).

## Out of Scope

- Reservas pasadas o canceladas del vehículo consultado — ya cubiertas por el listado general con
  filtro de estado de FEAT-001d; esta consulta no las duplica.
- Modificar o cancelar una reserva desde esta consulta (cubierto por FEAT-001d).
- Autenticación — sigue el mismo criterio público que las demás consultas de FEAT-001c/FEAT-001d.
- Búsqueda por criterios distintos a la patente exacta (tipo de vehículo, rango de fechas propio,
  texto libre).
- Cambios al modelo de datos de vehículos o reservas — esta consulta reutiliza el modelo existente.

## Risks and Mitigations

- **Riesgo:** una patente ingresada con mayúsculas/minúsculas o espacios distintos a como está
  guardada no matchea por una comparación exacta de string, y el sistema responde 404 sobre un
  vehículo que sí existe.
  **Mitigación:** normalizar la comparación (case-insensitive, sin espacios extra) al buscar por
  patente — a confirmar en PLAN si el modelo de FEAT-001a ya normaliza la patente al guardarla, o si
  hay que agregar la normalización en esta consulta.

## Dependencies

- FEAT-001a — modelo de datos de vehículos (patente, estado).
- FEAT-001c — modelo de datos de reservas y definición de "reserva activa".
- FEAT-001d — patrón ya existente de listar/filtrar reservas (mismo estilo de endpoint público).
