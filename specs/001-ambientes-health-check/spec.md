# Especificación: PED-11 · HU-03 Ambientes y health check

**Rama**: `feature/PED-11-ambientes-despliegue`

**Creada**: 2026-11-12

**Estado**: Borrador

**Entrada**: descripción del usuario: "PED-11 · HU-03 Ambientes y health check. Como equipo de
desarrollo, quiero tres ambientes bien separados y un health check que verifique la base de datos,
para probar sin riesgo y detectar fallos en producción. Criterios: ENVIRONMENT admite test, local y
production; en test la configuración no lee el archivo .env; en production la app no arranca si
falta DATABASE_URL de PostgreSQL o SECRET_KEY (mínimo 32 caracteres), ni si AI_PROVIDER es gemini y
falta GEMINI_API_KEY, y el error indica qué variable falta; AI_PROVIDER admite fake y gemini, con
fake por defecto en local y test; /docs está activo en local y desactivado en production; el nivel
de log por defecto es DEBUG en local e INFO en production; GET /health responde 200 con el estado
de la base de datos y el commit desplegado, y 503 si la base no responde; .env.example documenta
todas las variables sin valores reales. Fuera de alcance: modelos de negocio, migraciones de tablas
y login."

## Clarifications

### Session 2026-11-12

- Q: En producción, si no se define `AI_PROVIDER`, ¿qué proveedor usa y se permite `fake`? → A:
  `gemini` por defecto en producción; `fake` solo si se define explícitamente, y al arrancar así
  se registra un log de nivel WARNING que lo indica claramente.
- Q: Si en el servidor se olvida definir `ENVIRONMENT`, ¿qué hace la aplicación? → A: el valor
  por defecto es `production` (el más estricto); `local` y `test` se definen explícitamente. Si
  falta configuración en producción, el error sugiere: "Para desarrollo local copia .env.example
  a .env (ENVIRONMENT=local)".
- Q: ¿`GET /health` consulta la base en cada llamada aunque la plataforma lo invoque con
  frecuencia? → A: dos endpoints. `GET /health/live` no toca la base y es el que usa Render;
  `GET /health` consulta la base (200/503) y es el que usa el job de despliegue. Ambos devuelven
  el commit desplegado.

## Escenarios de usuario y pruebas *(obligatorio)*

### Historia 1 - Producción no arranca mal configurada (Prioridad: P1)

Como responsable del despliegue, quiero que la aplicación se niegue a arrancar en producción si
falta una variable obligatoria o tiene un valor inválido, y que el mensaje diga exactamente cuál,
para corregir la configuración antes de que un cliente vea un error.

**Por qué esta prioridad**: un despliegue que arranca sin base de datos de producción o con una
clave de sesión débil falla tarde y de forma confusa, o expone datos; es el riesgo más caro.

**Prueba independiente**: arrancar la aplicación con `ENVIRONMENT=production` y distintas
combinaciones de variables ausentes o inválidas, y comprobar que falla (o arranca) con el mensaje
esperado.

**Escenarios de aceptación**:

1. **Dado** `ENVIRONMENT=production` sin `DATABASE_URL`, **cuando** la aplicación arranca,
   **entonces** se detiene con un error que nombra `DATABASE_URL`.
2. **Dado** `ENVIRONMENT=production` con un `DATABASE_URL` que no es de PostgreSQL (por ejemplo,
   SQLite), **cuando** arranca, **entonces** se detiene con un error que nombra `DATABASE_URL` e
   indica que debe ser PostgreSQL.
3. **Dado** `ENVIRONMENT=production` sin `SECRET_KEY` o con una de menos de 32 caracteres,
   **cuando** arranca, **entonces** se detiene con un error que nombra `SECRET_KEY` e indica el
   mínimo de 32 caracteres.
4. **Dado** `ENVIRONMENT=production` y `AI_PROVIDER=gemini` sin `GEMINI_API_KEY`, **cuando**
   arranca, **entonces** se detiene con un error que nombra `GEMINI_API_KEY`.
5. **Dado** `ENVIRONMENT=production` con varias variables obligatorias ausentes, **cuando**
   arranca, **entonces** el error las nombra todas a la vez.
6. **Dado** `ENVIRONMENT=production` con todas las variables obligatorias válidas, **cuando**
   arranca, **entonces** la aplicación queda disponible.
7. **Dado** `ENVIRONMENT=production` y `AI_PROVIDER=fake` con el resto de variables válidas,
   **cuando** arranca, **entonces** la aplicación queda disponible y registra un log de nivel
   WARNING que indica que producción usa el proveedor de IA simulado.
8. **Dado** que no se define `ENVIRONMENT` ni las variables de producción (por ejemplo, un
   desarrollador que ejecuta la aplicación sin `.env`), **cuando** arranca, **entonces** se trata
   como producción, se detiene nombrando las variables faltantes y sugiere: "Para desarrollo
   local copia .env.example a .env (ENVIRONMENT=local)".
9. **Dado** cualquier error de configuración, **cuando** se muestra, **entonces** no incluye el
   valor de ninguna variable secreta.

---

### Historia 2 - Health checks de vida y de base de datos (Prioridad: P1)

Como responsable del despliegue, quiero dos comprobaciones: `GET /health/live`, que la plataforma
de despliegue (Render) consulta con frecuencia para saber si el proceso está vivo sin tocar la base,
y `GET /health`, que el job de despliegue consulta para confirmar que la base de datos responde.
Ambas indican qué commit está desplegado.

**Por qué esta prioridad**: sin `/health`, una base caída solo se descubre cuando un cliente falla;
sin separar `/health/live`, las consultas automáticas de la plataforma mantendrían la base
despierta y agotarían la cuota del plan gratuito.

**Prueba independiente**: consultar `GET /health/live` y `GET /health` con la base disponible y
con la base inaccesible, y comprobar el código de estado y el contenido.

**Escenarios de aceptación**:

1. **Dado** que la base de datos responde, **cuando** se consulta `GET /health`, **entonces**
   responde 200 con el estado general «ok», el estado de la base «ok», la versión y el commit
   desplegado.
2. **Dado** que la base de datos no responde, **cuando** se consulta `GET /health`, **entonces**
   responde 503 con el estado de la base «error», la versión y el commit.
3. **Dado** que la base no responde, **cuando** se responde 503, **entonces** la respuesta no
   incluye la cadena de conexión, credenciales ni el detalle técnico del error; ese detalle queda
   solo en el log, también sin credenciales.
4. **Dado** que la base de datos responde o no, **cuando** se consulta `GET /health/live`,
   **entonces** responde 200 con el estado general «ok», la versión y el commit, sin consultar la
   base de datos.
5. **Dado** que no se conoce el commit (ejecución local), **cuando** se consulta `GET /health` o
   `GET /health/live`, **entonces** el commit aparece como «local».
6. **Dado** que se conoce el commit desplegado, **cuando** se consulta `GET /health` o
   `GET /health/live`, **entonces** se muestran sus primeros 7 caracteres.

---

### Historia 3 - Pruebas aisladas de la configuración local (Prioridad: P2)

Como desarrollador, quiero que en el ambiente de pruebas la configuración no lea mi archivo `.env`,
para que mis valores locales (o de producción) nunca alteren ni contaminen las pruebas.

**Por qué esta prioridad**: protege el determinismo de las pruebas (principio II) y evita usar por
error una base o una clave reales; no bloquea el despliegue.

**Prueba independiente**: con un `.env` que define valores distintos de los predeterminados,
cargar la configuración en el ambiente de pruebas y comprobar que esos valores se ignoran.

**Escenarios de aceptación**:

1. **Dado** `ENVIRONMENT=test` y un `.env` que define otro valor para una variable, **cuando** se
   carga la configuración, **entonces** se usa el valor predeterminado o el de las variables de
   entorno del proceso, nunca el del `.env`.
2. **Dado** `ENVIRONMENT=local` y un `.env`, **cuando** se carga la configuración, **entonces**
   los valores del `.env` sí se aplican.
3. **Dado** `ENVIRONMENT=test` o `local` sin `AI_PROVIDER`, **cuando** se carga la configuración,
   **entonces** el proveedor de IA es `fake`.

---

### Historia 4 - Valores por defecto según el ambiente (Prioridad: P3)

Como desarrollador, quiero que la documentación interactiva de la API y el nivel de log se ajusten
solos al ambiente, para depurar con comodidad en local sin exponer la API ni llenar los logs en
producción.

**Por qué esta prioridad**: mejora la seguridad y la operación, pero la aplicación funciona sin
ello.

**Prueba independiente**: arrancar en cada ambiente y comprobar si `/docs` responde y qué nivel de
log se aplica.

**Escenarios de aceptación**:

1. **Dado** `ENVIRONMENT=local`, **cuando** se consulta `/docs`, **entonces** la documentación
   está disponible.
2. **Dado** `ENVIRONMENT=production`, **cuando** se consulta `/docs` (o el esquema de la API),
   **entonces** responde 404.
3. **Dado** `ENVIRONMENT=local` sin `LOG_LEVEL`, **cuando** arranca, **entonces** el nivel de log
   es DEBUG.
4. **Dado** `ENVIRONMENT=production` sin `LOG_LEVEL`, **cuando** arranca, **entonces** el nivel de
   log es INFO.
5. **Dado** un `LOG_LEVEL` explícito, **cuando** arranca en cualquier ambiente, **entonces** se usa
   ese nivel.

---

### Casos límite

- `ENVIRONMENT` sin definir: se asume `production` y se aplican todas sus validaciones; nunca se
  arranca en modo de desarrollo por omisión.
- `ENVIRONMENT` con un valor no admitido (por ejemplo, `prod` o `staging`): la aplicación no
  arranca y el error lista los valores admitidos.
- `AI_PROVIDER` con un valor no admitido: la aplicación no arranca y el error lista `fake` y
  `gemini`.
- `SECRET_KEY` de exactamente 32 caracteres: se acepta; de 31, se rechaza.
- Variables definidas pero vacías se tratan como ausentes.
- `AI_PROVIDER=fake` en producción: se permite solo si se define explícitamente, no exige
  `GEMINI_API_KEY` (útil para una demostración sin cuota de IA) y deja un log WARNING al arrancar.
- `GEMINI_API_KEY` presente con `AI_PROVIDER=fake`: se ignora sin error.
- La base de datos de producción está suspendida por inactividad y la primera consulta tarda:
  `GET /health` sigue respondiendo dentro de su tiempo límite (503 si lo excede);
  `GET /health/live` no se ve afectado.
- Fuera de producción no se exigen `DATABASE_URL` ni `SECRET_KEY`: se usan valores predeterminados
  seguros para desarrollo.

## Requisitos *(obligatorio)*

### Requisitos funcionales

- **FR-001**: La configuración DEBE aceptar en `ENVIRONMENT` únicamente `test`, `local` y
  `production`, con `production` por defecto, y rechazar cualquier otro valor al arrancar. Los
  ambientes `local` y `test` DEBEN definirse explícitamente.
- **FR-002**: En el ambiente `test`, la configuración NO DEBE leer el archivo `.env`; solo usa
  valores predeterminados y variables de entorno del proceso.
- **FR-003**: En los ambientes `local` y `production`, la configuración DEBE poder leer el archivo
  `.env` si existe; las variables de entorno del proceso tienen prioridad sobre él.
- **FR-004**: En `production`, la aplicación NO DEBE arrancar si `DATABASE_URL` falta o no apunta
  a PostgreSQL.
- **FR-005**: En `production`, la aplicación NO DEBE arrancar si `SECRET_KEY` falta o tiene menos
  de 32 caracteres.
- **FR-006**: En `production`, la aplicación NO DEBE arrancar si `AI_PROVIDER` es `gemini` y falta
  `GEMINI_API_KEY`.
- **FR-007**: Todo error de configuración DEBE nombrar cada variable ausente o inválida (todas a la
  vez, no solo la primera), explicar el motivo y NO DEBE mostrar valores de variables secretas.
  En `production`, el error DEBE terminar con la sugerencia: "Para desarrollo local copia
  .env.example a .env (ENVIRONMENT=local)".
- **FR-008**: `AI_PROVIDER` DEBE aceptar únicamente `fake` y `gemini`; por defecto es `fake` en
  `local` y `test`, y `gemini` en `production`. En `production`, `fake` solo se usa si se define
  explícitamente y, en ese caso, la aplicación DEBE registrar al arrancar un log de nivel WARNING
  que indique claramente que usa el proveedor de IA simulado.
- **FR-009**: La documentación interactiva de la API (`/docs`) y su esquema DEBEN estar disponibles
  en `local` y `test`, y desactivados (404) en `production`.
- **FR-010**: Si `LOG_LEVEL` no se define, el nivel de log DEBE ser DEBUG en `local` e INFO en
  `production`; si se define, se respeta en cualquier ambiente.
- **FR-011**: `GET /health` DEBE comprobar en cada consulta que la base de datos responde y
  devolver 200 con: estado general, estado de la base, versión de la aplicación y commit
  desplegado. Es la comprobación que usa el job de despliegue.
- **FR-012**: Si la base de datos no responde o tarda más de 5 segundos, `GET /health` DEBE
  devolver 503 con el estado de la base marcado como error, sin cadenas de conexión, credenciales
  ni detalles técnicos en la respuesta.
- **FR-013**: En ambos endpoints, el commit desplegado DEBE mostrarse con sus primeros 7
  caracteres, o «local» si la plataforma no lo informa.
- **FR-014**: `GET /health` y `GET /health/live` NO DEBEN requerir autenticación.
- **FR-015**: Los logs NO DEBEN contener valores de secretos ni la cadena de conexión con
  credenciales (principio VI).
- **FR-016**: `.env.example` DEBE documentar todas las variables de configuración (`ENVIRONMENT`,
  `LOG_LEVEL`, `DATABASE_URL`, `SECRET_KEY`, `AI_PROVIDER`, `GEMINI_API_KEY` y las ya listadas),
  con una breve explicación, los valores admitidos y sin valores reales de secretos.
- **FR-017**: `GET /health/live` DEBE responder 200 con estado general, versión y commit
  desplegado sin consultar la base de datos. Es la comprobación que usa la plataforma de
  despliegue (Render).

### Entidades clave

- **Configuración**: conjunto de valores que determina el comportamiento de la aplicación según el
  ambiente: ambiente, nivel de log, conexión a la base de datos, clave secreta, proveedor de IA y
  su clave, commit desplegado.
- **Estado de salud**: resultado de consultar `GET /health` (estado general, estado de la base de
  datos, versión y commit) o `GET /health/live` (estado general, versión y commit).

## Criterios de éxito *(obligatorio)*

### Resultados medibles

- **SC-001**: El 100 % de las combinaciones de configuración inválida en producción descritas en la
  Historia 1 impiden el arranque y nombran la variable afectada.
- **SC-002**: Una persona puede identificar qué variable corregir leyendo solo el mensaje de error,
  sin consultar el código, en menos de 1 minuto.
- **SC-003**: `GET /health` responde en menos de 5 segundos tanto con la base disponible como con
  la base caída.
- **SC-004**: Una caída de la base de datos se refleja como servicio no sano en la siguiente
  consulta a `GET /health`.
- **SC-005**: Ninguna prueba depende del contenido del archivo `.env` del desarrollador: la suite
  da el mismo resultado con o sin él.
- **SC-006**: Ninguna respuesta del health check ni ningún mensaje de error de configuración
  contiene un secreto o una credencial.
- **SC-007**: El 100 % de las variables que la aplicación lee aparecen documentadas en
  `.env.example`.
- **SC-008**: Las consultas automáticas de la plataforma de despliegue no generan ninguna consulta
  a la base de datos, de modo que la base puede suspenderse cuando no hay uso real.

## Supuestos

- Fuera de producción, si no se define `DATABASE_URL`, se usa una base SQLite local (archivo en
  `local`, en memoria en `test`), y, si no se define `SECRET_KEY`, se genera un valor aleatorio en cada arranque (nunca un valor
  fijo en el código); en producción sigue siendo obligatoria.
- Las pruebas definen `ENVIRONMENT=test` en las variables de entorno del proceso antes de cargar la
  configuración (no pueden tomarlo del `.env`, FR-002), y `.env.example` trae
  `ENVIRONMENT=local` para que una copia sirva directamente para desarrollo.
- En `test` el nivel de log por defecto es INFO, ya que la historia solo fija `local` y
  `production`.
- `/docs` en `test` se comporta como en `local` (activo), para poder probar su presencia y su
  ausencia.
- El commit lo informa la plataforma de despliegue (Render) mediante su variable de entorno; el
  health check actual ya lo expone y se conserva su formato.
- La ruta del health check de Render se configura como `/health/live`, y el job de despliegue
  consulta `/health` tras cada despliegue; esa configuración se documenta como parte de la historia.
- La comprobación de la base es una consulta mínima, sin tablas de negocio (las migraciones de
  tablas están fuera de alcance).
- El proveedor `fake` solo se declara como opción de configuración; el comportamiento de la IA
  pertenece a otras historias.
- Las variables de Telegram ya documentadas en `.env.example` se conservan.
- Fuera de alcance: modelos de negocio, migraciones de tablas, login y la conexión del proyecto con
  herramientas de la plataforma Neon.
