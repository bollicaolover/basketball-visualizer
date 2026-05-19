import { defineComponent, h } from 'vue'

/**
 * Mini-gráfico de línea (sparkline) dibujado como SVG inline.
 * Sin estado: recibe la serie de valores y el color del trazo.
 */
export default defineComponent({
  name: 'Sparkline',
  props: {
    values: { type: Array, default: () => [] },
    color:  { type: String, default: 'currentColor' },
  },
  setup(props) {
    return () => {
      const vals = props.values || []
      if (vals.length < 2) return h('div', { class: 'sparkline' })
      const W = 52, H = 24
      const max = Math.max(...vals, 1)
      const pts = vals
        .map((v, i) => `${(i / (vals.length - 1)) * W},${H - (v / max) * H * 0.9}`)
        .join(' ')
      return h('svg', { width: W, height: H, class: 'sparkline', viewBox: `0 0 ${W} ${H}` }, [
        h('polyline', {
          points: pts,
          fill: 'none',
          stroke: props.color,
          'stroke-width': '1.5',
          'stroke-linejoin': 'round',
          opacity: '0.7',
        }),
      ])
    }
  },
})
