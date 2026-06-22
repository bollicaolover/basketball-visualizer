# Capítulo 6 — Desarrollo del sistema (índice)

> Documento de apoyo a la memoria del TFG *basketball-visualizer*.
> El índice de este capítulo se ha reconstruido **exclusivamente** a partir de la
> trazabilidad real de *commits* del repositorio (`git log`) y de los CFD
> generados en `docs/` (`cfd.svg` y los snapshots `cfd_m{1..6}_*.svg`).
>
> **Coherencia con Kanban.** El proyecto se gestionó con dos flujos Kanban en
> paralelo (programación y documentación, WIP=1 cada uno; véase
> `scripts/generate_cfd_svg.py`). El capítulo sigue el **orden cronológico real**
> de entrega de módulos —un módulo por *commit*— articulado sobre los seis hitos
> del CFD. No se incluyen fases predictivas (análisis de requisitos,
> especificación formal, etc.) porque **no existen commits que las respalden**.
> Las refactorizaciones de junio sobre módulos ya construidos se reflejan como
> *subsecciones de iteración*, no como fases nuevas.

Rango temporal real: **8-ene-2026 → 22-jun-2026** (63 commits).

Hitos del CFD (snapshots de cierre):

| Hito | Archivo | Fecha |
|------|---------|-------|
| m1 — Geometría y homografía | `docs/cfd_m1_geometria.svg` | 26-feb-2026 |
| m2 — Tracking jugadores y balón | `docs/cfd_m2_tracking.svg` | 19-mar-2026 |
| m3 — Identidad (SigLIP + VLM2) | `docs/cfd_m3_identidad.svg` | 9-abr-2026 |
| m4 — Pipeline ejecutable | `docs/cfd_m4_pipeline.svg` | 30-abr-2026 |
| m5 — Web app completa + Docker | `docs/cfd_m5_webapp.svg` | 27-may-2026 |
| m6 — Entrega final | `docs/cfd_m6_entrega.svg` | 25-jun-2026 |

---

## 6.1 Configuración inicial y arquitectura base *(ene–feb 2026)*

Arranque de los dos flujos: esqueleto de proyecto, backend arrancable y seguridad básica.

| Commit | Fecha | Aporta |
|--------|-------|--------|
| `e089e45` | 08-ene | Setup, requirements y notebook de referencia |
| `9a122cb` | 15-ene | Esqueleto de pipeline y config global (constantes RF-DETR 11 clases) |
| `71f2465` | 22-ene | Scripts de descarga de dataset y modelos |
| `98f541d` / `33dfbb2` `[WEB-B1]` | 29-ene | Backend FastAPI + Dockerfile |
| `a398cac` `[WEB-B2]` | 20-feb | Autenticación por token HMAC |

## 6.2 Núcleo de visión I — geometría y homografía *(Hito m1, 26-feb)*

| Commit | Fecha | Aporta |
|--------|-------|--------|
| `261e036` | 03-feb | Detector RF-DETR local (11 clases) |
| `ddacadc` | 11-feb | Geometría de cancha FIBA + detector de keypoints |
| `4277600` | 18-feb | Homografía (DLT/SVD/RANSAC) + modelo PnP |
| `9730a01` | 26-feb | Render cenital 2D + estabilizador + suavizado |

Respaldo de cierre: `docs/cfd_m1_geometria.svg`.

## 6.3 Núcleo de visión II — tracking de jugadores y balón *(Hito m2, 19-mar)*

| Commit | Fecha | Aporta |
|--------|-------|--------|
| `404127e` | 05-mar | I/O de vídeo + tipos/interfaz de tracking |
| `be5eca9` | 12-mar | Tracker SAM3 (*prompt-once* sembrado por RF-DETR) |
| `6faee31` | 19-mar | Tracker de balón + punto de apoyo por máscara |

Respaldo: `docs/cfd_m2_tracking.svg`.

## 6.4 Identidad — equipos y dorsales *(Hito m3, 9-abr)*

| Commit | Fecha | Aporta |
|--------|-------|--------|
| `7506f54` | 26-mar | Clasificador de equipos SigLIP (no supervisado, voto por track) |
| `efc179e` | 02-abr | OCR de dorsal con SmolVLM2 (voto IoS) |
| `0a129b2` | 09-abr | Roster de jugadores + scripts de entrenamiento |

Respaldo: `docs/cfd_m3_identidad.svg`.

## 6.5 Análisis táctico y pipeline ejecutable de extremo a extremo *(Hito m4, 30-abr)*

| Commit | Fecha | Aporta |
|--------|-------|--------|
| `2485a57` `[E-1]` | 16-abr | Resolver de posesión |
| `65fb57e` `[E-2]` | 23-abr | Shot tracker (eventos de canasta) |
| `b4c7ca3` `[D-1]` | 30-abr | Orquestador principal por frame + profiling |
| `7e775bd` | 08-may | `run.py` + `run_batch.sh` (procesamiento por lotes) |

Respaldo: `docs/cfd_m4_pipeline.svg`.

## 6.6 Aplicación web — backend, frontend e integración *(Hito m5, 27-may)*

Construida en paralelo y reintegrada sobre el pipeline.

### 6.6.1 API del backend
| Commit | Fecha | Aporta |
|--------|-------|--------|
| `75786cf` `[WEB-B3]` | 16-mar | Subida de vídeo + transcodificación por chunks |
| `897e09b` `[WEB-B4]` | 07-abr | Endpoints de resultados + orquestación por subprocess |
| `7d9edf5` `[WEB-B5]` | 14-abr | Clasificador táctico (GNN + motor de reglas) |
| `ad4ce44` `[WEB-B6]` | 17-abr | Wrappers de visión (detector, tracker, homografía) + asset de cancha |

### 6.6.2 SPA Vue 3
| Commit | Fecha | Aporta |
|--------|-------|--------|
| `8487dd8` `[WEB-F1]` | 21-abr | Scaffold Vue 3 + Vite, design tokens |
| `22ced56` `[WEB-F2]` | 28-abr | Capa de servicios API + utilidades de display |
| `986ba13` `[WEB-F3]` | 05-may | Login + composable de auth (HMAC) |
| `3e8d156` `[WEB-F4]` | 12-may | Vista de subida (job, progreso, config de equipos) |
| `643a9cd` `[WEB-F5]` | 16-may | Vista de resultados: vídeo anotado + mapa táctico 2D |
| `49abcd2` `[WEB-F6]` | 19-may | App shell, sidebar, modal de proceso, sparkline, stats GPU |

### 6.6.3 Empaquetado e integración
| Commit | Fecha | Aporta |
|--------|-------|--------|
| `d731242` `[WEB-D1]` | 24-may | Metadata writer (JSON por frame) + módulo de ejecución + roster |
| `b04ef53` `[WEB-D2]` | 27-may | Docker + `serve.sh` + dist compilado del frontend |

Respaldo: `docs/cfd_m5_webapp.svg`.

## 6.7 Consolidación modular y ampliación de alcance *(junio 2026)*

### 6.7.1 Refactorización del prototipo a paquete `pipeline/` modular *(iteración)*
Reorganización de módulos ya construidos en 6.2–6.5; no es una fase nueva.

| Commit | Fecha | Aporta |
|--------|-------|--------|
| `68cd633` `[PIPE-T1]` | 19-jun | Tracking refactorizado: Kalman ball tracker, player tracker, dedup |
| `a34e38b` `[PIPE-D1]` | 19-jun | Mejora de detección y OCR de dorsal |
| `eb8f52d` `[PIPE-S1]` | 19-jun | Módulo de estrategia + refactor del resolver de posesión |
| `65806ab` `[PIPE-O1]` | 19-jun | Orquestador, config, E/S del pipeline y entrypoints |
| `6d083fb` `[PIPE-K1]` | 20-jun | Detector de keypoints KaliCalib + tooling |
| `38f7445` `[PIPE-POS2]` | 20-jun | Robustez de posesión ante oclusión y aglomeraciones |

Iteración revertida (bucle de retroalimentación CRISP-DM): segmentación de
sesiones SAM `10e1736` (intento, 14-jun) → `54ef5da` (revert, *"approach did
not work"*, 14-jun).

### 6.7.2 Nuevas capacidades (alcance descubierto) *(módulos nuevos)*
| Commit | Fecha | Aporta |
|--------|-------|--------|
| `087017b` `[PIPE-P1]` | 19-jun | Estimador de pose + detección de *release* de tiro |
| `3089f83` `[PIPE-3D1]` | 19-jun | Reconstrucción 3D del balón (método Pirotta) |
| `1018784` `[PIPE-TAC1]` | 20-jun | Reconocimiento de pantallas desde trayectorias |

### 6.7.3 Exposición en web y pruebas
| Commit | Fecha | Aporta |
|--------|-------|--------|
| `2248a5d` `[WEB-B7]` | 19-jun | API extendida: tracker mode + nuevos params del pipeline |
| `0ce835c` `[WEB-F7]` | 19-jun | Composable de tracker mode + vista de resultados |
| `4bf4677` `[WEB-B8]` | 20-jun | Endpoint `tactics.json` (pantallas reconocidas) |
| `cf63253` `[WEB-F8]` | 20-jun | Pantallas, trayectoria de tiro y tracker mode en la UI |
| `9e55140` `[TEST1]` | 19-jun | Scripts de evaluación + suite pytest |

## 6.8 Cierre y entrega final *(Hito m6, 25-jun)*

| Commit | Fecha | Aporta |
|--------|-------|--------|
| `349b335` / `fcf57b4` / `85a9f67` | 10–16-jun | Limpiezas: dead code, orquestador, imports, config |
| `846b27a` / `3198c8e` / `7f64742` | 16–20-jun | Renombrado a *basketball-visualizer* y reescritura del README |
| `5e1f2d9` `[DOC-CFD]` | 20-jun | CFD Kanban, progreso y figuras de homografía (generadores) |
| `ede5c66` `[DOC-TECH]` | 20-jun | Documentación de módulos tactics/3D + evidencia de resultados |
| `50e8b25` `[DOC-MEM]` | 20-jun | Documentos de apoyo a la redacción de la memoria |
| `f81889d` `[DOC-CFD]` | 22-jun | CFD rehecho como flujos paralelos (programación + documentación) |

Respaldo: `docs/cfd_m6_entrega.svg` y `docs/cfd.svg`.

## 6.9 Flujo de documentación en paralelo *(transversal)*

El CFD modela la documentación como **flujo continuo** (11 capítulos,
`DOC_START_DAY=5` en `generate_cfd_svg.py`), no como una fase final. Sección
breve que justifica, con el CFD completo (`docs/cfd.svg`), por qué la redacción
de la memoria avanzó en paralelo a la programación durante los 169 días del
proyecto.
