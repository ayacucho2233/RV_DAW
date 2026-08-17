# Threat Model FEAT-003: CI en GitHub Actions para PRs

| Field | Value |
|-------|-------|
| Ticket | FEAT-003 |
| Date | 2026-08-17 |
| Design reviewed | `.github/workflows/ci.yml` (1 archivo nuevo, no existe `.github/workflows/` previo) |

## Componentes y superficies de ataque

1. **Workflow de GitHub Actions** (`.github/workflows/ci.yml`), disparado por eventos
   `pull_request` (`opened`, `synchronize`, `reopened`). Ejecuta código del PR (tests, lint) sobre un
   runner de GitHub. Superficie: cualquier autor de PR (incluyendo forks) controla el código que
   corre dentro del job.
2. **Job `backend`**: instala dependencias Python (`pip install -r backend/requirements.txt`) y
   corre `ruff check .` / `pytest` contra un servicio PostgreSQL efímero.
3. **Job `frontend`**: instala dependencias Node (`npm ci`) y corre `npm run lint` / `npm test`
   (vitest).
4. **Servicio PostgreSQL efímero** (contenedor `postgres:16`, `POSTGRES_HOST_AUTH_METHOD=trust`,
   puerto 5433), usado solo por el job `backend` durante la corrida.
5. **Registries externos** (PyPI, npm registry) consultados durante la instalación de dependencias.

## Trust boundaries

- **Autor del PR (no confiable, puede ser un fork) → Runner de GitHub Actions**: el runner ejecuta
  código arbitrario del PR (tests, código de la app). Este es el límite de confianza principal.
- **Runner → Servicio PostgreSQL efímero**: ambos viven dentro de la red del mismo job; el servicio
  no está expuesto fuera del runner ni persiste luego de la corrida.
- **Runner → Registries externos (PyPI/npm)**: el runner descarga y ejecuta paquetes de terceros
  durante `pip install` / `npm ci`.

## Análisis STRIDE

### Workflow / Runner (disparado por `pull_request`)

| Categoría | Evaluación |
|---|---|
| Spoofing | Bajo. GitHub autentica el disparador del evento; no hay suplantación posible desde el propio workflow. |
| Tampering | Bajo. El evento es `pull_request` (no `pull_request_target`): para PRs de forks, GitHub usa un `GITHUB_TOKEN` de solo lectura y sin acceso a secrets del repo — un PR malicioso no puede usar el propio CI para modificar el repo. |
| Repudiation | Bajo. GitHub Actions deja log completo de cada corrida (quién disparó el PR, qué commit, qué salida tuvo cada step) — no se necesita logging adicional. |
| Information Disclosure | Bajo. El workflow no maneja secretos reales: la credencial de Postgres es de solo-test, sin valor fuera del contenedor efímero (NFR-02 del PRD). |
| **Denial of Service** | 🟡 **MEDIO**: un test que cuelgue (loop infinito, deadlock) o una corrida anómala podría bloquear el job indefinidamente, consumiendo minutos de CI sin límite. |
| **Elevation of Privilege** | 🟡 **MEDIO**: una dependencia de terceros comprometida (paquete de PyPI o npm) ejecuta código arbitrario durante la instalación, con los permisos del `GITHUB_TOKEN` de ese job. |

### Servicio PostgreSQL efímero

| Categoría | Evaluación |
|---|---|
| Spoofing / Tampering / Repudiation | N/A — contenedor efímero, sin datos persistentes, sin actores externos con acceso. |
| Information Disclosure | 🟢 **BAJO, riesgo aceptado** (ver abajo): `POSTGRES_HOST_AUTH_METHOD=trust` (sin password) es aceptable porque el contenedor solo es alcanzable desde los steps del mismo job — no expuesto a la red pública ni a otros jobs — y se destruye al terminar la corrida. |
| Denial of Service | Bajo. Cubierto por el timeout general del job (ver mitigación abajo). |
| Elevation of Privilege | N/A — no hay ruta desde este contenedor de test hacia la base de datos real de producción (credenciales, host y puerto distintos). |

### Instalación de dependencias (pip / npm)

Cubre el mismo riesgo de **Elevation of Privilege** ya listado arriba: un paquete comprometido en
`backend/requirements.txt` o en el árbol resuelto por `frontend/package-lock.json` podría ejecutar
código arbitrario durante `pip install` / `npm ci`.

## Riesgos clasificados

| Riesgo | STRIDE | Likelihood | Impact | Mitigación |
|---|---|---|---|---|
| Job colgado (test/loop infinito) consume minutos de CI sin límite | DoS | Medium | Low | `timeout-minutes: 10` en cada job (backend y frontend), consistente con NFR-03 del PRD |
| Dependencia comprometida (PyPI/npm) ejecuta código con permisos del `GITHUB_TOKEN` del job | Elevation of Privilege | Low | Medium | Dependencias ya fijadas por versión exacta (`requirements.txt` con `==`, `npm ci` contra `package-lock.json`); el workflow declara `permissions: contents: read` a nivel raíz (no se piden permisos de escritura que una dependencia comprometida podría abusar) |
| Actions de terceros (`actions/checkout`, `actions/setup-python`, `actions/setup-node`) como vector de supply chain | Elevation of Privilege | Low | Low | Son actions oficiales mantenidas por GitHub, pineadas a una versión mayor explícita (no `@main`/`@latest`) |

**Riesgo aceptado (F-TM-04):**

| Campo | Valor |
|---|---|
| Riesgo | `POSTGRES_HOST_AUTH_METHOD=trust` en el servicio Postgres de CI (sin password) |
| Quién lo acepta | El usuario del proyecto, en la sesión de PLAN de FEAT-003 (2026-08-17) |
| Justificación | Contenedor Docker efímero, sin exposición fuera de la red del job, destruido al terminar la corrida; necesario para igualar exactamente el default de `TEST_DATABASE_URL` en `backend/tests/conftest.py` (usuario `testuser`, sin password), de forma que AC-07 del PRD (fallo identificable si Postgres no está disponible) se pueda verificar sin ruido de credenciales |
| Condición de revisión | Si el workflow alguna vez corre contra una instancia Postgres persistente o compartida (no un contenedor de servicio efímero por job), o si `conftest.py` cambia su URL de test por defecto para requerir password |

Sin riesgos CRITICAL ni HIGH.

## Mitigaciones a incorporar en el spec

1. `timeout-minutes: 10` en el job `backend` y en el job `frontend`.
2. `permissions: contents: read` declarado a nivel de workflow (principio de mínimo privilegio; el
   CI no necesita escribir en el repo).
3. Las tres GitHub Actions usadas (`checkout`, `setup-python`, `setup-node`) pineadas a una versión
   mayor explícita (p. ej. `@v4`), no a `@main`.
4. El riesgo aceptado de `POSTGRES_HOST_AUTH_METHOD=trust` queda documentado en el spec (sección de
   riesgos o comentario en el propio workflow), citando este reporte.

## Resumen

- Superficies de ataque identificadas: 5
- Trust boundaries declaradas: 3
- Riesgos: C:0 H:0 M:2 L:1 (+ 1 riesgo aceptado documentado)
- Datos sensibles manejados: ninguno real — una credencial de Postgres de solo-test, sin valor fuera
  del contenedor efímero de CI (no aplica cifrado en tránsito/reposo, F-TM-07, porque no hay PII ni
  credenciales reales involucradas).
