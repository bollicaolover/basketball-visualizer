<div align="center">

# 🏀 basketball-visualizer — Análisis táctico de baloncesto

**Pipeline de visión por computador que detecta, sigue e identifica a los jugadores en vídeo de baloncesto y proyecta la jugada a una vista cenital 2D — con modelos entrenados localmente.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![Vue 3](https://img.shields.io/badge/Vue-3-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-académico-lightgrey)](#licencia)

</div>

---

## 📖 Tabla de contenidos

- [Descripción](#descripción)
- [Características](#características)
- [Arquitectura](#arquitectura)
- [Stack tecnológico](#stack-tecnológico)
- [Instalación](#instalación)
- [Uso rápido (CLI)](#uso-rápido-cli)
- [Aplicación web](#aplicación-web)
- [Roster (nombres y colores de equipo)](#roster-nombres-y-colores-de-equipo)
- [Entrenamiento de modelos](#entrenamiento-de-modelos)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Documentación](#documentación)
- [Licencia](#licencia)

---

## Descripción

`basketball-visualizer` toma un clip de baloncesto y produce **dos vídeos**: el original anotado (cajas, equipos, dorsales y nombres) y un **mapa cenital 2D** con las posiciones de los jugadores y el balón proyectadas sobre el plano de la cancha.

Combina el flujo de detección/identidad del cuaderno de Roboflow con la proyección 2D y el tracking de balón del proyecto original, pero **usando modelos propios entrenados localmente** (sin inferencia alojada de Roboflow).

El proyecto se distribuye de dos formas:

- 🖥️ **CLI** (`run.py`) — para procesar clips directamente desde la terminal.
- 🌐 **Aplicación web** — SPA en Vue 3 + API FastAPI para subir vídeos, seguir el progreso y visualizar resultados en el navegador.

## Características

- 🎯 **Detección local** con RF-DETR (11 clases, incluyendo `player-in-possession`).
- 🧩 **Tracking por máscara** con SAM 3 (prompt-once inicializado por RF-DETR).
- 👕 **Clasificación de equipos sin etiquetas** vía embeddings SigLIP + UMAP + K-means.
- 🔢 **OCR de dorsal** con un SmolVLM2 fine-tuneado localmente.
- 🏷️ **Resolución de nombre** cruzando equipo + dorsal contra un roster JSON opcional.
- 📐 **Homografía de cancha** a partir de keypoints para la proyección al plano 2D.
- 🏀 **Tracking de balón** y **resolución de posesión** con histéresis temporal.
- 🗺️ Salida dual: **vídeo anotado** + **minimapa cenital**.

## Arquitectura

```
RF-DETR (11 clases, local)
   └─► SAM 3 ............... tracking por máscara (prompt-once con RF-DETR)
   └─► TeamClassifier ...... equipos sin etiquetas (SigLIP + UMAP + K-means)
   └─► SmolVLM2 (local) .... OCR de dorsal  ──┐
                                              ├─► roster → nombre del jugador
   └─► Keypoints de cancha . homografía ──────┘
   └─► BallTracker ........ tracking de balón + posesión
        │
        ▼
   mapa cenital 2D  +  vídeo anotado
```

La aplicación web tiene tres piezas independientes:

```
┌───────────────┐   HTTP /api/*   ┌────────────────────┐   subprocess    ┌──────────────┐
│   Frontend    │ ──────────────► │  Backend (FastAPI) │ ──────────────► │  Pipeline ML │
│  Vue 3 + Vite │ ◄────────────── │  backend/app/      │  python -m      │  pipeline/   │
│  (SPA)        │   JSON / vídeo  │  main.py           │  pipeline.run   │              │
└───────────────┘                 └────────────────────┘                 └──────────────┘
```

> Detalle completo en [`docs/arquitectura.md`](docs/arquitectura.md).

## Stack tecnológico

| Capa        | Tecnologías                                                        |
|-------------|--------------------------------------------------------------------|
| Visión / ML | PyTorch · RF-DETR · SAM 3 · SigLIP · SmolVLM2 · Ultralytics · `supervision` |
| Backend     | FastAPI · Uvicorn                                                  |
| Frontend    | Vue 3 (`<script setup>`) · Vite 5 (Node 20)                        |
| Datos       | Roboflow (descarga de datasets) · UMAP · scikit-learn             |

## Instalación

El proyecto reutiliza el entorno conda del proyecto original, que ya tiene todas las dependencias instaladas:

```bash
conda activate tfg-baloncesto
```

Las dependencias están documentadas en [`requirements.txt`](requirements.txt). Después, enlaza los modelos ya entrenados (RF-DETR, SAM 3, keypoints de cancha):

```bash
python scripts/fetch_models.py
```

> El frontend usa un **Node 20 local** (`frontend/.node/`); el Node del sistema es demasiado antiguo para Vite 5.

## Uso rápido (CLI)

```bash
# Procesar un clip (sin dorsales hasta entrenar el OCR)
python run.py data/clip.mp4 -o data/out.mp4 --no-numbers
#   → data/out.mp4       (vídeo anotado)
#   → data/out_map.mp4   (mapa cenital 2D)

# Con el OCR de dorsal entrenado, los números salen automáticamente
python run.py data/clip.mp4 -o data/out.mp4

# Con roster (nombres de jugador + colores de equipo)
python run.py data/clip.mp4 -o data/out.mp4 \
    --roster data/roster.json --team-names "Lakers,Warriors"
```

<details>
<summary>Opciones disponibles</summary>

| Flag                  | Descripción                                                |
|-----------------------|------------------------------------------------------------|
| `-o, --output`        | Vídeo anotado de salida (por defecto `data/out.mp4`)       |
| `--no-overlay`        | No escribir el vídeo anotado                               |
| `--no-map`            | No escribir el mapa 2D                                     |
| `--no-numbers`        | Desactivar el OCR de dorsal                                |
| `--metadata`          | Escribir metadatos JSON por frame                          |
| `--clean-paths`       | Suavizar trayectorias (`sports.clean_paths`)               |
| `--progress-every N`  | Avisar cada N frames                                       |
| `--roster`            | JSON con rosters (dorsal → nombre)                         |
| `--team-names`        | Nombres de los dos equipos, p.ej. `'Lakers,Warriors'`      |

</details>

## Aplicación web

Compila el frontend y arranca el backend FastAPI (que sirve los estáticos compilados):

```bash
bash serve.sh                  # http://0.0.0.0:8000
bash serve.sh --port 8080      # puerto personalizado
```

Sube un vídeo desde el panel lateral, sigue el progreso del trabajo y visualiza el vídeo anotado junto al minimapa 2D. El roster se sube opcionalmente en el panel lateral: nombres de jugador, de equipo y colores se aplican automáticamente al resultado.

## Roster (nombres y colores de equipo)

Opcional. Un JSON indexado por **nombre de equipo**, con el color de la camiseta y el mapeo `dorsal → nombre`:

```json
{
  "Boston Celtics":  { "colors": "#FFFFFF", "players": { "0": "Tatum",   "7": "Brown"    } },
  "New York Knicks": { "colors": "#1D428A", "players": { "11": "Brunson", "23": "Robinson" } }
}
```

- `colors` — color de la **camiseta que se juega ese partido** (no el de marca). Se usa para emparejar cada equipo con el cluster detectado y asignar nombres al equipo claro/oscuro de forma automática (no posicional).
- `players` — resuelve el nombre cruzando equipo + dorsal (del OCR).

En la app web, la capa interactiva del frontend reorienta además por coincidencia de dorsales, de modo que el equipo claro/oscuro queda correcto aunque el color del roster no encaje.

## Entrenamiento de modelos

Solo el **OCR de dorsal** se entrena en este proyecto; el resto de modelos se enlazan con `scripts/fetch_models.py`.

```bash
# 1. Descargar el dataset de Roboflow (la API key solo se usa para descargar)
python scripts/download_jersey_dataset.py --workspace <tu_workspace>

# 2. Fine-tune del VLM → models/jersey-ocr/
python scripts/train_jersey_ocr.py --data data/jersey-numbers --epochs 5
```

Otros scripts de entrenamiento disponibles: `train_rfdetr.py`, `train_court_keypoints.py`.

## Estructura del proyecto

```
basketball-visualizer/
├── pipeline/                 Pipeline ML (CLI: python -m pipeline.run)
│   ├── detection/            RF-DETR local (11 clases)
│   ├── tracking/             SAM 3 (prompt-once), balón, punto de apoyo
│   ├── teams/                Clasificador de equipos SigLIP (sin etiquetas)
│   ├── identity/             OCR de dorsal (SmolVLM2 local) + roster
│   ├── court/                Keypoints, homografía, render del mapa 2D
│   ├── possession/           Resolución de posesión (histéresis temporal)
│   ├── scoring/              Tracking de tiros
│   └── orchestrator.py       Bucle por frame que une todas las etapas
├── backend/app/              API FastAPI (auth, jobs, GPU, sirve el frontend)
├── frontend/                 SPA Vue 3 + Vite (dist/ versionado)
├── scripts/                  Fetch de modelos, descarga de datasets, entrenamientos
├── docs/                     Arquitectura y metodología
├── run.py                    CLI del pipeline
├── serve.sh                  Compila el frontend y arranca el backend
└── requirements.txt          Dependencias Python (entorno conda tfg-baloncesto)
```

> `data/`, `models/`, `*.mp4`, `*.log` y `frontend/.node|node_modules` están en `.gitignore`. `frontend/dist/` **sí** se versiona (lo sirve el backend).

## Documentación

- 📐 [`docs/arquitectura.md`](docs/arquitectura.md) — estructura completa de frontend, backend y pipeline, convenciones de código y la tabla *"quiero cambiar X, ¿dónde toco?"*.
- 📋 [`docs/metodologia.md`](docs/metodologia.md) — metodología del TFG (Kanban + CRISP-DM).

## Licencia

Proyecto académico (Trabajo de Fin de Grado). Uso educativo.
