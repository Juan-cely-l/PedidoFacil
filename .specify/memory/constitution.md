<!--
Informe de impacto de sincronización (Sync Impact Report)
- Cambio de versión: plantilla sin inicializar → 1.0.0 (adopción inicial)
- Principios definidos (reemplazan los marcadores de la plantilla):
  - [PRINCIPLE_1_NAME] → I. TDD obligatorio (NO NEGOCIABLE)
  - [PRINCIPLE_2_NAME] → II. Pruebas deterministas y aisladas
  - [PRINCIPLE_3_NAME] → III. Calidad como puerta de integración
  - [PRINCIPLE_4_NAME] → IV. Stack fijo y simplicidad (YAGNI)
  - [PRINCIPLE_5_NAME] → V. La IA asiste, el humano decide
  - (nuevo) VI. Seguridad y privacidad
  - (nuevo) VII. Trazabilidad
- Secciones añadidas: «Restricciones adicionales», «Flujo de desarrollo y puertas de calidad»
- Secciones eliminadas: ninguna
- Plantillas dependientes: no se modifican en este comando (leen la constitución en
  tiempo de ejecución): .specify/templates/plan-template.md, spec-template.md,
  tasks-template.md
- TODO diferidos: ninguno
- Nota: este comentario es material temporal de revisión; elimínelo antes de hacer commit.
-->

# Constitución de PedidoFácil

PedidoFácil es una aplicación web para que emprendimientos registren pedidos (manualmente o
pegando el mensaje del cliente para que una IA lo estructure) y para que sus clientes consulten
el estado con un enlace. Es un proyecto académico individual (Ingeniería de Software),
gestionado con Scrum en Jira (proyecto PED), con entrega final el 2026-11-29.

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
- Autenticación del único usuario (el dueño) con `SessionMiddleware` de Starlette y
  `pwdlib[argon2]`.
- Despliegue en Render con su runtime nativo de Python y uv.
- Toda dependencia nueva DEBE justificarse en `plan.md` y agregarse con `uv add` solo cuando
  una historia la necesite.
- NO DEBEN crearse capas ni abstracciones sin un uso actual; el alcance DEBE ser proporcional a
  una sola persona.

**Justificación**: un stack fijo elimina decisiones repetidas y la simplicidad mantiene el
proyecto entregable en el plazo.

### V. La IA asiste, el humano decide

- La extracción NO DEBE inventar datos: los campos no detectados quedan vacíos y marcados para
  revisión.
- Ningún pedido extraído DEBE guardarse sin confirmación explícita del dueño.
- DEBE existir siempre un respaldo manual cuando la IA falla, tarda más de 15 s o devuelve datos
  inválidos.

**Justificación**: un pedido con datos inventados causa entregas erróneas; la IA ahorra tiempo
pero la responsabilidad es del dueño.

### VI. Seguridad y privacidad

- Los secretos DEBEN vivir solo en variables de entorno; `.env.example` documenta las claves sin
  valores.
- La página pública de seguimiento NO DEBE mostrar teléfono ni dirección y DEBE usar códigos
  aleatorios no secuenciales.
- Los logs NO DEBEN contener datos personales ni claves.

**Justificación**: el enlace de seguimiento es público y los datos de clientes son personales;
códigos secuenciales permitirían enumerar pedidos ajenos.

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

**Versión**: 1.0.0 | **Ratificada**: 2026-11-11 | **Última enmienda**: 2026-11-11
