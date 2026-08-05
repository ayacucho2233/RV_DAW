# PRD FEAT-001e: Integración con el ciclo de vida del vehículo

| Field | Value |
|-------|-------|
| Ticket | FEAT-001e |
| Tracker | none |
| Date | 2026-08-05 |
| PRD loops | 0 |

## Context and Problem

Con las reservas ya creables, listables, filtrables y cancelables (FEAT-001c, FEAT-001d), falta cerrar el vínculo que motivó dividir el PRD original en FEAT-001a/FEAT-001b: un vehículo con reservas activas no puede darse de baja, y las reservas pasadas de un vehículo ya dado de baja deben seguir siendo consultables. Sin este ticket, el administrador podría dar de baja un vehículo que un empleado ya reservó, dejando la reserva "colgada" sobre un vehículo inexistente para efectos prácticos.

**Personas:**
- **Administrador:** intenta dar de baja (temporal o definitiva) un vehículo del pool (flujo ya existente de FEAT-001a); este ticket agrega la validación de reservas activas sobre ese flujo.
- **Empleado (conductor):** consulta el listado de reservas (FEAT-001d) y espera seguir viendo sus reservas pasadas aunque el vehículo ya no esté activo.

## Goals

- Impedir que se dé de baja (temporal o definitiva) un vehículo que tiene reservas activas.
- Preservar la trazabilidad histórica: las reservas pasadas de un vehículo dado de baja permanecen visibles.

## Functional Requirements

- FR-01: El sistema no debe permitir pasar un vehículo a "baja temporal" ni a "baja definitiva" si tiene reservas activas.
- FR-02: El sistema debe mantener visibles en el listado de reservas las reservas pasadas de un vehículo en estado "baja temporal" o "baja definitiva".

## Non-Functional Requirements

- NFR-01: La validación de reservas activas al intentar dar de baja un vehículo debe responder en menos de 2 segundos, medido en el percentil 95 (p95), bajo carga normal esperada.

## Acceptance Criteria

*(Entre paréntesis, el AC/FR original de PRD-FEAT-001b del que proviene, para trazabilidad — ver también la tabla al final del documento.)*

- AC-01 (FR-01): IF el administrador intenta dar de baja temporalmente un vehículo con reservas activas, THEN THE sistema SHALL rechazar la operación e informar que el vehículo tiene reservas vigentes.
- AC-02 (FR-01): IF el administrador intenta dar de baja definitiva un vehículo con reservas activas, THEN THE sistema SHALL rechazar la operación e informar que el vehículo tiene reservas vigentes.
- AC-03 (FR-02): WHILE un vehículo está en estado "baja temporal", THE sistema SHALL mantener visibles sus reservas pasadas en el listado de reservas.
- AC-04 (FR-02): WHILE un vehículo está en estado "baja definitiva", THE sistema SHALL mantener visibles sus reservas pasadas en el listado de reservas.

## Out of Scope

- Creación, listado, filtrado y cancelación de reservas (cubierto por FEAT-001c y FEAT-001d).
- Alta, modificación y reactivación de vehículos (cubierto por FEAT-001a) — este ticket solo agrega una validación sobre los endpoints de baja ya existentes, no los reimplementa.
- Notificar al empleado si su reserva futura queda en riesgo porque el vehículo intentó darse de baja (el intento simplemente se rechaza; no hay reserva afectada en la práctica).
- Aplicación móvil nativa.

## Risks and Mitigations

| ID | Riesgo | Impacto | Probabilidad | Mitigación sugerida |
|-----|--------|---------|--------------|---------------------|
| R-01 | Condición de carrera entre un administrador dando de baja un vehículo y un empleado creando una reserva sobre el mismo vehículo al mismo tiempo. | Medio | Bajo | Igual que TM-03/AC-06 de tickets previos: usar una transacción con verificación de reservas activas antes de confirmar la baja, en la misma operación atómica (`SELECT FOR UPDATE` o equivalente, consistente con AGENTS.md). |

## Dependencies

| ID | Dependencia | Descripción |
|-----|-------------|-------------|
| D-01 | FEAT-001c | Este ticket depende del modelo de datos de reservas de FEAT-001c: FR-01/AC-01/AC-02 necesitan poder consultar si un vehículo tiene reservas activas. |
| D-02 | FEAT-001a | Depende de los endpoints de baja temporal/definitiva ya existentes: este ticket agrega una validación sobre ellos, no los crea. |
| D-03 | FEAT-001d | FR-02/AC-03/AC-04 dependen de que el listado de reservas (FEAT-001d) ya exista, para verificar que las reservas pasadas sigan apareciendo ahí. |
| D-04 | Infraestructura | Definir el entorno donde se alojará el sistema (servidor, cloud, on-premise). |
| D-05 | Stack tecnológico | Frontend: React + Vite. Backend: Python + FastAPI. Base de datos: PostgreSQL. |

---

## Trazabilidad con PRD-FEAT-001b (previo a esta segunda división)

| Este PRD | PRD-FEAT-001b |
|---|---|
| FR-01 | FR-08 |
| FR-02 | FR-09 |
| AC-01..AC-04 | AC-14..AC-17 |
