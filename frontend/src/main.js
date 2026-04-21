import { createApp } from 'vue'
// Fuentes autohospedadas (sin CDN): marcador condensado, cuerpo Inter y mono de datos.
import '@fontsource/saira-condensed/600.css'
import '@fontsource/saira-condensed/700.css'
import '@fontsource-variable/inter/wght.css'
import '@fontsource-variable/jetbrains-mono/wght.css'
import './styles/tokens.css'
import './styles/base.css'
import App from './App.vue'

createApp(App).mount('#app')
