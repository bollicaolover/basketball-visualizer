# Plan de redacción del TFG — *basketball-visualizer*

> **Documento de trabajo.** Guía para escribir la memoria del TFG sobre la
> plantilla `TRABAJO FIN DE GRADO.docx`
> (`/home/gdfraile/tfg/tfg-baloncesto-tacticas/TRABAJO FIN DE GRADO.docx`).
>
> - **Autor:** Gonzalo del Fraile Andújar
> - **Director:** Dr. Daniel Valero Carreras
> - **Escuela:** EPS — Grado en Ingeniería Informática
> - **Fecha objetivo de entrega:** ~26 de junio de 2026
> - **Hoy:** 16 de junio de 2026 → **quedan ~10 días**
> - **Objetivo de extensión:** 80–90 páginas con gráficas, imágenes y tablas.

> ⚠️ **Aviso de coherencia (22 jun 2026).** Este es un **log de trabajo histórico**:
> sus entradas registran, por fecha, lo que se fue haciendo en el `.docx`, y por
> eso **no se reescriben**. Para evitar contradicciones, las **fuentes canónicas**
> vigentes son:
> - **Metodología:** *Kanban* (ágil, individual) — [`metodologia.md`](metodologia.md).
>   Las menciones a «CRISP-DM», «6 fases» o «Kanban + CRISP-DM» que aparezcan más
>   abajo quedan **superadas**; la metodología definitiva es Kanban con tablero en
>   **GitHub Projects** (no Notion).
> - **Cifras y cronología:** [`datos-reales-tfg.md`](datos-reales-tfg.md) — **61
>   commits** (08-ene → 22-jun), **65 tarjetas** en el tablero (61 `Hecho` + 4
>   `Por hacer`). Cualquier conteo anterior (43 commits, «Sprint 0–7», hashes
>   antiguos) está obsoleto.
> - **Capítulo 6:** [`desarrollo-cap6.md`](desarrollo-cap6.md), estructurado por
>   las **6 áreas funcionales** del tablero (no por fases CRISP-DM).
> - **Tablero:** [GitHub Projects #2](https://github.com/users/bollicaolover/projects/2).

---

## Registro de progreso

> El `.docx` vive en `/home/gdfraile/tfg/tfg-baloncesto-tacticas/TRABAJO FIN DE GRADO.docx`
> (servidor). El usuario edita en su PC Windows y **descarga** el archivo del
> servidor tras cada bloque (vía MobaXterm/SCP). No editar a la vez en ambos
> lados. Backup: `TRABAJO FIN DE GRADO.backup-20260616-1007.docx`.

- ✅ **16 jun** — Título cambiado (portada ×2) → *"Sistema de detección, seguimiento e identificación de jugadores de baloncesto y proyección táctica 2D"*.
- ✅ **16 jun** — Objetivos (1.3) reescritos: O1 RF-DETR+SAM3, O2 SigLIP+UMAP+K-means, O3 SmolVLM2+roster, O5 posesión+tiros, O6 multi-GPU, O7 vídeo anotado+minimapa. (O5 ya no es acciones por pose.)
- ✅ **16 jun** — Front matter + Capítulo 1 realineados: Resumen, Abstract, palabras clave (ES/EN), Introducción (párrafos de tecnologías) y Definición. Sin métricas inventadas.
- ✅ **16 jun** — Datos reales extraídos y medidos → [`datos-reales-tfg.md`](datos-reales-tfg.md): cronología de commits, OCR **85,26 %** (real, medido con `scripts/eval_jersey_ocr.py`), pipeline **0,7 fps / 1.402 ms-frame** con desglose por etapa, LoC, 11 clases RF-DETR. Confirmado: GNN/motor experto = ficheros vacíos.
- ✅ **17 jun** — **Capítulo 4 (Tecnologías) reescrito**: pila real (Python 3.10, PyTorch/OpenCV/supervision, RF-DETR/SAM3/SigLIP+UMAP+K-means/SmolVLM2, FastAPI, Vue 3+Vite, Docker, Git/GitHub, Roboflow/conda). Corregido "Persistencia: PostgreSQL" → **sistema de ficheros** (no usa BD). Anexo: Python 3.11+→3.10+. Formato etiqueta-negrita preservado.
- ✅ **17 jun** — **Capítulo 8 (Conclusiones) reescrito**: 8.1 O1–O8 cumplidos (pila real, 85,26%), 8.2 conclusiones técnicas reales, 8.3 vías futuras (pose/tácticas/GNN/recomendación/tiempo real/multideporte). Sin pila falsa.
- ✅ **17 jun** — **Capítulo 7 (Pruebas) reescrito** con métricas reales: plan de pruebas (unitarias pytest, integración e2e, eval OCR, validación funcional, smoke tests), indicadores medidos (OCR **85,26 %**, pipeline **1.402 ms/frame ≈0,7 fps** con desglose por etapa, validación funcional posesión/tiros), escalabilidad (chunking multi-GPU), formación. Sin números manuales. Eliminados YOLOv8/ByteTrack/PARSeq 96,8 %/pose del capítulo.
- ✅ **17 jun** — Corregida numeración duplicada (los estilos Ttulo1/2/3 **autonumeran**; había "6.1. 6.1."). Capítulo 6 regenerado **sin números manuales**. H1 del cap. 6 renombrado a **"DESARROLLO DEL PROYECTO"** (TOC + cuerpo). **Capítulo 5 reescrito** con datos reales: tamaño por LoC (~11.365), cronología real de commits por fase CRISP-DM (8 ene–16 jun), y costes estimados con supuestos explícitos (~4.800 € personal; infra A100 institucional; software libre). Verificado en PDF: numeración correcta. ⚠️ Lección: comprobar siempre numeración automática del estilo antes de añadir números manuales.
- ✅ **16 jun** — Capítulo 6 **rehecho (v2)** con la estructura CRISP-DM detallada pedida por el usuario: 6.1 Entendimiento Negocio y Datos (requisitos/KPIs, ingesta scripts, Roboflow), 6.2 Preparación (court/segments, smoothing, camera_model, homography, court.png FIBA), 6.3 Modelado (RF-DETR, SAM3 prompt-once + iteración revertida, SigLIP+UMAP+K-means, SmolVLM2+roster 85,26%, reglas posesión/tiros), 6.4 Ingeniería/Despliegue (FastAPI+orchestrator, chunking multi-GPU, Vue 3). Con notas de alineación Kanban/WIP y referencias a ficheros reales. 363 párrafos, resto del doc intacto.
- ⏯️ (v1 previo) — Capítulo 6 reorganizado a CRISP-DM: 6.1 Comprensión del negocio (requisitos RF/RNF corregidos + casos de uso), 6.2 Comprensión de los datos, 6.3 Preparación, 6.4 Modelado (arquitectura + 7 etapas reales del pipeline), 6.5 Evaluación (datos medidos + iteración SAM revertida), 6.6 Despliegue (CLI/web/UI/Docker/multi-GPU). Eliminados 6.5 Tácticas y 6.6 Recomendación. ⚠️ Incidente: el 1er intento ancló en el TOC y borró cuerpo de cap.1–5; recuperado desde backup 14:49 + reaplicado con guardas. Pendiente: renombrar el H1 "SIGUIENTES CAPÍTULOS…" y actualizar índices en Word.
- ✅ **16 jun** — Capítulo 2 reescrito: conceptos (SAM3, VLM, expert como futuro), proyectos afines, diferenciador, alcance (dentro/fuera), y **Tabla 1 + selección invertidas → gana RF-DETR + SAM 3** (antes elegía YOLOv8+ByteTrack). Pendiente menor: convertir "Tabla 1" en tabla real de Word; verificar citas (Fernández/Martínez/Ramírez) que parecen inventadas; el hardware (RTX 3080+Colab, L4468) sin tocar — confirmar el real (¿A100?).
- ✅ **16 jun** — Doc de apoyo Cap. 2 ampliado → [`estado-del-arte.md`](estado-del-arte.md) (conceptos + proyectos afines + 4 tablas de alternativas A–D con cifras medidas). **Tabla 1 del `.docx` convertida en tabla real de Word** (4 columnas, epígrafe con campo SEQ → entra en índice de tablas; fila "Decisión" marca B=Seleccionada). Backup `...backup-20260616-1449.docx`. ⚠️ Aún pendiente en el Word: en *Actualizar campos* para refrescar el índice de tablas; **verificar/sustituir las citas Fernández/Martínez/Ramírez** (posiblemente inventadas).
- ✅ **16 jun** — **Hardware real confirmado y corregido en el `.docx` (2.3 viabilidad)**: NO es RTX 3080 + Colab Pro. Es **este servidor**: Linux Ubuntu 22.04, **2× NVIDIA A100-SXM4-40GB (80 GB VRAM)**, 2× Intel Xeon Silver 4216 (32 núcleos), 376 GB RAM, CUDA 12.6. Entrenamiento e inferencia, todo en el servidor. Aplicar también en cap. 5 (costes: amortización servidor/A100, no RTX+Colab) y cap. 7. Ver memoria `tfg-hardware-entorno`.
- ✅ **16 jun** — **Cap. 3 (Metodología) realineado en el `.docx`**: estaba en **Scrum/sprints/Jira con stack falso** → reescrito a **Kanban + CRISP-DM** (WIP=1, GitHub Projects, 6 fases con cronología real de commits, iteración E-3 `10e1736`/`54ef5da`). Scrum/sprints quedan solo como alternativa descartada. UML: quitado "Jugada" del dominio. Validado.
- ✅ **16 jun** — **Cap. 4 (Tecnologías) — bloque "Modelos de IA empleados" realineado** en el `.docx`: YOLOv8/ByteTrack/clustering-color/PARSeq(96,8%)/ViTPose/ST-GCN/PoseConv3D → **RF-DETR + SAM 3 + SigLIP/UMAP/K-means + SmolVLM2 (85,26%) + keypoints de cancha**. PyTorch: justificación actualizada. Validado.
- ✅ **16 jun** — **Cap. 5 (Estimación de recursos) realineado en el `.docx`**: Story Points/Sprint 0-7 → **estimación por LoC reales (≈11.365) + esfuerzo por fases CRISP-DM (≈360 h)**; módulos con stack falso → componentes reales con LoC; planificación por **fases CRISP-DM** (no sprints) con hitos por fecha real; **costes** rellenados (placeholders eliminados): personal 7.200 €, amortización servidor 2× A100 1.650 €, energía 60 €, licencias 0 € → **≈8.910 €** (hipótesis indicadas). Validado.
- ✅ **16 jun** — **Apartado 2 ampliado con el estudio del usuario** (`TFG Análisis Baloncesto Inteligente.pdf`, 12 págs, 44 refs reales): **2.1 Conceptos** reescrito en prosa rica (baloncesto táctico; visión MOT/Re-ID/homografía; RF-DETR+DINOv2 con benchmarks; SAM→SAM2→SAM3 PCS/masklets/token de presencia; SigLIP pérdida sigmoidea; PARSeq→SmolVLM2; sistemas expertos→futuro). **2.2 Proyectos afines** ampliado (Hudl/Synergy, Second Spectrum con Hawk-Eye 2023-24; académicos: Fernández UPM, **Bolaños-Martínez** UGR, Ramírez UPV) + **Tabla 3 real** (8 dimensiones × 3 enfoques, TFG resaltado). Citas sin verificar sustituidas por la versión del estudio. Validado.
- ✅ **16 jun** — **Bibliografía (Cap. 9) rehecha en el `.docx`**: placeholders `[REFERENCIA N]` y cita PARSeq inventada ("Bautista, R., Gimeno, F., Pozo, F.") → **21 referencias reales en APA 7**, alfabéticas (Anderson/Kanban, Bautista&Atienza/PARSeq real, Carion/DETR, FastAPI, Genius Sports/Second Spectrum, Hudl, Jocher/YOLOv8, Kirillov/SAM, Marafioti/SmolVLM2, Meta AI/SAM3 arXiv 2511.16719, Oquab/DINOv2, Pressman, PyTorch, Ravi/SAM2, Redmon/YOLOv3, Roboflow/RF-DETR, Sommerville, Vue.js, Wirth/CRISP-DM, Zhai/SigLIP, Zhang/ByteTrack). Validado. ⚠️ Citas Fernández (UPM) y Ramírez (UPV) del cap. 2 siguen con respaldo débil; Bolaños-Martínez (UGR) sí real. Pendiente: el usuario debe **citar en el texto** ("Actualizar campos") y, si usa numeración, enlazar.
- ⏳ **PENDIENTE en el `.docx` (stack falso aún presente, líneas del texto extraído):**
  - ✅ **Cap. 6 (Desarrollo) realineado** (16 jun): 6.4 pipeline reescrito a la pila real (RF-DETR→SAM3 prompt-once→SigLIP/UMAP/K-means→SmolVLM2→homografía PnP→posesión→tiros + orquestador); RF-05/RF-06 (tácticas/recomendación, no construidas)→posesión/tiros/roster; RNF-01 "tiempo real"→por lotes 0,7 fps; RNF-02→OCR 85,26%; CU-05/06→roster/historial; 6.3 arquitectura→3 piezas reales (Vue+FastAPI+pipeline subproceso, multi-GPU); **6.5 "Reconocimiento de tácticas"→"Resolución de posesión y detección de tiros"**; **6.6 "Motor de recomendación"→"Backend e integración multi-GPU"**; intro y 6.7 sin pose/acciones. 0 stack falso. Validado.
  - ✅ **Cap. 7 (Pruebas) realineado** (16 jun): intro despliegue (Docker, FastAPI sirve front + subproceso por GPU); plan de pruebas → **suite pytest real** (chunking, posesión, homografía, roster) + integración sobre test_videos + eval OCR; indicadores → **métricas reales** (OCR 85,26% 266/312, 1,4 s/frame 0,7 fps, OCR 39%/SAM3 30%, VRAM 7,8 GB, speedup 1,48×); escalabilidad → multi-GPU chunking; formación sin "tácticas/recomendaciones"; quitado "Tabla 3" literal. 0 stack falso. Validado.
  - ✅ **Cap. 8 (Conclusiones) realineado** (16 jun): intro sin "sistemas expertos"; **objetivos alcanzados → los 8 objetivos (O1-O8) cumplidos con la pila real** (RF-DETR, SAM3, SigLIP/UMAP/K-means, SmolVLM2 85,26%, homografía, posesión/tiros, multi-GPU, web, validación); conclusiones técnicas → RF-DETR/SAM3 + cuellos OCR 39%/SAM3 30% + arquitectura 3 piezas (no microservicios/razonamiento simbólico); vías futuras + pose (ViTPose/ST-GCN) como futuro. Validado.

### ✅ REALINEADO TECNOLÓGICO COMPLETO (16 jun)
Verificación global case-sensitive: `mAP/IDF1/top-1/96,8%/ST-GCN/ViTPose/PoseConv3D` = **0 en el cuerpo** (solo 1 mención legítima en Cap. 8 vías futuras). `YOLOv8/ByteTrack/PARSeq` solo en Cap. 2 (alternativas/estado del arte) y Bibliografía. **Todo el `.docx` describe ya la pila real (RF-DETR · SAM 3 · SigLIP · SmolVLM2) de principio a fin.** Caps. 2,3,4,5,6,7,8,9 realineados y validados.

⚠️ **Pendiente del usuario en Word (Windows):** *Actualizar campos* (índices general/tablas + 4 tablas SEQ); citar en texto las referencias del cap. 9; verificar citas Fernández (UPM)/Ramírez (UPV); generar figuras pendientes (Gantt, diagramas, capturas).
  - **Cap. 2**: refs PARSeq/YOLO+ByteTrack (~430/460/472) son OK como estado del arte; ⚠️ verificar citas Fernández/Martínez/Ramírez (posiblemente inventadas).
  - **Cap. 5**: el Gantt sigue siendo un placeholder → generar la figura (fases CRISP-DM sobre fechas reales de commits).
- ✅ **16 jun** — Pruebas (Cap. 7): suite **pytest** creada en [`tests/`](../tests/) (22 tests: chunking, posesión, homografía, roster), `pytest.ini`. **VRAM y multi-GPU medidos** ([`scripts/measure_performance.py`](../scripts/measure_performance.py) → [`perf-results.json`](perf-results.json)): 7,8 GB VRAM pico en 1× A100; speedup **1,48×** en 2× A100. Volcado en [`datos-reales-tfg.md` §5](datos-reales-tfg.md). Corregido hash del revert E-3 en `metodologia.md` (`54ef5da`).

### ⚠️ Pendiente de realineado tecnológico (resto del documento)

Todavía describen la pila falsa (YOLOv8/ByteTrack/PARSeq/ViTPose/ST-GCN/PoseConv3D/pose).
Conteo restante en el doc: YOLOv8 ×11, ByteTrack ×11, PARSeq ×11, ST-GCN ×8, PoseConv3D ×8, ViTPose ×5.

| Sección | Qué corregir | Notas |
|---|---|---|
| 2.1 Conceptos | PARSeq → VLM (SmolVLM2) | concepto OCR |
| 2.2 Proyectos afines | refs YOLO+ByteTrack, PARSeq | mantener como estado del arte/alternativas, no como "lo usado" |
| **2.3 Alternativas (Tabla 1 + selección)** | **invierte el ganador**: hoy elige "YOLOv8+ByteTrack" descartando "RF-DETR+SAM2". Debe **seleccionar RF-DETR + SAM 3** | crítico: contradice el código |
| 2.3 Alcance | quitar "acciones por pose" | |
| 5 Planificación | sprints (5087), tecnologías PyTorch (5233), modelos (5263), estimación módulos (5599/5613) | usar fechas reales de commits; sin pose |
| 6 Desarrollo | pasos del pipeline (6263), módulo acciones (6334) | 6.4 = etapas reales; acciones → vías futuras |
| 7 Pruebas | indicadores (6509) | sin top-1 de acciones; métricas reales o marcadas |
| 8 Conclusiones | 6664 (objetivos alcanzados), 6692 (técnicas) | reescribir con la pila real |
| 9 Bibliografía | ref PARSeq (6800) | quitar si no se cita, o dejar en alternativas |
| Métricas inventadas | "96,8 %" y similares | NO inventar: extraer de `train_jersey.log`/`run_full.log` o marcar como pendiente |

---

### ✅ Alineación tecnológica COMPLETA (17 jun)

Todos los capítulos (Resumen/Abstract, 1–8) reescritos a la pila real con datos
medidos. Verificación final: RF-DETR ×26, SAM 3 ×24, SigLIP ×18, SmolVLM2 ×15,
CRISP-DM ×21, Kanban ×16. Pila falsa eliminada salvo menciones legítimas
(YOLOv8/ByteTrack/PARSeq solo en Cap. 2 como alternativas/estado del arte y en
la referencia PARSeq de bibliografía; "Scrum" en la comparativa del Cap. 3).
ViTPose/ST-GCN/PoseConv3D/PostgreSQL/Jira → 0. Numeración de encabezados
verificada por PDF (sin duplicados). H1 del Cap. 6 → "DESARROLLO DEL PROYECTO".

**Figuras generadas (17 jun)** en `tfg-baloncesto-tacticas/figuras/` (PNG 200 dpi, datos reales):
- `fig_ocr_loss.png` — curva de pérdida del OCR (→ 6.3.4 / 7.2)
- `fig_latencias_etapa.png` — desglose de tiempos por etapa (→ 6.5 / 7.2)
- `fig_gantt.png` — cronología CRISP-DM+Kanban (→ 5.2)
- `fig_arquitectura.png` — 3 servicios desacoplados (→ 6.4.1)
- `fig_pipeline.png` — etapas del pipeline por frame (→ 6.4)
- `fig_crispdm.png` — 6 fases con iteración (→ 3.2 / 6 intro)
- `fig_casos_uso.png` — diagrama UML de casos de uso (→ 6.1.3)

**Frames anotados reales (17 jun)** — clip Celtics-Knicks procesado con roster (nombres: Brunson, Anunoby, Dadiet, Pritchard):
- `frame_overlay_f100.png` — vídeo anotado: cajas por equipo, dorsales #8/#11, cancha proyectada, evento "CANASTA" (→ 6.4.2/6.4.5)
- `frame_overlay_f78.png` — variante con más jugadores detectados
- `frame_map_f100.png` — minimapa cenital 2D con jugadores+dorsales+balón (→ 6.4.6)
- `frame_deteccion_f78.png` / `_f100.png` — **detección RF-DETR limpia** (solo cajas + clase + confianza, sin overlay del sistema) (→ 6.4.2)
- Nota: el verde de la cancha y el recuadro negro abajo-dcha NO los dibuja el pipeline — están en el vídeo broadcast original (publicidad virtual proyectada + marcador de TV tapado).

**Capturas de la app web (17 jun)** — vía Playwright+Chromium headless contra el backend local (job real con roster):
- `app_1_login.png` — pantalla de acceso (BASKET2D) (→ 6.6.3)
- `app_2_upload.png` — estado de subida / propuesta de valor + 3 pasos (→ 6.6.3)
- `app_3_resultados.png` — vista de resultados: clips + vídeo procesado (cajas/equipos/dorsales/controles/filtros) + esquema 2D (→ 6.6.3 / 6.4.6 / 7)

**Pendiente (NO es alineación; es contenido/forma):**
1. En Word: **Referencias → Actualizar tabla** (índice general + índices de figuras/tablas).
2. ✅ **14 figuras insertadas en el .docx (17 jun)** con pie autonumerado (campo SEQ "Figura", entran en el índice de figuras): CRISP-DM, casos de uso, Gantt, pipeline, detección RF-DETR, vídeo anotado SAM, UMAP equipos, curva OCR, homografía/minimapa, arquitectura, login+subida+resultados (app), latencias. Imágenes embebidas y centradas, validado. (Omitidas 2 casi-duplicadas: overlay_f78, deteccion_f100.) ✅ **4 tablas reales de Word creadas (17 jun)** con caption SEQ "Tabla": Tabla 1 (comparativa de alternativas, cap. 2), Tabla 2 (LoC por componente, cap. 5), Tabla 3 (cronología por fase, cap. 5), Tabla 4 (indicadores de desempeño medidos, cap. 7). Cabecera sombreada + bordes, validado. **Documento final: 14 imágenes + 4 tablas embebidas.**
3. ✅ **Bibliografía rehecha (17 jun)** — 19 referencias reales verificadas en APA 7 (orden alfabético), estilo "Referencias": RF-DETR (Robinson 2025, arXiv 2511.09554), SAM/SAM2/SAM3 (Kirillov 2023 / Ravi 2024 / Carion 2025, arXiv 2511.16719), SigLIP (Zhai 2023), SmolVLM (Marafioti 2025, arXiv 2504.05299), UMAP, DETR, PARSeq (Bautista &amp; Atienza, coautores corregidos), ByteTrack, YOLOv8, scikit-learn, PyTorch, CRISP-DM, Hartley&amp;Zisserman, Pressman, Sommerville, FastAPI, Vue. Eliminados placeholders y refs inventadas. ✅ Las citas inventadas del cuerpo del Cap. 2 (Fernández/Martínez/Ramírez) **sustituidas (17 jun)** por referencias reales de la bibliografía (YOLO, DETR, RF-DETR, ByteTrack, SAM, PARSeq, homografía). **Ya no queda ninguna cita inventada en el documento.**
4. ✅ **Hardware (2.3) corregido (17 jun)** → "servidor con dos GPU NVIDIA A100 de 40 GB" (eliminado RTX 3080 + Colab).
- ✅ **Figura UMAP (17 jun)** `fig_umap_equipos.png` — proyección UMAP 2D de 357 descriptores SigLIP reales, dos clusters separados (equipos), K-means k=2 (→ 6.3.3).
5. ✅ **Lista de abreviaturas rellenada (17 jun)** — 24 siglas reales del TFG en orden alfabético (API, CNN, CRISP-DM, DETR, FPS, GPU, HTTP, IA, IoS, JSON, LoC, mAP, MOT, OCR, RF-DETR, RGPD, ROI, SAM, SPA, UMAP, UML, VLM, VRAM, WIP). Eliminados los placeholders. (El "Lorem ipsum" de Agradecimientos es opcional/personal: lo escribe el autor.)

### ✅ Patrones de excelencia "TFG de 10" aplicados (17 jun)
Inspirado en la memoria del compañero (Marín, sobresaliente):
1. **Historias de usuario** (HU-1…HU-5, formato «Como…quiero…para…») en 6.1 + **«Revisión y lecciones aprendidas»** (6.5) con la iteración SAM revertida y el WIP.
2. **Rigor matemático**: ecuaciones OMML nativas de la **homografía** (matriz 3×3 + deshomogeneización) + método **DLT/SVD/RANSAC** en 6.2.2. Renderizado verificado.
3. **Viaje del usuario** (tabla Etapa/Vista/Acción) en 6.4.3.
4. **Anexos técnicos**: tabla **diccionario de las 11 clases RF-DETR** + tabla **esquema JSON de metadatos** (diccionario de datos). 
Documento: 14 imágenes + **7 tablas** + ecuaciones nativas.

---

## 0. Decisión previa imprescindible: alinear memoria ↔ proyecto real

La plantilla `.docx` ya trae redactados título, objetivos, resumen y estado del
arte describiendo un sistema **que no es el que has construido**. Hay que
resolver esto antes de escribir una línea más, porque afecta a TODO el documento.

| Tema | Lo que dice la plantilla | Lo realmente implementado | Acción en la memoria |
|---|---|---|---|
| Título | "Sistema experto para el **reconocimiento de tácticas** en tiempo real" | Análisis/visualización táctica automatizada (no reconoce tácticas) | **Cambiar título** a algo como *"Aplicación web para el análisis automático de vídeos de baloncesto mediante visión por computador"* |
| Detección | YOLOv8 | **RF-DETR** (11 clases, incl. `player-in-possession`) | Reescribir |
| Tracking | ByteTrack | **SAM 3** (segmentación, prompt-once + re-prompt) | Reescribir |
| OCR dorsal | PARSeq | **SmolVLM2** fine-tuneado localmente | Reescribir |
| Clasificación equipos | clustering de color | **SigLIP + UMAP + K-means** (sin etiquetas) | Reescribir |
| Proyección 2D | homografía por keypoints | igual ✅ | Mantener |
| Posesión / tiros | — | **resolver de posesión (histéresis)** + shot tracker | Añadir (es trabajo real hecho) |
| O5: reconocimiento de acciones (pose ST-GCN/PoseConv3D) | sí | **NO hecho** | → mover a *Vías futuras*; quitar de objetivos |
| 6.5 Reconocimiento de tácticas / 6.6 Motor de recomendación | sí | **NO hecho** | → reemplazar esas subsecciones por las etapas reales del pipeline |
| "en tiempo real" | sí | procesado por lotes (batch), multi-GPU | Quitar "tiempo real"; hablar de rendimiento por lotes |
| Despliegue | — | CLI + **app web Vue 3 + FastAPI**, contenedor reproducible (Apptainer), multi-GPU | Es un punto fuerte: explotarlo |

**Regla de oro:** la memoria debe describir lo que el tribunal puede ejecutar y
ver en el código. Todo lo no construido (acciones por pose, motor de tácticas,
recomendación, tiempo real) va a **8.3 Vías futuras**, presentado como evolución
natural, no como algo prometido y no cumplido. Esto es honesto, defendible y
sube nota (muestra criterio de alcance).

> **Fuentes de verdad para reescribir:** [`README.md`](../README.md),
> [`docs/arquitectura.md`](arquitectura.md), [`docs/metodologia.md`](metodologia.md)
> y el código de [`pipeline/`](../pipeline/).

---

## 1. Estructura del documento (según la plantilla) y presupuesto de páginas

La plantilla fija el índice. Objetivo ~85 págs de contenido (1–8) + preliminares
+ anexos. Reparto sugerido:

| Cap. | Sección (plantilla) | Págs. | Peso |
|---|---|---|---|
| — | Portada, agradecimientos, abreviaturas, índices | 6–8 | preliminar |
| — | **Resumen / Abstract** + palabras clave | 1–2 | preliminar |
| 1 | **Introducción** (motivación, definición, objetivos) | 5–6 | medio |
| 2 | **Estado del arte** (conceptos, proyectos afines, viabilidad) | 12–14 | **alto** |
| 3 | **Metodologías usadas** (CRISP-DM + Kanban) | 6–8 | medio |
| 4 | **Tecnologías y herramientas** | 6–8 | medio |
| 5 | **Estimación de recursos y planificación** (Gantt, costes) | 6–8 | medio |
| 6 | **Desarrollo** (análisis, diseño, soluciones) | **28–34** | **el núcleo** |
| 7 | **Despliegue y prueba** (plan de pruebas, métricas, etc.) | 8–10 | alto |
| 8 | **Conclusiones** (objetivos, conclusiones, vías futuras) | 4–5 | medio |
| 9 | **Bibliografía** | 2–3 | — |
| 10 | **Anexos** (manual instalación + usuario) | 5–8 | — |
| | **TOTAL aprox.** | **~90** | |

El capítulo 6 es ~⅓ del documento: ahí va el grueso de figuras y la
justificación técnica. No infles los demás con relleno; infla 6 con sustancia.

---

## 2. Qué escribir en cada capítulo (con figuras y fuente del contenido)

### Resumen / Abstract
- Ya hay borrador en la plantilla, pero **corregir tecnologías** (RF-DETR, SAM 3,
  SigLIP, SmolVLM2; no YOLOv8/ByteTrack/PARSeq). Un párrafo único cada uno.
- Palabras clave: *Visión por computador; Detección de objetos (RF-DETR);
  Segmentación y seguimiento (SAM 3); Clasificación de equipos (SigLIP);
  Reconocimiento de dorsales (VLM); Homografía; Aplicación web.*

### Cap. 1 — Introducción (5–6 pp)
- **Motivación**: pasión baloncesto + IA; coste del análisis manual; democratizar
  el análisis con hardware accesible. (Hay borrador reutilizable.)
- **Definición**: qué es la app — entrada vídeo → vídeo anotado + minimapa 2D.
- **Objetivos**: reescribir O1–O8. **Quitar O5 (acciones por pose)**. Dejar:
  - O1 detección+tracking con identidad temporal (RF-DETR + SAM 3)
  - O2 clasificación por equipo sin etiquetas (SigLIP+UMAP+K-means)
  - O3 OCR de dorsal (SmolVLM2 fine-tuned) + resolución de nombre vía roster
  - O4 proyección 2D por homografía
  - O5 (nuevo) resolución de posesión y detección de tiros
  - O6 selección de hardware (GPU/VRAM) desde la web; procesado multi-GPU
  - O7 integrar todo en una app web usable (subida, progreso, visualización)
  - O8 validar con vídeos representativos (precisión, latencia, utilidad)
- **Figura 1**: diagrama de bloques del sistema (puedes regenerar el ASCII del
  README como figura vectorial). **Figura 2**: captura de la app con resultado.

### Cap. 2 — Estado del arte (12–14 pp) — capítulo "de lectura"
- **2.1 Conceptos del dominio** (hay borrador; reorganizar en 3 bloques):
  baloncesto (posesión, jugada, sistemas of/def), visión (detección, MOT, re-ID,
  homografía), modelos (CNN vs transformers: YOLO/Faster R-CNN vs DETR/RF-DETR;
  SAM/SAM2/SAM3; SigLIP; VLMs para OCR en escena).
- **2.2 Proyectos afines**: Hudl/Synergy, Second Spectrum/Stats Perform, Roboflow
  sports, TFGs YOLO+ByteTrack. **Diferenciador**: pipeline completo integrado en
  una web, con modelos entrenados/ajustados localmente (sin inferencia alojada).
- **2.3 Viabilidad**: alcance (dentro/fuera — aquí dejas claro que tácticas y
  acciones quedan fuera), situación actual, alternativas (p.ej. RF-DETR vs YOLOv8,
  SAM3 vs ByteTrack, VLM vs PARSeq) y **selección justificada**. Esto conecta con
  CRISP-DM *Business/Data Understanding*.
- **Figuras**: tabla comparativa de soluciones comerciales/académicas; tabla de
  alternativas técnicas con criterios (precisión, latencia, dependencia de cloud,
  esfuerzo de etiquetado) y la elegida resaltada.

### Cap. 3 — Metodologías (6–8 pp) — **ya casi escrito en `docs/metodologia.md`**
- Volcar y ampliar [`docs/metodologia.md`](metodologia.md): CRISP-DM (6 fases) +
  Kanban (WIP=1). Es uno de tus puntos fuertes porque tienes **trazabilidad a
  commits**.
- **Figura**: diagrama de las 6 fases CRISP-DM con la flecha de iteración (E-3).
- **Figura**: captura del tablero GitHub Projects (columnas = fases).
- **Tabla**: el mapeo tarjeta → fase → commit (ya está en el .md). 
- ⚠️ Revisa que los hashes/labels de commits del .md coincidan con el repo real
  antes de incluirlos (un tribunal puede comprobarlos).

### Cap. 4 — Tecnologías y herramientas (6–8 pp)
- Tabla del stack (está en el README): PyTorch, RF-DETR, SAM 3, SigLIP, SmolVLM2,
  Ultralytics, `supervision`, UMAP, scikit-learn / FastAPI, Uvicorn / Vue 3,
  Vite, Node 20 / Roboflow (datasets), Apptainer, conda, Git+GitHub.
- Para cada bloque: **qué es y por qué se eligió** (1–2 frases). Incluye versión.
- **Figuras**: logos/tabla por capas (ML / Backend / Frontend / Datos / DevOps).

### Cap. 5 — Estimación de recursos y planificación (6–8 pp)
- **5.1 Estimación**: por puntos función o por líneas de código. Puedes contar
  LoC reales del repo (`cloc` o `git ls-files | xargs wc -l`) y presentarlo por
  módulo. Menciona COCOMO básico como referencia.
- **5.2 Planificación temporal**: **diagrama de Gantt** derivado del historial de
  commits/fases CRISP-DM (fechas reales de los commits). Es la forma más honesta
  y rápida de hacerlo.
- **5.3 Costes**: horas de dedicación × coste/hora becario + amortización GPU
  (RTX local) + Colab Pro + horas de cómputo de entrenamiento (tienes los logs:
  `train_jersey.log`, `run_full.log`). Tabla de costes directos/indirectos.
- **Figuras**: Gantt, tabla de esfuerzo por módulo, tabla de costes.

### Cap. 6 — Desarrollo (28–34 pp) — **EL NÚCLEO** (ver §3)
Detallado abajo. Organizar por las **etapas reales del pipeline**, no por las
subsecciones de la plantilla (6.5/6.6 no aplican).

### Cap. 7 — Despliegue y prueba (8–10 pp)
- **7.1 Plan de pruebas**: tests del backend ([`backend/tests/`](../backend/tests/)),
  pruebas funcionales de extremo a extremo con los vídeos de `data/test_videos`,
  validación cualitativa (capturas anotadas) y cuantitativa donde haya ground
  truth (precisión de detección, aciertos de OCR, % de IDs correctos).
- **7.2 Indicadores**: latencia por frame / FPS, tiempo total por clip, uso de
  VRAM, escalado multi-GPU (speedup con chunking). Saca números reales de los
  logs y del `profiling.py`.
- **7.3 Escalabilidad/mantenimiento**: arquitectura modular, multi-GPU con
  `chunking.py`, contenedor reproducible (Apptainer), separación pipeline/backend/frontend, convenciones de
  código (de `arquitectura.md`).
- **7.4 Formación de usuarios**: breve; remite al manual de usuario (anexo).
- **Figuras**: gráfica de latencia/FPS, gráfica de speedup multi-GPU, tabla de
  resultados de pruebas, capturas de la app procesando.

### Cap. 8 — Conclusiones (4–5 pp)
- **8.1 Objetivos alcanzados**: tabla O1–O8 → estado (cumplido/parcial) con
  evidencia. Honesto: lo no hecho no estaba entre los objetivos (porque lo
  quitaste en el cap.1).
- **8.2 Conclusiones técnicas y personales**.
- **8.3 Vías futuras**: **aquí** colocas reconocimiento de acciones por pose
  (ST-GCN/PoseConv3D), motor de tácticas (sistema experto), recomendación,
  tiempo real, multicámara, captura en directo. Bien presentado, es valor.

### Cap. 9 — Bibliografía (2–3 pp)
- Estilo IEEE o APA (mira cuál usan los ejemplos de tus compañeros). Papers:
  DETR/RF-DETR, SAM/SAM2/SAM3, SigLIP, SmolVLM, UMAP, homografía deportiva,
  ByteTrack/PARSeq (como alternativas del estado del arte). Gestor: Zotero/Mendeley.

### Cap. 10 — Anexos (5–8 pp)
- **10.1 Manual de instalación**: basado en README (conda, `fetch_models.py`,
  Node 20 local, `serve.sh`, Apptainer).
- **10.2 Manual de usuario**: flujo de la app web con capturas (subir vídeo →
  GPU → progreso → resultados → roster).
- **10.3 Otros**: formato del roster JSON, opciones de la CLI, estructura de
  `metadata.json`.

---

## 3. Cap. 6 en detalle — "Desarrollo según la metodología (CRISP-DM)"

El enunciado pide describir el desarrollo **según la metodología**. La forma
ganadora: estructurar el capítulo siguiendo las **fases CRISP-DM**, y dentro de
cada fase, las tarjetas Kanban (módulos) con su diseño y solución. Así el cap. 6
"demuestra" la metodología del cap. 3 en lugar de solo describirla.

Estructura propuesta para el cap. 6 (sustituye a 6.1–6.7 de la plantilla):

- **6.1 Análisis de requisitos** (funcionales + no funcionales) y **casos de uso**
  (subir vídeo, configurar GPU, visualizar resultados, gestionar roster).
  - Figuras: diagrama de casos de uso (UML), tabla de requisitos.
- **6.2 Arquitectura del sistema** (de `arquitectura.md`): 3 piezas
  (frontend / backend / pipeline), flujo de datos, decisión de no usar Celery/Redis.
  - Figuras: diagrama de arquitectura, diagrama de despliegue, diagrama de secuencia
    "subida → job → resultado".
- **6.3 Data Understanding & Preparation**: datasets (Roboflow), 11 clases del
  detector, dataset de dorsales NBA, preparación para el fine-tuning.
  - Figuras: muestras del dataset, distribución de clases, ejemplos de dorsales.
- **6.4 Modeling — pipeline de visión, etapa por etapa** (el corazón):
  1. **Detección RF-DETR** (11 clases): qué detecta, por qué RF-DETR vs YOLO.
  2. **Tracking SAM 3** (prompt-once + re-prompt; problema de deriva en vídeos
     largos → iteración E-3 de CRISP-DM). 
  3. **Clasificación de equipos** SigLIP + UMAP + K-means (sin etiquetas; voto
     por track).
  4. **OCR de dorsal** SmolVLM2 fine-tuneado (voto por IoS) + roster → nombre.
  5. **Homografía de cancha** (keypoints → matriz H → estabilización → render 2D).
  6. **Tracking de balón y resolución de posesión** (histéresis temporal).
  7. **Shot tracker** (eventos de canasta).
  8. **Orquestador** por frame que une todo (`orchestrator.py`).
  - Figuras por etapa: frame con cajas/clases; máscaras SAM; proyección UMAP 2D
    de embeddings con los clusters de equipo; recorte de dorsal + predicción;
    keypoints + cancha rectificada; minimapa 2D; diagrama de estados de posesión.
- **6.5 Interfaz de usuario (frontend)**: SPA Vue 3, composables, capa
  interactiva sincronizada por frame, minimapa.
  - Figuras: wireframe/capturas de Login, Upload, Results; estructura de
    componentes.
- **6.6 Backend e integración**: FastAPI, jobs en background + subprocess,
  lock por GPU, multi-GPU con chunking, servir el frontend compilado.
  - Figuras: diagrama de endpoints, secuencia multi-GPU (split → procesar →
    recombinar).

> Para cada etapa usa el patrón: **problema → alternativas → solución elegida →
> resultado (figura)**. Esto encaja con CRISP-DM y se lee como ingeniería, no
> como tutorial.

---

## 4. Inventario de figuras/gráficas a generar (objetivo: 30–45 elementos)

Un TFG de 85 pp con buena nota lleva ~1 figura cada 2–3 páginas. Lista de
producción (marca según las vayas haciendo):

**Capturas de la app** (las más rápidas y vistosas)
- [ ] Pantalla de login
- [ ] Panel de subida + selección de GPU
- [ ] Modal de progreso (tareas + hardware)
- [ ] Vista de resultados: vídeo anotado + minimapa 2D
- [ ] Capa interactiva de cajas con nombres/equipos

**Salidas del pipeline** (frames exportados)
- [ ] Frame con detecciones RF-DETR (cajas + clases)
- [ ] Frame con máscaras SAM 3
- [ ] Frame con equipos coloreados + dorsal + nombre
- [ ] Cancha: keypoints detectados sobre el frame
- [ ] Minimapa cenital 2D con posiciones
- [ ] Secuencia mostrando seguimiento de identidad en N frames

**Diagramas** (hazlos vectoriales: draw.io / Mermaid / PlantUML)
- [ ] Bloques del sistema (pipeline ML)
- [ ] Arquitectura 3 piezas (front/back/pipeline)
- [ ] Despliegue + secuencia subida→job→resultado
- [ ] Casos de uso (UML)
- [ ] 6 fases CRISP-DM + iteración
- [ ] Diagrama de estados de posesión
- [ ] Estructura de componentes del frontend

**Gráficas de datos** (matplotlib, desde logs reales)
- [ ] Curva de entrenamiento del OCR (loss/acc) — de `train_jersey.log`
- [ ] Distribución de clases del dataset de detección
- [ ] Proyección UMAP de embeddings de equipo (2D, coloreada por cluster)
- [ ] Latencia/FPS por etapa del pipeline (de `profiling.py`)
- [ ] Speedup multi-GPU (1 vs 2 vs N GPUs)
- [ ] Gantt del proyecto (fechas de commits)

**Tablas**
- [ ] Comparativa soluciones (cap.2)
- [ ] Alternativas técnicas y selección (cap.2)
- [ ] Stack tecnológico (cap.4)
- [ ] Esfuerzo por módulo + costes (cap.5)
- [ ] Tarjeta→fase→commit (cap.3, ya hecha)
- [ ] Requisitos funcionales/no funcionales (cap.6)
- [ ] Resultados de pruebas + objetivos alcanzados (cap.7/8)

> Cada figura/tabla **numerada y referenciada en el texto** ("ver Figura 12"),
> con pie de figura. La plantilla ya prepara los índices de Figura/Tabla/Imagen:
> usa los rótulos correctos (Referencias > Insertar título) para que se
> autogeneren.

---

## 5. Calendario sugerido (10 días, 16–26 junio)

Asume ~4–6 h/día. Escribe primero lo que ya tienes material (3, 6) y deja pulido
para el final.

| Día | Fecha | Tarea |
|---|---|---|
| 1 | 16 jun | **Decisión de alcance (§0)**: cambiar título, reescribir objetivos. Corregir Resumen/Abstract. Listar abreviaturas. |
| 2 | 17 jun | Cap. 3 (Metodología) — volcar y ampliar `metodologia.md`. Verificar commits. Generar diagramas CRISP-DM + Gantt base. |
| 3 | 18 jun | Cap. 6.1–6.3 (requisitos, casos de uso, arquitectura, datos) + diagramas. |
| 4 | 19 jun | Cap. 6.4 etapas 1–4 (detección, tracking, equipos, OCR) + capturas/figuras. |
| 5 | 20 jun | Cap. 6.4 etapas 5–8 + 6.5/6.6 (homografía, posesión, frontend, backend) + figuras. |
| 6 | 21 jun | **Generar TODAS las figuras pendientes** (capturas app, frames, gráficas matplotlib desde logs). |
| 7 | 22 jun | Cap. 2 (Estado del arte) — el más "de escribir". + Cap. 4 (Tecnologías). |
| 8 | 23 jun | Cap. 5 (planificación/costes) + Cap. 7 (pruebas, métricas reales). |
| 9 | 24 jun | Cap. 1 final, Cap. 8 (conclusiones + vías futuras), Bibliografía, Anexos. |
| 10 | 25 jun | **Revisión global**: numeración, índices automáticos, pies de figura, ortografía, coherencia tecnologías, páginas impares, formato. Exportar PDF. |
| — | 26 jun | Margen / entrega. |

---

## 6. Checklist de calidad antes de entregar

> Estado verificado el 17 jun contra el `.docx` real (no contra el registro).

- [x] **Coherencia tecnológica** — ✅ verificado: 0 menciones de ViTPose/ST-GCN/PoseConv3D/PostgreSQL/Jira/"96,8"/"RTX 3080"/Colab en el cuerpo; "tiempo real" solo como *no* tiempo real / vía futura. YOLOv8/ByteTrack/PARSeq solo en cap. 2 (estado del arte) y bibliografía.
- [x] **Título/portada/cabeceras** — ✅ portada (×2) y ✅ **cabeceras arregladas** (placeholder "Título del capítulo" → campo STYLEREF que muestra el título del capítulo al actualizar campos; también se corrigió que la cabecera mostraba la gráfica de latencias por un bug, logo UCAM restaurado).
- [x] **Objetivos cap.1 ↔ cap.8** — ✅ verificado: O1–O8 todos cerrados en 8.1.
- [~] **Figura/tabla numerada + pie + citada** — ✅ numeradas y con pie (14 figuras SEQ "Figura", 4 tablas SEQ "Tabla"); colocadas en contexto. Cita explícita en texto: Tablas 2/3 citadas ("La Tabla N…"); figuras con 3 refs explícitas. *Mejora opcional del usuario*: añadir referencias cruzadas (Insertar > Referencia cruzada) a las demás.
- [ ] **Índices actualizados** — ⏳ **acción del usuario en Word**: Ctrl+E → F9 → "Actualizar toda la tabla"; e Insertar tabla de ilustraciones (rótulos "Figura" y "Tabla"). No se puede hacer en el servidor (los campos se recalculan al abrir en Word).
- [x] **Primeras páginas de capítulo en impar** — ✅ verificado: 16 saltos de sección `oddPage` (la plantilla ya lo fuerza).
- [~] **Sangría** — gobernada por los estilos de la plantilla (Párrafo base); los párrafos insertados usan esos estilos. *Verificar manualmente* la nota de Introducción (sangría solo 1.ª línea).
- [x] **Bibliografía consistente + citada** — ✅ 19 refs APA 7 coherentes; las fuentes técnicas se citan en el cuerpo del cap. 2. (Si se exige cita numérica/autor-año en todo el texto, ampliar manualmente.)
- [x] **Hashes commits cap.3** — ✅ verificado en el repo `tfg-junio`: `10e1736` y `54ef5da` existen (iteración E-3).
- [ ] **Revisión TFGs de ejemplo** — ⏳ tarea de criterio del autor (puedo extraer su estructura/longitud para comparar si se desea).
- [ ] **Ortografía/gramática** — ⏳ pendiente de una lectura final con corrector (el contenido insertado se revisó, pero conviene un repaso completo en Word).

---

## 7. Atajos para producir material rápido

- **LoC por módulo** (cap.5): `git ls-files '*.py' '*.vue' '*.js' | xargs wc -l`
  agrupando por carpeta; o `cloc .` excluyendo `node_modules`/`.node`.
- **Fechas de commits para el Gantt**: `git log --pretty='%h %ad %s' --date=short`.
- **Curva de entrenamiento**: parsear `train_jersey.log` con un script y plotear
  con matplotlib (ejes loss/accuracy vs época).
- **Latencia por etapa**: el pipeline ya tiene `pipeline/profiling.py`; ejecuta un
  clip de prueba y exporta los tiempos a una gráfica de barras.
- **UMAP de equipos**: reutiliza el código de `pipeline/teams/` para volcar los
  embeddings 2D y colorear por cluster.
- **Frames anotados**: procesa un clip de `data/test_videos` con `run.py` y
  extrae frames con `ffmpeg -i out.mp4 -vf fps=1 frame_%03d.png`.
