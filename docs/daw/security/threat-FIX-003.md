# Threat Model — FIX-003

| Campo | Valor |
|-------|-------|
| Ticket | FIX-003 |
| Tier | FIX |
| Fecha | 2026-08-17 |

## Alcance del diseño

Configuración de linters (`backend/ruff.toml` nuevo, `frontend/eslint.config.js` con una regla
desactivada) + correcciones mecánicas de estilo en 14 archivos (imports sin ordenar, `dict()` →
literal, `with` anidados combinados, `noqa` obsoletos removidos, `check=False` explícito en
`subprocess.run`, una rama de código muerto eliminada en `client.js`, variables sin usar removidas
en tests). **Ningún cambio de lógica de negocio, de superficie de API, ni de flujo de datos.**

## Componentes y trust boundaries

No hay componentes nuevos ni boundaries nuevos: el fix no agrega inputs de usuario, no toca
autenticación/autorización, no integra servicios externos y no cambia ningún flujo de datos
existente. Todos los archivos tocados son: (a) config de tooling que no se ejecuta en producción,
(b) tests, (c) reordenamiento de imports/limpieza cosmética en `app/features/reservas/models.py` y
`alembic/`, (d) eliminación de una rama de código en `client.js` que nunca se ejecuta en un
navegador real (el `typeof btoa === "function"` siempre es `true` ahí).

## STRIDE por componente

| Componente | S | T | R | I | D | E |
|---|---|---|---|---|---|---|
| `backend/ruff.toml` (config) | — | — | — | — | — | — |
| Tests backend (mecánico) | — | — | — | — | — | — |
| `app/features/reservas/models.py` (solo reorden de imports) | — | — | — | — | — | — |
| `alembic/env.py` + migraciones (solo reorden de imports) | — | — | — | — | — | — |
| `frontend/src/api/client.js` (elimina rama muerta) | — | — | — | — | — | — |
| `frontend/eslint.config.js` (desactiva 1 regla) | — | — | — | — | — | — |
| Tests frontend (variables sin usar) | — | — | — | — | — | — |

Ninguna categoría STRIDE aplica: no hay superficie de ataque nueva en ningún componente tocado.

## Datos sensibles

No se clasifican datos sensibles nuevos. `client.js` mantiene exactamente el mismo comportamiento
de autenticación (Basic Auth vía `btoa`) que ya existía — solo se elimina una rama de fallback
muerta que nunca se ejecuta.

## Riesgos

Ninguno identificado.

## Veredicto

**PASSED** — 0 riesgos CRITICAL/HIGH/MEDIUM/LOW. `gates.threat = true`.
