# Lista de calidad de la especificación: PED-16 · HU-08 Cotización con IA

**Propósito**: validar que la especificación está completa y es de calidad antes de planificar
**Creada**: 2026-11-20
**Especificación**: [spec.md](../spec.md)

## Calidad del contenido

- [x] Sin detalles de implementación (lenguajes, frameworks, APIs)
- [x] Centrada en el valor para el usuario y el negocio
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

- [x] Todos los requisitos funcionales tienen criterios de aceptación claros
- [x] Los escenarios de usuario cubren los flujos principales
- [x] La funcionalidad cumple los resultados medibles de los criterios de éxito
- [x] No se filtran detalles de implementación en la especificación

## Notas

- Excepción deliberada a «sin detalles de implementación»: la sección «Restricciones de diseño»
  (RD-1, RD-2) nombra `app/services/` y `list_quotable_items` porque el dueño del producto las
  pidió como restricciones no negociables. El resto de la especificación no depende de la
  tecnología.
- El tiempo de espera no tiene valor en la especificación (se decide en el plan), pero sí un tope:
  los 15 s del principio V de la constitución (FR-011).
- Validación: una iteración, todos los puntos pasan.
