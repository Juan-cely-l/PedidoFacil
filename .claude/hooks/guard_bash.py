"""PreToolUse (Bash): bloquea comandos que rompen el flujo del proyecto."""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import decide, read_event

event = read_event()
command = event.get("tool_input", {}).get("command", "")
cwd = event.get("cwd", ".")

branch = subprocess.run(
    ["git", "branch", "--show-current"], cwd=cwd, capture_output=True, text=True, check=False
).stdout.strip()

if re.search(r"\bgit\s+(commit|merge|rebase)\b", command) and branch == "main":
    decide("deny", "Estás en main. Crea una rama feature/PED-XX-... antes de hacer commits.")
if re.search(r"\bgit\s+push\b.*\bmain\b", command):
    decide("deny", "main solo recibe cambios por pull request.")
if re.search(r"\bgit\s+push\b", command):
    decide("ask", f"Vas a subir la rama {branch or '(desconocida)'} a GitHub. ¿Lo apruebas?")
if re.search(r"\b(pip|pip3)\s+install\b|\bpython3?\s+-m\s+pip\b", command):
    decide("deny", "Este proyecto usa uv: `uv add <paquete>` o `uv add --dev <paquete>`.")
if re.search(r"(cat|less|more|head|tail|grep|source)\s+[^|;&]*\.env(\s|$)", command):
    decide("deny", "No leas .env: contiene secretos. Usa .env.example como referencia.")
if re.search(r"\brm\s+-[a-zA-Z]*r", command):
    decide("ask", "Borrado recursivo. ¿Lo apruebas?")
if re.search(r"alembic\s+downgrade", command):
    decide("ask", "Revertir una migración puede borrar datos. ¿Lo apruebas?")
sys.exit(0)
