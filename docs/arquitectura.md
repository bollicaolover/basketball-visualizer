# Arquitectura y estructura del proyecto

Guía para quien vaya a **modificar** la aplicación. Explica cómo está
organizado el código, dónde vive cada cosa y dónde tocar para los cambios más
habituales.

> Para la metodología del TFG (Kanban) ver [`metodologia.md`](metodologia.md).

---

## 1. Visión general

La aplicación tiene tres piezas independientes:

```
┌───────────────┐   HTTP /api/*   ┌────────────────────┐   subprocess    ┌──────────────┐
│   Frontend    │ ──────────────► │  Backend (FastAPI) │ ──────────────► │  Pipeline ML │
│  Vue 3 + Vite │ ◄────────────── │  backend/app/      │  python -m      │  pipeline/   │
│  (SPA)        │   JSON / vídeo  │  main.py           │  pipeline.run   │              │
└───────────────┘                 └────────────────────┘                 └──────────────┘
```

1. **Frontend** (`frontend/`): SPA en Vue 3 + Vite. Sube vídeos, sondea el
   estado del trabajo y visualiza resultados (vídeo anotado + minimapa 2D).
2. **Backend** (`backend/app/`): API FastAPI. Gestiona autenticación, subida,
   trabajos (jobs), métricas de hardware y sirve los resultados **y** el propio
   frontend compilado. Lanza el pipeline como subproceso (sin Celery/Redis).
3. **Pipeline ML** (`pipeline/`): el análisis de visión por computador real
   (detección → tracking → equipos → dorsales → homografía → posesión →
   render). Se ejecuta como `python -m pipeline.run`.

---

## 2. Estructura de la raíz

```
tfg-junio/
├── frontend/            SPA Vue 3 + Vite  (ver §3)
├── backend/             API FastAPI       (ver §4)
├── pipeline/            Pipeline ML       (ver §5)
├── docs/                Documentación (este fichero, metodología)
├── data/                Datos en tiempo de ejecución (uploads, jobs, salidas)
├── models/              Pesos de modelos (gitignored)
├── scripts/             Utilidades sueltas
├── run.py               CLI del pipeline (uso local directo)
├── serve.sh             Arranca el backend (que sirve el frontend ya compilado)
├── run_batch.sh         Procesado por lotes
├── requirements.txt     Dependencias Python (entorno conda `tfg-baloncesto`)
└── README.md
```

`data/`, `models/`, `*.mp4`, `*.pdf`, `*.log` y `frontend/.node|node_modules`
están en `.gitignore`. `frontend/dist/` **sí** se versiona (lo sirve el backend).

---

## 3. Frontend (`frontend/`)

SPA en **Vue 3** (`<script setup>`) construida con **Vite**. No usa Vuex/Pinia
ni Vue Router: el estado se gestiona con composables y el "enrutado" es manual
mediante el query param `?job=<id>`.

### 3.1 Estructura de `src/`

```
frontend/src/
├── main.js                 Punto de entrada: importa estilos globales + monta App
├── App.vue                 Shell: auth → login / app; alterna Upload ↔ Results por jobId
│
├── styles/                 ── Estilos globales (única fuente de verdad de color) ──
│   ├── tokens.css          Design tokens: paleta + tripletas RGB + tokens semánticos
│   └── base.css            Reset, tipografía base y scrollbar
│
├── config/                 ── Constantes (sin estado) ──
│   ├── index.js            Claves localStorage, intervalos de polling, geometría pista
│   └── palette.js          Paleta para <canvas> (espejo JS de tokens.css)
│
├── services/               ── Acceso al backend ──
│   └── api.js              TODAS las llamadas fetch (auth, system, jobs, outputs…)
│
├── composables/            ── Lógica reutilizable (estado + efectos) ──
│   ├── useAuth.js              Sesión: check al montar, login, logout
│   ├── useTeamNames.js        Nombres de equipo (persistidos)
│   ├── useGpus.js             Selección de GPU (auto / manual, persistida)
│   ├── useTestVideos.js       Catálogo de vídeos de prueba (+ prettifyTestVideo)
│   ├── useRecentAnalyses.js   Historial (persistido, agrupado, renombrable)
│   ├── useUploadJob.js        Subida + lanzar pipeline + sondeo de estado
│   ├── useSystemStats.js      Métricas CPU/GPU en tiempo real (para el modal)
│   └── useResizablePanel.js   Anchura arrastrable del panel derecho (persistida)
│
├── utils/                  ── Helpers puros (sin estado) ──
│   ├── format.js              formatSize, labelFromFile, fmtTime
│   └── labels.js              actionLabel, teamPrefix (etiquetas de dominio)
│
├── components/             ── Componentes reutilizables ──
│   ├── AppSidebar.vue         Barra lateral: subida, GPUs, test, historial
│   ├── ProcessingModal.vue    Modal de progreso (tareas + hardware)
│   └── Sparkline.js           Mini-gráfico SVG (render function)
│
└── views/                  ── Vistas de pantalla completa ──
    ├── LoginView.vue          Pantalla de contraseña
    ├── UploadView.vue         Estado vacío (placeholder previo al análisis)
    └── ResultsView.vue        Reproductor + capa de cajas + minimapa 2D
```

### 3.2 Reglas de organización (importante al modificar)

- **Colores: nunca hardcodear.** Todo color vive en
  [`styles/tokens.css`](../frontend/src/styles/tokens.css).
  - En CSS usa el token semántico: `color: var(--accent-rust)`.
  - Para color con transparencia usa la tripleta RGB:
    `background: rgba(var(--c-rust-rgb), 0.3)`.
  - En `<canvas>` (no lee CSS) usa
    [`config/palette.js`](../frontend/src/config/palette.js), que es el **espejo**
    de los tokens. Si cambias la paleta, actualiza **ambos** ficheros.
  - Para colorear trazos de SVG inline, usa una clase y `stroke: var(--token)`
    en CSS (las presentation attributes no aceptan `var()`).
- **Llamadas HTTP: solo en `services/api.js`.** Los componentes no llaman a
  `fetch` directamente; importan de `api.js`. Así rutas y manejo de errores
  quedan en un sitio.
- **Constantes mágicas: en `config/index.js`.** Claves de `localStorage`,
  intervalos, dimensiones del minimapa, etc. No repetir literales.
- **Lógica con estado reutilizable → composable** (`composables/use*.js`).
  Funciones puras → `utils/`.
- **Componentes de una sola pantalla → `views/`**; piezas reutilizables →
  `components/`.

### 3.3 Flujo de datos (resumen)

1. `App.vue` llama a `useAuth()`; si no hay sesión muestra `LoginView`.
2. `AppSidebar` posee los composables de subida/GPU/historial. Al subir un vídeo
   (`useUploadJob`), sondea `/api/jobs/{id}` cada 2 s y muestra `ProcessingModal`.
3. Al terminar el job, la sidebar emite `open-job` → `App.vue` fija `jobId` y
   actualiza la URL (`?job=<id>`).
4. `ResultsView` carga `metadata.json`, reproduce el vídeo limpio y dibuja la
   capa interactiva de cajas + el minimapa 2D sincronizados por frame.

### 3.4 Build y desarrollo

```bash
cd frontend
bash setup-node.sh        # instala Node portable en .node/ + npm ci + build
# o, si ya tienes Node 20:
npm install
npm run dev               # servidor de desarrollo (proxy /api y /static → :8000)
npm run build             # genera dist/ (lo sirve el backend en producción)
```

En desarrollo, `vite.config.js` redirige `/api` y `/static` a `http://localhost:8000`
(el backend), así que hay que tener el backend corriendo en paralelo.

---

## 4. Backend (`backend/app/`)

API **FastAPI**. Toda la lógica vive en dos ficheros:

| Fichero | Responsabilidad |
|---|---|
| [`main.py`](../backend/app/main.py) (~810 líneas) | App FastAPI, autenticación, endpoints, ejecución del pipeline en background, servir el frontend |
| [`chunking.py`](../backend/app/chunking.py) | Trocear/recombinar vídeo y metadatos para procesado multi-GPU (ffmpeg/ffprobe) |

### 4.1 Endpoints (definidos en `main.py`)

```
POST /api/auth/login            POST /api/upload
GET  /api/auth/check            GET  /api/jobs/{id}
POST /api/auth/logout           GET  /api/outputs/{id}/overlay.mp4
GET  /api/system/gpus           GET  /api/outputs/{id}/clean.mp4
GET  /api/system/stats          GET  /api/outputs/{id}/metadata.json
GET  /api/test-videos           GET/POST /api/outputs/{id}/annotations
POST /api/test-videos/{name}/process
GET  /{full_path}               → SPA fallback (index.html de Vue)
```

### 4.2 Cómo ejecuta el pipeline

- Sin Celery ni Redis: usa `BackgroundTasks` + `subprocess`.
- Cada job lanza `python -m pipeline.run` (ver §5) en la GPU asignada y parsea
  su stdout para reportar progreso en `/api/jobs/{id}`.
- Un **Lock por GPU** evita trabajos concurrentes en la misma tarjeta.
- Multi-GPU: `chunking.py` divide el vídeo en trozos, se procesan en paralelo y
  se recombinan vídeo + metadatos.
- Sirve el frontend compilado: monta `frontend/dist/assets` en `/assets`,
  `/static` para recursos (p.ej. `court.png`) y devuelve `index.html` para
  cualquier ruta no-API.

### 4.3 ⚠️ Carpetas vacías (andamiaje sin usar)

Estas rutas existen como **esqueleto** pero están **vacías** (0 líneas) y **no
se importan en ningún sitio**. La lógica real NO está aquí:

```
backend/app/config.py                 backend/app/db/__init__.py
backend/app/api/dependencies.py       backend/app/models/__init__.py
backend/app/api/routes/video.py       backend/app/utils/__init__.py
backend/app/api/routes/results.py
backend/app/core/**/*.py   (vision/, classifier/, expert/)
```

> Al modificar el backend, edita `main.py`/`chunking.py`. Si en el futuro se
> quiere modularizar (separar routers, dependencias, etc.), estas carpetas son
> el destino natural — pero hoy son placeholders. **No confundir con el
> pipeline ML real de `pipeline/`.**

### 4.4 Arranque

```bash
bash serve.sh                 # uvicorn backend.app.main:app --reload (puerto 8000)
# variables: PORT, HOST
```

`serve.sh` sirve el frontend **ya compilado** (`frontend/dist`). Para desarrollo
del frontend con recarga en caliente, arranca además `npm run dev` (§3.4).

---

## 5. Pipeline ML (`pipeline/`)

El análisis de visión real. Se invoca como módulo (`python -m pipeline.run`,
desde el backend) o vía la CLI de raíz (`python run.py clip.mp4 -o out.mp4`).

```
pipeline/
├── run.py            Entry point ejecutable (python -m pipeline.run)
├── orchestrator.py   Pipeline.process_video(): coordina todas las etapas
├── config.py         Settings (flags y parámetros del pipeline)
├── context.py        Estado compartido entre etapas
├── metadata_writer.py  Serializa los metadatos tácticos por frame (metadata.json)
├── profiling.py      Medición de tiempos
│
├── detection/        RF-DETR (11 clases): detección de jugadores/balón/aro…
├── tracking/         SAM (máscara) + tracker + balón + foot-point
├── teams/            Clasificación de equipo (SigLIP, voto por track)
├── identity/         OCR de dorsal (SmolVLM2) + roster (nombres)
├── court/            Keypoints de cancha → homografía → estabilización → render
├── possession/       Resolución del poseedor del balón
├── scoring/          Detección de tiros/canastas (shot_tracker)
└── io/               Lectura/escritura de vídeo
```

Etapas por frame (ver cabecera de [`orchestrator.py`](../pipeline/orchestrator.py)):
detección → cancha/homografía → tracking → equipos → dorsal/roster → balón →
proyección 2D → render (vídeo anotado + minimapa).

Salidas por job (en `data/jobs/{id}/` o el `output_dir` indicado):
`overlay.mp4` (anotado), `clean.mp4` (limpio, para la capa interactiva) y
`metadata.json` (datos tácticos por frame que consume `ResultsView`).

---

## 6. "Quiero cambiar X, ¿dónde toco?"

| Objetivo | Fichero(s) |
|---|---|
| Cambiar un color / la paleta | `frontend/src/styles/tokens.css` (+ `config/palette.js` si afecta al canvas) |
| Añadir/editar una llamada a la API | `frontend/src/services/api.js` |
| Cambiar el intervalo de sondeo, una clave de localStorage, geometría del minimapa | `frontend/src/config/index.js` |
| Lógica nueva reutilizable en el frontend | nuevo composable en `frontend/src/composables/` |
| Cambiar la barra lateral / subida | `frontend/src/components/AppSidebar.vue` |
| Cambiar el reproductor / minimapa / capa de cajas | `frontend/src/views/ResultsView.vue` |
| Añadir/editar un endpoint | `backend/app/main.py` |
| Cambiar el troceado multi-GPU | `backend/app/chunking.py` |
| Cambiar el análisis (detección, equipos, dorsales, cancha…) | el subpaquete correspondiente de `pipeline/` |
| Cambiar parámetros del pipeline | `pipeline/config.py` |

---

## 7. Restaurar el frontend anterior a la reorganización

Existe un backup comprimido (gitignored) del frontend previo al refactor:

```bash
rm -rf frontend && tar xzf frontend_backup_2026-06-15.tar.gz
```
