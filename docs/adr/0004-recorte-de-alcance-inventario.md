# ADR 0004: Recorte de alcance: sin inventario ni alertas de stock

## Estado

Aceptado, 18/11/2026; registrado el 20/11/2026.

La decisión se tomó en la planificación del Sprint 2 y quedó registrada en los comentarios de
PED-90 y PED-93 en Jira. El 20/11/2026 es la fecha en que se registra este ADR y se enmienda la
constitución (versión 1.3.0: preámbulo y principios IV, V y VI).

Reemplaza la parte de inventario del [ADR 0002](0002-alcance-ampliado-mensajeria-e-inventario.md).
En concreto, deja sin efecto tres puntos:

- el catálogo con inventario, registro de compras y alertas de stock bajo;
- la cotización con la disponibilidad del inventario;
- el descuento de inventario, dentro de una transacción, al convertir en pedido, y la regla de que
  los pedidos del bot no lo descuentan hasta que el dueño los confirma.

El resto del ADR 0002 se mantiene: Telegram con `httpx`, envío con `wa.me` y `t.me/share`, «la IA
identifica, el código calcula» y montos en pesos enteros.

## Contexto

En la planificación del Sprint 2, el 18/11/2026, había tres hechos sobre la mesa:

- **Velocidad**: el Sprint 1 cerró con 7 SP completados frente a 20 comprometidos.
- **Sprint 3 ya ocupado**: unas 17 horas del Sprint 3 están reservadas para el informe, las
  evidencias, la trazabilidad, el video, la presentación y la validación con usuarios. Queda muy
  poca capacidad para historias nuevas.
- **Bot irrenunciable**: el dueño del producto declaró irrenunciable el bot de Telegram (HU-20).
  Por eso el orden de recorte tuvo que fijarse por anticipado, para que ningún recorte posterior
  alcanzara al bot.

`docs/proceso.md` preveía una regla de recorte para velocidades menores de 15 SP: HU-19 solo con
alertas en el panel y el bot solo cotizando. Con 7 SP, ese recorte no alcanzaba, y además tocaba
al bot.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| Mantener el alcance completo | Cumple el backlog original. | Con 7 SP de velocidad frente a 20 comprometidos y un Sprint 3 ocupado por la entrega académica, no es realizable. Pone en riesgo las historias del núcleo y la entrega. |
| Aplicar la regla de recorte prevista en `docs/proceso.md` (alertas solo en el panel; el bot solo cotiza) | Recorte pequeño y ya acordado. | Insuficiente para una velocidad de 7 SP: conserva el inventario y las compras (HU-18), que son la mayor parte del trabajo de stock. Además, recorta el bot, que es irrenunciable. |
| **Retirar HU-18 y HU-19 completas** | Libera el trabajo de existencias, compras, descuento transaccional y alertas. Las historias del núcleo, incluido el bot, quedan intactas. | El producto deja de saber si hay unidades: el dueño valida la disponibilidad por su cuenta antes de enviar la cotización. |

## Decisión

**HU-18 (inventario y compras) y HU-19 (alertas de stock bajo) salen del alcance del proyecto.**
La aplicación no lleva existencias, no registra compras, no descuenta inventario al convertir en
pedido y no alerta de stock bajo.

Lo que esto implica para las demás historias:

- **Cotizable** es lo que está activo en el catálogo. No se miran unidades disponibles.
- **HU-08**: no valida unidades ni marca productos sin stock. Los productos no reconocidos se
  siguen marcando para revisión (principio V).
- **HU-17**: convertir una cotización en pedido no descuenta nada.
- **HU-20**: el bot responde solo si reconoció todos los productos, sin condición de
  disponibilidad. Sus pedidos siguen quedando «Por confirmar» hasta que el dueño los confirma.

## Consecuencias

**Positivas**

- El esfuerzo restante se concentra en el recorrido del mensaje a la cotización y al pedido.
- Desaparece la parte más delicada del modelo de datos: el descuento transaccional y la
  concurrencia sobre existencias.
- Las especificaciones nuevas no tienen que contemplar estados de stock.

**Negativas y riesgos**

- El dueño puede enviar una cotización por algo que no tiene. Mitigación: la cotización es un
  borrador que el dueño revisa antes de enviarla (principio V).
- El bot puede ofrecer productos agotados. Mitigación: sus pedidos quedan «Por confirmar» y el
  dueño decide.
- Los issues de Jira de HU-18 y HU-19 y las menciones al inventario en otras historias (por
  ejemplo, HU-08) deben actualizarse para reflejar el recorte.
- La regla de recorte de `docs/proceso.md` queda superada por esta decisión, y el documento lo
  indica.
- Recuperar el inventario más adelante requiere un nuevo ADR y una enmienda de la constitución.
