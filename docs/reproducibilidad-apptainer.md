# Reproducibilidad del entorno: de Docker (no viable) a Apptainer

**Fecha:** 2026-06-21
**Estado:** Artefactos añadidos en `deploy/apptainer/`. **Aditivo y aislado**: no
modifica el pipeline, el backend ni el despliegue actual (`serve.sh`). Si la
imagen no se construyera o no funcionara, el proyecto sigue ejecutándose
exactamente igual que antes.

---

## 1. Problema

La memoria menciona Docker como tecnología de despliegue, pero existen
`backend/Dockerfile` y `frontend/Dockerfile` **vacíos** (0 bytes): la
containerización estaba declarada pero **nunca implementada**. El despliegue
real se hace con `serve.sh` (Conda + Node embebido + Uvicorn).

Al intentar usar Docker se comprobó **empíricamente** que **no es viable en el
servidor**:

| Comprobación | Resultado |
| --- | --- |
| Cliente Docker instalado | Sí (29.3.1, vía snap) |
| `docker build` (Dockerfile trivial) | ❌ `permission denied` sobre `/var/run/docker.sock` |
| Usuario en grupo `docker` | ❌ No; el grupo `docker` **ni siquiera existe** |
| Daemon Docker | Corre como `root`; socket `root:root` (660) |
| Alternativas daemonless (podman/nerdctl) | ❌ No instaladas |
| Docker rootless | ❌ Faltan `rootlesskit`/`slirp4netns`/`fuse-overlayfs` |

El bloqueo está en el **acceso al daemon**, que corre como root. Todas las vías
para resolverlo (añadir el usuario al grupo `docker`, usar el daemon del
sistema, o instalar las dependencias de modo rootless) **requieren `sudo`**, del
que no se dispone en el servidor.

## 2. Solución adoptada: Apptainer

[Apptainer](https://apptainer.org) (antes Singularity) es el estándar de
contenedores en entornos HPC/GPU **sin privilegios de root**. Está instalado y
se verificó que **funciona en el usuario actual sin sudo** (descarga, conversión
a formato SIF y ejecución de una imagen de prueba).

Ventajas frente a Docker **en este escenario concreto**:

- **Rootless por diseño**: no necesita daemon, ni grupo `docker`, ni `sudo`.
- **GPU nativa** con `--nv` (expone las A100 sin `nvidia-container-toolkit`).
- **Portabilidad**: la imagen es **un único fichero `.sif`** que se copia y
  ejecuta en otro servidor GPU o clúster HPC (donde Docker suele estar vetado).
- **Interoperable con Docker**: parte de imágenes `docker://` y de definiciones
  estilo Dockerfile, así que no se pierde compatibilidad con quien sí tenga
  Docker.

## 3. Arquitectura de reproducibilidad

El entorno real es un híbrido (conda + pip + git + ruta local) e internamente
inconsistente, por lo que la reproducción se hace en **dos capas**:

```
environment.yml          ← CAPA 1 (conda): Python, CUDA 11.8, MKL, ffmpeg,
      │                     nodejs y libs de sistema (export fiel del entorno)
      │
requirements-lock.txt    ← CAPA 2 (pip): conjunto EXACTO de paquetes pip,
      │                     instalado con --no-deps (salta el resolutor)
      ▼
tfg.def                  ← receta Apptainer; aplica capa 1 + capa 2
      │
      ▼
tfg.sif                  ← artefacto CONGELADO y portable (no se versiona en git)
```

Esto resuelve los riesgos de reproducibilidad que `conda` por sí solo no cubre:

1. **CUDA + drivers GPU**: la imagen fija la capa de sistema (CUDA 11.8).
2. **Dependencia de rama git no publicada**: `sports` queda **anclado a un
   commit exacto** (`415751384e34f1cb7089a00909e0d7932fe73a75`) en lugar de a la
   rama `feat/basketball`.
3. **Deriva de versiones**: todo el conjunto pip queda **anclado a versión exacta**
   (incl. `supervision==0.28.0`, antes mal fijado a 0.27.0).

Los **modelos y datos pesados** (`models/`, `data/`, ~2 GB) **no** entran en la
imagen: se montan en ejecución. La imagen reproduce **código + entorno**, no los
pesos (que se descargan/enlazan aparte, igual que en el flujo actual).

### Por qué `--no-deps` (hallazgos del build real)

Los intentos de build destaparon que el entorno `tfg-baloncesto` **no es
trivialmente reproducible**, lo cual es en sí un resultado relevante:

- **El entorno viola metadatos de sus propios paquetes.** `opencv-python==4.13`
  declara `numpy>=2` en Python 3.10, pero el entorno usa `numpy==1.26.4`. El
  resolutor estricto de pip rechaza esa combinación; `--no-deps` reproduce el
  conjunto exacto ya validado sin re-resolver.
- **Metadatos de `torch` inconsistentes.** El registro decía `2.7.1+cu118`, pero
  el módulo que carga Python es `2.6.0+cu118` (una actualización a medias). Se
  ancla a la versión **realmente importada** (2.6.0, que casa con torchvision
  0.21.0).
- **Paquetes residuales no usados, excluidos del lock.** `torchaudio` (falla al
  importar por símbolo ABI no definido), `sam3` (instalado desde ruta local) y
  `pycuda` (sin wheel; requeriría el toolkit CUDA completo para compilar). **El
  pipeline no importa ninguno** (TensorRT se usa vía Ultralytics y está
  desactivado por defecto), así que se excluyen sin afectar a la funcionalidad.
- **Entorno compartido y cargado** (~520 paquetes: Django, Gradio, label-studio,
  PaddleOCR…). El lock lo reproduce fielmente; una limpieza a un entorno mínimo
  queda como mejora futura.

## 4. Ficheros añadidos

| Fichero | Propósito |
| --- | --- |
| `deploy/apptainer/environment.yml` | Capa conda: Python, CUDA 11.8 y libs de sistema |
| `deploy/apptainer/requirements-lock.txt` | Capa pip: conjunto exacto de paquetes (instalado con `--no-deps`) |
| `deploy/apptainer/tfg.def` | Definición de la imagen Apptainer |
| `deploy/apptainer/bundle_models.sh` | Empaqueta los pesos (dereferencia symlinks) para portar a otro host |
| `docs/reproducibilidad-apptainer.md` | Este documento |

Ninguno modifica código existente. `serve.sh`, `run.py`, `requirements.txt` y el
pipeline quedan intactos.

## 5. Uso

Construir la imagen (desde la raíz del repositorio):

```bash
apptainer build --fakeroot deploy/apptainer/tfg.sif deploy/apptainer/tfg.def
```

Ejecutar con GPU:

```bash
# Pipeline sobre un vídeo
apptainer run  --nv deploy/apptainer/tfg.sif run.py data/<video>.mp4

# Suite de tests del capítulo 7
apptainer exec --nv deploy/apptainer/tfg.sif pytest
```

> El `.sif` resultante no debe versionarse en git (es un artefacto pesado); ya
> está en `.gitignore`. La receta (`tfg.def`, `environment.yml`,
> `requirements-lock.txt`) sí se versiona.

### Modelos y datos en otro entorno (`--bind`)

La imagen reproduce **código + entorno**, pero **no** los pesos. En este servidor
varios modelos de `models/` son *symlinks* al proyecto original
(`tfg-baloncesto-tacticas`), que se rompen en otra máquina. Pesos que usa el
pipeline:

| Grupo | Tamaño real | ¿Necesario? |
| --- | --- | --- |
| `models/detection` (RF-DETR) | 122 MB | Sí |
| `models/court-keypoints` (YOLO-pose) | 42 MB | Sí |
| `models/jersey-ocr` (SmolVLM2) | 972 MB | Sí (OCR de dorsal) |
| `models/sam3` (SAM 3) | 6,5 GB | Solo con `--tracker sam` (por defecto) |
| `legibility`, `parseq-nba`, `reid-osnet` | <175 MB | Opcionales (bootstrap/alternativas) |

**Empaquetar los pesos** (dereferencia los symlinks a ficheros reales):

```bash
bash deploy/apptainer/bundle_models.sh              # núcleo (~1,1 GB)
bash deploy/apptainer/bundle_models.sh --with-sam3  # + SAM3 (~7,7 GB)
```

**Ejecutar en el host destino** montando los pesos con `--bind`:

```bash
# Opción A: colocar 'models/' junto al repo y ejecutar desde su raíz
#   (Apptainer monta $PWD por defecto; el pipeline lee rutas relativas).
apptainer run --nv deploy/apptainer/tfg.sif run.py data/clip.mp4

# Opción B: montar los pesos desde otra ruta
apptainer run --nv \
  --bind /ruta/destino/models:"$PWD"/models \
  deploy/apptainer/tfg.sif run.py data/clip.mp4
```

**Evitar mover los 6,5 GB de SAM3**: usar el tracker alternativo, que no lo
necesita: `run.py data/clip.mp4 --tracker botsort`.

## 6. Estado de validación

- ✅ Apptainer disponible y funcional sin sudo (probado con imagen de prueba).
- ✅ Versiones ancladas a partir del entorno real (`pip freeze`).
- ✅ **Imagen `tfg.sif` construida de extremo a extremo** (`apptainer build
  --fakeroot`, ~13 GB, sin sudo) el 2026-06-21.
- ✅ **Stack del pipeline importa dentro del contenedor**: torch 2.6.0+cu118,
  torchvision 0.21.0+cu118, cv2 4.13.0, numpy 1.26.4, supervision 0.28.0,
  transformers 5.8.1, ultralytics 8.4.50, rfdetr, scikit-learn, umap, sports.
- ✅ **GPU verificada con `--nv`**: `torch.cuda.is_available()` → True, 2×
  NVIDIA A100-SXM4-40GB detectadas.
- ✅ **Empaquetado de pesos** (`bundle_models.sh`) validado: dereferencia los
  symlinks de `models/` a ficheros reales portables.

El despliegue de referencia para la app web sigue siendo `serve.sh`; la imagen
Apptainer aporta el entorno reproducible y portable para ejecutar el pipeline.

## 7. Implicación para la memoria

Las menciones a **Docker** como tecnología de despliegue deben corregirse, por
ser engañosas (Dockerfiles vacíos, no ejecutable sin root). La opción honesta y
técnicamente más sólida es sustituirlas por **Apptainer**, justificando la
elección por la ausencia de privilegios root en el servidor y por ser el
estándar de contenedores en entornos HPC con GPU.
