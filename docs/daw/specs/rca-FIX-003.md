# RCA FIX-003: Configurar ruff/eslint correctamente y corregir hallazgos reales

## Root cause

Al agregar `ruff` (backend) y `eslint` (frontend) en el ticket anterior (commit `6e6a573`), se
instaló cada herramienta con su configuración por defecto, sin adaptarla a los patrones ya
presentes en el código del proyecto. Esto generó dos categorías de hallazgos distintas:

### 1. Falso positivo de configuración (12 de 36 hallazgos de ruff)

La regla `B008` de `flake8-bugbear` (incluida en el set por defecto de ruff) prohíbe llamar a una
función dentro de un valor por defecto de un argumento — en general una buena práctica, porque
detecta bugs de mutabilidad compartida. Pero **FastAPI usa exactamente ese patrón a propósito**:
`def endpoint(db: Session = Depends(get_db))` es la forma en que FastAPI resuelve inyección de
dependencias. Ruff expone un setting específico para este caso
(`lint.flake8-bugbear.extend-immutable-calls = ["fastapi.Depends", "fastapi.Query", ...]`) que
nunca se configuró al instalar la herramienta.

### 2. Deuda de estilo preexistente, nunca detectada (el resto)

El proyecto no tenía ningún linter configurado hasta el ticket anterior. Los demás hallazgos
(imports sin ordenar, un `dict()` que podía ser un literal, `with` anidados que se pueden combinar,
comentarios `# noqa` que ya no aplican, `subprocess.run` sin `check=` explícito, una rama de código
muerta en `frontend/src/api/client.js`, variables sin usar en tests) son issues reales de estilo/
limpieza que existían antes de este ticket, simplemente nunca se habían señalado.

Dos casos particulares que **no son bugs** y no se tocan en este fix:
- `DTZ001` (2 casos) en `test_reservas_service.py`: el test crea deliberadamente datetimes "naive"
  (sin timezone) para verificar que la app los rechaza. Agregarles timezone anularía el propósito
  del test.
- `PLW1510` (2 casos) en `test_migration.py`/`test_migration_reservas.py`: `subprocess.run(...)` se
  usa sin `check=True` a propósito, porque el test necesita capturar `returncode`/`stdout`/`stderr`
  para armar su propio mensaje de assert en vez de dejar que `subprocess` levante
  `CalledProcessError`. El fix es agregar `check=False` explícito (documenta la intención sin
  cambiar comportamiento), no agregar `check=True`.

## Affected component

- `backend/ruff.toml` (nuevo — configurar `extend-immutable-calls` para FastAPI)
- `backend/tests/test_vehiculos_service.py`, `backend/tests/test_reservas_service.py`,
  `backend/tests/test_migration.py`, `backend/tests/test_migration_reservas.py` (limpieza de estilo)
- `frontend/src/api/client.js` (eliminar fallback muerto con `Buffer`)
- `frontend/src/features/reservas/*.test.jsx` (variables sin usar)
- `frontend/src/features/reservas/ReservasListado.jsx`,
  `frontend/src/features/reservas/ReservasPublicPage.jsx`,
  `frontend/src/features/vehiculos/VehiculosAdminPage.jsx` (patrón `set-state-in-effect`, a evaluar
  en PLAN si corresponde refactor o suppression documentada)

## Related PRD

Ninguno — el área de tooling/lint no está cubierta por ningún PRD existente (confirmado con el
usuario en DEFINE).

## Gap in the PRD

No aplica.

## Rollback plan

Revertir el commit de este fix. Como no toca `ruff.toml`/`eslint.config.js` de forma incompatible
con lo ya commiteado en FIX previo (solo agrega configuración adicional) y los cambios de código
son cosméticos/de limpieza sin alterar comportamiento observable, un `git revert` del commit de
CODE es suficiente y no requiere pasos adicionales de datos/migraciones.
