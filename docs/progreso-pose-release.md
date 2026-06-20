# Progreso — Detección de suelta por pose (release → 3D + trigger)

Objetivo: detector ligero de **suelta** del tiro por pose (YOLOv8-pose sobre el
recorte del poseedor) para (a) sembrar la reconstrucción 3D con el frame de
release real y (b) reforzar el trigger del `ShotTracker`. Implementación
**opt-in** y crop-only para no penalizar el rendimiento.

Contexto y justificación: ver el veredicto en el análisis de eficiencia
(el `ShotTracker` no es cuello de botella; SwishAI no usa pose y es menos
completo que el actual). El valor real de la pose es la **suelta**, no el
make/miss.

## Estado

### ✅ Fase 1 — Estimador de pose
- `pipeline/pose/pose_estimator.py`: `PoseEstimator` (wrapper perezoso de
  `ultralytics` YOLOv8-pose). `wrists(frame, bbox) -> WristEstimate` infiere
  **solo sobre el recorte del poseedor** y devuelve muñecas (COCO 9/10) en coords
  de frame completo. No carga el modelo si `enabled=False`.
- `PoseSettings` en `pipeline/config.py` (opt-in, `yolov8n-pose.pt` auto-descarga,
  device, `min_kpt_conf`, `crop_margin_px`, `infer_every`).
- **Validado** sobre un frame real del clip q2-08.43: ambas muñecas con conf
  0.94/0.95 en coords de frame.

### ✅ Fase 2 — Detector de suelta
- `pipeline/scoring/release_detector.py`: `ReleaseDetector` (estado puro, sin
  modelo). Dispara `ReleaseEvent` cuando el balón se separa de la muñeca
  (`separation_px`) de forma monótona durante `confirm_frames` **y** sube
  (`min_upward_px`), habiendo estado "en la mano" (`held_px`) hace poco. Cooldown
  para no redisparar.
- `ReleaseSettings` en `pipeline/config.py` (opt-in).
- Tests: `tests/test_release_detector.py` (7) — suelta válida, bote (no), nunca
  poseído (no), cooldown, balón/muñeca ausentes, settings cableados. **Verde.**

### ✅ Fase 3 — Integración en el orchestrator
- `PoseEstimator` + `ReleaseDetector` instanciados en `Pipeline.__init__` (gated
  por `pose.enabled`) y reseteados en `process_video`.
- Helper `Pipeline._detect_release(ctx)`: muñecas del **poseedor real**
  (`ctx.possessor_track_id`) + centro del balón → `ReleaseDetector`; rellena
  `ctx.release_event`.
- `ShotTracker.update(..., release_now=bool)`: la suelta abre la ventana en
  `idle→pending` (trigger "release"), junto a `ball_at_rim`/`action`.
- `release_event` añadido a `FrameContext`. Todo opt-in; con pose off el
  comportamiento es idéntico al anterior.

### ✅ Fase 4 — Conexión con la 3D
- `scripts/reconstruct_shot_3d.py --pose-release`: corre pose sobre el jugador más
  cercano al balón (poseedor aproximado) y, si detecta suelta dentro del arco y el
  ajuste 3D resultante es **físico** (`_window_is_physical`), usa ese frame como
  inicio de ventana. Si no, mantiene la extensión heurística (fallback).

### ✅ Fase 5 — Validación
| Clip | Release POSE | Release heurística | Decisión | Suelta Z |
|------|--------------|--------------------|----------|----------|
| q2-08.43 | frame **152** | 147 | usa POSE (físico) | 1.9 m (realista) |
| q2-10.36 | frame 41 | 46 | descarta POSE (Z<suelo) → heurística | 1.5 m |

- En 08.43 la pose acierta la suelta (Δ5 frames vs heurística) y da una altura de
  release **más realista** (1.9 m vs 3.1 m de la heurística, que se sobre-extendía).
- En 10.36 la pose se adelanta de más (frame 41 → Z negativa); el guardarraíl
  físico lo rechaza y conserva la heurística. Comportamiento robusto.
- **Coste pose: ~8.9 ms/frame (crop del poseedor) = 0.52 %** del wall-time del
  pipeline (~1700 ms/frame). Despreciable.

### ✅ Fase 6 — Integración con metadata del pipeline (jun 2026)
- `pipeline/io/pipeline_metadata.py`: lee `{out}_metadata.json` (balón, aros,
  jugadores por frame).
- `scripts/reconstruct_shot_3d.py --metadata [auto|PATH]`: omite RF-DETR para
  balón/aro; reutiliza las mismas detecciones que la web y el `ShotTracker`.
- Documentación: `docs/resultados-trayectoria-3d.md` §6.

## Notas
- Entorno: `ultralytics 8.4.50` instalado; `ROBOFLOW_API_KEY` en `.env` (no
  necesaria para pose COCO; reservada para un eventual dataset/detector propio).
- Riesgo conocido: en plano abierto los jugadores son pequeños → muñecas
  ruidosas; mitigado con recorte + confianza de keypoint y carácter opt-in con
  fallback heurístico.
