# RCA FIX-007: Extraer la clasificación temporal de reservas a una función testeable

| Campo | Valor |
|-------|-------|
| Ticket | FIX-007 |
| Fecha | 2026-08-25 |
| PRD relacionado | `prd-FEAT-001d.md` (FR-02, AC-02/AC-03/AC-04) — sin gap |

## Causa raíz

La clasificación temporal de una reserva (`futuras`/`en_curso`/`pasadas`, FR-02 de FEAT-001d) se
implementó directamente como tres `if/elif` inline dentro de
`service.listar_reservas` (`backend/app/features/reservas/service.py:152-159`), acoplada al bucle
que filtra la lista completa de reservas. Al no existir como una función propia, no hay forma de
invocarla ni de testearla de forma aislada — cualquier verificación de esa lógica necesita pasar por
`listar_reservas` completo, con su acceso a base de datos.

Esto se volvió un problema concreto al querer construir `evals/run.py` (script de regresión que
llama a "la función de clasificación de la app" y compara resultados esperados): no hay ninguna
función que cumpla ese rol de forma aislada.

## Cadena de eventos

1. FEAT-001d (2026-08-06/07) definió FR-02 y sus ACs sobre el filtro de período.
2. La implementación resolvió el requisito con la forma más directa: condicionales dentro del
   propio bucle de filtrado en `listar_reservas`, sin considerar que la clasificación en sí
   pudiera necesitarse como unidad separada.
3. Ningún ticket posterior (FEAT-004, FEAT-005, FIX-001..005) tocó esa función, así que el
   acoplamiento nunca generó fricción — hasta ahora, al necesitar una función de clasificación
   invocable para el harness de evals.

## Componente afectado

`backend/app/features/reservas/service.py` (función `listar_reservas`) y
`backend/app/features/reservas/schemas.py` (donde vive el tipo `FiltroPeriodoReserva`, lugar
natural para la función que lo produce).

## Gap en el PRD

Ninguno. FR-02/AC-02/AC-03/AC-04 de `prd-FEAT-001d.md` describen el comportamiento observable
(qué reservas aparecen bajo cada filtro), no su forma de implementación interna. Extraer la lógica
a una función pura con el mismo comportamiento no cambia ningún AC.
