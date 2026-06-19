/**
 * Constantes de configuración de la app.
 * Centraliza claves de localStorage, intervalos y geometría de la pista para
 * evitar literales mágicos repartidos por los componentes.
 */

// ── Claves de localStorage ───────────────────────────────────────────────────
export const STORAGE_KEYS = {
  sidebarCollapsed: 'basket2d_sidebar_collapsed',
  teamNames:        'basket2d_team_names',
  gpuPrefs:         'basket2d_gpu_prefs',
  trackerMode:      'basket2d_tracker_mode',
  recentAnalyses:   'basket2d_recent',
  boxFilters:       'basket2d_box_filters',
  boxColors:        'basket2d_box_colors',
  panelSizes:       'basket2d_panel_sizes',
}

// ── Polling ──────────────────────────────────────────────────────────────────
export const JOB_POLL_INTERVAL_MS   = 2000   // estado del job en proceso
export const STATS_POLL_INTERVAL_MS = 2000   // métricas de hardware
export const STATS_HISTORY_LEN      = 20     // puntos del sparkline

// ── Historial ────────────────────────────────────────────────────────────────
export const RECENT_MAX = 20

// ── Reproductor / overlay ────────────────────────────────────────────────────
export const FRAME_STEP_S    = 0.033   // ~1 frame a 30 fps
export const EVENT_LINGER_S  = 1.2     // vigencia de un badge de evento

// ── Geometría de la pista (minimapa vertical) ────────────────────────────────
export const CANVAS_W     = 380
export const CANVAS_H     = 668        // 380 × (102/58) — pista + padding
export const COURT_LEN_FT = 94         // eje Y (arriba → abajo)
export const COURT_WID_FT = 50         // eje X (izquierda → derecha)
export const PADDING_FT   = 4.0
export const COURT_SCALE  = Math.min(
  CANVAS_W / (COURT_WID_FT + 2 * PADDING_FT),
  CANVAS_H / (COURT_LEN_FT + 2 * PADDING_FT),
)
export const ORIGIN_X = PADDING_FT * COURT_SCALE
export const ORIGIN_Y = PADDING_FT * COURT_SCALE
