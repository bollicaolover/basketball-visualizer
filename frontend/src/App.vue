<template>
  <!-- Pantalla de carga inicial -->
  <div v-if="checkingAuth" class="boot-screen">
    <svg class="boot-spin" width="28" height="28" viewBox="0 0 28 28" fill="none">
      <circle class="boot-track" cx="14" cy="14" r="11" stroke-width="2.5"/>
      <path class="boot-arc" d="M14 3a11 11 0 0 1 11 11" stroke-width="2.5" stroke-linecap="round"/>
    </svg>
  </div>

  <!-- Login -->
  <LoginView v-else-if="!authenticated" @authenticated="authenticated = true" />

  <!-- App principal -->
  <div v-else class="app-shell">
    <AppSidebar
      :active-job-id="jobId"
      @logout="logout"
      @open-job="openJob"
    />

    <div class="main-area">
      <UploadView v-if="!jobId" />
      <ResultsView v-else :key="jobId" :job-id="jobId" @reset="resetJob" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AppSidebar from './components/AppSidebar.vue'
import UploadView from './views/UploadView.vue'
import ResultsView from './views/ResultsView.vue'
import LoginView from './views/LoginView.vue'
import { useAuth } from './composables/useAuth.js'

const { authenticated, checkingAuth, logout } = useAuth()

// Job activo: se sincroniza con el query param `?job=` para enlaces compartibles.
const jobId = ref(new URLSearchParams(window.location.search).get('job'))

function openJob(id) {
  jobId.value = id
  window.history.pushState({}, '', `?job=${id}`)
}

function resetJob() {
  jobId.value = null
  window.history.pushState({}, '', window.location.pathname)
}
</script>

<style scoped>
.app-shell {
  display: flex;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-main);
}

.boot-screen {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-main);
}
.boot-spin { animation: spin 0.9s linear infinite; }
.boot-track { stroke: rgba(var(--c-blue-rgb), 0.25); }
.boot-arc   { stroke: var(--accent-orange); }
@keyframes spin { to { transform: rotate(360deg); } }

.main-area {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  min-height: 0;
}
</style>
