"""Protección de la aplicación: sesión del dueño.

La dependencia que exige sesión (`require_owner`) y la lista de rutas públicas llegan con la
Historia 3; aquí viven las constantes de la sesión que comparten la app y los servicios.
"""

SESSION_COOKIE = "pedidofacil_session"
# Duración máxima de la sesión: una jornada (research.md R5).
SESSION_MAX_AGE_SECONDS = 12 * 60 * 60
