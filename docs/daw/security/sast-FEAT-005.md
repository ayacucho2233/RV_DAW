# SAST — FEAT-005: Estado "Caducada" para reservas vencidas automáticamente

| Campo | Valor |
|---|---|
| Ticket | FEAT-005 |
| Tier | FEATURE |
| Fecha | 2026-08-18 |
| Alcance | Diff completo `main...feat/FEAT-005-estado-caducada` (17 archivos) |
| Threat model | `docs/daw/security/threat-FEAT-005.md` (PLAN): 0 CRITICAL/HIGH, 2 MEDIUM mitigados en spec (M-01, M-02), 2 LOW (1 mitigado, 1 aceptado) |

## Secrets (F-SAST-01)
✅ Sin credenciales, API keys ni connection strings hardcodeadas en el diff. `.env` confirmado en `.gitignore`.

## Injection (F-SAST-02/03/05)
✅ SQL: `repository.caducar_vencidas` usa SQLAlchemy Core `update(Reserva).where(...)` completamente parametrizado, sin concatenación de strings ni input de usuario en la query (el endpoint no recibe body ni params). La migración `0004_estado_caducada.py` usa únicamente `op.drop_constraint`/`op.create_check_constraint`/`op.create_index` con valores estáticos, sin SQL crudo con input externo.
✅ Command injection: N/A, no hay llamadas a exec/spawn/system en el diff.
✅ Path traversal: N/A, no hay manejo de paths con input de usuario.

## XSS y funciones inseguras (F-SAST-04/06/08)
✅ Sin `innerHTML`/`dangerouslySetInnerHTML` en el diff de frontend.
✅ Sin `eval()`/deserialización insegura ni criptografía débil introducida.

## Resto de categorías obligatorias (F-SAST-07/09/10/11/12/14/15)
✅ SSRF: N/A, sin llamadas salientes a URLs derivadas de input de usuario.
✅ Debug mode: sin cambios de configuración de entorno.
✅ Logging de datos sensibles: `service.caducar_reservas_vencidas` loguea `operacion`, `count`, `ip_origen`, `timestamp` — explícitamente sin `legajo`/`vehiculo_id`/`nombre_empleado` (mitigación M-02 del threat model, verificado además por `test_caducar_reservas_vencidas_loguea_operacion`).
✅ Unrestricted upload: N/A.
✅ CSRF: el endpoint es público y sin estado de sesión (mismo diseño ya aceptado para todo `/reservas`, documentado en el PRD como fuera de scope de autenticación — FEAT-001a lo cubre en otro feature). No introduce una superficie nueva distinta a los 6 endpoints preexistentes del mismo router.
✅ Validación de input incompleta: el endpoint no recibe body ni query params — nada que validar.
✅ Manejo de errores que filtra internals: el único error posible es el `429` ya existente del mecanismo de rate limit compartido (`_DEMASIADAS_REQUESTS`), sin nuevas rutas de excepción que expongan stack traces.

## Dependencias (F-SAST-13/16)
✅ `npm audit --production` (frontend): 0 vulnerabilidades.
✅ `pip-audit -r requirements.txt` (backend): sin CVEs conocidos.
Ninguna dependencia nueva fue agregada por este ticket.

## Suppressions
Ninguna. No hubo hallazgos Medium que requieran documentación de supresión.

---

**Total: 0 vulnerabilidades (0 crítico, 0 alto, 0 medio sin mitigar)**
**Resultado: PASSED**
