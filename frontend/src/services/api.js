/**
 * Capa de acceso al backend.
 * Toda comunicación HTTP con la API vive aquí; los componentes no llaman a
 * `fetch` directamente. Así las rutas y el manejo de errores quedan en un solo
 * sitio.
 */

const BASE = '/api'

/** Lanza un Error con el cuerpo de la respuesta si el status no es 2xx. */
async function ensureOk(res) {
  if (!res.ok) throw new Error(await res.text().catch(() => res.statusText))
  return res
}

// ── Autenticación ────────────────────────────────────────────────────────────
export const auth = {
  /** ¿Hay sesión válida? Devuelve boolean, nunca lanza. */
  async check() {
    try {
      const res = await fetch(`${BASE}/auth/check`)
      return res.ok
    } catch {
      return false
    }
  },

  /** Inicia sesión. Devuelve true si la contraseña es correcta. */
  async login(password) {
    const res = await fetch(`${BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    return res.ok
  },

  async logout() {
    await fetch(`${BASE}/auth/logout`, { method: 'POST' })
  },
}

// ── Sistema / hardware ───────────────────────────────────────────────────────
export const system = {
  /** GPUs disponibles. Lista vacía ante cualquier error. */
  async gpus() {
    try {
      const res = await fetch(`${BASE}/system/gpus`)
      const data = await res.json()
      return data.gpus ?? []
    } catch {
      return []
    }
  },

  /** Métricas de CPU/GPU en tiempo real. */
  async stats() {
    const res = await ensureOk(await fetch(`${BASE}/system/stats`))
    return res.json()
  },
}

// ── Vídeos de prueba ─────────────────────────────────────────────────────────
export const testVideos = {
  /** Lista de vídeos de prueba. Lista vacía ante cualquier error. */
  async list() {
    try {
      const res = await fetch(`${BASE}/test-videos`)
      const data = await res.json()
      return data.videos ?? []
    } catch {
      return []
    }
  },

  /** Lanza el análisis de un vídeo de prueba. Devuelve { job_id }. */
  async process(name, { gpus, memFraction, team1, team2, tracker }) {
    const qs = new URLSearchParams({
      gpus,
      mem_fraction: String(memFraction),
      team1,
      team2,
      tracker: tracker || 'sam',
    })
    const res = await ensureOk(
      await fetch(`${BASE}/test-videos/${encodeURIComponent(name)}/process?${qs}`, {
        method: 'POST',
      }),
    )
    return res.json()
  },
}

// ── Jobs ─────────────────────────────────────────────────────────────────────
export const jobs = {
  /** Sube un vídeo y arranca el pipeline. Devuelve { job_id }. */
  async upload({ file, gpus, memFraction, team1, team2, roster, tracker }) {
    const form = new FormData()
    form.append('file', file)
    form.append('gpus', gpus)
    form.append('mem_fraction', String(memFraction))
    form.append('team1', team1)
    form.append('team2', team2)
    form.append('tracker', tracker || 'sam')
    if (roster) form.append('roster', roster)
    const res = await ensureOk(await fetch(`${BASE}/upload`, { method: 'POST', body: form }))
    return res.json()
  },

  /** Estado de un job en proceso. */
  async status(jobId) {
    const res = await ensureOk(await fetch(`${BASE}/jobs/${jobId}`))
    return res.json()
  },
}

// ── Resultados / recursos estáticos ──────────────────────────────────────────
export const outputs = {
  /** Metadata del análisis. Devuelve { ok, status, data, detail }. */
  async metadata(jobId) {
    const res = await fetch(`${BASE}/outputs/${jobId}/metadata.json`)
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      return { ok: false, status: res.status, detail: body.detail }
    }
    return { ok: true, data: await res.json() }
  },

  /** Roster guardado en el servidor para este análisis, o null si no hay. */
  async roster(jobId) {
    try {
      const res = await fetch(`${BASE}/outputs/${jobId}/roster.json`)
      if (!res.ok) return null
      return await res.json()
    } catch {
      return null
    }
  },

  cleanVideoUrl:   (jobId) => `${BASE}/outputs/${jobId}/clean.mp4`,
  overlayVideoUrl: (jobId) => `${BASE}/outputs/${jobId}/overlay.mp4`,
  shot3dVideoUrl:  (jobId) => `${BASE}/outputs/${jobId}/shot3d.mp4`,

  /** Datos de reconstrucción 3D (incluye capa ``overlay`` para el canvas). */
  async shot3dJson(jobId) {
    try {
      const res = await fetch(`${BASE}/outputs/${jobId}/shot3d.json`)
      if (!res.ok) return null
      return await res.json()
    } catch {
      return null
    }
  },

  /** Comprueba si existe la reconstrucción 3D del tiro. */
  async hasShot3d(jobId) {
    try {
      const res = await fetch(`${BASE}/outputs/${jobId}/shot3d.mp4`, { method: 'HEAD' })
      return res.ok
    } catch {
      return false
    }
  },

  /** Pantallas (screens) reconocidas, o null si no hay. */
  async tactics(jobId) {
    try {
      const res = await fetch(`${BASE}/outputs/${jobId}/tactics.json`)
      if (!res.ok) return null
      return await res.json()
    } catch {
      return null
    }
  },
}

/** Imagen estática de la pista para el minimapa. */
export const courtImageUrl = `/static/court.png?v=${__COURT_VERSION__}`
