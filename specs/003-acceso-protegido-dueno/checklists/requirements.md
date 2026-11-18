# Lista de calidad de la especificación: PED-15 · HU-07 Acceso protegido del dueño

**Propósito**: validar que la especificación esté completa y tenga calidad antes de planificar
**Creada**: 2026-11-18
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
- «Google», `/health`, `/health/live`, `/productos` y `SECRET_KEY` aparecen porque son parte del
  pedido y del contrato con Render, no decisiones de implementación. La biblioteca (authlib) y
  los atributos técnicos de la cookie quedan para el plan; FR-010 los expresa en términos de
  comportamiento.
- Decisiones tomadas como supuestos que conviene confirmar con `/speckit-clarify`: volver a la
  página pedida tras el login (solo rutas propias); revalidar la lista blanca en cada petición;
  rechazar correos no verificados por Google; producción no arranca sin lista blanca.
- La duración de la sesión y la ruta de vuelta desde Google se fijan en el plan, por pedido del
  usuario.
