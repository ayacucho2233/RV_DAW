# PRD FEAT-003: CI en GitHub Actions para Pull Requests

| Field | Value |
|-------|-------|
| Ticket | FEAT-003 |
| Tracker | none |
| Date | 2026-08-17 |
| PRD loops | 0 |

## Context and Problem

El proyecto no tiene integración continua. Los tests (backend con pytest, frontend con vitest) y los
linters (ruff en backend, eslint en frontend) sólo corren localmente si cada desarrollador se acuerda
de ejecutarlos. Esto ya generó al menos un caso real: FIX-003 tuvo que corregir hallazgos de ruff y
eslint que se habían acumulado sin que nada los señalara en el momento en que se introdujeron.

Sin un workflow de CI, un PR puede mergearse a `main` con tests rotos o con código que no pasa el
linter, y el problema recién se descubre después, cuando es más caro de diagnosticar y corregir.

## Goals

- Que todo Pull Request ejecute automáticamente, sin intervención manual: instalación de
  dependencias, suite de tests y linter, tanto para backend como para frontend.
- Que el resultado (verde/rojo) sea visible en el propio PR de GitHub antes de mergear.
- Que el mismo comando que corre en CI sea el que ya está documentado en `AGENTS.md` → Stack, para
  que no haya divergencia entre "lo que corre en CI" y "lo que el equipo corre a mano".

## Functional Requirements

- FR-01: El workflow se dispara automáticamente en eventos `pull_request` (`opened`,
  `synchronize`, `reopened`) dirigidos a cualquier rama base.
- FR-02: El workflow define un job de backend que corre en un entorno Linux con Python.
- FR-03: El job de backend instala las dependencias listadas en `backend/requirements.txt`.
- FR-04: El job de backend levanta un servicio PostgreSQL efímero que satisface la
  `TEST_DATABASE_URL` por defecto de `backend/tests/conftest.py`
  (`postgresql+psycopg2://testuser@127.0.0.1:5433/reserva_vehiculos_test`), para que la suite de
  tests (que usa una base de datos real, no mocks) corra sin configuración adicional.
- FR-05: El job de backend ejecuta la suite de tests con `pytest` (según `AGENTS.md` /
  `backend/pytest.ini`).
- FR-06: El job de backend ejecuta el linter con `ruff check .` dentro de `backend/`.
- FR-07: El workflow define un job de frontend que corre en un entorno Linux con Node.js.
- FR-08: El job de frontend instala las dependencias con `npm ci`, usando `frontend/package-lock.json`
  para una instalación reproducible.
- FR-09: El job de frontend ejecuta la suite de tests con `npm test` (`vitest run`, no interactivo).
- FR-10: El job de frontend ejecuta el linter con `npm run lint` (`eslint .`).
- FR-11: Los jobs de backend y frontend corren en paralelo (son independientes entre sí).
- FR-12: Cada job usa cache de dependencias (pip y npm) para acelerar corridas sucesivas, con la
  clave de cache basada en el lockfile correspondiente (`requirements.txt`, `package-lock.json`).
- FR-13: El workflow reporta su resultado como un check de estado sobre el commit del PR, visible en
  la interfaz de GitHub.

## Non-Functional Requirements

- NFR-01: El workflow usa versiones de runtime fijas y explícitas (no `latest`): una versión de
  Python 3.x y una versión LTS de Node.js, para que la corrida sea reproducible entre ejecuciones.
- NFR-02: El workflow no expone ni loguea secretos; la contraseña de la base de datos de test es una
  credencial de solo-test, sin valor fuera de la corrida de CI.
- NFR-03: El tiempo total del workflow (ambos jobs, en paralelo) no debe superar los 10 minutos en
  una corrida sin cache fría extrema, para no volverse un cuello de botella en el flujo de PRs.

## Acceptance Criteria

- AC-01: WHEN se abre, sincroniza o reabre un Pull Request (FR-01), THE workflow de CI SHALL
  ejecutarse automáticamente sin intervención manual.
- AC-02: WHEN el job de backend (FR-02) corre, THE CI SHALL instalar las dependencias de
  `backend/requirements.txt` (FR-03), levantar el servicio PostgreSQL efímero descripto en FR-04,
  ejecutar `pytest` (FR-05) y ejecutar `ruff check .` (FR-06).
- AC-03: WHEN el job de frontend (FR-07) corre, THE CI SHALL instalar las dependencias con `npm ci`
  a partir de `package-lock.json` (FR-08), ejecutar `npm test` (FR-09) y ejecutar `npm run lint`
  (FR-10).
- AC-04: WHEN el workflow corre, THE CI SHALL ejecutar el job de backend y el de frontend en paralelo
  (FR-11) y SHALL reutilizar cache de dependencias por lockfile en cada uno (FR-12).
- AC-05: IF cualquier paso de instalación, tests o lint falla en cualquiera de los dos jobs, THEN THE
  CI SHALL marcar el check del PR como fallido (FR-13) y detener ese job sin ocultar el error.
- AC-06: WHEN ambos jobs (backend y frontend) terminan exitosamente, THE CI SHALL marcar el check del
  PR (FR-13) como exitoso.
- AC-07: IF el servicio de PostgreSQL no está disponible o no acepta conexiones al momento de correr
  los tests del backend (FR-04), THEN THE CI SHALL fallar el job de backend con un error identificable
  (no un timeout silencioso ni un falso verde).

## Out of Scope

- Deploy automático o cualquier acción sobre `main` al mergear (este ticket es solo el check de PR).
- Escaneo de seguridad (SAST/dependencias) dentro de este workflow — ya existe como gate separado
  dentro del pipeline de DAW (`/daw-security-sast`), no como parte de CI de GitHub.
- Reportes de cobertura de tests o publicación de artefactos.
- Ejecución de migraciones de Alembic contra una base persistente (los tests de backend crean y
  destruyen su propio esquema, ver `backend/tests/conftest.py`).
- Protección de rama (branch protection rule) que exija este check para poder mergear — queda para
  configuración manual del repositorio por parte del usuario, fuera del alcance de código.

## Risks and Mitigations

- **Riesgo:** la URL de test por defecto en `conftest.py` (puerto 5433, usuario `testuser`, sin
  password) no coincide con el servicio Postgres que se configure en el workflow, y los tests fallan
  por conexión en vez de por una razón real.
  **Mitigación:** el servicio de Postgres en el workflow se configura exactamente con esos valores
  (puerto 5433, usuario `testuser`, base `reserva_vehiculos_test`), documentado explícitamente en el
  spec.
- **Riesgo:** `npm run lint` o `ruff check .` fallan en CI por diferencias de entorno (versión de
  Node/Python distinta a la que usa cada desarrollador localmente) aunque el código esté bien.
  **Mitigación:** NFR-01 fija versiones explícitas, iguales a las que ya usa el proyecto (ver
  `requirements.txt` para pistas de versión de Python vía dependencias, y Vite 6 / eslint 10 para
  Node reciente).

## Dependencies

- `backend/requirements.txt`, `backend/pytest.ini`, `backend/ruff.toml` (ya existentes).
- `frontend/package.json`, `frontend/package-lock.json` (ya existentes).
- `backend/tests/conftest.py` — fuente de verdad de la URL de base de datos de test que CI debe
  satisfacer.
