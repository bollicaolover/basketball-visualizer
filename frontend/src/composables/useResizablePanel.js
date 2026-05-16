import { ref, onUnmounted } from 'vue'
import { STORAGE_KEYS } from '../config/index.js'

/**
 * Anchura arrastrable de la columna derecha (persistida).
 * Devuelve la anchura reactiva, el flag de arrastre y el manejador mousedown.
 *
 * @param {Object} opts
 * @param {number} opts.initial  anchura inicial por defecto.
 * @param {number} opts.min      mínimo en px.
 * @param {number} opts.max      máximo en px.
 */
export function useResizablePanel({ initial = 380, min = 240, max = 580 } = {}) {
  const saved = (() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEYS.panelSizes) ?? '{}') }
    catch { return {} }
  })()

  const width    = ref(saved.rightCol ?? initial)
  const dragging = ref(false)
  let drag = null

  function onMove(e) {
    if (!drag) return
    width.value = Math.max(min, Math.min(max, drag.startVal - (e.clientX - drag.startX)))
  }

  function onEnd() {
    dragging.value = false
    drag = null
    document.body.style.cursor = document.body.style.userSelect = ''
    localStorage.setItem(STORAGE_KEYS.panelSizes, JSON.stringify({ rightCol: width.value }))
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onEnd)
  }

  function startDrag(e) {
    e.preventDefault()
    dragging.value = true
    drag = { startX: e.clientX, startVal: width.value }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onEnd)
  }

  onUnmounted(() => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onEnd)
  })

  return { width, dragging, startDrag }
}
