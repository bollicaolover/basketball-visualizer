<template>
  <div class="results-page">

    <div v-if="metadataError" class="metadata-error-banner">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6">
        <circle cx="8" cy="8" r="7"/>
        <path d="M8 5v3.5M8 11v.5" stroke-linecap="round"/>
      </svg>
      {{ metadataError }}
    </div>

    <div class="main-grid">

      <!-- ── LEFT COLUMN: video + playback line + controls (una sola card) ── -->
      <div class="left-col">
        <div class="card player-card">

          <!-- Header -->
          <div class="card-header">
            <span class="card-label">VIDEO PROCESADO</span>
            <div class="synced-indicator" :class="syncClass">
              {{ syncLabel }}
              <span class="synced-dot"></span>
            </div>
          </div>

          <!-- Vídeo -->
          <div class="card-body video-body">
            <video
              ref="videoEl"
              class="video-el"
              :src="videoSrc"
              preload="metadata"
              :style="{ cursor: hoveredTrackId !== null ? 'pointer' : 'default' }"
              @timeupdate="onTimeUpdate"
              @loadedmetadata="onLoaded"
              @play="onPlay"
              @pause="onPause"
              @error="onVideoError"
              @seeked="onSeeked"
              @mousemove="onVideoMouseMove"
              @mouseleave="onVideoMouseLeave"
              @click="onVideoClick"
            ></video>
            <!-- Capa interactiva de cajas (dibujada desde la metadata) -->
            <canvas ref="boxCanvas" class="box-layer"></canvas>
            <p v-if="videoError" class="video-error">{{ videoError }}</p>
          </div>

          <!-- Barra de reproducción (pegada al vídeo) -->
          <div class="playback-line">
            <div class="timeline-top-row">
              <div class="frame-meta">
                <span class="frame-meta-label">FRAME</span>
                <span class="frame-meta-value">{{ currentFrame?.frame_index ?? '—' }}</span>
                <span class="frame-meta-sep">·</span>
                <span class="frame-meta-value">{{ currentFrame ? currentFrame.timestamp.toFixed(2) + 's' : '—' }}</span>
              </div>
              <div v-if="activeEvents.length" class="event-badges">
                <span
                  v-for="(e, i) in activeEvents"
                  :key="i"
                  class="event-badge"
                  :class="`event-badge--${e.type}`"
                >{{ eventText(e) }}</span>
              </div>
              <div class="time-display">
                <span class="time-current">{{ fmtTime(currentTime) }}</span>
                <span class="time-sep">/</span>
                <span class="time-total">{{ fmtTime(duration) }}</span>
              </div>
            </div>
            <input
              class="timeline"
              type="range"
              min="0"
              :max="duration || 1"
              :step="FRAME_STEP_S"
              :value="currentTime"
              :style="{ '--progress': timelineProgress + '%' }"
              @input="onScrub"
            />
          </div>

          <!-- Transporte: navegación + velocidad -->
          <div class="transport-bar">

            <!-- Botones de reproducción (centrados) -->
            <div class="playback-btns">
              <button class="ctrl-btn" title="Inicio" @click="seek(-duration)">
                <svg width="16" height="16" viewBox="0 0 14 14" fill="currentColor">
                  <rect x="1" y="2" width="2" height="10" rx="0.5"/>
                  <path d="M12 2L4 7l8 5V2z"/>
                </svg>
              </button>
              <button class="ctrl-btn" title="-10s" @click="seek(-10)">
                <svg width="16" height="16" viewBox="0 0 14 14" fill="currentColor">
                  <path d="M8 2L2 7l6 5V2z"/>
                  <path d="M12.5 2L6.5 7l6 5V2z"/>
                </svg>
              </button>
              <button class="ctrl-btn" title="-1 frame" @click="seek(-FRAME_STEP_S)">
                <svg width="16" height="16" viewBox="0 0 14 14" fill="currentColor">
                  <path d="M11 2L3 7l8 5V2z"/>
                </svg>
              </button>

              <button class="ctrl-btn ctrl-btn--play" @click="togglePlay" :title="playing ? 'Pausar' : 'Reproducir'">
                <svg v-if="!playing" width="22" height="22" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M3 2l11 6-11 6V2z"/>
                </svg>
                <svg v-else width="22" height="22" viewBox="0 0 16 16" fill="currentColor">
                  <rect x="3" y="2" width="3.5" height="12" rx="0.8"/>
                  <rect x="9.5" y="2" width="3.5" height="12" rx="0.8"/>
                </svg>
              </button>

              <button class="ctrl-btn" title="+1 frame" @click="seek(FRAME_STEP_S)">
                <svg width="16" height="16" viewBox="0 0 14 14" fill="currentColor">
                  <path d="M3 2l8 5-8 5V2z"/>
                </svg>
              </button>
              <button class="ctrl-btn" title="+10s" @click="seek(10)">
                <svg width="16" height="16" viewBox="0 0 14 14" fill="currentColor">
                  <path d="M2 2l6 5-6 5V2z"/>
                  <path d="M6.5 2l6 5-6 5V2z"/>
                </svg>
              </button>
              <button class="ctrl-btn" title="Final" @click="seek(duration)">
                <svg width="16" height="16" viewBox="0 0 14 14" fill="currentColor">
                  <rect x="11" y="2" width="2" height="10" rx="0.5"/>
                  <path d="M2 2l8 5-8 5V2z"/>
                </svg>
              </button>
            </div>

            <!-- Velocidad de reproducción (anclada a la derecha) -->
            <div class="speed-row">
              <span class="speed-label">VELOCIDAD</span>
              <button
                v-for="s in [0.5, 1, 1.5]"
                :key="s"
                class="speed-chip"
                :class="{ 'speed-chip--active': playbackRate === s }"
                @click="setSpeed(s)"
              >{{ s }}x</button>
            </div>

          </div><!-- /transport-bar -->

          <!-- Filtros de capa (banda propia, debajo del transporte) -->
          <div class="legend-panel">
            <div class="legend-panel-header">
              <span class="legend-panel-title">FILTROS DE CAPA</span>
              <div class="legend-all-row">
                <button
                  class="legend-all-btn"
                  :class="{ 'legend-all-btn--on': rosterLoaded }"
                  title="Cargar roster JSON: colores + nombres de equipo y jugadores"
                  @click="rosterInput?.click()"
                >
                  <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M2 4h12M2 8h12M2 12h7"/>
                  </svg>
                  ROSTER
                </button>
                <button v-if="rosterLoaded" class="legend-all-btn legend-all-btn--off" title="Quitar roster" @click="clearRoster">✕</button>
                <input ref="rosterInput" type="file" accept=".json,application/json" hidden @change="onRosterFile">
                <button class="legend-all-btn" title="Intercambiar qué nombre va a cada equipo" @click="swapTeams">
                  <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M4 4h8l-2-2M12 12H4l2 2"/>
                  </svg>
                  EQUIPOS
                </button>
                <button class="legend-all-btn" @click="setAllFilters(true)">ACTIVAR</button>
                <button class="legend-all-btn legend-all-btn--off" @click="setAllFilters(false)">DESACTIVAR</button>
                <button class="legend-all-btn" title="Restablecer colores" @click="resetColors">
                  <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M13 8a5 5 0 1 1-1.5-3.5M13 2v3h-3"/>
                  </svg>
                  COLOR
                </button>
              </div>
            </div>
            <div class="legend-grid">
              <div class="legend-row">
                <label class="color-edit-btn" :style="{ color: teamColors.home }" title="Cambiar color">
                  <input type="color" :value="teamColors.home" @input="setColor('home', $event.target.value)">
                  <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M11 2l3 3-9 9H2v-3L11 2z"/></svg>
                </label>
                <label class="toggle-item toggle-item--switch">
                  <input type="checkbox" class="toggle-input" :checked="filters.home" @change="toggleFilter('home')">
                  <span class="toggle-switch toggle-switch--home" :style="{ '--toggle-color': teamColors.home }"></span>
                </label>
                <input class="team-name-input" :value="homeName" maxlength="24" title="Nombre del equipo claro" @change="setTeamName(0, $event.target.value)">
              </div>
              <div class="legend-row">
                <label class="color-edit-btn" :style="{ color: teamColors.visitor }" title="Cambiar color">
                  <input type="color" :value="teamColors.visitor" @input="setColor('visitor', $event.target.value)">
                  <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M11 2l3 3-9 9H2v-3L11 2z"/></svg>
                </label>
                <label class="toggle-item toggle-item--switch">
                  <input type="checkbox" class="toggle-input" :checked="filters.visitor" @change="toggleFilter('visitor')">
                  <span class="toggle-switch toggle-switch--visitor" :style="{ '--toggle-color': teamColors.visitor }"></span>
                </label>
                <input class="team-name-input" :value="visitorName" maxlength="24" title="Nombre del equipo oscuro" @change="setTeamName(1, $event.target.value)">
              </div>
              <div class="legend-row">
                <label class="color-edit-btn" :style="{ color: teamColors.ball }" title="Cambiar color del balón">
                  <input type="color" :value="teamColors.ball" @input="setColor('ball', $event.target.value)">
                  <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M11 2l3 3-9 9H2v-3L11 2z"/></svg>
                </label>
                <label class="toggle-item">
                  <input type="checkbox" class="toggle-input" :checked="filters.ball" @change="toggleFilter('ball')">
                  <span class="toggle-switch toggle-switch--ball" :style="{ '--toggle-color': teamColors.ball }"></span>
                  <span class="toggle-label">BALÓN</span>
                </label>
              </div>
              <div class="legend-row">
                <label class="color-edit-btn" :style="{ color: teamColors.ref }" title="Cambiar color del árbitro">
                  <input type="color" :value="teamColors.ref" @input="setColor('ref', $event.target.value)">
                  <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M11 2l3 3-9 9H2v-3L11 2z"/></svg>
                </label>
                <label class="toggle-item">
                  <input type="checkbox" class="toggle-input" :checked="filters.referees" @change="toggleFilter('referees')">
                  <span class="toggle-switch toggle-switch--ref" :style="{ '--toggle-color': teamColors.ref }"></span>
                  <span class="toggle-label">ÁRBITRO</span>
                </label>
              </div>
              <div class="legend-row">
                <label class="color-edit-btn" :style="{ color: teamColors.rim }" title="Cambiar color del aro">
                  <input type="color" :value="teamColors.rim" @input="setColor('rim', $event.target.value)">
                  <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M11 2l3 3-9 9H2v-3L11 2z"/></svg>
                </label>
                <label class="toggle-item">
                  <input type="checkbox" class="toggle-input" :checked="filters.rims" @change="toggleFilter('rims')">
                  <span class="toggle-switch toggle-switch--rim" :style="{ '--toggle-color': teamColors.rim }"></span>
                  <span class="toggle-label">ARO</span>
                </label>
              </div>
              <div class="legend-row">
                <label class="toggle-item" :class="{ 'toggle-item--disabled': !hasTrajectoryData }" :title="trajectoryHint">
                  <input
                    type="checkbox"
                    class="toggle-input"
                    :checked="filters.trajectory"
                    :disabled="!hasTrajectoryData"
                    @change="toggleFilter('trajectory')"
                  >
                  <span class="toggle-switch toggle-switch--traj" :style="{ '--toggle-color': PALETTE.gold }"></span>
                  <span class="toggle-label">TRAYECTORIA</span>
                </label>
              </div>
              <div class="legend-row">
                <label class="toggle-item">
                  <input type="checkbox" class="toggle-input" :checked="filters.possessorOnly" @change="toggleFilter('possessorOnly')">
                  <span class="toggle-switch toggle-switch--poss"></span>
                  <span class="toggle-label">SOLO POSESOR</span>
                </label>
              </div>
            </div>
            <p v-if="rosterError" class="roster-msg roster-msg--err">{{ rosterError }}</p>
          </div>

        </div>
      </div>

      <!-- ── RIGHT COLUMN: esquemático + pista ── -->
      <div class="map-panel" :class="{ 'map-panel--collapsed': !mapOpen }">
        <button
          class="drawer-tab"
          :class="{ 'drawer-tab--open': mapOpen }"
          @click="mapOpen = !mapOpen"
          :title="mapOpen ? 'Colapsar mapa 2D' : 'Expandir mapa 2D'"
        >
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path :d="mapOpen ? 'M6 4l4 4-4 4' : 'M10 4l-4 4 4 4'" />
          </svg>
        </button>

        <div class="right-col">
          <!-- Schematic card -->
          <div class="card map-card">
          <div class="card-header">
            <span class="card-label">ESQUEMA 2D</span>
          </div>
          <div class="card-body canvas-body">
            <canvas
              ref="canvasEl"
              class="court-canvas"
              :width="CANVAS_W"
              :height="CANVAS_H"
            ></canvas>
          </div>
        </div>

          <!-- Jugadas reconocidas -->
          <div class="card screens-card">
            <div class="card-header jugadas-header">
              <span class="card-label">JUGADAS</span>
              <select v-model="activePlayType" class="play-type-select">
                <option value="screens">BLOQUEO</option>
              </select>
              <span class="screens-count">{{ activePlayCount }}</span>
            </div>
            <div class="screens-body">
              <template v-if="activePlayType === 'screens'">
                <p v-if="!screensView.length" class="screens-empty">
                  Sin bloqueos detectados en este clip.
                </p>
                <button
                  v-for="s in screensView"
                  :key="s.id"
                  class="screen-row"
                  :class="[`screen-row--${s.type}`, { 'screen-row--active': s.id === activeScreenId }]"
                  :title="`Saltar al bloqueo (frame ${s.screenFrame})`"
                  @click="goToScreen(s)"
                >
                  <span class="screen-badge">{{ s.label }}</span>
                  <span class="screen-team">{{ s.teamName }}</span>
                  <span class="screen-time">{{ s.time.toFixed(2) }}s</span>
                  <span class="screen-frame">f{{ s.screenFrame }}</span>
                </button>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>


  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  CANVAS_W, CANVAS_H, COURT_LEN_FT, COURT_SCALE, ORIGIN_X, ORIGIN_Y,
  EVENT_LINGER_S, FRAME_STEP_S, STORAGE_KEYS,
} from '../config/index.js'
import { PALETTE, BOX_COLORS, MAP_FILL, MAP_TRAIL, CANVAS_INK } from '../config/palette.js'
import { actionLabel, teamPrefix } from '../utils/labels.js'
import { fmtTime } from '../utils/format.js'
import { outputs, courtImageUrl } from '../services/api.js'
import { buildTrajectoryOverlay } from '../utils/shotTrajectory.js'

const props = defineProps({ jobId: String })
const emit = defineEmits(['reset'])

const videoEl = ref(null)
const canvasEl = ref(null)
const boxCanvas = ref(null)

// Vídeo de reproducción: se prefiere el limpio (sin cajas horneadas) para
// dibujar la capa interactiva encima; si no existe (jobs antiguos), cae al
// overlay anotado.
const CLEAN_SRC   = outputs.cleanVideoUrl(props.jobId)
const OVERLAY_SRC = outputs.overlayVideoUrl(props.jobId)
const videoSrc = ref(CLEAN_SRC)
const usingClean = ref(true)
const shot3dOverlay = ref(null)
const trajectoryOverlay = ref(null)
// Pantallas (screens) reconocidas por pipeline/tactics (Chen et al. 2012).
const screens = ref([])
// Tipo de jugada activo en la card JUGADAS.
const activePlayType = ref('screens')
const hasTrajectoryData = computed(() => {
  const ov = trajectoryOverlay.value
  return ov && Object.keys(ov.frames ?? {}).length > 0
})
const trajectoryHint = computed(() =>
  hasTrajectoryData.value
    ? 'Parábola del tiro (3D o estimada desde el balón)'
    : 'Sin tiro detectado en este clip',
)
const videoError = ref('')
const metadataError = ref('')
const playing = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const playbackRate = ref(1)

const framesData = ref([])
// Nombres de equipo: white→[0], dark→[1]. Por defecto "Equipo 1/2"; se
// sobreescriben con los que traiga la metadata (los que pase el usuario).
const teamNames = ref(['Equipo 1', 'Equipo 2'])
const homeName = computed(() => teamNames.value[0])
const visitorName = computed(() => teamNames.value[1])
const timelineProgress = computed(() => {
  if (!duration.value) return 0
  return Math.min(100, Math.max(0, (currentTime.value / duration.value) * 100))
})
// Override de nombres por análisis (renombrado en el filtro o intercambio). Es
// un ajuste de visualización; no reescribe la metadata del pipeline.
const teamOverrideKey = () => `basket2d_team_names_job_${props.jobId}`
function persistTeamNames() {
  try { localStorage.setItem(teamOverrideKey(), JSON.stringify(teamNames.value)) } catch {}
}
function setTeamName(idx, val) {
  const next = [...teamNames.value]
  next[idx] = val.trim() || (idx === 0 ? 'Equipo 1' : 'Equipo 2')
  teamNames.value = next
  persistTeamNames()
  redrawOverlays()
}
function swapTeams() {
  teamNames.value = [teamNames.value[1], teamNames.value[0]]
  persistTeamNames()
  redrawOverlays()
}

// Back-fill de identidad: el dorsal/nombre es propiedad del track (estable todo
// el vídeo), pero el OCR lo fija a mitad de clip. Se construye track_id→valor
// con el más frecuente visto en cualquier frame y se aplica desde el primero,
// en vez de mostrar el ID hasta que se fija el dorsal.
const numberByTrack = new Map()
const nameByTrack = new Map()
const teamByTrack = new Map()        // track_id → 'white'/'dark' (más frecuente)
const rosterNameByTrack = new Map()  // track_id → nombre resuelto desde el roster
function _mostFrequent(counts) {
  let best = null, bestN = -1
  for (const [v, n] of counts) if (n > bestN) { best = v; bestN = n }
  return best
}
function buildIdentityMaps() {
  numberByTrack.clear()
  nameByTrack.clear()
  teamByTrack.clear()
  const numC = new Map(), nameC = new Map(), teamC = new Map()
  const bump = (map, tid, val) => {
    let m = map.get(tid); if (!m) map.set(tid, m = new Map())
    m.set(val, (m.get(val) || 0) + 1)
  }
  for (const fr of framesData.value) {
    for (const p of (fr.players || [])) {
      if (p.number != null) bump(numC, p.track_id, p.number)
      if (p.name) bump(nameC, p.track_id, p.name)
      if (p.team) bump(teamC, p.track_id, p.team)
    }
  }
  for (const [tid, m] of numC) numberByTrack.set(tid, _mostFrequent(m))
  for (const [tid, m] of nameC) nameByTrack.set(tid, _mostFrequent(m))
  for (const [tid, m] of teamC) teamByTrack.set(tid, _mostFrequent(m))
}
function trackNumber(p) {
  const n = numberByTrack.get(p.track_id)
  return n != null ? n : (p.number != null ? p.number : null)
}
function trackName(p) {
  return rosterNameByTrack.get(p.track_id) ?? nameByTrack.get(p.track_id) ?? p.name ?? null
}

// ── Colores personalizables de cajas/tokens (persistidos) ───────────────────
// home→equipo claro, visitor→equipo oscuro. El canvas no lee variables CSS, así
// que estos valores alimentan tanto el dibujo como los swatches de la leyenda.
const DEFAULT_COLORS = {
  home: '#4f93e0', visitor: '#fdc500', ball: '#ff6b35', ref: '#7e93b0', rim: '#eaf0fa',
}
const teamColors = reactive({
  ...DEFAULT_COLORS,
  ...(() => { try { return JSON.parse(localStorage.getItem(STORAGE_KEYS.boxColors) ?? '{}') } catch { return {} } })(),
})
function setColor(key, val) {
  teamColors[key] = val
  localStorage.setItem(STORAGE_KEYS.boxColors, JSON.stringify(teamColors))
  redrawOverlays()
}
function resetColors() {
  Object.assign(teamColors, DEFAULT_COLORS)
  localStorage.setItem(STORAGE_KEYS.boxColors, JSON.stringify(teamColors))
  redrawOverlays()
}
function _hexRgb(hex) {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}
// Color de caja por rol de equipo.
function boxColor(team) {
  return team === 'white' ? teamColors.home : team === 'dark' ? teamColors.visitor : BOX_COLORS.unknown
}
// Relleno del punto del minimapa (mismo color con alpha).
function mapFillColor(team) {
  const c = team === 'white' ? teamColors.home : team === 'dark' ? teamColors.visitor : null
  if (!c) return MAP_FILL.unknown
  const [r, g, b] = _hexRgb(c)
  return `rgba(${r}, ${g}, ${b}, 0.95)`
}
// Estela de movimiento como tripleta "r, g, b".
function mapTrailRgb(team) {
  const c = team === 'white' ? teamColors.home : team === 'dark' ? teamColors.visitor : null
  if (!c) return MAP_TRAIL.unknown
  return _hexRgb(c).join(', ')
}

// ── Roster (JSON, mismo formato que el backend) ─────────────────────────────
// { "Equipo A": { "colors": "#rrggbb", "players": { "7": "Brown", ... } }, ... }
// Al cargarlo: orienta qué equipo del roster es el claro/oscuro por coincidencia
// de dorsales (fallback posicional) y auto-aplica colores + nombres de equipo +
// nombres de jugador. Persistido por análisis.
const rosterInput = ref(null)
const rosterError = ref('')
const rosterLoaded = ref(false)
const rosterKey = () => `basket2d_roster_job_${props.jobId}`
const _isHex = (s) => typeof s === 'string' && /^#[0-9a-fA-F]{6}$/.test(s)

function _dorsalsByColor() {
  const out = { white: new Set(), dark: new Set() }
  for (const [tid, num] of numberByTrack) {
    const team = teamByTrack.get(tid)
    if (team === 'white' || team === 'dark') out[team].add(num)
  }
  return out
}

// Decide qué clave del roster es el equipo claro y cuál el oscuro.
function _orientRoster(teamA, teamB, roster) {
  const dorsals = _dorsalsByColor()
  const nums = (k) => Object.keys(roster[k].players || {}).map(n => parseInt(n, 10))
  const overlap = (k, color) => nums(k).filter(n => dorsals[color].has(n)).length
  const direct = overlap(teamA, 'white') + overlap(teamB, 'dark')
  const swapped = overlap(teamA, 'dark') + overlap(teamB, 'white')
  // direct: A=claro, B=oscuro. swapped: al revés. Empate/0 → posicional.
  return swapped > direct ? { white: teamB, dark: teamA } : { white: teamA, dark: teamB }
}

function applyRoster(roster) {
  const teams = Object.keys(roster)
  if (teams.length < 2) { rosterError.value = 'El roster debe tener dos equipos.'; return false }
  const [a, b] = teams
  const { white, dark } = _orientRoster(a, b, roster)

  // Colores (si el roster los trae como hex válido).
  if (_isHex(roster[white].colors)) setColor('home', roster[white].colors)
  if (_isHex(roster[dark].colors))  setColor('visitor', roster[dark].colors)

  // Nombres de equipo.
  teamNames.value = [white, dark]
  persistTeamNames()

  // Nombres de jugador por dorsal, según el equipo (color) de cada track.
  rosterNameByTrack.clear()
  for (const [tid, num] of numberByTrack) {
    const team = teamByTrack.get(tid)
    const key = team === 'white' ? white : team === 'dark' ? dark : null
    const name = key && roster[key].players ? roster[key].players[String(num)] : null
    if (name) rosterNameByTrack.set(tid, name)
  }

  rosterLoaded.value = true
  rosterError.value = ''
  redrawOverlays()
  return true
}

function onRosterFile(e) {
  const file = e.target.files && e.target.files[0]
  e.target.value = ''  // permite recargar el mismo fichero
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    try {
      const roster = JSON.parse(String(reader.result))
      if (!roster || typeof roster !== 'object' || Array.isArray(roster)) {
        rosterError.value = 'JSON de roster no válido.'; return
      }
      if (applyRoster(roster)) {
        try { localStorage.setItem(rosterKey(), JSON.stringify(roster)) } catch {}
      }
    } catch {
      rosterError.value = 'No se pudo leer el JSON.'
    }
  }
  reader.readAsText(file)
}

function clearRoster() {
  rosterNameByTrack.clear()
  rosterLoaded.value = false
  rosterError.value = ''
  try { localStorage.removeItem(rosterKey()) } catch {}
  redrawOverlays()
}

const currentFrame = ref(null)
const synced = ref(false)
// Indicador de sincronía en tres estados: sin datos → "SIN SEÑAL"; con datos en
// pausa → "EN PAUSA" (estado de bienvenida, no de error); reproduciendo →
// "SINCRONIZADO". "SIN SEÑAL" queda reservado a la pérdida real de señal.
const syncLabel = computed(() =>
  !synced.value ? 'SIN SEÑAL' : (playing.value ? 'SINCRONIZADO' : 'EN PAUSA'),
)
const syncClass = computed(() => ({
  'synced-indicator--on':     synced.value && playing.value,
  'synced-indicator--paused': synced.value && !playing.value,
}))
const hoveredTrackId = ref(null)
// Selección múltiple: conjunto de track_id. Se reasigna un Set nuevo en cada
// cambio para que la reactividad del ref dispare el repintado.
const selectedTrackIds = ref(new Set())

// ── Filtros de la capa de cajas (persistidos) ───────────────────────────────
const filters = reactive({
  home: true, visitor: true, ball: true,
  referees: true, rims: false, possessorOnly: false, trajectory: false,
  ...(() => { try { return JSON.parse(localStorage.getItem(STORAGE_KEYS.boxFilters) ?? '{}') } catch { return {} } })(),
})
function toggleFilter(key) {
  filters[key] = !filters[key]
  localStorage.setItem(STORAGE_KEYS.boxFilters, JSON.stringify(filters))
  redrawOverlays()
}
function setAllFilters(val) {
  filters.home = val
  filters.visitor = val
  filters.ball = val
  filters.referees = val
  filters.rims = val
  if (!val) filters.possessorOnly = false
  localStorage.setItem(STORAGE_KEYS.boxFilters, JSON.stringify(filters))
  redrawOverlays()
}

// Eventos de interacción (pase/rebote/robo) precomputados con su timestamp.
const allEvents = ref([])
const activeEvents = ref([])   // eventos vigentes (~EVENT_LINGER_S tras dispararse)

// Redibuja mapa + cajas cuando cambia hover/selección (el RAF loop sólo corre
// mientras se reproduce; en pausa hay que repintar a mano).
watch([hoveredTrackId, selectedTrackIds], () => {
  if (!playing.value && currentFrame.value) drawCanvas(currentFrame.value)
  drawBoxes()
})

// Repinta ambas capas (mapa 2D si está en pausa, y siempre la capa de cajas).
function redrawOverlays() {
  if (!playing.value && currentFrame.value) drawCanvas(currentFrame.value)
  drawBoxes()
}

// ── Panel derecho colapsable ─────────────────────────────────────────────────
const mapOpen = ref(true)

let courtImage = null
let rafId = null
let vfcId = null
let seeking = false          // hay un seek del vídeo en curso
let pendingSeekTime = null   // última posición pedida mientras seekeaba
let boxResizeObs = null

onMounted(async () => {
  await loadMetadata()
  await loadShot3dOverlay()
  ensureTrajectoryOverlay()
  await loadTactics()
  loadCourtImage()
  // Repinta la capa de cajas cuando cambia el tamaño mostrado del vídeo
  // (redimensionar ventana, arrastrar el divisor de paneles, etc.).
  if (videoEl.value && 'ResizeObserver' in window) {
    boxResizeObs = new ResizeObserver(() => { resizeBoxCanvas(); drawBoxes() })
    boxResizeObs.observe(videoEl.value)
  }
})

async function loadShot3dOverlay() {
  const data = await outputs.shot3dJson(props.jobId)
  if (!data) return
  shot3dOverlay.value = data
  if (data.overlay?.frames && Object.keys(data.overlay.frames).length) {
    trajectoryOverlay.value = data.overlay
  }
}

function ensureTrajectoryOverlay() {
  if (trajectoryOverlay.value) return
  const fps = shot3dOverlay.value?.fps ?? 30
  const built = buildTrajectoryOverlay(framesData.value, fps)
  if (built) trajectoryOverlay.value = built
}

// ── Pantallas (screens) ─────────────────────────────────────────────────────
async function loadTactics() {
  const data = await outputs.tactics(props.jobId)
  screens.value = Array.isArray(data?.screens) ? data.screens : []
}

const SCREEN_LABELS = { front: 'FRONT', back: 'BACK', down: 'DOWN', undefined: '—' }

// Timestamp (s) de un frame_index, leído de la metadata (o estimado por fps).
function frameTimestamp(frameIndex) {
  const fr = framesData.value.find((f) => f.frame_index === frameIndex)
  if (fr && typeof fr.timestamp === 'number') return fr.timestamp
  const fps = shot3dOverlay.value?.fps ?? 30
  return frameIndex / fps
}

// Pantalla cuyo rango [start_frame, end_frame] contiene el frame dado, o null.
function activeScreenForFrame(frameIdx) {
  if (frameIdx == null) return null
  return screens.value.find(s => frameIdx >= s.start_frame && frameIdx <= s.end_frame) ?? null
}

// Vista de la lista: tipo, equipo, instante y frame de salto (cuando se fija).
const screensView = computed(() =>
  screens.value.map((s, i) => {
    const t = frameTimestamp(s.screen_frame)
    return {
      id: i,
      type: s.screen_type,
      label: SCREEN_LABELS[s.screen_type] ?? '—',
      teamName: s.team === 'white' ? teamNames.value[0]
        : s.team === 'dark' ? teamNames.value[1] : '—',
      team: s.team,
      time: t,
      startFrame: s.start_frame,
      endFrame: s.end_frame,
      screenFrame: s.screen_frame,
    }
  }),
)

// Número de eventos del tipo activo (para el badge del header).
const activePlayCount = computed(() =>
  activePlayType.value === 'screens' ? screensView.value.length : 0,
)

// Pantalla "activa": aquella cuyo rango contiene el frame mostrado ahora mismo.
const activeScreenId = computed(() => {
  const fi = currentFrame.value?.frame_index
  if (fi == null) return -1
  const hit = screensView.value.find((s) => fi >= s.startFrame && fi <= s.endFrame)
  return hit ? hit.id : -1
})

function goToScreen(s) {
  if (!videoEl.value) return
  videoEl.value.currentTime = Math.max(0, Math.min(duration.value, s.time))
}

onUnmounted(() => {
  stopRaf()
  stopFrameSync()
  boxResizeObs?.disconnect()
})

async function loadMetadata() {
  try {
    const result = await outputs.metadata(props.jobId)
    if (!result.ok) {
      metadataError.value = result.detail ?? `El análisis no está disponible (${result.status})`
      return
    }
    const data = result.data
    // Formato nuevo: {team_names, frames}; antiguo: array plano (compat).
    framesData.value = Array.isArray(data) ? data : (data.frames ?? [])
    buildIdentityMaps()
    const names = Array.isArray(data) ? null : data.team_names
    if (Array.isArray(names) && names.length === 2) teamNames.value = names
    // Override del usuario para este análisis (renombrado en el filtro).
    try {
      const ov = JSON.parse(localStorage.getItem(teamOverrideKey()) ?? 'null')
      if (Array.isArray(ov) && ov.length === 2) teamNames.value = ov
    } catch { /* ignora override corrupto */ }
    // Aplana los eventos de interacción con su timestamp (para badges/saltos).
    const evs = []
    for (const fr of framesData.value) {
      for (const e of (fr.action_events || [])) {
        evs.push({ ...e, t: fr.timestamp })
      }
    }
    allEvents.value = evs
    // Roster para este análisis (re-aplica colores + nombres). Primero el que
    // guardó el usuario en local; si no hay, el que dejó el servidor —así los
    // vídeos de prueba traen su roster sin que nadie suba el JSON.
    try {
      let saved = JSON.parse(localStorage.getItem(rosterKey()) ?? 'null')
      if (!saved || typeof saved !== 'object') {
        saved = await outputs.roster(props.jobId)
      }
      if (saved && typeof saved === 'object') applyRoster(saved)
    } catch { /* ignora roster corrupto */ }
    primeFirstFrame()  // si el vídeo ya cargó, puebla la cancha ahora mismo
  } catch (e) {
    console.error('No se pudieron cargar los metadatos:', e)
    metadataError.value = 'No se pudieron cargar los datos del análisis.'
  }
}

function onLoaded() {
  videoError.value = ''
  duration.value = videoEl.value.duration
  resizeBoxCanvas()
  drawBoxes()
  startFrameSync()   // sincroniza la capa con el frame mostrado (rVFC)
  primeFirstFrame()  // pinta el frame 0 ya en reposo (cancha poblada sin play)
}

// Pinta el primer frame disponible sin esperar a que el usuario dé a play, para
// que la pizarra 2D y los nombres aparezcan al abrir el análisis. Requiere que
// vídeo y metadatos estén cargados; se invoca desde ambos (el que llegue último).
function primeFirstFrame() {
  if (playing.value || !videoEl.value || !framesData.value.length) return
  updateCanvas(videoEl.value.currentTime || 0)
}

function onVideoError() {
  // El vídeo limpio puede no existir (jobs antiguos): se reintenta con el
  // overlay anotado antes de dar el error definitivo.
  if (usingClean.value) {
    usingClean.value = false
    videoSrc.value = OVERLAY_SRC
    return
  }
  videoError.value =
    'No se puede reproducir el vídeo (códec no compatible). ' +
    'Vuelve a procesar el clip con la versión actual del pipeline.'
}

// ── Sincronización capa↔vídeo ───────────────────────────────────────────────
// requestVideoFrameCallback entrega el mediaTime EXACTO del frame que el vídeo
// está mostrando, así la capa de cajas queda pegada al vídeo incluso en scrub
// rápido (cuando el decodificado va por detrás del slider). Fallback a RAF.
const hasVFC = () => !!videoEl.value && 'requestVideoFrameCallback' in videoEl.value

function pumpFrame(_now, meta) {
  const t = meta ? meta.mediaTime : (videoEl.value?.currentTime ?? 0)
  // En scrub el slider y la lectura de tiempo los fija onScrub; aquí seguimos
  // el vídeo solo durante la reproducción para no pelear con el arrastre.
  if (playing.value) currentTime.value = t
  updateCanvas(t)
  vfcId = videoEl.value?.requestVideoFrameCallback(pumpFrame)
}

function startFrameSync() {
  if (!hasVFC()) return
  if (vfcId !== null) videoEl.value.cancelVideoFrameCallback(vfcId)
  vfcId = videoEl.value.requestVideoFrameCallback(pumpFrame)
}

function stopFrameSync() {
  if (vfcId !== null && videoEl.value) videoEl.value.cancelVideoFrameCallback(vfcId)
  vfcId = null
}

function onPlay() {
  playing.value = true
  if (!hasVFC()) startRaf()
}

function onPause() {
  playing.value = false
  if (!hasVFC()) stopRaf()
}

function startRaf() {
  function tick() {
    if (!videoEl.value || videoEl.value.paused) return
    const t = videoEl.value.currentTime
    currentTime.value = t
    updateCanvas(t)
    rafId = requestAnimationFrame(tick)
  }
  if (rafId !== null) cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(tick)
}

function stopRaf() {
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
}

function onTimeUpdate() {
  if (!playing.value) {
    currentTime.value = videoEl.value.currentTime
    updateCanvas(videoEl.value.currentTime)
  }
}

// Scrub fluido: mantiene UN solo seek en vuelo. Mientras el vídeo busca, las
// posiciones intermedias se descartan y solo se conserva la última; al terminar
// (evento `seeked`) se salta a ella. Evita la cola de seeks que dejaba el vídeo
// rezagado respecto al slider.
function requestSeek(t) {
  const vid = videoEl.value
  if (!vid) return
  if (seeking) { pendingSeekTime = t; return }
  seeking = true
  vid.currentTime = t
}

function onSeeked() {
  seeking = false
  if (pendingSeekTime !== null) {
    const t = pendingSeekTime
    pendingSeekTime = null
    requestSeek(t)
  }
}

function onScrub(e) {
  const t = parseFloat(e.target.value)
  currentTime.value = t
  // Con rVFC la capa se sincroniza con el frame realmente presentado por el
  // vídeo (pumpFrame); sin rVFC, refresco inmediato del overlay.
  if (!hasVFC()) updateCanvas(t)
  requestSeek(t)
}

function updateCanvas(timestamp) {
  if (!framesData.value.length) return
  const entry = findByTimestamp(framesData.value, timestamp)
  currentFrame.value = entry
  synced.value = true
  // Eventos vigentes: los disparados en los últimos EVENT_LINGER_S segundos.
  activeEvents.value = allEvents.value.filter(
    e => timestamp >= e.t && timestamp <= e.t + EVENT_LINGER_S,
  )
  drawCanvas(entry)
  drawBoxes()
}

function eventText(e) {
  if (e.type === 'pass') return `PASE  ${teamPrefix(e.team)}${e.from_track_id}→${teamPrefix(e.team)}${e.track_id}`
  if (e.type === 'steal') return `ROBO  ${teamPrefix(e.team)}${e.track_id}`
  if (e.type === 'rebound') return `REBOTE ${e.kind === 'offensive' ? 'OF' : 'DEF'} ${teamPrefix(e.team)}${e.track_id}`
  return e.type
}

function findByTimestamp(frames, t) {
  let lo = 0, hi = frames.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (frames[mid].timestamp <= t) lo = mid
    else hi = mid - 1
  }
  return frames[lo]
}

function loadCourtImage() {
  const img = new Image()
  img.src = courtImageUrl
  img.onload = () => {
    courtImage = img
    const ctx = canvasEl.value?.getContext('2d')
    if (ctx) {
      ctx.fillStyle = PALETTE.bgCard
      ctx.fillRect(0, 0, CANVAS_W, CANVAS_H)
      drawCourtImage(ctx)
    }
  }
}

// Rotates the landscape court image -90° onto the portrait canvas, luego asienta
// la cancha en la pizarra oscura con un velo translúcido.
function drawCourtImage(ctx) {
  ctx.save()
  ctx.translate(0, CANVAS_H)
  ctx.rotate(-Math.PI / 2)
  ctx.drawImage(courtImage, 0, 0, CANVAS_H, CANVAS_W)
  ctx.restore()
  ctx.fillStyle = CANVAS_INK.courtTint
  ctx.fillRect(0, 0, CANVAS_W, CANVAS_H)
}

// Índice del frame por timestamp (para reconstruir las estelas hacia atrás).
function frameIndexByTimestamp(frames, t) {
  let lo = 0, hi = frames.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (frames[mid].timestamp <= t) lo = mid
    else hi = mid - 1
  }
  return lo
}

// Posición en pizarra de un jugador (misma transformación que en drawCanvas).
function courtXY(p) {
  return [CANVAS_W - ORIGIN_X - p.y_ft * COURT_SCALE, ORIGIN_Y + p.x_ft * COURT_SCALE]
}

// Estelas: rastro de las últimas TRAIL_LEN posiciones, desvaneciéndose hacia atrás.
const TRAIL_LEN = 12
function drawTrails(ctx, frame) {
  const frames = framesData.value
  const idx = frameIndexByTimestamp(frames, frame.timestamp)
  const start = Math.max(0, idx - TRAIL_LEN)
  const paths = new Map()   // track_id → { team, pts: [[x,y],…] }
  for (let i = start; i <= idx; i++) {
    for (const p of frames[i].players) {
      let entry = paths.get(p.track_id)
      if (!entry) { entry = { team: p.team, pts: [] }; paths.set(p.track_id, entry) }
      entry.pts.push(courtXY(p))
    }
  }
  ctx.save()
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  for (const { team, pts } of paths.values()) {
    if (pts.length < 2) continue
    const rgb = mapTrailRgb(team)
    for (let i = 1; i < pts.length; i++) {
      const a = (i / pts.length) * 0.55      // más opaco cuanto más reciente
      ctx.strokeStyle = `rgba(${rgb}, ${a})`
      ctx.lineWidth = 1 + (i / pts.length) * 3
      ctx.beginPath()
      ctx.moveTo(pts[i - 1][0], pts[i - 1][1])
      ctx.lineTo(pts[i][0], pts[i][1])
      ctx.stroke()
    }
  }
  ctx.restore()
}

// Etiqueta pequeña redondeada (acción) centrada en (cx, cy).
function drawActionTag(ctx, cx, cy, text, color) {
  ctx.font = 'bold 7.5px "Inter Variable", system-ui, sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  const w = ctx.measureText(text).width + 8
  ctx.fillStyle = CANVAS_INK.tagBg
  ctx.strokeStyle = CANVAS_INK.tagBorder
  ctx.lineWidth = 0.75
  ctx.beginPath()
  ctx.roundRect(cx - w / 2, cy - 6, w, 12, 3)
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = color
  ctx.fillText(text, cx, cy)
}

function drawCanvas(frame) {
  const ctx = canvasEl.value?.getContext('2d')
  if (!ctx) return

  ctx.fillStyle = PALETTE.bgCard
  ctx.fillRect(0, 0, CANVAS_W, CANVAS_H)
  if (courtImage) {
    drawCourtImage(ctx)
  }

  if (!frame) return

  drawTrails(ctx, frame)

  for (const p of frame.players) {
    // Vertical court: y_ft → X axis (mirrored to match -90° image rotation), x_ft → Y axis
    const px = CANVAS_W - ORIGIN_X - p.y_ft * COURT_SCALE
    const py = ORIGIN_Y + p.x_ft * COURT_SCALE
    const isPossessor = p.track_id === frame.possessor_track_id
    const isHovered   = p.track_id === hoveredTrackId.value || selectedTrackIds.value.has(p.track_id)

    const fillColor = mapFillColor(p.team)

    // Seleccionado/hover: anillo exterior azur (estado interactivo) con glow,
    // separado del posesor para no leerse como un doble círculo.
    if (isHovered) {
      ctx.save()
      ctx.shadowColor = CANVAS_INK.hoverGlow
      ctx.shadowBlur = 14
      ctx.beginPath()
      ctx.arc(px, py, 23, 0, Math.PI * 2)
      ctx.strokeStyle = CANVAS_INK.hoverRing
      ctx.lineWidth = 2.5
      ctx.stroke()
      ctx.restore()
    }

    // Posesor: anillo oro (estado de posesión).
    if (isPossessor) {
      ctx.beginPath()
      ctx.arc(px, py, 17, 0, Math.PI * 2)
      ctx.strokeStyle = PALETTE.gold
      ctx.lineWidth = 3
      ctx.stroke()
    }

    ctx.beginPath()
    ctx.arc(px, py, 13, 0, Math.PI * 2)
    ctx.fillStyle = fillColor
    ctx.fill()
    ctx.strokeStyle = CANVAS_INK.dotStroke
    ctx.lineWidth = 1.5
    ctx.stroke()

    // Etiqueta dentro del punto: dorsal si identificado (en cualquier frame del
    // track), sino prefix+id
    const pNum = trackNumber(p)
    const pName = trackName(p)
    const dotLabel = pNum != null ? String(pNum) : `${teamPrefix(p.team)}${p.track_id}`
    ctx.fillStyle = p.team === 'dark' ? PALETTE.navyDeep : PALETTE.white
    ctx.font = `${isHovered ? 'bold 12px' : 'bold 11px'} "Inter Variable", system-ui, sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(dotLabel, px, py)

    // Nombre del roster bajo el punto (siempre visible cuando está disponible)
    if (pName) {
      drawActionTag(ctx, px, py + 19, pName, PALETTE.chalk)
    }

    // Acción bajo el punto (posesor o hover); desplazada si hay nombre
    const tag = actionLabel(p.action)
    if (tag && p.action !== 'no_action' && (isPossessor || isHovered)) {
      const actionY = pName ? py + 31 : py + 19
      drawActionTag(ctx, px, actionY, tag, isPossessor ? PALETTE.gold : PALETTE.azure)
    }

    // Hovered: etiqueta encima del punto con nombre (si lo hay) o equipo
    if (isHovered) {
      const hoverLabel = pName
        ? pName
        : p.team === 'white' ? homeName.value : p.team === 'dark' ? visitorName.value : `ID ${p.track_id}`
      const labelColor = pName
        ? PALETTE.chalk
        : p.team === 'white' ? PALETTE.azure : p.team === 'dark' ? PALETTE.gold : PALETTE.blue
      ctx.font = 'bold 7.5px "Inter Variable", system-ui, sans-serif'
      const lw = ctx.measureText(hoverLabel).width + 10
      const lh = 14
      const lx = px - lw / 2
      const ly = py - 28
      ctx.fillStyle = CANVAS_INK.tagBg
      ctx.strokeStyle = CANVAS_INK.tagBorder
      ctx.lineWidth = 0.75
      ctx.beginPath()
      ctx.roundRect(lx, ly - lh / 2, lw, lh, 3)
      ctx.fill()
      ctx.stroke()
      ctx.fillStyle = labelColor
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(hoverLabel, px, ly)
    }
  }

  // Overlay de bloqueo activo: anillo sólido (screener), anillo discontinuo
  // (screenee) y línea punteada entre ambos, con color por tipo de pantalla.
  const activeScr = activeScreenForFrame(frame.frame_index)
  if (activeScr) {
    const SCOL = { front: PALETTE.teal, back: PALETTE.gold, down: PALETTE.orange }
    const col = SCOL[activeScr.screen_type] ?? PALETTE.chalk
    const scrP = frame.players.find(p => p.track_id === activeScr.screener_track)
    const seeP = frame.players.find(p => p.track_id === activeScr.screenee_track)
    if (scrP && seeP) {
      const [sx, sy] = courtXY(scrP)
      const [ex, ey] = courtXY(seeP)
      ctx.save()
      // Línea punteada entre ambos
      ctx.globalAlpha = 0.7
      ctx.setLineDash([5, 3])
      ctx.strokeStyle = col
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(sx, sy)
      ctx.lineTo(ex, ey)
      ctx.stroke()
      // Anillo screener (sólido)
      ctx.setLineDash([])
      ctx.globalAlpha = 1
      ctx.beginPath()
      ctx.arc(sx, sy, 21, 0, Math.PI * 2)
      ctx.strokeStyle = col
      ctx.lineWidth = 3
      ctx.stroke()
      // Anillo screenee (discontinuo)
      ctx.setLineDash([4, 3])
      ctx.beginPath()
      ctx.arc(ex, ey, 21, 0, Math.PI * 2)
      ctx.lineWidth = 2.5
      ctx.stroke()
      ctx.setLineDash([])
      ctx.restore()
      drawActionTag(ctx, sx, sy - 30, 'BLQ', col)
    }
  }

  if (frame.shot_side) {
    // Baskets are at center width (y=25ft) → px; near top/bottom → py
    const made = frame.shot_made === true
    const color = made ? PALETTE.green : PALETTE.red
    const label = made ? 'CANASTA' : 'FALLO'
    const bx = ORIGIN_X + 25 * COURT_SCALE
    const by = frame.shot_side === 'left'
      ? ORIGIN_Y + 5.25 * COURT_SCALE
      : ORIGIN_Y + (COURT_LEN_FT - 5.25) * COURT_SCALE
    ctx.beginPath()
    ctx.arc(bx, by, 14, 0, Math.PI * 2)
    ctx.strokeStyle = color
    ctx.lineWidth = 3
    ctx.stroke()
    ctx.fillStyle = color
    ctx.font = 'bold 8px "Inter Variable", system-ui, sans-serif'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    ctx.fillText(label, bx + 18, by)
  }
}

// ── Transformación vídeo↔pantalla (object-fit: contain) ─────────────────────
// Devuelve la escala y el offset de letterbox del contenido del vídeo dentro de
// su caja. Reutilizado para hit-testing (ratón) y para dibujar la capa de cajas.
function videoTransform() {
  const vid = videoEl.value
  if (!vid?.videoWidth) return null
  const rect = vid.getBoundingClientRect()
  const scale = Math.min(rect.width / vid.videoWidth, rect.height / vid.videoHeight)
  const ox = (rect.width  - vid.videoWidth  * scale) / 2
  const oy = (rect.height - vid.videoHeight * scale) / 2
  return { rect, scale, ox, oy }
}

// Jugador cuyo bbox contiene el punto de cliente (cx, cy), o null.
function playerAt(cx, cy) {
  const t = videoTransform()
  if (!t || !currentFrame.value) return null
  const nx = (cx - t.rect.left - t.ox) / t.scale
  const ny = (cy - t.rect.top  - t.oy) / t.scale
  for (const p of currentFrame.value.players) {
    if (!p.bbox) continue
    const [x1, y1, x2, y2] = p.bbox
    if (nx >= x1 && nx <= x2 && ny >= y1 && ny <= y2) return p.track_id
  }
  return null
}

function onVideoMouseMove(e) { hoveredTrackId.value = playerAt(e.clientX, e.clientY) }
function onVideoMouseLeave() { hoveredTrackId.value = null }

// Clic: añade/quita al jugador bajo el cursor del conjunto seleccionado
// (selección múltiple aditiva). Clic en vacío limpia toda la selección.
function onVideoClick(e) {
  const id = playerAt(e.clientX, e.clientY)
  if (id === null) {
    if (selectedTrackIds.value.size) selectedTrackIds.value = new Set()
    return
  }
  const next = new Set(selectedTrackIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedTrackIds.value = next
}

// ── Capa de cajas sobre el vídeo ────────────────────────────────────────────
function resizeBoxCanvas() {
  const canvas = boxCanvas.value
  const t = videoTransform()
  if (!canvas || !t) return
  const dpr = window.devicePixelRatio || 1
  const w = Math.round(t.rect.width), h = Math.round(t.rect.height)
  if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
    canvas.width = w * dpr
    canvas.height = h * dpr
  }
}

function strokeBox(ctx, t, bbox, color, lw) {
  const x = t.ox + bbox[0] * t.scale
  const y = t.oy + bbox[1] * t.scale
  const w = (bbox[2] - bbox[0]) * t.scale
  const h = (bbox[3] - bbox[1]) * t.scale
  ctx.strokeStyle = color
  ctx.lineWidth = lw
  ctx.strokeRect(x, y, w, h)
  return { x, y, w, h }
}

function tagBox(ctx, x, y, text, color) {
  ctx.font = 'bold 11px "Inter Variable", system-ui, sans-serif'
  const w = ctx.measureText(text).width + 8
  ctx.fillStyle = color
  ctx.fillRect(x, y - 14, w, 14)
  ctx.fillStyle = PALETTE.white
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, x + 4, y - 7)
}

function vidPt(t, vx, vy) {
  return [t.ox + vx * t.scale, t.oy + vy * t.scale]
}

function drawShot3d(ctx, t, frameIdx) {
  if (!filters.trajectory || !trajectoryOverlay.value) return
  const ov = trajectoryOverlay.value
  const fr = ov.frames[String(frameIdx)]
  if (!fr) return

  if (fr.rim) {
    const [cx, cy, r] = fr.rim
    const [px, py] = vidPt(t, cx, cy)
    ctx.beginPath()
    ctx.arc(px, py, r * t.scale, 0, Math.PI * 2)
    ctx.strokeStyle = PALETTE.gold
    ctx.lineWidth = 2
    ctx.stroke()
  }

  if (fr.arc?.length >= 2) {
    ctx.beginPath()
    for (let i = 0; i < fr.arc.length; i++) {
      const [px, py] = vidPt(t, fr.arc[i][0], fr.arc[i][1])
      if (i === 0) ctx.moveTo(px, py)
      else ctx.lineTo(px, py)
    }
    ctx.strokeStyle = PALETTE.yellow
    ctx.lineWidth = 3
    ctx.lineJoin = 'round'
    ctx.lineCap = 'round'
    ctx.stroke()
  }

  if (fr.end) {
    const [px, py] = vidPt(t, fr.end[0], fr.end[1])
    const endColor = fr.end_reason === 'rim' ? PALETTE.orange : PALETTE.slate
    ctx.beginPath()
    ctx.arc(px, py, 10, 0, Math.PI * 2)
    ctx.strokeStyle = endColor
    ctx.lineWidth = 2
    ctx.stroke()
    ctx.font = '600 11px "Inter Variable", system-ui, sans-serif'
    ctx.fillStyle = endColor
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    ctx.fillText(fr.end_reason === 'rim' ? 'aro' : 'suelo', px + 12, py + 4)
  }

  if (fr.ball_proj) {
    const [px, py] = vidPt(t, fr.ball_proj[0], fr.ball_proj[1])
    ctx.beginPath()
    ctx.arc(px, py, 8, 0, Math.PI * 2)
    ctx.fillStyle = PALETTE.orange
    ctx.fill()
    if (fr.ball_z_m != null) {
      ctx.font = '600 12px "Inter Variable", system-ui, sans-serif'
      ctx.fillStyle = PALETTE.orange
      ctx.fillText(`Z=${fr.ball_z_m} m`, px + 12, py - 8)
    }
  }

  if (fr.ball_meas) {
    const [px, py] = vidPt(t, fr.ball_meas[0], fr.ball_meas[1])
    ctx.beginPath()
    ctx.arc(px, py, 5, 0, Math.PI * 2)
    ctx.strokeStyle = PALETTE.green
    ctx.lineWidth = 2
    ctx.stroke()
  }

  const hud = ov.hud
  if (hud && frameIdx === ov.lo) {
    ctx.font = '600 13px "Inter Variable", system-ui, sans-serif'
    ctx.fillStyle = PALETTE.yellow
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
    const label = hud.apex_m != null
      ? `ápice ${hud.apex_m} m | RMSE ${hud.rmse_px}px`
      : 'trayectoria estimada (2D)'
    ctx.fillText(label, t.ox + 20, t.oy + 20)
  }
}

function drawBoxes() {
  const canvas = boxCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const dpr = window.devicePixelRatio || 1
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, canvas.width / dpr, canvas.height / dpr)

  // Solo dibujamos sobre el vídeo limpio; con el overlay antiguo ya hay cajas
  // horneadas (evita duplicarlas en jobs antiguos).
  if (!usingClean.value) return
  const frame = currentFrame.value
  const t = videoTransform()
  if (!frame || !t) return

  drawShot3d(ctx, t, frame.frame_index ?? frame.index ?? 0)

  const selIds = selectedTrackIds.value
  const hov = hoveredTrackId.value
  const teamOn = (team) =>
    team === 'white' ? filters.home :
    team === 'dark'  ? filters.visitor :
                       (filters.home || filters.visitor)

  // Jugadores
  for (const p of frame.players) {
    if (!p.bbox) continue
    if (!teamOn(p.team)) continue
    const isPoss = p.track_id === frame.possessor_track_id
    if (filters.possessorOnly && !isPoss) continue
    const isSel = selIds.has(p.track_id)
    const isHov = p.track_id === hov
    const color = boxColor(p.team)
    // Atenúa los no seleccionados cuando hay selección activa.
    ctx.globalAlpha = (selIds.size > 0 && !isSel) ? 0.35 : 1
    const lw = isSel ? 3.5 : isHov ? 3 : 2
    const box = strokeBox(ctx, t, p.bbox, isSel ? PALETTE.white : color, lw)
    if (isPoss) strokeBox(ctx, t, [p.bbox[0] - 2, p.bbox[1] - 2, p.bbox[2] + 2, p.bbox[3] + 2], teamColors.ball, 2)
    if (isSel || isHov || isPoss) {
      const pName = trackName(p)
      const pNum = trackNumber(p)
      const label = pName
        ? pName
        : pNum != null ? `#${pNum}` : `${teamPrefix(p.team)}${p.track_id}`
      tagBox(ctx, box.x, box.y, label, isSel ? PALETTE.navyDeep : color)
    }
    ctx.globalAlpha = 1
  }

  // Recuadros especiales para los participantes en la pantalla activa.
  const activeScrV = activeScreenForFrame(frame.frame_index)
  if (activeScrV) {
    const SCOL = { front: PALETTE.teal, back: PALETTE.gold, down: PALETTE.orange }
    const col = SCOL[activeScrV.screen_type] ?? PALETTE.chalk
    const scrP = frame.players.find(p => p.track_id === activeScrV.screener_track && p.bbox)
    const seeP = frame.players.find(p => p.track_id === activeScrV.screenee_track && p.bbox)
    if (scrP) {
      const b = strokeBox(ctx, t, [scrP.bbox[0]-2, scrP.bbox[1]-2, scrP.bbox[2]+2, scrP.bbox[3]+2], col, 3)
      tagBox(ctx, b.x, b.y, 'BLQ', col)
    }
    if (seeP) {
      ctx.save()
      ctx.setLineDash([5, 3])
      strokeBox(ctx, t, [seeP.bbox[0]-2, seeP.bbox[1]-2, seeP.bbox[2]+2, seeP.bbox[3]+2], col, 2.5)
      ctx.setLineDash([])
      ctx.restore()
    }
  }

  if (filters.possessorOnly) return

  // Balón
  if (filters.ball && frame.ball?.bbox) {
    strokeBox(ctx, t, frame.ball.bbox, teamColors.ball, 2.5)
  }
  // Árbitros
  if (filters.referees) {
    for (const r of (frame.referees || [])) strokeBox(ctx, t, r.bbox, teamColors.ref, 2)
  }
  // Aro(s)
  if (filters.rims) {
    for (const r of (frame.rims || [])) strokeBox(ctx, t, r.bbox, teamColors.rim, 2)
  }
}

function togglePlay() {
  if (!videoEl.value) return
  videoEl.value.paused ? videoEl.value.play() : videoEl.value.pause()
}

function seek(delta) {
  if (!videoEl.value) return
  videoEl.value.currentTime = Math.max(0, Math.min(duration.value, videoEl.value.currentTime + delta))
}

function setSpeed(s) {
  playbackRate.value = s
  if (videoEl.value) videoEl.value.playbackRate = s
}
</script>

<style scoped>
/* ── Error banner ── */
.metadata-error-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 1rem;
  margin-bottom: 8px;
  background: rgba(var(--c-rust-rgb), 0.1);
  border: 1px solid rgba(var(--c-rust-rgb), 0.3);
  border-radius: 7px;
  font-size: 12px;
  font-weight: 500;
  color: var(--accent-rust);
  flex-shrink: 0;
}

/* ── Layout raíz ── */
.results-page {
  flex: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  padding: 12px 0 12px 12px;
  gap: 0;
  overflow: hidden;
  min-height: 0;
  min-width: 0;
  background: var(--bg-main);
  position: relative;
}

/* ── Grid principal: dos columnas alineadas arriba ── */
.main-grid {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  column-gap: 8px;
  min-height: 0;
  align-items: stretch;
}

.left-col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  min-width: 0;
}

/* ── Panel derecho colapsable ── */
.map-panel {
  position: relative;
  width: var(--map-panel-w);
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-self: stretch;
  overflow: visible;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.map-panel--collapsed {
  width: 0;
}

.right-col {
  flex: 1;
  width: var(--map-panel-w);
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: opacity 0.2s ease;
}

.map-panel--collapsed .right-col {
  opacity: 0;
  pointer-events: none;
}

/* Cards inside right-col keep full width during animation */
.right-col .map-card {
  min-width: var(--map-panel-w);
}

/* ── Jugadas (bloqueos + futuros tipos) ── */
.screens-card {
  min-width: var(--map-panel-w);
  min-height: 0;
}
.jugadas-header {
  gap: 0.5rem;
}
.play-type-select {
  width: 88px;
  flex-shrink: 0;
  font-family: var(--font-display);
  font-size: var(--text-2xs);
  font-weight: 700;
  letter-spacing: 0.05em;
  background: rgba(255, 255, 255, 0.07);
  color: var(--text-on-navy);
  border: 1px solid rgba(var(--c-gold-rgb), 0.35);
  border-radius: 5px;
  padding: 2px 6px;
  cursor: pointer;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  text-transform: uppercase;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%23fdc500' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round' fill='none'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 6px center;
  padding-right: 20px;
}
.play-type-select:hover {
  background-color: rgba(255, 255, 255, 0.12);
  border-color: rgba(var(--c-gold-rgb), 0.6);
}
.play-type-select option {
  background: var(--c-navy-deep);
  color: var(--text-on-navy);
}
.screens-count {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--c-navy-deep);
  background: rgba(var(--c-gold-rgb), 0.85);
  border-radius: 9px;
  padding: 1px 8px;
  flex-shrink: 0;
}
.screens-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: var(--bg-panel);
  max-height: 210px;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: rgba(var(--c-gold-rgb), 0.4) transparent;
}
.screens-body::-webkit-scrollbar { width: 4px; }
.screens-body::-webkit-scrollbar-track { background: transparent; }
.screens-body::-webkit-scrollbar-thumb {
  background: rgba(var(--c-gold-rgb), 0.4);
  border-radius: 2px;
}
.screens-body::-webkit-scrollbar-thumb:hover {
  background: rgba(var(--c-gold-rgb), 0.7);
}
.screens-empty {
  margin: 0;
  font-size: var(--text-2xs);
  color: var(--text-muted);
  text-align: center;
  padding: 10px 4px;
}
.screen-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  background: var(--c-ink-3);
  border: 1px solid var(--border-mid);
  border-left: 3px solid var(--border-mid);
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  transition: background 0.12s, border-color 0.12s;
}
.screen-row:hover { background: var(--bg-panel); }
.screen-row--active {
  background: rgba(var(--c-gold-rgb), 0.12);
  border-color: rgba(var(--c-gold-rgb), 0.6);
}
.screen-row--front { border-left-color: var(--c-teal); }
.screen-row--back  { border-left-color: var(--c-gold); }
.screen-row--down  { border-left-color: var(--accent-rust); }
.screen-badge {
  font-family: var(--font-display);
  font-size: var(--text-2xs);
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--text-on-navy);
  background: var(--c-navy-deep);
  border-radius: 4px;
  padding: 2px 6px;
  min-width: 46px;
  text-align: center;
}
.screen-row--front .screen-badge { background: rgba(var(--c-teal-rgb), 0.9); color: var(--c-navy-deep); }
.screen-row--back  .screen-badge { background: rgba(var(--c-gold-rgb), 0.9); color: var(--c-navy-deep); }
.screen-row--down  .screen-badge { background: rgba(var(--c-rust-rgb), 0.9); color: #fff; }
.screen-team {
  flex: 1;
  font-size: var(--text-2xs);
  font-weight: 500;
  color: var(--text-on-navy);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.screen-time {
  font-variant-numeric: tabular-nums;
  font-size: var(--text-2xs);
  color: var(--text-muted);
}
.screen-frame {
  font-variant-numeric: tabular-nums;
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--text-muted);
  opacity: 0.65;
}

/* ── Pestaña del drawer (borde izquierdo del panel derecho) ── */
.drawer-tab {
  position: absolute;
  left: -26px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 6;
  pointer-events: auto;
  width: 18px;
  height: 56px;
  background: var(--bg-panel);
  border: 1px solid var(--border-mid);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-on-navy);
  transition: background 0.15s, color 0.15s;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
}
.drawer-tab:hover {
  background: var(--c-ink-3);
  color: rgba(var(--c-white-rgb), 0.85);
}

/* ── Sistema de Cards ── */
.card {
  background: var(--bg-panel);
  border-radius: 10px;
  border: 1px solid var(--border-mid);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 2px 10px rgba(var(--c-navy-deep-rgb), 0.12);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.45rem 0.9rem;
  background: var(--c-navy-deep);
  border-bottom: 2px solid rgba(var(--c-gold-rgb), 0.65);
  flex-shrink: 0;
}

.card-label {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--text-on-navy);
  text-transform: uppercase;
}

.card-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  position: relative;
  background: var(--bg-panel);
}

/* ── Player card (video + playback line + controls, todo en una) ── */
.player-card {
  flex: 1;
  min-height: 0;
}

.video-body {
  background: #050a12;
}

.video-el {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

/* Capa interactiva de cajas: superpuesta exactamente sobre el vídeo, sin
   capturar el ratón (los eventos van al <video> y se hace hit-test en JS). */
.box-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.video-error {
  position: absolute;
  bottom: 0.5rem;
  left: 0;
  right: 0;
  margin: 0 0.75rem;
  padding: 0.5rem 0.75rem;
  background: rgba(var(--c-rust-rgb), 0.12);
  border: 1px solid rgba(var(--c-rust-rgb), 0.3);
  border-radius: 6px;
  color: var(--accent-red);
  font-size: 11px;
}

/* ── Synced indicator (en card-header del video) ── */
.synced-indicator {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: var(--text-2xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  color: rgba(var(--c-white-rgb), 0.55);
  font-family: var(--font-mono);
}
.synced-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(var(--c-gold-rgb), 0.35);
  transition: background 0.3s;
}
.synced-indicator--on { color: var(--text-on-navy); }
.synced-indicator--on .synced-dot {
  background: var(--c-gold);
  box-shadow: 0 0 6px var(--c-gold);
}
/* En pausa: con datos, pero en reposo — oro atenuado, sin halo (no "en directo"). */
.synced-indicator--paused { color: rgba(var(--c-white-rgb), 0.78); }
.synced-indicator--paused .synced-dot { background: rgba(var(--c-gold-rgb), 0.7); }

/* ── Banda 1: scrubber (pegado al vídeo) ── */
.playback-line {
  padding: 0.4rem 1.25rem 0.55rem;
  background: var(--c-bg-pale);
  border-top: 2px solid var(--c-navy-deep);
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  flex-shrink: 0;
}

/* ── Banda 2: transporte (botones centrados, velocidad a la derecha) ── */
.transport-bar {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.5rem 1.25rem;
  background: var(--c-bg-pale);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
.transport-bar .speed-row {
  position: absolute;
  right: 1.25rem;
  top: 50%;
  transform: translateY(-50%);
}

/* ── Banda 3: filtros de capa (banda propia, abajo) ── */
.legend-panel {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  flex-shrink: 0;
  padding: 0.6rem 1.25rem 0.7rem;
  background: var(--c-bg-pale);
  border-top: 1px solid var(--border);
}

.legend-panel-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  justify-content: space-between;
}

.legend-panel-title {
  font-size: var(--text-2xs);
  font-weight: 800;
  letter-spacing: 0.14em;
  color: var(--text-muted);
  text-transform: uppercase;
  white-space: nowrap;
}

.legend-all-row { display: flex; gap: 0.25rem; }

.legend-all-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: var(--text-2xs);
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 0.2rem 0.5rem;
  border-radius: 3px;
  border: 1px solid var(--border-mid);
  background: var(--bg-main);
  color: var(--text-muted);
  cursor: pointer;
  text-transform: uppercase;
  font-family: inherit;
  transition: all 0.15s;
}
.legend-all-btn:hover { background: var(--c-navy-deep); color: var(--c-white); border-color: var(--c-navy-deep); }
.legend-all-btn--off:hover { background: var(--c-red); color: var(--c-white); border-color: var(--c-red); }
.legend-all-btn--on { background: var(--c-gold); color: var(--text-on-gold); border-color: var(--c-gold); }
.legend-all-btn--on:hover { background: var(--c-gold-hover); color: var(--text-on-gold); border-color: var(--c-gold-hover); }

.roster-msg { margin: 0.5rem 0 0; font-size: var(--text-2xs); letter-spacing: 0.02em; }
.roster-msg--err { color: var(--accent-red); }

.legend-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.35rem 1rem;
}

.toggle-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  user-select: none;
  min-width: 0;
}

/* Visualmente oculto pero enfocable por teclado (display:none lo sacaba del
   orden de tabulación). El <label> sigue alternando el estado al hacer clic. */
.toggle-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
.toggle-input:focus-visible + .toggle-switch {
  outline: 2px solid var(--c-gold);
  outline-offset: 2px;
}

.toggle-switch {
  width: 30px;
  height: 17px;
  border-radius: 9px;
  background: var(--c-border);
  position: relative;
  flex-shrink: 0;
  transition: background 0.2s, border-color 0.2s;
  border: 1.5px solid transparent;
}
.toggle-switch::after {
  content: '';
  position: absolute;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: var(--c-white);
  top: 1px;
  left: 1px;
  transition: transform 0.2s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
}
.toggle-input:checked + .toggle-switch::after { transform: translateX(13px); }

.toggle-input:checked + .toggle-switch { background: var(--toggle-color, var(--c-blue)); border-color: var(--toggle-color, var(--c-blue)); }

.toggle-item--disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.toggle-item--disabled .toggle-input {
  cursor: not-allowed;
}

.toggle-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.03em;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 0.25rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Fila de filtro ── */
.legend-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
}
.legend-row .toggle-item { flex: 0 1 auto; min-width: 0; }
.legend-row .toggle-item--switch { flex: 0 0 auto; }
.legend-row .toggle-label { overflow: hidden; text-overflow: ellipsis; }

/* Botón lápiz: abre el color picker nativo */
.color-edit-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  border-radius: 4px;
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.15s, background 0.15s;
  position: relative;
}
.color-edit-btn:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.1);
}
.color-edit-btn input[type="color"] {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}

/* Nombre de equipo editable */
.team-name-input {
  flex: 1 1 auto;
  min-width: 0;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 0.15rem 0.3rem;
  color: var(--text-primary);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.03em;
  font-family: inherit;
  outline: none;
  text-overflow: ellipsis;
  transition: border-color 0.15s, background 0.15s;
}
.team-name-input:hover { border-color: var(--border-mid); }
.team-name-input:focus { border-color: var(--accent-orange); background: var(--bg-main); }


/* Botones de reproducción (más grandes, centrados) */
.playback-btns {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-shrink: 0;
}

.ctrl-btn {
  width: 42px;
  height: 42px;
  background: var(--bg-main);
  border: 1.5px solid var(--c-border);
  border-radius: 9px;
  color: var(--text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
}
.ctrl-btn:hover {
  background: var(--c-navy-deep);
  color: var(--c-white);
  border-color: var(--c-navy-deep);
}

.ctrl-btn--play {
  width: 58px;
  height: 58px;
  background: var(--c-gold);
  border-color: var(--c-gold);
  color: var(--text-on-gold);
  border-radius: 50%;
  margin: 0 0.5rem;
}
.ctrl-btn--play:hover {
  background: var(--c-gold-hover);
  border-color: var(--c-gold-hover);
}

/* Velocidad */
.speed-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
}

.speed-label {
  font-size: var(--text-2xs);
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-right: 0.2rem;
}

.speed-chip {
  padding: 0.25rem 0.55rem;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  background: var(--border);
  color: var(--text-muted);
  border: none;
  cursor: pointer;
  transition: all 0.15s;
}
.speed-chip:hover { background: var(--border-mid); color: var(--text-secondary); }
.speed-chip--active {
  background: var(--c-navy-deep);
  color: var(--text-on-navy);
  font-weight: 700;
  border: 1px solid rgba(var(--c-gold-rgb), 0.4);
}

/* ── Map card ── */
.map-card {
  flex: 1;
  min-height: 0;
  border-radius: 10px 0 0 10px;
  border-right: none;
  box-shadow: -2px 0 10px rgba(var(--c-navy-deep-rgb), 0.08);
}

.canvas-body {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-navy-deep);
}

.court-canvas {
  height: 100%;
  width: auto;
  max-width: 100%;
  display: block;
}

/* ── Frame meta (en barra del reproductor) ── */
.frame-meta {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-variant-numeric: tabular-nums;
  color: var(--text-secondary);
  white-space: nowrap;
}
.frame-meta-label {
  font-size: var(--text-2xs);
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  font-family: var(--font-body);
}
.frame-meta-value {
  font-weight: 700;
  color: var(--text-primary);
}
.frame-meta-sep {
  color: var(--text-muted);
  opacity: 0.5;
}

.timeline-top-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.event-badges {
  display: flex;
  gap: 0.3rem;
  flex-shrink: 0;
}

.event-badge {
  padding: 0.14rem 0.45rem;
  border-radius: 3px;
  font-size: var(--text-2xs);
  font-weight: 700;
  letter-spacing: 0.06em;
  cursor: default;
}
.event-badge--steal   { background: rgba(var(--c-rust-rgb), 0.14);  color: var(--c-rust);   border: 1px solid rgba(var(--c-rust-rgb), 0.3); }
.event-badge--shot    { background: rgba(var(--c-orange-rgb), 0.2); color: var(--c-burnt);  border: 1px solid rgba(var(--c-orange-rgb), 0.45); }
.event-badge--foul    { background: rgba(var(--c-amber-rgb), 0.16); color: var(--c-amber-deep); border: 1px solid rgba(var(--c-amber-rgb), 0.4); }
.event-badge--pass    { background: rgba(var(--c-brown-rgb), 0.1);  color: var(--c-cocoa);  border: 1px solid rgba(var(--c-brown-rgb), 0.25); }
.event-badge--rebound { background: rgba(var(--c-cream-rgb), 0.28); color: var(--c-terracotta); border: 1px solid rgba(var(--c-rust-rgb), 0.3); }

.time-display {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 0.2rem;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-variant-numeric: tabular-nums;
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}
.time-current { color: var(--accent-orange); font-weight: 600; }
.time-sep { color: var(--text-muted); }

.timeline {
  width: 100%;
  cursor: pointer;
  height: 20px;
  -webkit-appearance: none;
  appearance: none;
  background: transparent;
  padding: 7px 0;
}
.timeline::-webkit-slider-runnable-track {
  height: 5px;
  border-radius: 3px;
  background: linear-gradient(
    to right,
    var(--c-blue) 0%,
    var(--c-blue) var(--progress, 0%),
    var(--border-mid) var(--progress, 0%),
    var(--border-mid) 100%
  );
}
.timeline::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--c-blue);
  margin-top: -4.5px;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0,0,0,0.25);
}
.timeline::-moz-range-progress {
  height: 5px;
  border-radius: 3px 0 0 3px;
  background: var(--c-blue);
}
.timeline::-moz-range-track {
  height: 5px;
  background: var(--border-mid);
  border-radius: 3px;
}
.timeline::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--c-blue);
  border: none;
  cursor: pointer;
}

/* ── Annotations card (barra inferior completa) ── */
</style>
