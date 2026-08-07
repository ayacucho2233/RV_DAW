# Threat Model — FEAT-001d: Listado, filtros y cancelación de reservas

| Field | Value |
|-------|-------|
| Ticket | FEAT-001d |
| Date | 2026-08-07 |
| Basis | STRIDE (Microsoft), OWASP Threat Modeling, OWASP ASVS, ISO 27001 |

## Arquitectura analizada

```
Navegador (vista pública)              Internet/red              FastAPI backend                    PostgreSQL
  ReservasListado.jsx                --JSON, SIN auth-->    router.py (reservas)  --SQLAlchemy-->     tabla reservas
  reservasApi.js (sin Authorization)                             |                                       ^
                                                                  v                                       |
                                                          service.py (listar_reservas,               --lee--+
                                                          cancelar_reserva)                                  |
                                                                 |                                          |
                                                                 v                                    vehiculos.repository
                                                          repository.py (reservas: listar_todas,      (import de solo lectura,
                                                          obtener_por_id, guardar)                     proyección patente/tipo)
```

Componentes cubiertos: `backend/app/features/reservas/{router,service,repository,schemas,exceptions}.py`
(modificados, sin cambios de modelo/migración), y `frontend/src/features/reservas/ReservasListado.jsx`
+ `reservasApi.js` + `App.jsx` (nuevos/modificados). Reusa los trust boundaries y la clasificación de
datos ya establecidos en `docs/daw/security/threat-FEAT-001c.md` — no se duplican, se referencian.

## Trust boundaries (F-TM-02)

Mismos boundaries que FEAT-001c (TB-C-01 a TB-C-04, ver `threat-FEAT-001c.md`): los 2 endpoints
nuevos cruzan el mismo boundary Internet ↔ FastAPI sin control de acceso (TB-C-01/03), por el mismo
diseño explícito del PRD ("sin restricción de visibilidad" para el listado; "sin autenticación real"
para la cancelación). No se declara ningún boundary nuevo.

## Datos sensibles (F-TM-05)

Misma clasificación que FEAT-001c (`nombre_empleado`/`legajo` PII, `licencia` PII sensible). Lo
nuevo de este ticket es la **superficie de exposición**: `GET /reservas` es el primer endpoint que
devuelve datos de reservas de **terceros** (no solo la propia, recién creada) a cualquier cliente sin
autenticación — ver TM-D-01 abajo.

## Análisis STRIDE por componente

### `reservas.router` — `GET /reservas` (listado público)

| STRIDE | Riesgo | Likelihood | Impact |
|---|---|---|---|
| Information Disclosure | Si el listado público expusiera `legajo`/`licencia` de cada reserva, cualquiera podría leer el legajo de otro empleado ahí mismo — ver TM-D-01 | Alta (endpoint público, sin fricción) | Crítico |
| Denial of Service | Sin rate limiting propio, un scraping del listado completo en loop degrada el servicio para el resto | Alta | Medio |
| Repudiation | N/A — es un endpoint de solo lectura, no genera una acción que negar | — | — |
| Elevation of Privilege | N/A — sin niveles de privilegio en este feature | — | — |

### `reservas.router` — `PATCH /reservas/{id}/cancelar`

| STRIDE | Riesgo | Likelihood | Impact |
|---|---|---|---|
| Spoofing | Cancelar la reserva de otro empleado conociendo/adivinando su `legajo` | Media (requiere conocer el legajo por algún canal externo a la app) | Medio |
| Tampering | `id` de reserva secuencial y adivinable (IDOR clásico) — mitigado en parte porque además requiere el `legajo` correcto | Media | Medio |
| Repudiation | Sin log de la cancelación, no hay forma de investigar abusos o disputas ("mi reserva desapareció") | Media | Medio |
| Information Disclosure | El código de error (403 vs. 404) permite inferir si un `id` de reserva existe probando legajos al azar | Baja | Bajo (ya aceptado como R-01 del PRD, mismo criterio que FEAT-001c) |
| Denial of Service | Sin rate limiting propio, cancelación masiva por fuerza bruta de `id`+legajos filtrados de otra fuente | Media | Alto (si se combina con TM-D-01 sin mitigar) |

## Riesgos y mitigaciones (F-TM-03)

| # | Riesgo | STRIDE | Likelihood | Impact | Mitigación (se pliega al spec) |
|---|--------|--------|------------|--------|-------------------------------|
| TM-D-01 | 🔴 **El listado público (`GET /reservas`) expone `legajo`/`licencia` de todas las reservas, convirtiéndose en un oráculo que anula la protección de FR-04/AC-06**: cualquiera podría leer el legajo real de otra reserva en el propio listado y usarlo de inmediato en `PATCH /reservas/{id}/cancelar` para cancelarla, sin necesidad de "conocer" el legajo por ningún canal externo. Esto degrada el riesgo ya aceptado en el PRD (R-01, spoofing por legajo conocido/adivinado) de "requiere información externa" a "trivialmente automatizable dentro de la propia app". | Information Disclosure | Alta | Crítico | `ReservaListItem` (schema de respuesta de `GET /reservas`) **no incluye `legajo` ni `licencia`** — solo `id, vehiculo_id, nombre_empleado, fecha_inicio, fecha_fin, destino, estado, patente, tipo, created_at, updated_at`. El legajo se sigue **proveyendo** por el cliente al cancelar (`CancelarReservaRequest.legajo`), nunca se **lee** desde el listado. Se pliega en Block 1 (`schemas.py`). |
| TM-D-02 | 🟠 DoS: los 2 endpoints nuevos, sin rate limiting propio, permiten scraping del listado completo o fuerza bruta de cancelaciones | Denial of Service | Alta | Alto | Mismo mecanismo `_aplicar_rate_limit` ya usado en los 3 endpoints de FEAT-001c (TM-C-02), con **clave de contador independiente por endpoint** (`"reservas-listado"` 60/min, `"reservas-cancelar"` 10/hora) — un abuso de un endpoint no debe descontar cupo de otro. Se pliega en Block 2. |
| TM-D-03 | 🟡 Sin log de cancelación (repudio, sin forma de investigar abusos o disputas) | Repudiation | Media | Medio | `service.py` loguea cada `cancelar_reserva` (nivel INFO) reusando `_log_operacion` ya existente, parametrizada: `{operación="cancelar_reserva", vehiculo_id, legajo, resultado, ip_origen, timestamp}` — mismo criterio de PII que `crear_reserva` (nunca `nombre_empleado`/`licencia`). Se pliega en Block 1. |
| TM-D-04 | 🟢 Suplantación de identidad del empleado (spoofing) — sin autenticación real, cancelar con un legajo correcto pero no propio | Spoofing | Media (tras TM-D-01, ya no es trivialmente automatizable desde la app, pero sigue siendo posible por otros canales: preguntar a un compañero, organigrama interno) | Medio | **Riesgo aceptado.** Mismo riesgo ya aprobado en el PRD (R-01, idéntico criterio que FEAT-001c): validación contra un padrón de empleados queda fuera de alcance de esta iteración. Reconfirmado por el usuario en esta fase de threat modeling, con TM-D-01 como mitigación de la vía de escalamiento más grave. |
| TM-D-05 | 🟢 PII (`legajo` en el body de `PATCH .../cancelar`, `nombre_empleado`/`destino` en las respuestas) en tránsito sin TLS | Information Disclosure | Media (depende de D-03) | Alto | Misma precondición ya establecida (TM-C-01/TM-01): TLS obligatorio en todo entorno que no sea desarrollo local. No se duplica el mecanismo. |
| TM-D-06 | 🟢 PII en reposo sin cifrado a nivel de columna | Information Disclosure | Baja | Alto | **Riesgo aceptado**, mismo criterio ya aprobado en FEAT-001a/FEAT-001c (TM-C-06): protección a nivel de infraestructura, sujeta a D-03 (infraestructura de despliegue, todavía sin definir). No se re-decide acá, se hereda. |

### Aceptación de riesgos (F-TM-04)

| Riesgo | Quién aceptó | Justificación | Condición de revisión |
|---|---|---|---|
| TM-D-04 (spoofing de identidad al cancelar) | Usuario del proyecto (owner de FEAT-001d), 2026-08-07 | Ya aceptado en el PRD (R-01) como riesgo conocido de no tener autenticación real de empleados; TM-D-01 elimina la vía de escalamiento más grave (leer el legajo desde la propia app), dejando solo canales externos a la app como vector residual. | Revisar si se agrega autenticación de empleados en una iteración futura, o si el volumen de cancelaciones indebidas reportado justifica priorizarlo antes. |
| TM-D-06 (PII en reposo sin cifrado por columna) | Usuario del proyecto (owner de FEAT-001d), 2026-08-07 | Hereda la aceptación ya formalizada en FEAT-001c (TM-C-06): la protección de datos en reposo se resuelve a nivel de infraestructura, no con cifrado aplicativo por campo, para no sobre-diseñar antes de que la infraestructura de despliegue esté definida. | Revisar cuando la infraestructura de despliegue se resuelva — si el entorno elegido no ofrece cifrado en reposo por defecto, reevaluar cifrado aplicativo para `legajo`/`licencia`. |

## Cifrado en tránsito y en reposo (F-TM-07)

- **PII en tránsito**: mitigado por TM-D-05 (misma precondición TLS ya establecida, no se duplica).
- **PII en reposo**: sin cifrado aplicativo por columna — riesgo aceptado explícitamente (TM-D-06),
  hereda la postura de FEAT-001a/FEAT-001c.
- Sin cambios a `DATABASE_URL` ni a la configuración de conexión — no se repite acá.

## Conclusión

```
┌─────────────────────────────────────────────────────────┐
│  /daw-threat-modeling FEAT-001d — MITIGATION REQUIRED →  │
│  PASSED tras plegar TM-D-01 al spec                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Attack surfaces identified: 2 (GET /reservas público,   │
│    PATCH /reservas/{id}/cancelar público)                 │
│  Trust boundaries declared: 0 nuevos (reusa TB-C-01 a     │
│    TB-C-04 de FEAT-001c)                                   │
│                                                          │
│  Risks:                                                  │
│    🔴 CRITICAL: TM-D-01 el listado expone legajo/licencia │
│       y anula FR-04/AC-06 — Mitigation: ReservaListItem   │
│       nunca incluye legajo/licencia (Block 1)              │
│    🟠 HIGH: TM-D-02 DoS sin rate limiting propio —         │
│       Mitigation: claves de contador independientes,       │
│       Block 2                                               │
│    🟡 MEDIUM: TM-D-03 sin log de cancelación —              │
│       Mitigation: _log_operacion parametrizada, Block 1     │
│    🟢 LOW (aceptado): TM-D-04 spoofing de identidad —       │
│       ya aprobado en PRD R-01, riesgo residual reducido      │
│       por TM-D-01                                            │
│    🟢 LOW (aceptado): TM-D-05/TM-D-06 TLS y cifrado en       │
│       reposo — heredan precondiciones ya establecidas         │
│                                                          │
│  Mitigations to fold into the spec:                       │
│    1. ReservaListItem sin legajo/licencia — Block 1        │
│    2. Claves de rate limit independientes por endpoint —   │
│       Block 2                                                │
│    3. Logging de cancelación con IP de origen, sin PII —    │
│       Block 1                                                │
│                                                          │
│  ─────────────────────────────────────────────────────   │
│  Risks: C:1 H:1 M:1 L:2 (el C ya mitigado en el spec       │
│  antes de este reporte; los 2 L aceptados con los 3         │
│  campos de F-TM-04 completos)                                │
│  Report: docs/daw/security/threat-FEAT-001d.md              │
└─────────────────────────────────────────────────────────┘
```
