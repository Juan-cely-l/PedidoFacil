"""Reglas del acceso del dueño: correos, destino de retorno y sesión.

Módulo puro: no importa la configuración ni hace HTTP, para probarlo con pruebas unitarias.
"""


def normalize_email(email: str) -> str:
    """Correo para comparar: sin espacios al inicio ni al final y sin distinguir mayúsculas."""
    raise NotImplementedError
