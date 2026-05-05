<template>
  <div class="login-screen">
    <div class="login-card">

      <!-- Brand -->
      <div class="login-brand">
        <svg class="brand-mark" width="32" height="32" viewBox="0 0 22 22" fill="none">
          <circle cx="11" cy="11" r="10" stroke-width="1.6"/>
          <path d="M11 1 Q4.5 11 11 21" stroke-width="1.2" fill="none"/>
          <path d="M11 1 Q17.5 11 11 21" stroke-width="1.2" fill="none"/>
          <path d="M1 11 H21" stroke-width="1.2"/>
        </svg>
        <span class="brand-name">BASKET<strong>2D</strong></span>
      </div>

      <p class="login-subtitle">Introduce la contraseña para continuar</p>

      <form class="login-form" @submit.prevent="submit">
        <div class="input-wrap" :class="{ 'input-wrap--error': error }">
          <svg class="input-icon" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="3" y="7" width="10" height="8" rx="1.5"/>
            <path d="M5 7V5a3 3 0 016 0v2"/>
          </svg>
          <input
            ref="inputEl"
            v-model="password"
            :type="showPw ? 'text' : 'password'"
            placeholder="Contraseña"
            class="login-input"
            autocomplete="current-password"
            spellcheck="false"
          />
          <button type="button" class="toggle-pw" @click="showPw = !showPw" tabindex="-1">
            <svg v-if="!showPw" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4">
              <path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z"/>
              <circle cx="8" cy="8" r="2"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4">
              <path d="M2 2l12 12M6.5 6.6A2 2 0 0010 10M4 4.4C2.5 5.5 1 8 1 8s2.5 5 7 5c1.3 0 2.5-.3 3.5-.9M7 3.1C7.3 3 7.7 3 8 3c4.5 0 7 5 7 5s-.7 1.4-1.9 2.6"/>
            </svg>
          </button>
        </div>

        <p v-if="error" class="login-error">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="6" cy="6" r="5"/>
            <path d="M6 4v3M6 8.5v.5"/>
          </svg>
          {{ error }}
        </p>

        <button type="submit" class="login-btn" :disabled="loading || !password">
          <svg v-if="!loading" width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M2 7h10M8 3l4 4-4 4"/>
          </svg>
          <svg v-else class="spin" width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M7 1a6 6 0 0 1 6 6" stroke-linecap="round"/>
          </svg>
          {{ loading ? 'VERIFICANDO…' : 'ENTRAR' }}
        </button>
      </form>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { auth } from '../services/api.js'

const emit = defineEmits(['authenticated'])

const password  = ref('')
const error     = ref('')
const loading   = ref(false)
const showPw    = ref(false)
const inputEl   = ref(null)

onMounted(() => inputEl.value?.focus())

async function submit() {
  if (!password.value || loading.value) return
  loading.value = true
  error.value = ''
  try {
    if (await auth.login(password.value)) {
      emit('authenticated')
    } else {
      error.value = 'Contraseña incorrecta'
      password.value = ''
      inputEl.value?.focus()
    }
  } catch {
    error.value = 'Error de conexión con el servidor'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-screen {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-main);
}

.login-card {
  width: 340px;
  background: var(--bg-panel);
  border-radius: 14px;
  border: 1px solid var(--border-mid);
  padding: 2.2rem 2rem 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.4rem;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.brand-mark circle,
.brand-mark path { stroke: var(--c-gold); }

.brand-name {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-primary);
}

.brand-name strong {
  font-weight: 700;
  color: var(--text-on-navy);
  letter-spacing: 0.05em;
}

.login-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  margin: -0.6rem 0 0;
  letter-spacing: 0.02em;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.input-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--bg-card);
  border: 1px solid var(--border-mid);
  border-radius: 8px;
  padding: 0 0.65rem;
  transition: border-color 0.15s;
}

.input-wrap:focus-within { border-color: rgba(var(--c-blue-rgb), 0.7); }
.input-wrap--error { border-color: rgba(var(--c-rust-rgb), 0.6); }

.input-icon { color: var(--text-muted); flex-shrink: 0; }

.login-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 13px;
  padding: 0.65rem 0;
  font-family: inherit;
  letter-spacing: 0.02em;
}

.login-input::placeholder { color: var(--text-muted); }

.toggle-pw {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.2rem;
  display: flex;
  align-items: center;
  transition: color 0.15s;
}
.toggle-pw:hover { color: var(--text-secondary); }

.login-error {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 11px;
  color: var(--accent-red);
  letter-spacing: 0.02em;
}

.login-btn {
  width: 100%;
  padding: 0.7rem;
  background: var(--accent-orange);
  border: none;
  border-radius: 8px;
  color: var(--text-on-accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  transition: background 0.15s, opacity 0.15s;
  margin-top: 0.2rem;
}
.login-btn:hover:not(:disabled) { background: var(--accent-orange-hover); }
.login-btn:disabled { opacity: 0.45; cursor: default; }

.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
