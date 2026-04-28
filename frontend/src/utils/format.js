/** Utilidades de formato puras (sin estado). */

/** Tamaño de fichero legible: "1.5 MB" / "320.0 KB". */
export function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** Etiqueta a partir del nombre de fichero: "mi_clip-01.mp4" → "mi clip 01". */
export function labelFromFile(file) {
  return file.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ')
}

/** Segundos → "m:ss". */
export function fmtTime(s) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60).toString().padStart(2, '0')
  return `${m}:${sec}`
}
