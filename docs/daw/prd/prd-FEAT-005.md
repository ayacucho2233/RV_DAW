# PRD FEAT-005: Estado "Caducada" para reservas vencidas automáticamente

| Field | Value |
|-------|-------|
| Ticket | FEAT-005 |
| Tracker | none |
| Date | 2026-08-18 |
| PRD loops | 1 |

## Context and Problem

Hoy `Reserva.estado` solo tiene dos valores: `activa` y `cancelada`. Cuando una reserva llega a su
`fecha_fin` sin que nadie la haya cancelado, el registro sigue en `estado = "activa"` para siempre —
solo se la reclasifica como "pasada" de forma calculada (no persistida) en el filtro `periodo` del
listado (`GET /reservas?periodo=pasadas`, `service.listar_reservas`).

Esto es inconsistente: una reserva vencida sigue contando como "activa" en cualquier lugar que
consulte el campo `estado` directamente, y no hay forma de distinguir, mirando el dato persistido,
una reserva que terminó porque se cumplió su plazo de una que sigue vigente.

## Goals

- Que una reserva `activa` cuya `fecha_fin` sea estrictamente anterior al instante de evaluación
  pase a un nuevo estado persistido `caducada`.
- Que `caducada` se comporte, en todo lo que hoy distingue `activa` de `cancelada` (solapamiento,
  disponibilidad, baja de vehículo, re-cancelación), exactamente igual que `cancelada` — sin que haga
  falta tocar esa lógica existente.
- Mantener `caducada` como un valor distinguible de `cancelada` en el dato persistido y en las
  respuestas de la API, para poder diferenciar "el empleado la canceló" de "venció sola".

## Functional Requirements

- FR-01: El sistema SHALL agregar el valor `caducada` a `EstadoReserva`, junto a los ya existentes
  `activa` y `cancelada`.
- FR-02: El sistema SHALL transicionar a `caducada` toda reserva en estado `activa` cuya `fecha_fin`
  sea estrictamente anterior al instante de evaluación. El mecanismo concreto de disparo (cuándo y
  cómo se evalúa esa transición) se define en la fase de PLAN.
- FR-03: El sistema SHALL rechazar la cancelación (`PATCH /reservas/{id}/cancelar`) de una reserva en
  estado `caducada`, con el mismo comportamiento (mensaje y código HTTP) que ya aplica hoy al intentar
  cancelar una reserva `cancelada`.
- FR-04: Toda consulta que hoy filtra reservas por `estado == activa` para determinar solapamiento,
  disponibilidad o bloqueo de baja de vehículo SHALL seguir funcionando sin modificarse — `caducada`
  queda excluida automáticamente por no ser `activa`, igual que `cancelada`.
- FR-05: Las respuestas de la API que exponen `estado` (`ReservaOut`, `ReservaListItem`) SHALL incluir
  `caducada` como valor válido, sin requerir cambios de schema más allá de que el enum lo admita.

## Non-Functional Requirements

- NFR-01: Ninguna respuesta de la API SHALL devolver como `estado: "activa"` una reserva cuya
  `fecha_fin` ya pasó, una vez que el mecanismo de transición (definido en PLAN) haya corrido sobre
  esa reserva.
- NFR-02: La migración de base de datos que agrega el valor `caducada` SHALL preservar los datos
  existentes: ninguna reserva `activa` o `cancelada` cambia de valor por el solo hecho de aplicar la
  migración.

## Acceptance Criteria

- AC-01: WHEN una reserva está en estado `activa` y su `fecha_fin` es estrictamente anterior al
  instante en que el sistema evalúa la transición, THE sistema SHALL cambiar su `estado` a `caducada`
  (FR-01, FR-02) y persistir el cambio.
- AC-02: WHEN una reserva está en estado `activa` y su `fecha_fin` es igual o posterior al instante de
  evaluación, THE sistema SHALL mantenerla en `activa` (no caduca hasta que el instante de evaluación
  sea estrictamente posterior a `fecha_fin`, FR-02).
- AC-03: WHEN se evalúa el solapamiento para una nueva reserva o la disponibilidad de un vehículo, THE
  sistema SHALL tratar una reserva `caducada` igual que una `cancelada` (no la considera activa, no
  bloquea el nuevo período) sin requerir cambios en las consultas existentes (FR-04).
- AC-04: WHEN se intenta dar de baja temporal o definitiva un vehículo, THE sistema SHALL NOT
  considerar las reservas `caducada` de ese vehículo como reservas activas que bloqueen la baja
  (mismo criterio que ya aplica a `cancelada`, FR-04).
- AC-05: IF se solicita cancelar una reserva que está en estado `caducada`, THEN THE sistema SHALL
  rechazar la operación con el mismo error (código y mensaje) que usa hoy para una reserva ya
  `cancelada` (FR-03).
- AC-06: IF la migración que agrega `caducada` se aplica sobre una base de datos con reservas
  `activa` cuya `fecha_fin` ya pasó, THEN THE sistema SHALL dejarlas en `activa` en el momento de
  aplicar la migración — la transición a `caducada` ocurre a través del mecanismo de FR-02, no como
  parte de la migración de esquema (FR-01).
- AC-07: WHEN una reserva en estado `caducada` se incluye en la respuesta de un endpoint que expone
  `estado` (`ReservaOut`, `ReservaListItem`), THE sistema SHALL devolver `"caducada"` como valor
  válido de ese campo, sin requerir manejo especial en el cliente (FR-05).

## Out of Scope

- El mecanismo exacto de disparo de la transición (job periódico, evaluación al leer, u otro) — se
  decide en PLAN; el usuario indicará su preferencia en esa fase.
- Notificar al empleado cuando su reserva caduca.
- Permitir "reactivar" una reserva `caducada` o `cancelada`.
- Un historial de auditoría más allá del propio valor de `estado` (no se agrega una tabla de eventos
  ni un campo que registre "quién/qué disparó" la transición).
- Cambios visuales o de UX en el frontend más allá de que el badge/etiqueta de estado muestre
  `caducada` quede acorde a los que ya existen (se define en PLAN si hace falta texto/color propios o
  alcanza con el que ya se usa para `cancelada`).

## Risks and Mitigations

- **Riesgo:** el mecanismo de disparo (a definir en PLAN) podría dejar una ventana de tiempo en la
  que una reserva vencida sigue apareciendo como `activa`. **Mitigación:** NFR-01 fija el criterio de
  corrección (nunca devolver `activa` sobre una reserva ya evaluada como vencida); el tamaño de esa
  ventana se acota en PLAN según el mecanismo elegido.
- **Riesgo:** una migración de esquema mal escrita podría re-clasificar reservas existentes como
  `caducada` en vez de dejar esa transición al mecanismo de FR-02. **Mitigación:** AC-06 lo prohíbe
  explícitamente — la migración solo amplía los valores válidos del campo, no reescribe datos.

## Dependencies

- FEAT-001c (creación/consulta de reservas) — define `EstadoReserva`, `models.py`, el flujo de
  solapamiento en `repository.py`/`service.py`.
- FEAT-001e (ciclo de vida del vehículo) — usa `existe_activa_para_vehiculo` para bloquear bajas; debe
  seguir funcionando sin cambios (FR-04/AC-04).
