# PRD FEAT-001c: Consulta y creación de reservas

| Field | Value |
|-------|-------|
| Ticket | FEAT-001c |
| Tracker | none |
| Date | 2026-08-05 |
| PRD loops | 0 |

## Context and Problem

Con el pool de vehículos ya gestionable por el administrador (FEAT-001a), falta la parte central para los empleados: consultar qué vehículos existen, saber si están disponibles para un período determinado y reservarlos. Este es el sub-ticket base de "Reservas y disponibilidad de vehículos" (FEAT-001b original, dividido por exceder el umbral de tamaño recomendado): cubre la creación de una reserva y la consulta de disponibilidad, sin autenticación ni aprobación previa. El empleado que realiza la reserva es quien conducirá el vehículo.

**Personas:**
- **Empleado (conductor):** cualquier persona de la empresa que necesita un vehículo del pool para una fecha determinada. Consulta disponibilidad y crea reservas a su propio nombre.

**Definición — reserva activa:** una reserva se considera *activa* si su período (inicio–fin) es futuro o está en curso y no fue cancelada. Las reservas canceladas o cuyo período ya finalizó no se consideran activas a los efectos de validar solapamientos.

## Goals

- Permitir a los empleados reservar vehículos del pool corporativo de forma simple y directa.
- Evitar conflictos de reserva (dos empleados reservando el mismo vehículo en el mismo período), incluso ante solicitudes simultáneas.
- Permitir consultar la disponibilidad de un vehículo para un período dado antes de reservar.

## Functional Requirements

- FR-01: El sistema debe mostrar el listado de vehículos del pool con su patente y tipo (auto / camioneta).
- FR-02: El sistema debe permitir crear una reserva indicando: nombre del empleado (quien será el conductor), número de legajo, número de licencia de conducir, vehículo, fecha/hora de inicio, fecha/hora de fin y destino.
- FR-03: El sistema debe validar que no exista otra reserva activa para el mismo vehículo en el período solicitado.
- FR-04: El sistema debe indicar si un vehículo está disponible para un período dado.

## Non-Functional Requirements

- NFR-01: El sistema debe permitir a un empleado completar una reserva en menos de 1 minuto, sin necesidad de capacitación previa.
- NFR-02: El sistema debe responder consultas de disponibilidad en menos de 2 segundos, medido en el percentil 95 (p95), bajo carga normal esperada.
- NFR-03: El sistema debe prevenir condiciones de carrera (race conditions) al crear reservas simultáneas sobre el mismo vehículo: ante dos solicitudes concurrentes para el mismo vehículo y período, solo una debe confirmarse.

## Acceptance Criteria

*(Entre paréntesis, el AC/FR original de PRD-FEAT-001b del que proviene, para trazabilidad — ver también la tabla al final del documento.)*

- AC-01 (FR-01): WHEN el empleado visualiza el listado de vehículos, THE sistema SHALL mostrar cada vehículo con su patente y tipo (auto / camioneta).
- AC-02 (FR-02): WHEN el empleado envía una reserva con un vehículo disponible y todos los campos requeridos completos, THE sistema SHALL confirmar la reserva y registrarla.
- AC-03 (FR-02): IF el empleado intenta enviar la reserva sin completar algún campo obligatorio (nombre, legajo, licencia, vehículo, fecha/hora inicio, fecha/hora fin, destino), THEN THE sistema SHALL rechazar la creación y señalar el campo faltante.
- AC-04 (FR-02): IF la fecha/hora de fin es anterior o igual a la de inicio, THEN THE sistema SHALL rechazar la reserva con un mensaje de error descriptivo.
- AC-05 (FR-03): IF otro empleado intenta reservar un vehículo en un período que se superpone con una reserva activa existente para ese vehículo, THEN THE sistema SHALL rechazar la reserva e informar el conflicto.
- AC-06 (NFR-03): WHEN llegan dos solicitudes de reserva simultáneas para el mismo vehículo y el mismo período, THE sistema SHALL confirmar solo una de las reservas y rechazar la otra con un código de conflicto (409).
- AC-07 (FR-04): WHEN se consulta la disponibilidad de vehículos para un rango horario dado, THE sistema SHALL marcar como no disponible todo vehículo con una reserva activa que se superponga con ese rango, y como disponible el resto.

## Out of Scope

- Alta, modificación, baja temporal, baja definitiva y reactivación de vehículos, y sus validaciones de patente/tipo (cubierto por FEAT-001a).
- Autenticación y gestión de roles para empleados (solo aplica al administrador, cubierto por FEAT-001a).
- Listado completo de reservas existentes, filtros por estado y cancelación de reservas (cubierto por FEAT-001d).
- Bloqueo de la baja de un vehículo con reservas activas, y visibilidad de reservas pasadas de un vehículo dado de baja (cubierto por FEAT-001e).
- Aprobación previa de reservas, por supervisores, administradores o cualquier otro rol.
- Gestión de mantenimiento o estado técnico de los vehículos.
- Notificaciones por email, SMS o push.
- Historial de kilometraje o combustible.
- Validación de formato específico de legajo o licencia de conducir (solo se exige que sean campos obligatorios, no vacíos).
- Aplicación móvil nativa.
- Integración con sistemas de RRHH o ERP.

## Risks and Mitigations

| ID | Riesgo | Impacto | Probabilidad | Mitigación sugerida |
|-----|--------|---------|--------------|---------------------|
| R-01 | Sin autenticación, un empleado puede reservar en nombre de otro. | Medio | Alto | Se registra número de legajo y licencia de conducir para trazabilidad básica. En una siguiente iteración, validar el legajo contra un padrón de empleados. |
| R-02 | Dos reservas creadas simultáneamente para el mismo vehículo. | Alto | Bajo | Cubierto por NFR-03 y AC-06: transacciones o bloqueo optimista en la capa de datos. |

## Dependencies

| ID | Dependencia | Descripción |
|-----|-------------|-------------|
| D-01 | FEAT-001a | Este ticket depende del modelo de datos de vehículos (patente, tipo, estado) creado en FEAT-001a para poder listarlos y validar disponibilidad. |
| D-02 | Infraestructura | Definir el entorno donde se alojará el sistema (servidor, cloud, on-premise). |
| D-03 | Stack tecnológico | Frontend: React + Vite. Backend: Python + FastAPI. Base de datos: PostgreSQL. |

---

## Trazabilidad con PRD-FEAT-001b (previo a esta segunda división)

| Este PRD | PRD-FEAT-001b |
|---|---|
| FR-01..FR-03 | FR-01..FR-03 |
| FR-04 | FR-07 |
| NFR-01..NFR-03 | NFR-01..NFR-03 |
| AC-01..AC-06 | AC-01..AC-06 |
| AC-07 | AC-13 |
