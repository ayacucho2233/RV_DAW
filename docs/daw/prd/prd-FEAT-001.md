# Parent PRD: Reserva de Vehículos Corporativos

| Metric | Value |
|--------|-------|
| Ticket | FEAT-001 |
| Date | 2026-08-02 |
| Status | Split |

## Sub-tickets

| Sub-ticket | Title | PRD | Dependencies | Status |
|---|---|---|---|---|
| FEAT-001a | Gestión del pool de vehículos | prd-FEAT-001a.md | none | done (PR #1, mergeado a main) |
| FEAT-001b | Reservas y disponibilidad de vehículos | prd-FEAT-001b.md | depends on FEAT-001a | split into c/d/e (ver nota abajo) |
| FEAT-001c | Consulta y creación de reservas | prd-FEAT-001c.md | depends on FEAT-001a | done (PR #2, mergeado a main) |
| FEAT-001d | Listado, filtros y cancelación de reservas | prd-FEAT-001d.md | depends on FEAT-001c, FEAT-001a | done (PR #3, mergeado a main) |
| FEAT-001e | Integración con ciclo de vida del vehículo | prd-FEAT-001e.md | depends on FEAT-001c, FEAT-001a, FEAT-001d | done (PR #4, mergeado a main) |

## Suggested implementation order

a → c → d → e

## Note on FEAT-001b

FEAT-001b ("Reservas y disponibilidad de vehículos") se definió y validó como un único sub-ticket,
pero en su propia fase DEFINE se detectó que también excedía el umbral recomendado (17 AC contra
5-7). Se dividió por segunda vez en `FEAT-001c`/`FEAT-001d`/`FEAT-001e`, continuando el alfabeto de
este mismo índice en vez de anidar un sub-índice propio (`FEAT-001ba`, etc.) — decisión del usuario
en DEFINE de FEAT-001b, 2026-08-05. `prd-FEAT-001b.md` se conserva como documento histórico/de
contexto (no se borra, para no perder la trazabilidad hacia PRD-FEAT-001 original), pero no es un
ticket ejecutable: su contenido vive redistribuido en FEAT-001c/d/e.

## Original context

La empresa cuenta con un pool de vehículos corporativos (autos y camionetas) disponibles para uso de los empleados. No existe un sistema centralizado para gestionar su disponibilidad. Se propuso un sistema simple que permite a cualquier empleado consultar los vehículos disponibles y reservarlos (sin autenticación ni aprobación previa), y a un administrador autenticado mantener el pool de vehículos (altas, modificaciones, bajas y reactivaciones).

El PRD original (28 criterios de aceptación, 21 requerimientos funcionales, 3 no funcionales) se dividió en DEFINE por exceder el umbral de tamaño recomendado para un ticket (5–7 ACs) y por cubrir dos áreas independientemente shippeables: la gestión del pool de vehículos por el administrador (FEAT-001a) y las reservas/disponibilidad por parte de los empleados (FEAT-001b), esta última dependiente de la primera.
