"""Punto de entrada: ejecuta todo el pipeline y genera web/data/predictions.json.

Uso:
    python build.py
Luego sirve la web:
    python -m http.server 8000 --directory web
    -> abre http://localhost:8000
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from simulate import main  # noqa: E402

if __name__ == "__main__":
    # Regenera el modelo bottom-up (ataque+defensa por jugador) antes de simular
    try:
        import players_model
        players_model.main()
    except Exception as e:  # noqa: BLE001
        print(f"(aviso: players_model no se regeneró: {e})")
    # Refresca la validación de minutos de gol
    try:
        import validate_timing
        validate_timing.main()
    except Exception as e:  # noqa: BLE001
        print(f"(aviso: validate_timing no corrió: {e})")
    main()
