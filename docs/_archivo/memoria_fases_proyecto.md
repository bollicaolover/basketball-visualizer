# Desarrollo del proyecto por fases

> Documento de apoyo a la memoria del TFG *basketball-visualizer*
> (Sistema de detección, seguimiento e identificación de jugadores de baloncesto
> y proyección táctica 2D). Su contenido se ha extraído del tablero Kanban del
> proyecto en Notion (*basketball-visualizer — Kanban*) y de la trazabilidad real
> de commits del repositorio. Cada apartado está pensado para copiarse de forma
> independiente al capítulo de desarrollo de la memoria.

> **Nota metodológica sobre las fechas.** El tablero Kanban de Notion almacena
> únicamente la fecha de creación de cada tarjeta (la mayoría se consolidaron al
> formalizar el tablero en junio de 2026), por lo que no ofrece fechas de inicio
> y cierre fiables por tarea. Para reconstruir la cronología real se han empleado
> las fechas de los *commits* etiquetados `[Kanban: CÓDIGO]` del repositorio, que
> sí son verificables. Los plazos (*lead time*) que se indican son, por tanto, la
> distancia entre entregas consecutivas en el control de versiones; cuando una
> fase se consolidó en una refactorización conjunta (junio), el plazo individual
> por tarea no puede separarse y así se hace constar.

---

## Fase 1: Configuración inicial, entorno y arquitectura base — Estado: Completada

**Período**: enero–febrero de 2026 (primer *commit* del esqueleto: 29 de enero de 2026).

**Objetivo de la fase**

Esta fase inicial tuvo como objetivo establecer los cimientos técnicos del
proyecto: definir el alcance del sistema, fijar una arquitectura modular que
separase con claridad el procesamiento de visión, el servicio web y la interfaz,
y dejar operativo el entorno de ejecución sobre el servidor de cómputo
(Ubuntu 22.04 con dos GPU NVIDIA A100 de 40 GB). Se buscó disponer cuanto antes
de un esqueleto de *backend* arrancable y de una política de seguridad básica
sobre la que construir el resto de componentes.

**Tareas realizadas**

1. **Definición del problema, alcance y arquitectura modular** — Se delimitó el
   sistema (entrada de vídeo → vídeo anotado + minimapa cenital 2D) y se fijó la
   separación en tres piezas (*pipeline* de visión, *backend* y *frontend*),
   decisión que gobierna todo el desarrollo posterior. Trabajo conceptual previo
   al primer *commit* de código.
2. **Configurar proyecto FastAPI** (`[Kanban: WEB-B1]`) — Esqueleto del
   *backend*: configuración de la aplicación FastAPI, inicialización de
   persistencia en sistema de ficheros y un *Dockerfile* de andamiaje (que
   quedaría sin completar). Entregado el 29 de enero
   de 2026.
3. **Autenticación por token HMAC** (`[Kanban: WEB-B2]`) — Capa de seguridad de
   la API mediante validación de token HMAC, como dependencia reutilizable en los
   endpoints. Entregada el 20 de febrero de 2026.
   *Lead time* respecto a la tarea anterior: **22 días**.

**Tareas en curso o pendientes**

Sin tareas pendientes asignadas a esta fase. Los cimientos quedaron cerrados y no
volvieron a tocarse hasta integrarse con el resto del sistema.

**Decisiones técnicas tomadas**

- **Arquitectura de tres piezas desacopladas** (*pipeline* / *backend* /
  *frontend*) en lugar de un sistema monolítico, con la persistencia resuelta
  sobre el **sistema de ficheros** y no sobre una base de datos relacional. La
  motivación fue reducir la complejidad operativa y facilitar el procesamiento
  por lotes en GPU.
- **FastAPI** como marco del *backend*, por su soporte nativo de operaciones
  asíncronas y su integración directa con el ecosistema Python del *pipeline*.
- **Autenticación por HMAC** en lugar de un proveedor de identidad externo,
  adecuada a un sistema de un solo operador y sin dependencia de servicios en la
  nube.

**Problemas encontrados y soluciones**

Sin incidencias registradas en esta fase.

**Resultado de la fase**

Al término de la fase se disponía de un *backend* FastAPI arrancable, con
seguridad por token y empaquetable en un contenedor reproducible (Apptainer), y de una arquitectura modular
documentada que fijaba las fronteras entre visión, servicio e interfaz. Este
andamiaje permitió que las fases siguientes pudieran desarrollar el *pipeline* de
visión y la aplicación web de forma independiente y reintegrarlos al final.

---

## Fase 2: Pipeline core — detección, tracking y homografía — Estado: Completada

**Período**: cronograma previsto febrero–marzo de 2026; el prototipo de visión se
construyó entre enero y abril (envoltorios de visión en el *backend*,
`[Kanban: WEB-B6]`, 17 de abril de 2026) y la consolidación modular definitiva se
entregó en junio de 2026 (*commits* `PIPE-*`). Véase el apartado *Desviaciones*.

**Objetivo de la fase**

El objetivo de esta fase fue construir el núcleo de visión por computador: la
detección de jugadores, árbitros y balón, el seguimiento con identidad temporal,
la clasificación por equipos sin etiquetas, el reconocimiento de dorsales y la
proyección geométrica de la cancha a una vista cenital mediante homografía. Se
trataba de pasar de fotogramas de difusión a una representación estructurada y
estable de qué hay en la pista y dónde está.

**Tareas realizadas**

1. **Detector de jugadores y balón con RF-DETR** (`[Kanban: PIPE-D1]`) — Detector
   *transformer* de 11 clases (incluida `player-in-possession`) sobre fotogramas
   de difusión; mejora posterior de la detección y del OCR de dorsal. Refactor
   consolidado el 19 de junio de 2026.
2. **Detector de keypoints de cancha** (`[Kanban: PIPE-K1]`) — Detector de puntos
   característicos de la pista (KaliCalib) y herramientas asociadas, base para la
   calibración geométrica. Entregado el 20 de junio de 2026.
3. **Geometría de cancha FIBA y segmentos** — Modelo geométrico de la cancha FIBA
   y sus segmentos, soporte de referencia para la homografía.
4. **Estimación de homografía y modelo PnP** — Cálculo de la matriz de homografía
   (DLT/SVD/RANSAC) a partir de los *keypoints*, con modelo PnP para la pose de
   cámara.
5. **Calibración automática de cámara (homografía)** — Calibración automática
   encadenando detección de *keypoints* y estimación de homografía.
6. **I/O de vídeo y tipos base del pipeline** — Lectura/escritura de vídeo y los
   tipos de datos comunes que recorren todas las etapas del *pipeline*.
7. **Tracker de jugadores con SAM3** (`[Kanban: PIPE-T1]`) — Seguimiento por
   segmentación con SAM 3 (estrategia *prompt-once* + *re-prompt*) con identidad
   temporal por jugador.
8. **Rastreador del balón con filtro de Kalman** (`[Kanban: PIPE-T1]`) — Tracker
   específico del balón basado en filtro de Kalman. Refactor del 19 de junio de
   2026.
9. **Deduplicación de detecciones y player tracker** (`[Kanban: PIPE-T1]`) —
   Eliminación de detecciones duplicadas y consolidación del *tracker* de
   jugadores.
10. **Suavizado y estabilización de trayectorias** — Suavizado temporal y
    estabilización de las trayectorias proyectadas para evitar oscilaciones en la
    vista cenital.
11. **Minimapa cenital 2D** — Renderizado de la vista cenital 2D de jugadores y
    balón a partir de la homografía.
12. **Clasificador de equipos (SigLIP + UMAP)** — Asignación de equipo sin
    etiquetas mediante descriptores SigLIP, reducción con UMAP y agrupamiento
    K-means (k=2), con voto por *track*.
13. **OCR de dorsales con SmolVLM2** — Reconocimiento del número de dorsal con un
    modelo VLM (SmolVLM2) ajustado localmente, con voto por IoS.
14. **Roster de jugadores y resolución de nombres** — Resolución del nombre del
    jugador a partir del dorsal y la plantilla del equipo (*roster*).
15. **Envoltorios de visión en el backend** (`[Kanban: WEB-B6]`) — Adaptadores de
    detector, *tracker* y homografía expuestos al *backend*, junto con el recurso
    de cancha. Entregados el 17 de abril de 2026; fueron la primera integración
    del prototipo de visión en el servicio web.

**Tareas en curso o pendientes**

- **Fine-tuning RF-DETR con dataset propio** — Estado: *Por hacer*. El detector
  opera con pesos preentrenados; el reentrenamiento con un conjunto propio quedó
  diferido. No bloquea el sistema, que funciona con el detector base.

**Decisiones técnicas tomadas**

- **RF-DETR (detección basada en *transformer*) frente a YOLOv8**, por su mejor
  comportamiento en escenas densas y oclusiones propias del baloncesto.
- **SAM 3 como mecanismo de seguimiento** (segmentación + *re-prompt*) en lugar
  de un *tracker* clásico tipo ByteTrack, buscando identidad más estable bajo
  oclusión.
- **Clasificación de equipos sin etiquetas** con SigLIP + UMAP + K-means, para
  evitar el coste de etiquetar manualmente equipos partido a partido.
- **Reconocimiento de dorsal con un VLM (SmolVLM2)** ajustado localmente en lugar
  de un OCR especializado tipo PARSeq, aprovechando su robustez ante recortes de
  baja resolución.
- **Refactorización del prototipo monolítico a un paquete `pipeline/` modular**
  (junio), separando detección, *tracking*, geometría, identidad y E/S en módulos
  independientes con interfaces claras.

**Problemas encontrados y soluciones**

- *Problema*: en vídeos largos el seguimiento por SAM acumulaba estado y se
  degradaba (deriva de identidad). → *Solución*: se introdujo una segmentación
  por sesiones con *re-prompt* periódico; un primer intento no resultó eficaz y
  fue revertido (*commits* `10e1736` y `54ef5da`, «*approach did not work*»),
  documentándose como iteración de evaluación → modelado característica de
  CRISP-DM.
- *Problema*: la pose por PnP no se activaba de forma fiable en vídeo de difusión
  por el ruido de los *keypoints*. → *Solución*: el mapa cenital recurre a la
  homografía de respaldo en lugar de la pose PnP cuando el error supera el umbral,
  manteniendo la estabilidad del minimapa.

**Resultado de la fase**

La fase entregó un *pipeline* de visión completo y modular capaz de detectar,
seguir, clasificar por equipo, identificar por dorsal y proyectar a 2D a los
agentes del juego. Esta representación estructurada y estable fue el prerrequisito
del análisis táctico de la fase siguiente, que opera sobre las trayectorias
producidas aquí.

---

## Fase 3: Análisis táctico — posesión, detección de bloqueos y vista cenital 2D — Estado: Completada

**Período**: cronograma previsto marzo–abril de 2026; el grueso del análisis
táctico se entregó en junio de 2026 (*commits* `PIPE-S1`, `PIPE-POS2`,
`PIPE-TAC1`, `PIPE-3D1`, `PIPE-P1`).

**Objetivo de la fase**

Esta fase tuvo por objetivo elevar la información del *pipeline* del nivel de
«dónde está cada agente» al nivel de «qué está ocurriendo tácticamente»:
resolver la posesión del balón, detectar eventos de canasta y, como ampliación de
alcance, reconocer bloqueos (*screens*) a partir de las trayectorias de los
jugadores. Se apoyó en la vista cenital 2D producida en la fase anterior como
soporte de representación.

**Tareas realizadas**

1. **Resolver de posesión del balón** (`[Kanban: PIPE-S1]`) — Atribución de la
   posesión mediante histéresis temporal, evitando parpadeos de asignación entre
   jugadores próximos. Refactor del 19 de junio de 2026.
2. **Robustez del resolutor de posesión (oclusión y multitudes)**
   (`[Kanban: PIPE-POS2]`) — Endurecimiento del resolutor frente a oclusiones y
   aglomeraciones de jugadores. Entregado el 20 de junio de 2026.
   *Lead time* respecto al resolutor base: **1 día**.
3. **Detección de canastas (shot tracker)** — Detección de eventos de canasta a
   partir del seguimiento del balón.
4. **Módulo de estrategia y reglas de juego** (`[Kanban: PIPE-S1]`) — Módulo de
   estrategia que centraliza las reglas de juego sobre las que se construye el
   análisis táctico.
5. **Reconocimiento de pantallas (screens)** (`[Kanban: PIPE-TAC1]`) — Detección
   y clasificación de bloqueos *front/back/down* sobre las trayectorias (método de
   Chen et al., 2012), en post-proceso sobre `{out}_metadata.json`, con *flag*
   `--tactics` y parámetros calibrados para reducir falsos positivos. Entregado el
   20 de junio de 2026. **Esta tarea constituyó la ampliación de alcance del
   proyecto** (véase *Desviaciones*).
6. **Reconstrucción 3D de la trayectoria del tiro** (`[Kanban: PIPE-3D1]`) —
   Reconstrucción tridimensional de la trayectoria del balón en el tiro (método de
   Pirotta), validada (RMSE ≈ 2,1 px; ápice ≈ 13,3 ft). Entregada el 19 de junio
   de 2026.
7. **Detector de lanzamiento por pose** (`[Kanban: PIPE-P1]`) — Detección del
   instante de lanzamiento mediante estimación de pose (YOLOv8-pose) que dispara
   la reconstrucción 3D y el *shot tracker*; funcionalidad *opt-in*. Entregada el
   19 de junio de 2026.

**Tareas en curso o pendientes**

- **Evaluación cuantitativa HOTA/MOTA** — Estado: *Por hacer*. La evaluación
  formal del seguimiento con las métricas HOTA/MOTA quedó diferida; la validación
  realizada es funcional y cualitativa más la del OCR de dorsal.

**Decisiones técnicas tomadas**

- **Atribución de posesión por histéresis temporal** en lugar de por umbral
  instantáneo de proximidad, para estabilizar la asignación.
- **Reconocimiento de bloqueos por reglas geométricas sobre trayectorias**
  (Chen et al., 2012) en post-proceso, en lugar de un modelo aprendido, por la
  ausencia de datos etiquetados de bloqueos y para mantener la interpretabilidad.
- **Reconstrucción 3D del tiro por el método de Pirotta** y disparo por **pose**,
  como vía para enriquecer el análisis del lanzamiento sin instrumentación
  adicional.

**Problemas encontrados y soluciones**

- *Problema*: el reconocimiento de bloqueos generaba inicialmente falsos
  positivos en zonas de alta densidad de jugadores. → *Solución*: se calibró
  `TacticsSettings` (umbrales de proximidad y duración) para suprimir detecciones
  espurias, documentándolo en `docs/tacticas-screen-recognition.md`.
- *Problema*: el resolutor de posesión fallaba bajo oclusión y en aglomeraciones.
  → *Solución*: tarea específica de endurecimiento (`PIPE-POS2`) un día después de
  la versión base.

**Resultado de la fase**

La fase entregó una capa de análisis táctico funcional: posesión robusta,
detección de canastas, reconstrucción 3D del tiro y, como ampliación, el
reconocimiento de bloqueos sobre trayectorias. Estos resultados alimentan los
paneles de la aplicación web (pantallas y trayectoria de tiro) de la fase
siguiente. La incorporación del reconocimiento de bloqueos amplió el alcance
inicial y desplazó el cierre del proyecto hacia el final de junio.

---

## Fase 4: UI, integración y sistema completo — Estado: Completada

**Período**: la interfaz y los endpoints web se desarrollaron entre marzo y mayo
de 2026 (*commits* `WEB-B3`/`WEB-B4` y `WEB-F1`…`WEB-F6`, `WEB-D1`/`WEB-D2`); la
integración final con el *pipeline* refactorizado y las tácticas se cerró en junio
de 2026 (`WEB-B7`/`WEB-B8`, `WEB-F7`/`WEB-F8`, `PIPE-O1`).

**Objetivo de la fase**

El objetivo fue convertir el *pipeline* de visión y el análisis táctico en un
sistema completo y usable: una aplicación web (Vue 3 + FastAPI) que permitiera
subir un vídeo, seleccionar GPU, seguir el progreso y visualizar los resultados
(vídeo anotado sincronizado con el minimapa cenital 2D), además del orquestador
que une todas las etapas y el procesado multi-GPU por lotes.

**Tareas realizadas**

1. **Endpoint de subida y transcodificación de vídeo** (`[Kanban: WEB-B3]`) —
   Subida de vídeo y transcodificación por *chunks*. 16 de marzo de 2026.
2. **Endpoints de resultados y gestión de jobs** (`[Kanban: WEB-B4]`) — Endpoints
   de resultados y orquestación del *pipeline* como subproceso. 7 de abril de 2026.
3. **Scaffold SPA Vue 3 + Vite** (`[Kanban: WEB-F1]`) — Andamiaje de la SPA con
   *design tokens* y estilos base. 21 de abril de 2026.
4. **Capa de servicios API (frontend)** (`[Kanban: WEB-F2]`) — Capa de servicios
   de la API y utilidades de presentación. 28 de abril de 2026.
5. **Vista de login** (`[Kanban: WEB-F3]`) — Pantalla de acceso y *composable* de
   autenticación con el flujo de token HMAC. 5 de mayo de 2026.
6. **Vista de subida de vídeo** (`[Kanban: WEB-F4]`) — Envío de *job*, *polling*
   de progreso y configuración de equipos. 12 de mayo de 2026.
7. **Vista de resultados (reproductor + minimapa)** (`[Kanban: WEB-F5]`) —
   Reproductor de vídeo anotado sincronizado con el mapa táctico 2D. 16 de mayo de
   2026.
8. **App shell, sidebar y panel de GPU stats** (`[Kanban: WEB-F6]`) — Esqueleto de
   la aplicación, barra lateral, modal de procesamiento, *sparkline* y estadísticas
   de GPU/sistema. 19 de mayo de 2026.
9. **Sincronización frame↔frontend (metadata JSON)** (`[Kanban: WEB-D1]`) — Escritor
   de metadatos por fotograma para la sincronización con el *frontend*, módulo de
   ejecución y *roster* de ejemplo. 24 de mayo de 2026.
10. **Empaquetar y servir frontend compilado** (`[Kanban: WEB-D2]`) — se
    crearon `Dockerfile` de andamiaje (que quedaron como esqueleto vacío) y el
    despliegue integrado real vía `serve.sh` + `dist` del *frontend*. 27 de mayo
    de 2026. La containerización se materializó después con Apptainer (véase
    `docs/reproducibilidad-apptainer.md`).
11. **Orquestador del pipeline (frame a frame)** (`[Kanban: PIPE-O1]`) —
    Orquestador que une todas las etapas por fotograma, junto con configuración y
    E/S del *pipeline*. 19 de junio de 2026.
12. **CLI y procesado multi-GPU (chunking)** (`[Kanban: PIPE-O1]`) — Puntos de
    entrada (`run.py`, `run_batch.sh`) y procesado multi-GPU por *chunks*.
13. **Ampliar API: modo tracker y nuevos parámetros** (`[Kanban: WEB-B7]`) —
    Extensión del *backend* para el modo *tracker* y nuevos parámetros del
    *pipeline*. 19 de junio de 2026.
14. **Endpoint de tácticas (screens) en el backend** (`[Kanban: WEB-B8]`) — Servicio
    de los bloqueos reconocidos vía `tactics.json`. 20 de junio de 2026.
15. **Panel de pantallas y trayectoria de tiro en resultados** (`[Kanban: WEB-F8]`) —
    Exposición de bloqueos, trayectoria de tiro y modo *tracker* en la vista de
    resultados. 20 de junio de 2026.
16. **Composable de modo tracker (frontend)** (`[Kanban: WEB-F7]`) — *Composable*
    de modo *tracker* y actualización de la vista de resultados. 19 de junio de
    2026.

**Tareas en curso o pendientes**

- **Panel de estadísticas por jugador** — Estado: *Por hacer*. Panel agregado de
  estadísticas individuales, diferido.
- **Exportación de clips de jugadas** — Estado: *Por hacer*. Recorte y exportación
  de clips por jugada, diferido.

Ambas son funcionalidades de valor añadido sobre la interfaz; ninguna bloquea el
flujo principal (subir → procesar → visualizar).

**Decisiones técnicas tomadas**

- **SPA Vue 3 + Vite** con *design tokens* propios, frente a un *frontend*
  renderizado en servidor.
- **Jobs en segundo plano + subproceso por GPU con bloqueo por GPU**, en lugar de
  una cola distribuida (Celery/Redis), por simplicidad operativa.
- **Procesado multi-GPU por *chunking*** para escalar el tiempo de proceso en las
  dos A100 disponibles.
- **Sincronización por metadatos JSON por fotograma**, que desacopla el render del
  *frontend* del *pipeline* y permite una capa interactiva sobre el vídeo.

**Problemas encontrados y soluciones**

- *Problema*: la interfaz se desarrolló contra un *pipeline* de visión aún en
  evolución (envoltorios de *backend* y prototipo monolítico), antes de la
  refactorización modular. → *Solución*: contrato estable de metadatos JSON por
  fotograma entre *pipeline* y *frontend*, que permitió integrar la versión modular
  final (`PIPE-O1`) sin rehacer la interfaz.
- *Problema*: incorporar las tácticas (bloqueos) a la salida exigió ampliar la API
  y la vista de resultados ya cerradas. → *Solución*: endpoint `tactics.json`
  (`WEB-B8`) y panel adicional (`WEB-F8`) añadidos de forma incremental sin alterar
  el flujo existente.

**Resultado de la fase**

La fase entregó el sistema completo y ejecutable de extremo a extremo: aplicación
web con acceso, subida, selección de GPU, seguimiento del progreso y visualización
de resultados (vídeo anotado + minimapa 2D + paneles de tácticas y tiro),
orquestador por fotograma y procesado multi-GPU. Es el entregable que el tribunal
puede ejecutar y observar, y la base sobre la que se documenta y prueba el sistema
en la fase final.

---

## Fase 5: Documentación, testing y redacción del TFG — Estado: En curso

**Período**: mayo–junio de 2026 (suite de pruebas y *scripts* el 19 de junio;
documentación técnica, figuras y memoria a partir del 20 de junio; entrega
prevista ~26 de junio de 2026).

**Objetivo de la fase**

Esta fase persigue validar el sistema, generar la evidencia (métricas, figuras y
documentación técnica reproducible) y redactar la memoria del TFG alineada con lo
realmente implementado. Se encuentra en curso a fecha de este documento.

**Tareas realizadas**

1. **Suite de pruebas pytest (22 tests)** (`[Kanban: TEST1]`) — Suite unitaria
   (chunking, posesión, homografía, *roster*) con `pytest.ini`. 19 de junio de 2026.
2. **Scripts de entrenamiento y evaluación** (`[Kanban: TEST1]`) — *Scripts* de
   evaluación (p. ej. OCR de dorsal) y medición de rendimiento. 19 de junio de 2026.
3. **Documentación técnica y CFD actualizados** (`[Kanban: DOC-CFD/DOC-TECH/DOC-MEM]`)
   — Figuras reproducibles (CFD Kanban, progreso por áreas, homografía) y documentos
   técnicos de módulos (tácticas, 3D, pose-release) y de apoyo a la memoria
   (estado del arte, datos reales, comparativa). 20 de junio de 2026.
4. **Metodología CRISP-DM + Kanban — Cap. 3** — Documento de metodología con la
   trazabilidad tarjeta → fase → *commit*.
5. **Arquitectura del sistema — Cap. 6.2** — Documento de arquitectura de las tres
   piezas del sistema.

**Tareas en curso o pendientes**

- **Redacción de la memoria (Memoria TFG)** — *En curso*. Se está redactando el
  documento sobre la plantilla institucional, con realineado tecnológico completo
  ya aplicado.
- **Tests de integración E2E del pipeline completo** — Estado: *Por hacer*. Las
  pruebas de extremo a extremo automatizadas quedan diferidas; existe validación
  funcional sobre los vídeos de prueba y la suite unitaria.

**Decisiones técnicas tomadas**

- **Figuras reproducibles por generadores** (`scripts/generate_*_svg.py`), de modo
  que las gráficas del CFD, el progreso y la homografía puedan regenerarse a partir
  de datos reales.
- **Validación basada en métricas medidas y no inventadas** (OCR de dorsal 85,26 %;
  *pipeline* ≈ 1.402 ms/fotograma ≈ 0,7 fps; pico de 7,8 GB de VRAM; *speedup*
  1,48× en 2× A100), extraídas de *logs* y *scripts* de medición.

**Problemas encontrados y soluciones**

- *Problema*: la plantilla de memoria describía inicialmente una pila tecnológica
  que no coincidía con la implementada (YOLOv8/ByteTrack/PARSeq, «tiempo real»,
  motor de tácticas/recomendación). → *Solución*: realineado tecnológico completo
  del documento a la pila real (RF-DETR · SAM 3 · SigLIP · SmolVLM2), trasladando a
  «vías futuras» lo no construido.

**Resultado de la fase (parcial)**

A fecha de este documento existen la suite de pruebas unitarias, los *scripts* de
evaluación, la documentación técnica con figuras reproducibles y la memoria en
redacción avanzada con su realineado tecnológico cerrado. Quedan pendientes las
pruebas de integración E2E automatizadas y el cierre final de la memoria.

---

## Línea temporal general

> *Tareas completadas/pendientes* contabilizan tarjetas hoja del tablero
> (excluidos los cuatro epígrafes contenedores: *Core & Infrastructure*,
> *Detección & Tracking*, *Identidad & Equipos*, *Analytics & Reglas*).

| Fase | Período real (evidencia en commits) | Tareas completadas | Tareas pendientes | Estado |
|------|--------------------------------------|--------------------|-------------------|--------|
| 1 — Configuración inicial, entorno y arquitectura base | ene–feb 2026 (29 ene – 20 feb) | 3 | 0 | Completada |
| 2 — Pipeline core: detección, tracking, homografía | prototipo ene–abr; consolidación jun 2026 | 15 | 1 | Completada |
| 3 — Análisis táctico: posesión, bloqueos, vista 2D | jun 2026 (19–20 jun) | 7 | 1 | Completada |
| 4 — UI, integración y sistema completo | mar–may + jun 2026 | 16 | 2 | Completada |
| 5 — Documentación, testing y redacción del TFG | may–jun 2026 (en curso) | 5 | 1 (+ memoria en curso) | En curso |
| **Total** | **ene–jun 2026** | **46** | **5** | — |

El tablero Kanban reportaba en su última instantánea 55 tarjetas con 51 hechas y
4 diferidas (93 %); este documento enumera 51 tarjetas hoja (46 hechas + 5 en
*Por hacer*) más los 4 epígrafes contenedores. La pequeña diferencia se debe a que
la enumeración se ha realizado mediante búsqueda sobre el tablero —la consulta
directa de la base de datos requiere un plan de Notion superior— y a que el conteo
de «4 diferidas» corresponde a una instantánea anterior a añadirse la quinta
tarjeta diferida.

---

## Evolución del sistema

**De la Fase 1 a la Fase 2.** El proyecto partió de un andamiaje de servicio
(FastAPI con seguridad por token y empaquetado en contenedor reproducible) y una arquitectura de tres
piezas claramente delimitada. Sobre esa frontera entre visión, servicio e interfaz
se construyó el núcleo de visión por computador, que transformó el sistema de un
esqueleto vacío a un *pipeline* capaz de detectar, seguir e identificar a los
agentes del juego y proyectar la pista a una vista cenital.

**De la Fase 2 a la Fase 3.** Una vez disponible una representación estructurada y
estable de las trayectorias, el sistema dejó de limitarse a «dónde está cada
agente» para razonar sobre «qué ocurre»: resolución de posesión, detección de
canastas y, como ampliación, reconocimiento de bloqueos y reconstrucción 3D del
tiro. La capa táctica se apoyó directamente en el minimapa 2D y en las trayectorias
suavizadas producidas en la fase anterior.

**De la Fase 3 a la Fase 4.** Con el análisis táctico funcionando, el esfuerzo se
centró en convertir el conjunto en un producto usable. La interfaz web —que se
había ido construyendo en paralelo contra un contrato estable de metadatos— se
integró con el *pipeline* modular y la salida táctica, sumando el orquestador por
fotograma y el procesado multi-GPU. El sistema pasó de un conjunto de módulos a una
aplicación ejecutable de extremo a extremo.

**De la Fase 4 a la Fase 5.** Con el sistema completo y ejecutable, el foco se
desplazó a la validación, la generación de evidencia reproducible y la redacción de
la memoria, cerrando el ciclo CRISP-DM (Evaluation → Deployment) y documentando las
decisiones tomadas a lo largo del proyecto.

---

## Desviaciones respecto a la planificación inicial

La reconstrucción de la cronología real a partir del control de versiones revela
varias desviaciones respecto a la planificación inicial por fases, que se documentan
de forma explícita por honestidad metodológica:

1. **Ampliación de alcance: reconocimiento de bloqueos (*screens*).** El proyecto
   se amplió para incorporar la detección de bloqueos a partir de las trayectorias
   de los jugadores (`[Kanban: PIPE-TAC1]`, 20 de junio de 2026), funcionalidad no
   contemplada en el plan inicial. Esta ampliación, junto con su soporte en el
   *backend* (`WEB-B8`) y en la interfaz (`WEB-F8`), añadió valor analítico al
   sistema pero **retrasó el cierre del proyecto** hacia el final de junio, al
   incorporarse cuando la interfaz y la API ya estaban cerradas y obligar a
   extenderlas de forma incremental.

2. **Orden real de las fases distinto al planificado.** El cronograma preveía
   completar el *pipeline* core (Fase 2) y el análisis táctico (Fase 3) antes de la
   interfaz (Fase 4). En la práctica, la capa web (endpoints y vistas, `WEB-B3`…
   `WEB-F6`, marzo–mayo) se desarrolló **antes** de la consolidación modular
   definitiva del *pipeline* de visión y del análisis táctico, concentrados en junio
   (`PIPE-*`). El sistema funcionó durante ese tiempo contra un prototipo de visión
   (el script monolítico inicial y los envoltorios de *backend* `WEB-B6`), y la
   interfaz se diseñó contra un contrato estable de metadatos JSON que permitió
   integrar después la versión modular sin rehacer el *frontend*.

3. **Concentración de la refactorización del pipeline en junio.** Buena parte de
   las tarjetas del núcleo de visión y del análisis táctico comparten fecha de
   entrega (19–20 de junio), correspondiente a la refactorización del prototipo a
   un paquete `pipeline/` modular. Por ello, el *lead time* individual de esas
   tareas no es separable y se ha indicado la fecha de consolidación conjunta en
   lugar de plazos por tarea.

4. **Tareas diferidas (5).** Quedaron en estado *Por hacer*: *Fine-tuning RF-DETR
   con dataset propio* (Fase 2), *Evaluación cuantitativa HOTA/MOTA* (Fase 3),
   *Panel de estadísticas por jugador* y *Exportación de clips de jugadas*
   (Fase 4) y *Tests de integración E2E del pipeline completo* (Fase 5). Ninguna
   es bloqueante: el sistema funciona con el detector preentrenado, con validación
   funcional y unitaria, y con el flujo principal completo. Estas tareas se
   presentan como vías de continuación naturales.

5. **Limitación instrumental en la extracción de datos.** La consulta directa de la
   base de datos del tablero Kanban (modo SQL/vista) no estuvo disponible por
   requerir un plan de Notion superior, por lo que la enumeración de tareas se
   realizó mediante búsqueda semántica sobre el tablero y se cruzó con los *commits*
   etiquetados del repositorio. Esto explica la diferencia menor entre el conteo del
   tablero (55 tarjetas) y el enumerado aquí (51 hoja + 4 contenedores).
