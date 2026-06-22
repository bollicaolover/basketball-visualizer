# Datos reales del proyecto (para la memoria del TFG)

> Métricas extraídas del repositorio y los logs el **16 jun 2026**; cronología y
> referencias a *commits* **actualizadas el 22 jun 2026** tras la reconstrucción
> del historial de git. Úsense para sustituir las cifras y narrativas inventadas
> de la plantilla. **Regla: no inventar.** Lo que no esté medido aquí se marca
> como *pendiente de medición*, no se rellena.

## 1. Cronología real (git) — base para planificación (cap. 5) y Gantt

**61 commits**, del **2026-01-08** al **2026-06-22**, en un **único historial lineal**
(rama `master`) que refleja el flujo **Kanban WIP=1**: una tarjeta entregable por
commit, sin solapamiento. El tablero de **GitHub Projects**
([Project #2](https://github.com/users/bollicaolover/projects/2)) recoge **65
tarjetas**: **61 `Hecho`** (una por commit, cada una enlazada al commit que la
cierra) y **4 `Por hacer`** (diferidas, ver §6.5 de
[`desarrollo-cap6.md`](desarrollo-cap6.md)).

> **Hito de entrega ordinaria:** 2026-05-18 (`0d84f78` [DOC-1], tag
> `entrega-ordinaria`). La **ampliación de alcance** posterior (posesión robusta,
> pose/reconstrucción 3D del tiro, reconocimiento de pantallas) se concentra entre
> el 18-may y el 22-jun.

**Reparto por área funcional del tablero Kanban:**

| Área | Commits | Tarjetas (tablero) | Rango de fechas |
|---|---|---|---|
| Detección & Tracking | 8 | 9 (1 diferida) | 01-13 → 06-13 |
| Geometría & Homografía | 4 | 4 | 02-11 → 06-17 |
| Identidad & Equipos | 3 | 3 | 03-26 → 04-09 |
| Analytics & Reglas | 9 | 10 (1 diferida) | 04-16 → 06-18 |
| Core & Infrastructure | 24 | 26 (2 diferidas) | 01-08 → 06-19 |
| Memoria TFG | 13 | 13 | 05-18 → 06-22 |
| **Total** | **61** | **65** | **01-08 → 06-22** |

El detalle **commit → tarjeta → área** es trazable directamente en el historial de
git (`git log`, cada mensaje lleva el código de tarjeta, p. ej. `[DET-5]`) y en el
tablero (campos *Área*, *Tamaño* y *Estado*). No se duplica aquí para mantener una
única fuente de verdad y evitar desincronización.

**Iteración revertida (evidencia honesta de proceso, área Analytics & Reglas):**
- 2026-06-04 `5f1c64e` [ANL-3] — intento de segmentar sesiones SAM para frenar la
  deriva de identidad en vídeos largos.
- 2026-06-05 `b12cbb7` [ANL-3] — **revertido: «el enfoque de segmentación SAM no
  funcionó»**.
> Probar, medir y descartar es parte legítima del método: es un bucle de
> retroalimentación característico de **Kanban** (flujo continuo), no de fases
> cerradas. La tarjeta se abrió, se evaluó y se cerró revirtiendo el cambio.

## 2. OCR de dorsal — entrenamiento real (de `train_jersey.log`)

- Modelo base: **SmolVLM2** — 511.643.840 parámetros totales; **4.161.536 entrenables (0,81 %)** → ajuste fino tipo adaptadores (PEFT/LoRA), no full fine-tuning.
- Dataset: **2.547 pares imagen-texto** de dorsal (carpeta `data/jersey-numbers` contiene 3.141 ficheros en total, imágenes + etiquetas).
- **5 épocas**. Loss media por época:

| Época | Loss media |
|---|---|
| 0 | 0,4502 |
| 1 | 0,0267 |
| 2 | 0,0171 |
| 3 | 0,0125 |
| 4 | 0,0101 |

### Exactitud medida (evaluación real, 16 jun 2026)

Evaluación sobre el split **test** (`scripts/eval_jersey_ocr.py`, réplica fiel de
la inferencia de `pipeline/identity/number_ocr.py`):

| Métrica | Valor |
|---|---|
| Muestras de test (dorsal numérico) | 312 |
| Aciertos (coincidencia exacta) | 266 |
| **Exactitud** | **85,26 %** |
| Predicciones vacías | 0 |
| Latencia media | 284 ms/imagen (A100) |
| Throughput | 3,5 img/s |

> El "96,8 %" de la plantilla era **inventado**: sustituir por **85,26 %**.
> Patrón de errores típico: confusión 1↔2 dígitos y crops ocluidos
> (p. ej. 40→10, 13→15, 34→24, "00"→"0"). 5 muestras del jsonl con `suffix`
> vacío (prefijo UUID) se excluyen por estar mal exportadas.

## 3. Líneas de código (para estimación de tamaño, cap. 5)

| Componente | LoC |
|---|---|
| `pipeline/` (Python) | 5.112 |
| └ court/ | 1.918 |
| └ tracking/ | 666 |
| └ scoring/ | 408 |
| └ identity/ | 246 |
| └ possession/ | 185 |
| └ io/ | 172 |
| └ teams/ | 164 |
| └ detection/ | 69 |
| `backend/` (Python) | 1.037 |
| `scripts/` (Python) | 444 |
| `run.py` | 61 |
| `frontend/src/` (Vue/JS/CSS) | 4.513 |
| **Total versionado (sin dist/node_modules)** | **~11.365** |

## 4. Detector RF-DETR — 11 clases reales (`pipeline/config.py`)

`basketball`(0), `ball`(1), `ball-in-basket`(2), `number`(3), `player`(4),
`player-in-possession`(5), `player-jump-shot`(6), `player-layup-dunk`(7),
`player-shot-block`(8), `referee`(9), `rim`(10).

> Las clases 6–8 son **acciones detectadas por el propio detector** (no por
> pose). El **shot tracker** (commit `542b11e` [ANL-2]) detecta lanzamientos a
> partir de estas clases + `ball-in-basket`. Por eso O5 (posesión + tiros) es real:
> no usa ViTPose/ST-GCN. El "reconocimiento de acciones por pose" de la
> plantilla nunca se implementó.

## 5. Rendimiento del pipeline — medido (16 jun 2026)

Ejecución real de `run.py` con profiling (`settings.profile=True`) sobre el clip
`boston-celtics-new-york-knicks-game-1-q2-10.36-10.32.mp4` (**109 frames, 3,6 s,
30 fps**) en **1× NVIDIA A100-40GB**. Tiempos GPU aproximados (`cuda_sync=False`).

- **Total de procesamiento:** 152,8 s → **1.402 ms/frame ≈ 0,7 fps**.
- **Tiempo de pared** (incluida carga de los 4 modelos): **3 min 7 s**.
- Confirma que el sistema es de **procesado por lotes, no tiempo real** (refuerza
  la eliminación de "tiempo real" del título/objetivos).

**Desglose por etapa (% del cómputo):**

| Etapa | ms/frame | % |
|---|---|---|
| Dorsal (OCR SmolVLM2) | 550,5 | 39,3 |
| Tracking (SAM 3) | 424,4 | 30,3 |
| Calibración de equipos (una vez) | 175,0 | 12,5 |
| Equipos (SigLIP) | 101,5 | 7,2 |
| Detección (RF-DETR) | 91,5 | 6,5 |
| Cancha (keypoints + homografía) | 31,3 | 2,2 |
| Escritura / render / proyección / decod. / posesión | <10 c/u | <2 |

> Lecturas para el cap. 7: el **OCR (39 %)** y el **tracking SAM 3 (30 %)** son
> los cuellos de botella; RF-DETR detecta rápido (91 ms/frame). Vía de mejora
> evidente: cuantización/optimización del VLM y de SAM 3.

**Salidas tácticas reales del mismo clip (validación funcional):**
- Dorsales fijados: 10 tracks con número (p. ej. #7, #11, #23, #32…).
- Posesión: Equipo 1 85,4 % / Equipo 0 14,6 % (89 frames con poseedor).
- Tiros: 1/1 acierto detectado (aro derecho).

### Consumo de VRAM y escalado multi-GPU (medido, 16 jun 2026)

Medición real con `scripts/measure_performance.py` sobre el mismo clip (109
frames) en A100-40GB. Resultados en [`perf-results.json`](perf-results.json).

| Configuración | Tiempo de pared | VRAM pico | Speedup |
|---|---|---|---|
| **1× A100** | 187,0 s | **7.941 MiB (≈7,8 GB)** | 1,0× (base) |
| **2× A100** (chunking) | 126,7 s | 5.839 / 6.015 MiB por GPU | **1,48×** |

- **VRAM pico ≈ 7,8 GB** en 1 GPU → el pipeline (4 modelos: RF-DETR + SAM 3 +
  SigLIP + SmolVLM2) **cabe holgadamente en una GPU de 8–12 GB**, no requiere la
  A100 completa. Refuerza la narrativa de *hardware accesible* (cap. 1/2).
- **Speedup 1,48× con 2 GPUs** (eficiencia 0,74), **sublineal**: cada trozo paga
  el coste fijo de cargar los 4 modelos (~65 s), que no se reparte. Por Amdahl,
  el speedup tiende a 2× cuanto **más largo** es el clip (el coste por-frame
  domina sobre la carga fija). Con 109 frames el coste de carga pesa demasiado.
  Vía de mejora: reutilizar workers/modelos entre trozos en lugar de relanzar el
  subproceso por chunk.

> Reproducible con: `python scripts/measure_performance.py --clip <clip> --gpus 0,1`.

## 6. Componentes NO implementados (mantener fuera del cuerpo, solo en Vías futuras)

- **Motor experto / reglas tácticas**: `backend/app/core/expert/{engine,rules}.py` → **0 líneas** (el andamiaje del backend, commit `2a09f75` [CORE-7], creó estos ficheros vacíos como vías futuras).
- **Clasificador GNN de jugadas**: `backend/app/core/classifier/{model,graph_builder,inference}.py` → **0 líneas**.
- **Reconocimiento de acciones por pose** (ViTPose/ST-GCN/PoseConv3D): no existe.
- Todo `backend/app/core/` = 0 líneas (andamiaje). La lógica real del backend está en `backend/app/main.py` + `chunking.py`.

> ⚠️ No afirmar en la memoria que el GNN o el motor experto están implementados.
> El andamiaje (`2a09f75` [CORE-7]) crea esos ficheros, pero están vacíos.
