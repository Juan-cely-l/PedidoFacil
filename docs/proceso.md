# Proceso de trabajo de PedidoFácil

Proyecto individual de Ingeniería de Software gestionado con Scrum en Jira (proyecto `PED`). Este documento define los roles, la Definición de Listo, la Definición de Terminado y las ceremonias. Complementa la constitución (`.specify/memory/constitution.md`), que fija las reglas técnicas.

## Roles combinados

El equipo es de una sola persona, Juan Esteban Cely, que ejerce los tres roles de Scrum:

| Rol | Responsabilidades | Cómo se evita que sea solo nominal |
|---|---|---|
| Product Owner | Ordenar el backlog, definir el objetivo de cada sprint y aceptar las historias terminadas | Las prioridades se justifican con las entrevistas y los dueños de emprendimiento validan cada incremento en la Sprint Review |
| Scrum Master | Cuidar el timebox de las ceremonias, la bitácora diaria, los bloqueos y el seguimiento de la mejora de cada retrospectiva | Cada mejora acordada se crea como tarea en Jira en el sprint siguiente |
| Developer | Especificar, implementar con TDD, integrar y desplegar | Las puertas automáticas (CI, hooks, ruleset de `main`) sustituyen la revisión por pares |

## Definición de Listo (DoR)

Una historia puede entrar a un sprint cuando:

- Tiene el formato «Como… quiero… para…» y criterios de aceptación verificables.
- Está estimada en Story Points y cabe en un sprint.
- Sus dependencias están resueltas (por ejemplo, la cotización requiere el catálogo).
- Se sabe si lleva el ciclo completo de Spec Kit o la versión corta (`specify` → `tasks` → `implement`).

## Definición de Terminado (DoD)

Una historia está terminada cuando cumple todo lo siguiente:

1. **Especificada:** existe su carpeta `specs/NNN-.../` con `spec.md`, `plan.md` y `tasks.md`, y `spec.md` describe lo que el código hace realmente.
2. **Funciona:** cumple todos sus criterios de aceptación, verificados a mano en local.
3. **Probada con TDD:** cada comportamiento nuevo tiene una prueba que falló primero; el historial del PR muestra commits `test(...)` antes de los `feat(...)`. La IA y la API de Telegram están simuladas en las pruebas.
4. **Integrada:** se trabajó en una rama `feature/PED-XX-...` y se integró por pull request con squash merge, con el check «Calidad y pruebas» en verde (ruff, formato, mypy estricto y pytest con cobertura ≥ 80 %).
5. **Revisada:** el diff se revisó después de una pausa, siguiendo la plantilla de PR; al menos un PR del proyecto tiene la revisión de otra persona.
6. **Desplegada:** el despliegue en Render terminó, `/health` responde 200 con el commit esperado y el recorrido funciona en la URL de demostración.
7. **Segura:** no hay secretos en el código; `.env.example` está actualizado si se agregó una variable.
8. **Registrada:** el issue de Jira está en Done, con el PR y la carpeta de la especificación enlazados.

**Un sprint está terminado cuando** el incremento está desplegado y etiquetado (`v0.1`, `v0.2`, `v1.0`), la Sprint Review tiene la retroalimentación de un usuario registrada en Jira y la retrospectiva dejó una mejora con responsable y forma de comprobarla.

## Ceremonias

| Ceremonia | Cuándo | Duración | Evidencia |
|---|---|---|---|
| Sprint Planning | Primer día del sprint (miércoles) | 30 min | Objetivo del sprint en Jira y sprint iniciado |
| Daily Scrum | Cada día de trabajo | 5 min | Comentario en el issue en curso: ayer / hoy / bloqueos |
| Sprint Review | Último día (martes) | 30–45 min | Demostración a un dueño de emprendimiento; su retroalimentación queda como comentarios o issues nuevos |
| Retrospectiva | Después de la review | 20 min | Una mejora, su responsable y cómo comprobarla, creada como tarea del sprint siguiente |

## Métricas de flujo (Lean)

- **Tiempo de ciclo:** tiempo de cada historia entre «In Progress» y «Done», tomado de Jira.
- **Ítems terminados por sprint:** Story Points completados, tomados del informe de velocidad.

Regla de recorte acordada: si la velocidad del Sprint 1 es menor a 15 SP, las alertas de stock se entregan solo en el panel (HU-19) y el bot de Telegram solo cotiza, sin tomar el pedido (HU-20).
