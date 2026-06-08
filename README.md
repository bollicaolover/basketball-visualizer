# tfg-junio — análisis táctico de baloncesto

Pipeline modular que combina el flujo de detección/identidad del cuaderno de
Roboflow con la proyección al plano 2D y el tracking de balón del proyecto
original, **usando modelos propios entrenados localmente** (sin inferencia
alojada de Roboflow).

## Flujo

```
RF-DETR (11 clases, local)
   → SAM 3 (tracking por máscara, prompt-once con RF-DETR)
   → TeamClassifier SigLIP (equipos, sin etiquetas)
   → SmolVLM2 local (OCR de dorsal) + roster (nombre)
   → keypoints de cancha + homografía (proyección 2D)
   → BallTracker
   → mapa cenital + vídeo anotado
```

## Instalación

Reutiliza el entorno conda del proyecto original:

```bash
conda activate tfg-baloncesto
```

## Puesta en marcha

```bash
# 1. Enlaza los modelos ya entrenados (RF-DETR, SAM3, keypoints de cancha)
python scripts/fetch_models.py

# 2. Ejecuta el pipeline (sin números hasta entrenar el OCR)
python run.py data/clip.mp4 -o data/out.mp4 --no-numbers
#   produce data/out.mp4 (anotado) y data/out_map.mp4 (mapa 2D)
```

## OCR de dorsal (entrenar el SmolVLM2 propio)

```bash
# Descarga el dataset de Roboflow (solo usa la API key para descargar)
python scripts/download_jersey_dataset.py --workspace <tu_workspace>

# Fine-tune del VLM -> models/jersey-ocr/
python scripts/train_jersey_ocr.py --data data/jersey-numbers --epochs 5

# Con el modelo entrenado, los números salen automáticamente:
python run.py data/clip.mp4 -o data/out.mp4
```

## Roster (nombres de jugador + colores de equipo)

Opcional. Un JSON indexado por **nombre de equipo**, con el color de la
camiseta y el mapeo `dorsal → nombre`:

```json
{
  "Boston Celtics":  { "colors": "#FFFFFF", "players": { "0": "Tatum", "7": "Brown" } },
  "New York Knicks": { "colors": "#1D428A", "players": { "11": "Brunson", "23": "Robinson" } }
}
```

- `colors` debe ser el color de la **camiseta que se juega ese partido** (no el
  de marca): se usa para emparejar cada equipo con el cluster detectado y asignar
  los nombres al equipo claro/oscuro de forma automática (no posicional).
- `players` resuelve el nombre cruzando equipo + dorsal (del OCR).

Por CLI:

```bash
python run.py data/clip.mp4 -o data/out.mp4 --roster data/roster.json
```

En la app web el roster se sube en el panel lateral (opcional): los nombres de
jugador y equipo y los colores se aplican automáticamente al resultado. La capa
interactiva del frontend reorienta además por coincidencia de dorsales, de modo
que el equipo claro/oscuro queda correcto aunque el color del roster no encaje.

## Estructura

- `pipeline/detection/` — RF-DETR local (11 clases).
- `pipeline/tracking/`  — SAM 3 (prompt-once), balón, punto de apoyo por máscara.
- `pipeline/teams/`     — clasificador de equipos SigLIP (sin etiquetas).
- `pipeline/identity/`  — OCR de dorsal (SmolVLM2 local) + roster.
- `pipeline/court/`     — keypoints, homografía, render del mapa 2D (portado).
- `pipeline/orchestrator.py` — bucle por frame que une todas las etapas.
- `scripts/`            — fetch de modelos, descarga de datasets y entrenamientos.
- `frontend/` + `backend/` — aplicación web (SPA Vue 3 + API FastAPI).

> **Para modificar la app**, consulta [`docs/arquitectura.md`](docs/arquitectura.md):
> estructura completa de frontend, backend y pipeline, convenciones del código y
> una tabla "quiero cambiar X, ¿dónde toco?".

## Modelos

`scripts/fetch_models.py` enlaza desde `tfg-baloncesto-tacticas`:
RF-DETR 11 clases, SAM 3, keypoints de cancha, y (puente opcional) PARSeq +
legibilidad. El SmolVLM2 de dorsal se entrena con `scripts/train_jersey_ocr.py`.
