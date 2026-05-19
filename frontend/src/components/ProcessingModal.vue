<template>
  <Teleport to="body">
    <div class="modal-backdrop" v-if="visible">
      <div class="modal-card">

        <!-- Header -->
        <div class="modal-header">
          <div class="modal-spinner">
            <svg class="spin-svg" viewBox="0 0 44 44" fill="none">
              <circle cx="22" cy="22" r="18" stroke-width="3"/>
              <path d="M22 4a18 18 0 0 1 18 18" stroke-width="3" stroke-linecap="round"/>
            </svg>
          </div>
          <span class="modal-title">PROCESANDO ANÁLISIS IA…</span>
        </div>

        <!-- Body: tasks + hardware -->
        <div class="modal-body">

          <!-- Task list -->
          <div class="panel tasks-panel">
            <span class="panel-label">ESTADO DE TAREAS</span>
            <div class="task-list">
              <div
                v-for="task in tasks"
                :key="task.id"
                class="task-row"
                :class="`task-row--${task.status}`"
              >
                <!-- Icon -->
                <div class="task-icon">
                  <!-- done -->
                  <svg v-if="task.status === 'done'" viewBox="0 0 16 16" fill="none" class="icon-check">
                    <circle cx="8" cy="8" r="7" stroke-width="1.4"/>
                    <path d="M4.5 8l2.5 2.5 4.5-4.5" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  <!-- running -->
                  <svg v-else-if="task.status === 'running'" viewBox="0 0 16 16" fill="none" class="icon-running">
                    <circle cx="8" cy="8" r="7" stroke-width="1.4"/>
                    <path d="M8 1a7 7 0 0 1 7 7" stroke-width="1.8" stroke-linecap="round" class="spin-arc"/>
                  </svg>
                  <!-- pending -->
                  <svg v-else viewBox="0 0 16 16" fill="none" class="icon-pending">
                    <circle cx="8" cy="8" r="7" stroke-width="1.4"/>
                  </svg>
                </div>

                <!-- Label + progress bar for AI task -->
                <div class="task-content">
                  <span class="task-label">{{ task.label }}</span>
                  <template v-if="task.status === 'running' && task.progress !== undefined">
                    <div class="task-progress-row">
                      <div class="task-bar">
                        <div class="task-bar-fill" :style="{ width: task.progress + '%' }"></div>
                      </div>
                      <span class="task-pct">{{ task.progress }}%</span>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </div>

          <!-- Hardware panel -->
          <div class="panel hw-panel">
            <div class="panel-label-row">
              <span class="panel-label">RENDIMIENTO DEL HARDWARE</span>
              <span class="live-badge">
                <span class="live-dot"></span>
                RECURSOS EN TIEMPO REAL
              </span>
            </div>

            <div class="hw-list">
              <!-- GPUs -->
              <div v-for="(gpu, i) in hwStats.gpus" :key="i" class="hw-row">
                <span class="hw-name">
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" class="hw-icon hw-icon--gpu">
                    <rect x="1" y="2" width="8" height="6" rx="1" stroke-width="1.2"/>
                    <path d="M3 2V1M5 2V1M7 2V1M3 8v1M5 8v1M7 8v1" stroke-width="1" stroke-linecap="round"/>
                  </svg>
                  GPU{{ i + 1 }} ({{ gpu.memory_total_gb }}GB)
                </span>
                <div class="hw-bar-wrap">
                  <Sparkline :values="gpuHistory[i] || []" :color="PALETTE.orange" />
                  <div class="hw-bar">
                    <div class="hw-bar-fill hw-bar-fill--blue" :style="{ width: gpu.utilization + '%' }"></div>
                  </div>
                </div>
                <span class="hw-pct hw-pct--gpu">{{ gpu.utilization }}%</span>
              </div>

              <!-- CPU -->
              <div class="hw-row">
                <span class="hw-name">
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" class="hw-icon hw-icon--cpu">
                    <rect x="2" y="2" width="6" height="6" rx="0.5" stroke-width="1.2"/>
                    <rect class="hw-icon-core" x="3.5" y="3.5" width="3" height="3"/>
                  </svg>
                  CPU ({{ cpuCores > 0 ? cpuCores + ' núcleos' : 'CPU' }})
                </span>
                <div class="hw-bar-wrap">
                  <Sparkline :values="cpuHistory" :color="PALETTE.teal" />
                  <div class="hw-bar">
                    <div class="hw-bar-fill hw-bar-fill--purple" :style="{ width: hwStats.cpu_percent + '%' }"></div>
                  </div>
                </div>
                <span class="hw-pct hw-pct--cpu">{{ hwStats.cpu_percent }}%</span>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { toRef } from 'vue'
import Sparkline from './Sparkline.js'
import { useSystemStats } from '../composables/useSystemStats.js'
import { PALETTE } from '../config/palette.js'

const props = defineProps({
  visible:  Boolean,
  tasks:    { type: Array, default: () => [] },
  progress: { type: Number, default: 0 },
})

const { hwStats, cpuHistory, gpuHistory, cpuCores } = useSystemStats(toRef(props, 'visible'))
</script>

<style scoped>
/* ── Overlay ── */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(var(--c-navy-deep-rgb), 0.55);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-card {
  width: min(780px, 96vw);
  background: var(--c-ink-1);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 28px 70px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(var(--c-gold-rgb), 0.22);
}

/* ── Header ── */
.modal-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.1rem 1.4rem;
  background: var(--c-navy-deep);
  border-bottom: 1px solid rgba(var(--c-gold-rgb), 0.4);
}

.modal-spinner {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
}

.spin-svg {
  width: 100%;
  height: 100%;
  animation: spin 1s linear infinite;
}
.spin-svg circle { stroke: rgba(var(--c-gold-rgb), 0.25); }
.spin-svg path   { stroke: var(--c-gold); }

.modal-title {
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--text-on-navy);
  text-transform: uppercase;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Body ── */
.modal-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
}

.panel {
  padding: 1.1rem 1.25rem;
}

.tasks-panel {
  border-right: 1px solid var(--border);
}

.panel-label {
  display: block;
  font-size: var(--text-2xs);
  font-weight: 700;
  letter-spacing: 0.14em;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 0.9rem;
}

.panel-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.9rem;
}

.live-badge {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: var(--text-2xs);
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--text-muted);
}

.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-gold);
  animation: pulse-dot 1.4s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.3; }
}

/* ── Task list ── */
.task-list {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.task-row {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
}

.task-icon {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  margin-top: 1px;
}

.task-icon svg { width: 16px; height: 16px; }

/* Iconos de estado de tarea */
.icon-check circle { fill: rgba(var(--c-gold-rgb), 0.16); stroke: var(--c-gold); }
.icon-check path   { stroke: var(--c-gold); }
.icon-running circle { stroke: rgba(var(--c-blue-rgb), 0.3); }
.icon-running path   { stroke: var(--c-blue); }
.icon-pending circle { stroke: rgba(var(--c-white-rgb), 0.2); }

.spin-arc {
  transform-origin: 8px 8px;
  animation: spin 0.9s linear infinite;
}

.task-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.task-label {
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: 0.02em;
  line-height: 1.3;
}

.task-row--done    .task-label { color: var(--text-secondary); }
.task-row--running .task-label { color: var(--c-blue-hover); font-weight: 600; }
.task-row--pending .task-label { color: var(--text-muted); }

.task-progress-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.task-bar {
  flex: 1;
  height: 5px;
  background: rgba(var(--c-blue-rgb), 0.15);
  border-radius: 3px;
  overflow: hidden;
}

.task-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--c-blue), var(--c-gold));
  border-radius: 3px;
  transition: width 0.6s ease;
  box-shadow: 0 0 6px rgba(var(--c-gold-rgb), 0.5);
}

.task-pct {
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--text-on-navy);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  min-width: 28px;
}

/* ── Hardware panel ── */
.hw-panel { background: var(--c-ink-2); }

.hw-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.hw-row {
  display: grid;
  grid-template-columns: 110px 1fr 36px;
  align-items: center;
  gap: 0.5rem;
}

.hw-name {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hw-icon { flex-shrink: 0; }
.hw-icon--gpu rect,
.hw-icon--gpu path { stroke: var(--c-gold); }
.hw-icon--cpu rect { stroke: var(--c-teal); }
.hw-icon--cpu .hw-icon-core { fill: rgba(var(--c-teal-rgb), 0.4); stroke: none; }

.hw-bar-wrap {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

:deep(.sparkline) { flex-shrink: 0; }

.hw-bar {
  flex: 1;
  height: 6px;
  background: rgba(var(--c-white-rgb), 0.07);
  border-radius: 3px;
  overflow: hidden;
}

.hw-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.8s ease;
}

.hw-bar-fill--orange { background: linear-gradient(90deg, var(--c-navy), var(--c-gold)); box-shadow: 0 0 6px rgba(var(--c-gold-rgb), 0.4); }
.hw-bar-fill--blue   { background: linear-gradient(90deg, var(--c-orange-hover), var(--c-orange)); box-shadow: 0 0 6px rgba(var(--c-orange-rgb), 0.4); }
.hw-bar-fill--purple { background: linear-gradient(90deg, var(--c-teal-hover), var(--c-teal)); box-shadow: 0 0 6px rgba(var(--c-teal-rgb), 0.4); }

.hw-pct {
  font-size: var(--text-2xs);
  font-weight: 700;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.hw-pct--gpu { color: var(--text-on-navy); }
.hw-pct--cpu { color: var(--c-teal); }
</style>
