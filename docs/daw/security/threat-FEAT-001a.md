# Threat Model — FEAT-001a: Gestión del pool de vehículos

| Field | Value |
|-------|-------|
| Ticket | FEAT-001a |
| Date | 2026-08-02 |
| Basis | STRIDE (Microsoft), OWASP Threat Modeling, OWASP ASVS, ISO 27001 |

## Arquitectura analizada

```
Navegador (panel admin React)         Internet/red                FastAPI backend                  PostgreSQL
  App.jsx / VehiculosAdminPage.jsx  --HTTP Basic + JSON-->   router.py (vehiculos)  --SQLAlchemy-->  tabla vehiculos
  client.js (sesión admin en memoria)                          |
                                                                 v
                                                          security.py (HTTPBasic + bcrypt vs
                                                          ADMIN_PASSWORD_HASH)
                                                                 |
                                                                 v
                                                          service.py -> repository.py
```

Componentes cubiertos: `backend/app/core/security.py`, `backend/app/features/vehiculos/router.py`,
`service.py`, `repository.py`, `models.py`, `backend/app/main.py` (CORS), PostgreSQL, y el panel
admin en `frontend/src/features/vehiculos/`.

## Trust boundaries (F-TM-02)

| # | Boundary | Cruce | Nivel de confianza |
|---|----------|-------|---------------------|
| TB-01 | Internet ↔ FastAPI | Cualquier cliente HTTP (no solo el navegador — CORS no es un control de acceso, solo restringe JS de otros orígenes en el navegador) → 6 endpoints de administración | No confiable → confiable, solo tras auth |
| TB-02 | FastAPI ↔ PostgreSQL | `repository.py` vía SQLAlchemy | Confiable, pero credenciales sensibles en tránsito/reposo |
| TB-03 | Navegador (JS) ↔ FastAPI | `client.js` (axios), scope restringido por CORS | No confiable → confiable, solo tras auth |

## Datos sensibles (F-TM-05)

| Dato | Clasificación | Dónde vive |
|---|---|---|
| `ADMIN_PASSWORD_HASH` | Credencial | Variable de entorno del backend |
| Password HTTP Basic (en tránsito, antes del hash) | Credencial | Header `Authorization` de cada request admin |
| `DATABASE_URL` (incluye password de PostgreSQL) | Credencial | Variable de entorno del backend |
| Patente / tipo / estado del vehículo | Dato de negocio, no PII | Tabla `vehiculos` |

La patente y el tipo de vehículo no son PII ni credenciales — no requieren cifrado especial más allá
de la protección estándar de la base de datos. Las credenciales sí lo requieren (F-TM-07, abajo).

## Análisis STRIDE por componente

### `security.py` (autenticación HTTP Basic)

| STRIDE | Riesgo | Likelihood | Impact |
|---|---|---|---|
| Spoofing | Fuerza bruta contra la única credencial de admin compartida (HTTP Basic no tiene lockout nativo) | Media | Alto |
| Tampering | N/A — no modifica datos | — | — |
| Repudiation | Una sola credencial compartida: no se puede atribuir una acción a una persona específica | Baja | Media |
| Information Disclosure | Mensaje de error que revela si el usuario existe pero la contraseña es incorrecta (username enumeration) | Baja | Baja |
| Denial of Service | Sin rate limiting, un atacante puede saturar el endpoint de auth | Baja (herramienta interna) | Media |
| Elevation of Privilege | N/A — un solo rol admin, sin niveles de privilegio | — | — |

### `router.py` / `service.py` / `repository.py` (vehículos)

| STRIDE | Riesgo | Likelihood | Impact |
|---|---|---|---|
| Spoofing | Cubierto por TB-01 (ver arriba) | — | — |
| Tampering | Inyección SQL si se usara SQL crudo sin parametrizar | Baja (mitigado por diseño: ORM) | Alto |
| Repudiation | Sin log de qué operación de alta/baja/reactivación se ejecutó y cuándo | Media | Media |
| Information Disclosure | `IntegrityError` de Postgres (violación del `UNIQUE` en patente, condición de carrera TOCTOU entre el chequeo en `service.py` y el `INSERT`) sin capturar, filtrando un 500 con detalle interno del driver de DB | Media | Media |
| Denial of Service | Igual que arriba, sin rate limiting | Baja | Media |
| Elevation of Privilege | N/A | — | — |

### `main.py` (CORS) / PostgreSQL (TB-02)

| STRIDE | Riesgo | Likelihood | Impact |
|---|---|---|---|
| Tampering | `DATABASE_URL` mal gestionada (commiteada, logueada) | Baja si se sigue el plan | Alto |
| Information Disclosure | Conexión a Postgres sin TLS si la DB está en una red no confiable | Depende de D-02 (infraestructura, aún sin definir) | Alto |

### Panel admin (React + Vite)

| STRIDE | Riesgo | Likelihood | Impact |
|---|---|---|---|
| Information Disclosure | XSS si la patente (input de usuario) se renderizara con `dangerouslySetInnerHTML` | Baja (React escapa por defecto) | Alto si ocurriera |
| Information Disclosure | Header `Authorization` interceptado en tránsito si no hay TLS | Media (depende de D-02) | Crítico |

## Riesgos y mitigaciones (F-TM-03)

| # | Riesgo | STRIDE | Likelihood | Impact | Mitigación (se pliega al spec) |
|---|--------|--------|------------|--------|-------------------------------|
| TM-01 | 🟠 HTTP Basic transmite la credencial en Base64 (no cifrado) — sin TLS obligatorio, es equivalente a texto plano en la red | Information Disclosure | Media | Crítico | **Requisito no negociable de despliegue:** todo el tráfico debe servirse detrás de TLS (terminación TLS en el proxy/load balancer, o `https` directo). Documentar en `README`/spec como precondición de producción; en desarrollo local se acepta HTTP explícitamente. Se pliega como nota en Block 3 del spec. |
| TM-02 | 🟠 Fuerza bruta sobre la única credencial admin — HTTP Basic no tiene lockout | Spoofing | Media | Alto | Agregar rate limiting a los 6 endpoints de administración (p. ej. `slowapi`), ej. máx. N intentos fallidos por IP por minuto. Se pliega como tarea explícita de Block 3. |
| TM-03 | 🟡 `IntegrityError` de Postgres (condición de carrera en patente única) sin capturar → 500 con detalle interno | Information Disclosure | Media | Media | `repository.py` debe capturar `IntegrityError` en el `INSERT`/`UPDATE` y traducirlo a `PatenteYaExisteError` (ya definida en Block 2). `main.py` debe registrar un exception handler genérico que devuelva 500 sin detalle interno para cualquier error no anticipado. Se pliega en Block 2 y Block 3. |
| TM-04 | 🟡 Sin log de operaciones administrativas (alta/modificación/baja/reactivación) | Repudiation | Media | Media | Loguear cada operación de escritura (endpoint, timestamp, resultado) desde `service.py` o `router.py`, sin incluir la contraseña ni el header `Authorization`. No se requiere atribución por persona (una sola credencial compartida, fuera de alcance de este sub-ticket). Se pliega como tarea de Block 2/3. |
| TM-05 | 🟢 Mensaje de error de auth revela si el usuario existe | Information Disclosure | Baja | Baja | `security.py` debe devolver siempre el mismo 401 genérico ("credenciales inválidas"), sin distinguir usuario incorrecto de contraseña incorrecta. Se pliega en Block 3. |
| TM-06 | 🟢 DoS por ausencia de rate limiting general | Denial of Service | Baja | Media | Cubierto en la práctica por TM-02 (mismo mecanismo). Si el entorno de despliegue (D-02, aún no definido) resulta ser público, agregar protección adicional a nivel de infraestructura (WAF/rate limiting del proxy) — queda documentado como dependencia abierta, no bloquea este ticket. |

No hay riesgos que requieran ser aceptados sin mitigación (F-TM-04 no aplica): los 6 riesgos identificados tienen mitigación concreta arriba.

## Cifrado en tránsito y en reposo (F-TM-07)

- **`ADMIN_PASSWORD_HASH`**: se almacena ya hasheado con bcrypt (irreversible) — "en reposo" nunca existe la contraseña en texto plano, solo el hash, y solo en la variable de entorno del backend (nunca en la base de datos ni en el código).
- **Password HTTP Basic en tránsito**: mitigado por TM-01 (TLS obligatorio en todo entorno que no sea desarrollo local).
- **`DATABASE_URL`**: en reposo, solo en `.env` (excluido de git vía el `.gitignore` actualizado en Block 1) y en el entorno de ejecución del servidor, nunca logueada. En tránsito hacia PostgreSQL: usar `sslmode=require` si la base de datos no corre en el mismo host/red de confianza que el backend (a decidir junto con D-02, infraestructura).

## Conclusión

```
┌─────────────────────────────────────────────────────────┐
│  /daw-threat-modeling FEAT-001a — PASSED                 │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Attack surfaces identified: 4 (auth, API admin,         │
│    conexión a DB, panel admin)                            │
│  Trust boundaries declared: 3 (TB-01, TB-02, TB-03)       │
│                                                          │
│  Risks:                                                  │
│    🟠 HIGH: TM-01 credencial HTTP Basic sin TLS —         │
│       Mitigation: TLS obligatorio en producción            │
│    🟠 HIGH: TM-02 fuerza bruta sin lockout —               │
│       Mitigation: rate limiting en endpoints admin          │
│    🟡 MEDIUM: TM-03 fuga de detalle interno en 500 —       │
│       Mitigation: exception handler genérico + traducir    │
│       IntegrityError                                       │
│    🟡 MEDIUM: TM-04 sin log de operaciones admin —          │
│       Mitigation: logging de escrituras                     │
│    🟢 LOW: TM-05 enumeración de usuario en 401 —            │
│       Mitigation: mensaje de error genérico                 │
│    🟢 LOW: TM-06 DoS sin rate limiting —                    │
│       Mitigation: cubierta por TM-02                        │
│                                                          │
│  Mitigations to fold into the spec:                       │
│    1. TLS obligatorio en despliegue (Block 3, nota de      │
│       infraestructura)                                     │
│    2. Rate limiting en los 6 endpoints admin (Block 3)      │
│    3. Traducir IntegrityError → PatenteYaExisteError +      │
│       exception handler genérico para 500 (Block 2/3)       │
│    4. Logging de operaciones de escritura (Block 2/3)       │
│    5. Mensaje 401 genérico, sin distinguir el motivo        │
│       (Block 3)                                            │
│                                                          │
│  ─────────────────────────────────────────────────────   │
│  Risks: C:0 H:2 M:2 L:2                                    │
│  Report: docs/daw/security/threat-FEAT-001a.md             │
└─────────────────────────────────────────────────────────┘
```
