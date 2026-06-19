import { ref } from 'vue'
import { STORAGE_KEYS } from '../config/index.js'

const VALID = new Set(['sam', 'botsort'])

function loadStored() {
  const raw = localStorage.getItem(STORAGE_KEYS.trackerMode)
  return VALID.has(raw) ? raw : 'sam'
}

/**
 * Backend de tracking seleccionado en el sidebar (`sam` | `botsort`).
 */
export function useTrackerMode() {
  const trackerMode = ref(loadStored())

  function setTrackerMode(mode) {
    if (!VALID.has(mode)) return
    trackerMode.value = mode
    localStorage.setItem(STORAGE_KEYS.trackerMode, mode)
  }

  return { trackerMode, setTrackerMode }
}
