/**
 * Paleta para dibujo en <canvas>.
 *
 * El canvas no puede leer variables CSS, así que estos valores reflejan los
 * tokens de `styles/tokens.css` (dirección "film room"). Si cambias la paleta,
 * actualiza ambos sitios.
 */

// Colores sólidos — espejo de tokens.css
export const PALETTE = {
  // Marca / acento
  navyDeep: '#001b4d',
  navy:     '#003f88',
  blue:     '#2f6fd0',
  azure:    '#4f93e0',
  gold:     '#fdc500',
  yellow:   '#ffd500',
  slate:    '#7e93b0',
  // Superficies
  ink0:     '#0a0e16',
  ink1:     '#111826',
  bgCard:   '#0f1626',   // fondo del canvas (pizarra)
  chalk:    '#eaf0fa',
  white:    '#ffffff',
  // Funcional (datos / estados)
  green:    '#22c55e',
  red:      '#f05252',
  orange:   '#ff6b35',
  teal:     '#2dd4bf',
}

// Colores de las cajas / minimapa por rol de entidad.
export const BOX_COLORS = {
  white:   PALETTE.azure,   // equipo local
  dark:    PALETTE.gold,    // equipo visitante
  ball:    PALETTE.orange,
  ref:     PALETTE.slate,
  rim:     PALETTE.chalk,
  unknown: PALETTE.blue,
}

// Relleno de los puntos del minimapa.
export const MAP_FILL = {
  white:   'rgba(79, 147, 224, 0.95)',
  dark:    'rgba(253, 197, 0, 0.95)',
  unknown: 'rgba(47, 111, 208, 0.92)',
}

// Estelas de movimiento (rastro corto detrás de cada jugador en la pizarra).
export const MAP_TRAIL = {
  white:   '79, 147, 224',
  dark:    '253, 197, 0',
  unknown: '47, 111, 208',
}

// Tonos auxiliares usados al pintar etiquetas / resaltes en el canvas.
export const CANVAS_INK = {
  tagBg:      'rgba(10, 14, 22, 0.82)',     // pastilla oscura translúcida
  tagBorder:  'rgba(253, 197, 0, 0.35)',    // filo dorado tenue
  tagText:    '#eaf0fa',
  dotStroke:  'rgba(10, 14, 22, 0.65)',
  hoverGlow:  'rgba(79, 147, 224, 0.75)',    // azur: estado interactivo (selección/hover)
  hoverRing:  'rgba(79, 147, 224, 0.95)',
  courtTint:  'rgba(10, 14, 22, 0.28)',     // velo para asentar la cancha
}
