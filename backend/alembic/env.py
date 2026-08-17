import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.features.reservas.models

# Se importa por su efecto de registrar cada modelo contra `Base.metadata`.
# Cuando se agreguen más features, sus modelos se importan acá también para
# que `target_metadata` los incluya.
import app.features.vehiculos.models  # noqa: F401
from alembic import context
from app.core.database import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# `DATABASE_URL` se lee del entorno, nunca hardcodeada en alembic.ini
# (ver AGENTS.md: nunca hardcodear credenciales/configuración sensible).
# Nota: además de esta variable, correr Alembic requiere que las otras 3
# variables de `Settings` (ADMIN_USERNAME, ADMIN_PASSWORD_HASH,
# FRONTEND_ORIGIN) también estén seteadas, porque `Base` vive en
# `app.core.database`, que importa `app.core.config` — y esa importación
# instancia `Settings()` completo. Es el costo de tener un único `Base`
# compartido entre features (ver decisión documentada en database.py).
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL no está seteada en el entorno. "
        "Alembic la necesita para poder migrar la base de datos."
    )
config.set_main_option("sqlalchemy.url", database_url)

# MetaData del modelo, usado para el soporte de 'autogenerate'.
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
