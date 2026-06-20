#!/usr/bin/env python3
"""Genera docs/homography_diagram.svg: diagrama explicativo de la homografía.

Panel izquierdo  -> vista de cámara (perspectiva, cámara de banda elevada).
Panel derecho    -> vista cenital (plano 2D de la cancha).
Líneas discontinuas conectan los keypoints homólogos; la matriz H en el
centro representa la transformación.

La geometría procede de pipeline/court/geometry.py (los MISMOS 33 keypoints
NBA que usa el estimador de homografía del pipeline). El panel izquierdo se
obtiene proyectando esa geometría con un modelo de cámara pinhole que imita
un plano de retransmisión de banda elevado (no se usa una H ad-hoc: es una
proyección 3D real, así la distorsión perspectiva es fiel).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.court.geometry import (  # noqa: E402
    EDGES,
    NBA_CENTER_CIRCLE_RADIUS_CM,
    NBA_THREE_POINT_ARC_RADIUS_CM,
    CM_PER_FOOT,
)

# geometry.py no expone vertices_ft sin numpy; lo replicamos en python puro.
from pipeline.court import geometry as G  # noqa: E402


def vertices_ft_pure():
    raw = G._raw_vertices_cm()
    return [(x / CM_PER_FOOT, y / CM_PER_FOOT) for (x, y) in raw]


V = vertices_ft_pure()  # 33 puntos (x=largo, y=ancho) en pies
COURT_L = G.NBA_COURT_LENGTH_CM / CM_PER_FOOT   # 94 ft
COURT_W = G.NBA_COURT_WIDTH_CM / CM_PER_FOOT    # 50 ft

# ---------------------------------------------------------------------------
# Modelo de cámara pinhole: banda lateral elevada, mirando al centro.
# ---------------------------------------------------------------------------
CAM = (COURT_L * 0.5, -15.0, 46.0)        # detrás de la banda inferior, elevada
TARGET = (COURT_L * 0.5, COURT_W * 0.5 + 4.0, 0.0)
FOCAL = 720.0


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    m = math.sqrt(_dot(a, a))
    return (a[0] / m, a[1] / m, a[2] / m)


_F = _norm(_sub(TARGET, CAM))
_R = _norm(_cross(_F, (0.0, 0.0, 1.0)))
_U = _cross(_R, _F)


def project(p3):
    """Proyecta un punto mundial (x,y,z=0) a coords de imagen (u,v)."""
    d = _sub(p3, CAM)
    xc, yc, zc = _dot(d, _R), _dot(d, _U), _dot(d, _F)
    if zc <= 0.01:
        zc = 0.01
    return (FOCAL * xc / zc, -FOCAL * yc / zc)  # v negada: arriba = arriba


def world_pt(x_ft, y_ft):
    return (x_ft, y_ft, 0.0)


# ---------------------------------------------------------------------------
# Curvas de la cancha (arcos), muestreadas en mundo y proyectadas/aplanadas.
# ---------------------------------------------------------------------------
def arc_pts(cx, cy, r, a0, a1, n=40):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n),
             cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def circle_pts(cx, cy, r, n=48):
    return [(cx + r * math.cos(2 * math.pi * i / n),
             cy + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


CC = NBA_CENTER_CIRCLE_RADIUS_CM / CM_PER_FOOT
TPR = NBA_THREE_POINT_ARC_RADIUS_CM / CM_PER_FOOT


def three_point_arc(rim_idx, straight_a, straight_b):
    rx, ry = V[rim_idx]
    ax, ay = V[straight_a]
    bx, by = V[straight_b]
    a0 = math.atan2(ay - ry, ax - rx)
    a1 = math.atan2(by - ry, bx - rx)
    # Ir por el lado largo (a través del centro de la cancha).
    if rim_idx < 13:  # canasta izquierda -> arco abre hacia +x
        if a1 < a0:
            a1 += 2 * math.pi
    else:
        if a1 > a0:
            a1 -= 2 * math.pi
    return arc_pts(rx, ry, TPR, a0, a1, 48)


CURVES_WORLD = [
    circle_pts(COURT_L / 2, COURT_W / 2, CC),     # círculo central
    circle_pts(V[10][0], V[10][1], CC),           # círculo tiro libre izq
    circle_pts(V[22][0], V[22][1], CC),           # círculo tiro libre dcha
    three_point_arc(6, 7, 8),                     # arco 3pt izq
    three_point_arc(26, 24, 25),                  # arco 3pt dcha
]

# ---------------------------------------------------------------------------
# Keypoints etiquetados (subconjunto semántico, con su color/letra).
# ---------------------------------------------------------------------------
LABELS = [
    (0,  "A", "esq. inf-izq",      "#ff6b6b"),
    (5,  "B", "esq. sup-izq",      "#ffd93d"),
    (9,  "C", "tiro libre izq",    "#6bcB77"),
    (11, "D", "tiro libre izq",    "#4dd0e1"),
    (13, "E", "vértice 3pt izq",   "#9c88ff"),
    (16, "F", "centro cancha",     "#ff9f43"),
    (15, "G", "banda inf. medio",  "#ff7eb6"),
    (17, "H", "banda sup. medio",  "#54a0ff"),
    (19, "I", "vértice 3pt dcha",  "#c8a2c8"),
    (27, "J", "esq. inf-dcha",     "#1dd1a1"),
    (32, "K", "esq. sup-dcha",     "#feca57"),
]

# ---------------------------------------------------------------------------
# Layout SVG
# ---------------------------------------------------------------------------
W, H = 1280, 660
LP = {"x": 48, "y": 120, "w": 480, "h": 380}    # panel izq (cámara)
RP = {"x": 752, "y": 120, "w": 480, "h": 380}   # panel dcha (cenital)


def fit(points, box, pad=26):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    sx = (box["w"] - 2 * pad) / (maxx - minx)
    sy = (box["h"] - 2 * pad) / (maxy - miny)
    s = min(sx, sy)
    ox = box["x"] + pad + (box["w"] - 2 * pad - s * (maxx - minx)) / 2
    oy = box["y"] + pad + (box["h"] - 2 * pad - s * (maxy - miny)) / 2

    def tf(p):
        return (ox + s * (p[0] - minx), oy + s * (p[1] - miny))
    return tf


# --- Panel izquierdo: proyección perspectiva ---
proj_v = [project(world_pt(x, y)) for (x, y) in V]
proj_curves = [[project(world_pt(x, y)) for (x, y) in c] for c in CURVES_WORLD]
all_left = proj_v + [p for c in proj_curves for p in c]
TF_L = fit(all_left, LP)

# --- Panel derecho: cenital (x=largo horizontal, y=ancho vertical, flip Y) ---
def top_pt(p):
    return (p[0], COURT_W - p[1])  # flip para que "arriba" quede arriba


top_v = [top_pt((x, y)) for (x, y) in V]
top_curves = [[top_pt((x, y)) for (x, y) in c] for c in CURVES_WORLD]
all_right = top_v + [p for c in top_curves for p in c]
TF_R = fit(all_right, RP)

L = [TF_L(p) for p in proj_v]
R = [TF_R(p) for p in top_v]
LC = [[TF_L(p) for p in c] for c in proj_curves]
RC = [[TF_R(p) for p in c] for c in top_curves]

# ---------------------------------------------------------------------------
# Emisión SVG
# ---------------------------------------------------------------------------
NAVY_BG = "#0b1220"
PANEL_BG = "#111c33"
PANEL_STROKE = "#24344f"
LINE = "#3a567f"
WOOD = "#c98a4b"
TXT = "#e6edf6"
SUB = "#8aa0c0"
ACCENT = "#5ad1c8"


def poly(points, stroke, w, dash=None, fill="none", opacity=1.0):
    d = " ".join(f"{x:.1f},{y:.1f}" for (x, y) in points)
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<polyline points="{d}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{w}"{dash_attr} stroke-linejoin="round" '
            f'stroke-linecap="round" opacity="{opacity}"/>')


def line(p, q, stroke, w, dash=None, opacity=1.0):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{q[0]:.1f}" '
            f'y2="{q[1]:.1f}" stroke="{stroke}" stroke-width="{w}"'
            f'{dash_attr} opacity="{opacity}"/>')


parts = []
parts.append(
    f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
    f'font-family="\'Segoe UI\',Helvetica,Arial,sans-serif">')
parts.append(f'<rect width="{W}" height="{H}" fill="{NAVY_BG}"/>')

# defs: glow + arrow
parts.append(
    '<defs>'
    '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">'
    '<feGaussianBlur stdDeviation="2.5" result="b"/>'
    '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
    '</filter>'
    f'<marker id="arrow" markerWidth="10" markerHeight="10" refX="7" refY="3" '
    f'orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="{ACCENT}"/></marker>'
    f'<linearGradient id="hgrad" x1="0" y1="0" x2="1" y2="1">'
    f'<stop offset="0" stop-color="{ACCENT}"/>'
    f'<stop offset="1" stop-color="#7c9cff"/></linearGradient>'
    '</defs>')

# Title
parts.append(
    f'<text x="{W/2}" y="52" text-anchor="middle" fill="{TXT}" '
    f'font-size="30" font-weight="700">Homograf&#237;a: del plano de '
    f'c&#225;mara al plano cenital</text>')
parts.append(
    f'<text x="{W/2}" y="80" text-anchor="middle" fill="{SUB}" '
    f'font-size="15">x&#39; = H&#183;x &#8212; los 33 keypoints NBA del modelo '
    f'enlazan ambos planos (RANSAC sobre pares imagen&#8596;cancha)</text>')

# Panels backgrounds
for box, title, sub in (
    (LP, "Plano de cámara", "fotograma de vídeo · banda elevada (perspectiva)"),
    (RP, "Plano cenital", "cancha 2D · coordenadas reales (pies)")):
    parts.append(
        f'<rect x="{box["x"]}" y="{box["y"]}" width="{box["w"]}" '
        f'height="{box["h"]}" rx="12" fill="{PANEL_BG}" '
        f'stroke="{PANEL_STROKE}" stroke-width="1.5"/>')
    parts.append(
        f'<text x="{box["x"]+16}" y="{box["y"]-26}" fill="{TXT}" '
        f'font-size="18" font-weight="600">{title}</text>')
    parts.append(
        f'<text x="{box["x"]+16}" y="{box["y"]-8}" fill="{SUB}" '
        f'font-size="13">{sub}</text>')

# clip paths so court stays inside panels
parts.append(
    f'<clipPath id="clipL"><rect x="{LP["x"]}" y="{LP["y"]}" '
    f'width="{LP["w"]}" height="{LP["h"]}" rx="12"/></clipPath>'
    f'<clipPath id="clipR"><rect x="{RP["x"]}" y="{RP["y"]}" '
    f'width="{RP["w"]}" height="{RP["h"]}" rx="12"/></clipPath>')

# --- draw court edges + curves in each panel ---
def draw_court(verts, curves, clip):
    g = [f'<g clip-path="url(#{clip})">']
    for (a, b) in EDGES:
        g.append(line(verts[a], verts[b], LINE, 2.0, opacity=0.85))
    for c in curves:
        g.append(poly(c, LINE, 2.0, opacity=0.85))
    g.append('</g>')
    return "".join(g)


parts.append(draw_court(L, LC, "clipL"))
parts.append(draw_court(R, RC, "clipR"))

# --- connecting dashed lines between homologous labeled keypoints ---
parts.append('<g opacity="0.55">')
for (idx, lab, _desc, col) in LABELS:
    parts.append(line(L[idx], R[idx], col, 1.6, dash="5 5"))
parts.append('</g>')

# --- labeled keypoints on both panels ---
def draw_kp(pt, col, lab):
    x, y = pt
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{col}" '
            f'stroke="#0b1220" stroke-width="1.5" filter="url(#glow)"/>'
            f'<text x="{x:.1f}" y="{y-11:.1f}" text-anchor="middle" '
            f'fill="{col}" font-size="13" font-weight="700">{lab}</text>')


for (idx, lab, _desc, col) in LABELS:
    parts.append(draw_kp(L[idx], col, lab))
    parts.append(draw_kp(R[idx], col, lab))

# --- center H badge with arrow ---
cx, cy = W / 2, LP["y"] + LP["h"] / 2
parts.append(
    f'<line x1="{LP["x"]+LP["w"]+6}" y1="{cy}" x2="{RP["x"]-6}" y2="{cy}" '
    f'stroke="{ACCENT}" stroke-width="2.5" marker-end="url(#arrow)" '
    f'opacity="0.9"/>')
bw, bh = 116, 110
parts.append(
    f'<rect x="{cx-bw/2}" y="{cy-bh/2}" width="{bw}" height="{bh}" rx="12" '
    f'fill="{PANEL_BG}" stroke="url(#hgrad)" stroke-width="2"/>')
parts.append(
    f'<text x="{cx}" y="{cy-30}" text-anchor="middle" fill="{ACCENT}" '
    f'font-size="20" font-weight="700">H</text>')
# 3x3 matrix glyph
mvals = [["h₁₁", "h₁₂", "h₁₃"],
         ["h₂₁", "h₂₂", "h₂₃"],
         ["h₃₁", "h₃₂", "1"]]
mx0, my0, dx, dy = cx - 34, cy - 10, 24, 20
for r, row in enumerate(mvals):
    for c, val in enumerate(row):
        parts.append(
            f'<text x="{mx0+c*dx:.1f}" y="{my0+r*dy:.1f}" '
            f'text-anchor="middle" fill="{SUB}" font-size="12" '
            f'font-family="monospace">{val}</text>')
# matrix brackets
parts.append(
    f'<path d="M{cx-44},{cy-22} l-5,0 l0,52 l5,0" fill="none" '
    f'stroke="{SUB}" stroke-width="1.4"/>'
    f'<path d="M{cx+44},{cy-22} l5,0 l0,52 l-5,0" fill="none" '
    f'stroke="{SUB}" stroke-width="1.4"/>')

# --- legend ---
lx, ly = LP["x"], LP["y"] + LP["h"] + 30
parts.append(
    f'<text x="{lx}" y="{ly}" fill="{SUB}" font-size="13">'
    f'Keypoints hom&#243;logos:</text>')
cols = 6
for i, (idx, lab, desc, col) in enumerate(LABELS):
    col_i = i % cols
    row_i = i // cols
    ex = lx + 132 + col_i * 178
    ey = ly - 11 + row_i * 26
    parts.append(
        f'<circle cx="{ex}" cy="{ey}" r="6" fill="{col}"/>'
        f'<text x="{ex+12}" y="{ey+4}" fill="{TXT}" font-size="12">'
        f'<tspan font-weight="700">{lab}</tspan> '
        f'<tspan fill="{SUB}">{desc}</tspan></text>')

parts.append('</svg>')

out = ROOT / "docs" / "homography_diagram.svg"
out.write_text("\n".join(parts), encoding="utf-8")
print(str(out))
