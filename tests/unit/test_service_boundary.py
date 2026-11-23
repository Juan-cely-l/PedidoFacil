"""Frontera del servicio de cotización (RD-1, research R8).

Prueba de guarda: el servicio y el contrato con la IA se importan sin cargar nada de la web, para
que el webhook de Telegram (HU-20) los reutilice. Pasa desde que existen los módulos y falla si
alguien agrega un import de FastAPI, Starlette, Jinja2, `app.config` o `app.db`.

Se ejecuta en un intérprete limpio porque en el proceso de pytest esos módulos ya están cargados.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE_MODULES = ("app.services.quotes", "app.services.quote_ai")
FORBIDDEN_MODULES = ("fastapi", "starlette", "jinja2", "app.config", "app.db")

_PROBE = """
import importlib
import sys

root, *modules = sys.argv[1:]
sys.path.insert(0, root)
for module in modules:
    importlib.import_module(module)
forbidden = {forbidden!r}
print(",".join(name for name in forbidden if name in sys.modules))
"""


def test_el_servicio_de_cotizacion_no_carga_nada_de_la_web() -> None:
    probe = _PROBE.format(forbidden=FORBIDDEN_MODULES)

    result = subprocess.run(  # noqa: S603  (intérprete y argumentos propios, sin entrada externa)
        [sys.executable, "-I", "-c", probe, str(ROOT), *SERVICE_MODULES],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"módulos web cargados: {result.stdout.strip()}"
