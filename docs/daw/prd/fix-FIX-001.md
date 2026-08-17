# Fix FIX-001: Corregir test_config_falla_sin_database_url

- **Bug**: `test_config_falla_sin_database_url` no detecta la ausencia de `DATABASE_URL` porque `Settings` (pydantic-settings, `model_config = SettingsConfigDict(env_file=".env")`) sigue leyendo el valor desde `backend/.env` aunque el test lo borre de `os.environ` con `monkeypatch.delenv`, así que `Settings()` nunca lanza `ValidationError` y el test falla con "DID NOT RAISE ValidationError".
- **Change**: `backend/tests/test_config.py:32-41` — en `test_config_falla_sin_database_url`, forzar que la recarga de `Settings` ignore `env_file` (p. ej. instanciando `Settings(_env_file=None)` en vez de depender solo de `_reload_config()`), para que la ausencia de la variable en el entorno real quede efectivamente simulada.
- **Regression test**: `test_config_falla_sin_database_url` (ya existe en `backend/tests/test_config.py`; falla hoy con "DID NOT RAISE ValidationError" y debe pasar tras el fix).
- **Risk**: none — el cambio queda acotado al archivo de test; no modifica `app/core/config.py` ni el comportamiento de arranque de la app.
