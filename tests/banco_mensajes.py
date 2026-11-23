"""Banco de mensajes de PED-16: la entrada de las pruebas de extracción y del script de medición.

Es el oráculo de SC-008 (al menos 80 % de productos, variantes y cantidades correctos) y de las
pruebas de `build_lines` (research.md R14). Por eso:

- **Catálogos propios y fijos**: el banco no usa el catálogo de producción. Las pruebas y
  `scripts/medir_gemini.py` resuelven contra estos mismos ids, así que los resultados son
  reproducibles. Hay un catálogo por negocio, porque cada mensaje se cotiza contra el catálogo de
  quien lo recibe.
- **Ningún mensaje de este banco es real.** Es una limitación de SC-008 y viaja con el banco:
  - `"E01"` y `"E02"`: escritos a partir del **perfil** de los casos E01 (repostería) y E02
    (accesorios) del kit de descubrimiento (PED-66) y de la propuesta (PED-67), es decir, de qué
    datos pide cada negocio y qué error se observó. No están copiados de mensajes de clientes:
    esos dos casos son **simulados, con datos inventados**, y no registran mensajes textuales.
  - `"inventado"`: escrito para cubrir un caso que E01 y E02 no muestran.

  Un acierto medido con este banco dice cómo extrae el modelo mensajes plausibles, no cómo
  extrae los de clientes reales. Se declara así en cualquier reporte de SC-008.
- **Estilo de WhatsApp**: minúsculas, sin tildes, cantidades en palabras, varios productos por
  frase, fechas relativas y errores de escritura.

Regla de puntuación (fijada el 2026-11-21, antes de medir; research.md R14):

- un ítem esperado es correcto si hay una línea, no usada por otro ítem, con el mismo estado,
  producto y variante, y con la misma cantidad cuando la cantidad esperada no es `None`;
- una línea que no corresponde a ningún ítem esperado es sobrante;
- acierto = correctos / (esperados + sobrantes), entre 0.0 y 1.0;
- caso límite: con esperados = 0 y sobrantes = 0, el acierto es 1.0 (un mensaje que no es un
  pedido y no produjo líneas); con esperados = 0 y algún sobrante, el acierto es 0.0.

Los precios no se puntúan: ningún `ItemEsperado` lleva precio, porque el precio nunca sale de la
IA ni del mensaje. Las pruebas verifican aparte que cada línea «Lista» lleva el `unit_price` de su
ítem del catálogo (caso R10).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models.catalog import QuotableItem
from app.services.quotes import LineDraft

Negocio = Literal["reposteria", "accesorios"]
Origen = Literal["E01", "E02", "inventado"]
Estado = Literal["lista", "por_revisar"]
Motivo = Literal["no_reconocido", "falta_variante", "cantidad_invalida"]


@dataclass(frozen=True)
class ItemEsperado:
    """Lo que el código debe producir para un pedido del mensaje.

    `quantity=None` significa que la cantidad no se evalúa: el cliente no la dio de forma
    precisa o el ítem no está en el catálogo.
    """

    product_id: int | None
    variant_id: int | None
    quantity: int | None
    status: Estado = "lista"
    review_reason: Motivo | None = None


@dataclass(frozen=True)
class CasoBanco:
    """Un mensaje del banco, con su negocio, su procedencia y lo esperado."""

    id: str
    negocio: Negocio
    origen: Origen
    texto: str
    esperado: tuple[ItemEsperado, ...]


@dataclass(frozen=True)
class Acierto:
    """Resultado de comparar las líneas producidas con lo esperado."""

    esperados: int
    correctos: int
    sobrantes: int

    @property
    def valor(self) -> float:
        """Correctos sobre esperados más sobrantes, de 0.0 a 1.0; 1.0 si no había nada."""
        total = self.esperados + self.sobrantes
        return 1.0 if total == 0 else self.correctos / total


def _item(product_id: int, variant_id: int | None, label: str, unit_price: int) -> QuotableItem:
    return QuotableItem(
        product_id=product_id, variant_id=variant_id, label=label, unit_price=unit_price
    )


# Ids de repostería: productos 1 a 9, variantes 101 a 112.
CATALOGO_REPOSTERIA: list[QuotableItem] = [
    _item(1, 101, "Torta de chocolate — Tamaño: Pequeña", 35000),
    _item(1, 102, "Torta de chocolate — Tamaño: Mediana", 45000),
    _item(1, 103, "Torta de chocolate — Tamaño: Grande", 60000),
    _item(2, 104, "Torta de zanahoria — Tamaño: Mediana", 42000),
    _item(2, 105, "Torta de zanahoria — Tamaño: Grande", 58000),
    _item(3, 106, "Torta de tres leches — Tamaño: Mediana", 40000),
    _item(3, 107, "Torta de tres leches — Tamaño: Grande", 55000),
    _item(4, 108, "Cupcake — Sabor: Vainilla", 4000),
    _item(4, 109, "Cupcake — Sabor: Chocolate", 4500),
    _item(4, 110, "Cupcake — Sabor: Red velvet", 5000),
    _item(5, None, "Alfajor", 2500),
    _item(6, None, "Galleta de avena", 1500),
    _item(7, None, "Brownie", 4000),
    _item(8, 111, "Postre de maracuyá — Tamaño: Individual", 7000),
    _item(8, 112, "Postre de maracuyá — Tamaño: Familiar", 32000),
    _item(9, None, "Pan de banano", 18000),
]

# Ids de accesorios: productos 21 a 28, variantes 201 a 211.
CATALOGO_ACCESORIOS: list[QuotableItem] = [
    _item(21, 201, "Aretes de argolla — Color: Dorado", 18000),
    _item(21, 202, "Aretes de argolla — Color: Plateado", 18000),
    _item(22, 203, "Collar de perlas — Color: Blanco", 35000),
    _item(22, 204, "Collar de perlas — Color: Rosado", 35000),
    _item(23, 205, "Pulsera tejida — Color: Negro", 12000),
    _item(23, 206, "Pulsera tejida — Color: Rojo", 12000),
    _item(23, 207, "Pulsera tejida — Color: Azul", 12000),
    _item(24, None, "Anillo ajustable", 15000),
    _item(25, 208, "Diadema de tela — Color: Beige", 9000),
    _item(25, 209, "Diadema de tela — Color: Negro", 9000),
    _item(26, None, "Scrunchie de satín", 5000),
    _item(27, None, "Llavero personalizado", 8000),
    _item(28, 210, "Bolso de mano — Color: Negro", 65000),
    _item(28, 211, "Bolso de mano — Color: Camel", 65000),
]

CATALOGOS: dict[Negocio, list[QuotableItem]] = {
    "reposteria": CATALOGO_REPOSTERIA,
    "accesorios": CATALOGO_ACCESORIOS,
}

_NO_RECONOCIDO = ItemEsperado(None, None, None, "por_revisar", "no_reconocido")

MENSAJES: tuple[CasoBanco, ...] = (
    # --- Repostería ------------------------------------------------------------------------
    # E01: el caso pide sabor, tamaño, dedicatoria, hora y modalidad; la dedicatoria no es un
    # producto y la hora es justo el dato que E01 omitió al registrar.
    CasoBanco(
        id="R01",
        negocio="reposteria",
        origen="E01",
        texto=(
            "hola buenas, necesito una torta de chocolate mediana pa el sabado a las 4 de la "
            "tarde, que diga feliz cumple mami. la recojo yo"
        ),
        esperado=(ItemEsperado(1, 102, 1),),
    ),
    # E01: varios productos en una frase, con dirección y fecha relativa.
    CasoBanco(
        id="R02",
        negocio="reposteria",
        origen="E01",
        texto=(
            "buenas tardes quisiera encargar dos tortas de tres leches grandes y una de "
            "zanahoria mediana para mañana, me las mandan a la cra 15 # 80-20"
        ),
        esperado=(ItemEsperado(3, 107, 2), ItemEsperado(2, 104, 1)),
    ),
    # E01: ambiguo entre variantes (no dice el tamaño): «falta la presentación».
    CasoBanco(
        id="R03",
        negocio="reposteria",
        origen="E01",
        texto="hola!! me regalas el precio de una torta de chocolate para el viernes",
        esperado=(ItemEsperado(1, None, 1, "por_revisar", "falta_variante"),),
    ),
    # E01: errores de escritura, día del mes y abono (dato que E01 exige registrar).
    CasoBanco(
        id="R04",
        negocio="reposteria",
        origen="E01",
        texto=(
            "hola kiero 1 torta de zanaoria grande y 4 cupcaques de chocolate, es pa el 28 a "
            "las 10 am, dejo abono de la mitad"
        ),
        esperado=(ItemEsperado(2, 105, 1), ItemEsperado(4, 109, 4)),
    ),
    # Inventado: «media docena» y «una docena» en la misma frase.
    CasoBanco(
        id="R05",
        negocio="reposteria",
        origen="inventado",
        texto="porfa media docena de cupcakes red velvet y una docena de alfajores",
        esperado=(ItemEsperado(4, 110, 6), ItemEsperado(5, None, 12)),
    ),
    # Inventado: sin cantidad explícita (se asume 1 y se marca para confirmar).
    CasoBanco(
        id="R06",
        negocio="reposteria",
        origen="inventado",
        texto="quiero el pan de banano para hoy en la tarde",
        esperado=(ItemEsperado(9, None, 1),),
    ),
    # Inventado: cantidades aproximadas en palabras («unas veinte», «un par»). Se espera 20:
    # el dueño confirma la cantidad exacta en el borrador.
    CasoBanco(
        id="R07",
        negocio="reposteria",
        origen="inventado",
        texto="necesito unas veinte galletas de avena y un par de brownies pa mañana temprano",
        esperado=(ItemEsperado(6, None, 20), ItemEsperado(7, None, 2)),
    ),
    # Inventado: un producto fuera del catálogo (torta de fondant) junto a uno que sí está.
    CasoBanco(
        id="R08",
        negocio="reposteria",
        origen="inventado",
        texto=(
            "buenas, ustedes hacen tortas de fondant con figuras? y me separan tambien 3 "
            "postres de maracuya individuales"
        ),
        esperado=(_NO_RECONOCIDO, ItemEsperado(8, 111, 3)),
    ),
    # Inventado: no es un pedido. Es el mensaje más común en el WhatsApp de un negocio y donde un
    # modelo está más tentado de inventar líneas: no debe salir ninguna, ni «Por revisar».
    CasoBanco(
        id="R09",
        negocio="reposteria",
        origen="inventado",
        texto="buenas tardes, estan abiertos hoy?",
        esperado=(),
    ),
    # Inventado: el cliente menciona un precio. El precio de la línea sale del catálogo, nunca
    # del mensaje (principio V); es el antecedente de la inyección que enfrentará HU-20. El
    # mensaje dice 40 mil y el catálogo 45.000 a propósito: una línea con 45000 prueba que el
    # precio salió del catálogo; una con 40000 delataría que salió del mensaje.
    CasoBanco(
        id="R10",
        negocio="reposteria",
        origen="inventado",
        texto="hola, me dijeron que la torta de chocolate mediana estaba en 40 mil, me la llevo",
        esperado=(ItemEsperado(1, 102, 1),),
    ),
    # --- Accesorios ------------------------------------------------------------------------
    # E02: el cliente llega desde Instagram y elige color, el dato que E02 confundió.
    CasoBanco(
        id="A01",
        negocio="accesorios",
        origen="E02",
        texto="hola vi en insta los aretes de argolla, me mandas 2 pares en dorado?",
        esperado=(ItemEsperado(21, 201, 2),),
    ),
    # E02: dos colores del mismo modelo, con modalidad y fecha relativa.
    CasoBanco(
        id="A02",
        negocio="accesorios",
        origen="E02",
        texto=(
            "buenas quiero la pulsera tejida azul y la negra, una de cada una, para recoger "
            "el lunes"
        ),
        esperado=(ItemEsperado(23, 207, 1), ItemEsperado(23, 205, 1)),
    ),
    # E02: ambiguo entre variantes (no dice el color) y cantidad implícita («me lo llevo»).
    CasoBanco(
        id="A03",
        negocio="accesorios",
        origen="E02",
        texto="cuanto vale el collar de perlas? me lo llevo",
        esperado=(ItemEsperado(22, None, None, "por_revisar", "falta_variante"),),
    ),
    # E02: una medida («talla 7») que no es una variante del catálogo: no debe inventarla.
    CasoBanco(
        id="A04",
        negocio="accesorios",
        origen="E02",
        texto=(
            "necesito un anillo ajustable talla 7 y un llavero personalizado con la letra m, "
            "pa pasado mañana"
        ),
        esperado=(ItemEsperado(24, None, 1), ItemEsperado(27, None, 1)),
    ),
    # Inventado: un producto fuera del catálogo (billetera) junto a uno que sí está.
    CasoBanco(
        id="A05",
        negocio="accesorios",
        origen="inventado",
        texto="hola tienen billeteras de cuero? y tambien quiero tres scrunchies de satin",
        esperado=(_NO_RECONOCIDO, ItemEsperado(26, None, 3)),
    ),
    # Inventado: errores de escritura, varios productos y envío con fecha relativa.
    CasoBanco(
        id="A06",
        negocio="accesorios",
        origen="inventado",
        texto="porfa un bolzo de mano camel y dos diademas de tela beige, envio a soacha el sabado",
        esperado=(ItemEsperado(28, 211, 1), ItemEsperado(25, 208, 2)),
    ),
    # Inventado: nada del mensaje está en el catálogo (escenario 2.5 de la spec).
    CasoBanco(
        id="A07",
        negocio="accesorios",
        origen="inventado",
        texto="hola hacen gorras bordadas? necesito como quince para un evento de la empresa",
        esperado=(_NO_RECONOCIDO,),
    ),
)


def _acierta(item: ItemEsperado, linea: LineDraft) -> bool:
    """Una línea acierta un ítem si coinciden estado, producto, variante y, si importa, cantidad."""
    return (
        linea.status == item.status
        and linea.product_id == item.product_id
        and linea.variant_id == item.variant_id
        and (item.quantity is None or linea.quantity == item.quantity)
    )


def puntuar(esperado: tuple[ItemEsperado, ...], lineas: list[LineDraft]) -> Acierto:
    """Compara las líneas producidas con lo esperado, con la regla del docstring del módulo.

    Cada línea acierta como mucho un ítem; las que no aciertan ninguno son sobrantes.
    """
    libres = list(lineas)
    correctos = 0
    for item in esperado:
        linea = next((linea for linea in libres if _acierta(item, linea)), None)
        if linea is not None:
            libres.remove(linea)
            correctos += 1
    return Acierto(esperados=len(esperado), correctos=correctos, sobrantes=len(libres))
