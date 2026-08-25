"""Corre los casos de evals/casos.json contra la función real de la app que
clasifica el período de una reserva (clasificar_periodo_reserva). Sale con
código 1 si el porcentaje de aciertos es menor a 80%, para que el CI lo
tome como fallo (FIX-007).
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
CASOS_PATH = REPO_ROOT / "evals" / "casos.json"
UMBRAL_APROBACION = 0.8

sys.path.insert(0, str(BACKEND_DIR))

# app.core.config.Settings() no tiene defaults (ver backend/app/core/config.py)
# y se instancia apenas se importa app.features.reservas.schemas (vía
# app.core.database). Mismo patrón que backend/tests/conftest.py: valores
# dummy, sin conexión real a base de datos (la función evaluada es pura).
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://evals@localhost/evals")
os.environ.setdefault("ADMIN_USERNAME", "evals")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$evalsevalsevalsevalsevalsevalsevalsevalse")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:5173")

from app.features.reservas.schemas import clasificar_periodo_reserva  # noqa: E402


def main() -> int:
    casos = json.loads(CASOS_PATH.read_text(encoding="utf-8"))

    fallidos = []
    for caso in casos:
        entrada = caso["entrada"]
        esperado = caso["espero"]

        obtenido = clasificar_periodo_reserva(
            fecha_inicio=datetime.fromisoformat(entrada["fecha_inicio"]),
            fecha_fin=datetime.fromisoformat(entrada["fecha_fin"]),
            ahora=datetime.fromisoformat(entrada["ahora"]),
        )

        if obtenido != esperado:
            fallidos.append((entrada, esperado, obtenido))

    total = len(casos)
    pasaron = total - len(fallidos)
    porcentaje = (pasaron / total * 100) if total else 0.0

    print(f"{pasaron}/{total} casos pasaron ({porcentaje:.1f}%)")

    if fallidos:
        print("\nCasos fallidos:")
        for entrada, esperado, obtenido in fallidos:
            print(f"  entrada={entrada} esperado={esperado!r} obtenido={obtenido!r}")

    if total == 0 or (pasaron / total) < UMBRAL_APROBACION:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
