## Issue de Jira

PED-

## Qué cambia

<!-- Resumen en 1-3 líneas. -->

## Cómo se probó

<!-- Pruebas automatizadas nuevas o actualizadas y verificación manual. -->

## Checklist de la Definición de Terminado

- [ ] Cumple todos los criterios de aceptación de la historia
- [ ] Tiene al menos una prueba automatizada nueva o actualizada (la IA, simulada)
- [ ] CI en verde (ruff, formato, mypy, pytest con cobertura ≥ 80 %)
- [ ] Sin secretos en el código; `.env.example` actualizado si hay variables nuevas
- [ ] README o guía actualizados si cambió cómo ejecutar o desplegar
- [ ] Autorrevisión del diff hecha después de una pausa (o revisión de otra persona)
- [ ] Tras el merge: despliegue verificado en `/health` y recorrido probado en la demo
