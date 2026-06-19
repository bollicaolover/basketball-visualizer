/**
 * Trayectoria 2D del balón a partir de la metadata del pipeline.
 * Fallback cuando no hay reconstrucción 3D (misma heurística que el backend:
 * parábola convexa en Y-imagen centrada en el ápice).
 */

function ballCenter(frame) {
  const bb = frame?.ball?.bbox
  if (!bb || bb.length < 4) return null
  return [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2]
}

function contiguousRuns(samples) {
  if (!samples.length) return []
  const runs = [[samples[0]]]
  for (let i = 1; i < samples.length; i++) {
    if (samples[i].idx === samples[i - 1].idx + 1) runs[runs.length - 1].push(samples[i])
    else runs.push([samples[i]])
  }
  return runs
}

/** Ajuste y = a·t² + b·t + c por mínimos cuadrados (t = 0..n-1). */
function fitQuadraticY(ys) {
  const n = ys.length
  if (n < 3) return null
  let s0 = n, s1 = 0, s2 = 0, s3 = 0, s4 = 0
  let sy = 0, sty = 0, st2y = 0
  for (let i = 0; i < n; i++) {
    const t = i
    const t2 = t * t
    s1 += t
    s2 += t2
    s3 += t2 * t
    s4 += t2 * t2
    sy += ys[i]
    sty += t * ys[i]
    st2y += t2 * ys[i]
  }
  // Resolver sistema 3×3 por eliminación simple
  const A = [
    [s0, s1, s2, sy],
    [s1, s2, s3, sty],
    [s2, s3, s4, st2y],
  ]
  for (let col = 0; col < 3; col++) {
    let pivot = col
    for (let row = col + 1; row < 3; row++) {
      if (Math.abs(A[row][col]) > Math.abs(A[pivot][col])) pivot = row
    }
    ;[A[col], A[pivot]] = [A[pivot], A[col]]
    const div = A[col][col] || 1e-9
    for (let row = col + 1; row < 3; row++) {
      const f = A[row][col] / div
      for (let j = col; j < 4; j++) A[row][j] -= f * A[col][j]
    }
  }
  const x = [0, 0, 0]
  for (let i = 2; i >= 0; i--) {
    let sum = A[i][3]
    for (let j = i + 1; j < 3; j++) sum -= A[i][j] * x[j]
    x[i] = sum / (A[i][i] || 1e-9)
  }
  return { a: x[2], b: x[1], c: x[0] }
}

function rmsQuadratic(coeffs, ys) {
  if (!coeffs) return Infinity
  let sum = 0
  for (let i = 0; i < ys.length; i++) {
    const pred = coeffs.a * i * i + coeffs.b * i + coeffs.c
    sum += (pred - ys[i]) ** 2
  }
  return Math.sqrt(sum / ys.length)
}

function rimFromFrame(frame) {
  const rims = frame?.rims
  if (!rims?.length) return null
  const r = rims[0]
  const bb = r.bbox
  if (!bb) return null
  const cx = (bb[0] + bb[2]) / 2
  const cy = (bb[1] + bb[3]) / 2
  const rad = Math.max((bb[2] - bb[0]), (bb[3] - bb[1])) / 2
  return [cx, cy, rad]
}

/**
 * @param {Array} frames metadata frames
 * @param {number} fps
 * @returns overlay compatible con drawShot3d o null
 */
export function buildTrajectoryOverlay(frames, fps = 30) {
  const samples = []
  for (const f of frames) {
    const c = ballCenter(f)
    if (c) samples.push({ idx: f.frame_index ?? f.index ?? 0, x: c[0], y: c[1] })
  }
  samples.sort((a, b) => a.idx - b.idx)
  if (samples.length < 8) return null

  const minLen = 8
  const halfWindow = Math.max(4, Math.round(0.5 * fps))
  let best = null

  for (const run of contiguousRuns(samples)) {
    if (run.length < minLen) continue
    let apexI = 0
    for (let i = 1; i < run.length; i++) {
      if (run[i].y < run[apexI].y) apexI = i
    }
    const i0 = Math.max(0, apexI - halfWindow)
    const i1 = Math.min(run.length - 1, apexI + halfWindow)
    const seg = run.slice(i0, i1 + 1)
    if (seg.length < minLen) continue

    const ys = seg.map((p) => p.y)
    const coeffs = fitQuadraticY(ys)
    if (!coeffs || coeffs.a <= 0) continue
    const tVertex = -coeffs.b / (2 * coeffs.a)
    if (tVertex < 0 || tVertex > seg.length - 1) continue
    const rms = rmsQuadratic(coeffs, ys)
    const amp = Math.max(...ys) - Math.min(...ys)
    if (rms > 22 || amp < 40) continue
    if (!best || amp > best.amp) {
      best = { amp, seg, coeffs, lo: seg[0].idx, hi: seg[seg.length - 1].idx }
    }
  }
  if (!best) return null

  const { seg, coeffs, lo, hi } = best
  const tEnd = seg.length - 1 + Math.max(8, Math.round(0.35 * fps))
  const nArc = Math.max(40, Math.round(tEnd * 2))
  const arcPts = []
  for (let t = 0; t <= nArc; t++) {
    const tt = (t / nArc) * tEnd
    const x0 = seg[0].x
    const x1 = seg[seg.length - 1].x
    const x = x0 + (tt / tEnd) * (x1 - x0)
    const y = coeffs.a * tt * tt + coeffs.b * tt + coeffs.c
    arcPts.push([x, y])
  }

  const frameMap = Object.fromEntries(frames.map((f) => [f.frame_index ?? f.index, f]))
  const overlayHi = hi + Math.max(8, Math.round(0.4 * fps))
  const overlayFrames = {}

  for (let fi = lo; fi <= overlayHi; fi++) {
    const meta = frameMap[fi]
    if (!meta) continue
    const entry = { arc: arcPts.map(([x, y]) => [Math.round(x), Math.round(y)]) }
    const rim = rimFromFrame(meta)
    if (rim) entry.rim = rim
    if (fi >= lo && fi <= hi) {
      const c = ballCenter(meta)
      if (c) {
        entry.ball_meas = [c[0], c[1]]
        const rel = fi - lo
        const yModel = coeffs.a * rel * rel + coeffs.b * rel + coeffs.c
        entry.ball_proj = [Math.round(c[0]), Math.round(yModel)]
      }
    }
    if (fi === overlayHi) {
      const last = arcPts[arcPts.length - 1]
      entry.end = [Math.round(last[0]), Math.round(last[1])]
      entry.end_reason = rim ? 'rim' : 'floor'
    }
    overlayFrames[String(fi)] = entry
  }

  return {
    lo,
    hi,
    overlay_hi: overlayHi,
    end_reason: 'floor',
    hud: { apex_m: null, rmse_px: null, source: '2d' },
    frames: overlayFrames,
  }
}
