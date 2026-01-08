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

## Estructura

- `pipeline/detection/` — RF-DETR local (11 clases).
- `pipeline/tracking/`  — SAM 3 (prompt-once), balón, punto de apoyo por máscara.
- `pipeline/teams/`     — clasificador de equipos SigLIP (sin etiquetas).
- `pipeline/identity/`  — OCR de dorsal (SmolVLM2 local) + roster.
- `pipeline/court/`     — keypoints, homografía, render del mapa 2D (portado).
- `pipeline/orchestrator.py` — bucle por frame que une todas las etapas.
- `scripts/`            — fetch de modelos, descarga de datasets y entrenamientos.

## Modelos

`scripts/fetch_models.py` enlaza desde `tfg-baloncesto-tacticas`:
RF-DETR 11 clases, SAM 3, keypoints de cancha, y (puente opcional) PARSeq +
legibilidad. El SmolVLM2 de dorsal se entrena con `scripts/train_jersey_ocr.py`.
