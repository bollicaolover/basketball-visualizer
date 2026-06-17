"""Figura de la trayectoria 3D reconstruida de un tiro (para la memoria del TFG).

Lee el JSON que produce ``scripts/reconstruct_shot_3d.py`` y genera una figura de
tres paneles (PNG + PDF), sin necesidad de re-ejecutar el detector:

  A) Altura del balón frente al tiempo: parábola balística + puntos reconstruidos,
     con la cota del aro (10 ft) y el ápice anotado.
  B) Vista 3D de la trayectoria sobre el plano de la cancha, con los aros.
  C) Vista cenital (planta): recorrido X–Y sobre el contorno de la cancha NBA.

Uso:
    python scripts/plot_shot_3d.py --json docs/results/shot3d.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.court.ball_3d import RIM_HEIGHT_M  # noqa: E402
from pipeline.court.geometry import (  # noqa: E402
    NBA_BASELINE_TO_RIM_CENTER_CM,
    NBA_COURT_LENGTH_CM,
    NBA_COURT_WIDTH_CM,
)

# Dimensiones de cancha en metros (cm / 100).
GRAVITY_M_S2 = 9.81
COURT_L = NBA_COURT_LENGTH_CM / 100.0             # 28.65 m
COURT_W = NBA_COURT_WIDTH_CM / 100.0              # 15.24 m
RIM_OFF = NBA_BASELINE_TO_RIM_CENTER_CM / 100.0
RIMS = [(RIM_OFF, COURT_W / 2.0), (COURT_L - RIM_OFF, COURT_W / 2.0)]

ACCENT = "#e8590c"   # naranja balón
TRAJ = "#1c7ed6"     # azul trayectoria
COURT = "#adb5bd"


def _nearest_rim(x: float, y: float) -> tuple[float, float]:
    return min(RIMS, key=lambda r: (r[0] - x) ** 2 + (r[1] - y) ** 2)


def main() -> None:
    ap = argparse.ArgumentParser(description="Figura de la trayectoria 3D del tiro")
    ap.add_argument("--json", type=Path, default=ROOT / "docs/results/shot3d.json")
    ap.add_argument("--out", type=Path, default=None, help="ruta base de salida (sin extensión)")
    args = ap.parse_args()

    d = json.loads(args.json.read_text())
    fps = float(d["fps"])
    frames = np.array(d["frames"], dtype=float)
    pts = np.array(d["points_3d_m"], dtype=float)
    X0, Vx, Y0, Vy, Z0, Vz = d["params_X0_Vx_Y0_Vy_Z0_Vz_m"]
    t = (frames - frames[0]) / fps
    apex_t = Vz / GRAVITY_M_S2
    apex_z = Z0 + Vz * Vz / (2 * GRAVITY_M_S2)

    # Región de interés en pista (zoom): la trayectoria + el aro más cercano.
    rim = _nearest_rim(float(np.mean(pts[:, 0])), float(np.mean(pts[:, 1])))
    xs = np.concatenate([pts[:, 0], [rim[0], X0]])
    ys = np.concatenate([pts[:, 1], [rim[1], Y0]])
    pad = 2.5  # metros
    xlo, xhi = xs.min() - pad, xs.max() + pad
    ylo, yhi = ys.min() - pad, ys.max() + pad

    plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.3})
    fig = plt.figure(figsize=(15.5, 5.0))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 1.0, 1.0], wspace=0.28)

    # --- Panel A: altura vs tiempo (resultado principal) ---
    axA = fig.add_subplot(gs[0, 0])
    tt = np.linspace(t.min(), max(t.max(), apex_t), 200)
    zz = Z0 + Vz * tt - 0.5 * GRAVITY_M_S2 * tt**2
    axA.plot(tt, zz, color=TRAJ, lw=2, label="parábola balística")
    axA.scatter(t, pts[:, 2], color=ACCENT, s=22, zorder=5, label="puntos reconstruidos")
    axA.axhline(RIM_HEIGHT_M, ls="--", color=COURT, lw=1.2)
    axA.text(t.min(), RIM_HEIGHT_M + 0.07, "aro (3.05 m)", color="#666", fontsize=8)
    axA.scatter([apex_t], [apex_z], marker="*", s=160, color="#f08c00", zorder=6,
                edgecolor="white", linewidth=0.6)
    axA.annotate(f"ápice {apex_z:.2f} m", (apex_t, apex_z),
                 textcoords="offset points", xytext=(6, -14), fontsize=8)
    axA.set_xlabel("tiempo (s)")
    axA.set_ylabel("altura sobre la cancha (m)")
    axA.set_title("A · Altura del balón vs tiempo")
    axA.legend(fontsize=8, loc="lower center")

    # --- Panel B: vista 3D (zoom a la zona del tiro) ---
    axB = fig.add_subplot(gs[0, 1], projection="3d")
    floor = [[(xlo, ylo, 0), (xhi, ylo, 0), (xhi, yhi, 0), (xlo, yhi, 0)]]
    axB.add_collection3d(Poly3DCollection(floor, facecolor=COURT, alpha=0.15, edgecolor=COURT))
    axB.plot(pts[:, 0], pts[:, 1], pts[:, 2], color=TRAJ, lw=2)
    axB.scatter(pts[:, 0], pts[:, 1], pts[:, 2], color=ACCENT, s=16)
    rx, ry = rim
    axB.plot([rx, rx], [ry, ry], [0, RIM_HEIGHT_M], color="#868e96", lw=1.4)
    axB.scatter([rx], [ry], [RIM_HEIGHT_M], color="#495057", s=30, marker="o")
    axB.text(rx, ry, RIM_HEIGHT_M + 0.3, "aro", fontsize=8, color="#495057")
    axB.set_xlabel("X (m)")
    axB.set_ylabel("Y (m)")
    axB.set_zlabel("Z (m)")
    axB.set_title("B · Trayectoria 3D (zoom)")
    axB.set_xlim(xlo, xhi)
    axB.set_ylim(ylo, yhi)
    zmax = max(5.0, pts[:, 2].max() + 0.5)
    axB.set_zlim(0, zmax)
    axB.set_box_aspect((xhi - xlo, yhi - ylo, zmax))
    axB.view_init(elev=20, azim=-70)

    # --- Panel C: planta cenital (zoom) ---
    axC = fig.add_subplot(gs[0, 2])
    axC.add_patch(plt.Rectangle((0, 0), COURT_L, COURT_W, fill=False, edgecolor=COURT, lw=1.4))
    axC.scatter([rim[0]], [rim[1]], color="#495057", s=40, marker="o", zorder=4, label="aro")
    sc = axC.scatter(pts[:, 0], pts[:, 1], c=pts[:, 2], cmap="viridis", s=30, zorder=5)
    axC.plot(pts[:, 0], pts[:, 1], color=TRAJ, lw=1, alpha=0.6, zorder=3)
    axC.scatter([X0], [Y0], marker="s", s=55, color=ACCENT, zorder=6,
                edgecolor="white", linewidth=0.6, label="suelta")
    cb = fig.colorbar(sc, ax=axC, fraction=0.046, pad=0.04)
    cb.set_label("altura Z (m)", fontsize=8)
    axC.set_xlabel("X (m)")
    axC.set_ylabel("Y (m)")
    axC.set_title("C · Vista cenital (zoom)")
    axC.set_aspect("equal")
    axC.set_xlim(xlo, xhi)
    axC.set_ylim(ylo, yhi)
    axC.legend(fontsize=8, loc="best")

    rmse = d["reproj_rmse_px"]
    fig.suptitle(
        f"Reconstrucción 3D del tiro — {d['clip']}  ·  "
        f"{len(pts)} frames, RMSE reproyección = {rmse:.1f} px",
        fontsize=11,
    )
    fig.subplots_adjust(left=0.05, right=0.97, top=0.88, bottom=0.12)

    base = args.out or args.json.with_suffix("")
    png, pdf = Path(f"{base}.png"), Path(f"{base}.pdf")
    fig.savefig(png, dpi=160)
    fig.savefig(pdf)
    print(f"[INFO] Figura guardada: {png}")
    print(f"[INFO] Figura guardada: {pdf}")


if __name__ == "__main__":
    main()
