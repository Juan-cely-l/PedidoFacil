"""PostToolUse (Edit/Write/MultiEdit): formatea y revisa el archivo Python editado.

Si quedan errores de lint que ruff no corrige solo, se los devuelve a Claude (código de
salida 2) para que los arregle en el momento y no en la CI. Si ruff no puede ejecutarse
(por ejemplo, sin `uv sync`), solo avisa y no bloquea.
"""

import json
import subprocess
import sys

event = json.load(sys.stdin)
path = event.get("tool_input", {}).get("file_path", "")
if not path.endswith(".py"):
    sys.exit(0)

cwd = event.get("cwd", ".")
ruff = ["uv", "run", "--no-sync", "ruff"]
check = subprocess.run(
    [*ruff, "check", "--fix", "--output-format", "concise", path],
    cwd=cwd,
    capture_output=True,
    text=True,
    check=False,
)
subprocess.run([*ruff, "format", path], cwd=cwd, capture_output=True, check=False)
if check.returncode == 1:  # ruff se ejecutó y quedan problemas sin corrección automática
    sys.stderr.write(f"ruff encontró problemas en {path}:\n{check.stdout}")
    sys.exit(2)
if check.returncode != 0:  # no se pudo ejecutar ruff: avisar sin bloquear
    sys.stderr.write(f"Aviso: no se pudo ejecutar ruff ({check.stderr.strip()[:200]})\n")
sys.exit(0)
