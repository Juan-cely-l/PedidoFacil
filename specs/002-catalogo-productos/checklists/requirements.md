# Lista de calidad de la especificación: PED-88 · HU-15 Catálogo de productos

**Propósito**: validar que la especificación esté completa y tenga calidad antes de planificar
**Creada**: 2026-11-16
**Especificación**: [spec.md](../spec.md)

## Calidad del contenido

- [x] Sin detalles de implementación (lenguajes, frameworks, APIs)
- [x] Centrada en el valor para el usuario y las necesidades del negocio
- [x] Escrita para personas no técnicas
- [x] Todas las secciones obligatorias completas

## Completitud de los requisitos

- [x] No quedan marcadores [NEEDS CLARIFICATION]
- [x] Los requisitos se pueden probar y no son ambiguos
- [x] Los criterios de éxito son medibles
- [x] Los criterios de éxito no dependen de la tecnología
- [x] Todos los escenarios de aceptación están definidos
- [x] Los casos límite están identificados
- [x] El alcance está claramente delimitado
- [x] Las dependencias y los supuestos están identificados

## Preparación de la funcionalidad

- [x] Cada requisito funcional tiene criterios de aceptación claros
- [x] Los escenarios de usuario cubren los flujos principales
- [x] La funcionalidad cumple los resultados medibles de los criterios de éxito
- [x] No se filtran detalles de implementación en la especificación

## Notas

- Validada en la primera iteración.
- Decisiones tomadas como supuestos que conviene confirmar con `/speckit-clarify`: variante de un
  solo tipo y un valor; comparación de duplicados que ignora mayúsculas, tildes y espacios; precio
  máximo holgado de 100.000.000 COP con mensaje de posible error de digitación; reactivación
  permitida si no choca con un activo.
- FR-010 depende de que las historias de cotizaciones y pedidos guarden una copia del nombre, la
  variante y el precio en cada línea.
- 2026-11-16: se retiró el requisito de sesión iniciada; el login es HU-07 (PED-15), Sprint 3.
- 2026-11-16: el precio se normaliza quitando puntos y espacios antes de validar; la coma se
  rechaza (separador decimal).
- 2026-11-16: el punto solo es separador de miles si agrupa tres dígitos («45.00» y «4.5» se
  rechazan); la normalización conserva la ñ; el escenario de pedidos anteriores pasa a dependencia.
