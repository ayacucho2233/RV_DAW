# Spec FEAT-003: CI en GitHub Actions para Pull Requests

| Field | Value |
|-------|-------|
| Ticket | FEAT-003 |
| PRD | docs/daw/prd/prd-FEAT-003.md |
| Tier | FEATURE |
| Date | 2026-08-17 |
| Spec loops | 0 |

## Summary

Se crea un único workflow de GitHub Actions, `.github/workflows/ci.yml`, disparado en cada
`pull_request` (`opened`, `synchronize`, `reopened`). Define dos jobs independientes que corren en
paralelo: `backend` (instala dependencias Python, levanta un servicio PostgreSQL efímero que
satisface la `TEST_DATABASE_URL` por defecto de `backend/tests/conftest.py`, corre `ruff check .` y
`pytest`) y `frontend` (instala dependencias Node con `npm ci`, corre `npm run lint` y `npm test`).
El workflow declara `permissions: contents: read` a nivel raíz y `timeout-minutes: 10` en cada job,
por las mitigaciones del threat model (`docs/daw/security/threat-FEAT-003.md`).

## Coverage: PRD → blocks

| Requirement | Covered by |
|---|---|
| FR-01 | Block 1 |
| FR-02 | Block 1 |
| FR-03 | Block 1 |
| FR-04 | Block 1 |
| FR-05 | Block 1 |
| FR-06 | Block 1 |
| FR-07 | Block 1 |
| FR-08 | Block 1 |
| FR-09 | Block 1 |
| FR-10 | Block 1 |
| FR-11 | Block 1 |
| FR-12 | Block 1 |
| FR-13 | Block 1 |
| NFR-01 | Strategy: versiones fijas y explícitas en el propio YAML (Python 3.12, Node 20, Postgres 16), sin `latest` en ningún `uses:` ni `python-version:`/`node-version:` |
| NFR-02 | Strategy: la única "credencial" del workflow es la de Postgres de test (sin password, `trust`), documentada como riesgo aceptado en el threat model; no se referencia ningún secret real de GitHub (`secrets.*`) |
| NFR-03 | Strategy: `timeout-minutes: 10` en cada job (backend y frontend), que corren en paralelo — el límite duro por job impide que el workflow completo supere los 10 minutos por un job colgado |

## Dependencies between blocks

Ninguna — es un único bloque, un único archivo nuevo.

## Block 1 — Workflow de CI (`.github/workflows/ci.yml`)

**Files**
- `.github/workflows/ci.yml` (new) — workflow de GitHub Actions con los jobs `backend` y `frontend`.

**Logic**

Estructura del workflow (nombres de keys en inglés, como lo exige la sintaxis de GitHub Actions):

```
name: CI

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read

jobs:
  backend:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: testuser
          POSTGRES_DB: reserva_vehiculos_test
          POSTGRES_HOST_AUTH_METHOD: trust
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - run: pip install -r requirements.txt
        working-directory: backend
      - run: ruff check .
        working-directory: backend
      - run: pytest
        working-directory: backend

  frontend:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
        working-directory: frontend
      - run: npm run lint
        working-directory: frontend
      - run: npm test
        working-directory: frontend
```

Notas de implementación (no negociables, vienen del threat model y del PRD):

- `POSTGRES_HOST_AUTH_METHOD: trust` (sin password) es intencional: reproduce exactamente el default
  de `TEST_DATABASE_URL` en `backend/tests/conftest.py:12-15`
  (`postgresql+psycopg2://testuser@127.0.0.1:5433/reserva_vehiculos_test`, sin password). Riesgo
  aceptado documentado en `docs/daw/security/threat-FEAT-003.md` — un comentario en el propio YAML,
  arriba del bloque `services.postgres`, debe referenciar ese archivo.
- `permissions: contents: read` a nivel de workflow: el CI no necesita escribir en el repositorio.
- Las tres actions (`actions/checkout`, `actions/setup-python`, `actions/setup-node`) van pineadas a
  `@v4`, nunca a `@main` ni sin versión.
- `pip install`, `ruff check .` y `pytest` corren con `working-directory: backend` (no `cd` manual),
  para que cada step sea independientemente legible en los logs de GitHub Actions.
- `npm ci` (no `npm install`) para que la instalación sea reproducible a partir de
  `frontend/package-lock.json`, consistente con FR-08.
- El health check `pg_isready` con reintentos asegura que `pytest` no arranque antes de que Postgres
  acepte conexiones (evita el falso-fallo por timing que describe AC-07 del PRD).

**Error handling**

- Si `pip install`, `ruff check .` o `pytest` fallan (exit code ≠ 0), el step falla y GitHub Actions
  detiene el resto de ese job automáticamente (comportamiento por defecto, sin `continue-on-error`)
  — cubre AC-05.
- Si el servicio Postgres no pasa su health check dentro de los reintentos configurados, GitHub
  Actions falla el job `backend` antes de llegar al step de `pytest`, con un mensaje explícito de
  "service container failed to become healthy" — cubre AC-07 (fallo identificable, no timeout
  silencioso).
- Si `npm ci`, `npm run lint` o `npm test` fallan, el step falla y detiene el job `frontend` —
  mismo mecanismo que el backend, cubre AC-05 para el lado frontend.
- Ambos jobs son independientes (`jobs.backend` y `jobs.frontend` no declaran `needs:` entre sí): el
  fallo de uno no cancela ni oculta el resultado del otro — cubre FR-11 y AC-04.

**Required tests**

- [ ] T1 — Validación de sintaxis: `python3 -c "import yaml, sys; yaml.safe_load(open('.github/workflows/ci.yml'))"` no lanza excepción — valida que el YAML es válido antes de commitear.
- [ ] T2 — Corrida real en un Pull Request de esta misma rama: ambos jobs (`backend`, `frontend`)
      aparecen como checks del PR y terminan en verde — valida AC-01, AC-02, AC-03, AC-06.
- [ ] T3 — En esa misma corrida (o en una segunda corrida sobre el mismo lockfile), confirmar en los
      logs que `backend` y `frontend` arrancan sin esperarse entre sí (no hay `needs:`) y que el step
      de cache (`setup-python`/`setup-node`) reporta cache hit en la segunda corrida — valida AC-04,
      FR-11, FR-12.
- [ ] T4 — Rotura deliberada y temporal de un test de **backend** en un commit de prueba: el job
      `backend` se marca en rojo (error documentado: falla de `pip install`/`ruff check .`/`pytest`)
      y el job `frontend` no se ve afectado — valida AC-05 y la independencia de jobs. Revertir el
      commit de prueba antes de mergear.
- [ ] T5 — Rotura deliberada y temporal de un test de **frontend** en un commit de prueba: el job
      `frontend` se marca en rojo (error documentado: falla de `npm ci`/`npm run lint`/`npm test`) y
      el job `backend` no se ve afectado — valida AC-05 y la independencia de jobs. Revertir el
      commit de prueba antes de mergear.
- [ ] T6 — Verificación del comportamiento ante Postgres no disponible: cambiar temporalmente el
      puerto mapeado del servicio (p. ej. a uno que no exponga el servicio) en un commit de prueba y
      confirmar que el job `backend` falla con un mensaje identificable de "service container
      unhealthy" (error documentado: health check de Postgres falla), no con un timeout genérico de
      `pytest` — valida AC-07. Revertir el commit de prueba antes de mergear.

**Completion criterion**

`.github/workflows/ci.yml` existe, pasa la validación de sintaxis YAML, y una corrida real sobre un
PR de esta rama muestra ambos jobs (`backend`, `frontend`) en verde ejecutando exactamente
`ruff check .` + `pytest` (backend) y `npm run lint` + `npm test` (frontend) — los mismos comandos
documentados en `AGENTS.md` → Stack.

## Final verification

- `.github/workflows/ci.yml` es el único archivo nuevo del ticket.
- Ambos jobs corren en paralelo, con `timeout-minutes: 10` cada uno y `permissions: contents: read`
  a nivel de workflow.
- El job `backend` corre contra un Postgres real (no mocks), en el puerto y usuario que
  `backend/tests/conftest.py` espera por defecto.
- Ningún secret de GitHub (`secrets.*`) es referenciado por el workflow.
- El riesgo aceptado de `POSTGRES_HOST_AUTH_METHOD=trust` está comentado en el propio archivo y
  referenciado en `docs/daw/security/threat-FEAT-003.md`.
