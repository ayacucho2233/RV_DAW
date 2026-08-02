# PRD FEAT-001a: Gestión del pool de vehículos

| Field | Value |
|-------|-------|
| Ticket | FEAT-001a |
| Tracker | none |
| Date | 2026-08-02 |
| PRD loops | 0 |

## Context and Problem

La empresa cuenta con un pool de vehículos corporativos (autos y camionetas). Antes de que un empleado pueda reservar nada, el administrador necesita poder mantener ese pool: darlo de alta, corregirlo y sacar de circulación los vehículos que ya no están disponibles, sin perder el historial.

Este sub-ticket es el primero de la división de FEAT-001 y es la base sobre la que se apoya FEAT-001b (reservas): establece el modelo de datos del vehículo, sus estados y las operaciones de administración protegidas por autenticación.

**Personas:**
- **Administrador:** responsable de mantener la base de vehículos del pool (altas, modificaciones y bajas). Requiere autenticación para operar.

**Definición — estados de un vehículo:** un vehículo puede estar en uno de tres estados: **activo** (disponible para nuevas reservas), **baja temporal** (no disponible para nuevas reservas, pero puede volver a "activo" mediante reactivación) o **baja definitiva** (no disponible para nuevas reservas y no puede reactivarse). Un vehículo puede pasar de "activo" a "baja temporal" o directamente a "baja definitiva". Ninguno de los dos estados de baja elimina físicamente el registro del vehículo.

> **Nota de alcance:** la regla que bloquea una baja cuando el vehículo tiene reservas activas, y la que mantiene visibles las reservas pasadas de un vehículo dado de baja, se documentan y validan en **FEAT-001b** — dependen del modelo de reservas, que no existe todavía en este sub-ticket (ver "Out of Scope" y "Dependencies").

## Goals

- Permitir al administrador mantener el pool de vehículos (alta, modificación, baja temporal, baja definitiva, reactivación) sin eliminar físicamente ningún registro.
- Garantizar que solo el administrador autenticado pueda operar sobre el pool.
- Garantizar la unicidad de patente y la validez del tipo de vehículo en toda operación de alta o modificación.

## Functional Requirements

- FR-01: El sistema debe permitir al administrador agregar vehículos al pool indicando patente y tipo (auto / camioneta).
- FR-02: El sistema debe permitir al administrador modificar la patente y el tipo de un vehículo existente.
- FR-03: El sistema debe permitir al administrador dar de baja temporalmente un vehículo del pool: el vehículo pasa al estado "baja temporal" y deja de estar disponible para nuevas reservas, sin eliminarse físicamente.
- FR-04: El sistema debe permitir al administrador dar de baja definitiva un vehículo del pool, desde el estado "activo" o "baja temporal": el vehículo pasa al estado "baja definitiva" y deja de estar disponible para nuevas reservas, sin eliminarse físicamente.
- FR-05: El sistema debe requerir autenticación mediante HTTP Basic para toda operación de administración de vehículos (alta, modificación, baja temporal, baja definitiva, reactivación).
- FR-06: El sistema debe permitir al administrador reactivar un vehículo en estado "baja temporal", volviendo a hacerlo disponible para nuevas reservas en estado "activo".
- FR-07: El sistema no debe permitir reactivar un vehículo en estado "baja definitiva".
- FR-08: El sistema debe validar que la patente de un vehículo sea única dentro del pool al darlo de alta.
- FR-09: El sistema debe validar que la patente de un vehículo sea única dentro del pool al modificarlo.
- FR-10: El sistema debe validar que el tipo de un vehículo sea "auto" o "camioneta" al darlo de alta.
- FR-11: El sistema debe validar que el tipo de un vehículo sea "auto" o "camioneta" al modificarlo.

## Non-Functional Requirements

No se identifican requerimientos no funcionales propios de este sub-ticket con una métrica distinta a las ya definidas para el conjunto del sistema; los NFR de rendimiento y concurrencia (consulta de disponibilidad, condiciones de carrera) pertenecen al dominio de reservas y se documentan en FEAT-001b.

## Acceptance Criteria

*(Entre paréntesis, el AC/FR original de PRD-FEAT-001 del que proviene, para trazabilidad — ver también la tabla al final del documento.)*

- AC-01 (FR-01): WHEN el administrador agrega un vehículo al pool con patente y tipo válidos, THE sistema SHALL dejar el vehículo disponible para ser reservado.
- AC-02 (FR-02): WHEN el administrador modifica la patente o el tipo de un vehículo existente, THE sistema SHALL reflejar los cambios de inmediato en el listado de vehículos.
- AC-03 (FR-03): WHEN el administrador da de baja temporalmente un vehículo activo sin reservas activas, THE sistema SHALL pasarlo al estado "baja temporal" y dejar de mostrarlo en el pool disponible para nuevas reservas.
- AC-04 (FR-04): WHEN el administrador da de baja definitiva un vehículo activo o en "baja temporal" sin reservas activas, THE sistema SHALL pasarlo al estado "baja definitiva" y dejar de mostrarlo en el pool disponible para nuevas reservas.
- AC-05 (FR-05): IF un endpoint de administración de vehículos (alta, modificación, baja temporal, baja definitiva o reactivación) recibe una petición sin credenciales HTTP Basic válidas, THEN THE sistema SHALL responder 401 y no ejecutar la acción.
- AC-06 (FR-06): WHEN el administrador reactiva un vehículo en estado "baja temporal", THE sistema SHALL pasarlo a estado "activo" y dejarlo disponible en el pool para nuevas reservas.
- AC-07 (FR-07): IF el administrador intenta reactivar un vehículo en estado "baja definitiva", THEN THE sistema SHALL rechazar la operación e informar que un vehículo en baja definitiva no puede reactivarse.
- AC-08 (FR-08): IF el administrador intenta dar de alta un vehículo con una patente ya existente en el pool, THEN THE sistema SHALL rechazar la operación e informar que la patente ya existe.
- AC-09 (FR-09): IF el administrador intenta modificar un vehículo asignándole una patente que ya existe en otro vehículo del pool, THEN THE sistema SHALL rechazar la operación e informar que la patente ya existe.
- AC-10 (FR-10): IF el administrador intenta dar de alta un vehículo con un tipo distinto de "auto" o "camioneta", THEN THE sistema SHALL rechazar la operación e informar que el tipo no es válido.
- AC-11 (FR-11): IF el administrador intenta modificar un vehículo asignándole un tipo distinto de "auto" o "camioneta", THEN THE sistema SHALL rechazar la operación e informar que el tipo no es válido.

## Out of Scope

- Creación, listado, filtrado, cancelación y consulta de disponibilidad de reservas (cubierto por FEAT-001b).
- Bloqueo de una baja por existir reservas activas sobre el vehículo, y visibilidad de reservas pasadas de un vehículo dado de baja: ambas dependen del modelo de reservas y se implementan en FEAT-001b sobre los endpoints de este ticket.
- Autenticación y gestión de roles para empleados (solo aplica al administrador).
- Aprobación previa de altas o bajas por otros roles.
- Gestión de mantenimiento o estado técnico de los vehículos.
- Notificaciones por email, SMS o push.
- Aplicación móvil nativa.
- Integración con sistemas de RRHH o ERP.

## Risks and Mitigations

| ID | Riesgo | Impacto | Probabilidad | Mitigación sugerida |
|-----|--------|---------|--------------|---------------------|
| R-01 | El pool de vehículos no está cargado inicialmente, dejando el sistema vacío. | Alto | Medio | Definir proceso de carga inicial de vehículos antes del go-live. |
| R-02 | Mientras FEAT-001b no esté implementado, dar de baja un vehículo no verifica reservas activas (porque el modelo de reservas todavía no existe). | Medio | Medio | No exponer las operaciones de baja a producción hasta que FEAT-001b esté desplegado, o aceptar el riesgo explícitamente para un go-live parcial solo de alta/listado. |

## Dependencies

| ID | Dependencia | Descripción |
|-----|-------------|-------------|
| D-01 | Infraestructura | Definir el entorno donde se alojará el sistema (servidor, cloud, on-premise). |
| D-02 | Stack tecnológico | Frontend: React + Vite. Backend: Python + FastAPI. Base de datos: PostgreSQL. |
| D-03 | Credenciales de administrador | Definir y provisionar de forma segura el usuario/contraseña de HTTP Basic para el rol administrador (FR-05), sin hardcodear en el código fuente. |
| D-04 | FEAT-001b | La validación de reservas activas al dar de baja un vehículo, y la visibilidad de reservas pasadas de vehículos dados de baja, se agregan en FEAT-001b sobre los endpoints que crea este ticket. |

---

## Trazabilidad con PRD-FEAT-001 (original)

| Este PRD | PRD-FEAT-001 original |
|---|---|
| FR-01..FR-04 | FR-08..FR-11 |
| FR-05..FR-07 | FR-14..FR-16 |
| FR-08..FR-11 | FR-17..FR-20 |
| AC-01..AC-11 | AC-14..AC-17, AC-22..AC-28 |
