# Estado del arte (material para el Cap. 2 de la memoria)

> Documento de apoyo para redactar el capítulo 2 del TFG. Reúne conceptos del
> dominio, proyectos afines y el estudio de viabilidad con la **selección de
> alternativas justificada**. Fuentes de verdad: [`README.md`](../README.md),
> [`pipeline/config.py`](../pipeline/config.py), [`arquitectura.md`](arquitectura.md)
> y [`datos-reales-tfg.md`](datos-reales-tfg.md). **Regla: no inventar cifras.**
>
> ⚠️ **Corrección crítica respecto a la plantilla.** La "Tabla 1" original elegía
> *YOLOv8 + ByteTrack* descartando *RF-DETR + SAM*. Eso **contradice el código**:
> el sistema construido usa **RF-DETR + SAM 3**. Este documento invierte la
> selección para que la memoria describa lo que el tribunal puede ejecutar.

---

## 2.1 Conceptos del dominio

El proyecto cruza dos dominios: el **baloncesto** (qué se quiere medir) y la
**visión por computador** (cómo se mide). Esta sección fija el vocabulario que
usa el resto de la memoria.

### 2.1.1 Conceptos de baloncesto

- **Posesión**: qué equipo (y qué jugador) controla el balón en cada instante.
  Es la unidad básica del análisis táctico: casi toda estadística avanzada se
  normaliza "por posesión". En este sistema se resuelve por frame con una
  máquina de estados con histéresis (ver [`possession/`](../pipeline/possession/)).
- **Tiro (intento de canasta)** y su resultado (acierto/fallo): evento discreto
  que delimita el final de muchas posesiones. El sistema lo detecta combinando
  las clases de acción del detector con la señal `ball-in-basket`.
- **Jugada / sistema ofensivo-defensivo**: patrón espacio-temporal coordinado
  (un *pick and roll*, una zona 2-3…). **Queda fuera del alcance** de este TFG
  (ver 2.3): reconocer jugadas exige modelar relaciones entre jugadores a lo
  largo del tiempo, no solo detectarlos.
- **Dorsal y roster**: el número de camiseta identifica al jugador dentro de su
  equipo; cruzándolo con un *roster* (plantilla) se obtiene el nombre.

### 2.1.2 Conceptos de visión por computador

- **Detección de objetos**: localizar y clasificar instancias (cajas + clase)
  en cada frame. Aquí, 11 clases de baloncesto (jugadores, balón, aro, acciones…).
- **Seguimiento multi-objeto (MOT, *Multi-Object Tracking*)**: mantener una
  identidad temporal consistente (un `track_id`) para cada objeto a lo largo de
  los frames. El reto clásico son los *ID switches* (intercambios de identidad)
  en oclusiones y cruces, frecuentes en baloncesto por la aglomeración.
- **Re-identificación (re-ID)**: reasignar la identidad correcta a un objeto que
  desaparece y reaparece (sale de plano, queda totalmente ocluido).
- **Segmentación**: en vez de una caja, una **máscara** píxel a píxel del objeto.
  Permite recortes con fondo negro (mejor para clasificar equipo/dorsal) y un
  *foot point* preciso (el píxel inferior de la máscara) para la proyección 2D.
- **Homografía**: transformación proyectiva 3×3 que relaciona el plano de la
  imagen con el plano del suelo de la cancha. Permite proyectar las posiciones
  de los jugadores a una vista cenital 2D (minimapa táctico).
- **Embedding**: vector de características que resume el contenido visual de un
  recorte. Recortes de la misma camiseta producen embeddings cercanos, lo que
  habilita la clasificación de equipos **sin etiquetas** (clustering).

### 2.1.3 Familias de modelos relevantes

| Familia | Ejemplos | Idea clave | Rol en este TFG |
|---|---|---|---|
| Detectores CNN de una etapa | YOLO (v5–v11) | Rejilla de anclas, muy rápidos | Alternativa descartada (ver 2.3) |
| Detectores *transformer* (DETR) | DETR, Deformable-DETR, **RF-DETR** | Detección como predicción de conjuntos, sin NMS ni anclas | **Detector elegido** |
| Trackers por asociación | SORT, ByteTrack, BoT-SORT | Asocian cajas entre frames (movimiento + apariencia) | Alternativa descartada |
| Modelos de segmentación promptables | SAM, SAM 2, **SAM 3** | Segmentan/siguen objetos a partir de un *prompt* | **Tracker elegido** (prompt-once) |
| Modelos de visión-lenguaje (VLM) | SmolVLM, Qwen-VL, **SmolVLM2** | Razonan sobre imagen+texto; OCR robusto en escena | **OCR de dorsal elegido** |
| *Encoders* imagen-texto | CLIP, **SigLIP** | Embeddings alineados imagen-texto | **Clasificación de equipos** |
| Reducción de dimensión / clustering | **UMAP**, **K-means** | Proyectar y agrupar embeddings | Equipos sin etiquetas |

> **CNN vs. transformers en detección.** YOLO (CNN, una etapa) domina por
> velocidad pero depende de anclas y de supresión de no-máximos (NMS), sensible
> al *hiperajuste* y a aglomeraciones. La familia DETR plantea la detección como
> predicción directa de un conjunto de objetos con atención global, eliminando
> anclas y NMS. **RF-DETR** es una variante eficiente orientada a *fine-tuning*
> sobre datasets propios (vía Roboflow), lo que encaja con el dataset local de 11
> clases de este proyecto.

---

## 2.2 Proyectos y soluciones afines

### 2.2.1 Soluciones comerciales y académicas

| Solución | Tipo | Qué ofrece | Limitación para este caso |
|---|---|---|---|
| **Hudl / Hudl Assist** | Comercial (SaaS) | Etiquetado de vídeo, estadísticas, *highlights* | Cerrado, de pago, con etiquetado semi-manual; sin acceso al modelo |
| **Synergy Sports** | Comercial (SaaS) | Análisis táctico y *scouting* profesional | Orientado a ligas profesionales; coste elevado; cerrado |
| **Second Spectrum / Stats Perform** | Comercial (tracking óptico) | Tracking 2D/3D con cámaras fijas calibradas en estadio | Requiere instalación multicámara dedicada; inaccesible a nivel aficionado |
| **Roboflow Sports** | Open source (notebooks) | Recetas de detección/tracking/proyección para deportes | Apoyado en **inferencia alojada** de Roboflow; ejemplos, no una aplicación |
| **TFGs/papers con YOLO+ByteTrack** | Académico | Detección+tracking de jugadores | Pila clásica CNN+asociación; rara vez OCR de dorsal por VLM ni app integrada |

### 2.2.2 Diferenciador de este proyecto

El sistema construido se distingue en cuatro ejes:

1. **Pipeline completo e integrado**: de vídeo crudo a vídeo anotado + minimapa
   2D + estadísticas (posesión, tiros), no un módulo aislado.
2. **Modelos entrenados/ajustados localmente**, sin inferencia alojada: el
   OCR de dorsal es un **SmolVLM2 fine-tuneado** en local; el detector es un
   **RF-DETR** propio. Nada depende de una API de pago en *runtime*.
3. **Identificación por dorsal con VLM** (no OCR clásico) y resolución de nombre
   contra *roster*, algo poco habitual en los TFGs afines.
4. **Aplicación web usable** (Vue 3 + FastAPI) con selección de GPU, progreso en
   vivo y procesado **multi-GPU**: el resultado es una herramienta, no un script.

> Frente a las soluciones comerciales (cerradas y de pago) y a los notebooks de
> Roboflow (dependientes de inferencia alojada), este proyecto demuestra que un
> pipeline de extremo a extremo es viable con **hardware accesible y modelos
> propios**.

---

## 2.3 Estudio de viabilidad

### 2.3.1 Alcance (dentro / fuera)

**Dentro del alcance (implementado y verificable en el código):**

- Detección de jugadores, balón, aro y árbitros (RF-DETR, 11 clases).
- Seguimiento con identidad temporal (SAM 3, prompt-once + re-prompt).
- Clasificación de equipo sin etiquetas (SigLIP + UMAP + K-means).
- OCR de dorsal (SmolVLM2 fine-tuneado) + resolución de nombre vía roster.
- Proyección 2D por homografía (keypoints de cancha) y minimapa cenital.
- Resolución de posesión (histéresis temporal) y detección de tiros.
- Aplicación web (subida, GPU, progreso, visualización) + CLI; multi-GPU; entorno reproducible en contenedor (Apptainer).

**Fuera del alcance (se trasladan a Vías futuras, cap. 8):**

- **Reconocimiento de jugadas/tácticas** (sistemas ofensivos/defensivos).
- **Reconocimiento de acciones por pose** (ViTPose/ST-GCN/PoseConv3D): no se usa
  estimación de pose; las acciones de tiro provienen de clases del propio detector.
- **Motor experto / recomendación táctica** (los ficheros `core/expert/` y
  `core/classifier/` del backend son andamiaje vacío — ver
  [`datos-reales-tfg.md` §6](datos-reales-tfg.md)).
- **Procesado en tiempo real**: el sistema es **por lotes** (≈0,7 fps medido en
  A100 — ver [`datos-reales-tfg.md` §5](datos-reales-tfg.md)).
- **Captura en directo / multicámara**.

> Delimitar el alcance con honestidad es criterio de ingeniería: lo no construido
> no se promete en los objetivos (cap. 1) y reaparece como evolución natural en
> Vías futuras (cap. 8).

### 2.3.2 Selección de alternativas técnicas

Para cada decisión clave se compararon alternativas con criterios homogéneos:
**precisión esperada en aglomeración**, **identidad temporal**, **dependencia de
cloud**, **esfuerzo de etiquetado** y **encaje con el dataset/​hardware**.

#### A) Detección: RF-DETR vs. YOLOv8

| Criterio | YOLOv8 (CNN, 1 etapa) | **RF-DETR (transformer)** ✅ |
|---|---|---|
| Anclas / NMS | Sí (sensible al ajuste) | **No** (predicción de conjuntos) |
| Robustez en aglomeración | Media | **Alta** (atención global) |
| *Fine-tuning* sobre dataset propio | Bueno | **Bueno e integrado con Roboflow** |
| Clases de acción en el propio detector | Posible | **Sí** (clases 5–8: posesión y tiros) |
| Velocidad | **Muy alta** | Alta (≈91 ms/frame medido) |

> **Elegido: RF-DETR.** Aunque YOLOv8 es más rápido, RF-DETR encaja mejor con el
> dataset local de 11 clases (incluidas las clases de **acción** que alimentan la
> posesión y el *shot tracker*) y es más robusto en escenas aglomeradas. La
> detección no es el cuello de botella del pipeline (lo son el OCR y el tracking),
> así que la diferencia de velocidad no penaliza.

#### B) Seguimiento: SAM 3 vs. ByteTrack

| Criterio | ByteTrack (asociación de cajas) | **SAM 3 (segmentación promptable)** ✅ |
|---|---|---|
| Salida | Caja + ID | **Máscara** + ID |
| Recorte para equipo/dorsal | Caja (incluye fondo) | **Máscara** (fondo negro, más limpio) |
| *Foot point* para homografía | Centro/base de caja (aprox.) | **Píxel inferior de máscara** (preciso) |
| Re-aparición tras oclusión | Heurística de asociación | **Re-prompt** desde detecciones RF-DETR |
| Coste | Bajo | **Alto** (≈424 ms/frame medido) |

> **Elegido: SAM 3 (prompt-once + re-prompt).** Las máscaras mejoran la
> clasificación de equipo (recorte sin fondo) y dan un *foot point* preciso para
> la proyección 2D. El coste es alto (segunda etapa más cara del pipeline) y la
> **deriva en vídeos largos** motivó una iteración (tarjeta [ANL-3]: intento de
> segmentar sesiones SAM, finalmente revertido — ver §4 en
> [`metodologia.md`](metodologia.md)).

#### C) OCR de dorsal: SmolVLM2 (VLM) vs. PARSeq (OCR clásico)

| Criterio | PARSeq (OCR de texto) | **SmolVLM2 (VLM) fine-tuneado** ✅ |
|---|---|---|
| Robustez con números deformados/rotados | Media | **Alta** (razonamiento visión-lenguaje) |
| Ajuste a dominio (dorsales) | Reentrenar | **PEFT/LoRA local** (0,81 % de params) |
| Dependencia de cloud | No | **No** (modelo local) |
| Exactitud medida | — | **85,26 %** (test real, 312 muestras) |
| Coste | Bajo | **Alto** (≈550 ms/frame; etapa más cara) |

> **Elegido: SmolVLM2 fine-tuneado localmente.** El *fine-tuning* tipo adaptadores
> (PEFT/LoRA: solo 4,16 M de 511 M parámetros) logra **85,26 %** de exactitud
> exacta en el test (no el "96,8 %" inventado de la plantilla). Es la etapa más
> costosa del pipeline (39 % del cómputo): vía de mejora evidente = cuantización.

#### D) Clasificación de equipos: SigLIP+clustering vs. clustering de color

| Criterio | Histograma/clustering de color | **SigLIP + UMAP + K-means** ✅ |
|---|---|---|
| Etiquetas necesarias | No | **No** (no supervisado) |
| Robustez a iluminación/sombras | Baja | **Alta** (embeddings semánticos) |
| Equipos con colores parecidos | Frágil | **Más robusto** |
| Coste | Muy bajo | Medio (≈101 ms/frame) |

> **Elegido: SigLIP + UMAP + K-means.** Los embeddings de SigLIP separan los dos
> equipos sin etiquetas y son más robustos a iluminación que el color crudo. La
> asignación equipo→nombre se resuelve después contra el roster.

### 2.3.3 Resumen de la pila seleccionada

```
Detección ........ RF-DETR (11 clases, local)
Tracking ......... SAM 3 (prompt-once + re-prompt)
Equipos .......... SigLIP + UMAP + K-means (sin etiquetas)
Dorsal ........... SmolVLM2 fine-tuned (PEFT) → roster → nombre
Cancha ........... Keypoints → homografía (RANSAC + PnP) → minimapa 2D
Posesión/tiros ... histéresis temporal + shot tracker
```

> Esta es la pila **realmente implementada**. Toda mención a YOLOv8 / ByteTrack /
> PARSeq en la memoria debe quedar como *alternativa del estado del arte*, nunca
> como "lo usado".

---

## Material para figuras y tablas del capítulo

- **Tabla**: comparativa de soluciones comerciales/académicas (2.2.1).
- **Tabla**: alternativas técnicas A–D con la opción elegida resaltada (2.3.2).
- **Figura**: línea temporal de modelos (CNN → DETR; SAM → SAM 2 → SAM 3).
- **Figura**: diagrama de la pila seleccionada (2.3.3) como bloques vectoriales.
- **Diagrama dentro/fuera del alcance** (2.3.1) en dos columnas.
