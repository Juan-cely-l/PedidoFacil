"""Contrato con el proveedor de IA para cotizar un mensaje (PED-16, research.md R5 y R6).

Aquí viven el esquema de lo que devuelve la IA (sin ningún campo de precio), las instrucciones y
la construcción del agente. No importa FastAPI, Starlette, Jinja2 ni `app.config`: el bot de
Telegram (HU-20) lo reutiliza tal cual (RD-1, research.md R8).
"""
