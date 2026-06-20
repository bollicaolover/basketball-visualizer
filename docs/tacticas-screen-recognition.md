# Reconocimiento de pantallas (*screens*) a partir de trayectorias

Notas de extracción e implementación a partir del artículo de referencia
`docs/references/main.pdf`:

> H.-T. Chen, C.-L. Chou, T.-S. Fu, S.-Y. Lee, B.-S. P. Lin,
> **"Recognizing tactic patterns in broadcast basketball video using player
> trajectory"**, *J. Vis. Commun. Image R.* 23 (2012) 932–947.

Este es el artículo del que parte el bloque táctico del TFG. Aquí se resume lo
que aporta y **qué parte se ha implementado** en `pipeline/tactics/`.

---

## 1. Resumen del sistema del artículo

Pipeline de cuatro etapas para reconocer *patrones de pantalla* en vídeo de
baloncesto de retransmisión:

1. **Calibración de cámara** (§3): detección de píxeles de líneas blancas →
   Hough → extracción paso a paso de 5 líneas (`L1`..`L5`: banda, fondo, dos
   horizontales del área y línea de tiros libres) → 6 intersecciones →
   homografía plano-a-plano `p' = H·p` (8 GdL, mínimos cuadrados). Precisión
   declarada **91,47 %** de frames bien calibrados (vs. 77,32 % de Farin).
2. **Extracción y seguimiento de jugadores** (§4): segmentación por color
   dominante (GMM) dentro de la cancha, *clustering* k-means (k=6, espacio
   YCbCr, se toman los 2 *clusters* mayores como los dos equipos) y seguimiento
   con **filtro de Kalman** (Algoritmo 1). Precisión/recall medios de tracking
   **89,71 % / 89,20 %**.
3. **Discriminación ataque/defensa** (§4.2): se proyectan las posiciones al
   modelo de cancha; para cada equipo se calcula la **distancia media de sus
   jugadores a la canasta**. El equipo cuyos jugadores están de media **más
   lejos** de la canasta es el atacante (cada defensor se coloca más cerca del
   aro que su par atacante). En el experimento acertó en los 40 clips.
4. **Reconocimiento de pantallas** (§5): detección (Algoritmo 2) + clasificación
   (Ec. 9) en tres tipos: *front*, *back* y *down*.

### Tipos de pantalla (§5)

- **Front-screen**: el bloqueador (*screener*) pone el bloqueo y el *screenee*
  supera al defensor perpendicularmente a la dirección defensor→canasta; suele
  fijarse cerca de la línea de 3 y el *screenee* sale a un espacio abierto (no
  va al aro).
- **Back-screen**: el bloqueo se pone por detrás del defensor; el *screenee*
  corta **hacia la canasta**. El bloqueador sube del *poste bajo* al *poste alto*.
- **Down-screen**: el bloqueador baja del *poste alto* al *poste bajo* y el
  *screenee* sube a recibir.

### Algoritmo 2 — Detección de pantalla

```
Entrada: players_off, players_def
si ∃ i,j ∈ players_off con ds < dist(i,j) < Ds, i≠j:
    si ∃ d ∈ players_def con dist(d,i) < ds  ó  dist(d,j) < ds:
        screener := el atacante más cercano al defensor d
        screenee := el otro atacante
devuelve screener, screenee
```

Idea: dos atacantes **anormalmente juntos** (normalmente el ataque abre el
campo) con **al menos un defensor entre/junto a ellos** ⇒ se está poniendo un
bloqueo. El *screener* es el atacante que contacta con el defensor.

### Ecuación 9 — Clasificación de pantalla

Notación: `p_init`, `p_screen`, `p_last` = posición del *screener* al inicio,
al fijar el bloqueo y al final; lo mismo con `'` para el *screenee*;
`p_basket` = canasta atacada.

```
screenType =
  Down,  si |p_basket - p_init| > |p_basket - p_screen|              (el screener baja hacia el aro)
  Back,  si no Down  y  ang(d_moving, d_basket) <  θs               (el screenee corta al aro)
  Front, si no Down  y  ang(d_moving, d_basket) >= θs               (el screenee sale a espacio abierto)
  undefined, en otro caso

con d_moving = p'_last - p'_screen   (movimiento del screenee tras el bloqueo)
    d_basket = p_basket - p'_screen  (dirección screenee → canasta)
    ang(a,b) = arccos( a·b / (|a||b|) )
```

### Datos experimentales (§6)

- Vídeos: 4 partidos masculinos JJOO Pekín 2008 (640×352, 29,97 fps).
- 80 clips (40 entrenamiento / 40 test). **35/40** pantallas bien clasificadas.
- Errores típicos: oclusiones (tracking) y casos límite en los que el
  *screener* fija el bloqueo más cerca del aro que su punto de partida (Ec. 9
  lo etiqueta como *down* erróneamente).

---

## 2. Qué se ha implementado aquí

El pipeline `tfg-junio` ya cubre las etapas 1–2 del artículo **con tecnología
más moderna** (RF-DETR + SAM 3 + homografía/PnP por keypoints + clasificación
de equipos SigLIP), de modo que la **aportación nueva del artículo que faltaba**
era el bloque táctico (§4.2 y §5). Eso es lo implementado:

`pipeline/tactics/` — reconocimiento de pantallas sobre las trayectorias en
coordenadas de cancha (pies) que el pipeline ya escribe en `{out}_metadata.json`:

- `geometry.py` — posición de las canastas y canasta atacada por el ataque.
- `recognizer.py` — discriminación ataque/defensa (§4.2), detección de pantalla
  por frame (Algoritmo 2) y clasificación por trayectoria (Ec. 9), con
  agregación temporal de detecciones frame a frame en *eventos* de pantalla.
- `run.py` — lee `{out}_metadata.json` y escribe `{out}_tactics.json`; CLI
  `python -m pipeline.tactics.run`.
- `TacticsSettings` en `pipeline/config.py`; se ejecuta tras la pasada principal
  (como `shot3d`) cuando `settings.tactics.enabled` (flag CLI `--tactics`).

### Integración web

- **Backend** (`backend/app/main.py`): tras fusionar la metadata final (mono- y
  multi-GPU), `_generate_tactics()` corre el reconocedor sobre
  `overlay_metadata.json` y escribe `tactics.json`. Se sirve en
  `GET /api/outputs/{job_id}/tactics.json` y se anuncia como `tactics_url` en el
  payload del job. Se calcula en el backend (no por chunk) para operar sobre las
  trayectorias completas.
- **Frontend** (`frontend/src/views/ResultsView.vue`): tarjeta **PANTALLAS** en
  la columna del mapa 2D con la lista de screens (badge FRONT/BACK/DOWN +
  equipo + instante). Cada fila salta el vídeo al frame del bloqueo y la pantalla
  cuyo rango contiene el frame actual se resalta. API en `services/api.js`
  (`outputs.tactics`).

### Mejora respecto al artículo (2012)

La discriminación ataque/defensa del artículo usa una heurística de distancia
media al aro. Aquí se prefiere la **posesión** ya resuelta por `PossessionResolver`
(clase `player-in-possession` de RF-DETR): el equipo del poseedor **es** el
atacante, señal mucho más fiable. La heurística de distancia del artículo se
conserva como *fallback* cuando no hay poseedor en el frame.

### Unidades y parámetros

El artículo trabaja en el modelo de cancha (unidades del *court model*); aquí
todo está en **pies (ft)** sobre la geometría NBA de `pipeline/court/geometry.py`.
Parámetros por defecto (configurables en `TacticsSettings`):

| Símbolo (paper) | Parámetro | Defecto | Significado |
|---|---|---|---|
| `ds` | `contact_dist_ft` | 4.0 ft | contacto *screener*↔defensor / atacantes muy juntos |
| `Ds` | `near_dist_ft` | 12.0 ft | umbral superior "dos atacantes juntos" |
| `θs` | `back_front_angle_deg` | 60° | corte *back* vs *front* |
| — | `min_event_frames` | 3 | frames mínimos para confirmar el evento |
| — | `max_gap_frames` | 5 | huecos tolerados (oclusión) dentro de un evento |
