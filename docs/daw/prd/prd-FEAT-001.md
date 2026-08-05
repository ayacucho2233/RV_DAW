# Parent PRD: Reserva de Vehículos Corporativos

| Metric | Value |
|--------|-------|
| Ticket | FEAT-001 |
| Date | 2026-08-02 |
| Status | Split |

## Sub-tickets

| Sub-ticket | Title | PRD | Dependencies | Status |
|---|---|---|---|---|
| FEAT-001a | Gestión del pool de vehículos | prd-FEAT-001a.md | none | done (PR #1, se mergea cuando se apruebe) |
| FEAT-001b | Reservas y disponibilidad de vehículos | prd-FEAT-001b.md | depends on FEAT-001a | active |

## Suggested implementation order

a → b

## Original context

La empresa cuenta con un pool de vehículos corporativos (autos y camionetas) disponibles para uso de los empleados. No existe un sistema centralizado para gestionar su disponibilidad. Se propuso un sistema simple que permite a cualquier empleado consultar los vehículos disponibles y reservarlos (sin autenticación ni aprobación previa), y a un administrador autenticado mantener el pool de vehículos (altas, modificaciones, bajas y reactivaciones).

El PRD original (28 criterios de aceptación, 21 requerimientos funcionales, 3 no funcionales) se dividió en DEFINE por exceder el umbral de tamaño recomendado para un ticket (5–7 ACs) y por cubrir dos áreas independientemente shippeables: la gestión del pool de vehículos por el administrador (FEAT-001a) y las reservas/disponibilidad por parte de los empleados (FEAT-001b), esta última dependiente de la primera.
