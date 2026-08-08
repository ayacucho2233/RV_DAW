# Threat Model — FEAT-001c: Consulta y creación de reservas

| Field | Value |
|-------|-------|
| Ticket | FEAT-001c |
| Date | 2026-08-05 |
| Basis | STRIDE (Microsoft), OWASP Threat Modeling, OWASP ASVS, ISO 27001 |

## Arquitectura analizada

```
Navegador (vista pública)              Internet/red              FastAPI backend                    PostgreSQL
  ReservasPublicPage.jsx/           --JSON, SIN auth-->    router.py (reservas)  --SQLAlchemy-->     tabla reservas
  ReservaForm.jsx                                              |                                       ^
  reservasApi.js (sin Authorization)                           v                                       |
                                                          service.py (SELECT FOR UPDATE          --lee--+
                                                          sobre reservas activas del vehículo)            |
                                                                 |                                        |
                                                                 v                                  vehiculos.repository
                                                          repository.py (reservas)              (import de solo lectura,
                                                                                                   proyección VehiculoPublico)
```

Componentes cubiertos: `backend/app/features/reservas/{router,service,repository,models,schemas,exceptions}.py`,
`backend/app/main.py` (wiring, sin cambios de CORS), PostgreSQL (tabla `reservas`), y
`frontend/src/features/reservas/` (vista pública) + `App.jsx` (vista condicional nueva).

## Trust boundaries (F-TM-02)

| # | Boundary | Cruce | Nivel de confianza |
|---|----------|-------|---------------------|
| TB-C-01 | Internet ↔ FastAPI (`reservas.router`) | Cualquier cliente HTTP → 3 endpoints públicos | No confiable → **sigue sin control de acceso**, a diferencia de TB-01 de FEAT-001a (que cruzaba a "confiable, solo tras auth"). Es el boundary más débil de todo el sistema hasta ahora, por diseño explícito del PRD. |
| TB-C-02 | FastAPI ↔ PostgreSQL (`reservas`) | `repository.py` vía SQLAlchemy, incluye `SELECT ... FOR UPDATE` | Confiable, pero con PII en tránsito/reposo (ver F-TM-05/07) |
| TB-C-03 | Navegador (JS) ↔ FastAPI reservas | `reservasApi.js` sin header `Authorization` | No confiable → sigue sin control de acceso (mismo que TB-C-01, vía navegador) |
| TB-C-04 | `reservas.service` ↔ `vehiculos.repository` | Import de Python directo (mismo proceso, no HTTP) para leer el pool de vehículos desde un contexto sin autenticación | Confiable a nivel de proceso, pero la proyección hacia afuera (`VehiculoPublico`: solo `patente`/`tipo`) es la barrera real — un descuido acá filtraría el campo `estado` administrativo (u otros) a la vista pública |

## Datos sensibles (F-TM-05)

| Dato | Clasificación | Dónde vive |
|---|---|---|
| `nombre_empleado` | PII | Tabla `reservas` |
| `legajo` | PII (identificador de empleado) | Tabla `reservas` |
| `licencia` | PII sensible (número de licencia de conducir) | Tabla `reservas` |
| `destino`, `fecha_inicio`, `fecha_fin`, `vehiculo_id` | Dato de negocio, no PII | Tabla `reservas` |
| Patente / tipo del vehículo (proyección pública) | Dato de negocio, no PII | Ya clasificado en threat-FEAT-001a.md |

A diferencia de FEAT-001a (que solo manejaba credenciales de un único admin), este ticket introduce
el primer dato PII de terceros del proyecto (empleados que ni siquiera se autentican), sin ningún
control de acceso sobre quién puede leerlo o escribirlo — el impacto de cualquier fuga es mayor.

## Análisis STRIDE por componente

### `reservas.router` (endpoints públicos, sin auth)

| STRIDE | Riesgo | Likelihood | Impact |
|---|---|---|---|
| Spoofing | Sin autenticación, cualquiera puede crear una reserva declarando el nombre/legajo de otro empleado | Alta | Medio |
| Tampering | Manipulación de `fecha_inicio`/`fecha_fin` con datetimes naive (sin timezone) para intentar confundir la comparación de solapamiento | Media | Medio |
| Repudiation | Sin log aplicativo de la creación de reservas; el único registro es la fila en `reservas`, con datos no verificados | Media | Medio |
| Information Disclosure | PII (legajo/licencia) en tránsito sin TLS | Media (depende de D-02) | Alto |
| Denial of Service | Sin rate limiting: reservar programáticamente todos los vehículos para todas las fechas futuras bloquea el uso real (DoS de negocio, no solo de infraestructura) | Alta | Alto |
| Elevation of Privilege | N/A — sin niveles de privilegio en este feature | — | — |

### `reservas.service` / `repository.py` (lógica de negocio + `SELECT FOR UPDATE`)

| STRIDE | Riesgo | Likelihood | Impact |
|---|---|---|---|
| Tampering | Inyección SQL si se usara SQL crudo sin parametrizar | Baja (mitigado por diseño: SQLAlchemy ORM, mismo patrón ya validado por SAST en FEAT-001a) | Alto |
| Information Disclosure | La proyección hacia `vehiculos.repository` (TB-C-04) filtra más campos que `patente`/`tipo` si no se respeta `VehiculoPublico` | Baja (ya especificado en la spec) | Medio |
| Denial of Service | El `SELECT FOR UPDATE` es por `vehiculo_id`, no global — un spam de altas sobre un mismo vehículo podría generar contención de lock en ESE vehículo, pero no tira el sistema entero | Baja | Bajo (cubierto en la práctica por la mitigación de rate limiting general) |

### PostgreSQL (TB-C-02) / Frontend público (TB-C-01/03)

| STRIDE | Riesgo | Likelihood | Impact |
|---|---|---|---|
| Information Disclosure | PII en reposo sin cifrado a nivel de columna | Baja (protección de infraestructura, D-02) | Alto |
| Information Disclosure | XSS si algún campo de texto libre (`nombre_empleado`, `destino`) se renderizara sin escapar | Baja (React escapa por defecto, mismo criterio que FEAT-001a) | Alto si ocurriera |

## Riesgos y mitigaciones (F-TM-03)

| # | Riesgo | STRIDE | Likelihood | Impact | Mitigación (se pliega al spec) |
|---|--------|--------|------------|--------|-------------------------------|
| TM-C-01 | 🟠 PII (legajo, licencia) en tránsito sin TLS | Information Disclosure | Media | Alto | Mismo requisito no negociable que TM-01 de FEAT-001a: todo el tráfico detrás de TLS en cualquier entorno que no sea desarrollo local. No se duplica el mecanismo, se referencia la misma precondición de despliegue — impacto mayor acá por tratarse de PII de terceros, no solo de una credencial administrativa. |
| TM-C-02 | 🟠 DoS de negocio: sin rate limiting, se puede monopolizar todo el pool de vehículos | Denial of Service | Alta | Alto | Agregar rate limiting general (mismo `slowapi` ya usado en `vehiculos`) sobre los 3 endpoints de `reservas`, en particular `POST /reservas` (ej. máx. 10 altas por IP por hora) y `GET /reservas/disponibilidad` (límite más laxo, solo lectura). Se pliega como tarea explícita de Block 3. |
| TM-C-03 | 🟡 Tampering vía datetimes naive/aware inconsistentes en la comparación de solapamiento | Tampering | Media | Medio | `ReservaCreate` (Pydantic) debe exigir `fecha_inicio`/`fecha_fin` timezone-aware explícitamente y rechazar valores naive con un error descriptivo, antes de que lleguen a la comparación de solapamiento. Se pliega en Block 2 (`schemas.py`). |
| TM-C-04 | 🟡 Sin log de creación de reservas (repudio, sin forma de investigar abusos) | Repudiation | Media | Medio | `service.py` debe loguear cada `crear_reserva` (nivel INFO): `{operación, vehiculo_id, legajo, resultado, ip_origen, timestamp}` — sin exponerlo vía API. La IP de origen se agrega acá (a diferencia de TM-04 de FEAT-001a) porque, al no haber autenticación, es el único dato adicional de trazabilidad disponible. Se pliega en Block 2/3. |
| TM-C-05 | 🟢 Suplantación de identidad del empleado (spoofing) — sin autenticación, cualquiera declara cualquier legajo | Spoofing | Alta | Medio | **Riesgo aceptado.** Ya documentado y aprobado en el PRD (R-01): trazabilidad básica vía legajo/licencia declarados, validación contra un padrón de empleados como mejora futura fuera de alcance. Confirmado nuevamente por el usuario en esta fase de threat modeling. |
| TM-C-06 | 🟢 PII (legajo, licencia) en reposo sin cifrado a nivel de columna | Information Disclosure | Baja | Alto | **Riesgo aceptado.** Consistente con la postura ya aceptada en FEAT-001a: protección a nivel de infraestructura de la base de datos (D-02, todavía sin definir), no cifrado aplicativo por campo. Confirmado por el usuario en esta fase. |

### Aceptación de riesgos (F-TM-04)

| Riesgo | Quién aceptó | Justificación | Condición de revisión |
|---|---|---|---|
| TM-C-05 (spoofing de identidad) | Usuario del proyecto (owner de FEAT-001c), 2026-08-05 | Ya aceptado en el PRD (R-01) al definir el sub-ticket: el sistema es intencionalmente sin autenticación de empleados en esta iteración; agregar verificación contra un padrón real es una mejora futura fuera de alcance. | Revisar si se agrega autenticación de empleados en una iteración futura, o si el volumen de abuso reportado justifica priorizarlo antes. |
| TM-C-06 (PII en reposo sin cifrado por columna) | Usuario del proyecto (owner de FEAT-001c), 2026-08-05 | Mismo criterio ya aceptado en FEAT-001a: la protección de datos en reposo se resuelve a nivel de infraestructura (cifrado de disco/DB), no con cifrado aplicativo por campo, para no sobre-diseñar antes de que D-02 (infraestructura de despliegue) esté definido. | Revisar cuando D-02 se resuelva — si el entorno elegido no ofrece cifrado en reposo por defecto, reevaluar cifrado aplicativo para `legajo`/`licencia`. |

## Cifrado en tránsito y en reposo (F-TM-07)

- **PII en tránsito** (`nombre_empleado`, `legajo`, `licencia`, en el body de `POST /reservas` y en las respuestas `ReservaOut`): mitigado por TM-C-01 (TLS obligatorio en todo entorno que no sea desarrollo local — misma precondición que TM-01 de FEAT-001a, no se duplica el mecanismo).
- **PII en reposo** (tabla `reservas`, columnas `legajo`/`licencia`): sin cifrado aplicativo por columna — riesgo aceptado explícitamente (TM-C-06), sujeto a que D-02 (infraestructura) resuelva cifrado a nivel de disco/DB.
- **`DATABASE_URL`**: mismo tratamiento ya establecido en FEAT-001a (`.env`, nunca committeado, `sslmode=require` a decidir con D-02) — sin cambios, no se repite acá.

## Conclusión

```
┌─────────────────────────────────────────────────────────┐
│  /daw-threat-modeling FEAT-001c — PASSED                 │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Attack surfaces identified: 4 (router público, service/ │
│    repository con lock, PostgreSQL, frontend público)     │
│  Trust boundaries declared: 4 (TB-C-01 a TB-C-04)          │
│                                                          │
│  Risks:                                                  │
│    🟠 HIGH: TM-C-01 PII sin TLS en tránsito —             │
│       Mitigation: TLS obligatorio (misma precondición     │
│       que FEAT-001a)                                       │
│    🟠 HIGH: TM-C-02 DoS de negocio sin rate limiting —     │
│       Mitigation: rate limiting general (slowapi) en       │
│       los 3 endpoints, Block 3                              │
│    🟡 MEDIUM: TM-C-03 tampering de fechas naive/aware —    │
│       Mitigation: exigir timezone-aware en schemas.py      │
│    🟡 MEDIUM: TM-C-04 sin log de creación de reservas —    │
│       Mitigation: logging con IP de origen, Block 2/3       │
│    🟢 LOW (aceptado): TM-C-05 spoofing de identidad —       │
│       ya aprobado en PRD R-01, reconfirmado acá             │
│    🟢 LOW (aceptado): TM-C-06 PII en reposo sin cifrado     │
│       por columna — sujeto a D-02                            │
│                                                          │
│  Mitigations to fold into the spec:                       │
│    1. TLS obligatorio (referencia a la precondición de     │
│       FEAT-001a, sin duplicar código) — Block 3             │
│    2. Rate limiting general con slowapi en los 3            │
│       endpoints de reservas — Block 3                       │
│    3. Validación timezone-aware de fecha_inicio/fecha_fin  │
│       en ReservaCreate — Block 2                             │
│    4. Logging de creación de reserva con IP de origen —     │
│       Block 2/3                                              │
│                                                          │
│  ─────────────────────────────────────────────────────   │
│  Risks: C:0 H:2 M:2 L:2 (los 2 L aceptados con los 3        │
│  campos de F-TM-04 completos)                                │
│  Report: docs/daw/security/threat-FEAT-001c.md              │
└─────────────────────────────────────────────────────────┘
```
