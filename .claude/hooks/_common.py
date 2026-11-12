"""Utilidades compartidas por los hooks de Claude Code de PedidoFácil."""

import json
import sys
from typing import Any, NoReturn


def read_event() -> dict[str, Any]:
    """Lee el evento JSON que Claude Code envía por la entrada estándar."""
    event: dict[str, Any] = json.load(sys.stdin)
    return event


def decide(decision: str, reason: str) -> NoReturn:
    """Responde «allow», «ask» o «deny» a un PreToolUse y termina."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.exit(0)
