import { ref, computed } from 'vue'
import { system } from '../services/api.js'
import { STORAGE_KEYS } from '../config/index.js'

/**
 * Selección de GPUs (persistida en localStorage).
 * Modo "auto": el backend elige la GPU con más memoria libre; en modo manual
 * el usuario marca índices concretos.
 */
export function useGpus() {
  const availableGpus = ref([])
  const selectedGpus  = ref([])
  const showGpuConfig = ref(false)
  const autoGpu       = ref(true)

  const multiGpuSelected = computed(() => selectedGpus.value.length > 1)
  // Parámetro enviado al backend: "auto" o el CSV de índices seleccionados.
  const gpusParam = computed(() =>
    autoGpu.value ? 'auto' : selectedGpus.value.join(','),
  )

  function loadPrefs() {
    try {
      const p = JSON.parse(localStorage.getItem(STORAGE_KEYS.gpuPrefs) ?? '{}')
      if (Array.isArray(p.gpus)) selectedGpus.value = p.gpus
      if (typeof p.auto === 'boolean') autoGpu.value = p.auto
    } catch { /* defaults */ }
  }

  function savePrefs() {
    localStorage.setItem(
      STORAGE_KEYS.gpuPrefs,
      JSON.stringify({ gpus: selectedGpus.value, auto: autoGpu.value }),
    )
  }

  function toggleAuto() {
    autoGpu.value = !autoGpu.value
    savePrefs()
  }

  function toggleGpu(index) {
    const i = selectedGpus.value.indexOf(index)
    if (i >= 0) selectedGpus.value.splice(i, 1)
    else        selectedGpus.value.push(index)
    selectedGpus.value.sort((a, b) => a - b)
    savePrefs()
  }

  async function refresh() {
    availableGpus.value = await system.gpus()
    loadPrefs()
    // Depura la selección contra lo realmente disponible.
    const avail = availableGpus.value.map(g => g.index)
    selectedGpus.value = selectedGpus.value.filter(i => avail.includes(i))
    if (selectedGpus.value.length === 0 && avail.length) selectedGpus.value = [avail[0]]
    savePrefs()
  }

  return {
    availableGpus, selectedGpus, showGpuConfig, autoGpu,
    multiGpuSelected, gpusParam,
    toggleAuto, toggleGpu, refresh,
  }
}
