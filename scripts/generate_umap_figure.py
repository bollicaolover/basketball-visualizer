#!/usr/bin/env python3
"""Figura 6.9 — Proyección UMAP de descriptores SigLIP (separación de equipos).

Pipeline REAL (no inventado):
  1. RF-DETR detecta jugadores sobre fotogramas muestreados del clip de prueba.
  2. Los recortes centrales (camiseta) se pasan por SigLIP -> embeddings.
  3. UMAP (2 componentes) proyecta los embeddings a 2D.
  4. K-means (k=2) separa los dos equipos sin etiquetas.
  5. Se colorea cada punto por su cluster y se anota el color medio de camiseta.

Salida: docs/fig6_9_umap_equipos.png

Ejecutar dentro del entorno `tfg-baloncesto`:
  conda run -n tfg-baloncesto python scripts/generate_umap_figure.py
"""
from pathlib import Path

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
import umap

from pipeline.config import DetectionSettings, PLAYER_CLASSES
from pipeline.detection.rfdetr_detector import RFDETRDetector
from sports.common.team import TeamClassifier

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CLIP = ROOT / "data/test_videos/boston-celtics-new-york-knicks-game-1-q2-10.36-10.32.mp4"

SAMPLE_EVERY = 4        # 1 de cada N fotogramas
CROP_SCALE = 0.6        # recorte central para realzar la camiseta
MIN_PX = 16
SEED = 42

AZUL = "#2563eb"
NARANJA = "#ea580c"


def collect_player_crops():
    det = RFDETRDetector(DetectionSettings(device="cuda"))
    cap = cv2.VideoCapture(str(CLIP))
    crops, frame_idx = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % SAMPLE_EVERY == 0:
            d = det.detect(frame)
            for box, cid in zip(d.xyxy, d.class_id):
                if int(cid) not in PLAYER_CLASSES:
                    continue
                x1, y1, x2, y2 = box
                # recorte central (escala CROP_SCALE) centrado en la caja
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                w, h = (x2 - x1) * CROP_SCALE, (y2 - y1) * CROP_SCALE
                a, b = int(max(cx - w / 2, 0)), int(max(cy - h / 2, 0))
                c, e = int(cx + w / 2), int(cy + h / 2)
                crop = frame[b:e, a:c]
                if crop.shape[0] >= MIN_PX and crop.shape[1] >= MIN_PX:
                    crops.append(crop)
        frame_idx += 1
    cap.release()
    print(f"[INFO] {len(crops)} recortes de jugador de {frame_idx} fotogramas")
    return crops


def mean_shirt_rgb(crop):
    # color medio del tercio superior (camiseta), BGR -> RGB normalizado
    h = crop.shape[0]
    band = crop[: max(h // 2, 1)]
    bgr = band.reshape(-1, 3).mean(axis=0)
    return np.array([bgr[2], bgr[1], bgr[0]]) / 255.0


def main():
    crops = collect_player_crops()
    if len(crops) < 10:
        raise SystemExit("Muy pocos recortes para UMAP")

    tc = TeamClassifier(device="cuda")
    feats = tc.extract_features(crops)            # SigLIP embeddings reales
    print(f"[INFO] embeddings SigLIP: {feats.shape}")

    reducer = umap.UMAP(n_components=2, random_state=SEED)
    proj = reducer.fit_transform(feats)
    labels = KMeans(n_clusters=2, random_state=SEED, n_init=10).fit_predict(proj)

    # orientar clusters por luminancia de camiseta (cluster claro vs oscuro)
    shirt = np.array([mean_shirt_rgb(c) for c in crops])
    lum = shirt.mean(axis=1)
    lum0, lum1 = lum[labels == 0].mean(), lum[labels == 1].mean()
    light = 0 if lum0 >= lum1 else 1
    color_map = {light: AZUL, 1 - light: NARANJA}
    name_map = {light: "Equipo claro", 1 - light: "Equipo oscuro"}

    fig, ax = plt.subplots(figsize=(7.6, 5.6), dpi=150)
    for k in (0, 1):
        m = labels == k
        ax.scatter(proj[m, 0], proj[m, 1], s=42, c=color_map[k],
                   edgecolors="white", linewidths=0.5, alpha=0.85,
                   label=f"{name_map[k]}  (n={int(m.sum())})")

    ax.set_xlabel("UMAP-1")
    ax.set_ylabel("UMAP-2")
    ax.set_title("Proyección UMAP de descriptores SigLIP\n"
                 f"Separación no supervisada de equipos — {len(crops)} recortes "
                 "de jugador (K-means, k=2)", fontsize=11, pad=12)
    ax.legend(loc="best", framealpha=0.9)
    ax.grid(alpha=0.2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    fig.tight_layout()
    out = DOCS / "fig6_9_umap_equipos.png"
    fig.savefig(out, bbox_inches="tight")
    print("escrito", out)


if __name__ == "__main__":
    main()
