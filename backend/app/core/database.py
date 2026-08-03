"""Engine y sesión síncronos de SQLAlchemy (driver psycopg2).

También define `Base`, la clase declarativa compartida por TODOS los
modelos del backend (no solo `vehiculos`): vive acá, y no en el módulo de
un feature puntual, porque `alembic/env.py` necesita un único
`Base.metadata` que agregue las tablas de cada feature a medida que el
proyecto crezca (p. ej. FEAT-001b agregará un modelo `Reserva` que deberá
registrarse contra este mismo `Base`).
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency de FastAPI: abre una sesión por request y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
