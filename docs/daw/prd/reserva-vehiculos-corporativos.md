# PRD-001: Reserva de Vehículos Corporativos — Sistema para que empleados reserven vehículos del pool corporativo sin aprobación previa

---

## Contexto y Problema

La empresa cuenta con un pool de vehículos corporativos (autos y camionetas) disponibles para uso de los empleados. Actualmente no existe un sistema centralizado para gestionar su disponibilidad, lo que genera conflictos y falta de visibilidad sobre el uso de la flota.

Se propone un sistema simple que permita a cualquier empleado consultar los vehículos disponibles y realizar una reserva, sin necesidad de autenticación ni aprobación previa. El empleado que realiza la reserva es quien conducirá el vehículo.

**Personas:**
- **Empleado (conductor):** cualquier persona de la empresa que necesita un vehículo del pool para una fecha determinada. Consulta disponibilidad, crea reservas a su propio nombre y puede cancelar únicamente las reservas que él mismo creó.
- **Administrador:** responsable de mantener la base de vehículos del pool (altas, modificaciones y bajas). Requiere autenticación para operar.

**Definición — reserva activa:** una reserva se considera *activa* si su período (inicio–fin) es futuro o está en curso y no fue cancelada. Las reservas canceladas o cuyo período ya finalizó no se consideran activas a los efectos de validar solapamientos ni de bloquear la baja de un vehículo.

**Definición — estados de un vehículo:** un vehículo puede estar en uno de tres estados: **activo** (disponible para nuevas reservas), **baja temporal** (no disponible para nuevas reservas, pero puede volver a "activo" mediante reactivación) o **baja definitiva** (no disponible para nuevas reservas y no puede reactivarse). Un vehículo puede pasar de "activo" a "baja temporal" o directamente a "baja definitiva"; ambas transiciones están bloqueadas si el vehículo tiene reservas activas. Ninguno de los dos estados de baja elimina físicamente el registro del vehículo: sus reservas pasadas permanecen visibles en el listado de reservas.

---

## Objetivos

- Permitir a los empleados reservar vehículos del pool corporativo de forma simple y directa.
- Evitar conflictos de reserva (dos empleados reservando el mismo vehículo en el mismo período), incluso ante solicitudes simultáneas.
- Registrar el uso de los vehículos por empleado, fecha y destino para trazabilidad básica.

---

## Requerimientos Funcionales

| ID | Descripción |
|------|-------------|
| RF-01 | El sistema debe mostrar el listado de vehículos del pool con su patente y tipo (auto / camioneta). |
| RF-02 | El sistema debe permitir crear una reserva indicando: nombre del empleado (quien será el conductor), número de legajo, número de licencia de conducir, vehículo, fecha/hora de inicio, fecha/hora de fin y destino. |
| RF-03 | El sistema debe validar que no exista otra reserva activa para el mismo vehículo en el período solicitado. |
| RF-04 | El sistema debe listar las reservas existentes. |
| RF-05 | El sistema debe permitir filtrar reservas por estado (futuras, en curso, pasadas). |
| RF-06 | El sistema debe permitir cancelar una reserva existente indicando el número de legajo del solicitante. |
| RF-07 | El sistema debe indicar si un vehículo está disponible para un período dado. |
| RF-08 | El sistema debe permitir al administrador agregar vehículos al pool indicando patente y tipo (auto / camioneta). |
| RF-09 | El sistema debe permitir al administrador modificar la patente y el tipo de un vehículo existente. |
| RF-10 | El sistema debe permitir al administrador dar de baja temporalmente un vehículo del pool: el vehículo pasa al estado "baja temporal" y deja de estar disponible para nuevas reservas, sin eliminarse físicamente. |
| RF-11 | El sistema debe permitir al administrador dar de baja definitiva un vehículo del pool, desde el estado "activo" o "baja temporal": el vehículo pasa al estado "baja definitiva" y deja de estar disponible para nuevas reservas, sin eliminarse físicamente. |
| RF-12 | El sistema no debe permitir pasar un vehículo a "baja temporal" ni a "baja definitiva" si tiene reservas activas. |
| RF-13 | El sistema debe mantener visibles en el listado de reservas las reservas pasadas de un vehículo en estado "baja temporal" o "baja definitiva". |
| RF-14 | El sistema debe requerir autenticación mediante HTTP Basic para toda operación de administración de vehículos (alta, modificación, baja temporal, baja definitiva, reactivación). |
| RF-15 | El sistema debe permitir al administrador reactivar un vehículo en estado "baja temporal", volviendo a hacerlo disponible para nuevas reservas en estado "activo". |
| RF-16 | El sistema no debe permitir reactivar un vehículo en estado "baja definitiva". |
| RF-17 | El sistema debe validar que la patente de un vehículo sea única dentro del pool al darlo de alta. |
| RF-18 | El sistema debe validar que la patente de un vehículo sea única dentro del pool al modificarlo. |
| RF-19 | El sistema debe validar que el tipo de un vehículo sea "auto" o "camioneta" al darlo de alta. |
| RF-20 | El sistema debe validar que el tipo de un vehículo sea "auto" o "camioneta" al modificarlo. |
| RF-21 | El sistema no debe permitir cancelar una reserva a un empleado cuyo número de legajo no coincida con el del legajo que creó la reserva. |

---

## Requerimientos No Funcionales

| ID | Descripción |
|-------|-------------|
| RNF-01 | El sistema debe permitir a un empleado completar una reserva en menos de 1 minuto, sin necesidad de capacitación previa. |
| RNF-02 | El sistema debe responder consultas de disponibilidad en menos de 2 segundos, medido en el percentil 95 (p95), bajo carga normal esperada. |
| RNF-03 | El sistema debe prevenir condiciones de carrera (race conditions) al crear reservas simultáneas sobre el mismo vehículo: ante dos solicitudes concurrentes para el mismo vehículo y período, solo una debe confirmarse. |

---

## Criterios de Aceptación

| ID | RF que cubre | Criterio |
|------|-------------|-----------|
| AC-01 | RF-01 | Dado que el empleado ingresa al sistema, cuando visualiza el listado de vehículos, entonces se muestra cada vehículo con su patente y tipo (auto / camioneta). |
| AC-02 | RF-02 | Dado un vehículo disponible y todos los campos requeridos completos, cuando el empleado envía la reserva, entonces la reserva se confirma y queda registrada. |
| AC-03 | RF-02 | Dado que el empleado no completa algún campo obligatorio (nombre, legajo, licencia, vehículo, fecha/hora inicio, fecha/hora fin, destino), cuando intenta enviar la reserva, entonces el sistema no la crea y señala el campo faltante. |
| AC-04 | RF-02 | Dado que la fecha/hora de fin es anterior o igual a la de inicio, cuando el empleado envía la reserva, entonces el sistema la rechaza con un mensaje de error descriptivo. |
| AC-05 | RF-03 | Dado un vehículo con una reserva activa en un período determinado, cuando otro empleado intenta reservar el mismo vehículo en un período que se superpone, entonces el sistema rechaza la reserva e informa el conflicto. |
| AC-06 | RNF-03 | Dado un vehículo disponible, cuando llegan dos solicitudes de reserva simultáneas para el mismo vehículo y el mismo período, entonces el sistema confirma solo una de las reservas y rechaza la otra con un código de conflicto (409). |
| AC-07 | RF-04 | Dado que el empleado accede al listado de reservas sin aplicar ningún filtro, cuando consulta el listado, entonces el sistema muestra todas las reservas existentes. |
| AC-08 | RF-05 | Dado que el empleado filtra las reservas por estado "futuras", cuando aplica el filtro, entonces el sistema muestra únicamente las reservas con fecha de inicio posterior al momento actual. |
| AC-09 | RF-05 | Dado que el empleado filtra las reservas por estado "en curso", cuando aplica el filtro, entonces el sistema muestra únicamente las reservas cuyo período (inicio–fin) abarca el momento actual. |
| AC-10 | RF-05 | Dado que el empleado filtra las reservas por estado "pasadas", cuando aplica el filtro, entonces el sistema muestra únicamente las reservas con fecha de fin anterior al momento actual. |
| AC-11 | RF-06 | Dado que el empleado que creó la reserva ingresa su número de legajo, cuando solicita la cancelación, entonces la reserva se cancela y el vehículo queda disponible para ese período. |
| AC-12 | RF-21 | Dado una reserva creada por un legajo determinado, cuando otro empleado intenta cancelarla con un número de legajo distinto, entonces el sistema rechaza la cancelación e informa que solo el solicitante original puede cancelarla. |
| AC-13 | RF-07 | Dado un vehículo con una reserva activa que se superpone con el período consultado y otro vehículo sin reservas en ese período, cuando se consulta disponibilidad para ese rango horario, entonces el primero se marca como no disponible y el segundo como disponible. |
| AC-14 | RF-08 | Dado que el administrador ingresa patente y tipo válidos para un vehículo nuevo, cuando lo agrega al pool, entonces el vehículo queda disponible para ser reservado. |
| AC-15 | RF-09 | Dado un vehículo existente, cuando el administrador modifica su patente o tipo, entonces los cambios quedan reflejados de inmediato en el listado de vehículos. |
| AC-16 | RF-10 | Dado un vehículo activo sin reservas activas, cuando el administrador lo da de baja temporalmente, entonces el vehículo pasa a estado "baja temporal" y deja de aparecer en el pool disponible para nuevas reservas. |
| AC-17 | RF-11 | Dado un vehículo activo o en "baja temporal" sin reservas activas, cuando el administrador lo da de baja definitiva, entonces el vehículo pasa a estado "baja definitiva" y deja de aparecer en el pool disponible para nuevas reservas. |
| AC-18 | RF-12 | Dado un vehículo con reservas activas, cuando el administrador intenta darlo de baja temporalmente, entonces el sistema rechaza la operación e informa que el vehículo tiene reservas vigentes. |
| AC-19 | RF-12 | Dado un vehículo con reservas activas, cuando el administrador intenta darlo de baja definitiva, entonces el sistema rechaza la operación e informa que el vehículo tiene reservas vigentes. |
| AC-20 | RF-13 | Dado un vehículo en estado "baja temporal" que tiene reservas pasadas asociadas, cuando se consulta el listado de reservas, entonces esas reservas pasadas siguen siendo visibles. |
| AC-21 | RF-13 | Dado un vehículo en estado "baja definitiva" que tiene reservas pasadas asociadas, cuando se consulta el listado de reservas, entonces esas reservas pasadas siguen siendo visibles. |
| AC-22 | RF-14 | Dado un request a un endpoint de administración de vehículos (alta, modificación, baja temporal, baja definitiva o reactivación) sin credenciales HTTP Basic válidas, cuando se realiza la petición, entonces el sistema responde 401 y no ejecuta la acción. |
| AC-23 | RF-15 | Dado un vehículo en estado "baja temporal", cuando el administrador lo reactiva, entonces el vehículo pasa a estado "activo" y vuelve a estar disponible en el pool para nuevas reservas. |
| AC-24 | RF-16 | Dado un vehículo en estado "baja definitiva", cuando el administrador intenta reactivarlo, entonces el sistema rechaza la operación e informa que un vehículo en baja definitiva no puede reactivarse. |
| AC-25 | RF-17 | Dado un vehículo existente con una patente determinada, cuando el administrador intenta dar de alta un nuevo vehículo con esa misma patente, entonces el sistema rechaza la operación e informa que la patente ya existe. |
| AC-26 | RF-18 | Dado un vehículo existente con una patente determinada, cuando el administrador intenta modificar otro vehículo asignándole esa misma patente, entonces el sistema rechaza la operación e informa que la patente ya existe. |
| AC-27 | RF-19 | Dado un tipo de vehículo distinto de "auto" o "camioneta", cuando el administrador intenta dar de alta un vehículo con ese tipo, entonces el sistema rechaza la operación e informa que el tipo no es válido. |
| AC-28 | RF-20 | Dado un tipo de vehículo distinto de "auto" o "camioneta", cuando el administrador intenta modificar un vehículo asignándole ese tipo, entonces el sistema rechaza la operación e informa que el tipo no es válido. |

---

## Fuera de Alcance

- Autenticación y gestión de roles para empleados (solo aplica al administrador).
- Aprobación previa de reservas, por supervisores, administradores o cualquier otro rol.
- Gestión de mantenimiento o estado técnico de los vehículos.
- Notificaciones por email, SMS o push.
- Historial de kilometraje o combustible.
- Validación de formato específico de legajo o licencia de conducir (solo se exige que sean campos obligatorios, no vacíos).
- Aplicación móvil nativa.
- Integración con sistemas de RRHH o ERP.

---

## Riesgos

| ID | Riesgo | Impacto | Probabilidad | Mitigación sugerida |
|-----|--------|---------|--------------|---------------------|
| R-01 | Sin autenticación, un empleado puede reservar en nombre de otro. | Medio | Alto | Se registra número de legajo y licencia de conducir para trazabilidad básica. En una siguiente iteración, validar el legajo contra un padrón de empleados. |
| R-02 | Sin aprobación, no hay control sobre el uso adecuado de los vehículos. | Medio | Medio | Registrar siempre nombre y destino; habilitar aprobación en una fase futura. |
| R-03 | Dos reservas creadas simultáneamente para el mismo vehículo. | Alto | Bajo | Cubierto por RNF-03 y AC-06: transacciones o bloqueo optimista en la capa de datos. |
| R-04 | El pool de vehículos no está cargado inicialmente, dejando el sistema vacío. | Alto | Medio | Definir proceso de carga inicial de vehículos antes del go-live. |

---

## Dependencias

| ID | Dependencia | Descripción |
|-----|-------------|-------------|
| D-01 | Carga inicial de vehículos | El administrador del sistema debe cargar el listado de vehículos antes del go-live. |
| D-02 | Infraestructura | Definir el entorno donde se alojará el sistema (servidor, cloud, on-premise). |
| D-03 | Stack tecnológico | Frontend: React + Vite. Backend: Python + FastAPI. Base de datos: PostgreSQL. |
| D-04 | Credenciales de administrador | Definir y provisionar de forma segura el usuario/contraseña de HTTP Basic para el rol administrador (RF-14), sin hardcodear en el código fuente. |
