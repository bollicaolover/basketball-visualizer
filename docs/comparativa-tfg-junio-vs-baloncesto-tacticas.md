# Comparativa: `tfg-junio` vs `tfg-baloncesto-tacticas`

> Documento de apoyo para la memoria del TFG. Resume las diferencias entre el
> repositorio que se presenta (`tfg-junio`) y el proyecto predecesor donde se
> acumuló la mayor parte del trabajo experimental (`tfg-baloncesto-tacticas`).
>
> **Autor:** Gonzalo del Fraile Andújar  
> **Fecha:** 17 de junio de 2026  
> **Uso previsto:** citar trabajo previo, justificar decisiones de diseño y
> reutilizar métricas/experimentos sin versionar todo el repo antiguo.

---

## 1. Relación entre ambos proyectos

| Aspecto | `tfg-baloncesto-tacticas` | `tfg-junio` |
|---------|---------------------------|-------------|
| **Rol** | Proyecto original / laboratorio de experimentación | Versión final para entrega y defensa |
| **Nombre comercial** | Basketball Tactics Analyzer | basketball-visualizer |
| **Commits git** | ~19 | ~43 |
| **LoC pipeline Python** | ~12.505 | ~5.112 |
| **LoC tests Python** | ~5.827 | ~290 |
| **LoC frontend (Vue/JS/CSS)** | ~2.140 | ~4.513 |
| **Memoria TFG (.docx)** | Sí (`TRABAJO FIN DE GRADO.docx`) | PDF de apoyo (`TFG Análisis Baloncesto Inteligente.pdf`) |
| **Dependencia directa** | — | Enlaza modelos vía `scripts/fetch_models.py` → symlinks a `tfg-baloncesto-tacticas/models/` |

**Idea clave:** `tfg-junio` no parte de cero. Es una **refactorización y convergencia**
sobre el trabajo previo: conserva la proyección 2D, la app web y parte de los
modelos entrenados, pero **cambia la pila de detección/tracking/identidad** y
**elimina módulos experimentales** (acciones por pose, Re-ID, TensorRT, etc.)
que no forman parte del sistema presentado.

```
tfg-baloncesto-tacticas                    tfg-junio
─────────────────────────                  ─────────
YOLO E-BARD + BoT-SORT          ──►        RF-DETR (11 clases) + SAM 3
TensorRT FP16                   ──►        PyTorch directo
3 clasificadores de equipos     ──►        SigLIP + UMAP + K-means (sin etiquetas)
PARSeq / YOLO dígitos / OCR     ──►        SmolVLM2 fine-tuned (OCR dorsal)
Re-ID OSNet (SportsMOT)         ──►        (descartado; SAM mantiene identidad)
Acciones por pose (ST-GCN…)     ──►        (descartado; tiros vía clases RF-DETR)
~40 tests + benchmarks          ──►        4 tests unitarios + eval OCR
Docker + systemd + Gradio       ──►        serve.sh + FastAPI monolítico
```

---

## 2. Objetivo funcional común

Ambos proyectos comparten el **mismo objetivo de alto nivel**:

> Procesar un vídeo de baloncesto y producir (1) un vídeo anotado con jugadores,
> equipos y eventos, y (2) un **mapa cenital 2D** con posiciones proyectadas
> sobre la cancha.

Salidas comunes:

- Vídeo overlay (`overlay.mp4` / `out.mp4`)
- Mapa cenital (`out_map.mp4`)
- Metadatos JSON por frame (posiciones, posesión, equipos…)
- Aplicación web Vue 3 + API FastAPI para subir, procesar y visualizar

---

## 3. Diferencias en la pila de visión por computador

### 3.1 Detección

| | `tfg-baloncesto-tacticas` | `tfg-junio` |
|---|---------------------------|-------------|
| **Modelo** | YOLOv11 fine-tuned (E-BARD) | RF-DETR (11 clases, DINOv2) |
| **Clases** | 4: `basketball`, `hoop`, `player`, `referee` | 11: jugadores, balón, aro, dorsal, acciones (`player-jump-shot`, `player-layup-dunk`, `player-shot-block`, `player-in-possession`, `ball-in-basket`…) |
| **Inferencia** | TensorRT FP16 (`trt_engine.py`) + fallback PyTorch | PyTorch nativo (`rfdetr_detector.py`) |
| **mAP@50 (test)** | **0,889** (E-BARD) | *Pendiente de medición formal en tfg-junio* |
| **Latencia detector** | ~13–19 ms/frame (51 FPS aislado) | ~91 ms/frame en pipeline completo (~6,5 % del total) |

**Ventaja de RF-DETR en junio:** las clases semánticas de acción y posesión
permiten resolver tiros y balón en posesión **sin un módulo de pose separado**.

### 3.2 Tracking de jugadores

| | `tfg-baloncesto-tacticas` | `tfg-junio` |
|---|---------------------------|-------------|
| **Algoritmo** | BoT-SORT (boxmot) + Re-ID OSNet opcional | SAM 3 (segmentación, prompt-once desde RF-DETR) |
| **Salida** | Bounding box + `track_id` | Máscara binaria + `track_id` |
| **MOT (SportsMOT val)** | MOTA 80,7 · IDF1 58,3 · 1.968 ID switches | *No evaluado con métricas MOT estándar* |
| **Post-procesado** | Dedup IoU, smoother de cajas, guard de ID swap, swap detection, roster tracker | Foot point por máscara (`MaskFootPoint`) |
| **Coste en pipeline** | ~96 ms/frame (70 % del total YOLO-stack) | ~424 ms/frame (30 % del total RF-DETR-stack) |

**Ventaja de SAM 3:** máscaras limpias para clasificación de equipos, OCR de
dorsal y proyección del punto de apoyo. **Inconveniente:** mucho más lento que
BoT-SORT; es el segundo cuello de botella del sistema final.

### 3.3 Clasificación de equipos

| | `tfg-baloncesto-tacticas` | `tfg-junio` |
|---|---------------------------|-------------|
| **Enfoque** | Supervisado (CNN ResNet) o zero-shot (CLIP) o no supervisado (KMeans) | **Solo no supervisado:** SigLIP embeddings + UMAP + K-means |
| **Precisión medida** | CNN **91,7 %** · CLIP 83,3 % · Cluster 72,7 % | *No evaluado con ground truth anotado* |
| **Ventaja** | Tres backends intercambiables (`Settings`) | Sin necesidad de dataset etiquetado por equipo |
| **Roster** | `RosterTracker` (empareja dorsales detectados) | JSON de roster + emparejamiento por color/dorsales en frontend |

### 3.4 Identificación de jugadores (dorsales)

| | `tfg-baloncesto-tacticas` | `tfg-junio` |
|---|---------------------------|-------------|
| **Enfoques probados** | PARSeq NBA, detector YOLO de dígitos, OCR genérico, clasificador CNN de camiseta | **SmolVLM2** fine-tuned (PEFT, 0,81 % params entrenables) |
| **Exactitud dorsal** | PARSeq ~96,8 % (plantilla; no verificado en repo) | **85,26 %** (266/312 test, medido con `eval_jersey_ocr.py`) |
| **Coste en pipeline** | Variable según backend | **550 ms/frame (39 % del total)** — principal cuello de botella |
| **Scripts de entrenamiento** | `train_parseq_dorsal.py`, `train_dorsal_detector.py`, `build_dorsal_*_dataset.py` | `train_jersey_ocr.py`, `download_jersey_dataset.py` |

### 3.5 Cancha, homografía y proyección 2D

| | `tfg-baloncesto-tacticas` | `tfg-junio` |
|---|---------------------------|-------------|
| **Keypoints** | YOLOv11-Pose, 33 keypoints | **Mismo checkpoint** (`court-keypoints/best.pt`, enlazado) |
| **Homografía** | RANSAC + buffer por segmentos | RANSAC + estabilizador + **modelo PnP de cámara** (`camera_model.py`) |
| **Residual px (media)** | 11,09 px | *Comparte lógica base; PnP añade estabilidad en junio* |
| **Jugadores dentro cancha** | 100 % | Validado funcionalmente en clips NBA |
| **Suavizado** | `WorldTrackSmoother` + `PlayerBoxSmoother` | `WorldTrackSmoother` + `sports.clean_paths` opcional |

> El módulo `pipeline/court/` es el **más heredado** entre ambos repos (geometría,
> homografía, renderer, segments, smoothing, stabilizer).

### 3.6 Posesión, tiros y eventos

| | `tfg-baloncesto-tacticas` | `tfg-junio` |
|---|---------------------------|-------------|
| **Posesión** | `PossessionTracker` (proximidad + continuidad + penalización cambio equipo) | `PossessionResolver` (proximidad + clase `player-in-possession` + histéresis) |
| **Canastas / tiros** | `BasketEventDetector` (proximidad balón-aro) | `ShotTracker` (clases RF-DETR `player-jump-shot`, `player-layup-dunk`, `ball-in-basket`) |
| **Acciones por pose** | **Sí:** ST-GCN, PoseConv3D, SpaceJam (10 clases) | **No** (descartado; documentado como vía futura) |
| **Eventos de interacción** | Pase, rebote, robo (`pipeline/actions/events.py`) | No implementado |

### 3.7 Reconocimiento de acciones (solo en baloncesto-tacticas)

Módulo experimental completo en `pipeline/actions/`:

- `pose_extractor.py` — YOLO11m-Pose (17 keypoints COCO)
- `pose_buffer.py` — ventana temporal por track
- `stgcn.py` / `posec3d.py` — clasificadores espacio-temporales
- `action_classifier.py` / `recognizer.py` — orquestación
- Dataset: **SpaceJam** (10 clases de gesto)
- Documentación: `docs/memoria/reconocimiento_acciones.md`

**Decisión en tfg-junio:** descartado del alcance. Los tiros se detectan por
clases del detector RF-DETR, no por pose. Justificación en memoria: complejidad,
dataset sintético limitado y cuellos de botella adicionales.

---

## 4. Rendimiento comparativo

### 4.1 Throughput end-to-end

| Métrica | `tfg-baloncesto-tacticas` (YOLO stack) | `tfg-junio` (RF-DETR + SAM + VLM) |
|---------|----------------------------------------|-----------------------------------|
| **ms/frame total** | **136,5** (~7,3 fps) | **1.402** (~0,7 fps) |
| **Ratio tiempo real** | ~4× más rápido que real-time | ~47× más lento que real-time |
| **VRAM pico (1 GPU)** | No medido formalmente | **7,8 GB** (4 modelos en A100) |
| **Multi-GPU speedup** | No implementado | **1,48×** (2× A100, chunking) |

### 4.2 Desglose por etapa

**baloncesto-tacticas** (139 frames, clip Celtics-Knicks Q1):

| Etapa | ms/frame | % |
|-------|----------|---|
| Detección YOLO | 16,7 | 12,2 |
| Tracking BoT-SORT | 95,9 | 70,3 |
| Clasificación equipos | 6,3 | 4,6 |
| Keypoints + homografía | 16,9 | 12,4 |
| Proyección + render | <1 | <1 |

**tfg-junio** (109 frames, clip Celtics-Knicks Q2):

| Etapa | ms/frame | % |
|-------|----------|---|
| OCR dorsal (SmolVLM2) | 550,5 | 39,3 |
| Tracking SAM 3 | 424,4 | 30,3 |
| Calibración equipos (una vez) | 175,0 | 12,5 |
| Equipos SigLIP | 101,5 | 7,2 |
| Detección RF-DETR | 91,5 | 6,5 |
| Cancha + homografía | 31,3 | 2,2 |
| Resto (render, posesión…) | <10 | <2 |

**Lectura para la memoria:** el stack YOLO es ~10× más rápido pero menos rico
semánticamente. El stack RF-DETR+SAM+VLM sacrifica velocidad a cambio de
máscaras, dorsales y clases de acción integradas.

---

## 5. Arquitectura de software

### 5.1 Pipeline

| Componente | baloncesto-tacticas | tfg-junio |
|------------|---------------------|-----------|
| **Entrada CLI** | `python -m pipeline.run` | `python run.py` / `python -m pipeline.run` |
| **Configuración** | `Settings` con 3 perfiles (`default`, `legacy_identity`, `debug`) | `Settings` único + flags CLI |
| **Módulos exclusivos** | `actions/`, `dorsals/`, `reid/`, `legacy/`, `nba/`, `runtime/`, `strategy/` | `identity/` (OCR + roster), `profiling.py`, `io/` |
| **Orquestador** | ~1.040 LoC (incluye acciones, dorsales, swap detection…) | ~640 LoC (más acotado) |
| **Multi-GPU** | No | Sí (`chunking` en backend) |

### 5.2 Backend (FastAPI)

Ambos comparten la misma idea: API REST + jobs en background + subprocess del pipeline.

| Característica | baloncesto-tacticas | tfg-junio |
|----------------|---------------------|-----------|
| **Estructura** | `backend/app/main.py` monolítico | `backend/app/` modular (`api/`, `core/`, `db/`, `utils/`) |
| **Auth** | Básica | HMAC token (`LoginView`) |
| **Anotaciones usuario** | POST/GET `/annotations` | No |
| **Transcodificación** | No | Sí (chunks para subida) |
| **Persistencia** | Sistema de ficheros | Sistema de ficheros (sin PostgreSQL en runtime) |
| **Scaffolding futuro** | — | `core/expert/`, `core/classifier/` → **ficheros vacíos** (GNN, motor experto) |

### 5.3 Frontend (Vue 3 + Vite)

| | baloncesto-tacticas | tfg-junio |
|---|---------------------|-----------|
| **Vistas** | Login, Upload, Results | Login, Upload, Results |
| **Componentes extra** | ProcessingModal | AppSidebar, ProcessingModal, Sparkline (stats GPU) |
| **Design system** | Básico | Tokens CSS (`tokens.css`), paleta NBA, fuentes Saira Condensed |
| **Roster interactivo** | Limitado | Reorientación equipo claro/oscuro por dorsales |
| **dist/ versionado** | Sí | Sí |

### 5.4 Infraestructura y despliegue

| | baloncesto-tacticas | tfg-junio |
|---|---------------------|-----------|
| **Contenedores** | `docker/docker-compose.yml` (Postgres, MinIO) | Apptainer rootless con GPU (`deploy/apptainer/`); `serve.sh` local |
| **systemd** | `basket2d.service` | No |
| **Scripts arranque** | `start.sh`, `stop.sh`, `serve.sh`, `tunnel.py` | `serve.sh`, `run_batch.sh` |
| **Gradio** | `.gradio_tmp/` (prototipos) | No |
| **Entorno conda** | `tfg-baloncesto` (compartido) | `tfg-baloncesto` (reutilizado) |

---

## 6. Modelos entrenados y datasets

### 6.1 Solo en `tfg-baloncesto-tacticas` (trabajo previo reutilizable en docs)

| Modelo | Dataset | Script | Métrica destacada |
|--------|---------|--------|-------------------|
| YOLO E-BARD detección | E-BARD | `train_yolo_ebard.py` | mAP@50 = 0,889 |
| YOLO E-BARD JNR | E-BARD JNR | `prepare_ebard_jnr.py` | Variante ligera |
| Court keypoints | Roboflow court keypoints | `train_court_keypoints.py` | Residual homografía ~11 px |
| Jersey CNN (equipos) | jersey_crops | `train_jersey_classifier.py` | Acc 91,7 % |
| Re-ID OSNet | SportsMOT | `train_reid.py` | Fine-tune 60 epochs |
| PARSeq dorsales | dorsal_recognition_* | `train_parseq_dorsal.py` | ~96,8 % (plantilla) |
| Dorsal digits YOLO | dorsal_digits | `train_dorsal_detector.py` | Detección de dígitos |
| ST-GCN acciones | SpaceJam | `train_action_stgcn.py` | Experimental |
| PoseConv3D acciones | SpaceJam | `train_action_posec3d.py` | Experimental |
| RF-DETR 11 clases | Roboflow basketball | `train_rfdetr.py` | **Usado en junio** |
| SAM 3 | Meta (pretrained) | — | **Usado en junio** |

### 6.2 Entrenado en `tfg-junio`

| Modelo | Dataset | Script | Métrica |
|--------|---------|--------|---------|
| SmolVLM2 OCR dorsal | Roboflow jersey-numbers (2.547 pares) | `train_jersey_ocr.py` | **85,26 %** exactitud test |

### 6.3 Enlace entre repos (`fetch_models.py`)

`tfg-junio` **no duplica** los checkpoints pesados; crea symlinks desde
`tfg-baloncesto-tacticas`:

```
models/artifacts/checkpoint_best_ema.pth  →  models/detection/     (RF-DETR)
models/artifacts/court-keypoints/best.pt  →  models/court-keypoints/
models/artifacts/sam3/                    →  models/sam3/
models/artifacts/parseq-nba/              →  models/parseq-nba/      (bootstrap OCR)
models/artifacts/legibility/              →  models/legibility/      (bootstrap OCR)
```

---

## 7. Tests y evaluación

### 7.1 Cobertura de tests

| | baloncesto-tacticas | tfg-junio |
|---|---------------------|-----------|
| **Nº ficheros test** | ~35 | 4 |
| **Ámbitos** | Detección, tracking, MOT, homografía, equipos (×3), posesión, canastas, acciones, oclusión, dedup, swap, integración e2e, vídeo web | Chunking multi-GPU, posesión, homografía, roster |
| **Benchmarks** | `benchmark.py`, `compare_models.py`, `evaluate_coco.py` | `measure_performance.py`, `eval_jersey_ocr.py` |

### 7.2 Scripts de evaluación (baloncesto-tacticas → citar en memoria)

| Script | Métrica | Resultado guardado |
|--------|---------|-------------------|
| `eval_detection.py` | mAP@50, mAP@50-95, F1 por clase | `docs/results/detection_metrics.json` |
| `eval_tracking_mot.py` | MOTA, IDF1, ID switches | `docs/results/tracking_metrics.json` |
| `eval_teams.py` | Accuracy, F1 (CNN/CLIP/Cluster) | `docs/results/teams_metrics.json` |
| `eval_homography.py` | Residual px, inliers, confianza | `docs/results/homography_metrics.json` |
| `eval_speed.py` | ms/frame por etapa | `docs/results/speed_metrics.json` |
| `eval_dorsal_recognition.py` | Exactitud OCR/PARSeq | — |
| `eval_per_number.py` | Exactitud por dorsal | — |

### 7.3 Documentación de métricas

- **baloncesto-tacticas:** `docs/metricas_evaluacion.md` — guía completa de
  evaluación por etapa (8 secciones, umbrales objetivo, comandos reproducibles).
- **tfg-junio:** `docs/datos-reales-tfg.md` + `docs/perf-results.json` —
  métricas medidas del sistema final (OCR, pipeline, VRAM, multi-GPU).

---

## 8. Documentación disponible en cada repo

### 8.1 `tfg-junio/docs/` (repo de entrega)

| Fichero | Contenido |
|---------|-----------|
| `arquitectura.md` | Frontend, backend, pipeline; tabla "quiero cambiar X" |
| `metodologia.md` | Kanban (ágil, individual), tablero, trazabilidad, iteraciones |
| `estado-del-arte.md` | Cap. 2: conceptos, alternativas, justificación RF-DETR+SAM3 |
| `datos-reales-tfg.md` | Métricas medidas, commits, LoC, componentes NO implementados |
| `plan-tfg.md` | Plan de redacción memoria, progreso por capítulo |
| `perf-results.json` | VRAM y speedup multi-GPU |
| `comparativa-*.md` | Este documento |

### 8.2 `tfg-baloncesto-tacticas/docs/` (trabajo previo)

| Fichero / carpeta | Contenido |
|-------------------|-----------|
| `metricas_evaluacion.md` | Metodología de evaluación completa (YOLO era) |
| `results/*.json` | Métricas JSON reproducibles (detección, tracking, equipos, homografía, speed) |
| `memoria/reconocimiento_acciones.md` | Módulo ST-GCN/PoseConv3D (vía futura) |
| `annotations/` | Ground truth equipos (`teams_gt.json`) |
| `images/` | Figuras para memoria |
| `TRABAJO FIN DE GRADO.docx` | Memoria completa (en raíz del repo) |

---

## 9. Qué incluir en la memoria sin subir todo baloncesto-tacticas

### 9.1 Citar como trabajo previo / evolución del proyecto

En la memoria conviene explicar que el TFG pasó por **dos iteraciones**:

1. **Fase exploratoria** (`tfg-baloncesto-tacticas`): stack YOLO+BoT-SORT, múltiples
   backends, Re-ID, acciones por pose, TensorRT, evaluación exhaustiva (~35 tests).
2. **Fase de convergencia** (`tfg-junio`): selección de RF-DETR+SAM3+SmolVLM2,
   simplificación del pipeline, foco en identificación y proyección 2D.

Esto demuestra un **proceso iterativo y experimental** (probar alternativas, medir,
descartar), coherente con el flujo continuo de Kanban: las tarjetas de experimento y
de *rework* se incorporaban según los resultados empíricos.

### 9.2 Métricas reutilizables del repo antiguo

| Para argumentar… | Métrica de baloncesto-tacticas | Nota |
|------------------|-------------------------------|------|
| Viabilidad detección baloncesto | mAP@50 = 0,889 (YOLO E-BARD) | Comparar con estado del arte; RF-DETR es la evolución |
| Calidad tracking clásico | MOTA 80,7 · IDF1 58,3 | Contexto; SAM3 no evaluado con MOT Challenge |
| Clasificación equipos supervisada vs no supervisada | CNN 91,7 % vs SigLIP+KMeans | Justifica elección no supervisada en junio |
| Homografía estable | Residual 11 px, 100 % dentro cancha | Compartido (mismo keypoint model) |
| Velocidad stack anterior | 7,3 fps end-to-end | Contraste con 0,7 fps del stack final |
| Acciones por pose (futuro) | Doc `reconocimiento_acciones.md` | Vías futuras del cap. 8 |

### 9.3 Material que NO hace falta versionar en tfg-junio

- Pesos de modelos (`.pt`, `.pth`, `.engine`) — ya enlazados por symlink
- Datasets (`data/raw/`, `data/dorsal_*`, SportsMOT…) — decenas de GB
- Logs de entrenamiento (`train_*.log`, `entrenamiento.log`)
- Outputs de jobs (`data/outputs/` — cientos de UUIDs)
- Prototipos Gradio (`.gradio_tmp/`)
- Notebooks experimentales
- Memoria `.docx` (vive en baloncesto-tacticas; junio tiene PDF resumen)

### 9.4 Ficheros pequeños que sí conviene copiar/referenciar

```
tfg-baloncesto-tacticas/docs/results/*.json     → citar tablas en cap. 7
tfg-baloncesto-tacticas/docs/metricas_evaluacion.md → metodología evaluación previa
tfg-baloncesto-tacticas/docs/memoria/reconocimiento_acciones.md → cap. 8 futuro
tfg-baloncesto-tacticas/docs/annotations/teams_gt.json → eval equipos
```

---

## 10. Tabla resumen de características

| Característica | baloncesto-tacticas | tfg-junio | Presentado |
|----------------|:-------------------:|:---------:|:----------:|
| Detección RF-DETR 11 clases | ✓ (entrenado) | ✓ (usado) | ✓ |
| Detección YOLO E-BARD | ✓ (producción) | — | — |
| Tracking SAM 3 | ✓ (artefacto) | ✓ (usado) | ✓ |
| Tracking BoT-SORT + Re-ID | ✓ | — | — |
| TensorRT FP16 | ✓ | — | — |
| Clasificación equipos SigLIP | — | ✓ | ✓ |
| Clasificación equipos CNN/CLIP | ✓ | — | — |
| OCR dorsal SmolVLM2 | — | ✓ (entrenado) | ✓ |
| OCR dorsal PARSeq/dígitos | ✓ (experimental) | — | — |
| Keypoints cancha + homografía | ✓ | ✓ (heredado) | ✓ |
| Mapa cenital 2D | ✓ | ✓ | ✓ |
| Posesión balón | ✓ | ✓ | ✓ |
| Detección tiros/canastas | ✓ (proximidad) | ✓ (clases RF-DETR) | ✓ |
| Acciones por pose (ST-GCN) | ✓ (experimental) | — | Futuro |
| Roster → nombre jugador | Parcial | ✓ | ✓ |
| App web Vue 3 | ✓ | ✓ (mejorada) | ✓ |
| Multi-GPU chunking | — | ✓ | ✓ |
| Docker / systemd | ✓ | — | — |
| Suite tests exhaustiva | ✓ (~35) | Mínima (4) | Parcial |
| Documentación evaluación | ✓ (completa) | ✓ (datos reales) | ✓ |

---

## 11. Narrativa sugerida para la memoria (Cap. 2 / 6)

> El desarrollo del TFG siguió un proceso iterativo en dos fases. En la fase
> inicial se construyó un pipeline completo basado en YOLOv11 (E-BARD) y
> BoT-SORT, con inferencia acelerada por TensorRT, evaluación exhaustiva sobre
> benchmarks estándar (mAP@50 = 0,889 en detección; MOTA = 80,7 en tracking)
> y experimentación con múltiples backends para equipos y dorsales. Esta fase
> demostró la viabilidad técnica del análisis táctico 2D (~7 fps en GPU).
>
> Tras evaluar las limitaciones del tracking por bounding box (oclusiones,
> intercambios de identidad, recortes imprecisos para OCR) y la fragmentación
> de módulos (detector + tracker + clasificador + OCR independientes), se
> rediseñó el sistema hacia una arquitectura unificada: RF-DETR como detector
> semántico de 11 clases, SAM 3 para tracking por máscara, SigLIP para equipos
> sin etiquetas y SmolVLM2 para OCR de dorsales. El sistema final sacrifica
> velocidad (0,7 fps vs 7,3 fps) a cambio de identificación más rica (máscaras,
> dorsales al 85,26 %, clases de acción integradas) y un pipeline más coherente
> (~5.100 LoC vs ~12.500 LoC). Los modelos entrenados en la fase inicial se
> reutilizan mediante enlaces simbólicos (RF-DETR, keypoints, SAM 3).

---

## 12. Referencias cruzadas entre repos

| Concepto | baloncesto-tacticas | tfg-junio |
|----------|---------------------|-----------|
| Orquestador | `pipeline/orchestrator.py` | `pipeline/orchestrator.py` |
| Config clases | `pipeline/config.py` (4 clases) | `pipeline/config.py` (11 clases) |
| Homografía | `pipeline/court/homography.py` | `pipeline/court/homography.py` (+ PnP) |
| Fetch modelos | — | `scripts/fetch_models.py` |
| Eval OCR | `scripts/eval_dorsal_recognition.py` | `scripts/eval_jersey_ocr.py` |
| Memoria | `TRABAJO FIN DE GRADO.docx` | `docs/plan-tfg.md` + PDF |
| Plan redacción | — | `docs/plan-tfg.md` |

---

*Generado automáticamente a partir del análisis de ambos repositorios locales
(17 jun 2026). Para métricas actualizadas, ejecutar los scripts de evaluación
indicados en cada sección.*
