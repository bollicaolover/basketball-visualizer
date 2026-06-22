#!/usr/bin/env python3
"""
Genera docs/cfd.svg (CFD completo) y docs/cfd_m{n}_*.svg (snapshots por hito).

Cumulative Flow Diagram del proyecto, gestionado con **Kanban de flujo único y
WIP=1** (una sola tarjeta activa en cada momento). El diagrama es *data-derived*:
la curva «Hecho» se construye a partir del **historial real de git** (una tarjeta
entregable por commit), de modo que es verificable frente al repositorio.

Modelo:
  - Hecho   : commits acumulados leídos de `git log` (61 commits, 8-ene → 22-jun).
  - Scope   : backlog planificado; crece con el *scope discovery* (rework + la
              ampliación de alcance posterior a la entrega ordinaria del 18-may).
              Es una estimación de planificación, no una magnitud medida.
  - WIP=1   : una tarjeta en progreso entre el inicio y la entrega final.
  - El hueco final entre Scope (65) y Hecho (61) son las **4 tarjetas diferidas**.

Para regenerar:
    python3 scripts/generate_cfd_svg.py
"""
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

START = date(2026, 1, 8)
FINAL = date(2026, 6, 22)
ORDINARIA = date(2026, 5, 18)

MAX_DAYS = (FINAL - START).days          # 165
DELIVERY_DAY = MAX_DAYS                   # entrega final
ORD_DAY = (ORDINARIA - START).days        # 130
MAX_SCOPE = 70                            # headroom del eje Y

# ── Curva «Hecho» desde git (fallback embebido si no hay repo) ────────────────
def done_series_from_git() -> list:
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "log", "--reverse", "--date=short", "--pretty=%ad"],
            capture_output=True, text=True, check=True).stdout
        days = {}
        cum = 0
        pts = [(0, 0)]
        offs = []
        for line in out.splitlines():
            y, m, d = map(int, line.strip().split("-"))
            offs.append((date(y, m, d) - START).days)
        from collections import Counter
        byday = Counter(offs)
        for off in sorted(byday):
            cum += byday[off]
            pts.append((off, cum))
        if pts[-1][1] >= 60:
            return pts
    except Exception as e:
        print("  (aviso: no se pudo leer git, uso curva embebida)", e)
    # Fallback: 61 commits reales (8-ene → 22-jun)
    return [(0,0),(0,1),(5,2),(10,3),(14,4),(19,5),(34,6),(41,7),(43,8),(49,9),
            (56,10),(63,11),(67,12),(70,13),(77,14),(84,15),(89,16),(91,17),(96,18),
            (98,19),(103,20),(104,21),(110,22),(112,23),(117,24),(120,25),(124,26),
            (128,27),(130,28),(131,29),(136,30),(139,31),(140,32),(147,34),(148,35),
            (152,36),(154,38),(157,40),(160,49),(161,51),(162,53),(163,56),(164,59),
            (165,61)]

DONE = done_series_from_git()

# Scope: backlog planificado (estimación). Sube con la ampliación tras la ordinaria.
SCOPE = [(0, 55), (ORD_DAY, 65)]
DISCOVERIES = [(ORD_DAY, 65, "ampliación de alcance (may–jun)")]

# ── Hitos para snapshots: (día, slug, título, fecha_legible) ──────────────────
MILESTONES = [
    ( 49, "m1_geometria",  "Geometría y homografía",                "26 feb 2026"),
    ( 91, "m2_identidad",  "Identidad de equipos (SigLIP + VLM)",   " 9 abr 2026"),
    (112, "m3_pipeline",   "Pipeline ejecutable de extremo a extremo","30 abr 2026"),
    (ORD_DAY, "m4_entrega_ordinaria", "Entrega ordinaria",          "18 may 2026"),
    (161, "m5_tactica",    "Ampliación táctica (pose/3D/pantallas)", "18 jun 2026"),
    (MAX_DAYS, "m6_entrega","Entrega final",                         "22 jun 2026"),
]

MONTHS = [("Ene", 0), ("Feb", 24), ("Mar", 52), ("Abr", 83), ("May", 113), ("Jun", 144)]


# ── Utilidades de series ──────────────────────────────────────────────────────
def step(series, day):
    val = series[0][1]
    for d, v in series:
        if d <= day:
            val = v
        else:
            break
    return val


def build_data():
    days = sorted({d for d, _ in DONE} | {d for d, _ in SCOPE}
                  | {d for d, _, _ in DISCOVERIES} | {0, MAX_DAYS})
    data = []
    for day in days:
        done = step(DONE, day)
        scope = step(SCOPE, day)
        wip = 1 if 0 < day < DELIVERY_DAY else 0
        wip = min(wip, max(scope - done, 0))
        data.append((day, done, scope, wip))
    return data


# ── Render ────────────────────────────────────────────────────────────────────
W, H = 760, 440
ML, MR, MT, MB = 60, 28, 52, 70
CW = W - ML - MR
CH = H - MT - MB

def cx(day): return ML + day / MAX_DAYS * CW
def cy(val): return MT + CH - val / MAX_SCOPE * CH

def poly(top, bot): return " ".join(f"{x:.1f},{y:.1f}" for x, y in top + list(reversed(bot)))
def pline(pts): return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def render_cfd(out_path, data, snapshot_day=None, title_label="", date_str=""):
    is_snap = snapshot_day is not None
    baseP  = [(cx(d), cy(0))        for d, dn, s, w in data]
    doneP  = [(cx(d), cy(dn))       for d, dn, s, w in data]
    wipP   = [(cx(d), cy(dn + w))   for d, dn, s, w in data]
    scopeP = [(cx(d), cy(s))        for d, dn, s, w in data]

    done_now, scope_now = data[-1][1], data[-1][2]
    pct = round(done_now / scope_now * 100) if scope_now else 0

    L = []
    L.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
    L.append('  <defs><style>text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;}</style></defs>')
    L.append(f'  <rect width="{W}" height="{H}" fill="#ffffff"/>')
    L.append(f'  <rect x="{ML}" y="{MT}" width="{CW}" height="{CH}" fill="#FAFAFA"/>')

    main_title = (f'Snapshot · {title_label}' if is_snap
                  else 'Cumulative Flow Diagram — basketball-visualizer')
    sub_title = (f'{date_str}  ·  {done_now}/{scope_now} tarjetas ({pct}%)  ·  Kanban WIP=1'
                 if is_snap
                 else 'Ene – Jun 2026  ·  65 tarjetas (61 hechas · 4 diferidas)  ·  Kanban de flujo único, WIP=1')
    L.append(f'  <text x="20" y="20" font-size="13" font-weight="700" fill="#111111">{main_title}</text>')
    L.append(f'  <text x="20" y="35" font-size="10" fill="#888888">{sub_title}</text>')

    for v in sorted(set(list(range(0, MAX_SCOPE + 1, 10)) + [MAX_SCOPE])):
        y = cy(v); edge = v in (0, MAX_SCOPE)
        L.append(f'  <line x1="{ML}" y1="{y:.1f}" x2="{ML+CW}" y2="{y:.1f}" stroke="{"#CBD5E1" if edge else "#E2E8F0"}" stroke-width="{"1.5" if edge else "1"}"/>')
        L.append(f'  <text x="{ML-6}" y="{y+4:.1f}" font-size="10" text-anchor="end" fill="#94A3B8">{v}</text>')
    lx, ly = ML - 44, MT + CH / 2
    L.append(f'  <text x="{lx:.1f}" y="{ly:.1f}" font-size="10" fill="#64748B" text-anchor="middle" transform="rotate(-90,{lx:.1f},{ly:.1f})">Tarjetas acumuladas</text>')

    for label, day in MONTHS:
        x = cx(day)
        L.append(f'  <line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{MT+CH}" stroke="#E2E8F0" stroke-width="1"/>')
        L.append(f'  <text x="{x:.1f}" y="{MT+CH+16}" font-size="11" text-anchor="middle" fill="#94A3B8">{label}</text>')

    if is_snap and snapshot_day < MAX_DAYS:
        fx = cx(snapshot_day); fw = cx(MAX_DAYS) - fx
        L.append(f'  <rect x="{fx:.1f}" y="{MT}" width="{fw:.1f}" height="{CH}" fill="#94A3B8" opacity="0.12"/>')

    # Bandas apiladas (abajo→arriba): Hecho · WIP · Por hacer
    L.append(f'  <polygon points="{poly(scopeP, wipP)}" fill="#FECACA" opacity="0.75"/>')  # Por hacer/diferido
    L.append(f'  <polygon points="{poly(wipP, doneP)}"  fill="#FDE68A" opacity="0.85"/>')  # En progreso (WIP=1)
    L.append(f'  <polygon points="{poly(doneP, baseP)}" fill="#BBF7D0" opacity="0.92"/>')  # Hecho
    L.append(f'  <polyline points="{pline(scopeP)}" fill="none" stroke="#DC2626" stroke-width="1" stroke-linejoin="round" stroke-dasharray="4,3"/>')
    L.append(f'  <polyline points="{pline(doneP)}"  fill="none" stroke="#16A34A" stroke-width="1.6" stroke-linejoin="round"/>')

    last_day = data[-1][0]
    for disc_day, disc_scope, disc_label in DISCOVERIES:
        if disc_day > last_day:
            continue
        x, y0 = cx(disc_day), cy(disc_scope)
        L.append(f'  <line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y0-16:.1f}" stroke="#818CF8" stroke-width="1" stroke-dasharray="2,2"/>')
        L.append(f'  <text x="{x-3:.1f}" y="{y0-18:.1f}" font-size="8" text-anchor="end" fill="#6366F1">{disc_label}</text>')
        L.append(f'  <polygon points="{x:.1f},{y0-2} {x-3:.1f},{y0-7} {x+3:.1f},{y0-7}" fill="#6366F1"/>')

    L.append(f'  <rect x="{ML}" y="{MT}" width="{CW}" height="{CH}" fill="none" stroke="#CBD5E1" stroke-width="1"/>')

    # Entrega ordinaria (siempre) y entrega final
    ox = cx(ORD_DAY)
    L.append(f'  <line x1="{ox:.1f}" y1="{MT}" x2="{ox:.1f}" y2="{MT+CH}" stroke="#F59E0B" stroke-width="1.3" stroke-dasharray="5,4"/>')
    L.append(f'  <text x="{ox-4:.1f}" y="{MT+12}" font-size="9" text-anchor="end" fill="#B45309" font-weight="600">Entrega ordinaria</text>')
    dlx = cx(DELIVERY_DAY)
    L.append(f'  <line x1="{dlx:.1f}" y1="{MT}" x2="{dlx:.1f}" y2="{MT+CH}" stroke="#EF4444" stroke-width="1.5" stroke-dasharray="5,4"/>')
    L.append(f'  <text x="{dlx-4:.1f}" y="{MT+12}" font-size="9" text-anchor="end" fill="#EF4444" font-weight="600">Entrega final</text>')

    if is_snap:
        sx = cx(snapshot_day)
        L.append(f'  <line x1="{sx:.1f}" y1="{MT}" x2="{sx:.1f}" y2="{MT+CH}" stroke="#0F172A" stroke-width="2"/>')
        L.append(f'  <rect x="{sx-13:.1f}" y="{MT+14}" width="26" height="13" fill="#ffffff" rx="2"/>')
        L.append(f'  <text x="{sx:.1f}" y="{MT+24}" font-size="9" text-anchor="middle" fill="#0F172A" font-weight="700">hoy</text>')

    if not is_snap or snapshot_day >= MAX_DAYS:
        dx, dy = cx(MAX_DAYS) - 5, cy(scope_now) + 26
        L.append(f'  <text x="{dx:.1f}" y="{dy:.1f}" font-size="8" text-anchor="end" fill="#991B1B">4 tarjetas</text>')
        L.append(f'  <text x="{dx:.1f}" y="{dy+11:.1f}" font-size="8" text-anchor="end" fill="#991B1B">diferidas</text>')

    leg = [("#BBF7D0", "#16A34A", "Hecho"),
           ("#FDE68A", "#CA8A04", "En progreso (WIP=1)"),
           ("#FECACA", "#DC2626", "Por hacer / diferido")]
    leg_y = MT + CH + 28
    col_w = (CW + MR) // 3
    for j, (fill, stroke, lbl) in enumerate(leg):
        lx = ML + j * col_w
        L.append(f'  <rect x="{lx}" y="{leg_y-9}" width="14" height="10" fill="{fill}" stroke="{stroke}" stroke-width="1" rx="2"/>')
        L.append(f'  <text x="{lx+19}" y="{leg_y}" font-size="10" fill="#555555">{lbl}</text>')

    L.append('</svg>')
    out_path.write_text("\n".join(L), encoding="utf-8")
    tag = f'snapshot {date_str}' if is_snap else 'CFD completo'
    print(f"  ✓ {out_path.name:<28}  {tag:<22}  {done_now}/{scope_now} ({pct}%)")


# ── Main ──────────────────────────────────────────────────────────────────────
DATA = build_data()
print("Generando CFDs (Kanban WIP=1, data-derived de git)...")
render_cfd(DOCS / "cfd.svg", DATA)
for snap_day, slug, label, date_str in MILESTONES:
    subset = [r for r in DATA if r[0] <= snap_day]
    if subset and subset[-1][0] < snap_day:
        last = subset[-1]
        subset.append((snap_day, last[1], last[2], last[3]))
    render_cfd(DOCS / f"cfd_{slug}.svg", subset, snapshot_day=snap_day,
               title_label=label, date_str=date_str)
print(f"\n{1 + len(MILESTONES)} SVG generados en docs/")
