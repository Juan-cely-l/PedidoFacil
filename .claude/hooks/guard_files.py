"""PreToolUse (Edit/Write/MultiEdit): protege archivos según su riesgo.

- Bloquea: secretos (.env, llaves) y uv.lock (solo cambia con `uv add`).
- Pide confirmación: constitución, CI, hooks, configuración de herramientas,
  migraciones ya escritas y pruebas existentes (TDD: no se ajusta la prueba para pasar).
"""

import subprocess
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).parent))
from _common import decide, read_event

event = read_event()
raw = event.get("tool_input", {}).get("file_path", "")
root = Path(event.get("cwd", ".")).resolve()
try:
    rel = PurePosixPath(Path(raw).resolve().relative_to(root).as_posix())
except ValueError:
    decide("ask", f"{raw} está fuera del proyecto.")

name = rel.name
if (name == ".env" or name.startswith(".env.")) and name != ".env.example":
    decide("deny", "Los archivos .env contienen secretos: edítalos tú a mano.")
if rel.suffix in {".pem", ".key"}:
    decide("deny", "No se editan llaves ni certificados.")
if str(rel) == "uv.lock":
    decide("deny", "uv.lock solo cambia con `uv add` o `uv lock`, nunca a mano.")

protected = {
    ".specify/memory/constitution.md": "la constitución (cambia con /speckit-constitution y PR)",
    ".pre-commit-config.yaml": "los hooks de pre-commit",
    "pyproject.toml": "la configuración de dependencias y herramientas",
    ".claude/settings.json": "los permisos y hooks de Claude Code",
}
if str(rel) in protected:
    decide("ask", f"Vas a modificar {protected[str(rel)]}. ¿Lo apruebas?")
if rel.parts[:1] == (".github",) or rel.parts[:2] == (".claude", "hooks"):
    decide("ask", f"{rel} controla la CI o los hooks. ¿Lo apruebas?")


def tracked(path: PurePosixPath) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(path)],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


if rel.parts[:2] == ("migrations", "versions") and tracked(rel):
    decide("ask", f"{rel} es una migración ya registrada: crea una nueva en lugar de editarla.")
if rel.parts[:1] == ("tests",) and rel.suffix == ".py" and tracked(rel):
    decide(
        "ask",
        f"Vas a cambiar pruebas existentes en {rel}. Si estás en fase verde, "
        "la prueba no se toca: ¿es una prueba nueva o una corrección aprobada?",
    )
sys.exit(0)
