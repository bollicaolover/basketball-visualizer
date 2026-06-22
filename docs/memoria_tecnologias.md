# Tecnologías y Herramientas Utilizadas

El presente capítulo documenta el conjunto de tecnologías sobre las que se
construye el sistema de análisis táctico de baloncesto desarrollado en este TFG.
A diferencia de un mero listado de dependencias, cada selección se presenta
acompañada de una justificación razonada que confronta la herramienta elegida
con las alternativas reales evaluadas durante el proyecto. El criterio rector ha
sido pragmático: el sistema es un *pipeline* de visión por computador y
*deep learning* que debe ejecutarse sobre vídeo real de baloncesto en un
servidor con GPUs NVIDIA A100, exponerse a través de una aplicación web y, al
mismo tiempo, ser mantenible y depurable por una sola persona en el marco
temporal de un trabajo de fin de grado. En consecuencia, se ha priorizado la
madurez del ecosistema, la integración entre componentes y la disponibilidad de
modelos preentrenados sobre la novedad o el rendimiento teórico máximo.

La inventario completo se ha obtenido a partir de los ficheros de dependencias
(`requirements.txt` de la raíz y del *backend*, `package.json` del *frontend*),
de las sentencias `import` reales presentes en el código (`pipeline/`,
`backend/`) y de los *scripts* de despliegue y documentación. Las versiones que
aparecen indicadas se han verificado contra el entorno Conda `tfg-baloncesto`
realmente instalado en el servidor, dado que buena parte del `requirements.txt`
no fija versiones (véase la sección final de verificación).

---

## Tabla resumen

| Tecnología | Versión | Categoría | Alternativas evaluadas | Criterio de selección principal |
|------------|---------|-----------|------------------------|---------------------------------|
| Python | 3.10 | Lenguaje principal (backend + CV) | C++, Julia | Ecosistema de DL/CV y velocidad de desarrollo |
| PyTorch | 2.6.0+cu118 | Deep Learning | TensorFlow, JAX | Modelos preentrenados (RF-DETR, SAM 3, *transformers*) y soporte CUDA |
| OpenCV | 4.13.0 | Visión por computador / geometría / vídeo | scikit-image, Pillow | Homografía, filtro de Kalman y E/S de vídeo en una sola librería |
| RF-DETR | 1.6.5 | Detección de objetos | YOLOv8/v11, RT-DETR original | Precisión en jugadores/balón y *fine-tuning* propio |
| SAM 3 (vía transformers) | 5.8.1 | Tracking por máscara | ByteTrack, BoT-SORT puro | Continuidad de identidad por *memory bank* en vídeo completo |
| Ultralytics (YOLOv8-pose) | 8.4.50 | Keypoints de cancha + pose | MMPose, OpenPose | Detección de *keypoints* y pose en un solo *framework* ligero |
| supervision | 0.28.0 | Utilidades de detección | Código propio | Estructura `Detections` y anotadores compatibles con todo el *pipeline* |
| transformers (HF) | 5.8.1 | Modelos fundacionales (SAM 3, SmolVLM2, SigLIP) | Repos sueltos por modelo | Carga unificada de tres familias de modelos distintas |
| FastAPI | 0.115.14 | Framework de *backend* | Flask, Django | API asíncrona, tipada y con *BackgroundTasks* sin Celery/Redis |
| Vue 3 | 3.4 | Framework de *frontend* | React, Svelte | SPA reactiva ligera servida como estáticos por FastAPI |
| Vite | 5.2 | *Build tool* de *frontend* | webpack, CRA | Compilación rápida y *dev server* con *proxy* a la API |
| NumPy | 1.26.4 | Cómputo numérico | — | Base aritmética de todo el código geométrico |
| boxmot (BoT-SORT) | 19.0.0 | Tracking alternativo + ReID | DeepSORT, ByteTrack | *Tracker* opcional con ReID OSNet para escenas sin SAM |
| scikit-learn | 1.7.2 | Clustering de equipos | Código propio | K-means sobre *embeddings* de equipo |
| umap-learn | 0.5.12 | Reducción de dimensionalidad | t-SNE, PCA | Proyección de *embeddings* SigLIP antes del *clustering* |
| PEFT | 0.19.1 | *Fine-tuning* del OCR | *Full fine-tuning* | LoRA sobre SmolVLM2 con poca VRAM |
| sports (Roboflow) | git | Utilidades de baloncesto | Código propio | `TeamClassifier` (SigLIP) y `ConsecutiveValueTracker` ya probados |
| ffmpeg | sistema | Procesamiento de vídeo | MoviePy, PyAV | Corte/concatenación y *transcode* sin recodificar en exceso |
| Pillow | 12.2.0 | Imagen (E/S para modelos HF) | — | Formato `PIL.Image` que esperan los modelos *transformers* |
| matplotlib | 3.10.9 | Visualización 3D del tiro | Plotly | Render de la trayectoria 3D a PNG/MP4 sin servidor gráfico |
| pytest | 9.0.3 | *Testing* | unittest | Suite de lógica pura del cap. 7 sin GPU |
| nvidia-ml-py (pynvml) | 12.575 | Monitorización de GPU | parseo de `nvidia-smi` | Memoria/uso de GPU en tiempo real para la web |
| psutil | 7.2.2 | Monitorización de CPU | `/proc` manual | Uso de CPU para el panel de sistema |
| uvicorn | 0.46.0 | Servidor ASGI | Hypercorn, Gunicorn | Servidor recomendado por FastAPI |
| python-multipart | 0.0.28 | Subida de ficheros | — | *Multipart* para el *endpoint* de subida de vídeo |
| pycocotools | 2.0.11 | Evaluación de detección | Código propio | mAP en formato COCO para validar RF-DETR |
| roboflow | 1.3.3 | Descarga de datasets (solo *training*) | Descarga manual | Acceso a datasets etiquetados de baloncesto |
| python-dotenv | 1.2.2 | Configuración | `os.environ` directo | Carga de claves (`HF_TOKEN`, Roboflow) desde `.env` |
| KaliCalib | third_party | Calibración de cancha | Homografía por *keypoints* | Calibración robusta como vía experimental |
| CUDA / cuDNN | 11.8 | Aceleración GPU | CPU | Inferencia DL viable sobre A100 |
| PlantUML | 1.2024.7 | Diagramas UML | draw.io, Mermaid | Diagramas como código versionable |
| Git | — | Control de versiones | — | Historial y trazabilidad (*flujo Kanban*) |
| Conda | — | Gestión de entornos | venv, Poetry | Entorno único `tfg-baloncesto` con CUDA |

---

## 1. Lenguaje de programación principal

### Python (versión 3.10)

**Categoría**: Lenguaje de programación principal (*backend* + *pipeline* de CV).

**Rol en el proyecto**
Python es el lenguaje en el que está escrita la práctica totalidad del sistema:
el *pipeline* de visión (`pipeline/`, con sus subsistemas de detección,
*tracking*, homografía, pose, reconstrucción 3D del tiro y reconocimiento de
pantallas), el *backend* web (`backend/app/main.py` y `chunking.py`) y los
*scripts* de orquestación (`run.py`). Solo el *frontend* escapa a Python, al
estar escrito en JavaScript/Vue. La elección viene en gran medida impuesta por
el dominio: todas las librerías de *deep learning* y visión que el proyecto
necesita (PyTorch, OpenCV, *transformers*, Ultralytics) exponen su API principal
en Python.

**Alternativas consideradas**

| Alternativa | Ventaja principal | Motivo de descarte |
|-------------|-------------------|--------------------|
| C++ | Rendimiento en bucle de vídeo y acceso nativo a OpenCV/CUDA | Productividad muy inferior; los modelos DL no tienen API C++ de primera clase |
| Julia | Cómputo numérico rápido sin GIL | Ecosistema de visión y modelos preentrenados inmaduro frente a Python |

**Justificación de la elección**
El factor determinante es el ecosistema. El sistema depende de modelos
fundacionales recientes —RF-DETR, SAM 3, SmolVLM2, SigLIP— que se distribuyen
casi exclusivamente con *bindings* de Python a través de Hugging Face
`transformers` y de las librerías de Roboflow y Ultralytics. Reescribir el
*pipeline* en C++ habría obligado a portar o reimplementar la inferencia de cada
modelo, un esfuerzo desproporcionado para un TFG y una fuente continua de
errores difíciles de depurar.

En segundo lugar, el rendimiento crítico no reside en el código Python sino en
las operaciones vectorizadas de NumPy y en los *kernels* CUDA que ejecutan
PyTorch y OpenCV; Python actúa como capa de orquestación, donde su penalización
por interpretación es marginal frente al coste de la inferencia en GPU. El
*pipeline* procesa el vídeo *frame* a *frame* delegando el trabajo pesado a estas
librerías, de modo que el lenguaje no es el cuello de botella.

Finalmente, Python ofrece una curva de aprendizaje y un volumen de documentación
que resultan decisivos cuando el tiempo de depuración es un recurso escaso. Se
ha fijado la versión 3.10 por ser la del entorno Conda del servidor y por
garantizar compatibilidad con todas las dependencias (PyTorch con CUDA 11.8,
*transformers* 5, FastAPI). El uso intensivo de *type hints* (`typing`,
`dataclasses`) y de `from __future__ import annotations` en todo el código
documenta los contratos entre módulos sin coste en ejecución.

**Referencias**
- Python Software Foundation (2024). *Python 3.10 Documentation*. https://docs.python.org/3.10/
- Harris, C. R. et al. (2020). *Array programming with NumPy*. Nature 585, 357–362.

---

## 2. Visión por computador y Deep Learning

### PyTorch (versión 2.6.0+cu118)

**Categoría**: *Framework* de *deep learning* y aceleración GPU.

**Rol en el proyecto**
PyTorch es el sustrato de cálculo de todos los modelos neuronales del sistema.
Sobre él se ejecutan el detector RF-DETR (`pipeline/detection/rfdetr_detector.py`),
el *tracker* por máscara SAM 3 (`pipeline/tracking/sam_tracker.py`), el detector
de *keypoints* y pose de Ultralytics, el OCR de dorsales basado en SmolVLM2
(`pipeline/identity/number_ocr.py`) y el clasificador de equipos por *embeddings*
SigLIP. También gestiona la asignación de GPU y la fracción de memoria
(`--mem-fraction`) que el *backend* pasa a cada *job*. La compilación es
`+cu118`, es decir, ligada a CUDA 11.8, la versión soportada por los
*drivers* del servidor con las A100.

**Alternativas consideradas**

| Alternativa | Ventaja principal | Motivo de descarte |
|-------------|-------------------|--------------------|
| TensorFlow / Keras | Madurez en producción y *serving* | Menor disponibilidad de los modelos concretos que usa el proyecto |
| JAX | Rendimiento y diferenciación funcional | Ecosistema de visión y modelos preentrenados mucho más reducido |

**Justificación de la elección**
La razón central es la compatibilidad de modelos. RF-DETR, SAM 3 y la familia de
*transformers* de Hugging Face que el proyecto integra (SmolVLM2, SigLIP) se
publican y mantienen primariamente en PyTorch. Hugging Face `transformers`, que
el sistema usa para tres modelos distintos, tiene a PyTorch como *backend* de
referencia, mientras que el soporte para TensorFlow o JAX es parcial y, en el
caso de los modelos más recientes como SAM 3, inexistente. Optar por otro
*framework* habría reducido drásticamente el catálogo de modelos disponibles.

En cuanto a rendimiento e infraestructura, PyTorch con CUDA 11.8 explota
plenamente las A100 del servidor; el sistema controla explícitamente la memoria
(`torch.cuda.set_per_process_memory_fraction` y la variable
`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` en `run_batch.sh`) para poder
ejecutar varios *jobs* sin provocar *out-of-memory*. El *backend* serializa los
trabajos con un único *lock* por GPU precisamente porque cada uno satura un
dispositivo.

Por último, PyTorch ofrece un modelo de ejecución imperativo (*eager*) que
facilita enormemente la depuración: los tensores se pueden inspeccionar en
cualquier punto, algo valioso en un proyecto donde la geometría 3D y el
seguimiento generan errores sutiles. La madurez de su comunidad y documentación
reduce el tiempo invertido en resolver incidencias de integración con CUDA.

**Referencias**
- Paszke, A. et al. (2019). *PyTorch: An Imperative Style, High-Performance Deep Learning Library*. NeurIPS.
- PyTorch Foundation (2024). *PyTorch 2.6 Documentation*. https://pytorch.org/docs/

---

### OpenCV (versión 4.13.0)

**Categoría**: Visión por computador, geometría y procesamiento de vídeo.

**Rol en el proyecto**
OpenCV (`cv2`) es, tras NumPy, la librería más transversal del *pipeline*:
aparece en 19 ficheros. Concentra tres responsabilidades. Primera, la
**geometría de cancha**: cálculo de la homografía que proyecta el plano de la
imagen al plano del campo (`pipeline/court/homography.py`), el modelo de cámara
con PnP y un **filtro de Kalman** de 12 estados para suavizar la pose
(`pipeline/court/camera_model.py`, `cv2.KalmanFilter(12, 6)`). Segunda, el
**seguimiento del balón** mediante un Kalman propio de 4 estados
(`pipeline/tracking/ball_tracker_kalman.py`), implementado con álgebra de NumPy
pero alineado con las primitivas de OpenCV. Tercera, la **E/S y anotación de
vídeo**: lectura *frame* a *frame*, dibujo de cajas y trayectorias y escritura
del vídeo de salida.

**Alternativas consideradas**

| Alternativa | Ventaja principal | Motivo de descarte |
|-------------|-------------------|--------------------|
| scikit-image | API más *pythónica* para procesado de imagen | Sin homografía robusta, PnP ni *VideoCapture* integrados |
| Pillow (PIL) | Ligera para E/S de imagen | No cubre geometría proyectiva ni vídeo; solo se usa como puente a modelos HF |

**Justificación de la elección**
El proyecto necesita resolver geometría proyectiva real —`cv2.findHomography`
con RANSAC, `cv2.solvePnP`, `cv2.perspectiveTransform`— y OpenCV es la
referencia indiscutible para estas operaciones, con implementaciones probadas
durante dos décadas. Reimplementarlas o buscarlas dispersas en otras librerías
habría añadido riesgo sin beneficio. La homografía es la columna vertebral del
*minimapa* táctico y del cálculo de posiciones de jugador sobre el campo, por lo
que su corrección numérica es crítica.

La integración es el segundo argumento: OpenCV trabaja directamente sobre
*arrays* de NumPy, el mismo tipo que circula por todo el *pipeline* y que
consumen `supervision` y PyTorch (tras conversión). Esto evita copias y
conversiones de formato entre etapas. El filtro de Kalman incorporado
(`cv2.KalmanFilter`) permitió implementar el suavizado de la pose de cámara
—siguiendo el enfoque de la tesis de Pirotta— sin añadir dependencias.

Finalmente, OpenCV es *headless*-compatible (en el servidor coexisten
`opencv-python` y `opencv-python-headless`), lo que permite ejecutar el
*pipeline* en un servidor sin entorno gráfico. Su madurez y la abundancia de
ejemplos para problemas de calibración deportiva reducen el tiempo de
depuración, factor relevante dado que la calibración de cancha fue una de las
partes más delicadas del proyecto.

**Referencias**
- Bradski, G. (2000). *The OpenCV Library*. Dr. Dobb's Journal of Software Tools.
- OpenCV team (2024). *OpenCV 4.x Documentation — Camera Calibration and 3D Reconstruction*. https://docs.opencv.org/4.x/

---

### RF-DETR (versión 1.6.5)

**Categoría**: Detección de objetos (jugadores, balón, aro).

**Rol en el proyecto**
RF-DETR es el detector principal del sistema. Carga un *checkpoint* propio
(`models/detection/checkpoint_best_ema.pth`) afinado sobre datos de baloncesto y
produce, para cada *frame*, las cajas de jugadores, balón y aro que alimentan al
*tracker*, al clasificador de equipos y al módulo de reconstrucción 3D del tiro
(`pipeline/detection/rfdetr_detector.py`, `pipeline/shot3d/reconstruct.py`). Su
rendimiento se ha validado de forma cuantitativa: las métricas mAP en formato
COCO se almacenan en `docs/results/rfdetr_detection_metrics.json`.

**Alternativas consideradas**

| Alternativa | Ventaja principal | Motivo de descarte |
|-------------|-------------------|--------------------|
| YOLOv8 / YOLOv11 (Ultralytics) | Inferencia muy rápida y *framework* maduro | Menor precisión observada sobre balón pequeño y oclusiones; se mantiene para *keypoints*/pose |
| RT-DETR (original) | Arquitectura DETR en tiempo real | Menos integrado con el ecosistema Roboflow y con peor soporte de *fine-tuning* documentado |

**Justificación de la elección**
La elección responde a un criterio de precisión específico del dominio. El balón
de baloncesto es un objeto pequeño, rápido y sujeto a fuertes oclusiones; los
detectores basados en anclas de la familia YOLO mostraron más falsos negativos
en estas condiciones. RF-DETR, al ser un detector *transformer* sin anclas ni
NMS, gestiona mejor las detecciones densas y solapadas, lo que se traduce en
trayectorias de balón más completas —esenciales para la reconstrucción 3D del
tiro, que necesita una parábola sin huecos.

El segundo factor es la capacidad de afinado. RF-DETR se distribuye con un flujo
de *fine-tuning* sencillo y bien integrado con los datasets de Roboflow
(`sports`, `roboflow`), lo que permitió entrenar un *checkpoint* específico para
baloncesto en el propio servidor. Esta especialización es la que justifica el
coste computacional añadido frente a YOLO: el sistema no necesita un detector
genérico, sino uno preciso en tres clases concretas.

Cabe matizar honestamente el papel de cada detector: RF-DETR se reserva para la
detección de entidades del juego, mientras que YOLOv8-pose de Ultralytics se
emplea para *keypoints* de cancha y pose de jugador, donde su velocidad y su
salida específica son más adecuadas. Ambos coexisten porque resuelven problemas
distintos; no es una redundancia sino una división de tareas.

**Referencias**
- Roboflow (2024). *RF-DETR: A Real-Time Detection Transformer*. https://github.com/roboflow/rf-detr
- Zhao, Y. et al. (2024). *DETRs Beat YOLOs on Real-time Object Detection* (RT-DETR). CVPR.

---

### SAM 3 (vía transformers 5.8.1)

**Categoría**: *Tracking* de jugadores por máscara (segmentación + memoria).

**Rol en el proyecto**
SAM 3 (*Segment Anything Model 3*) es el *tracker* por defecto del sistema
(`--tracker sam`). Se carga a través de Hugging Face `transformers`
(`Sam3TrackerVideoModel`, `Sam3TrackerVideoProcessor`) en
`pipeline/tracking/sam_tracker.py` y mantiene un *memory bank* a lo largo de
todo el vídeo, segmentando cada jugador y conservando su identidad entre
*frames*. Esta propiedad condiciona la arquitectura del *backend*: como el
*memory bank* abarca el vídeo completo, los trabajos con SAM **no se trocean**
entre GPUs (al contrario que el modo *chunked*), porque partir el vídeo
reiniciaría las identidades.

**Alternativas consideradas**

| Alternativa | Ventaja principal | Motivo de descarte |
|-------------|-------------------|--------------------|
| ByteTrack | Muy rápido, solo cajas | Pierde identidad en oclusiones largas frecuentes en baloncesto |
| BoT-SORT + ReID (boxmot) | Buena reidentificación por apariencia | Se conserva como modo alternativo, pero la máscara de SAM separa mejor jugadores muy juntos |

**Justificación de la elección**
El reto distintivo del *tracking* en baloncesto es la oclusión: los jugadores se
cruzan, bloquean y agrupan constantemente. Los *trackers* basados solo en cajas
(ByteTrack) tienden a intercambiar identidades en estos cruces. SAM 3 segmenta a
nivel de máscara y mantiene un banco de memoria temporal, lo que le permite
recuperar la identidad de un jugador tras una oclusión prolongada con mucha mayor
fiabilidad. La continuidad de identidad es un requisito duro del sistema, porque
de ella dependen la clasificación de equipos, la lectura de dorsal y el
reconocimiento de pantallas.

El segundo argumento es la integración: al cargarse vía `transformers`, SAM 3
reutiliza la misma infraestructura (PyTorch, gestión de *device*, tokens de
Hugging Face) que ya usan el OCR y el clasificador de equipos, sin añadir un
*stack* nuevo. El coste de esta calidad es computacional —SAM consume el vídeo
entero en una GPU— y el sistema lo asume conscientemente, ofreciendo BoT-SORT
como alternativa más ligera (`--tracker botsort`) para escenarios donde la VRAM
o el tiempo sean limitantes.

Se reconoce, no obstante, que SAM 3 es un modelo muy reciente: su madurez como
dependencia es menor que la de OpenCV o YOLO, y su disponibilidad depende de una
versión de `transformers>=5`. Este riesgo se mitiga manteniendo el *tracker*
clásico como respaldo plenamente funcional.

**Referencias**
- Kirillov, A. et al. (2023). *Segment Anything*. ICCV. (Base conceptual de la familia SAM.)
- Hugging Face (2025). *Transformers — SAM 3 Tracker Video Model*. https://huggingface.co/docs/transformers

---

### Ultralytics — YOLOv8-pose (versión 8.4.50)

**Categoría**: Detección de *keypoints* de cancha y estimación de pose.

**Rol en el proyecto**
Ultralytics aporta dos modelos YOLOv8 en el sistema. El primero detecta los
*keypoints* de la cancha (`models/court-keypoints/best.pt`,
`pipeline/court/keypoint_detector.py`), cuyas correspondencias alimentan el
cálculo de la homografía. El segundo es un YOLOv8-pose (`yolov8n-pose.pt`) que
estima la pose del jugador (`pipeline/pose/pose_estimator.py`) y, en concreto, se
usa para detectar el instante de **soltado del balón** en el tiro
(`pipeline/scoring/release_detector.py`), que dispara la reconstrucción 3D.

**Alternativas consideradas**

| Alternativa | Ventaja principal | Motivo de descarte |
|-------------|-------------------|--------------------|
| MMPose | Catálogo de modelos de pose muy amplio | Instalación y configuración pesadas; sobredimensionado para el caso |
| OpenPose | Pionero en pose multipersona | Proyecto poco mantenido y de integración compleja |

**Justificación de la elección**
Ultralytics resuelve dos necesidades distintas —*keypoints* de cancha y pose— con
una única API homogénea y modelos ligeros (la variante *nano* `n`), lo que
simplifica el código y el despliegue. La detección de *keypoints* personalizados
fue posible gracias a su flujo de entrenamiento sencillo, que permitió afinar un
modelo de cancha propio. Para la pose, el modelo *nano* preentrenado es
suficiente, ya que el sistema no necesita una pose de altísima precisión sino
detectar de forma robusta la geometría brazos-balón que marca el soltado.

La integración con el resto del *pipeline* es directa: las salidas se convierten
a estructuras `supervision`/NumPy ya usadas en todas las etapas. Además, la
madurez y la enorme comunidad de Ultralytics reducen el riesgo y el tiempo de
depuración frente a alternativas más académicas como MMPose u OpenPose, cuya
puesta en marcha habría consumido un tiempo desproporcionado para el papel
auxiliar que la pose desempeña en el sistema.

**Referencias**
- Jocher, G. et al. (2023). *Ultralytics YOLOv8*. https://github.com/ultralytics/ultralytics
- Ultralytics (2024). *Pose Estimation Docs*. https://docs.ultralytics.com/tasks/pose/

---

### transformers (Hugging Face) (versión 5.8.1)

**Categoría**: Carga de modelos fundacionales (SAM 3, SmolVLM2, SigLIP).

**Rol en el proyecto**
`transformers` actúa como **capa unificada de acceso a tres familias de modelos
distintas**: SAM 3 para el *tracking* por máscara, SmolVLM2 para el OCR de
dorsales (`pipeline/identity/number_ocr.py`, `_try_load_smolvlm`) y SigLIP —a
través de la utilidad `TeamClassifier` de la librería `sports`— para los
*embeddings* de clasificación de equipos. Requiere `transformers>=5` por la
inclusión de SAM 3.

**Alternativas consideradas**
Se consideró cargar cada modelo desde su repositorio individual con código de
inferencia *ad hoc*, pero se descartó por la multiplicación de dependencias
incompatibles y de formatos de pesos que ello habría supuesto.

**Justificación de la elección**
El valor de `transformers` en este proyecto no es un modelo concreto sino la
**homogeneización**: tres modelos heterogéneos (un *tracker* de vídeo, un VLM de
OCR y un codificador imagen-texto) se cargan, se mueven a la GPU y se invocan con
el mismo patrón de `Processor`/`Model` y el mismo manejo de `HF_TOKEN`. Esto
reduce drásticamente la superficie de código de integración y el número de
dependencias transitivas conflictivas. La madurez del *hub* de Hugging Face,
además, garantiza la disponibilidad de los pesos y de versiones recientes como
SAM 3, que no existen fuera de este ecosistema. El coste es la exigencia de una
versión muy reciente (`>=5`), asumida porque es la única que expone SAM 3.

**Referencias**
- Wolf, T. et al. (2020). *Transformers: State-of-the-Art Natural Language Processing*. EMNLP (System Demos).
- Hugging Face (2025). *Transformers Documentation*. https://huggingface.co/docs/transformers

---

### supervision (versión 0.28.0)

**Categoría**: Utilidades de detección y anotación.

**Rol en el proyecto**
`supervision` (`sv`) proporciona la estructura de datos `sv.Detections` que
circula entre etapas del *pipeline* (detección → *tracking* → equipos →
metadatos) y los anotadores que dibujan cajas, etiquetas y trayectorias sobre el
vídeo de salida. Aparece en 19 ficheros, lo que la convierte en el "pegamento"
de formato del sistema.

**Alternativas consideradas**
Se consideró definir estructuras de detección propias, pero se descartó porque
RF-DETR, Ultralytics y la librería `sports` ya producen o consumen
`sv.Detections`, de modo que reinventarlas habría añadido conversiones en cada
frontera.

**Justificación de la elección**
La razón es la interoperabilidad: al adoptar el formato `sv.Detections` que ya
usan los detectores y utilidades del ecosistema Roboflow, el *pipeline* encadena
etapas sin código de conversión y aprovecha anotadores probados para la
visualización. Es una dependencia de soporte, pero su presencia transversal la
hace estructural: estandariza cómo viajan las detecciones por todo el sistema.
Se observa que el `requirements.txt` fija `0.27.0` mientras el entorno tiene
`0.28.0` (véase la sección de verificación).

**Referencias**
- Roboflow (2024). *Supervision*. https://github.com/roboflow/supervision

---

## 3. Tracking y reidentificación

### boxmot — BoT-SORT + OSNet ReID (versión 19.0.0)

**Categoría**: *Tracking* alternativo por caja con reidentificación.

**Rol en el proyecto**
`boxmot` implementa el *tracker* BoT-SORT que el sistema ofrece como alternativa
a SAM (`--tracker botsort`, `pipeline/tracking/player_tracker.py`). Incorpora
reidentificación por apariencia mediante un modelo OSNet
(`models/reid-osnet/osnet_x0_25_sportsmot.pt`) que se activa con
`botsort_with_reid`. Es la vía ligera del sistema cuando no se quiere pagar el
coste de SAM.

**Alternativas consideradas**
Se evaluaron DeepSORT y ByteTrack; `boxmot` se eligió porque empaqueta varios
*trackers* SOTA (incluido BoT-SORT) con soporte de ReID intercambiable bajo una
sola API.

**Justificación de la elección**
`boxmot` aporta un *tracker* maduro con ReID por apariencia sin necesidad de
implementar la asociación de movimiento y aspecto manualmente. El modelo OSNet
afinado en *SportsMOT* es especialmente adecuado para deporte, donde los
jugadores de un mismo equipo visten igual y la reidentificación por color es
insuficiente. Funciona como red de seguridad arquitectónica: garantiza que el
sistema sigue siendo utilizable en GPUs con poca VRAM o cuando SAM no esté
disponible, a costa de una continuidad de identidad algo inferior en oclusiones
severas.

**Referencias**
- Aharon, N., Orfaig, R., Bobrovsky, B. (2022). *BoT-SORT: Robust Associations Multi-Pedestrian Tracking*. arXiv:2206.14651.
- Zhou, K. et al. (2019). *Omni-Scale Feature Learning for Person Re-Identification* (OSNet). ICCV.

---

## 4. Identificación y clasificación de equipos

### scikit-learn (versión 1.7.2)

**Categoría**: *Clustering* de equipos.

**Rol en el proyecto**
Proporciona el algoritmo K-means que agrupa a los jugadores en dos equipos a
partir de sus *embeddings* visuales, dentro del flujo de
`pipeline/teams/team_classifier.py` (en cooperación con la utilidad
`TeamClassifier` de `sports`). Es la pieza no supervisada que asigna equipo sin
necesidad de etiquetas previas.

**Alternativas consideradas**
Se consideró implementar K-means a mano sobre NumPy, pero se descartó por no
aportar nada frente a una implementación estándar, probada y vectorizada.

**Justificación de la elección**
scikit-learn es el estándar de facto para *clustering* clásico en Python: su
K-means es robusto, está optimizado y se integra de forma natural con los
*arrays* NumPy de *embeddings*. Para un problema de dos *clusters* (dos equipos)
no se justifica nada más complejo, y su madurez elimina cualquier riesgo de
implementación. Es una dependencia de soporte pero necesaria para la
clasificación de equipos sin etiquetas.

**Referencias**
- Pedregosa, F. et al. (2011). *Scikit-learn: Machine Learning in Python*. JMLR 12, 2825–2830.

---

### umap-learn (versión 0.5.12)

**Categoría**: Reducción de dimensionalidad de *embeddings*.

**Rol en el proyecto**
UMAP reduce la dimensionalidad de los *embeddings* SigLIP de cada jugador antes
del *clustering* K-means, dentro del clasificador de equipos. Al separar mejor
las dos nubes (equipo claro / equipo oscuro) en un espacio de baja dimensión,
mejora la robustez de la asignación de equipo.

**Alternativas consideradas**
Se consideraron PCA y t-SNE; PCA es lineal y separa peor las clases, y t-SNE no
está pensado para proyectar datos nuevos de forma estable.

**Justificación de la elección**
UMAP preserva mejor la estructura local y global de los *embeddings* de alta
dimensión que PCA, lo que produce *clusters* de equipo más nítidos sobre los que
K-means converge de forma más fiable. Frente a t-SNE, es más rápido y permite un
comportamiento más reproducible. Es una dependencia de soporte heredada del flujo
de `TeamClassifier` de la librería `sports`, que el proyecto reutiliza.

**Referencias**
- McInnes, L., Healy, J., Melville, J. (2018). *UMAP: Uniform Manifold Approximation and Projection*. arXiv:1802.03426.

---

### PEFT (versión 0.19.1)

**Categoría**: *Fine-tuning* eficiente del OCR de dorsales.

**Rol en el proyecto**
PEFT se emplea en el entrenamiento del OCR de dorsales basado en SmolVLM2: aplica
LoRA (*Low-Rank Adaptation*) para afinar el VLM sobre dorsales de baloncesto sin
reentrenar todos sus pesos. Es una dependencia de *training*, no de *runtime* de
inferencia.

**Alternativas consideradas**
Se consideró el *fine-tuning* completo del modelo, descartado por su elevado
consumo de VRAM y su mayor riesgo de sobreajuste con un dataset pequeño.

**Justificación de la elección**
LoRA vía PEFT permite afinar un modelo grande como SmolVLM2 entrenando solo unas
pocas matrices de bajo rango, reduciendo drásticamente la memoria y el tiempo
necesarios. Para un dataset de dorsales relativamente reducido, esto evita el
sobreajuste y hace el entrenamiento viable en una sola GPU. Su integración nativa
con Hugging Face `transformers` lo hace la opción natural dado que el resto de
modelos ya viven en ese ecosistema.

**Referencias**
- Hu, E. J. et al. (2021). *LoRA: Low-Rank Adaptation of Large Language Models*. arXiv:2106.09685.
- Hugging Face (2024). *PEFT Documentation*. https://huggingface.co/docs/peft

---

### sports (Roboflow, instalada desde git)

**Categoría**: Utilidades específicas de baloncesto.

**Rol en el proyecto**
La librería `sports` (rama `feat/basketball` del repositorio de Roboflow) aporta
componentes reutilizados directamente: `TeamClassifier` (que envuelve SigLIP +
UMAP + K-means) y `ConsecutiveValueTracker`, usado para estabilizar la lectura de
dorsal y la asignación de equipo a lo largo del tiempo
(`pipeline/teams/team_classifier.py`, `pipeline/identity/number_ocr.py`).

**Alternativas consideradas**
Se consideró reimplementar estas utilidades, pero se descartó al estar ya
probadas y ajustadas al dominio del baloncesto en el código de referencia del
que parte el proyecto.

**Justificación de la elección**
Reutilizar `sports` evita reescribir lógica no trivial (votación temporal de
valores consecutivos, *pipeline* de clasificación de equipos) que ya funciona
sobre el mismo formato `sv.Detections`. Al instalarse desde git en una rama
concreta, queda fijada la versión que el proyecto ha validado. El riesgo de
depender de una rama no publicada en PyPI se asume conscientemente y se documenta
(véase la sección de verificación).

**Referencias**
- Roboflow (2024). *sports* (rama `feat/basketball`). https://github.com/roboflow/sports

---

## 5. Framework de backend

### FastAPI (versión 0.115.14)

**Categoría**: *Framework* de *backend* / API REST.

**Rol en el proyecto**
FastAPI implementa toda la API del sistema (`backend/app/main.py`): subida de
vídeo (`POST /api/upload`), procesamiento de clips de ejemplo, consulta de estado
de los *jobs*, *streaming* de los vídeos y JSON de resultados, estadísticas de
CPU/GPU en tiempo real y guardado de anotaciones del usuario. Lanza el
*pipeline* como subproceso mediante `BackgroundTasks`, sirve el *frontend* Vue
compilado como ficheros estáticos y aplica un *middleware* de autenticación por
*cookie* HMAC opcional. La arquitectura es deliberadamente sencilla: un único
*lock* por GPU en lugar de una cola distribuida.

**Alternativas consideradas**

| Alternativa | Ventaja principal | Motivo de descarte |
|-------------|-------------------|--------------------|
| Flask | Minimalista y muy conocido | Sin asincronía ni validación/tipado nativos; más código repetitivo |
| Django | *Framework* completo con ORM y admin | Sobredimensionado: el sistema no usa base de datos relacional ni necesita su andamiaje |

**Justificación de la elección**
El *backend* tiene un perfil muy concreto: pocas rutas, operaciones de I/O largas
(procesar un vídeo tarda minutos) y necesidad de *streaming* y de subida de
ficheros grandes. FastAPI encaja por su modelo asíncrono y sus
`BackgroundTasks`, que permiten lanzar el *pipeline* sin bloquear la API y sin
introducir un sistema de colas externo como Celery + Redis; el propio código
documenta esta decisión ("*Sin Celery ni Redis; se usa BackgroundTasks +
subprocess*"). Para un único servidor con GPUs serializadas por un *lock*, esa
simplicidad es una ventaja de mantenimiento, no una limitación.

El segundo argumento es el tipado y la validación automática: los *endpoints*
declaran sus parámetros (`Query`, `Form`, `File`, `UploadFile`) y FastAPI valida
y documenta la API sin código adicional, lo que reduce errores en la frontera
entre *frontend* y *backend*. Frente a Django, se evita todo el andamiaje de un
ORM y un sistema de migraciones que el proyecto no necesita, ya que el estado se
persiste en ficheros JSON sobre el sistema de archivos.

Finalmente, FastAPI se apoya en Starlette y Uvicorn, un *stack* maduro y bien
documentado, y comparte lenguaje (Python) con el *pipeline*, lo que permite
importar directamente funciones de `pipeline/` (p. ej. los *helpers* de ffmpeg en
`chunking.py`) sin puentes entre procesos salvo el subproceso que aísla la GPU.

**Referencias**
- Ramírez, S. (2018–2024). *FastAPI Documentation*. https://fastapi.tiangolo.com/
- Encode (2024). *Starlette Documentation*. https://www.starlette.io/

---

## 6. Framework de frontend

### Vue 3 (versión 3.4) y Vite (versión 5.2)

**Categoría**: *Framework* de *frontend* y *build tool*.

**Rol en el proyecto**
Vue 3 implementa la SPA con la que interactúa el usuario (`frontend/src/`):
vistas de subida (`UploadView.vue`), resultados (`ResultsView.vue`) y *login*
(`LoginView.vue`), con *composables* reactivos (`useUploadJob`,
`useSystemStats`, `useGpus`, etc.) que consumen la API de FastAPI y muestran el
progreso del análisis, el reproductor de vídeo con la capa interactiva de cajas
y la trayectoria 3D del tiro. Vite es el *build tool*: ofrece el *dev server* con
*proxy* a `localhost:8000` (`vite.config.js`) y compila la aplicación a estáticos
que el *backend* sirve desde `frontend/dist`.

**Alternativas consideradas**

| Alternativa | Ventaja principal | Motivo de descarte |
|-------------|-------------------|--------------------|
| React | Ecosistema y comunidad mayores | API más verbosa; curva de *hooks* innecesaria para esta SPA |
| Svelte | *Bundle* mínimo, sin *virtual DOM* | Comunidad y recursos menores; sin ventaja decisiva aquí |

**Justificación de la elección**
La aplicación es una SPA de complejidad media —tres vistas y un puñado de
componentes— cuyo principal reto es la reactividad: reflejar en tiempo real el
progreso de un *job* y manipular una capa de anotaciones sobre el vídeo. La
*Composition API* de Vue 3 modela esto con *composables* limpios y reutilizables
(`useUploadJob`, `useSystemStats`) sin el peso conceptual de los *hooks* de
React. Para un único desarrollador, Vue ofrece una curva de aprendizaje suave y
una plantilla declarativa cercana al HTML, lo que acelera el desarrollo de la UI.

Vite se elige como *build tool* por su velocidad: arranque casi instantáneo del
*dev server* y recarga en caliente, frente a la lentitud de webpack o
Create-React-App. Su *proxy* integrado (`/api` y `/static` → `localhost:8000`)
permite desarrollar *frontend* y *backend* en paralelo sin configurar CORS en
local. La cadena Vue 3 + Vite es, además, la combinación recomendada y mejor
documentada del ecosistema Vue, lo que minimiza fricción. Como nota de
despliegue, el proyecto incluye un Node 20 embebido (`frontend/.node/`) porque el
Node del sistema es demasiado antiguo para Vite 5; `serve.sh` lo usa
explícitamente al compilar.

**Referencias**
- You, E. et al. (2024). *Vue 3 Documentation*. https://vuejs.org/
- Vite team (2024). *Vite Documentation*. https://vitejs.dev/

---

## 7. Procesamiento de vídeo

### ffmpeg / ffprobe (binario del sistema)

**Categoría**: Procesamiento y manipulación de vídeo.

**Rol en el proyecto**
ffmpeg es el motor de manipulación de vídeo del *backend* (`backend/app/chunking.py`,
localizado vía `pipeline.io.video._find_ffmpeg`). Se encarga de partir el vídeo
en segmentos exactos para el procesamiento *multi-GPU* (`split_video`),
concatenar los *overlays* resultantes (`concat_videos`), sondear *fps* y número
de *frames* (`probe_video` con ffprobe) y generar el vídeo "limpio"
(`transcode_clean`) que el *frontend* usa para la capa interactiva.

**Alternativas consideradas**
Se consideraron MoviePy y PyAV; se descartaron porque añaden una capa Python
sobre ffmpeg con menos control sobre el corte exacto por *frames* y el copiado de
*streams* sin recodificar.

**Justificación de la elección**
ffmpeg es la herramienta de referencia para manipulación de vídeo y permite
operaciones precisas —corte por rangos de *frames*, concatenación y *transcode*—
invocándolo directamente como subproceso, lo que da control total sobre los
parámetros y evita dependencias Python pesadas. Para la lectura *frame* a *frame*
del análisis se usa `cv2.VideoCapture` de OpenCV; ffmpeg se reserva para las
operaciones de troceado/ensamblado donde su exactitud es imprescindible.

**Referencias**
- FFmpeg team (2024). *FFmpeg Documentation*. https://ffmpeg.org/documentation.html

---

### Pillow (versión 12.2.0) y matplotlib (versión 3.10.9)

**Categoría**: Imagen (puente a modelos) y visualización 3D.

**Rol en el proyecto**
Pillow (`PIL.Image`) actúa como formato puente para alimentar a los modelos de
`transformers` (SAM 3, SmolVLM2), que esperan imágenes PIL en lugar de *arrays*
OpenCV. matplotlib (con `mpl_toolkits.mplot3d`) genera la visualización de la
**trayectoria 3D del tiro** reconstruida (`pipeline/shot3d/reconstruct.py`),
produciendo los PNG/PDF/MP4 que documentan el resultado (`docs/results/shot3d_*`).

**Alternativas consideradas**
Para la imagen, OpenCV ya cubre la E/S, pero Pillow es obligado por la API de los
modelos HF. Para la visualización 3D se consideró Plotly, descartado por requerir
un *backend* web/JS para el render, innecesario aquí.

**Justificación de la elección**
Pillow no es una elección sino un requisito de interoperabilidad con
`transformers`, y su coste es nulo. matplotlib se elige para la visualización 3D
porque renderiza a fichero (*backend* no interactivo) sin necesidad de entorno
gráfico ni servidor JS, lo que encaja con un servidor *headless*; su `mplot3d`
basta para representar la parábola del tiro con sus métricas (altura del ápice,
RMSE), que es exactamente lo que el TFG necesita evidenciar.

**Referencias**
- Clark, A. (2015). *Pillow (PIL Fork) Documentation*. https://pillow.readthedocs.io/
- Hunter, J. D. (2007). *Matplotlib: A 2D Graphics Environment*. Computing in Science & Engineering 9(3).

---

## 8. Gestión de datos y almacenamiento

El sistema **no utiliza base de datos relacional ni NoSQL**. El estado de cada
*job* se persiste como ficheros JSON sobre el sistema de archivos
(`data/jobs/{job_id}.json`, escritos de forma atómica con `tmp`+`replace` en
`backend/app/main.py`), los vídeos y metadatos de salida se guardan en
`data/outputs/{job_id}/`, y los *rosters* y anotaciones del usuario también son
JSON. Se consideró SQLite —incluso existe un módulo `backend/app/db/` vacío como
vestigio de esa idea— pero se descartó: para un único servidor con trabajos
serializados por GPU, el volumen de metadatos por *job* es pequeño y la
naturaleza efímera de los resultados no justifica el esquema, las migraciones ni
la indexación de una base de datos. El sistema de archivos ofrece simplicidad,
inspección directa (los JSON son legibles) y cero dependencias añadidas. El
formato JSON, manejado con la librería estándar `json`, es además el mismo que
consume el *frontend*, lo que elimina capas de serialización intermedias.

---

## 9. Comunicación y API

La comunicación *frontend*–*backend* es **REST sobre HTTP**, implementada con los
*routers* de FastAPI y consumida desde el *frontend* con `fetch` encapsulado en
`frontend/src/services/api.js`. El progreso de los *jobs* se obtiene por
**sondeo** (*polling*) del *endpoint* `GET /api/jobs/{job_id}` en lugar de
WebSockets: dado que el procesamiento dura minutos y el progreso se actualiza en
intervalos de segundos, el sondeo periódico es suficiente y mucho más simple de
implementar y depurar que una conexión persistente. La transferencia de vídeo se
hace por *streaming* HTTP (`FileResponse`) y la subida por *multipart*
(`python-multipart`). La autenticación, opcional, usa una *cookie* de sesión
firmada con HMAC-SHA256 (`hmac`, `hashlib`, `secrets` de la biblioteca estándar),
sin almacén de sesiones en servidor.

---

## 10. Hardware y aceleración

### NVIDIA A100 + CUDA 11.8

**Categoría**: Hardware de cómputo y aceleración GPU.

**Rol en el proyecto**
El entorno de ejecución real del proyecto es un servidor con **dos GPUs NVIDIA
A100 de 40 GB**. Toda la inferencia de *deep learning* (RF-DETR, SAM 3, YOLO,
SmolVLM2, SigLIP) se ejecuta sobre ellas a través de PyTorch compilado para CUDA
11.8. El sistema gestiona activamente este recurso: selecciona la GPU con más
memoria libre (`_resolve_gpu`), serializa los trabajos con un *lock* por GPU,
controla la fracción de memoria por proceso (`--mem-fraction`) y soporta un modo
*chunked* que reparte un vídeo entre varias GPUs (salvo con SAM, que exige el
vídeo completo).

**Alternativas consideradas**

| Alternativa | Ventaja principal | Motivo de descarte |
|-------------|-------------------|--------------------|
| CPU | Sin necesidad de GPU dedicada | Inferencia de SAM 3/RF-DETR sobre vídeo inviable por tiempo |
| GPU de consumo (p. ej. RTX) + Colab | Coste menor | Memoria insuficiente para SAM sobre vídeo largo; entorno menos estable |

**Justificación de la elección**
La elección del hardware no es una decisión de diseño sino el entorno disponible,
pero condiciona toda la arquitectura. Los 40 GB de VRAM de cada A100 son lo que
hace viable mantener el *memory bank* de SAM 3 sobre un vídeo completo, que es la
clave de la continuidad de identidad. CUDA 11.8 se fija por ser la versión
soportada por los *drivers* del servidor y compatible con el *build* de PyTorch
`2.6.0+cu118`. El diseño del *backend* —*lock* por GPU, selección por memoria
libre, control de fracción— es una respuesta directa a la realidad de compartir
dos GPUs entre trabajos potencialmente concurrentes sin provocar
*out-of-memory*.

**Referencias**
- NVIDIA (2020). *NVIDIA A100 Tensor Core GPU Architecture*. https://www.nvidia.com/en-us/data-center/a100/
- NVIDIA (2022). *CUDA Toolkit 11.8 Documentation*. https://docs.nvidia.com/cuda/

---

## 11. Calibración de cancha (componente experimental)

### KaliCalib (third_party)

**Categoría**: Calibración robusta de cancha (vía alternativa).

**Rol en el proyecto**
KaliCalib se incluye como código de terceros (`third_party/KaliCalib/`) y se
integra mediante `pipeline/court/kali_detector.py` como una vía **experimental**
de calibración de cancha basada en una red neuronal, frente a la homografía por
*keypoints* de YOLO que constituye el camino por defecto. Sus dependencias
propias (torch, torchvision, `yacs`, `pytorch-ignite`, `deepsport-utilities`)
están aisladas en su `requirements.txt`. Existen resultados de *benchmark* en
`docs/results/kali_*`.

**Alternativas consideradas**
La alternativa es la homografía por *keypoints* (OpenCV + YOLO), que es la activa
por defecto. KaliCalib se mantiene para contrastar precisión de calibración.

**Justificación de la elección**
Se incorpora KaliCalib porque la calibración de cancha en *broadcast* es uno de
los problemas más difíciles del proyecto, y disponer de un método publicado y
robusto como referencia permite validar y comparar la homografía propia. Se
mantiene honestamente como componente experimental/comparativo, no como camino de
producción, dado su mayor coste de integración y dependencias.

**Referencias**
- Maglo, A., Orcesi, A., Pham, Q.-C. (2023). *KaliCalib: A Framework for Basketball Court Registration*. (PDF en `docs/references/KaliCalib.pdf`.)

---

## 12. Entorno de desarrollo y herramientas auxiliares

### Conda, Git, pytest, ffmpeg, monitorización

- **Conda** gestiona el entorno único `tfg-baloncesto`, que contiene todas las
  dependencias incluyendo PyTorch con CUDA. Se eligió sobre `venv`/Poetry porque
  resuelve mejor las dependencias binarias de CUDA y librerías científicas. Los
  *scripts* (`serve.sh`, `run_batch.sh`) invocan explícitamente sus binarios.
- **Git** controla el versionado, con un flujo de trabajo **Kanban** reflejado en
  los mensajes de *commit* (`[Kanban: DOC-MEM] ...`).
- **pytest (9.0.3)** ejecuta la suite de pruebas de lógica pura del proyecto
  (`tests/`, `pytest.ini`), diseñada para correr sin GPU; valida la lógica de
  posesión, geometría y tácticas de forma reproducible en CI o local.
- **nvidia-ml-py / pynvml (12.575)** y **psutil (7.2.2)** alimentan el panel de
  estadísticas de la web (`/api/system/stats`), leyendo uso/memoria de GPU y CPU;
  el *backend* cae a parsear `nvidia-smi` si pynvml falla.
- **pycocotools (2.0.11)** se usa solo para evaluar la detección de RF-DETR en
  formato COCO (mAP), no en *runtime*.
- **roboflow (1.3.3)** y **python-dotenv (1.2.2)** son de soporte al
  entrenamiento: descarga de datasets etiquetados y carga de claves
  (`HF_TOKEN`, `ROBOFLOW_API_KEY`) desde `.env`.
- **uvicorn (0.46.0)** es el servidor ASGI que ejecuta la app FastAPI;
  **python-multipart (0.0.28)** habilita la subida de ficheros.

### Documentación y diagramas: PlantUML (1.2024.7) y Markdown

La documentación de la memoria se redacta en **Markdown** (`docs/`, este mismo
fichero) y los diagramas UML —casos de uso, clases, componentes y secuencia— se
mantienen como código en **PlantUML** (`docs/uml/*.puml`, renderizados a PNG por
`render.sh`). Se eligió PlantUML sobre herramientas gráficas (draw.io) porque los
diagramas-como-código se versionan con Git y se regeneran de forma reproducible;
el motor interno *Smetana* evita la dependencia de Graphviz en el servidor.

---

## ⚠️ Pendiente de verificación

Esta sección recoge los puntos que conviene revisar o completar manualmente antes
de dar el capítulo por cerrado.

**Versiones inferidas del entorno (no fijadas en `requirements.txt`).** El
`requirements.txt` raíz declara la mayoría de paquetes **sin versión**. Las
versiones indicadas en este capítulo (PyTorch 2.6.0+cu118, NumPy 1.26.4, OpenCV
4.13.0, transformers 5.8.1, Ultralytics 8.4.50, RF-DETR 1.6.5, boxmot 19.0.0,
scikit-learn 1.7.2, umap-learn 0.5.12, PEFT 0.19.1, Pillow 12.2.0, roboflow
1.3.3, python-dotenv 1.2.2, pytest 9.0.3, matplotlib 3.10.9, psutil 7.2.2,
pynvml/nvidia-ml-py 12.575, pycocotools 2.0.11) se han **leído del entorno Conda
`tfg-baloncesto` instalado**, no del fichero de dependencias. Conviene fijarlas
en `requirements.txt` para garantizar reproducibilidad.

**Discrepancia de versión en `supervision`.** El `requirements.txt` fija
`supervision==0.27.0`, pero el entorno instalado tiene **0.28.0**. Debe unificarse
el criterio (actualizar el *pin* o reinstalar la versión fijada).

**Dependencia instalada desde rama git no publicada.** `sports` se instala desde
`git+https://github.com/roboflow/sports.git@feat/basketball`, una rama de
*feature* no publicada en PyPI. Es un riesgo de reproducibilidad: conviene
anclar a un *commit* concreto (no solo a la rama) o documentar el *hash* usado.

**Containerización: de Docker (no viable) a Apptainer.** Existen
`backend/Dockerfile` y `frontend/Dockerfile`, pero **ambos están vacíos** (0
bytes): la containerización estaba declarada pero nunca implementada. Se
comprobó empíricamente que **Docker no es viable en el servidor**: el daemon
corre como `root`, el usuario no pertenece a ningún grupo `docker` (que ni
siquiera existe) y no hay privilegios `sudo` para resolverlo. Como sustituto
reproducible y sin root se adoptó **Apptainer** (estándar de contenedores en
entornos HPC con GPU), que funciona en el usuario actual y expone la GPU con
`--nv`. La receta vive en `deploy/apptainer/` (`environment.yml` con versiones
ancladas como fuente de verdad + `tfg.def`), de forma aditiva y sin alterar el
despliegue real actual, que sigue siendo `serve.sh` (Conda + Node embebido +
Uvicorn). Véase `docs/reproducibilidad-apptainer.md`.

**Módulos de *backend* vacíos (arquitectura abandonada).** El árbol
`backend/app/core/` contiene `classifier/` (con `graph_builder.py`,
`inference.py`, `model.py`), `expert/` (`engine.py`, `rules.py`) y `vision/`
(`detector.py`, `homography.py`, `tracker.py`), además de `pipeline.py` y
`db/` — **todos los ficheros están vacíos (0 líneas)**. Parecen el andamiaje de
una arquitectura inicial (posible clasificador por *graph neural network* +
sistema experto de reglas) que se descartó en favor del *pipeline* actual
(`pipeline/` invocado como subproceso). No deben describirse como tecnologías
del sistema; conviene eliminarlos del repositorio o aclarar su estado.

**Tecnologías sin justificación explícita en el código.** SmolVLM2 y SigLIP se
usan de forma efectiva (OCR de dorsal y *embeddings* de equipo), pero la elección
concreta de **estos** modelos frente a otros VLM/codificadores no está razonada
en el código; si se quiere una sección propia para cada uno, la justificación
debe redactarse manualmente a partir del criterio del autor (probablemente:
tamaño reducido para caber en VRAM junto a SAM, y disponibilidad en Hugging
Face).

**Dependencias presentes en el entorno pero no importadas directamente.** `scipy`
(1.15.3) está en el entorno pero **no aparece importado** en `pipeline/` ni
`backend/`; es muy probablemente una dependencia transitiva (de scikit-learn,
umap-learn o KaliCalib). No se ha incluido como tecnología propia por no usarse
directamente; verificar si en algún punto se desea usar para interpolación de
trayectorias.

**Editor / IDE.** No hay evidencia en el repositorio del editor usado (VSCode,
PyCharm…). Si la memoria exige mencionarlo, debe añadirse manualmente; no se ha
inferido por falta de pruebas.
