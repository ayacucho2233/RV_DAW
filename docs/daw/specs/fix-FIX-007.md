# Fix-plan FIX-007: Extraer clasificación temporal de reservas y agregar evals/run.py

| Field | Value |
|-------|-------|
| Ticket | FIX-007 |
| Tier | FIX |
| RCA | docs/daw/specs/rca-FIX-007.md |
| Date | 2026-08-25 |
| Spec loops | 0 |

## Problem

No existe ninguna forma de invocar ni testear de forma aislada la clasificación temporal de una
reserva (`futuras`/`en_curso`/`pasadas`, FR-02 de `prd-FEAT-001d.md`) — vive como tres `if/elif`
inline dentro de `listar_reservas`. Esto impide construir `evals/run.py`, un script de regresión que
necesita llamar a "la función de clasificación de la app" y comparar el resultado con lo esperado.

## Root cause

Ver `docs/daw/specs/rca-FIX-007.md`: la implementación de FEAT-001d resolvió el requisito
acoplando la clasificación al bucle de filtrado, sin extraerla como unidad independiente.

## Solution — steps

1. `backend/app/features/reservas/schemas.py:26` (justo después de la definición de
   `FiltroPeriodoReserva`) — agregar la función pura:
   ```python
   def clasificar_periodo_reserva(
       fecha_inicio: datetime, fecha_fin: datetime, ahora: datetime
   ) -> FiltroPeriodoReserva:
       if fecha_inicio > ahora:
           return "futuras"
       if fecha_inicio <= ahora <= fecha_fin:
           return "en_curso"
       return "pasadas"
   ```
2. `backend/app/features/reservas/service.py:152-159` — importar `clasificar_periodo_reserva` de
   `schemas.py` y reemplazar los tres `if/elif` por:
   ```python
   if periodo is not None:
       ahora = datetime.now(timezone.utc)
       reservas = [
           r for r in reservas
           if clasificar_periodo_reserva(r.fecha_inicio, r.fecha_fin, ahora) == periodo
       ]
   ```
   Sin cambio de firma ni de comportamiento observable: las tres condiciones originales son
   mutuamente excluyentes y exhaustivas (confirmado en el impact scan de PLAN), así que la nueva
   rama `else → "pasadas"` es equivalente a la condición original `fecha_fin < ahora`.
3. `evals/run.py` (nuevo, en la raíz del repo, fuera de `backend/`) — script standalone sin
   frameworks, sin librerías nuevas, sin clases:
   - Agrega `backend/` a `sys.path`.
   - Setea con `os.environ.setdefault(...)` las 4 env vars que `app.core.config.Settings()`
     requiere sin default (`DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`,
     `FRONTEND_ORIGIN`), mismo patrón que ya usa `backend/tests/conftest.py:12-32` — necesario
     porque importar `schemas.py` dispara la cadena `models.py → core.database → core.config`
     que instancia `Settings()` a nivel de módulo.
   - Importa `clasificar_periodo_reserva` desde `app.features.reservas.schemas`.
   - Lee `evals/casos.json` (lista de objetos `{"entrada": {...}, "espero": "..."}` donde
     `entrada` trae `fecha_inicio`/`fecha_fin`/`ahora` en ISO 8601).
   - Por cada caso: parsea las fechas con `datetime.fromisoformat`, llama a la función, compara
     contra `espero`.
   - Imprime: cuántos casos pasaron sobre el total, el porcentaje, y el detalle (entrada, esperado,
     obtenido) de los que fallaron.
   - Sale con código 1 si el porcentaje de aciertos es menor a 80% (para que CI lo tome como fallo);
     código 0 si es ≥ 80%.
4. `evals/casos.json` — reescribir por completo (el contenido actual es de otro dominio, no aplica
   a esta función). Hasta 20 casos que cubran: reservas claramente futuras, claramente pasadas, en
   curso, casos límite (`ahora == fecha_inicio`, `ahora == fecha_fin`), y duraciones cortas y
   largas.

## Dependencies between steps

1 → 2 (service.py necesita que la función exista antes de importarla) → 3 y 4 son independientes
entre sí pero ambos dependen de que la función exista (paso 1) para que el script tenga algo real
que evaluar.

## Error handling

- `evals/run.py` no maneja input externo del usuario (no hay HTTP, no hay autenticación) — solo lee
  un archivo JSON local del propio repo. Si `evals/casos.json` no existe o tiene JSON inválido, el
  script falla con la excepción de Python sin capturarla (es una herramienta de desarrollo/CI, no
  un servicio; un traceback es información suficiente para quien la corre).
- Si `clasificar_periodo_reserva` recibe fechas naive (sin timezone), se comporta igual que hoy el
  código inline: no valida timezone-awareness (esa validación ya ocurre antes, en
  `ReservaCreate._validar_timezone_aware`, fuera del alcance de esta función).

## Tests

- [ ] **Regression test** — no aplica un test que "falle antes y pase después" en el sentido
  clásico, porque no hay un bug de comportamiento: es una extracción de función. La regresión real
  es la suite existente de `backend/tests/test_reservas_service.py` (tests de `listar_reservas` con
  `periodo=futuras/en_curso/pasadas`, confirmados en el impact scan) y
  `backend/tests/test_reservas_router.py` (tests HTTP de `GET /reservas?periodo=...`) — deben
  seguir pasando sin modificarlos, confirmando que el refactor preserva el comportamiento.
- [ ] `evals/run.py` corrido manualmente contra `evals/casos.json` — todos los casos deben pasar
  (100%, no solo ≥80%, porque los casos los define este mismo fix-plan para la función que también
  define).

## Regression risk

Bajo. Es una extracción de función 1:1 sin cambio de comportamiento, confirmada por el impact scan
(las 3 condiciones originales son mutuamente excluyentes y exhaustivas). No cambia la firma de
`listar_reservas`, no toca el router, no toca el frontend (que trata `periodo` como string opaco de
query param). El único riesgo real es un error de transcripción al mover la lógica — mitigado por
correr la suite de tests existente sin cambios.

## Rollback plan

- Pasos: revertir el commit de CODE (`git revert`). No hay migración de datos, no hay cambio de
  schema de base de datos, no hay endpoint nuevo — revertir el commit deja el código exactamente
  como estaba (los `if/elif` inline en `service.py`).
- Indicadores: si `backend/tests/test_reservas_service.py` o `test_reservas_router.py` fallan tras
  el cambio, o si `evals/run.py` reporta menos del 100% en `evals/casos.json`.
