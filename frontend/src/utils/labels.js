/** Etiquetas de dominio (baloncesto): acciones y prefijos de equipo. */

// Etiquetas legibles por clase de acción.
export const ACTION_LABEL = {
  block: 'bloqueo', pass: 'pase', run: 'corre', dribble: 'drible',
  shoot: 'tiro', ball_in_hand: 'balón', defense: 'defensa', pick: 'bloqueo dir.',
  no_action: '—', walk: 'camina',
}

/** Texto legible de una acción, o null si no hay. */
export function actionLabel(a) {
  return a ? (ACTION_LABEL[a] ?? a) : null
}

/** Prefijo de equipo: white→"H" (home), dark→"V" (visitor). */
export function teamPrefix(team) {
  return team === 'white' ? 'H' : team === 'dark' ? 'V' : ''
}
