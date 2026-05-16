import { ref, computed, nextTick } from 'vue'
import { STORAGE_KEYS, RECENT_MAX } from '../config/index.js'

/**
 * Historial de análisis recientes (persistido en localStorage).
 * Soporta renombrado en línea y agrupación por antigüedad.
 */
export function useRecentAnalyses() {
  const recentAnalyses = ref(load())
  const editingJobId   = ref(null)
  const editingLabel   = ref('')

  function load() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEYS.recentAnalyses) ?? '[]')
    } catch {
      return []
    }
  }

  function save() {
    localStorage.setItem(STORAGE_KEYS.recentAnalyses, JSON.stringify(recentAnalyses.value))
  }

  function add(jobId, label) {
    recentAnalyses.value = recentAnalyses.value.filter(r => r.jobId !== jobId)
    recentAnalyses.value.unshift({ jobId, label, createdAt: Date.now() })
    if (recentAnalyses.value.length > RECENT_MAX) recentAnalyses.value.splice(RECENT_MAX)
    save()
  }

  const grouped = computed(() => {
    const now = Date.now()
    const DAY = 86_400_000
    const groups = [
      { label: 'Hoy',             items: [], cutoff: now - DAY },
      { label: 'Últimos 7 días',  items: [], cutoff: now - 7 * DAY },
      { label: 'Últimos 30 días', items: [], cutoff: now - 30 * DAY },
      { label: 'Más antiguo',     items: [], cutoff: -Infinity },
    ]
    for (const item of recentAnalyses.value) {
      const ts = item.createdAt ?? 0
      const g = groups.find(g => ts > g.cutoff) ?? groups[groups.length - 1]
      g.items.push(item)
    }
    return groups.filter(g => g.items.length > 0)
  })

  function startRename(item) {
    editingJobId.value = item.jobId
    editingLabel.value = item.label
    nextTick(() => document.querySelector('.recent-rename-input')?.select())
  }

  function commitRename() {
    if (!editingJobId.value) return
    const trimmed = editingLabel.value.trim()
    if (trimmed) {
      const item = recentAnalyses.value.find(r => r.jobId === editingJobId.value)
      if (item) item.label = trimmed
      save()
    }
    editingJobId.value = null
    editingLabel.value = ''
  }

  function cancelRename() {
    editingJobId.value = null
    editingLabel.value = ''
  }

  return {
    recentAnalyses, grouped,
    editingJobId, editingLabel,
    add, startRename, commitRename, cancelRename,
  }
}
