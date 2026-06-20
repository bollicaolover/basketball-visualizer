#!/usr/bin/env python3
"""
Genera docs/progreso.svg — Gantt de progreso del TFG basketball-visualizer.

Para actualizar el diagrama, edita el campo `done` de cada área y ejecuta:
    python scripts/generate_progress_svg.py
"""
from datetime import date
from pathlib import Path

# ── Progreso actual ────────────────────────────────────────────────────────
# Edita `done` para reflejar el estado real de cada área.
AREAS = [
    # (nombre,                    inicio,            fin,               total, done, color)
    ("Planificación",          date(2026, 1,  8), date(2026, 1, 22),  2,  2, "#64748B"),
    ("Core & Infra",           date(2026, 1, 29), date(2026, 6, 19), 16, 16, "#3B82F6"),
    ("Detección & Tracking",   date(2026, 1, 22), date(2026, 6, 19),  6,  6, "#F97316"),
    ("Geometría & Homografía", date(2026, 2, 11), date(2026, 3, 19),  5,  5, "#CA8A04"),
    ("Identidad & Equipos",    date(2026, 3, 26), date(2026, 4,  9),  4,  4, "#9333EA"),
    ("Analytics & Reglas",     date(2026, 4,  7), date(2026, 6, 19),  9,  9, "#16A34A"),
    ("Memoria TFG",            date(2026, 6, 14), date(2026, 6, 26),  9,  9, "#B45309"),
]
# ──────────────────────────────────────────────────────────────────────────

PROJECT_START = date(2026, 1, 8)
PROJECT_END   = date(2026, 6, 26)
AUTHOR        = "Gonzalo del Fraile Andújar"

MONTHS = [
    ("Ene", date(2026, 1,  8)),
    ("Feb", date(2026, 2,  1)),
    ("Mar", date(2026, 3,  1)),
    ("Abr", date(2026, 4,  1)),
    ("May", date(2026, 5,  1)),
    ("Jun", date(2026, 6,  1)),
]

# ── Layout ─────────────────────────────────────────────────────────────────
SVG_W   = 760
LBL_W   = 178
CHART_X = LBL_W
CHART_W = SVG_W - CHART_X - 20
ROW_H   = 26
ROW_GAP = 8
STEP    = ROW_H + ROW_GAP
AXIS_Y  = 138
TOP     = 150
TOTAL   = (PROJECT_END - PROJECT_START).days

def xp(d):
    return CHART_X + (d - PROJECT_START).days / TOTAL * CHART_W

GANTT_H = len(AREAS) * STEP
LEG_Y1  = TOP + GANTT_H + 16
SVG_H   = LEG_Y1 + 36

# ── Estadísticas ───────────────────────────────────────────────────────────
total_tasks = sum(a[3] for a in AREAS)
done_tasks  = sum(a[4] for a in AREAS)
pct         = round(done_tasks / total_tasks * 100)
today       = date.today()
days_left   = max(0, (PROJECT_END - today).days)

if pct == 100:
    stat4_val, stat4_lbl = "✓", "proyecto entregado"
else:
    stat4_val, stat4_lbl = str(days_left), "días hasta entrega"

# ── Construcción del SVG ───────────────────────────────────────────────────
L = []

def add(*args):
    L.extend(args)

add(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_W} {SVG_H}"'
    f' width="{SVG_W}" height="{SVG_H}">',
    '  <defs><style>'
    'text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;}'
    '</style></defs>',
    f'  <rect width="{SVG_W}" height="{SVG_H}" fill="#ffffff"/>',
    # Título
    f'  <text x="20" y="26" font-size="14" font-weight="700" fill="#111111">'
    f'Progreso del proyecto — basketball-visualizer</text>',
    f'  <text x="20" y="42" font-size="10" fill="#888888">'
    f'Ene – Jun 2026  ·  Kanban + CRISP-DM  ·  {AUTHOR}</text>',
)

# Cajas de estadísticas
STATS = [
    (str(total_tasks), "tareas totales"),
    (str(done_tasks),  "completadas"),
    (f"{pct}%",        "progreso global"),
    (stat4_val,        stat4_lbl),
]
bw, bh, bgap = 160, 50, 10
for i, (val, lbl) in enumerate(STATS):
    bx = 20 + i * (bw + bgap)
    add(
        f'  <rect x="{bx}" y="54" width="{bw}" height="{bh}" fill="#F5F5F5" rx="7"/>',
        f'  <text x="{bx+12}" y="83" font-size="21" font-weight="800" fill="#111111">{val}</text>',
        f'  <text x="{bx+12}" y="97" font-size="10" fill="#888888">{lbl}</text>',
    )

# Fondo del Gantt
add(f'  <rect x="{CHART_X}" y="{AXIS_Y-6}" width="{CHART_W+20}" height="{GANTT_H+TOP-AXIS_Y+8}"'
    f' fill="#F9F9F9" rx="5"/>')

# Líneas de meses
for mlabel, mdate in MONTHS:
    if mdate > PROJECT_END:
        continue
    mx = xp(mdate)
    add(
        f'  <line x1="{mx:.1f}" y1="{AXIS_Y-2}" x2="{mx:.1f}" y2="{TOP+GANTT_H-4}"'
        f' stroke="#E5E5E5" stroke-width="1"/>',
        f'  <text x="{mx+3:.1f}" y="{AXIS_Y}" font-size="10" fill="#BBBBBB">{mlabel}</text>',
    )

# Barras del Gantt
for i, (name, start, end, tasks, done, color) in enumerate(AREAS):
    ry = TOP + i * STEP
    x1 = xp(start)
    x2 = xp(end)
    bw_ = max(x2 - x1, 4)
    fw  = bw_ * done / tasks if tasks else 0

    if i % 2 == 0:
        add(f'  <rect x="0" y="{ry-1}" width="{SVG_W}" height="{ROW_H+2}" fill="#00000008"/>')

    add(
        f'  <text x="{CHART_X-8}" y="{ry+ROW_H//2+4}" font-size="11"'
        f' text-anchor="end" fill="#222222" font-weight="500">{name}</text>',
        f'  <rect x="{x1:.1f}" y="{ry}" width="{bw_:.1f}" height="{ROW_H}"'
        f' fill="{color}22" rx="4"/>',
        f'  <rect x="{x1:.1f}" y="{ry}" width="{fw:.1f}" height="{ROW_H}"'
        f' fill="{color}" rx="4" opacity="0.85"/>',
        f'  <text x="{x2+6:.1f}" y="{ry+ROW_H//2+4}" font-size="10" fill="#999999">'
        f'{done}/{tasks}</text>',
    )

# Línea de entrega
dlx = xp(PROJECT_END)
add(
    f'  <line x1="{dlx:.1f}" y1="{AXIS_Y-2}" x2="{dlx:.1f}" y2="{TOP+GANTT_H-4}"'
    f' stroke="#EF4444" stroke-width="1.5"/>',
    f'  <text x="{dlx-3:.1f}" y="{AXIS_Y}" font-size="9" text-anchor="end"'
    f' fill="#EF4444" font-weight="600">Entrega</text>',
)

# Leyenda — 2 filas de 4
leg_items = [(name, color) for name, *_, color in AREAS] + [("Entrega (26 jun)", "#EF4444")]
for row in range(2):
    lx = 20
    ly = LEG_Y1 + row * 18
    for name, color in leg_items[row*4:(row+1)*4]:
        if name == "Entrega (26 jun)":
            add(f'  <line x1="{lx}" y1="{ly-5}" x2="{lx+12}" y2="{ly-5}"'
                f' stroke="{color}" stroke-width="2"/>')
        else:
            add(f'  <rect x="{lx}" y="{ly-9}" width="10" height="10"'
                f' fill="{color}" rx="2"/>')
        add(f'  <text x="{lx+16}" y="{ly}" font-size="10" fill="#666666">{name}</text>')
        lx += round(len(name) * 6.3) + 28

add('</svg>')

# ── Escritura ──────────────────────────────────────────────────────────────
out = Path(__file__).parent.parent / "docs" / "progreso.svg"
out.write_text("\n".join(L), encoding="utf-8")
print(f"✓ {out}  ({SVG_H}px alto, {done_tasks}/{total_tasks} tareas, {pct}%)")
