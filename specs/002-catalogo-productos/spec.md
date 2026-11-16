# Especificación: PED-88 · HU-15 Catálogo de productos

**Rama**: `feature/PED-88-catalogo-productos`

**Creada**: 2026-11-16

**Estado**: Borrador

**Entrada**: descripción del usuario: "PED-88 · HU-15 Catálogo de productos. Como dueño, quiero
registrar mis productos con sus variantes y precios, para que las cotizaciones usen siempre mis
precios reales. Criterios: puedo crear, editar, consultar y desactivar productos con nombre,
descripción corta y precio en pesos (entero mayor que cero); un producto puede tener variantes
(sabor, peso, color, marca o tamaño), cada una con su propio precio si difiere; cada producto
indica si controla inventario; un producto desactivado no aparece en cotizaciones nuevas pero se
conserva en pedidos anteriores; no se permiten dos productos activos con el mismo nombre y
variante. Fuera de alcance: fotos, categorías, importación desde Excel y las unidades disponibles
(eso es HU-18)."

## Escenarios de usuario y pruebas *(obligatorio)*

### Historia 1 - Registrar y consultar productos (Prioridad: P1)

El dueño entra al catálogo, registra un producto con nombre, descripción corta, precio en pesos e
indica si controla inventario. Luego ve el producto en el listado del catálogo y puede abrir su
detalle.

**Por qué esta prioridad**: sin productos registrados no hay precios reales que cotizar; es la
base de todo el flujo de cotización.

**Prueba independiente**: se crea un producto desde el catálogo y se verifica que aparece en el
listado con sus datos exactos; entrega valor por sí sola como lista de precios del negocio.

**Escenarios de aceptación**:

1. **Dado** el catálogo, **cuando** el dueño registra «Brownie», descripción «Brownie de
   chocolate», precio 5000 y «controla inventario» activado, **entonces** el producto queda activo
   y aparece en el listado con esos datos.
2. **Dado** el formulario de nuevo producto, **cuando** el precio se escribe «45.000», «45 000» o
   «45000», **entonces** en los tres casos se guarda 45000.
3. **Dado** el formulario de nuevo producto, **cuando** el precio es 0, negativo, lleva coma
   decimal («45,5») o no es numérico, **entonces** no se guarda y se muestra el mensaje «El precio
   debe ser un número entero mayor que cero».
4. **Dado** el formulario de nuevo producto, **cuando** el precio usa puntos que no agrupan
   exactamente tres dígitos («45.00» o «4.5»), **entonces** no se guarda y se muestra el mensaje
   «Usa el punto solo para separar miles, por ejemplo 45.000; los pesos no llevan centavos».
5. **Dado** el formulario de nuevo producto, **cuando** el nombre está vacío, **entonces** no se
   guarda y se indica que el nombre es obligatorio.
6. **Dado** varios productos registrados, **cuando** el dueño consulta el catálogo, **entonces** ve
   los productos activos ordenados por nombre, con su precio y si controlan inventario.

---

### Historia 2 - Variantes con precio propio (Prioridad: P2)

El dueño agrega variantes a un producto (por ejemplo, Torta: sabor «Chocolate», sabor «Vainilla»;
Café: peso «250 g», peso «500 g»). Cada variante usa el precio del producto salvo que se le asigne
uno propio.

**Por qué esta prioridad**: muchos emprendimientos venden el mismo producto en presentaciones con
precio distinto; sin variantes la cotización usaría un precio equivocado.

**Prueba independiente**: se crea un producto con dos variantes, una con precio propio y otra sin
él, y se verifica que el precio efectivo de cada una es el esperado.

**Escenarios de aceptación**:

1. **Dado** el producto «Café» con precio 18000, **cuando** el dueño agrega la variante peso
   «250 g» sin precio propio, **entonces** su precio efectivo es 18000.
2. **Dado** el producto «Café», **cuando** el dueño agrega la variante peso «500 g» con precio
   32000, **entonces** su precio efectivo es 32000.
3. **Dado** una variante sin precio propio, **cuando** el dueño cambia el precio del producto a
   20000, **entonces** el precio efectivo de esa variante pasa a 20000; las variantes con precio
   propio no cambian.
4. **Dado** el formulario de variante, **cuando** el tipo no es sabor, peso, color, marca ni tamaño,
   o el valor está vacío, **entonces** no se guarda y se indica el error.
5. **Dado** el producto «Café» con la variante activa peso «500 g», **cuando** el dueño intenta
   agregar otra variante peso «500 g», **entonces** no se guarda y se indica que esa variante ya
   existe.

---

### Historia 3 - Editar y desactivar productos (Prioridad: P3)

El dueño corrige datos de un producto o variante (nombre, descripción, precio, control de
inventario) y desactiva lo que ya no vende. Puede volver a activarlo más adelante.

**Por qué esta prioridad**: los precios cambian y los productos se descontinúan; sin esto el
catálogo deja de reflejar la realidad, pero se puede trabajar unos días sin ello.

**Prueba independiente**: se edita el precio de un producto y se verifica el nuevo valor; se
desactiva y se verifica que ya no figura entre los productos disponibles para cotizar.

**Escenarios de aceptación**:

1. **Dado** el producto «Brownie» a 5000, **cuando** el dueño cambia el precio a 5500, **entonces**
   el catálogo muestra 5500 y las cotizaciones nuevas usan 5500.
2. **Dado** el producto activo «Brownie», **cuando** el dueño lo desactiva, **entonces** deja de
   estar disponible para cotizaciones nuevas y aparece como inactivo al consultar los inactivos.
3. **Dado** un producto desactivado, **cuando** el dueño consulta los inactivos, **entonces** el
   producto sigue existiendo con su nombre, sus variantes y su precio: desactivar nunca borra. Que
   los pedidos anteriores muestren los datos de su momento (FR-010) lo prueban las historias de
   cotización y pedido.
4. **Dado** el producto activo «Brownie», **cuando** el dueño intenta crear o renombrar otro
   producto como «brownie » (otras mayúsculas o espacios), **entonces** no se guarda y se indica
   que ya existe un producto activo con ese nombre.
5. **Dado** un producto inactivo «Brownie» y otro activo con el mismo nombre, **cuando** el dueño
   intenta reactivar el inactivo, **entonces** no se reactiva y se indica el conflicto.
6. **Dado** un producto activo, **cuando** el dueño desactiva una de sus variantes, **entonces** esa
   variante deja de estar disponible para cotizar y las demás siguen disponibles.

---

### Casos límite

- Precio con puntos o espacios como separadores de miles («45.000», «45 000», «1.250.000»): se
  acepta (45000, 1250000) solo si cada separador agrupa exactamente tres dígitos.
- Precio con coma («45,5» o «45,000»): se rechaza, porque en Colombia la coma es separador decimal
  y los pesos no llevan centavos.
- Precio con puntos que no agrupan tres dígitos («45.00», «4.5», «45000.000»): se rechaza con el
  mensaje «Usa el punto solo para separar miles, por ejemplo 45.000; los pesos no llevan
  centavos». Así «45.00» nunca se convierte en silencio en 4500.
- Precio muy alto: se acepta hasta 100.000.000 COP, un límite holgado para cualquier producto del
  negocio; por encima se rechaza con el mensaje «El precio supera 100.000.000; revisa si hay un
  error de digitación».
- Nombre o valor de variante con espacios al inicio o al final: se recortan antes de guardar y de
  comparar duplicados.
- Duplicados que solo difieren en mayúsculas o tildes («Té» y «te»): se consideran el mismo nombre.
  La ñ no es tilde y se conserva: «Piña» y «Pina» son nombres distintos.
- Mismo valor con distinto tipo (color «Negro» y marca «Negro»): son variantes distintas.
- Desactivar un producto desactiva para cotizar todas sus variantes, aunque cada una conserve su
  propio estado.
- Producto sin variantes: se cotiza directamente con el precio del producto.
- No hay borrado definitivo: un producto o variante creado por error se desactiva.

## Requisitos *(obligatorio)*

### Requisitos funcionales

- **FR-001**: El sistema DEBE permitir al dueño crear productos con nombre (obligatorio, máximo 100
  caracteres), descripción corta (opcional, máximo 200 caracteres), precio en pesos colombianos y
  la indicación de si controla inventario.
- **FR-002**: El precio DEBE ser un entero mayor que cero y menor o igual a 100.000.000 COP. Se
  admiten solo dígitos, opcionalmente agrupados de a tres con punto o espacio como separador de
  miles («45.000», «45 000», «45000»). Un punto que no agrupa exactamente tres dígitos («45.00»,
  «4.5») DEBE rechazarse con un mensaje que explique que el punto solo separa miles. La coma se
  rechaza siempre, porque es separador decimal y los pesos no llevan centavos. Si supera el
  máximo, el mensaje DEBE sugerir un posible error de digitación.
- **FR-003**: El sistema DEBE permitir al dueño consultar el catálogo: listado de productos activos
  ordenado por nombre, opción para ver los inactivos y detalle de cada producto con sus variantes.
- **FR-004**: El sistema DEBE permitir al dueño editar nombre, descripción, precio y control de
  inventario de un producto.
- **FR-005**: El sistema DEBE permitir agregar a un producto variantes con un tipo (sabor, peso,
  color, marca o tamaño), un valor (obligatorio, máximo 50 caracteres) y un precio propio opcional
  que cumple las mismas reglas de FR-002.
- **FR-006**: El precio efectivo de una variante DEBE ser su precio propio si lo tiene y, si no, el
  precio vigente del producto.
- **FR-007**: El sistema DEBE permitir editar, desactivar y reactivar variantes.
- **FR-008**: El sistema DEBE permitir desactivar y reactivar productos; NO DEBE permitir borrarlos
  definitivamente.
- **FR-009**: Un producto inactivo, o una variante inactiva, NO DEBE estar disponible para
  cotizaciones nuevas.
- **FR-010**: Los pedidos y cotizaciones anteriores DEBEN conservar el nombre, la variante y el
  precio que tenían al crearse, aunque después el producto se edite o se desactive.
- **FR-011**: El sistema NO DEBE permitir dos productos activos con el mismo nombre, ni dos variantes
  activas del mismo producto con el mismo tipo y valor. La comparación ignora mayúsculas, tildes y
  espacios al inicio y al final, y conserva la ñ («Piña» ≠ «Pina»). La regla se aplica al crear,
  editar y reactivar.
- **FR-012**: Cada error de validación DEBE mostrarse en español junto al campo correspondiente, sin
  perder lo que el dueño ya escribió.
- **FR-013**: El sistema DEBE ofrecer a otras partes de la aplicación (cotizaciones, bot) la lista
  de productos y variantes disponibles para cotizar con su precio efectivo, que es la única fuente
  de precios.

### Entidades clave

- **Producto**: algo que vende el negocio. Atributos: nombre, descripción corta, precio en pesos
  (entero), si controla inventario, si está activo. Tiene cero o más variantes.
- **Variante**: presentación de un producto. Atributos: tipo (sabor, peso, color, marca o tamaño),
  valor, precio propio opcional, si está activa. Pertenece a un solo producto.

## Criterios de éxito *(obligatorio)*

### Resultados medibles

- **SC-001**: El dueño registra un producto nuevo con dos variantes en menos de 2 minutos.
- **SC-002**: El 100 % de los precios aceptados son enteros en pesos entre 1 y 100.000.000; ningún
  valor fuera de ese rango ni con decimales llega a guardarse.
- **SC-003**: Ningún producto o variante inactivo aparece entre los disponibles para cotizar.
- **SC-004**: En el 100 % de los intentos se impide un producto activo con nombre repetido o una
  variante activa repetida, incluso si solo difieren en mayúsculas, tildes o espacios.
- **SC-005**: El catálogo se puede usar completo (crear, consultar, editar, desactivar) en una
  pantalla de 360 px de ancho sin desplazamiento horizontal.
- **SC-006**: Con 500 productos registrados, el listado del catálogo se muestra en menos de
  2 segundos.

## Supuestos

- Una variante se describe con un solo tipo y un valor; las combinaciones (por ejemplo, sabor y
  tamaño a la vez) se registran como variantes separadas o como productos distintos.
- La unicidad «mismo nombre y variante» se interpreta como: nombres de producto activos únicos y,
  dentro de un producto, variantes activas únicas por tipo y valor.
- «Controla inventario» es solo una marca en esta historia; las unidades disponibles y su descuento
  pertenecen a HU-18.
- La conservación de datos en pedidos anteriores (FR-010) se garantiza guardando una copia del
  nombre, la variante y el precio en cada línea de cotización o pedido; esas entidades se definen
  en sus propias historias.
- Fuera de alcance: fotos, categorías, importación desde Excel, unidades disponibles (HU-18),
  historial de cambios de precio, borrado definitivo y la protección del catálogo con inicio de
  sesión (login del dueño: HU-07, PED-15, Sprint 3).
