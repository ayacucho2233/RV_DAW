# Fix FIX-002: Documentar FIX-001 en el CHANGELOG

- **Bug**: FIX-001 (corrección de `test_config_falla_sin_database_url`) se cerró sin entrada en `CHANGELOG.md` porque el guard de LOC de QUICK-FIX bloqueó esa escritura en RELEASE (la rama ya estaba en 14 LOC, sobre el límite de 10) y RELEASE no permite abandonar el ticket para reclasificar.
- **Change**: `CHANGELOG.md` — agregar una entrada bajo `## [Unreleased]` / `### Fixed` describiendo el fix de FIX-001, siguiendo el mismo formato que las entradas existentes de FEAT-001/FEAT-002.
- **Regression test**: no aplica — cambio de documentación puro, sin código ejecutable.
- **Risk**: none — solo agrega texto a `CHANGELOG.md`, no toca código ni comportamiento de la app.
