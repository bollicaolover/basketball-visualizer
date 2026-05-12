import { ref } from 'vue'
import { STORAGE_KEYS } from '../config/index.js'

/**
 * Nombres de equipo (opcionales, persistidos).
 * Si se dejan vacíos, el backend usa "Equipo 1/2".
 */
export function useTeamNames() {
  const team1 = ref('')
  const team2 = ref('')

  try {
    const t = JSON.parse(localStorage.getItem(STORAGE_KEYS.teamNames) ?? '{}')
    team1.value = t.team1 ?? ''
    team2.value = t.team2 ?? ''
  } catch { /* defaults */ }

  function save() {
    localStorage.setItem(
      STORAGE_KEYS.teamNames,
      JSON.stringify({ team1: team1.value, team2: team2.value }),
    )
  }

  return { team1, team2, save }
}
