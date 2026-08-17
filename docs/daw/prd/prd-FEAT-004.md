# PRD FEAT-004: Consulta de reservas activas por patente

| Field | Value |
|-------|-------|
| Ticket | FEAT-004 |
| Tracker | none |
| Date | 2026-08-17 |
| PRD loops | 1 |

## Context and Problem

El sistema ya permite listar todas las reservas y filtrarlas por estado (futuras / en curso /
pasadas — FEAT-001d), pero no hay forma de consultar directamente las reservas de **un vehículo en
particular**. Alguien que quiere saber "¿este vehículo tiene reservas activas ahora mismo?" tiene
que revisar el listado completo a mano y buscar las filas que correspondan a esa patente.

Este ticket agrega una consulta acotada: dado el número de patente de un vehículo del pool, mostrar
únicamente sus reservas **activas** (mismo criterio ya establecido en FEAT-001c: período futuro o en
curso, y no cancelada).

**Ampliación (PRD loops 1):** al diseñar la búsqueda por patente en PLAN, se detectó que la
validación de unicidad de patente de FEAT-001a es sensible a mayúsculas/minúsculas — hoy nada impide
que existan simultáneamente, por ejemplo, "ABC123" y "abc123" como dos vehículos distintos del pool.
Si esta consulta buscara de forma case-insensitive sin cerrar ese hueco, una patente ambigua podría
devolver un resultado no determinístico. Se decidió, con el usuario, cerrar el hueco de raíz en este
mismo ticket en vez de aceptarlo como riesgo: la unicidad de patente pasa a ser case-insensitive
tanto al dar de alta como al modificar un vehículo (FR-05/AC-05/AC-06 más abajo).

**Personas:**
- **Empleado o cualquier consultante:** igual que las consultas ya existentes de disponibilidad y
  listado (FEAT-001c, FEAT-001d), esta consulta es pública, sin autenticación.

## Goals

- Permitir saber, para un vehículo puntual, si tiene reservas activas y cuáles son, sin tener que
  revisar el listado completo.
- Reutilizar la definición de "reserva activa" y el modelo de datos ya existentes, sin duplicar
  lógica de negocio.
- Garantizar que la búsqueda por patente sea determinística: que no puedan existir dos vehículos en
  el pool cuya patente difiera solo en mayúsculas/minúsculas.

## Functional Requirements

- FR-01: El sistema debe permitir consultar las reservas de un vehículo específico indicando su
  número de patente.
- FR-02: El sistema debe devolver únicamente las reservas activas del vehículo consultado (período
  futuro o en curso, no cancelada).
- FR-03: El sistema debe informar cuando la patente consultada no corresponde a ningún vehículo del
  pool.
- FR-04: El sistema debe incluir, para cada reserva activa devuelta, al menos: nombre del empleado,
  fecha/hora de inicio, fecha/hora de fin y destino.
- FR-05: El sistema debe garantizar que la patente de un vehículo sea única en el pool sin
  distinguir mayúsculas de minúsculas, tanto al darlo de alta como al modificarlo.

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
- AC-05: IF se intenta dar de alta un vehículo con una patente que ya existe en el pool en cualquier
  combinación de mayúsculas/minúsculas (FR-05), THEN THE sistema SHALL rechazar la operación e
  informar que la patente ya existe.
- AC-06: IF se intenta modificar un vehículo asignándole una patente que ya existe en otro vehículo
  del pool en cualquier combinación de mayúsculas/minúsculas (FR-05), THEN THE sistema SHALL rechazar
  la operación e informar que la patente ya existe.

## Out of Scope

- Reservas pasadas o canceladas del vehículo consultado — ya cubiertas por el listado general con
  filtro de estado de FEAT-001d; esta consulta no las duplica.
- Modificar o cancelar una reserva desde esta consulta (cubierto por FEAT-001d).
- Autenticación — sigue el mismo criterio público que las demás consultas de FEAT-001c/FEAT-001d.
- Búsqueda por criterios distintos a la patente exacta (tipo de vehículo, rango de fechas propio,
  texto libre).
- Cambios al modelo de datos de reservas — esta consulta reutiliza el modelo existente.
- Normalizar o migrar patentes ya guardadas con formato inconsistente (espacios, guiones) — FR-05
  solo cubre unicidad case-insensitive, no un formato canónico de patente.

## Risks and Mitigations

- **Riesgo:** una patente ingresada con mayúsculas/minúsculas distintas a como está guardada no
  matchea por una comparación exacta de string, y el sistema responde 404 sobre un vehículo que sí
  existe.
  **Mitigación:** la búsqueda por patente de esta consulta es case-insensitive (FR-01), y FR-05
  garantiza que esa búsqueda sea determinística al no permitir patentes duplicadas en distinto
  casing.
- **Riesgo:** si ya existen en el pool dos vehículos cuya patente difiere solo en
  mayúsculas/minúsculas al momento de aplicar la restricción de unicidad case-insensitive (FR-05), la
  migración que la crea falla.
  **Mitigación:** verificar antes de aplicar la migración que no existan duplicados actuales en el
  pool; de existir, resolverlos manualmente antes de continuar (el pool de este proyecto es de
  volumen bajo/de prueba, por lo que se confirma en PLAN si aplica).

## Dependencies

- FEAT-001a — modelo de datos de vehículos (patente, estado).
- FEAT-001c — modelo de datos de reservas y definición de "reserva activa".
- FEAT-001d — patrón ya existente de listar/filtrar reservas (mismo estilo de endpoint público).
