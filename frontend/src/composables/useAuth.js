import { ref, onMounted } from 'vue'
import { auth } from '../services/api.js'

/**
 * Estado de autenticación de la app.
 * Comprueba la sesión al montar y expone acciones de login/logout.
 */
export function useAuth() {
  const authenticated = ref(false)
  const checkingAuth  = ref(true)

  onMounted(async () => {
    authenticated.value = await auth.check()
    checkingAuth.value = false
  })

  async function logout() {
    await auth.logout()
    authenticated.value = false
  }

  return { authenticated, checkingAuth, logout }
}
