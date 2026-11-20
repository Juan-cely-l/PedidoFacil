# Especificación: PED-15 · HU-07 Acceso protegido del dueño

**Rama**: `feature/PED-15-acceso-protegido`

**Creada**: 2026-11-18

**Estado**: Borrador

**Entrada**: descripción del usuario: "Acceso protegido del dueño (PED-15, HU-07). Como dueño,
quiero entrar con mi cuenta de Google, para que solo yo pueda ver y gestionar mi catálogo, mis
cotizaciones y mis pedidos. Criterios: entro con mi cuenta de Google y la aplicación no guarda
contraseñas; solo los correos de la lista blanca pueden entrar: un correo válido de Google que no
esté en ella recibe un rechazo claro y no crea sesión; todas las rutas de gestión exigen sesión y,
sin ella, redirigen al login; puedo cerrar sesión; la sesión sobrevive a un reinicio del servidor
y caduca sola. /health y /health/live siguen públicos (Render los usa como health check); la
página de login también es pública; todo lo demás, incluido /productos y su detalle, exige
sesión. Reglas de la constitución 1.2.0: Google OAuth 2.0 (OIDC), lista blanca en OWNER_EMAILS,
cookie de sesión httponly, samesite=lax y secure en producción, tokens fuera de logs y mensajes
de error, pruebas sin llamar a Google. Fuera de alcance: registro de usuarios, recuperación de
contraseña, roles y permisos, varios usuarios simultáneos. La ruta exacta de redirección y la
duración de la sesión se deciden en el plan."

## Escenarios de usuario y pruebas *(obligatorio)*

### Historia 1 - Entrar con la cuenta de Google (Prioridad: P1)

El dueño abre la aplicación, elige «Entrar con Google», se identifica en Google y vuelve a la
aplicación con su sesión iniciada, en la página que quería ver.

**Por qué esta prioridad**: sin entrada no hay forma de usar la aplicación una vez protegida; es
el camino principal y habilita llevar datos personales de clientes a producción (límite del
riesgo aceptado el 2026-11-16).

**Prueba independiente**: con el proveedor de identidad simulado, completar el inicio de sesión
con un correo autorizado y verificar que se puede abrir el catálogo.

**Escenarios de aceptación**:

1. **Dado** que el dueño no tiene sesión, **cuando** abre la página de login, **entonces** ve la
   opción «Entrar con Google» y ningún campo de contraseña.
2. **Dado** que el dueño elige «Entrar con Google» y Google confirma un correo verificado que está
   en la lista blanca, **cuando** vuelve a la aplicación, **entonces** queda con sesión iniciada y
   ve su nombre o correo en la navegación.
3. **Dado** que el dueño intentó abrir `/productos` sin sesión y fue enviado al login, **cuando**
   completa el inicio de sesión, **entonces** llega a `/productos` y no a una página genérica.
4. **Dado** que el dueño ya tiene sesión, **cuando** abre la página de login, **entonces** se le
   lleva directamente al catálogo.

---

### Historia 2 - Rechazar a quien no está autorizado (Prioridad: P1)

Cualquier persona tiene cuenta de Google. Si alguien que no es el dueño completa el inicio de
sesión con Google, la aplicación le dice con claridad que no tiene acceso y no le abre sesión.

**Por qué esta prioridad**: es la garantía de seguridad de la historia; sin ella, autenticarse
con Google bastaría para ver datos personales de clientes.

**Prueba independiente**: con el proveedor simulado, completar el inicio de sesión con un correo
verificado que no está en la lista y comprobar el mensaje y que el catálogo sigue inaccesible.

**Escenarios de aceptación**:

1. **Dado** un correo verificado por Google que no está en la lista blanca, **cuando** vuelve a la
   aplicación, **entonces** ve el mensaje «Esta cuenta de Google no tiene acceso a PedidoFácil» y
   no queda ninguna sesión: abrir `/productos` lo vuelve a enviar al login.
2. **Dado** un correo que Google no marca como verificado, **cuando** vuelve a la aplicación,
   **entonces** se rechaza igual que un correo no autorizado, aunque figure en la lista.
3. **Dado** que el dueño cancela o niega el permiso en Google, **cuando** vuelve a la aplicación,
   **entonces** ve el mensaje «No se completó el inicio de sesión con Google» en la página de login
   y no queda sesión.
4. **Dado** que la comunicación con Google falla, **cuando** vuelve a la aplicación, **entonces**
   ve un mensaje claro sin detalles técnicos ni datos del proveedor, y no queda sesión.
5. **Dado** una respuesta de inicio de sesión que no corresponde a un intento iniciado desde esta
   aplicación (por ejemplo, un enlace reutilizado o fabricado), **cuando** llega, **entonces** se
   rechaza y no crea sesión.

---

### Historia 3 - Gestión siempre protegida (Prioridad: P1)

Toda página o acción de gestión exige sesión. Sin ella, la persona es enviada al login y nada se
guarda. Los health checks y la página de login siguen abiertos.

**Por qué esta prioridad**: proteger solo algunas rutas dejaría huecos; y proteger de más los
health checks tumbaría el despliegue en Render.

**Prueba independiente**: sin sesión, recorrer todas las rutas registradas de la aplicación y
comprobar que solo las públicas responden sin redirigir al login.

**Escenarios de aceptación**:

1. **Dado** que no hay sesión, **cuando** se abre `/productos`, el detalle de un producto o el
   formulario de nuevo producto, **entonces** se redirige al login.
2. **Dado** que no hay sesión, **cuando** se envía el formulario de crear producto o de agregar
   variante, **entonces** se redirige al login y no se guarda nada.
3. **Dado** que no hay sesión, **cuando** se consultan `/health` y `/health/live`, **entonces**
   responden igual que hoy, sin redirigir.
4. **Dado** que no hay sesión, **cuando** se abre la página de login, **entonces** responde sin
   redirigir.
5. **Dado** que el correo del dueño se quita de la lista blanca mientras tiene una sesión abierta,
   **cuando** hace la siguiente petición de gestión, **entonces** se le trata como sin sesión.

---

### Historia 4 - Cerrar sesión y caducidad (Prioridad: P2)

El dueño puede cerrar sesión desde cualquier página de gestión. Si no lo hace, la sesión caduca
sola después de un tiempo. Un reinicio o un nuevo despliegue del servidor no cierra su sesión.

**Por qué esta prioridad**: el dueño puede usar equipos compartidos; pero sin esta historia el
acceso ya está protegido por las historias 1 a 3.

**Prueba independiente**: iniciar sesión, cerrarla y verificar que el catálogo vuelve a exigir
login; con el reloj simulado, verificar que la sesión deja de valer al cumplirse su duración.

**Escenarios de aceptación**:

1. **Dado** que el dueño tiene sesión, **cuando** elige «Cerrar sesión», **entonces** vuelve a la
   página de login con el mensaje «Cerraste sesión» y abrir `/productos` exige entrar de nuevo.
2. **Dado** que el dueño tiene sesión, **cuando** el servidor se reinicia o se despliega una nueva
   versión, **entonces** su sesión sigue vigente.
3. **Dado** que el dueño inició sesión, **cuando** se cumple la duración máxima definida en el
   plan, **entonces** la siguiente petición de gestión lo envía al login.

---

### Casos límite

- Correos de la lista con mayúsculas o espacios («  Dueno@Gmail.com ») coinciden con el correo
  que entrega Google sin distinguir mayúsculas ni espacios.
- La lista blanca puede tener varios correos (por ejemplo, el dueño con dos cuentas), aunque haya
  un solo dueño.
- Lista blanca vacía o ausente: en producción la aplicación no arranca y el error nombra la
  variable que falta, igual que con las demás variables obligatorias.
- La página a la que se vuelve tras el login solo puede ser una ruta de la propia aplicación;
  cualquier otra (un dominio externo) se ignora y se va al catálogo.
- Cerrar sesión no se puede provocar desde otro sitio: la acción exige una petición de la propia
  aplicación.
- Una sesión caducada o alterada se trata como si no hubiera sesión, sin errores visibles.
- Los mensajes de error del login nunca muestran tokens, códigos del proveedor ni detalles
  técnicos.

## Requisitos *(obligatorio)*

### Requisitos funcionales

- **FR-001**: El dueño DEBE poder iniciar sesión con su cuenta de Google; la aplicación NO DEBE
  pedir ni guardar contraseñas.
- **FR-002**: Solo DEBEN obtener sesión los correos verificados por Google que estén en la lista
  blanca configurada; la comparación ignora mayúsculas y espacios al inicio y al final.
- **FR-003**: Un correo no autorizado, no verificado, una cancelación en Google, un fallo de
  comunicación o una respuesta que no corresponda a un intento propio DEBEN terminar en la página
  de login con un mensaje claro en español y sin sesión.
- **FR-004**: Toda ruta de gestión (consultas y acciones) DEBE exigir sesión; sin ella, DEBE
  redirigir al login sin ejecutar la acción.
- **FR-005**: `/health`, `/health/live` y la página de login (con su paso de vuelta desde Google)
  DEBEN ser públicos.
- **FR-006**: Tras iniciar sesión, el dueño DEBE volver a la página de la aplicación que intentó
  abrir; si no había ninguna, o no es una ruta propia, al catálogo.
- **FR-007**: El dueño DEBE poder cerrar sesión desde cualquier página de gestión; al hacerlo, la
  sesión deja de valer de inmediato.
- **FR-008**: La sesión DEBE seguir vigente tras un reinicio o un nuevo despliegue del servidor y
  DEBE caducar sola al cumplirse una duración máxima (definida en el plan).
- **FR-009**: En cada petición de gestión, el correo de la sesión DEBE seguir estando en la lista
  blanca; si ya no está, se trata como sin sesión.
- **FR-010**: La sesión NO DEBE ser legible por el código de las páginas, NO DEBE enviarse en
  peticiones iniciadas desde otros sitios (salvo la navegación normal hacia la aplicación) y, en
  producción, solo DEBE viajar por conexiones cifradas (constitución, principio VI).
- **FR-011**: Los tokens que entrega el proveedor de identidad NO DEBEN aparecer en logs, en
  mensajes de error ni en la sesión más allá de lo necesario para identificar al dueño.
- **FR-012**: En producción, la aplicación NO DEBE arrancar si falta la lista blanca o la
  configuración del proveedor de identidad; el error nombra lo que falta sin mostrar valores.
- **FR-013**: Las pruebas automatizadas DEBEN cubrir el inicio de sesión, el rechazo y el cierre
  sin comunicarse con Google (constitución, principio II).
- **FR-014**: La navegación DEBE mostrar, con sesión, quién está conectado y la opción de cerrar
  sesión.

### Entidades clave

- **Sesión del dueño**: identifica a quien entró. Atributos: correo verificado, nombre para
  mostrar, momento de inicio. No guarda contraseñas ni tokens del proveedor.
- **Lista blanca de correos**: configuración del despliegue (no una tabla) con los correos que
  pueden entrar.

## Criterios de éxito *(obligatorio)*

### Resultados medibles

- **SC-001**: El dueño autorizado entra en menos de 30 segundos desde la página de login, sin
  contar el tiempo que tarde en identificarse dentro de Google.
- **SC-002**: El 100 % de las rutas de gestión, recorridas sin sesión, redirigen al login, y
  ninguna acción sin sesión guarda datos.
- **SC-003**: 0 sesiones creadas para correos fuera de la lista blanca o no verificados.
- **SC-004**: `/health` y `/health/live` responden sin sesión el 100 % de las veces; el despliegue
  en Render no cambia de estado por esta historia.
- **SC-005**: Ningún token del proveedor aparece en logs ni en respuestas, verificado con valores
  centinela en las pruebas.
- **SC-006**: Una sesión abierta sigue valiendo tras reiniciar el servidor y deja de valer al
  cumplirse su duración máxima.

## Supuestos

- La duración máxima de la sesión y la ruta exacta de vuelta desde Google se fijan en el plan, no
  aquí.
- «Sobrevive a un reinicio» requiere una clave de sesión fija: en producción ya la da
  `SECRET_KEY`. En local, si no se define, la clave cambia en cada arranque y la sesión se pierde
  al reiniciar; es aceptable para desarrollo.
- En la aplicación aún no hay manejo de sesión: hoy solo existe la configuración de la clave
  (`SECRET_KEY`). Esta historia lo agrega.
- La documentación interactiva de la API solo existe fuera de producción y queda como está.
- Para usar el login en local hace falta un cliente OAuth de Google con la dirección local
  registrada (ADR 0003); las pruebas no lo necesitan.
- Cotizaciones y pedidos aún no existen: cuando se construyan, sus rutas nacen protegidas por la
  misma regla (FR-004).
- Fuera de alcance: registro de usuarios, recuperación de contraseña, roles y permisos, y varias
  personas con sesión a la vez con permisos distintos.
