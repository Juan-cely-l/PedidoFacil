"""Hook commit-msg: exige el formato `tipo(PED-123): descripción`.

La clave de Jira en el mensaje enlaza cada commit con su issue (GitHub for Jira),
lo que da la trazabilidad historia -> commit -> PR que pide el proyecto.
"""

import re
import sys
from pathlib import Path

TIPOS = "feat|fix|docs|test|refactor|perf|style|build|ci|chore|revert"
PATRON = re.compile(rf"^({TIPOS})\(PED-\d+\)!?: \S.{{2,}}")
PERMITIDOS = ("Merge ", "Revert ", "fixup! ", "squash! ", "amend! ")

EJEMPLO = """
Formato esperado:  tipo(PED-123): descripción breve
Ejemplos:
  feat(PED-12): registrar pedido manual
  test(PED-14): cubrir transiciones inválidas de estado
  ci(PED-10): ejecutar pytest en pull requests
Tipos válidos: feat, fix, docs, test, refactor, perf, style, build, ci, chore, revert
"""


def main() -> int:
    primera_linea = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()[0].strip()
    if primera_linea.startswith(PERMITIDOS) or PATRON.match(primera_linea):
        return 0
    sys.stderr.write(f"Mensaje de commit inválido: {primera_linea!r}\n{EJEMPLO}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
