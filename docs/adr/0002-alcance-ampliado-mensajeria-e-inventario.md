# ADR 0002: Alcance ampliado con mensajería e inventario

## Estado

Aceptado, 2026-11-11.

Complementa el [ADR 0001](0001-stack-tecnologico.md): el stack que allí se fija se mantiene y
este ADR solo le agrega piezas. Reemplaza las menciones del ADR 0001 a la página pública de
consulta, que deja de formar parte del alcance.

## Contexto

El alcance de PedidoFácil se amplió (constitución v1.1.0). Ahora la aplicación atiende los
pedidos desde el primer mensaje del cliente:

- **Catálogo e inventario**, con registro de compras y alertas de stock bajo.
- **Cotización con IA**: la IA identifica los productos que pide el cliente y la aplicación arma
  la cotización con los precios y la disponibilidad del inventario.
- **Envío por WhatsApp o Telegram** de la cotización y, cuando el cliente la acepta, conversión
  en pedido con descuento del inventario.
- **Bot de Telegram** que atiende solo a los clientes.
- Ya no existe la página pública de seguimiento.

Restricciones que condicionan las decisiones:

- **Tiempo**: quedan 18 días hasta la entrega (2026-11-29), para una sola persona.
- **TDD y pruebas sin red** (constitución, principios I y II): cada integración externa debe
  poder simularse de forma determinista.
- **Costo cero**: ninguna integración puede exigir pagos ni trámites empresariales.
- **La IA asiste, el humano decide** (principio V): los datos que llegan al cliente, sobre todo
  los precios, deben ser verificables.

## Opciones consideradas

### Integración con Telegram

| Opción | A favor | En contra |
|---|---|---|
| **Bot API con `httpx` y webhook en FastAPI** | El webhook es un endpoint más de FastAPI, con las mismas capas y pruebas que el resto; `httpx.MockTransport` simula la API sin red; sin dependencias nuevas de bots. | Hay que modelar a mano las pocas partes de la Bot API que se usan (actualizaciones y envío de mensajes). |
| python-telegram-bot | Librería madura que cubre toda la Bot API. | Trae su propio ciclo de ejecución, que choca con el de FastAPI, y es difícil de simular en las pruebas. |
| aiogram | Asíncrona y completa. | Mismo problema: ciclo de ejecución y despachador propios que chocan con FastAPI y complican las pruebas. |

### Envío por WhatsApp

| Opción | A favor | En contra |
|---|---|---|
| **Enlaces `wa.me` (y `t.me/share` para Telegram) desde la web** | Sin cuenta, costo ni credenciales; el dueño envía el mensaje ya armado desde su propio teléfono; se prueba verificando el enlace generado. | El envío no es automático: requiere un clic del dueño. |
| API oficial de WhatsApp Cloud | Envío automático y recepción de mensajes. | Requiere una cuenta de empresa verificada y tiene costo por conversación; trámite inviable en el plazo y contrario al costo cero. |

### Cálculo de la cotización

| Opción | A favor | En contra |
|---|---|---|
| **La IA identifica productos, variantes y cantidades; el código calcula precios y totales desde el catálogo** | Los precios salen siempre del catálogo y los totales son verificables con pruebas unitarias; los productos no reconocidos quedan marcados en vez de inventados. | Requiere emparejar lo que entiende la IA con los productos del catálogo. |
| La IA genera la cotización completa | Menos código propio. | La IA puede inventar precios y sus totales no son verificables; incumple el principio V. |

### Representación de montos

| Opción | A favor | En contra |
|---|---|---|
| **Enteros en pesos colombianos** | Aritmética exacta; el peso no usa centavos en la práctica; se compara con igualdad en las pruebas. | Si algún día se necesitaran fracciones habría que migrar el tipo. |
| `float` | Nativo y cómodo. | Errores de redondeo binario en sumas y multiplicaciones; totales que no cuadran. |

## Decisión

Se agregan al stack del ADR 0001, y la constitución (principios II, IV, V y VI) las fija como
obligatorias:

- **Bot API de Telegram con llamadas directas con `httpx`** y un webhook en FastAPI, sin librerías
  de bots; en pruebas, `httpx.MockTransport`. El webhook valida la cabecera
  `X-Telegram-Bot-Api-Secret-Token`.
- **Envío desde la web con enlaces `wa.me` y `t.me/share`**; la API oficial de WhatsApp queda
  fuera del alcance.
- **La IA identifica, el código calcula**: la IA nunca fija precios ni totales.
- **Montos como enteros en pesos colombianos**, nunca `float`; el descuento de inventario se hace
  dentro de una transacción.
- Los pedidos creados por el bot quedan «Por confirmar» y no descuentan inventario hasta que el
  dueño los confirma.

## Consecuencias

**Positivas**

- Todas las integraciones nuevas se prueban sin red: Telegram con `httpx.MockTransport`, la IA
  con `TestModel`/`FunctionModel` y los enlaces de WhatsApp como texto.
- Sin costos ni trámites con terceros más allá de crear el bot en Telegram.
- Los precios y totales son exactos y verificables, y nunca dependen de la IA.
- Al desaparecer la página pública, se reduce la superficie expuesta de datos personales.

**Negativas y riesgos**

- **Alcance frente a capacidad**: el backlog suma 48 SP frente a una capacidad estimada de unos
  38 SP. Regla de recorte: según la velocidad real del Sprint 1, se recortan HU-19 y HU-20.
- El webhook de Telegram es un endpoint público: depende de validar el secreto y de no filtrar
  datos ajenos ni internos en los mensajes (principio VI).
- El envío por WhatsApp no es automático; el bot solo existe en Telegram.
- La Bot API se modela a mano: si se usaran más funciones habría que ampliar ese código propio.
- Cambiar cualquiera de estas piezas requiere un nuevo ADR y una enmienda de la constitución.
