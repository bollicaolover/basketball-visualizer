# Metodología: Kanban (ágil, individual)

> Documento de apoyo al **Capítulo 3 — Metodologías usadas** de la memoria del TFG
> *basketball-visualizer*. Describe la metodología de gestión del trabajo realmente
> empleada y su trazabilidad al repositorio. Fuente única de verdad de la
> metodología; cualquier otra mención debe ser coherente con este documento.

## 1. Elección de la rama metodológica

El proyecto tiene un **componente experimental dominante**: el comportamiento real
del *pipeline* de visión (detección, seguimiento, identidad, homografía) ante
oclusiones, movimiento de cámara e iluminación de difusión **no puede
determinarse a priori**. Eso descarta un enfoque **predictivo/en cascada**, que
exigiría congelar requisitos al inicio: cualquier resultado empírico inesperado
obligaría a retroceder en el ciclo con un coste documental alto.

Por ello se adopta un enfoque **ágil e incremental**: construir, medir y refinar
cada módulo de forma progresiva, incorporando los resultados de cada iteración
como insumo de la siguiente.

## 2. Elección del marco ágil: Kanban

Se consideraron tres marcos ágiles y se descartaron dos:

| Marco | Por qué se descarta en un TFG individual |
|-------|------------------------------------------|
| **Scrum** | Roles y ceremonias diseñados para equipos; en trabajo unipersonal añaden sobrecarga procedimental sin beneficio. Los *sprints* de duración fija imponen una cadencia artificial poco compatible con tareas exploratorias de duración impredecible. |
| **XP** | Prácticas como *pair programming* carecen de sentido en solitario; la disciplina TDD ralentiza las fases exploratorias propias de la investigación aplicada. |
| **Kanban** ✅ | **Seleccionado.** Flujo continuo, sin iteraciones de duración fija ni roles. Hace visible el estado global, limita el trabajo en curso (WIP) y permite reorientar el desarrollo según los resultados empíricos sin el coste de replanificar un *sprint*. |

**Kanban** se ajusta de forma natural a un proyecto experimental e individual: la
ausencia de estructura temporal rígida —que en otros contextos sería una
limitación— aquí es una ventaja, porque el ritmo se adapta a la dificultad real
de cada tarea (p. ej., una decisión en el módulo de homografía puede condicionar
el comportamiento del de detección de bloqueos).

## 3. Implementación del tablero

El tablero se implementa en **GitHub Projects**, junto al repositorio de código,
de modo que cada tarjeta puede enlazarse al *commit* que la cierra y el tribunal
puede verificar la trazabilidad. Las tareas se gestionan como **Issues**
etiquetados por **área** y **estado**.

- **Columnas (estados):** `Por hacer` · `En progreso` · `Hecho`.
- **WIP limitado a 1:** una sola tarjeta activa en `En progreso` en cada momento.
- **Tarjeta = módulo/experimento entregable**, vinculada a `pipeline/`,
  `backend/`, `frontend/`, `scripts/` o `docs/`.
- **Estimación previa por *T-shirt sizing*** (S/M/L/XL) antes de abrir cada área
  (véase Capítulo 5).

### 3.1 Áreas funcionales del tablero

Las tarjetas se agrupan en **seis áreas** que se corresponden con las carpetas
reales del repositorio:

| Área | Carpetas | Estado |
|------|----------|--------|
| Detección & Tracking | `pipeline/detection/`, `pipeline/tracking/`, `pipeline/io/` | Hecho |
| Geometría & Homografía | `pipeline/court/` | Hecho |
| Identidad & Equipos | `pipeline/identity/`, `pipeline/teams/` | Hecho |
| Analytics & Reglas | `pipeline/possession/`, `pipeline/scoring/`, `pipeline/strategy/`, `pipeline/tactics/`, `pipeline/pose/` | Hecho |
| Core & Infrastructure | `backend/`, `frontend/` | Hecho |
| Memoria TFG | `docs/`, `TRABAJO FIN DE GRADO.docx` | En progreso |

## 4. Naturaleza iterativa y no lineal del flujo

El desarrollo **no fue lineal**. Al tratarse de un trabajo experimental, el avance
en un área revelaba con frecuencia trabajo pendiente en otra ya tocada, lo que
generaba **tarjetas de revisión (*rework*)** que se incorporaban al flujo según se
descubrían. Esta es precisamente la fortaleza de Kanban frente a un marco de
iteraciones cerradas. Ejemplos reales:

- La tarjeta **«Robustez del resolutor de posesión»** (Analytics & Reglas) surgió
  a raíz de fallos observados durante las pruebas funcionales del *pipeline*
  completo, no estaba planificada de inicio.
- El trabajo sobre **tracking** sacó a la luz limitaciones de la **detección**,
  generando tarjetas correctivas en el área de Detección.
- **Iteración descartada (evidencia honesta de proceso):** un intento de
  segmentar las sesiones de SAM para frenar la deriva de identidad en vídeos
  largos se probó, se evaluó y **se revirtió** («*approach did not work*»). Probar,
  medir y descartar es parte legítima del método.

> **Nota sobre el trabajo experimental previo.** Buena parte de la comparación de
> alternativas (p. ej. RF-DETR frente a YOLO, distintos *datasets* y *trackers*)
> se realizó en el repositorio predecesor `tfg-baloncesto-tacticas`, que actuó como
> **laboratorio de experimentación**. `basketball-visualizer` (`tfg-junio`) es la
> **convergencia final**: integra los modelos ganadores y descarta lo que no aportó
> ventaja neta (véase `comparativa-tfg-junio-vs-baloncesto-tacticas.md`).

## 5. Evidencia de la metodología

| Principio | Evidencia verificable |
|-----------|-----------------------|
| Kanban WIP=1 | Historial de *commits*: entregas de un módulo a la vez, sin solapamiento de tarjetas activas. |
| Flujo visible | Tablero de GitHub Projects con Issues etiquetados por área y estado. |
| Entrega incremental | Cada tarjeta deja el sistema en un estado ejecutable antes de abrir la siguiente. |
| Proceso iterativo | Tarjetas de *rework* (robustez de posesión) e iteración revertida (reset de sesiones SAM). |
| Trazabilidad | Cada tarjeta `Hecho` enlazada al *commit* que la cierra en el repositorio. |
| Estimación ágil | *T-shirt sizing* por área (Capítulo 5). |

> La tabla detallada **tarjeta → área → componente → commit** se mantiene en
> [`desarrollo-cap6.md`](desarrollo-cap6.md) y se consolida con los hashes reales
> tras la reconstrucción del historial de *git*.
