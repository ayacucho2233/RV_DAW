# Threat Model — FEAT-001e: Integración con el ciclo de vida del vehículo

| Campo | Valor |
|---|---|
| Ticket | FEAT-001e |
| Fase | PLAN |
| Spec | `docs/daw/specs/spec-FEAT-001e.md` |
| Fecha | 2026-08-08 |

## Componentes nuevos/modificados

1. `reservas.repository.existe_activa_para_vehiculo(db, vehiculo_id)` — nueva función interna, solo
   lectura, sin input directo de usuario (recibe `vehiculo_id` ya validado por FastAPI como `int` en
   el path del endpoint).
2. `vehiculos.service.dar_de_baja_temporal`/`dar_de_baja_definitiva` — nueva rama de validación
   (lock + chequeo de reservas activas) sobre un flujo ya protegido por `verificar_admin`.
3. `vehiculos.exceptions.VehiculoConReservasActivasError` — nuevo mensaje de dominio expuesto en el
   body de la respuesta 409.
4. `VehiculosAdminPage.jsx` — deja de reemplazar el `detail` del backend por un texto genérico para
   los 409 de esta página.

## Trust boundaries (F-TM-02)

Sin boundaries nuevas. Los 4 componentes viven del lado servidor (backend) o son un cambio de
presentación en un cliente ya autenticado (frontend admin, tras `verificar_admin`/HTTP Basic — sin
cambios en esta pieza). La nueva dependencia cruzada `vehiculos.service → reservas.repository` es
intra-proceso, mismo nivel de confianza, misma sesión de base de datos — no cruza ninguna frontera
de confianza existente (mismo criterio que la dirección opuesta ya establecida en FEAT-001c/d).

## Análisis STRIDE por componente

### `vehiculos.service.dar_de_baja_temporal`/`dar_de_baja_definitiva` (con la nueva validación)

| STRIDE | Análisis | Likelihood | Impact |
|---|---|---|---|
| Spoofing | N/A — sin cambios en `verificar_admin`, mismo mecanismo de auth que ya protege estos 2 endpoints. | — | — |
| Tampering | N/A — el cliente no puede influir en el resultado del chequeo (`existe_activa_para_vehiculo` lee directamente de `reservas`, sin parámetro de request adicional). | — | — |
| Repudiation | El rechazo por `VehiculoConReservasActivasError` NO se loguea (mismo patrón que el rechazo existente por `TransicionEstadoInvalidaError`/`VehiculoNoEncontradoError` — `_log_operacion` de `vehiculos` solo registra el camino de éxito, a diferencia de `_log_operacion` de `reservas` que sí registra rechazos). Ver TM-E-01. | Baja | Bajo |
| Information Disclosure | El mensaje de `VehiculoConReservasActivasError` expone `vehiculo_id` (ya conocido por quien hace el request) y el hecho booleano "tiene reservas activas" — sin PII, sin `legajo`/`nombre_empleado`/`licencia`. Ver TM-E-02 (frontend). | Baja | Bajo |
| Denial of Service | El nuevo `SELECT EXISTS` está protegido por el mismo `verificar_admin` (HTTP Basic + rate limiting ya existente en `app.core.security`) que ya limita estos 2 endpoints — sin nueva superficie. | Baja | Bajo |
| Elevation of Privilege | N/A — sigue exigiendo admin, sin cambio de nivel de privilegio. | — | — |

### `VehiculosAdminPage.jsx` — mensaje 409 ya no enmascarado

| STRIDE | Análisis | Likelihood | Impact |
|---|---|---|---|
| Information Disclosure | Antes: mensaje genérico fijo para CUALQUIER 409. Después: se muestra `error.detail` tal como lo devuelve el backend. Riesgo: si en el futuro un nuevo tipo de excepción se mapea a 409 sin que su mensaje esté pensado para mostrarse al usuario final, el frontend lo expondría directamente. Mitigación: **el patrón ya existente en `router.py`/`exceptions.py`** garantiza que `_a_http` solo usa `str(exc)` de excepciones de dominio propias (`VehiculoDomainError` y subclases) — nunca una excepción cruda de Python ni un stack trace; el mismo control ya protege a `ReservasListado.jsx`/`reservasApi.js`, que usan exactamente este patrón sin `MENSAJES_ERROR` para 409. Ver TM-E-02. | Baja | Bajo |

## Riesgos y mitigaciones (F-TM-03)

| # | Riesgo | STRIDE | Likelihood | Impact | Mitigación |
|---|---|---|---|---|---|
| TM-E-01 | 🟢 El rechazo de una baja por `VehiculoConReservasActivasError` no queda logueado — sin rastro para investigar intentos repetidos de baja indebida. | Repudiation | Baja | Bajo | **Riesgo aceptado.** Mismo patrón ya presente en `vehiculos.service` desde FEAT-001a (ningún rechazo de baja se loguea hoy, solo los éxitos) — extender el logging de rechazos a TODOS los rechazos de `vehiculos` es una mejora legítima pero fuera del alcance de este ticket (tocaría los 3 métodos de baja/reactivar existentes, no solo el nuevo). Aceptado por el usuario del proyecto, 2026-08-08. A revisar: si se agrega auditoría administrativa como feature propia, incluir ahí el logging simétrico de `vehiculos` (éxito y rechazo, como ya hace `reservas`). |
| TM-E-02 | 🟢 El frontend deja de enmascarar el `detail` del backend para 409 en `VehiculosAdminPage.jsx`, exponiendo directamente cualquier mensaje de excepción de dominio mapeada a 409 en el futuro. | Information Disclosure | Baja | Bajo | Mitigado por diseño: `_a_http`/`_MAPEO_ERRORES_HTTP` en `router.py` solo traducen excepciones de `VehiculoDomainError` (nunca excepciones crudas), y cada subclase ya redacta su mensaje pensando en mostrarse al usuario (confirmado para las 3 excepciones que hoy mapean a 409: `TransicionEstadoInvalidaError`, `PatenteYaExisteError` — no aplica a esta página —, `VehiculoConReservasActivasError`). Mismo patrón ya en producción sin incidentes en `reservasApi.js`/`ReservasListado.jsx` desde FEAT-001c/d. |

### Aceptación de riesgos (F-TM-04)

| Riesgo | Quién acepta | Justificación | Cuándo revisar |
|---|---|---|---|
| TM-E-01 (rechazo de baja sin log) | Usuario del proyecto (owner de FEAT-001e), 2026-08-08 | Extender a logging simétrico en `vehiculos` (éxito+rechazo, como ya hace `reservas`) es una mejora consistente pero de alcance mayor al de este ticket — tocaría 3 métodos existentes sin relación directa con FR-01/FR-02. | Si se agrega una feature de auditoría administrativa, o si se reporta un incidente de bajas indebidas repetidas que requiera investigación retroactiva. |

## Datos sensibles (F-TM-05)

Sin datos sensibles nuevos. `VehiculoConReservasActivasError` expone solo `vehiculo_id` (identificador interno, ya conocido por el caller) — ningún campo de PII (`legajo`, `nombre_empleado`, `licencia`, `destino`) aparece en ningún mensaje de error de este ticket.

## Cifrado en tránsito y en reposo (F-TM-07)

Sin cambios — hereda las mismas precondiciones ya establecidas (TLS obligatorio en despliegue, TM-C-01/TM-D-05; PII en reposo sin cifrado adicional, riesgo aceptado TM-C-06/TM-D-06). Este ticket no introduce ni maneja PII nueva.

## Resumen

```
┌─────────────────────────────────────────────────────────┐
│  /daw-threat-modeling — PASSED                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Attack surfaces identified: 2 (validación de baja con   │
│    reservas activas; mensaje 409 sin enmascarar en el     │
│    panel admin)                                           │
│  Trust boundaries declared: 0 nuevas (reusa las de        │
│    FEAT-001a/c/d)                                          │
│                                                          │
│  Risks:                                                  │
│    🟢 LOW (aceptado): TM-E-01 rechazo de baja sin log —    │
│       mismo patrón ya existente en vehiculos desde         │
│       FEAT-001a, fuera de alcance extenderlo acá            │
│    🟢 LOW: TM-E-02 mensaje 409 sin enmascarar — mitigado    │
│       por diseño (solo excepciones de dominio propias      │
│       llegan a `detail`, mismo patrón ya en producción      │
│       en reservas)                                         │
│                                                          │
│  Mitigations to fold into the spec: ninguna adicional —     │
│    ambos riesgos son LOW y ya están mitigados por el        │
│    diseño existente o aceptados explícitamente               │
│                                                          │
│  ─────────────────────────────────────────────────────   │
│  Risks: C:0 H:0 M:0 L:2                                   │
│  Report: docs/daw/security/threat-FEAT-001e.md             │
└─────────────────────────────────────────────────────────┘
```
