import { ref, computed, onUnmounted } from 'vue'
import { jobs, testVideos as testVideosApi } from '../services/api.js'
import { JOB_POLL_INTERVAL_MS } from '../config/index.js'
import { labelFromFile } from '../utils/format.js'
import { prettifyTestVideo } from './useTestVideos.js'

const STATUS_LABELS = {
  pending:    'En cola…',
  processing: 'Procesando con IA…',
  done:       '¡Listo!',
  error:      'Error en el procesamiento',
}

/**
 * Subida de vídeo + lanzamiento del pipeline + sondeo del estado.
 *
 * @param {Object}   deps
 * @param {Ref<string>}   deps.gpusParam  "auto" o CSV de índices.
 * @param {Ref<string>}   deps.team1
 * @param {Ref<string>}   deps.team2
 * @param {Ref<string>}   deps.trackerMode  "sam" | "botsort".
 * @param {(jobId, label) => void} deps.onRecent  registra el análisis.
 * @param {(jobId) => void}        deps.onDone    se llama al completarse.
 */
export function useUploadJob({ gpusParam, team1, team2, trackerMode, onRecent, onDone }) {
  const selectedFile = ref(null)
  const rosterFile   = ref(null)   // roster JSON opcional (nombres + colores)
  const isDragging   = ref(false)
  const uploading    = ref(false)
  const uploadJobId  = ref(null)
  const jobStatus    = ref(null)
  const jobTasks     = ref([])
  const jobProgress  = ref(0)
  const errorMsg     = ref('')
  const processingTestVideo = ref(null)   // nombre del vídeo de prueba en proceso

  let pollTimer = null

  const statusLabel = computed(() => STATUS_LABELS[jobStatus.value] ?? jobStatus.value)

  const showProcessingModal = computed(() =>
    !!uploadJobId.value && (jobStatus.value === 'pending' || jobStatus.value === 'processing'),
  )

  const baseParams = () => ({
    gpus:        gpusParam.value,
    memFraction: 1.0,
    team1:       team1?.value?.trim() ?? '',
    team2:       team2?.value?.trim() ?? '',
    tracker:     trackerMode?.value ?? 'sam',
  })

  function resetJobState() {
    clearInterval(pollTimer)
    jobStatus.value   = null
    uploadJobId.value = null
    jobTasks.value    = []
    jobProgress.value = 0
  }

  function startPolling(label) {
    pollTimer = setInterval(() => pollStatus(label), JOB_POLL_INTERVAL_MS)
  }

  async function pollStatus(label) {
    try {
      const data = await jobs.status(uploadJobId.value)
      jobStatus.value = data.status
      if (data.tasks) jobTasks.value = data.tasks
      if (data.progress !== undefined) jobProgress.value = data.progress
      if (data.status === 'done') {
        clearInterval(pollTimer)
        onRecent?.(uploadJobId.value, label)
        onDone?.(uploadJobId.value)
      } else if (data.status === 'error') {
        clearInterval(pollTimer)
        errorMsg.value = data.error ?? 'Error desconocido'
      }
    } catch { /* silencioso */ }
  }

  // ── File picker / drag & drop ──────────────────────────────────────────────
  function onDrop(e) {
    isDragging.value = false
    const file = e.dataTransfer.files[0]
    if (file) selectedFile.value = file
  }

  function onFileChange(e) {
    selectedFile.value = e.target.files[0] ?? null
  }

  function onRosterChange(e) {
    rosterFile.value = e.target.files[0] ?? null
  }
  function clearRoster() {
    rosterFile.value = null
  }

  // ── Acciones ───────────────────────────────────────────────────────────────
  async function upload() {
    if (!selectedFile.value) return
    resetJobState()
    uploading.value = true
    const label = labelFromFile(selectedFile.value)
    try {
      const data = await jobs.upload({
        file: selectedFile.value, roster: rosterFile.value, ...baseParams(),
      })
      uploadJobId.value = data.job_id
      jobStatus.value = 'pending'
      // Guarda el roster por job para que la vista de resultados auto-aplique
      // colores + nombres al abrir el análisis (mismo formato que el backend).
      if (rosterFile.value) {
        try {
          localStorage.setItem(
            `basket2d_roster_job_${data.job_id}`,
            await rosterFile.value.text(),
          )
        } catch { /* roster no legible: el backend ya lo recibió igualmente */ }
      }
      startPolling(label)
    } catch (err) {
      alert(`Error al subir el vídeo: ${err.message}`)
    } finally {
      uploading.value = false
    }
  }

  async function processTestVideo(tv) {
    if (processingTestVideo.value) return
    processingTestVideo.value = tv.name
    resetJobState()
    const label = prettifyTestVideo(tv.name)
    try {
      const data = await testVideosApi.process(tv.name, baseParams())
      uploadJobId.value = data.job_id
      jobStatus.value = 'pending'
      startPolling(label)
    } catch (err) {
      alert(`Error al lanzar el análisis: ${err.message}`)
    } finally {
      processingTestVideo.value = null
    }
  }

  onUnmounted(() => clearInterval(pollTimer))

  return {
    selectedFile, rosterFile, isDragging, uploading,
    uploadJobId, jobStatus, jobTasks, jobProgress, errorMsg,
    processingTestVideo,
    statusLabel, showProcessingModal,
    onDrop, onFileChange, onRosterChange, clearRoster, upload, processTestVideo,
  }
}
