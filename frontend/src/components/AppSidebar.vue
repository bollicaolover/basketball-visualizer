<template>
  <aside class="sidebar" :class="{ 'sidebar--collapsed': collapsed }">

    <!-- Brand -->
    <div class="sidebar-brand">
      <span class="brand-name" :class="{ 'brand-name--hidden': collapsed }">TFG</span>
      <button class="collapse-btn" :title="collapsed ? 'Expandir sidebar' : 'Colapsar sidebar'" @click="toggleCollapse">
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <path :d="collapsed ? 'M6 3l5 5-5 5' : 'M10 3l-5 5 5 5'" />
        </svg>
      </button>
    </div>

    <!-- Clips de ejemplo · vía principal de análisis -->
    <div v-if="testVideos.testVideos.value.length && !collapsed" class="sidebar-section sidebar-section--primary">
      <div class="tv-header" @click="testVideos.showTestVideos.value = !testVideos.showTestVideos.value">
        <span class="s-section-label s-section-label--accent">CLIPS DE EJEMPLO</span>
        <svg class="tv-caret" :class="{ 'tv-caret--open': testVideos.showTestVideos.value }" width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6">
          <path d="M4 6l4 4 4-4"/>
        </svg>
      </div>
      <p class="tv-hint">Celtics vs Knicks · roster aplicado automáticamente</p>
      <div v-if="testVideos.showTestVideos.value" class="tv-list">
        <button
          v-for="tv in testVideos.testVideos.value"
          :key="tv.name"
          class="tv-item"
          :disabled="!!upload.processingTestVideo.value"
          @click="upload.processTestVideo(tv)"
        >
          <svg width="11" height="11" viewBox="0 0 16 16" fill="none" class="tv-icon">
            <polygon points="4,2 13,8 4,14" fill="currentColor"/>
          </svg>
          <span class="tv-label">{{ prettifyTestVideo(tv.name) }}</span>
          <span v-if="upload.processingTestVideo.value === tv.name" class="tv-spinner"></span>
          <span v-else class="tv-size">{{ formatSize(tv.size) }}</span>
        </button>
      </div>
    </div>

    <!-- Subir tu propio vídeo · vía secundaria -->
    <div v-show="!collapsed" class="sidebar-section">
      <span class="s-section-label">O SUBE TU VÍDEO</span>

      <div
        class="dropzone"
        :class="{ 'dropzone--over': upload.isDragging.value, 'dropzone--file': upload.selectedFile.value }"
        @dragover.prevent="upload.isDragging.value = true"
        @dragleave="upload.isDragging.value = false"
        @drop.prevent="upload.onDrop"
        @click="fileInput.click()"
      >
        <input ref="fileInput" type="file" accept=".mp4,video/mp4" hidden @change="upload.onFileChange" />
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4">
          <path d="M10 13V4M10 4L7 7M10 4l3 3"/>
          <path d="M3 14v1a2 2 0 002 2h10a2 2 0 002-2v-1"/>
        </svg>
        <div class="dz-text">
          <span class="dz-title">{{ upload.selectedFile.value ? upload.selectedFile.value.name : 'ARRASTRA AQUÍ' }}</span>
          <span class="dz-sub">{{ upload.selectedFile.value ? formatSize(upload.selectedFile.value.size) : 'VÍDEO MP4' }}</span>
        </div>
      </div>

      <!-- Roster (JSON, opcional): nombres de jugadores + colores de equipo -->
      <div class="roster-pick">
        <input ref="rosterInput" type="file" accept=".json,application/json" hidden @change="upload.onRosterChange" />
        <button class="roster-btn" type="button" @click="rosterInput.click()">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2 4h12M2 8h12M2 12h7"/>
          </svg>
          <span class="roster-btn-text">{{ upload.rosterFile.value ? upload.rosterFile.value.name : 'Roster JSON · opcional' }}</span>
        </button>
        <button v-if="upload.rosterFile.value" class="roster-clear" type="button" title="Quitar roster" @click="upload.clearRoster">✕</button>
      </div>

      <!-- GPU configuration -->
      <div v-if="gpus.availableGpus.value.length" class="gpu-config">
        <button class="gpu-toggle" type="button" @click="gpus.showGpuConfig.value = !gpus.showGpuConfig.value">
          <svg class="gpu-chip-ico" width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4">
            <rect x="2" y="2" width="12" height="12" rx="1.5"/>
            <rect x="5" y="5" width="6" height="6" rx="0.5"/>
          </svg>
          <span class="gpu-toggle-label">GPU · {{ gpus.autoGpu.value ? 'Auto' : `${gpus.selectedGpus.value.length}/${gpus.availableGpus.value.length}` }}</span>
          <svg class="gpu-caret" :class="{ 'gpu-caret--open': gpus.showGpuConfig.value }" width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6">
            <path d="M4 6l4 4 4-4"/>
          </svg>
        </button>

        <div v-if="gpus.showGpuConfig.value" class="gpu-panel">
          <label class="gpu-item gpu-item--auto">
            <input type="checkbox" :checked="gpus.autoGpu.value" @change="gpus.toggleAuto" />
            <span class="gpu-name">Auto · GPU con más memoria libre</span>
          </label>

          <div class="gpu-list" :class="{ 'gpu-list--disabled': gpus.autoGpu.value }">
            <label v-for="g in gpus.availableGpus.value" :key="g.index" class="gpu-item">
              <input
                type="checkbox"
                :disabled="gpus.autoGpu.value"
                :checked="gpus.selectedGpus.value.includes(g.index)"
                @change="gpus.toggleGpu(g.index)"
              />
              <span class="gpu-name">GPU{{ g.index }} · {{ g.name }}</span>
              <span class="gpu-mem">{{ g.memory_total_gb }}GB</span>
            </label>
          </div>

          <p v-if="!gpus.autoGpu.value && gpus.multiGpuSelected.value" class="gpu-warn">
            Con varias GPUs el vídeo se reparte en trozos: más rápido, pero la
            identidad de los jugadores puede reiniciarse en las fronteras.
          </p>
        </div>
      </div>

      <button
        class="upload-btn"
        :class="{ 'upload-btn--ready': upload.selectedFile.value && !upload.uploading.value }"
        :disabled="!upload.selectedFile.value || upload.uploading.value"
        @click="upload.upload"
      >
        <svg width="12" height="12" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10 13V4M10 4L7 7M10 4l3 3"/>
          <path d="M3 14v1a2 2 0 002 2h10a2 2 0 002-2v-1"/>
        </svg>
        {{ upload.uploading.value ? 'SUBIENDO…' : 'SUBIR VÍDEO' }}
      </button>

      <div v-if="upload.uploadJobId.value && upload.jobStatus.value" class="status-block">
        <div class="status-pill" :class="`status-pill--${upload.jobStatus.value}`">
          <span class="status-dot"></span>
          {{ upload.statusLabel.value }}
        </div>
        <div v-if="upload.jobStatus.value === 'processing'" class="progress-track">
          <div class="progress-fill"></div>
        </div>
        <p v-if="upload.jobStatus.value === 'error'" class="error-text">{{ upload.errorMsg.value }}</p>
      </div>
    </div>

    <!-- Historial -->
    <div v-show="!collapsed" class="sidebar-section sidebar-section--grow">
      <span class="s-section-label">HISTORIAL</span>
      <div class="recent-list">
        <template v-for="group in recent.grouped.value" :key="group.label">
          <span class="recent-group-label">{{ group.label }}</span>
          <div
            v-for="item in group.items"
            :key="item.jobId"
            class="recent-item"
            :class="{ 'recent-item--active': item.jobId === activeJobId, 'recent-item--editing': recent.editingJobId.value === item.jobId }"
            @click="recent.editingJobId.value !== item.jobId && emit('open-job', item.jobId)"
          >
            <svg width="11" height="11" viewBox="0 0 14 14" fill="currentColor" class="recent-icon">
              <path d="M1 1h8l4 4v8H1V1z" opacity="0.6"/>
            </svg>
            <input
              v-if="recent.editingJobId.value === item.jobId"
              class="recent-rename-input"
              v-model="recent.editingLabel.value"
              @keydown.enter.prevent="recent.commitRename"
              @keydown.escape.prevent="recent.cancelRename"
              @blur="recent.commitRename"
              @click.stop
            />
            <span
              v-else
              class="recent-label"
              @dblclick.stop="recent.startRename(item)"
            >{{ item.label }}</span>
            <button
              v-if="recent.editingJobId.value !== item.jobId"
              class="rename-btn"
              title="Renombrar"
              @click.stop="recent.startRename(item)"
            >
              <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M11 2l3 3-9 9H2v-3L11 2z"/>
              </svg>
            </button>
          </div>
        </template>
        <div v-if="recent.recentAnalyses.value.length === 0" class="recent-empty">
          Sin análisis recientes
        </div>
      </div>
    </div>

    <!-- Modal de procesamiento (teleport a body) -->
    <ProcessingModal
      :visible="upload.showProcessingModal.value"
      :tasks="upload.jobTasks.value"
      :progress="upload.jobProgress.value"
    />
  </aside>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import ProcessingModal from './ProcessingModal.vue'
import { useGpus } from '../composables/useGpus.js'
import { useTestVideos, prettifyTestVideo } from '../composables/useTestVideos.js'
import { useRecentAnalyses } from '../composables/useRecentAnalyses.js'
import { useUploadJob } from '../composables/useUploadJob.js'
import { formatSize } from '../utils/format.js'
import { STORAGE_KEYS } from '../config/index.js'

defineProps({
  activeJobId: { type: String, default: null },
})
const emit = defineEmits(['logout', 'open-job'])

const fileInput = ref(null)
const rosterInput = ref(null)

// ── Colapsado (persistido) ──────────────────────────────────────────────────
const collapsed = ref(localStorage.getItem(STORAGE_KEYS.sidebarCollapsed) === 'true')
function toggleCollapse() {
  collapsed.value = !collapsed.value
  localStorage.setItem(STORAGE_KEYS.sidebarCollapsed, String(collapsed.value))
}

// ── Composables de estado ───────────────────────────────────────────────────
const gpus       = useGpus()
const testVideos = useTestVideos()
const recent     = useRecentAnalyses()
const upload     = useUploadJob({
  gpusParam: gpus.gpusParam,
  onRecent: recent.add,
  onDone: (jobId) => emit('open-job', jobId),
})

onMounted(() => {
  gpus.refresh()
  testVideos.refresh()
})
</script>

<style>
/* Scrollbar oculta: los pseudo-elementos webkit no funcionan en <style scoped>. */
.sidebar,
.sidebar .tv-list {
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.sidebar::-webkit-scrollbar,
.sidebar .tv-list::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
  background: transparent;
}
</style>

<style scoped>
.sidebar {
  width: 260px;
  height: 100%;
  min-width: 0;
  min-height: 0;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  z-index: 20;
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}
.sidebar--collapsed {
  width: 48px;
  overflow: hidden;
}

.sidebar-brand {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-height: 52px;
  padding: 0.65rem 0.75rem;
  background: var(--c-navy-deep);
  border-bottom: 2px solid rgba(var(--c-gold-rgb), 0.65);
  flex-shrink: 0;
}

.brand-mark circle,
.brand-mark path { stroke: var(--accent-orange); }

.brand-actions {
  display: flex;
  align-items: center;
  margin-left: auto;
}

.collapse-btn {
  position: relative;
  z-index: 1;
  flex-shrink: 0;
  background: none;
  border: none;
  color: rgba(var(--c-white-rgb), 0.55);
  cursor: pointer;
  padding: 0.2rem;
  border-radius: 4px;
  display: flex;
  align-items: center;
  transition: color 0.15s, background 0.15s;
  margin-left: auto;
}
.collapse-btn:hover {
  color: var(--c-white);
  background: rgba(var(--c-white-rgb), 0.1);
}
.sidebar--collapsed .sidebar-brand {
  justify-content: center;
  padding: 0.65rem 0;
}
.sidebar--collapsed .collapse-btn {
  margin-left: 0;
}

.brand-name {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--text-on-navy);
  text-transform: uppercase;
  white-space: nowrap;
  line-height: 1;
  opacity: 1;
  transition: opacity 0.15s ease;
  pointer-events: none;
}
.brand-name--hidden {
  opacity: 0;
}
.brand-name strong {
  font-weight: 700;
  color: var(--text-on-navy);
  letter-spacing: 0.08em;
}

/* ── Sidebar sections ── */
.sidebar-section {
  padding: 0.85rem 0.85rem 0.9rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.sidebar-section--grow {
  flex: 1;
  border-bottom: none;
}
/* Vía principal (clips de ejemplo): acento dorado a la izquierda, como la
   barra de marca. El oro marca "lo destacado" en toda la app. */
.sidebar-section--primary {
  flex-shrink: 0;
  border-left: 2px solid rgba(var(--c-gold-rgb), 0.55);
  padding-left: calc(0.85rem - 2px);
}

.s-section-label {
  font-size: var(--text-2xs);
  font-weight: 800;
  letter-spacing: 0.14em;
  color: var(--text-secondary);
  text-transform: uppercase;
}
.s-section-label--accent { color: var(--c-gold); }

/* ── Roster (JSON opcional) ── */
.roster-pick {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.roster-btn {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: var(--bg-card);
  border: 1px solid var(--border-mid);
  border-radius: 6px;
  padding: 0.45rem 0.55rem;
  color: var(--text-secondary);
  font-size: 10.5px;
  font-family: inherit;
  letter-spacing: 0.02em;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}
.roster-btn:hover { border-color: var(--accent-orange); color: var(--text-primary); }
.roster-btn-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.roster-clear {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border: 1px solid var(--border-mid);
  border-radius: 6px;
  background: var(--bg-card);
  color: var(--text-muted);
  cursor: pointer;
  font-size: 11px;
}
.roster-clear:hover { background: var(--c-red); color: var(--c-white); border-color: var(--c-red); }

/* ── Upload button ── */
.upload-btn {
  width: 100%;
  padding: 0.6rem;
  background: transparent;
  border: 1px solid var(--border-mid);
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.07em;
  cursor: default;
  transition: background 0.2s, border-color 0.2s, color 0.2s, box-shadow 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
}
.upload-btn--ready {
  background: var(--accent-orange);
  border-color: var(--accent-orange);
  color: var(--text-on-accent);
  cursor: pointer;
  box-shadow: 0 0 16px rgba(var(--c-blue-rgb), 0.45);
}
.upload-btn--ready:hover {
  background: var(--accent-orange-hover);
  border-color: var(--accent-orange-hover);
  box-shadow: 0 0 22px rgba(var(--c-blue-rgb), 0.6);
}

/* ── GPU config ── */
.gpu-config {
  margin: 0.5rem 0;
}
.gpu-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.55rem;
  background: var(--bg-card);
  border: 1px solid var(--border-mid);
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
}
.gpu-toggle:hover { border-color: var(--accent-blue); color: var(--text-primary); }
.gpu-chip-ico { flex-shrink: 0; }
.gpu-toggle-label { flex: 1; text-align: left; }
.gpu-caret { transition: transform 0.2s; flex-shrink: 0; }
.gpu-caret--open { transform: rotate(180deg); }

.gpu-panel {
  margin-top: 0.4rem;
  padding: 0.5rem 0.55rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.gpu-item {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 10.5px;
  color: var(--text-muted);
  cursor: pointer;
}
.gpu-item input { accent-color: var(--accent-orange); cursor: pointer; }
.gpu-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gpu-mem { color: var(--text-muted); opacity: 0.7; flex-shrink: 0; }

.gpu-item--auto {
  color: var(--text-secondary);
  font-weight: 600;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--border);
}
.gpu-list { display: flex; flex-direction: column; gap: 0.4rem; }
.gpu-list--disabled { opacity: 0.4; pointer-events: none; }

.gpu-warn {
  font-size: var(--text-2xs);
  line-height: 1.4;
  color: var(--accent-rust);
  opacity: 0.9;
}

/* ── Dropzone ── */
.dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.9rem 0.5rem;
  border: 1.5px dashed var(--border-mid);
  border-radius: 7px;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  background: var(--bg-card);
  text-align: center;
  color: var(--text-muted);
}
.dropzone:hover,
.dropzone--over { border-color: var(--accent-rust); background: rgba(var(--c-rust-rgb), 0.06); }
.dropzone--file { border-color: var(--accent-orange); border-style: solid; }

.dz-text { display: flex; flex-direction: column; gap: 0.15rem; }
.dz-title {
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  word-break: break-all;
  line-height: 1.3;
}
.dz-sub {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  letter-spacing: 0.04em;
}

/* ── Status ── */
.status-block {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.status-pill {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.65rem;
  border-radius: 20px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
.status-pill--pending    { background: rgba(var(--c-amber-rgb), 0.14); color: var(--accent-yellow); }
.status-pill--processing { background: rgba(var(--c-blue-rgb), 0.16);  color: var(--c-blue-hover); }
.status-pill--done        { background: rgba(var(--c-green-rgb), 0.16); color: var(--accent-green); }
.status-pill--error      { background: rgba(var(--c-rust-rgb), 0.14); color: var(--accent-rust); }

.progress-track {
  height: 3px;
  background: var(--border-mid);
  border-radius: 2px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  width: 40%;
  background: var(--accent-green);
  animation: slide 1.6s ease-in-out infinite alternate;
}
@keyframes slide {
  from { transform: translateX(-100%); }
  to   { transform: translateX(350%); }
}

.error-text {
  font-size: var(--text-2xs);
  font-family: var(--font-mono);
  color: var(--accent-red);
  word-break: break-word;
}

/* ── Historial ── */
.recent-list {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.recent-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.45rem 0.55rem;
  background: none;
  border: none;
  border-radius: 5px;
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.02em;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
  overflow: hidden;
  box-sizing: border-box;
}
.recent-item:hover { background: var(--border); color: var(--text-primary); }
.recent-item:hover .rename-btn { opacity: 1; }
.recent-item--active { background: var(--c-navy-deep); color: var(--text-on-navy); font-weight: 600; }
.recent-item--editing { cursor: default; background: var(--border); }

.rename-btn {
  flex-shrink: 0;
  margin-left: auto;
  opacity: 0;
  background: none;
  border: none;
  padding: 0.1rem 0.2rem;
  color: inherit;
  cursor: pointer;
  border-radius: 3px;
  transition: opacity 0.12s, background 0.12s;
  display: flex;
  align-items: center;
}
.rename-btn:hover { background: var(--border-mid); }

.recent-rename-input {
  flex: 1;
  min-width: 0;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.02em;
  padding: 0;
}

.recent-group-label {
  display: block;
  font-size: var(--text-2xs);
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  text-transform: uppercase;
  padding: 0.5rem 0.3rem 0.15rem;
  margin-top: 0.2rem;
}
.recent-icon { flex-shrink: 0; opacity: 0.5; }

.recent-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-empty {
  font-size: 10.5px;
  color: var(--text-muted);
  text-align: center;
  padding: 0.5rem 0;
  font-style: italic;
}

/* ── Vídeos de prueba ── */
.tv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
}
.tv-caret { transition: transform 0.2s; flex-shrink: 0; color: var(--text-muted); }
.tv-caret--open { transform: rotate(180deg); }

.tv-hint {
  font-size: var(--text-2xs);
  line-height: 1.35;
  letter-spacing: 0.02em;
  color: var(--text-muted);
  margin: -0.15rem 0 0.05rem;
}

.tv-list {
  display: flex;
  flex-direction: column;
  gap: 0.12rem;
  max-height: 222px;
  overflow-y: auto;
  overflow-x: hidden;
}

.tv-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.42rem 0.5rem;
  background: none;
  border: none;
  border-radius: 5px;
  color: var(--text-secondary);
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: 0.02em;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
  overflow: hidden;
  flex-shrink: 0;
}
.tv-item:hover:not(:disabled) { background: var(--border); color: var(--text-primary); }
.tv-item:disabled { opacity: 0.45; cursor: default; }

.tv-icon { flex-shrink: 0; color: var(--accent-orange); }
.tv-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tv-size {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  opacity: 0.6;
  flex-shrink: 0;
  font-family: var(--font-mono);
}

.tv-spinner {
  flex-shrink: 0;
  width: 9px;
  height: 9px;
  border: 1.5px solid rgba(var(--c-orange-rgb), 0.3);
  border-top-color: var(--accent-orange);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
