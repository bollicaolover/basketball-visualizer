#!/usr/bin/env python3
"""Genera las gráficas de datos reales del capítulo 6 de la memoria.

Salida en docs/:
  - fig6_10_train_jersey_loss.png  (Figura 6.10, curva de entrenamiento SmolVLM2/LoRA)
  - fig6_14_pipeline_latency.png   (Figura 6.14, latencia por etapa del pipeline)

Fuentes de datos REALES (no inventadas):
  - train_jersey.log                -> curva de loss por paso y media por época
  - docs/datos-reales-tfg.md §5     -> desglose de latencia medido el 16-jun-2026
"""
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
LOG = ROOT / "train_jersey.log"

# Paleta coherente con los CFD del proyecto
AZUL = "#2563eb"
VERDE = "#16a34a"
NARANJA = "#ea580c"
GRIS = "#64748b"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.6,
    "figure.dpi": 150,
})


def fig_training_curve():
    """Figura 6.10 — loss de entrenamiento del OCR de dorsales SmolVLM2/LoRA."""
    step_re = re.compile(r"epoch (\d+) step (\d+) loss ([\d.]+)")
    mean_re = re.compile(r"\[EPOCH (\d+)\] loss medio ([\d.]+)")

    steps, losses, epoch_of_step = [], [], []
    epoch_means = {}
    # contamos pasos acumulados para tener un eje X monótono
    steps_per_epoch = {}
    text = LOG.read_text(errors="ignore")
    for line in text.splitlines():
        m = step_re.search(line)
        if m:
            ep, st, ls = int(m.group(1)), int(m.group(2)), float(m.group(3))
            steps_per_epoch.setdefault(ep, []).append(st)
        mm = mean_re.search(line)
        if mm:
            epoch_means[int(mm.group(1))] = float(mm.group(2))

    # eje X global = paso acumulado
    max_step = {ep: max(s) for ep, s in steps_per_epoch.items()}
    offset = 0
    offsets = {}
    for ep in sorted(steps_per_epoch):
        offsets[ep] = offset
        offset += max_step[ep] + 20  # +20 = granularidad del logging

    global_x, global_y = [], []
    for line in text.splitlines():
        m = step_re.search(line)
        if m:
            ep, st, ls = int(m.group(1)), int(m.group(2)), float(m.group(3))
            global_x.append(offsets[ep] + st)
            global_y.append(ls)

    fig, ax = plt.subplots(figsize=(8.5, 4.6))

    # loss por paso (cruda, semitransparente)
    ax.plot(global_x, global_y, color=AZUL, lw=0.9, alpha=0.45,
            label="Loss por paso (cada 20 pasos)")

    # media por época, como marcadores en el centro de cada época
    mean_x, mean_y = [], []
    for ep in sorted(epoch_means):
        cx = offsets[ep] + max_step[ep] / 2
        mean_x.append(cx)
        mean_y.append(epoch_means[ep])
    ax.plot(mean_x, mean_y, "o-", color=NARANJA, lw=2.0, ms=8,
            label="Loss media por época")
    for cx, cy, ep in zip(mean_x, mean_y, sorted(epoch_means)):
        ax.annotate(f"{cy:.4f}", (cx, cy), textcoords="offset points",
                    xytext=(0, 12), ha="center", fontsize=9, color=NARANJA)

    # líneas verticales separando épocas
    for ep in sorted(steps_per_epoch):
        if ep > 0:
            ax.axvline(offsets[ep] - 10, color=GRIS, ls=":", lw=0.8, alpha=0.6)
    # etiquetas de época (en la base, para no chocar con la leyenda)
    for ep in sorted(steps_per_epoch):
        cx = offsets[ep] + max_step[ep] / 2
        ax.text(cx, -0.45, f"época {ep}", ha="center", fontsize=9, color=GRIS)

    ax.set_ylim(-0.6, 5.6)
    ax.set_xlabel("Paso de entrenamiento acumulado")
    ax.set_ylabel("Loss (entropía cruzada)")
    ax.set_title("Entrenamiento del OCR de dorsales — SmolVLM2 + LoRA "
                 "(0,81 % de parámetros, 2.547 pares, 5 épocas)",
                 fontsize=11, pad=14)
    ax.legend(loc="upper right", framealpha=0.9)

    fig.tight_layout()
    out = DOCS / "fig6_10_train_jersey_loss.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print("escrito", out)


def fig_pipeline_latency():
    """Figura 6.14 — latencia media por etapa del pipeline (datos §5 medidos)."""
    # Datos reales: docs/datos-reales-tfg.md §5 (clip de 109 frames, 1x A100)
    etapas = [
        ("OCR dorsal\n(SmolVLM2)", 550.5, 39.3),
        ("Tracking\n(SAM 3)", 424.4, 30.3),
        ("Calibración equipos\n(una vez)", 175.0, 12.5),
        ("Equipos\n(SigLIP)", 101.5, 7.2),
        ("Detección\n(RF-DETR)", 91.5, 6.5),
        ("Cancha\n(keypoints+homog.)", 31.3, 2.2),
    ]
    labels = [e[0] for e in etapas]
    ms = [e[1] for e in etapas]
    pct = [e[2] for e in etapas]

    # cuellos de botella en naranja, resto en azul
    colors = [NARANJA if v >= 400 else AZUL for v in ms]

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    bars = ax.bar(labels, ms, color=colors, width=0.66, edgecolor="white")

    for b, v, p in zip(bars, ms, pct):
        ax.text(b.get_x() + b.get_width() / 2, v + 8,
                f"{v:.1f} ms\n({p:.1f} %)", ha="center", va="bottom",
                fontsize=9)

    ax.set_ylabel("Latencia media (ms/frame)")
    ax.set_ylim(0, 640)
    ax.set_title("Latencia por etapa del pipeline — clip de 109 frames, 1× A100-40GB\n"
                 "Total 1.402 ms/frame (≈0,7 fps): procesado por lotes, no tiempo real",
                 fontsize=11, pad=14)
    ax.yaxis.set_major_locator(MultipleLocator(100))
    ax.tick_params(axis="x", labelsize=9)

    # leyenda manual
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color=NARANJA, label="Cuello de botella (≥400 ms)"),
        Patch(color=AZUL, label="Resto de etapas"),
    ], loc="upper right", framealpha=0.9)

    fig.tight_layout()
    out = DOCS / "fig6_14_pipeline_latency.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print("escrito", out)


if __name__ == "__main__":
    fig_training_curve()
    fig_pipeline_latency()
