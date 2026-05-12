import { ref } from 'vue'
import { testVideos as testVideosApi } from '../services/api.js'

/** Nombre legible de un vídeo de prueba: "Q1 · 1:23 – 1:45". */
export function prettifyTestVideo(name) {
  const base = name.replace(/\.mp4$/, '')
  const m = base.match(/-(q\d+)-(\d+\.\d+)-(\d+\.\d+)$/)
  if (!m) return base
  const q = m[1].toUpperCase()
  const t1 = m[2].replace('.', ':')
  const t2 = m[3].replace('.', ':')
  return `${q} · ${t1} – ${t2}`
}

/** Catálogo de vídeos de prueba disponibles en el servidor. */
export function useTestVideos() {
  const testVideos     = ref([])
  const showTestVideos = ref(true)

  async function refresh() {
    testVideos.value = await testVideosApi.list()
  }

  return { testVideos, showTestVideos, refresh }
}
