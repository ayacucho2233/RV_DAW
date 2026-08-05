# PRD FEAT-001b: Reservas y disponibilidad de vehículos

> ⚠️ **Superado.** Este PRD se dividió por segunda vez en DEFINE (2026-08-05) por exceder el umbral
> de tamaño recomendado (17 AC). Su contenido vive redistribuido en `prd-FEAT-001c.md`,
> `prd-FEAT-001d.md` y `prd-FEAT-001e.md` — ver el índice en `prd-FEAT-001.md`. Se conserva como
> documento histórico/de contexto, no es un ticket ejecutable.

| Field | Value |
|-------|-------|
| Ticket | FEAT-001b |
| Tracker | none |
| Date | 2026-08-02 |
| PRD loops | 0 |

## Context and Problem

Con el pool de vehículos ya gestionable por el administrador (FEAT-001a), falta la parte que usan los empleados día a día: consultar qué vehículos están disponibles, reservarlos para una fecha determinada y cancelar sus propias reservas. También falta la regla que conecta ambos sub-tickets: un vehículo con reservas activas no puede darse de baja, y las reservas pasadas de un vehículo dado de baja deben seguir siendo visibles.

Se propone un sistema simple que permita a cualquier empleado consultar los vehículos disponibles y realizar una reserva, sin necesidad de autenticación ni aprobación previa. El empleado que realiza la reserva es quien conducirá el vehículo.

**Personas:**
- **Empleado (conductor):** cualquier persona de la empresa que necesita un vehículo del pool para una fecha determinada. Consulta disponibilidad, crea reservas a su propio nombre y puede cancelar únicamente las reservas que él mismo creó.

**Definición — reserva activa:** una reserva se considera *activa* si su período (inicio–fin) es futuro o está en curso y no fue cancelada. Las reservas canceladas o cuyo período ya finalizó no se consideran activas a los efectos de validar solapamientos ni de bloquear la baja de un vehículo.

## Goals

- Permitir a los empleados reservar vehículos del pool corporativo de forma simple y directa.
- Evitar conflictos de reserva (dos empleados reservando el mismo vehículo en el mismo período), incluso ante solicitudes simultáneas.
- Registrar el uso de los vehículos por empleado, fecha y destino para trazabilidad básica.
- Enlazar el ciclo de vida de una reserva con el de baja/reactivación de un vehículo (FEAT-001a): una reserva activa bloquea la baja del vehículo que reserva.

## Functional Requirements

- FR-01: El sistema debe mostrar el listado de vehículos del pool con su patente y tipo (auto / camioneta).
- FR-02: El sistema debe permitir crear una reserva indicando: nombre del empleado (quien será el conductor), número de legajo, número de licencia de conducir, vehículo, fecha/hora de inicio, fecha/hora de fin y destino.
- FR-03: El sistema debe validar que no exista otra reserva activa para el mismo vehículo en el período solicitado.
- FR-04: El sistema debe listar las reservas existentes.
- FR-05: El sistema debe permitir filtrar reservas por estado (futuras, en curso, pasadas).
- FR-06: El sistema debe permitir cancelar una reserva existente indicando el número de legajo del solicitante.
- FR-07: El sistema debe indicar si un vehículo está disponible para un período dado.
- FR-08: El sistema no debe permitir pasar un vehículo a "baja temporal" ni a "baja definitiva" si tiene reservas activas.
- FR-09: El sistema debe mantener visibles en el listado de reservas las reservas pasadas de un vehículo en estado "baja temporal" o "baja definitiva".
- FR-10: El sistema no debe permitir cancelar una reserva a un empleado cuyo número de legajo no coincida con el del legajo que creó la reserva.

## Non-Functional Requirements

- NFR-01: El sistema debe permitir a un empleado completar una reserva en menos de 1 minuto, sin necesidad de capacitación previa.
- NFR-02: El sistema debe responder consultas de disponibilidad en menos de 2 segundos, medido en el percentil 95 (p95), bajo carga normal esperada.
- NFR-03: El sistema debe prevenir condiciones de carrera (race conditions) al crear reservas simultáneas sobre el mismo vehículo: ante dos solicitudes concurrentes para el mismo vehículo y período, solo una debe confirmarse.

## Acceptance Criteria

*(Entre paréntesis, el AC/FR original de PRD-FEAT-001 del que proviene, para trazabilidad — ver también la tabla al final del documento.)*

- AC-01 (FR-01): WHEN el empleado visualiza el listado de vehículos, THE sistema SHALL mostrar cada vehículo con su patente y tipo (auto / camioneta).
- AC-02 (FR-02): WHEN el empleado envía una reserva con un vehículo disponible y todos los campos requeridos completos, THE sistema SHALL confirmar la reserva y registrarla.
- AC-03 (FR-02): IF el empleado intenta enviar la reserva sin completar algún campo obligatorio (nombre, legajo, licencia, vehículo, fecha/hora inicio, fecha/hora fin, destino), THEN THE sistema SHALL rechazar la creación y señalar el campo faltante.
- AC-04 (FR-02): IF la fecha/hora de fin es anterior o igual a la de inicio, THEN THE sistema SHALL rechazar la reserva con un mensaje de error descriptivo.
- AC-05 (FR-03): IF otro empleado intenta reservar un vehículo en un período que se superpone con una reserva activa existente para ese vehículo, THEN THE sistema SHALL rechazar la reserva e informar el conflicto.
- AC-06 (NFR-03): WHEN llegan dos solicitudes de reserva simultáneas para el mismo vehículo y el mismo período, THE sistema SHALL confirmar solo una de las reservas y rechazar la otra con un código de conflicto (409).
- AC-07 (FR-04): WHEN el empleado consulta el listado de reservas sin aplicar ningún filtro, THE sistema SHALL mostrar todas las reservas existentes.
- AC-08 (FR-05): WHEN el empleado filtra las reservas por estado "futuras", THE sistema SHALL mostrar únicamente las reservas con fecha de inicio posterior al momento actual.
- AC-09 (FR-05): WHEN el empleado filtra las reservas por estado "en curso", THE sistema SHALL mostrar únicamente las reservas cuyo período (inicio–fin) abarca el momento actual.
- AC-10 (FR-05): WHEN el empleado filtra las reservas por estado "pasadas", THE sistema SHALL mostrar únicamente las reservas con fecha de fin anterior al momento actual.
- AC-11 (FR-06): WHEN el empleado que creó la reserva solicita la cancelación indicando su número de legajo, THE sistema SHALL cancelar la reserva y dejar el vehículo disponible para ese período.
- AC-12 (FR-10): IF un empleado intenta cancelar una reserva con un número de legajo distinto al que la creó, THEN THE sistema SHALL rechazar la cancelación e informar que solo el solicitante original puede cancelarla.
- AC-13 (FR-07): WHEN se consulta la disponibilidad de vehículos para un rango horario dado, THE sistema SHALL marcar como no disponible todo vehículo con una reserva activa que se superponga con ese rango, y como disponible el resto.
- AC-14 (FR-08): IF el administrador intenta dar de baja temporalmente un vehículo con reservas activas, THEN THE sistema SHALL rechazar la operación e informar que el vehículo tiene reservas vigentes.
- AC-15 (FR-08): IF el administrador intenta dar de baja definitiva un vehículo con reservas activas, THEN THE sistema SHALL rechazar la operación e informar que el vehículo tiene reservas vigentes.
- AC-16 (FR-09): WHILE un vehículo está en estado "baja temporal", THE sistema SHALL mantener visibles sus reservas pasadas en el listado de reservas.
- AC-17 (FR-09): WHILE un vehículo está en estado "baja definitiva", THE sistema SHALL mantener visibles sus reservas pasadas en el listado de reservas.

## Out of Scope

- Alta, modificación, baja temporal, baja definitiva y reactivación de vehículos, y sus validaciones de patente/tipo (cubierto por FEAT-001a).
- Autenticación y gestión de roles para empleados (solo aplica al administrador, cubierto por FEAT-001a).
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
| R-02 | Sin aprobación, no hay control sobre el uso adecuado de los vehículos. | Medio | Medio | Registrar siempre nombre y destino; habilitar aprobación en una fase futura. |
| R-03 | Dos reservas creadas simultáneamente para el mismo vehículo. | Alto | Bajo | Cubierto por NFR-03 y AC-06: transacciones o bloqueo optimista en la capa de datos. |

## Dependencies

| ID | Dependencia | Descripción |
|-----|-------------|-------------|
| D-01 | FEAT-001a | Este ticket depende del modelo de datos de vehículos y de los endpoints de administración (alta, baja temporal, baja definitiva) creados en FEAT-001a. FR-08/AC-14/AC-15 agregan la validación de reservas activas sobre esos endpoints; FR-09/AC-16/AC-17 dependen de que el estado del vehículo (baja temporal/definitiva) ya exista. |
| D-02 | Infraestructura | Definir el entorno donde se alojará el sistema (servidor, cloud, on-premise). |
| D-03 | Stack tecnológico | Frontend: React + Vite. Backend: Python + FastAPI. Base de datos: PostgreSQL. |

---

## Trazabilidad con PRD-FEAT-001 (original)

| Este PRD | PRD-FEAT-001 original |
|---|---|
| FR-01..FR-07 | FR-01..FR-07 |
| FR-08 | FR-12 |
| FR-09 | FR-13 |
| FR-10 | FR-21 |
| NFR-01..NFR-03 | NFR-01..NFR-03 |
| AC-01..AC-13 | AC-01..AC-13 |
| AC-14..AC-15 | AC-18..AC-19 |
| AC-16..AC-17 | AC-20..AC-21 |
