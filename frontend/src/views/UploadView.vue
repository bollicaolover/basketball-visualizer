<template>
  <div class="upload-page">
    <!-- Pizarra ambiente: media cancha en tiza, tenue, de fondo -->
    <svg class="court-motif" viewBox="0 0 280 320" fill="none" aria-hidden="true">
      <rect x="14" y="14" width="252" height="292" rx="4" />
      <line x1="14" y1="160" x2="266" y2="160" />
      <circle cx="140" cy="160" r="34" />
      <path d="M14 86 H266" opacity="0.5" />
      <rect x="96" y="14" width="88" height="120" />
      <circle cx="140" cy="134" r="34" />
      <path d="M44 14 V40 a96 96 0 0 0 192 0 V14" />
      <circle cx="140" cy="40" r="7" />
    </svg>

    <div class="hero">
      <span class="hero-eyebrow">
        <span class="eyebrow-dot"></span>
        Análisis táctico de baloncesto
      </span>

      <h1 class="hero-title">Sube un clip<br>y reconstruye la jugada</h1>

      <p class="hero-lead">
        Arrastra un vídeo <strong>MP4</strong> al panel lateral o elige uno de los
        vídeos de prueba. El sistema detecta jugadores, balón y aro, y proyecta el
        movimiento sobre una pizarra 2D sincronizada con el vídeo.
      </p>

      <!-- Pasos del pipeline: es una secuencia real, por eso van numerados -->
      <ol class="pipeline-steps">
        <li>
          <span class="step-num">01</span>
          <span class="step-text"><strong>Detecta</strong> jugadores, balón y aro fotograma a fotograma</span>
        </li>
        <li>
          <span class="step-num">02</span>
          <span class="step-text"><strong>Sigue</strong> cada identidad y estima la posesión</span>
        </li>
        <li>
          <span class="step-num">03</span>
          <span class="step-text"><strong>Proyecta</strong> las posiciones sobre la pizarra 2D</span>
        </li>
      </ol>

      <div class="hero-hint">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10 3 L5 8 l5 5" />
        </svg>
        Empieza en el panel de la izquierda
      </div>
    </div>
  </div>
</template>

<style scoped>
.upload-page {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  overflow: hidden;
  min-height: 0;
  min-width: 0;
  background:
    radial-gradient(120% 90% at 18% 0%, rgba(var(--c-blue-rgb), 0.10), transparent 60%),
    var(--bg-main);
  position: relative;
}

/* ── Pizarra ambiente ── */
.court-motif {
  position: absolute;
  right: -40px;
  top: 50%;
  transform: translateY(-50%);
  height: 118%;
  width: auto;
  stroke: var(--c-line-2);
  stroke-width: 1.1;
  opacity: 0.28;
  pointer-events: none;
}
.court-motif rect,
.court-motif circle,
.court-motif line,
.court-motif path { vector-effect: non-scaling-stroke; }

/* ── Hero ── */
.hero {
  position: relative;
  z-index: 1;
  max-width: 540px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-on-navy);
}
.eyebrow-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-gold);
  box-shadow: 0 0 8px var(--c-gold);
}

.hero-title {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: clamp(40px, 6vw, 64px);
  line-height: 0.96;
  letter-spacing: 0.01em;
  text-transform: uppercase;
  color: var(--text-primary);
  margin: 0.9rem 0 0;
}

.hero-lead {
  font-size: var(--text-md);
  line-height: 1.6;
  color: var(--text-secondary);
  margin: 1.1rem 0 0;
  max-width: 46ch;
}
.hero-lead strong { color: var(--text-primary); font-weight: 600; }

/* ── Pasos del pipeline ── */
.pipeline-steps {
  list-style: none;
  margin: 1.8rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  width: 100%;
  max-width: 460px;
}
.pipeline-steps li {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  padding: 0.7rem 0;
  border-top: 1px solid var(--border);
}
.pipeline-steps li:last-child { border-bottom: 1px solid var(--border); }

.step-num {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--text-on-navy);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
  width: 1.8rem;
}
.step-text {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  letter-spacing: 0.01em;
}
.step-text strong { color: var(--text-primary); font-weight: 600; }

/* ── Hint ── */
.hero-hint {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 1.8rem;
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}
.hero-hint svg {
  color: var(--text-on-navy);
  animation: nudge 1.6s ease-in-out infinite;
}
@keyframes nudge {
  0%, 100% { transform: translateX(0); }
  50%      { transform: translateX(-4px); }
}
</style>
