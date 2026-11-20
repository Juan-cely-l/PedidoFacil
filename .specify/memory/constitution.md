<!--
Informe de impacto de sincronización (Sync Impact Report)
- Cambio de versión: 1.2.0 → 1.3.0 (MINOR; enmienda del 2026-11-20)
- Motivo: recorte de alcance. HU-18 (inventario y compras) y HU-19 (alertas de stock bajo)
  salieron del backlog del proyecto en la planificación del Sprint 2, el 2026-11-18 (ADR 0004).
- Por qué MINOR y no MAJOR: ningún principio se elimina ni se redefine; los siete conservan su
  título, su propósito y su justificación. Lo que cambia es el alcance del producto: los puntos
  retirados describían funcionalidad que salió del backlog y ya no tienen nada que regular. Por
  analogía con las reglas de versionado, es un cambio material de la guía (MINOR), no una
  redefinición (MAJOR) ni una corrección de redacción (PATCH).
- Vacío en la gobernanza: las reglas de versionado no contemplan el caso de retirar una exigencia
  de un principio que se conserva. MAJOR cubre eliminar o redefinir un principio; MINOR, agregar
  o ampliar; PATCH, aclarar sin cambio semántico. Retirar una exigencia por recorte de alcance
  no encaja en ninguna; aquí se clasifica como MINOR por la razón anterior. Queda pendiente
  precisarlo en la sección de gobernanza en una enmienda futura.
- Preámbulo: sin «disponibilidad del inventario», sin descuento de existencias al convertir en
  pedido y sin alertas de stock bajo; se declara que la aplicación no lleva inventario.
- Principios modificados (sin cambio de título):
  - IV. Stack fijo y simplicidad (YAGNI): se retira «El descuento de inventario DEBE hacerse
    dentro de una transacción».
  - V. La IA asiste, el humano decide: se retira la exigencia de marcar los productos sin
    unidades; el bot responde solo si reconoció todos los productos (sin condición de
    disponibilidad); los pedidos del bot quedan «Por confirmar» sin mención al descuento de
    inventario.
  - VI. Seguridad y privacidad: el ejemplo de información interna ya no es el inventario.
- Secciones añadidas: ninguna
- Secciones eliminadas: ninguna
- Plantillas dependientes: no se modifican en este comando (leen la constitución en tiempo de
  ejecución). CLAUDE.md se actualiza en el mismo commit.
- TODO diferidos: precisar en la gobernanza cómo se versiona retirar una exigencia de un
  principio que se conserva.
-->

# Constitución de PedidoFácil

PedidoFácil es una aplicación web que atiende los pedidos de un emprendimiento desde el primer
mensaje del cliente. Una IA identifica los productos que pide el cliente; la aplicación arma la
cotización con los precios del catálogo, la envía por WhatsApp o Telegram y, cuando el cliente
acepta, la convierte en pedido. Un bot de Telegram atiende únicamente a los clientes. La
aplicación no lleva inventario ni registra compras. No existe página pública de seguimiento. Es un proyecto académico individual
(Ingeniería de Software), gestionado con Scrum en Jira (proyecto PED), con entrega final el
2026-11-29.

## Principios fundamentales

### I. TDD obligatorio (NO NEGOCIABLE)

- NO DEBE existir código de producción sin una prueba que haya fallado primero.
- El ciclo es estrictamente rojo → verde → refactor.
- En `tasks.md`, cada tarea de implementación DEBE ir precedida de su tarea de prueba.
- Antes de implementar se DEBE ejecutar `uv run pytest` y confirmar que la prueba nueva falla
  por la razón esperada (no por un error de importación, sintaxis o configuración).
- La evidencia DEBE quedar en el historial del PR: un commit `test(...)` en rojo, luego
  `feat(...)` o `fix(...)` en verde y, si aplica, `refactor(...)`.

**Justificación**: la prueba que falla primero demuestra que verifica el comportamiento nuevo y
deja evidencia auditable del proceso, que es parte de la evaluación académica.

### II. Pruebas deterministas y aisladas

- Ninguna prueba ni la CI DEBE hacer llamadas de red reales.
- La IA se prueba con `TestModel` o `FunctionModel` de Pydantic AI, y
  `ALLOW_MODEL_REQUESTS=False` DEBE estar activado globalmente en las pruebas.
- La Bot API de Telegram DEBE simularse con `httpx.MockTransport`.
- Las pruebas NUNCA DEBEN llamar a Google: el cliente OAuth se sustituye con
  `app.dependency_overrides` o `httpx.MockTransport`.
- La base de datos de pruebas DEBE ser SQLite en memoria.
- Cuando un comportamiento dependa del día actual, la fecha DEBE congelarse con
  `time-machine`.
- Las pruebas unitarias (servicios y lógica, sin HTTP) van en `tests/unit`; las de integración
  (endpoints con `TestClient`) van en `tests/integration`.

**Justificación**: pruebas que dependen de la red, del reloj o de un servicio externo son lentas,
cuestan dinero (cuota de Gemini) y fallan de forma intermitente.

### III. Calidad como puerta de integración

- Cobertura DEBE ser ≥ 80 %, incluyendo ramas.
- `mypy --strict`, `ruff check` y `ruff format --check` DEBEN pasar sin errores.
- El check de CI «Calidad y pruebas» DEBE pasar antes de integrar cualquier cambio a `main`.

**Justificación**: una puerta automática y objetiva sustituye la revisión por pares que un
proyecto individual no tiene.

### IV. Stack fijo y simplicidad (YAGNI)

- Python 3.12 gestionado con uv.
- FastAPI con arquitectura en capas: routers → services → repositories; modelos en
  `app/models`. Los routers NO DEBEN acceder a repositorios directamente.
- SQLModel + Alembic para persistencia; `create_all` NO DEBE usarse fuera de las pruebas.
- SQLite en local y PostgreSQL (Neon) en producción, seleccionados vía `DATABASE_URL`.
- Interfaz con Jinja2 + HTMX + Pico.css; sin frameworks de frontend.
- Extracción con Pydantic AI y Gemini.
- Integración con la Bot API de Telegram mediante llamadas directas con `httpx` y un webhook en
  FastAPI; NO DEBEN usarse librerías de bots.
- Envío de cotizaciones desde la web por WhatsApp y Telegram con enlaces `wa.me` y
  `t.me/share`; la API oficial de WhatsApp queda fuera del alcance.
- Los montos DEBEN guardarse como enteros en pesos colombianos (COP), nunca como `float`.
- Autenticación del dueño con Google OAuth 2.0 (OpenID Connect) mediante `authlib`, sobre el
  `SessionMiddleware` de Starlette. La aplicación NO DEBE guardar contraseñas.
- Despliegue en Render con su runtime nativo de Python y uv.
- Toda dependencia nueva DEBE justificarse en `plan.md` y agregarse con `uv add` solo cuando
  una historia la necesite.
- NO DEBEN crearse capas ni abstracciones sin un uso actual; el alcance DEBE ser proporcional a
  una sola persona.

**Justificación**: un stack fijo elimina decisiones repetidas y la simplicidad mantiene el
proyecto entregable en el plazo.

### V. La IA asiste, el humano decide

- La IA identifica productos, variantes y cantidades, pero NUNCA DEBE fijar precios: los totales
  los calcula el código a partir del catálogo.
- Los productos no reconocidos DEBEN quedar marcados; NUNCA DEBEN inventarse datos.
- El bot solo DEBE responder por su cuenta si reconoció todos los productos; en cualquier otro
  caso avisa al cliente y notifica al dueño.
- Los pedidos creados por el bot DEBEN quedar en estado «Por confirmar» hasta que el dueño los
  confirme.
- DEBE existir siempre un respaldo manual cuando la IA falla, tarda más de 15 s o devuelve datos
  inválidos.

**Justificación**: un precio o un producto inventado por la IA genera cobros y entregas
erróneas; calcular los totales en código y dejar la confirmación al dueño mantiene la
responsabilidad en el humano mientras la IA ahorra tiempo.

### VI. Seguridad y privacidad

- Los secretos DEBEN vivir solo en variables de entorno; `.env.example` documenta las claves sin
  valores.
- El webhook de Telegram DEBE validar la cabecera `X-Telegram-Bot-Api-Secret-Token` y rechazar
  las peticiones que no la incluyan o no coincidan.
- El token del bot DEBE vivir solo en variables de entorno.
- Los mensajes enviados a clientes NO DEBEN incluir datos de otros clientes ni información
  interna del negocio.
- Los logs NO DEBEN contener datos personales ni claves.
- El acceso DEBE restringirse con una lista blanca de correos autorizados (`OWNER_EMAILS`):
  autenticarse con Google no basta para entrar.
- La cookie de sesión DEBE ser `httponly` y `samesite=lax`, y `secure` en producción.
- Los tokens de OAuth y los `id_token` NO DEBEN aparecer en logs ni en mensajes de error.

**Justificación**: el webhook es un endpoint público que cualquiera podría invocar y los datos de
clientes son personales; sin el secreto, un tercero podría crear pedidos falsos, y un mensaje mal
armado podría filtrar datos ajenos o del negocio. Cualquier persona tiene cuenta de Google, así
que solo la lista blanca separa al dueño del resto; y una cookie robada o un token en un log
darían acceso a todo el negocio.

### VII. Trazabilidad

- Cada especificación DEBE corresponder a una historia de Jira y llevar su clave (PED-XX) en el
  título.
- Ramas: `feature/PED-XX-descripcion`.
- Commits: `tipo(PED-XX): descripción`.
- La integración a `main` se hace solo por pull request con squash merge.

**Justificación**: enlaza cada cambio con su historia del backlog Scrum, de la especificación al
commit.

## Restricciones adicionales

- La interfaz DEBE estar en español y ser usable en pantallas de 360 px de ancho.
- Los identificadores de código (variables, funciones, clases, módulos) DEBEN estar en inglés.
- Docstrings, mensajes al usuario y nombres de pruebas DEBEN estar en español.

## Flujo de desarrollo y puertas de calidad

1. Historia en Jira (PED-XX) → `/speckit-specify` → `/speckit-clarify` si hay ambigüedades.
2. `/speckit-plan`: la verificación de constitución del plan DEBE pasar; toda violación se
   justifica en la sección de complejidad de `plan.md`.
3. `/speckit-tasks`: cada tarea de implementación precedida de su tarea de prueba (Principio I).
4. `/speckit-analyze` DEBE ejecutarse antes de `/speckit-implement`.
5. Implementación en rama `feature/PED-XX-descripcion` siguiendo rojo → verde → refactor.
6. Pull request a `main`; el check «Calidad y pruebas» DEBE pasar; integración con squash merge.

## Gobernanza

- Esta constitución prevalece sobre cualquier otra práctica o instrucción del proyecto.
- Solo se modifica mediante pull request que actualice la versión según versionado semántico:
  - **MAJOR**: se elimina o redefine un principio.
  - **MINOR**: se agrega un principio o sección, o se amplía materialmente una guía.
  - **PATCH**: aclaraciones, redacción o correcciones sin cambio semántico.
- Todo plan y todo PR DEBEN verificar el cumplimiento de estos principios; cualquier violación
  DEBE justificarse en la sección de complejidad (Complexity Tracking) de `plan.md`.
- La guía operativa para el agente de desarrollo está en `CLAUDE.md`.

**Versión**: 1.3.0 | **Ratificada**: 2026-11-11 | **Última enmienda**: 2026-11-20
