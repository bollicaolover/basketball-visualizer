# Capítulo 6 — Desarrollo del sistema

> Fuente única de verdad para redactar el **Capítulo 6** de la memoria del TFG
> *basketball-visualizer*. Sustituye a los antiguos `indice-cap6-desarrollo.md` y
> `memoria_fases_proyecto.md`.
>
> **Estructura.** El capítulo se organiza por las **seis áreas funcionales** del
> tablero Kanban (= funcionalidad conseguida), no por fases lineales, porque el
> desarrollo fue iterativo y no lineal (véase [`metodologia.md`](metodologia.md)).
> Cada área se desarrolla con el patrón: **objetivo → tarjetas (incluidos
> experimentos y *rework*) → decisiones técnicas (alternativas comparadas) →
> problemas e iteraciones → resultado**. Así el capítulo *demuestra* la metodología
> del Capítulo 3 en lugar de solo describirla.
>
> Los datos numéricos (LoC, métricas, latencias) provienen de
> [`datos-reales-tfg.md`](datos-reales-tfg.md). Los *hashes* de *commit* se
> añadirán tras la reconstrucción del historial de *git*.

---

## 6.1 Análisis funcional

### 6.1.1 Requisitos funcionales (selección)

| ID | Requisito |
|----|-----------|
| RF-01 | Subir un vídeo de baloncesto y lanzar su análisis desde la web. |
| RF-02 | Detectar jugadores, árbitros, balón y aro por fotograma. |
| RF-03 | Seguir a cada jugador con identidad temporal estable. |
| RF-04 | Clasificar a cada jugador por equipo sin etiquetas previas. |
| RF-05 | Reconocer el dorsal y resolver el nombre del jugador vía *roster*. |
| RF-06 | Proyectar las posiciones a una vista cenital 2D (homografía). |
| RF-07 | Resolver la posesión del balón y detectar eventos de canasta. |
| RF-08 | Reconocer bloqueos (*screens*) a partir de las trayectorias. |
| RF-09 | Visualizar vídeo anotado + minimapa 2D sincronizados por fotograma. |
| RF-10 | Seleccionar GPU y seguir el progreso del trabajo desde la web. |

### 6.1.2 Requisitos no funcionales (selección)

| ID | Requisito |
|----|-----------|
| RNF-01 | Procesado **por lotes** (no tiempo real): ≈ 0,7 fps medido. |
| RNF-02 | Exactitud de OCR de dorsal ≥ 85 % (medido: **85,26 %**). |
| RNF-03 | Reproducibilidad del entorno (Conda + Node embebido; Apptainer). |
| RNF-04 | Escalado multi-GPU por *chunking* (*speedup* 1,48× en 2× A100). |
| RNF-05 | Ejecutable en GPU de gama media (VRAM pico ≈ 7,8 GB). |

### 6.1.3 Casos de uso

Actor principal: **entrenador/analista**. Casos: *subir partido*, *seleccionar
GPU*, *seguir progreso*, *visualizar resultados (vídeo + minimapa)*, *gestionar
roster*, *consultar historial*. (Diagrama UML de casos de uso en `docs/uml/`.)

---

## 6.2 Arquitectura del sistema

Tres piezas desacopladas (detalle en [`arquitectura.md`](arquitectura.md)):

```
Frontend (Vue 3 + Vite)  ──HTTP /api/*──►  Backend (FastAPI)  ──subprocess──►  Pipeline ML (pipeline/)
        SPA              ◄──JSON/vídeo──         main.py        python -m pipeline.run
```

- **Frontend** (`frontend/`, ~4.513 LoC): SPA; sube, sondea estado, visualiza.
- **Backend** (`backend/`, ~1.037 LoC): FastAPI; auth, jobs, *lock* por GPU,
  *chunking* multi-GPU; sirve el *frontend* compilado. Sin Celery/Redis.
- **Pipeline ML** (`pipeline/`, ~5.112 LoC): el análisis de visión real.

Decisión clave: **persistencia en sistema de ficheros** (no BD) y ejecución del
*pipeline* como **subproceso** con *lock* por GPU, priorizando simplicidad
operativa y procesado por lotes en GPU.

> El esqueleto modular de `backend/app/core/` (vision/classifier/expert) quedó como
> **andamiaje vacío**; la lógica real vive en `backend/app/main.py` y `chunking.py`.
> El clasificador GNN y el motor experto **no se implementaron** (ficheros de 0
> líneas) y se presentan como **vías futuras**, no como trabajo hecho.

---

## 6.3 Desarrollo por áreas funcionales (tablero Kanban)

### 6.3.1 Área — Detección & Tracking
**Carpetas:** `pipeline/detection/`, `pipeline/tracking/`, `pipeline/io/`.

**Objetivo.** Pasar de fotogramas de difusión a una representación estructurada y
estable: qué entidades hay en pista y dónde, con identidad temporal.

**Tarjetas.**
- Detector de jugadores/balón/aro **RF-DETR** (11 clases, incl.
  `player-in-possession` y clases de acción).
- I/O de vídeo y tipos base del *pipeline* (`pipeline/io/`, `tracking/types.py`).
- *Tracker* de jugadores **SAM 3** (*prompt-once* sembrado por RF-DETR +
  *re-prompt* periódico).
- *Tracker* de balón con **filtro de Kalman** + punto de apoyo por máscara.
- Deduplicación de detecciones y consolidación del *player tracker*.
- Suavizado y estabilización de trayectorias (`tracking/smoother.py`).
- *(Por hacer)* Fine-tuning de RF-DETR con *dataset* propio.

**Decisiones técnicas (alternativas comparadas).**
- **RF-DETR vs YOLOv8** → se elige RF-DETR por mejor comportamiento en escenas
  densas y oclusiones, a costa de algo más de latencia (≈ 91 ms/frame), asumible
  en procesado diferido. *(Comparativa realizada en el laboratorio previo.)*
- **SAM 3 vs ByteTrack** → SAM 3 mantiene la identidad bajo oclusión severa por
  continuidad de máscara; ByteTrack opera solo sobre cajas y pierde el ID. Coste:
  ≈ 424 ms/frame (cuello de botella del *pipeline*).

**Problemas e iteraciones (no linealidad).**
- En vídeos largos, SAM acumulaba estado y derivaba la identidad → se intentó
  segmentar por sesiones con *re-prompt*; **el intento se revirtió** tras evaluarlo.
- El trabajo de *tracking* reveló fallos de detección → tarjetas correctivas en
  Detección (*rework*).

**Resultado.** Detección + seguimiento con identidad temporal estable, base para
el resto del sistema.

---

### 6.3.2 Área — Geometría & Homografía
**Carpetas:** `pipeline/court/`.

**Objetivo.** Proyectar la pista y las posiciones de los agentes a una vista
cenital 2D estable.

**Tarjetas.**
- Geometría de cancha FIBA y definición de segmentos (`court/geometry.py`).
- Detector de *keypoints* de cancha (`court/keypoints.py`).
- Estimación de homografía (DLT/SVD/RANSAC) + modelo PnP (`court/homography.py`).
- Calibración automática de cámara encadenando *keypoints* → homografía
  (`court/camera_model.py`).
- Render del minimapa cenital 2D.

**Decisiones técnicas.**
- Homografía por *keypoints* con respaldo: cuando el error de la pose PnP supera
  un umbral, el minimapa recurre a la **homografía de respaldo**, manteniendo la
  estabilidad.

**Problemas e iteraciones.**
- La pose PnP no se activaba con fiabilidad en vídeo de difusión por el ruido de
  los *keypoints* → solución de respaldo descrita arriba.

**Resultado.** Vista cenital 2D estable; es el área de mayor volumen de código del
*pipeline* (`court/` ≈ 1.918 LoC).

---

### 6.3.3 Área — Identidad & Equipos
**Carpetas:** `pipeline/identity/`, `pipeline/teams/`.

**Objetivo.** Asignar equipo y dorsal/nombre a cada jugador seguido.

**Tarjetas.**
- Clasificador de equipos **SigLIP + UMAP + K-means (k=2)**, sin etiquetas, voto
  por *track*.
- OCR de dorsal con **SmolVLM2** ajustado localmente (PEFT/LoRA), voto por IoS.
- *Roster* de jugadores: resolución del nombre a partir del dorsal y la plantilla.

**Decisiones técnicas (alternativas comparadas).**
- **SigLIP/UMAP/K-means vs histogramas de color** → el enfoque no supervisado es
  robusto ante iluminación y colores de camiseta similares; el de color es frágil.
- **SmolVLM2 vs PARSeq/TrOCR** → el VLM es más robusto ante dorsales deformados,
  ocluidos o rotados; coste: es la etapa más cara (≈ 550 ms/frame).

**Datos reales.** Ajuste fino de SmolVLM2: 0,81 % de parámetros entrenables, 5
épocas (*loss* 0,45 → 0,01); **exactitud medida 85,26 %** (266/312 muestras).

**Resultado.** Identidad de equipo y dorsal/nombre por jugador. Errores típicos:
confusión de 1↔2 dígitos y *crops* ocluidos.

---

### 6.3.4 Área — Analytics & Reglas
**Carpetas:** `pipeline/possession/`, `pipeline/scoring/`, `pipeline/strategy/`,
`pipeline/tactics/`, `pipeline/pose/`.

**Objetivo.** Elevar la información de «dónde está cada agente» a «qué ocurre
tácticamente». **Esta área concentra la ampliación de alcance posterior a la
entrega ordinaria del 18 de mayo.**

**Tarjetas.**
- Resolver de posesión del balón por **histéresis temporal** (`possession/resolver.py`).
- **Robustez del resolutor** ante oclusión y aglomeraciones *(tarjeta de rework)*.
- Módulo de estrategia y reglas de juego (`strategy/rules.py`).
- *Shot tracker*: eventos de canasta a partir de clases de acción + `ball-in-basket`.
- **Reconocimiento de pantallas (*screens*)** sobre trayectorias (método de Chen
  et al., 2012), en post-proceso con *flag* `--tactics` (`tactics/`).
- Detector de **lanzamiento por pose** (YOLOv8-pose, *opt-in*) que dispara la
  reconstrucción 3D del tiro (`pose/release_detector.py`).
- *(Por hacer)* Evaluación cuantitativa HOTA/MOTA.

**Decisiones técnicas.**
- Posesión por **histéresis temporal** en lugar de umbral instantáneo, para evitar
  parpadeos de asignación entre jugadores próximos.
- Reconocimiento de bloqueos por **reglas geométricas sobre trayectorias** (no un
  modelo aprendido) por ausencia de datos etiquetados y por interpretabilidad.

**Problemas e iteraciones.**
- La robustez de posesión nació de fallos detectados en pruebas funcionales del
  *pipeline* completo (*feedback loop* característico de Kanban).
- El reconocimiento de bloqueos generaba falsos positivos en zonas densas → se
  calibraron umbrales en `TacticsSettings` (ver `tacticas-screen-recognition.md`).

**Resultado.** Posesión robusta, detección de canastas, reconstrucción 3D del tiro
(RMSE ≈ 2,1 px) y reconocimiento de bloqueos. **Validación funcional** sobre clip
Celtics–Knicks: posesión 85,4 %/14,6 %, 1/1 tiro detectado.

---

### 6.3.5 Área — Core & Infrastructure (web e integración)
**Carpetas:** `backend/`, `frontend/`.

**Objetivo.** Convertir el *pipeline* en un sistema completo y usable.

**Tarjetas — Backend.**
- Configurar proyecto **FastAPI** + autenticación por **token HMAC**.
- Endpoint de subida + **transcodificación por *chunks*** (`chunking.py`).
- Endpoints de resultados + orquestación del *pipeline* por **subproceso**.
- *Wrappers* de visión en el *backend* (primera integración del prototipo).
- Endpoint de tácticas (`tactics.json`).

**Tarjetas — Frontend (SPA Vue 3).**
- *Scaffold* Vue 3 + Vite + *design tokens*; capa de servicios API.
- Vistas: Login, Subida (job + *polling* + config de equipos), Resultados
  (reproductor sincronizado con minimapa 2D).
- *App shell*, *sidebar*, modal de progreso, *sparkline*, *stats* de GPU/sistema.
- Panel de pantallas y trayectoria de tiro.

**Tarjetas — Integración.**
- *Metadata writer* (JSON por fotograma) como **contrato estable** *pipeline*↔*frontend*.
- Orquestador por fotograma + CLI (`run.py`, `run_batch.sh`) + **multi-GPU** por *chunking*.
- Empaquetado: `serve.sh` + `dist` compilado; reproducibilidad con **Apptainer**.

**Decisiones técnicas.**
- **Vue 3 + Vite** (curva corta, Composition API) frente a React/Angular.
- **FastAPI** (async + Pydantic) frente a Flask/Django.
- *Jobs* en *background* + subproceso por GPU con *lock*, en lugar de cola
  distribuida (Celery/Redis), por simplicidad operativa.
- **Sincronización por metadatos JSON por fotograma**, que desacopla el *render*
  del *frontend* del *pipeline* y permitió integrar la versión modular sin rehacer
  la interfaz.

**Problemas e iteraciones.**
- La interfaz se desarrolló contra un *pipeline* aún en evolución → el contrato de
  metadatos JSON permitió integrar después la versión modular sin reescribir el
  *frontend*.
- Incorporar las tácticas exigió ampliar API y vista de resultados ya cerradas →
  se añadieron de forma incremental (`tactics.json` + panel).

**Resultado.** Sistema ejecutable de extremo a extremo: web con acceso, subida,
selección de GPU, progreso y visualización (vídeo anotado + minimapa + paneles).

---

## 6.4 Rendimiento del sistema (resumen)

| Indicador | Valor medido |
|-----------|--------------|
| Latencia *pipeline* | ≈ 1.402 ms/frame ≈ **0,7 fps** (1× A100) |
| Cuellos de botella | OCR SmolVLM2 (39 %), SAM 3 (30 %) |
| VRAM pico | ≈ **7,8 GB** (cabe en GPU de gama media) |
| *Speedup* multi-GPU | **1,48×** en 2× A100 (*chunking*) |
| OCR de dorsal | **85,26 %** (266/312) |

Detalle completo y reproducibilidad en [`datos-reales-tfg.md`](datos-reales-tfg.md).

---

## 6.5 Tarjetas diferidas (alcance consciente)

Quedaron en `Por hacer`, ninguna bloqueante: *fine-tuning* de RF-DETR con *dataset*
propio, evaluación HOTA/MOTA, panel de estadísticas por jugador y tests de
integración E2E. Se presentan como vías de continuación naturales (Capítulo 8).
