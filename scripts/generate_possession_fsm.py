#!/usr/bin/env python3
"""Figura 6.13 — Máquina de estados del resolver de posesión.

Genera docs/possession_fsm.svg reflejando la lógica REAL de
pipeline/possession/resolver.py (no la descripción naíf "Equipo A/B/Disputado":
el resolver razona por track_id; el % por equipo se deriva después).

Estados internos (_possessor / _pending / _loose_count):
  · POSEEDOR = T (estable)     · PENDIENTE → T' (histéresis)   · SIN POSEEDOR (suelto)

Cada frame calcula un candidato c (señal primaria clase-5 por IoU, o secundaria
por proximidad) y la máquina temporal aplica histéresis (switch_frames),
balón suelto (loose_frames) y recuperación rápida del último poseedor.
"""
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"

INK = "#0f172a"
SLATE = "#475569"
BLUE_F, BLUE_B, BLUE_I = "#eff6ff", "#2563eb", "#1e3a8a"
GREEN_F, GREEN_B, GREEN_I = "#f0fdf4", "#16a34a", "#166534"
RED_F, RED_B, RED_I = "#fef2f2", "#dc2626", "#991b1b"
AMBER_F, AMBER_B, AMBER_I = "#fffbeb", "#d97706", "#92400e"


def text(x, y, s, size=14, fill=INK, weight="normal", anchor="middle", style=""):
    st = f' font-style="{style}"' if style else ""
    return (f'<text x="{x}" y="{y}" font-family="DejaVu Sans, Arial, sans-serif" '
            f'font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{st}>{s}</text>')


def state(cx, cy, w, h, title, sub, fill, border, ink):
    x, y = cx - w / 2, cy - h / 2
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" '
            f'stroke="{border}" stroke-width="2.5"/>'
            + text(cx, cy - 6, title, size=16, fill=ink, weight="bold")
            + text(cx, cy + 16, sub, size=12, fill=SLATE, style="italic"))


def edge(path, color=SLATE):
    return (f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.2" '
            f'marker-end="url(#ar)"/>')


def labels(x, y, lines, fill=SLATE, anchor="middle", size=12):
    out = []
    for i, ln in enumerate(lines):
        out.append(text(x, y + i * 15, ln, size=size, fill=fill, anchor=anchor))
    return "".join(out)


def main():
    W, H = 1240, 770
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
         f'width="{W}" height="{H}" font-family="DejaVu Sans, Arial, sans-serif">']
    s.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    s.append('<defs><marker id="ar" markerWidth="10" markerHeight="10" refX="8" refY="3" '
             'orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,3 L0,6 z" fill="#475569"/>'
             '</marker></defs>')

    s.append(text(W / 2, 34, "Máquina de estados del resolver de posesión",
                  size=22, fill=INK, weight="bold"))
    s.append(text(W / 2, 56, "pipeline/possession/resolver.py — razona por track_id; el % por equipo se deriva después",
                  size=12.5, fill=SLATE, style="italic"))

    # --- Caja: cálculo del candidato por frame ---
    bx, by, bw, bh = 36, 90, 330, 470
    s.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="12" '
             f'fill="#f8fafc" stroke="{SLATE}" stroke-width="1.8" stroke-dasharray="6 4"/>')
    cx = bx + bw / 2
    s.append(text(cx, by + 26, "Candidato c del frame", size=15, fill=INK, weight="bold"))
    s.append(text(cx, by + 44, "(_frame_candidate, en espacio imagen)", size=10.5, fill=SLATE, style="italic"))
    # primaria
    s.append(f'<rect x="{bx+18}" y="{by+62}" width="{bw-36}" height="92" rx="9" fill="{AMBER_F}" stroke="{AMBER_B}" stroke-width="1.8"/>')
    s.append(text(cx, by + 84, "1 · Señal primaria", size=12.5, fill=AMBER_I, weight="bold"))
    s.append(labels(cx, by + 104, [
        "detección clase-5 (player-in-possession)",
        "asociada por IoU ≥ class5_iou,",
        "con balón cerca (si class5_requires_ball)"], size=11))
    # secundaria
    s.append(f'<rect x="{bx+18}" y="{by+166}" width="{bw-36}" height="118" rx="9" fill="{BLUE_F}" stroke="{BLUE_B}" stroke-width="1.8"/>')
    s.append(text(cx, by + 188, "2 · Señal secundaria (proximidad)", size=12.5, fill=BLUE_I, weight="bold"))
    s.append(labels(cx, by + 208, [
        "dist. borde balón→bbox / altura",
        "≤ max_ball_distance_heights;",
        "supresión cerca del aro;",
        "filtro de balón en vuelo (velocidad)"], size=11))
    # desempate
    s.append(f'<rect x="{bx+18}" y="{by+296}" width="{bw-36}" height="92" rx="9" fill="{GREEN_F}" stroke="{GREEN_B}" stroke-width="1.8"/>')
    s.append(text(cx, by + 318, "3 · Desempate P3 (forcejeo)", size=12.5, fill=GREEN_I, weight="bold"))
    s.append(labels(cx, by + 338, [
        "(a) poseedor / último poseedor",
        "(b) coincidencia de movimiento",
        "(c) el más cercano"], size=11))
    s.append(text(cx, by + 410, "⇒  c = track_id   ó   c = None",
                  size=13, fill=INK, weight="bold"))
    s.append(text(cx, by + 432, "(balón suelto / ningún candidato válido)",
                  size=10.5, fill=SLATE, style="italic"))

    # --- Estados de la máquina temporal ---
    pos = (790, 200)      # POSEEDOR = T (estable)
    pend = (1045, 410)    # PENDIENTE -> T'
    none = (790, 600)     # SIN POSEEDOR
    s.append(state(*pos, 320, 96, "POSEEDOR = T", "_possessor = T  (estable)", BLUE_F, BLUE_B, BLUE_I))
    s.append(state(*pend, 250, 96, "PENDIENTE → T′", "histéresis: pend_count", AMBER_F, AMBER_B, AMBER_I))
    s.append(state(*none, 320, 96, "SIN POSEEDOR", "_possessor = None  (suelto)", RED_F, RED_B, RED_I))

    # feed del candidato a la máquina
    s.append(edge(f"M {bx+bw} {by+225} C 470 315, 520 320, 600 280"))
    s.append(text(470, 300, "candidato c", size=12, fill=SLATE, style="italic"))

    # POSEEDOR=T  ->  PENDIENTE  (candidato distinto)
    s.append(edge("M 935 225 C 1000 270, 1010 320, 1020 362"))
    s.append(labels(1030, 280, ["c = T′ ≠ T", "(pend = 1)"], anchor="start"))

    # PENDIENTE -> POSEEDOR (promueve o cancela)
    s.append(edge("M 940 388 C 870 330, 850 290, 845 250"))
    s.append(labels(770, 330, ["c = T′ ×switch_frames ⇒ poseedor := T′", "c = T ⇒ cancela (vuelve a T)"], anchor="middle"))

    # POSEEDOR=T -> SIN POSEEDOR  (balón suelto)
    s.append(edge("M 730 248 C 690 360, 690 440, 720 552"))
    s.append(labels(636, 400, ["c = None", "×loose_frames", "⇒ suelto"], anchor="middle"))

    # SIN POSEEDOR -> POSEEDOR  (fast-return)
    s.append(edge("M 850 552 C 890 440, 890 360, 850 248"))
    s.append(labels(790, 468, ["c = último poseedor", "⇒ recupera (1 frame)"], anchor="middle"))

    # SIN POSEEDOR -> PENDIENTE  (candidato nuevo)
    s.append(edge("M 950 588 C 1020 540, 1050 500, 1060 460"))
    s.append(labels(1090, 545, ["c = candidato", "nuevo (pend = 1)"], anchor="start"))

    # self-loops (salen y entran por el borde real del nodo)
    # POSEEDOR=T self: c = T  (bucle sobre el borde superior)
    s.append(edge("M 720 152 C 705 108, 875 108, 858 152"))
    s.append(text(790, 100, "c = T (se mantiene)", size=11.5, fill=SLATE, anchor="middle"))
    # PENDIENTE self: pend++  (bucle por el borde derecho)
    s.append(edge("M 1170 392 C 1216 370, 1216 434, 1172 430"))
    s.append(labels(1206, 402, ["c = T′", "(pend++)"], anchor="middle", size=11))
    # SIN POSEEDOR self: c = None  (bucle bajo el borde inferior)
    s.append(edge("M 720 648 C 705 692, 875 692, 858 648"))
    s.append(text(790, 712, "c = None (se mantiene)", size=11.5, fill=SLATE, anchor="middle"))

    # nota de parámetros
    s.append(text(W - 20, H - 16,
                  "T = poseedor actual · T′ = candidato distinto · switch_frames, loose_frames = umbrales de histéresis (PossessionSettings)",
                  size=10.5, fill=SLATE, anchor="end", style="italic"))

    s.append('</svg>')
    out = DOCS / "possession_fsm.svg"
    out.write_text("\n".join(s), encoding="utf-8")
    print("escrito", out)


if __name__ == "__main__":
    main()
