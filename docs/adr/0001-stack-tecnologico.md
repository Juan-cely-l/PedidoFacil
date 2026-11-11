# ADR 0001: Stack tecnológico de PedidoFácil

## Estado

Aceptado, 2026-11-11.

## Contexto

PedidoFácil es una aplicación web para que emprendimientos registren pedidos (a mano o pegando
el mensaje del cliente para que una IA lo estructure) y para que sus clientes consulten el
estado con un enlace.

Restricciones que condicionan la elección:

- **Tiempo**: proyecto individual de 3 semanas (entrega el 2026-11-29).
- **Experiencia del autor**: sólida en Spring Boot y nula en frameworks web de Python. El stack
  debe tener conceptos equivalentes y una curva de aprendizaje corta.
- **TDD y CI obligatorios** (constitución, principios I a III): cada pieza del stack debe poder
  probarse rápido, sin red y de forma determinista, y la CI debe ejecutar lint, tipos, pruebas y
  cobertura en cada pull request.
- **Costo cero**: alojamiento, base de datos e IA en planes gratuitos.
- **Un solo usuario administrador** (el dueño) y una página pública de consulta.

## Opciones consideradas

### Framework web

| Opción | A favor | En contra |
|---|---|---|
| **FastAPI** | Liviano; inyección con `Depends` y validación con Pydantic, análogos a la inyección de dependencias y a DTO + Bean Validation de Spring; `TestClient` similar a MockMvc; tipado que encaja con `mypy --strict`. | Menos «baterías incluidas»: login y administración se construyen a mano. |
| Django | Admin, ORM, autenticación y migraciones integrados. | Mucha convención propia que aprender en 3 semanas; tipado estricto más difícil; trae mucho más de lo que necesita un solo usuario. |
| Spring Boot | Lo que el autor ya domina. | No cumple el objetivo de aprender Python; más pesado de arrancar y desplegar en planes gratuitos; el ecosistema de IA elegido (Pydantic AI) es de Python. |

### Interfaz

| Opción | A favor | En contra |
|---|---|---|
| **Jinja2 + HTMX + Pico.css** | HTML generado en el servidor y probable con `TestClient`; interactividad sin compilación ni JavaScript propio; Pico.css da un diseño responsivo (360 px) sin escribir clases. | Interacciones muy ricas en el cliente resultan más trabajosas. |
| React | Interfaz muy flexible. | Segundo proyecto (Node, empaquetador, pruebas de frontend), API separada y más superficie de CI; desproporcionado para una persona en 3 semanas. |
| Streamlit | Prototipos muy rápidos. | Pensado para tableros de datos, no para formularios con sesión y rutas públicas; difícil de probar con TDD y de controlar el HTML y la privacidad de la página pública. |

### Persistencia

| Opción | A favor | En contra |
|---|---|---|
| **SQLModel + Alembic** | Una sola clase sirve como modelo de tabla y de validación (Pydantic), con menos duplicación; Alembic versiona el esquema como Flyway. | SQLModel es una capa sobre SQLAlchemy con documentación menos completa en casos avanzados. |
| SQLAlchemy 2.0 (+ Alembic) | Más maduro y flexible. | Exige modelos ORM y esquemas Pydantic por separado: más código para el mismo resultado. |
| `create_all` sin migraciones | Cero configuración. | No permite evolucionar el esquema en producción sin perder datos; se reserva solo para las pruebas. |

### Base de datos de producción

| Opción | A favor | En contra |
|---|---|---|
| **PostgreSQL en Neon** | Plan gratuito que no expira; respaldos y restauración a un punto en el tiempo; conexión por `DATABASE_URL`. | La base se suspende sin uso y la primera consulta tras la pausa es más lenta. |
| PostgreSQL gratuito de Render | Misma plataforma que la aplicación. | Expira a los 30 días y no tiene respaldos: riesgo de perder los datos de la demostración antes o después de la entrega. |

En local y en pruebas se usa SQLite (en memoria para las pruebas), que no requiere servidor.

### Integración con la IA

| Opción | A favor | En contra |
|---|---|---|
| **Pydantic AI + Gemini** | Salida estructurada validada directamente contra un modelo Pydantic; `TestModel` y `FunctionModel` permiten probar con TDD sin red, y `ALLOW_MODEL_REQUESTS=False` bloquea llamadas reales por accidente; permite cambiar de proveedor sin reescribir el servicio. | Una dependencia y una abstracción más sobre el SDK del proveedor. |
| SDK `google-genai` directo | Sin intermediarios; acceso a todas las funciones de Gemini. | Para probarlo hay que simular el cliente a mano, y validar y reintentar la salida estructurada también queda a cargo del proyecto. |

### Despliegue

| Opción | A favor | En contra |
|---|---|---|
| **Render con runtime nativo de Python y uv** | Sin archivos extra que mantener; instala desde `uv.lock`, igual que la CI; despliegue automático desde `main`. | Ata la configuración de construcción a Render. |
| Docker en Render | Entorno reproducible y portable. | `Dockerfile` adicional que mantener y probar, y compilaciones más lentas, sin una necesidad actual que lo justifique (YAGNI). |

## Decisión

Se adopta el siguiente stack, que la constitución (principio IV) fija como obligatorio:

- **Python 3.12** gestionado con **uv**.
- **FastAPI** con arquitectura en capas: routers → services → repositories, modelos en
  `app/models`.
- **SQLModel + Alembic**; `create_all` solo en las pruebas.
- **SQLite** en local y pruebas; **PostgreSQL en Neon** en producción, vía `DATABASE_URL`.
- **Jinja2 + HTMX + Pico.css** para la interfaz.
- **Pydantic AI con Gemini** para extraer pedidos de los mensajes; en pruebas, `TestModel`
  o `FunctionModel` con `ALLOW_MODEL_REQUESTS=False`.
- **SessionMiddleware de Starlette + `pwdlib[argon2]`** para el login del dueño.
- **Render con runtime nativo de Python y uv** para el despliegue.

## Consecuencias

**Positivas**

- Cada capa se prueba sin red: servicios con pruebas unitarias, endpoints y HTML con
  `TestClient`, IA con `TestModel`/`FunctionModel` y base de datos con SQLite en memoria.
- Un solo lenguaje y un solo proyecto: la CI (ruff, mypy, pytest) cubre todo el código.
- Equivalencias directas con Spring (`Depends` ↔ inyección de dependencias, Pydantic ↔ DTO +
  Bean Validation, Alembic ↔ Flyway, `TestClient` ↔ MockMvc) reducen la curva de aprendizaje.
- Los datos de producción no expiran y tienen respaldos.

**Negativas y riesgos**

- El login, la protección de rutas y la administración se construyen a mano (no hay admin como
  en Django); se acota a un solo usuario.
- SQLite en pruebas y PostgreSQL en producción pueden comportarse distinto (tipos, zonas
  horarias, restricciones). Mitigación: migraciones de Alembic probadas contra PostgreSQL antes
  de desplegar y evitar SQL específico de un motor.
- La pausa de Neon y el reposo del plan gratuito de Render agregan latencia a la primera
  petición, algo aceptable para una demostración académica.
- La dependencia de un plan gratuito de Gemini implica límites de cuota; el respaldo manual
  (principio V) garantiza que la aplicación siga siendo usable si la IA falla.
- Cambiar cualquiera de estas piezas requiere un nuevo ADR y una enmienda de la constitución.
