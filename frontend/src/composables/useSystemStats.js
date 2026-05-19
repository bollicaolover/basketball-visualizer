import { ref, watch, onUnmounted } from 'vue'
import { system } from '../services/api.js'
import { STATS_POLL_INTERVAL_MS, STATS_HISTORY_LEN } from '../config/index.js'

/**
 * Sondea las métricas de hardware mientras `visible` sea true y mantiene un
 * pequeño histórico para los sparklines.
 *
 * @param {Ref<boolean>} visible
 */
export function useSystemStats(visible) {
  const hwStats    = ref({ cpu_percent: 0, gpus: [] })
  const cpuHistory = ref([])
  const gpuHistory = ref([])   // array de arrays, uno por GPU
  const cpuCores   = ref(0)

  let timer = null

  async function fetchStats() {
    try {
      const data = await system.stats()
      hwStats.value = data
      if (data.cpu_cores != null) cpuCores.value = data.cpu_cores

      cpuHistory.value = [...cpuHistory.value, data.cpu_percent].slice(-STATS_HISTORY_LEN)

      data.gpus.forEach((g, i) => {
        if (!gpuHistory.value[i]) gpuHistory.value[i] = []
        gpuHistory.value[i] = [...gpuHistory.value[i], g.utilization].slice(-STATS_HISTORY_LEN)
      })
      while (gpuHistory.value.length < data.gpus.length) gpuHistory.value.push([])
    } catch { /* silencioso */ }
  }

  watch(visible, (v) => {
    if (v) {
      fetchStats()
      timer = setInterval(fetchStats, STATS_POLL_INTERVAL_MS)
    } else {
      clearInterval(timer)
      timer = null
    }
  }, { immediate: true })

  onUnmounted(() => clearInterval(timer))

  return { hwStats, cpuHistory, gpuHistory, cpuCores }
}
