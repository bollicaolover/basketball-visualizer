#!/usr/bin/env python3
"""
Genera docs/cfd.svg (CFD completo) y docs/cfd_m{n}_*.svg (snapshots por hito).

El proyecto se gestionó con DOS flujos Kanban en paralelo, cada uno con WIP=1:
  - Programación  (tareas técnicas del sistema)
  - Documentación (capítulos de la memoria, desarrollados de forma CONTINUA
                   durante todo el proyecto)
Por eso el WIP combinado puede llegar a 2 (1 tarjeta de programación + 1 de
documentación activas a la vez).

Modelo de datos: dos series acumuladas (programación y documentación) que se
combinan en un único CFD apilado. Para añadir/editar un hito, modifica las
listas y ejecuta:
    python3 scripts/generate_cfd_svg.py
"""
from pathlib import Path

# ── Series acumuladas: (día desde 8-ene-2026, tareas hechas) ──────────────────
# Flujo de PROGRAMACIÓN: 51 tarjetas técnicas; 46 completadas, 5 diferidas.
# El repunte de junio refleja la refactorización del pipeline a módulos y la
# ampliación de alcance (reconocimiento de pantallas / bloqueos).
PROG_DONE = [
    (  0,  0), (  7,  1), ( 21,  2), ( 26,  3), ( 34,  4), ( 43,  5),
    ( 49,  6), ( 56,  7), ( 63,  8), ( 70,  9), ( 77, 10), ( 85, 11),
    ( 90, 12), ( 99, 13), (104, 14), (113, 15), (118, 16), (125, 17),
    (132, 18), (140, 19), (157, 21), (159, 24), (160, 28), (162, 34),
    (164, 40), (166, 43), (168, 46),
]
# Scope de programación: crece al descubrirse nuevas mejoras técnicas.
PROG_SCOPE = [(0, 42), (34, 44), (52, 46), (70, 48), (90, 51)]

# Flujo de DOCUMENTACIÓN: 11 capítulos de la memoria, todos completados.
# Desarrollo continuo a lo largo de todo el proyecto (no concentrado al final).
# (día, hechos)  —  cada escalón es un capítulo cerrado.
DOC_DONE = [
    (  0, 0), ( 10, 1), ( 25, 2), ( 45, 3), ( 65, 4), ( 95, 5),
    (135, 6), (150, 7), (158, 8), (162, 9), (165, 10), (168, 11),
]
DOC_SCOPE_TOTAL = 11        # conocido desde el inicio (índice oficial de la memoria)

# Ventanas de actividad (para el band de WIP). 0 = inactivo.
DOC_START_DAY = 5           # la redacción arranca pocos días después del inicio
DELIVERY_DAY  = 168         # en la entrega ya no hay nada "en progreso"

MAX_DAYS  = 169   # duración del proyecto
MAX_SCOPE = 62    # scope total (51 programación + 11 documentación)

# ── Hitos para snapshots ──────────────────────────────────────────────────────
# (día, slug_archivo, título, fecha_legible)
MILESTONES = [
    ( 49, "m1_geometria",  "Geometría y homografía completas",         "26 feb 2026"),
    ( 70, "m2_tracking",   "Tracking de jugadores y balón",            "19 mar 2026"),
    ( 92, "m3_identidad",  "Identidad de equipos (SigLIP+VLM2)",       " 9 abr 2026"),
    (113, "m4_pipeline",   "Pipeline ejecutable de extremo a extremo", "30 abr 2026"),
    (140, "m5_webapp",     "Web app completa + Docker",                "27 may 2026"),
    (168, "m6_entrega",    "Entrega final",                            "25 jun 2026"),
]

MONTHS = [
    ("Ene",  0), ("Feb", 24), ("Mar", 52),
    ("Abr", 83), ("May",113), ("Jun",144),
]

# Marcadores de scope discovery (día, scope_total_tras_el_descubrimiento, etiqueta)
DISCOVERIES = [
    (34, 55, "+2 mejoras técnicas"),
    (52, 57, "+2 mejoras técnicas"),
    (70, 59, "+2 mejoras técnicas"),
    (90, 62, "+3 mejoras técnicas"),
]


# ── Utilidades de series ──────────────────────────────────────────────────────
def step(series: list, day: int) -> int:
    """Valor de una serie escalonada (último punto con d <= day)."""
    val = series[0][1]
    for d, v in series:
        if d <= day:
            val = v
        else:
            break
    return val


def build_data() -> list:
    """Combina las dos series en (día, prog_done, doc_done, scope, wip)."""
    days = sorted({d for d, _ in PROG_DONE}
                  | {d for d, _ in PROG_SCOPE}
                  | {d for d, _ in DOC_DONE}
                  | {d for d, _, _ in DISCOVERIES}
                  | {0, MAX_DAYS})
    data = []
    for day in days:
        pd = step(PROG_DONE, day)
        ps = step(PROG_SCOPE, day)
        dd = step(DOC_DONE, day)
        scope = ps + DOC_SCOPE_TOTAL
        done = pd + dd
        wip_prog = 1 if 0 < day < DELIVERY_DAY else 0
        wip_doc  = 1 if DOC_START_DAY <= day < DELIVERY_DAY else 0
        wip = min(wip_prog + wip_doc, scope - done)
        data.append((day, pd, dd, scope, wip))
    return data


# ── Función de renderizado ─────────────────────────────────────────────────────
W, H       = 760, 440
ML, MR, MT, MB = 60, 28, 52, 70
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
    - data        : lista de (día, prog_done, doc_done, scope, wip)
    - snapshot_day: si se indica, dibuja el marcador vertical y la región futura.
    """
    is_snapshot = snapshot_day is not None

    # Puntos de cada banda apilada (de abajo arriba: doc → prog → wip → scope)
    baseP    = [(cx(d), cy(0))                  for d, pd, dd, s, w in data]
    docDoneP = [(cx(d), cy(dd))                 for d, pd, dd, s, w in data]
    doneP    = [(cx(d), cy(pd + dd))            for d, pd, dd, s, w in data]
    wipTopP  = [(cx(d), cy(pd + dd + w))        for d, pd, dd, s, w in data]
    scopeP   = [(cx(d), cy(s))                  for d, pd, dd, s, w in data]

    prog_now  = data[-1][1]
    doc_now   = data[-1][2]
    scope_now = data[-1][3]
    done_now  = prog_now + doc_now
    pct       = round(done_now / scope_now * 100) if scope_now else 0

    L: list[str] = []

    # ── Cabecera ──────────────────────────────────────────────────────────────
    L.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
    L.append('  <defs><style>text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;}</style></defs>')
    L.append(f'  <rect width="{W}" height="{H}" fill="#ffffff"/>')
    L.append(f'  <rect x="{ML}" y="{MT}" width="{CW}" height="{CH}" fill="#FAFAFA"/>')

    # ── Título ─────────────────────────────────────────────────────────────────
    main_title = (f'Snapshot {title_label}' if is_snapshot
                  else 'Cumulative Flow Diagram — basketball-visualizer')
    sub_title  = (f'{date_str}  ·  {done_now}/{scope_now} tareas ({pct}%)  ·  WIP≤2 (programación + documentación)'
                  if is_snapshot
                  else 'Ene – Jun 2026  ·  62 tareas (57 hechas, 11 de documentación continua)  ·  WIP≤2: 1 programación + 1 documentación')
    L.append(f'  <text x="20" y="20" font-size="13" font-weight="700" fill="#111111">{main_title}</text>')
    L.append(f'  <text x="20" y="35" font-size="10" fill="#888888">{sub_title}</text>')

    # ── Cuadrícula horizontal + etiquetas Y ────────────────────────────────────
    grid_vals = list(range(0, MAX_SCOPE + 1, 10)) + [MAX_SCOPE]
    for v in sorted(set(grid_vals)):
        y     = cy(v)
        edge  = v in (0, MAX_SCOPE)
        color = "#CBD5E1" if edge else "#E2E8F0"
        lw    = "1.5"    if edge else "1"
        L.append(f'  <line x1="{ML}" y1="{y:.1f}" x2="{ML+CW}" y2="{y:.1f}" stroke="{color}" stroke-width="{lw}"/>')
        L.append(f'  <text x="{ML-6}" y="{y+4:.1f}" font-size="10" text-anchor="end" fill="#94A3B8">{v}</text>')

    # Etiqueta eje Y rotada
    lx, ly = ML - 44, MT + CH / 2
    L.append(f'  <text x="{lx:.1f}" y="{ly:.1f}" font-size="10" fill="#64748B" text-anchor="middle"'
             f' transform="rotate(-90,{lx:.1f},{ly:.1f})">Tareas acumuladas</text>')

    # ── Meses ──────────────────────────────────────────────────────────────────
    for label, day in MONTHS:
        x = cx(day)
        L.append(f'  <line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{MT+CH}" stroke="#E2E8F0" stroke-width="1"/>')
        L.append(f'  <text x="{x:.1f}" y="{MT+CH+16}" font-size="11" text-anchor="middle" fill="#94A3B8">{label}</text>')

    # ── Región futura (solo en snapshots) ──────────────────────────────────────
    if is_snapshot and snapshot_day < MAX_DAYS:
        fx = cx(snapshot_day)
        fw = cx(MAX_DAYS) - fx
        L.append(f'  <rect x="{fx:.1f}" y="{MT}" width="{fw:.1f}" height="{CH}"'
                 f' fill="#94A3B8" opacity="0.12"/>')
        proj_y = cy(scope_now)
        L.append(f'  <line x1="{fx:.1f}" y1="{proj_y:.1f}" x2="{cx(MAX_DAYS):.1f}" y2="{proj_y:.1f}"'
                 f' stroke="#DC2626" stroke-width="1" stroke-dasharray="4,3" opacity="0.4"/>')

    # ── Áreas apiladas ──────────────────────────────────────────────────────────
    L.append(f'  <polygon points="{poly(scopeP, wipTopP)}" fill="#FECACA" opacity="0.75"/>')   # Por hacer / diferido
    L.append(f'  <polygon points="{poly(wipTopP, doneP)}"  fill="#FDE68A" opacity="0.85"/>')   # En progreso (WIP)
    L.append(f'  <polygon points="{poly(doneP, docDoneP)}" fill="#BBF7D0" opacity="0.90"/>')   # Hecho — programación
    L.append(f'  <polygon points="{poly(docDoneP, baseP)}" fill="#99F6E4" opacity="0.95"/>')   # Hecho — documentación

    # Bordes
    L.append(f'  <polyline points="{pline(scopeP)}"   fill="none" stroke="#DC2626" stroke-width="1"   stroke-linejoin="round" stroke-dasharray="4,3"/>')
    L.append(f'  <polyline points="{pline(wipTopP)}"  fill="none" stroke="#CA8A04" stroke-width="1"   stroke-linejoin="round"/>')
    L.append(f'  <polyline points="{pline(doneP)}"    fill="none" stroke="#16A34A" stroke-width="1.5" stroke-linejoin="round"/>')
    L.append(f'  <polyline points="{pline(docDoneP)}" fill="none" stroke="#0D9488" stroke-width="1.2" stroke-linejoin="round"/>')

    # ── Marcadores de scope discovery (solo los que ya han ocurrido) ────────────
    last_day = data[-1][0]
    for i, (disc_day, disc_scope, disc_label) in enumerate(DISCOVERIES):
        if disc_day > last_day:
            continue
        x  = cx(disc_day)
        y0 = cy(disc_scope)
        y1 = y0 - 18
        # Alternar anchor izq/dcha para evitar solapamiento horizontal
        if i % 2 == 0:
            tx, anchor = x + 3, "start"
        else:
            tx, anchor = x - 3, "end"
        # Si el tallo llega demasiado cerca del borde superior, bajar la etiqueta
        if y1 < MT + 20:
            label_y = y0 + 14
            y1 = max(y0 - 6, MT)   # tallo corto
        else:
            label_y = y1 + 1
        L.append(f'  <line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y1:.1f}"'
                 f' stroke="#818CF8" stroke-width="1" stroke-dasharray="2,2"/>')
        L.append(f'  <text x="{tx:.1f}" y="{label_y:.1f}" font-size="8" text-anchor="{anchor}" fill="#6366F1">{disc_label}</text>')
        L.append(f'  <polygon points="{x:.1f},{y0-2} {x-3:.1f},{y0-7} {x+3:.1f},{y0-7}" fill="#6366F1"/>')

    # ── Etiqueta del flujo de documentación continua ────────────────────────────
    if not is_snapshot or snapshot_day >= 95:
        tx, ty = cx(96), cy(step(DOC_DONE, 96)) + 12
        L.append(f'  <text x="{tx:.1f}" y="{ty:.1f}" font-size="8" fill="#0F766E" font-weight="600">'
                 f'documentación continua (WIP=1)</text>')

    # ── Marco ────────────────────────────────────────────────────────────────────
    L.append(f'  <rect x="{ML}" y="{MT}" width="{CW}" height="{CH}" fill="none" stroke="#CBD5E1" stroke-width="1"/>')

    # ── Línea de entrega (siempre visible) ──────────────────────────────────────
    dlx = cx(168)
    L.append(f'  <line x1="{dlx:.1f}" y1="{MT}" x2="{dlx:.1f}" y2="{MT+CH}"'
             f' stroke="#EF4444" stroke-width="1.5" stroke-dasharray="5,4"/>')
    L.append(f'  <text x="{dlx-4:.1f}" y="{MT+12}" font-size="9" text-anchor="end"'
             f' fill="#EF4444" font-weight="600">Entrega</text>')

    # ── Marcador vertical de snapshot ───────────────────────────────────────────
    if is_snapshot:
        sx = cx(snapshot_day)
        L.append(f'  <line x1="{sx:.1f}" y1="{MT}" x2="{sx:.1f}" y2="{MT+CH}"'
                 f' stroke="#0F172A" stroke-width="2"/>')
        L.append(f'  <rect x="{sx-13:.1f}" y="{MT+14}" width="26" height="13" fill="#ffffff" rx="2"/>')
        L.append(f'  <text x="{sx:.1f}" y="{MT+24}" font-size="9" text-anchor="middle"'
                 f' fill="#0F172A" font-weight="700">hoy</text>')

    # ── Anotación sprint final TFG ──────────────────────────────────────────────
    if not is_snapshot or snapshot_day >= 157:
        ax, ay = cx(157), cy(step(PROG_DONE, 157) + step(DOC_DONE, 157)) - 10
        # text-anchor="end" para que no desborde el borde derecho
        L.append(f'  <text x="{ax-4:.1f}" y="{ay:.1f}" font-size="8" text-anchor="end" fill="#166534" font-weight="600">sprint final TFG ▲</text>')

    # ── Anotación "5 diferidas" (CFD completo o snapshot final) ──────────────────
    if not is_snapshot or snapshot_day >= 168:
        dx, dy = cx(168) - 5, cy(scope_now) + 28  # bajado para no solapar "Entrega"
        L.append(f'  <text x="{dx:.1f}" y="{dy:.1f}" font-size="8" text-anchor="end" fill="#991B1B">5 tareas</text>')
        L.append(f'  <text x="{dx:.1f}" y="{dy+11:.1f}" font-size="8" text-anchor="end" fill="#991B1B">diferidas</text>')

    # ── Leyenda (2 filas para no desbordar el ancho) ─────────────────────────────
    leg_y = MT + CH + 28
    row1 = [
        ("#BBF7D0", "#16A34A", "Hecho · programación"),
        ("#99F6E4", "#0D9488", "Hecho · documentación"),
        ("#FDE68A", "#CA8A04", "En progreso (WIP≤2)"),
    ]
    row2 = [
        ("#FECACA", "#DC2626", "Por hacer / diferido"),
        ("#E0E7FF", "#6366F1", "Scope discovery"),
    ]
    col_w = (CW + MR) // 3   # ~233px por columna
    for j, (fill, stroke, lbl) in enumerate(row1):
        lx = ML + j * col_w
        L.append(f'  <rect x="{lx}" y="{leg_y-9}" width="14" height="10" fill="{fill}" stroke="{stroke}" stroke-width="1" rx="2"/>')
        L.append(f'  <text x="{lx+19}" y="{leg_y}" font-size="10" fill="#555555">{lbl}</text>')
    for j, (fill, stroke, lbl) in enumerate(row2):
        lx = ML + j * col_w
        L.append(f'  <rect x="{lx}" y="{leg_y+5}" width="14" height="10" fill="{fill}" stroke="{stroke}" stroke-width="1" rx="2"/>')
        L.append(f'  <text x="{lx+19}" y="{leg_y+14}" font-size="10" fill="#555555">{lbl}</text>')

    L.append('</svg>')

    out_path.write_text("\n".join(L), encoding="utf-8")

    if is_snapshot:
        print(f"  ✓ {out_path.name:<30}  {date_str}  —  {done_now}/{scope_now} tareas ({pct}%)")
    else:
        print(f"  ✓ {out_path.name:<30}  CFD completo  —  {done_now}/{scope_now} tareas")


# ── Main ────────────────────────────────────────────────────────────────────
docs = Path(__file__).parent.parent / "docs"
DATA = build_data()

print("Generando CFDs...")

# 1. CFD completo
render_cfd(docs / "cfd.svg", DATA)

# 2. Snapshots por hito
for snap_day, slug, label, date_str in MILESTONES:
    subset = [row for row in DATA if row[0] <= snap_day]
    if subset and subset[-1][0] < snap_day:
        last = subset[-1]
        subset.append((snap_day, last[1], last[2], last[3], last[4]))
    render_cfd(docs / f"cfd_{slug}.svg", subset,
               snapshot_day=snap_day, title_label=label, date_str=date_str)

print(f"\n{1 + len(MILESTONES)} archivos generados en docs/")
