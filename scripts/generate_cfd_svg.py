#!/usr/bin/env python3
"""
Genera docs/cfd.svg (CFD completo) y docs/cfd_m{n}_*.svg (snapshots por hito).

Hitos definidos en MILESTONES. Para añadir uno nuevo, agrega una entrada y ejecuta:
    python3 scripts/generate_cfd_svg.py
"""
from pathlib import Path

# ── Datos: (día desde 8-ene-2026, hecho_acumulado, scope_total) ───────────
# Scope crece cuando se descubren nuevas mejoras técnicas durante el desarrollo.
DATA = [
    (  0,  0, 46), (  0,  1, 46), (  7,  2, 46), ( 21,  3, 46), ( 26,  4, 46),
    ( 34,  6, 48),  # 11 feb — +2 mejoras técnicas descubiertas
    ( 41,  7, 48), ( 43,  8, 48), ( 49, 10, 48),
    ( 52, 10, 50),  # 1 mar — +2 mejoras técnicas
    ( 56, 11, 50), ( 63, 12, 50), ( 67, 13, 50),
    ( 70, 14, 52),  # 19 mar — +2 mejoras técnicas
    ( 77, 15, 52), ( 85, 16, 52),
    ( 90, 17, 55),  # 7 abr — +3 mejoras técnicas
    ( 92, 19, 55), ( 99, 20, 55), (100, 21, 55), (104, 22, 55),
    (106, 23, 55), (111, 24, 55), (113, 25, 55), (118, 26, 55),
    (121, 27, 55), (125, 28, 55), (129, 29, 55), (132, 30, 55),
    (137, 31, 55), (140, 32, 55), (157, 34, 55), (159, 36, 55),
    (160, 38, 55), (162, 44, 55), (164, 46, 55),
    # Trabajo de junio commiteado tarde: cancha KaliCalib, robustez de posesión,
    # reconocimiento de pantallas (Chen 2012) y su exposición en backend/web app.
    (166, 49, 55), (168, 51, 55),
]
MAX_DAYS  = 169   # duración del proyecto
MAX_SCOPE = 55    # scope máximo (eje Y fijo para comparabilidad entre snapshots)

# ── Hitos para snapshots ──────────────────────────────────────────────────
# (día, slug_archivo, título, fecha_legible)
MILESTONES = [
    ( 49, "m1_geometria",  "Geometría y homografía completas",    "26 feb 2026"),
    ( 70, "m2_tracking",   "Tracking de jugadores y balón",       "19 mar 2026"),
    ( 92, "m3_identidad",  "Identidad de equipos (SigLIP+VLM2)",  " 9 abr 2026"),
    (113, "m4_pipeline",   "Pipeline ejecutable de extremo a extremo", "30 abr 2026"),
    (140, "m5_webapp",     "Web app completa + Docker",           "27 may 2026"),
    (168, "m6_entrega",    "Entrega final",                       "25 jun 2026"),
]

MONTHS = [
    ("Ene",  0), ("Feb", 24), ("Mar", 52),
    ("Abr", 83), ("May",113), ("Jun",144),
]

DISCOVERIES = [
    (34,  48, "+2 mejoras técnicas"),
    (52,  50, "+2 mejoras técnicas"),
    (70,  52, "+2 mejoras técnicas"),
    (90,  55, "+3 mejoras técnicas"),
]

# ── Función de renderizado ─────────────────────────────────────────────────
W, H       = 760, 420
ML, MR, MT, MB = 60, 28, 52, 50
CW = W - ML - MR
CH = H - MT - MB

def cx(day: int | float) -> float: return ML + day / MAX_DAYS * CW
def cy(val: int | float) -> float: return MT + CH - val / MAX_SCOPE * CH

def poly(top_pts, bot_pts) -> str:
    pts = top_pts + list(reversed(bot_pts))
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

def pline(pts) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def render_cfd(out_path: Path, data: list, snapshot_day: int | None = None,
               title_label: str = "", date_str: str = "") -> None:
    """
    Renderiza un CFD completo o un snapshot hasta `snapshot_day`.
    - data        : lista de (día, hecho_acum, scope_total)
    - snapshot_day: si se indica, dibuja el marcador vertical y la región futura en gris
    """
    is_snapshot = snapshot_day is not None

    # Puntos de cada banda apilada
    hechoP  = [(cx(d), cy(done))                                      for d, done, s in data]
    wipP    = [(cx(d), cy(done + (1 if done < s else 0)))             for d, done, s in data]
    scopeP  = [(cx(d), cy(s))                                         for d, done, s in data]
    baseP   = [(cx(d), cy(0))                                         for d, done, s in data]

    done_now  = data[-1][1]
    scope_now = data[-1][2]
    pct       = round(done_now / scope_now * 100) if scope_now else 0

    L: list[str] = []

    # ── Cabecera ────────────────────────────────────────────────────────────
    L.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
    L.append('  <defs><style>text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;}</style></defs>')
    L.append(f'  <rect width="{W}" height="{H}" fill="#ffffff"/>')
    L.append(f'  <rect x="{ML}" y="{MT}" width="{CW}" height="{CH}" fill="#FAFAFA"/>')

    # ── Título ───────────────────────────────────────────────────────────────
    main_title = (f'Snapshot {title_label}' if is_snapshot
                  else 'Cumulative Flow Diagram — basketball-visualizer')
    sub_title  = (f'{date_str}  ·  {done_now}/{scope_now} tareas ({pct}%)  ·  Kanban WIP=1'
                  if is_snapshot
                  else 'Ene – Jun 2026  ·  55 tareas identificadas (51 completadas)  ·  Kanban WIP=1')
    L.append(f'  <text x="20" y="20" font-size="13" font-weight="700" fill="#111111">{main_title}</text>')
    L.append(f'  <text x="20" y="35" font-size="10" fill="#888888">{sub_title}</text>')

    # ── Cuadrícula horizontal + etiquetas Y ──────────────────────────────────
    for v in range(0, MAX_SCOPE + 1, 10):
        y     = cy(v)
        color = "#CBD5E1" if v in (0, MAX_SCOPE) else "#E2E8F0"
        lw    = "1.5"    if v in (0, MAX_SCOPE) else "1"
        L.append(f'  <line x1="{ML}" y1="{y:.1f}" x2="{ML+CW}" y2="{y:.1f}" stroke="{color}" stroke-width="{lw}"/>')
        L.append(f'  <text x="{ML-6}" y="{y+4:.1f}" font-size="10" text-anchor="end" fill="#94A3B8">{v}</text>')

    # Etiqueta eje Y rotada
    lx, ly = ML - 44, MT + CH / 2
    L.append(f'  <text x="{lx:.1f}" y="{ly:.1f}" font-size="10" fill="#64748B" text-anchor="middle"'
             f' transform="rotate(-90,{lx:.1f},{ly:.1f})">Tareas acumuladas</text>')

    # ── Meses ────────────────────────────────────────────────────────────────
    for label, day in MONTHS:
        x = cx(day)
        L.append(f'  <line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{MT+CH}" stroke="#E2E8F0" stroke-width="1"/>')
        L.append(f'  <text x="{x:.1f}" y="{MT+CH+16}" font-size="11" text-anchor="middle" fill="#94A3B8">{label}</text>')

    # ── Región futura (solo en snapshots) ───────────────────────────────────
    if is_snapshot and snapshot_day < MAX_DAYS:
        fx = cx(snapshot_day)
        fw = cx(MAX_DAYS) - fx
        L.append(f'  <rect x="{fx:.1f}" y="{MT}" width="{fw:.1f}" height="{CH}"'
                 f' fill="#94A3B8" opacity="0.12"/>')
        # Scope proyectado (línea punteada) a la derecha del snapshot
        proj_y = cy(scope_now)
        L.append(f'  <line x1="{fx:.1f}" y1="{proj_y:.1f}" x2="{cx(MAX_DAYS):.1f}" y2="{proj_y:.1f}"'
                 f' stroke="#DC2626" stroke-width="1" stroke-dasharray="4,3" opacity="0.4"/>')

    # ── Áreas apiladas ───────────────────────────────────────────────────────
    L.append(f'  <polygon points="{poly(scopeP, wipP)}"   fill="#FECACA" opacity="0.75"/>')
    L.append(f'  <polygon points="{poly(wipP,   hechoP)}" fill="#FDE68A" opacity="0.85"/>')
    L.append(f'  <polygon points="{poly(hechoP, baseP)}"  fill="#BBF7D0" opacity="0.90"/>')

    # Bordes
    L.append(f'  <polyline points="{pline(hechoP)}" fill="none" stroke="#16A34A" stroke-width="1.5" stroke-linejoin="round"/>')
    L.append(f'  <polyline points="{pline(wipP)}"   fill="none" stroke="#CA8A04" stroke-width="1"   stroke-linejoin="round"/>')
    L.append(f'  <polyline points="{pline(scopeP)}" fill="none" stroke="#DC2626" stroke-width="1"   stroke-linejoin="round" stroke-dasharray="4,3"/>')

    # ── Marcadores de scope discovery (solo los que ya han ocurrido) ─────────
    last_day = data[-1][0]
    for disc_day, disc_scope, disc_label in DISCOVERIES:
        if disc_day > last_day:
            continue
        x  = cx(disc_day)
        y0 = cy(disc_scope)
        y1 = y0 - 18
        L.append(f'  <line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y1:.1f}"'
                 f' stroke="#818CF8" stroke-width="1" stroke-dasharray="2,2"/>')
        L.append(f'  <text x="{x+3:.1f}" y="{y1+1:.1f}" font-size="8" fill="#6366F1">{disc_label}</text>')
        # Flecha
        L.append(f'  <polygon points="{x:.1f},{y0-2} {x-3:.1f},{y0-7} {x+3:.1f},{y0-7}" fill="#6366F1"/>')

    # ── Marco ────────────────────────────────────────────────────────────────
    L.append(f'  <rect x="{ML}" y="{MT}" width="{CW}" height="{CH}" fill="none" stroke="#CBD5E1" stroke-width="1"/>')

    # ── Línea de entrega (siempre visible) ───────────────────────────────────
    dlx = cx(168)
    L.append(f'  <line x1="{dlx:.1f}" y1="{MT}" x2="{dlx:.1f}" y2="{MT+CH}"'
             f' stroke="#EF4444" stroke-width="1.5" stroke-dasharray="5,4"/>')
    L.append(f'  <text x="{dlx-4:.1f}" y="{MT+12}" font-size="9" text-anchor="end"'
             f' fill="#EF4444" font-weight="600">Entrega</text>')

    # ── Marcador vertical de snapshot ────────────────────────────────────────
    if is_snapshot:
        sx = cx(snapshot_day)
        L.append(f'  <line x1="{sx:.1f}" y1="{MT}" x2="{sx:.1f}" y2="{MT+CH}"'
                 f' stroke="#0F172A" stroke-width="2"/>')
        # Etiqueta "hoy" con fondo blanco
        lbl = "hoy"
        L.append(f'  <rect x="{sx-13:.1f}" y="{MT+14}" width="26" height="13" fill="#ffffff" rx="2"/>')
        L.append(f'  <text x="{sx:.1f}" y="{MT+24}" font-size="9" text-anchor="middle"'
                 f' fill="#0F172A" font-weight="700">{lbl}</text>')

    # ── Anotación sprint final TFG (solo en el CFD completo o en m6) ─────────
    if not is_snapshot or snapshot_day >= 157:
        ax, ay = cx(157), cy(34) - 10
        L.append(f'  <text x="{ax+4:.1f}" y="{ay:.1f}" font-size="8" fill="#166534" font-weight="600">▲ sprint final TFG</text>')

    # ── Anotación "9 diferidas" (solo en CFD completo o snapshot final) ───────
    if not is_snapshot or snapshot_day >= 168:
        dx, dy = cx(168) - 5, cy(50) + 4
        L.append(f'  <text x="{dx:.1f}" y="{dy:.1f}" font-size="8" text-anchor="end" fill="#991B1B">4 tareas</text>')
        L.append(f'  <text x="{dx:.1f}" y="{dy+11:.1f}" font-size="8" text-anchor="end" fill="#991B1B">diferidas</text>')

    # ── Leyenda ───────────────────────────────────────────────────────────────
    leg_y = MT + CH + 30
    items = [
        ("#BBF7D0", "#16A34A", "solid",  "Hecho"),
        ("#FDE68A", "#CA8A04", "solid",  "En progreso (WIP=1)"),
        ("#FECACA", "#DC2626", "dashed", "Por hacer / diferido"),
        ("#E0E7FF", "#6366F1", "dashed", "Scope discovery"),
    ]
    lx = ML
    for fill, stroke, style, lbl in items:
        dash = ' stroke-dasharray="4,3"' if style == "dashed" else ""
        L.append(f'  <rect x="{lx}" y="{leg_y-9}" width="14" height="10" fill="{fill}" stroke="{stroke}" stroke-width="1" rx="2"/>')
        L.append(f'  <text x="{lx+19}" y="{leg_y}" font-size="10" fill="#555555">{lbl}</text>')
        lx += len(lbl) * 6.2 + 34

    L.append('</svg>')

    out_path.write_text("\n".join(L), encoding="utf-8")

    if is_snapshot:
        print(f"  ✓ {out_path.name:<30}  {date_str}  —  {done_now}/{scope_now} tareas ({pct}%)")
    else:
        print(f"  ✓ {out_path.name:<30}  CFD completo  —  {done_now}/{scope_now} tareas")


# ── Main ──────────────────────────────────────────────────────────────────
docs = Path(__file__).parent.parent / "docs"

print("Generando CFDs...")

# 1. CFD completo
render_cfd(docs / "cfd.svg", DATA)

# 2. Snapshots por hito
for snap_day, slug, label, date_str in MILESTONES:
    subset = [(d, done, s) for d, done, s in DATA if d <= snap_day]
    # Asegura que el último punto esté exactamente en snap_day
    if subset and subset[-1][0] < snap_day:
        last = subset[-1]
        subset.append((snap_day, last[1], last[2]))
    render_cfd(docs / f"cfd_{slug}.svg", subset,
               snapshot_day=snap_day, title_label=label, date_str=date_str)

print(f"\n{1 + len(MILESTONES)} archivos generados en docs/")
