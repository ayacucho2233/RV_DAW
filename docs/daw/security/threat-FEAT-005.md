# Threat Model FEAT-005: Estado "Caducada" para reservas vencidas automáticamente

| Field | Value |
|-------|-------|
| Ticket | FEAT-005 |
| Date | 2026-08-18 |
| Design reviewed | `POST /reservas/caducar-vencidas` (nuevo endpoint público) + `EstadoReserva.caducada` (nuevo valor de enum) + migración de CHECK constraint + trigger desde `App.jsx` al montar |

## Componentes y superficies de ataque

1. **`POST /reservas/caducar-vencidas`** (nuevo, público, sin auth, sin body) — dispara un `UPDATE`
   masivo sobre `reservas`. Llamado automáticamente por el frontend en cada carga de página
   (`App.jsx`, `useEffect` al montar), pero el endpoint en sí es alcanzable por cualquier cliente
   HTTP, no solo por el frontend.
2. **`repository.caducar_vencidas`** (nuevo) — `UPDATE reservas SET estado='caducada' WHERE
   estado='activa' AND fecha_fin < :ahora`, vía SQLAlchemy Core `update()` (parametrizado, sin SQL
   crudo).
3. **Nueva migración Alembic** — reemplaza el CHECK constraint `estado_reserva` (2 valores → 3), sin
   reescribir filas existentes.
4. **`EstadoReserva.caducada`** — nuevo valor expuesto en `ReservaOut`/`ReservaListItem`, sin campos
   nuevos ni PII adicional.

## Trust boundaries

- **Cliente anónimo → `POST /reservas/caducar-vencidas`**: mismo límite ya aceptado para los 6
  endpoints existentes de `/reservas` (público por diseño del PRD original, FEAT-001c/d). No cruza
  ningún límite nuevo — sigue del lado "sin autenticar" del feature, igual que sus hermanos.
- **Aplicación → Base de datos**: sin cambios — el `UPDATE` va parametrizado vía SQLAlchemy, sin
  concatenación de strings.
- **`caducar_vencidas` (bulk) ↔ `cancelar_reserva` (por id)**: ambos escriben sobre la misma tabla
  sin coordinarse entre sí — es el único límite nuevo de facto que introduce este diseño (ver riesgo
  de carrera abajo).

## Análisis STRIDE

### `POST /reservas/caducar-vencidas`

| Categoría | Evaluación |
|---|---|
| Spoofing | N/A — público por diseño, mismo criterio que los 6 endpoints hermanos de este router. |
| Tampering | Bajo. Sin input del cliente (sin body, sin params) — no hay superficie de inyección. El único efecto posible es adelantar una transición que de todos modos iba a ocurrir (una reserva vencida vencida está). |
| Repudiation | 🟡 **MEDIO** (ver riesgo abajo) — a diferencia de `crear_reserva`/`cancelar_reserva`, el diseño original no logueaba esta operación. |
| Information Disclosure | Bajo. La respuesta es `{"caducadas": N}` — un conteo, sin PII ni detalle por reserva. |
| Denial of Service | 🟡 **MEDIO** (ver riesgo abajo) — el `WHERE estado='activa' AND fecha_fin < ahora` no tiene índice que lo cubra; con la tabla creciendo, cada llamada (hasta 60/min por IP) puede degenerar en un full scan. |
| Elevation of Privilege | N/A — no hay ningún límite de autorización que cruzar; el endpoint no toca nada que `verificar_admin` proteja. |

### Carrera `cancelar_reserva` vs. `caducar_vencidas`

| Categoría | Evaluación |
|---|---|
| Tampering | 🟢 **BAJO** (riesgo aceptado, ver tabla de riesgos) — `cancelar_reserva` lee sin lock (`obtener_por_id`) y escribe incondicionalmente (`guardar`); si `caducar_vencidas` corre en el medio sobre la misma fila, la cancelación puede pisar `caducada` con `cancelada`. |

## Riesgos clasificados

| Riesgo | STRIDE | Likelihood | Impact | Mitigación |
|---|---|---|---|---|
| Full table scan en cada llamada a `caducar_vencidas` (no hay índice que cubra `estado + fecha_fin`) — con tabla grande, 60 llamadas/min por IP pueden degradar el servicio | Denial of Service | Media | Medio | Agregar índice compuesto `ix_reservas_estado_fecha_fin` sobre `(estado, fecha_fin)` en la misma migración que agrega el valor `caducada` — mandato de AGENTS.md ("no hacer consultas de disponibilidad sin índice en las columnas de fecha"). |
| Sin registro de auditoría de la operación masiva (a diferencia de `crear_reserva`/`cancelar_reserva`, que sí loguean vía `_log_operacion`) | Repudiation | — | Bajo | Agregar una línea de log en `service.caducar_reservas_vencidas` (`operacion=caducar_vencidas resultado=ok count=N ip_origen=X timestamp=Y`), sin legajo/vehiculo_id (no aplica a una operación masiva) — mismo criterio de mínima PII en logs ya documentado en `service.py`. |
| Abuso del endpoint por un cliente que no es el frontend (llamadas repetidas para forzar carga en la base) | Denial of Service | Baja | Bajo | Rate limit propio, 60/min por IP, balde independiente `"reservas-caducar-vencidas"` — mismo mecanismo (`_aplicar_rate_limit`) ya validado en los 6 endpoints existentes (TM-C-02 original). |
| **Carrera `cancelar_reserva` vs. `caducar_vencidas`**: una cancelación concurrente con el sweep puede pisar `caducada` con `cancelada`, dejando un registro que dice "el empleado la canceló" cuando en realidad ya había vencido | Tampering | Baja | Bajo | **Riesgo aceptado** (ver abajo) — no se modifica `cancelar_reserva` en este ticket. |

### Riesgo aceptado: carrera `cancelar_reserva` vs. `caducar_vencidas`

- **Quién lo acepta:** el usuario del proyecto, en la fase PLAN de FEAT-005 (confirmado
  explícitamente al presentarle esta alternativa frente a blindar `cancelar_reserva` con un `UPDATE`
  condicional).
- **Justificación:** la ventana de carrera es angosta (requiere que ambas operaciones caigan sobre la
  misma fila casi en el mismo instante, justo en el límite de su vencimiento) y el impacto de negocio
  es bajo — en ambos casos la reserva queda terminada; lo único que se pierde es la precisión de *por
  qué* terminó. Cerrarla de raíz requeriría cambiar `repository.guardar` (compartido con otros paths
  de escritura) a un `UPDATE` condicional, lo cual excede el alcance de este ticket.
- **Condición de revisión:** si una futura funcionalidad depende de que la distinción
  `cancelada`/`caducada` sea exacta para algo consecuente (auditoría formal, facturación, disputas
  legales), o si telemetría en producción muestra que esta carrera ocurre con una frecuencia no
  despreciable, se revisita con un `UPDATE` condicional (`WHERE estado = 'activa'`, verificando
  `rowcount`) en `cancelar_reserva`.

## Datos sensibles

Ningún componente de este diseño introduce PII nueva. El endpoint no recibe ni devuelve
`nombre_empleado`/`legajo`/`licencia` — solo un conteo agregado. El log nuevo (`caducar_vencidas`)
sigue el mismo criterio ya establecido en `service.py`: nunca `nombre_empleado` ni `licencia`, y en
este caso tampoco `legajo` (no aplica a una operación masiva).
