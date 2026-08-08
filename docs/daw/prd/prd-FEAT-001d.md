# PRD FEAT-001d: Listado, filtros y cancelación de reservas

| Field | Value |
|-------|-------|
| Ticket | FEAT-001d |
| Tracker | none |
| Date | 2026-08-05 |
| PRD loops | 0 |

## Context and Problem

Con la creación de reservas y la consulta de disponibilidad ya cubiertas (FEAT-001c), falta que los empleados puedan ver qué reservas existen, filtrarlas por estado, y cancelar las que ellos mismos crearon. Sin esto, una reserva creada es una reserva que nadie puede revisar ni deshacer.

**Personas:**
- **Empleado (conductor):** consulta el listado de reservas (propias o de otros, sin restricción de visibilidad) y puede cancelar únicamente las reservas que él mismo creó, identificándose por su número de legajo.

## Goals

- Permitir a cualquier empleado consultar el estado de las reservas del pool.
- Permitir cancelar una reserva propia de forma simple, sin fricción de autenticación adicional.
- Impedir que un empleado cancele una reserva que no le pertenece.

## Functional Requirements

- FR-01: El sistema debe listar las reservas existentes.
- FR-02: El sistema debe permitir filtrar reservas por estado (futuras, en curso, pasadas).
- FR-03: El sistema debe permitir cancelar una reserva existente indicando el número de legajo del solicitante.
- FR-04: El sistema no debe permitir cancelar una reserva a un empleado cuyo número de legajo no coincida con el del legajo que creó la reserva.

## Non-Functional Requirements

- NFR-01: El sistema debe responder consultas de listado y filtrado de reservas en menos de 2 segundos, medido en el percentil 95 (p95), bajo carga normal esperada.

## Acceptance Criteria

*(Entre paréntesis, el AC/FR original de PRD-FEAT-001b del que proviene, para trazabilidad — ver también la tabla al final del documento.)*

- AC-01 (FR-01): WHEN el empleado consulta el listado de reservas sin aplicar ningún filtro, THE sistema SHALL mostrar todas las reservas existentes.
- AC-02 (FR-02): WHEN el empleado filtra las reservas por estado "futuras", THE sistema SHALL mostrar únicamente las reservas con fecha de inicio posterior al momento actual.
- AC-03 (FR-02): WHEN el empleado filtra las reservas por estado "en curso", THE sistema SHALL mostrar únicamente las reservas cuyo período (inicio–fin) abarca el momento actual.
- AC-04 (FR-02): WHEN el empleado filtra las reservas por estado "pasadas", THE sistema SHALL mostrar únicamente las reservas con fecha de fin anterior al momento actual.
- AC-05 (FR-03): WHEN el empleado que creó la reserva solicita la cancelación indicando su número de legajo, THE sistema SHALL cancelar la reserva y dejar el vehículo disponible para ese período.
- AC-06 (FR-04): IF un empleado intenta cancelar una reserva con un número de legajo distinto al que la creó, THEN THE sistema SHALL rechazar la cancelación e informar que solo el solicitante original puede cancelarla.

## Out of Scope

- Creación de reservas y validación de disponibilidad/solapamiento (cubierto por FEAT-001c).
- Alta, modificación, baja y reactivación de vehículos (cubierto por FEAT-001a).
- Bloqueo de la baja de un vehículo con reservas activas, y visibilidad de reservas pasadas de un vehículo dado de baja (cubierto por FEAT-001e).
- Autenticación real de empleados (la identificación por legajo no es un mecanismo de autenticación, es un campo de formulario).
- Notificaciones por email, SMS o push.
- Aplicación móvil nativa.

## Risks and Mitigations

| ID | Riesgo | Impacto | Probabilidad | Mitigación sugerida |
|-----|--------|---------|--------------|---------------------|
| R-01 | Sin autenticación real, cualquiera que conozca el legajo de otro empleado puede cancelar su reserva. | Medio | Bajo | Aceptado como riesgo conocido para esta iteración (mismo criterio que FEAT-001c, R-01); validar legajo contra un padrón de empleados en una fase futura. |

## Dependencies

| ID | Dependencia | Descripción |
|-----|-------------|-------------|
| D-01 | FEAT-001c | Este ticket depende del modelo de datos y la creación de reservas de FEAT-001c: no hay nada que listar, filtrar o cancelar sin eso. |
| D-02 | FEAT-001a | Depende del modelo de vehículos para mostrar patente/tipo junto a cada reserva listada. |
| D-03 | Infraestructura | Definir el entorno donde se alojará el sistema (servidor, cloud, on-premise). |
| D-04 | Stack tecnológico | Frontend: React + Vite. Backend: Python + FastAPI. Base de datos: PostgreSQL. |

---

## Trazabilidad con PRD-FEAT-001b (previo a esta segunda división)

| Este PRD | PRD-FEAT-001b |
|---|---|
| FR-01 | FR-04 |
| FR-02 | FR-05 |
| FR-03 | FR-06 |
| FR-04 | FR-10 |
| AC-01..AC-06 | AC-07..AC-12 |
