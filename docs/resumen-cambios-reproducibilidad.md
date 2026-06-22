# Resumen de cambios: containerización y reproducibilidad (Docker → Apptainer)

**Fecha:** 2026-06-21
**Autor:** gdfraile (con asistencia de Claude Code)
**Alcance:** todo lo realizado es **aditivo y aislado**. No se ha modificado el
pipeline, el *backend*, `serve.sh`, `run.py` ni `requirements.txt`. Si los
artefactos nuevos fallaran, el proyecto sigue funcionando exactamente igual.

Documento técnico detallado: [`reproducibilidad-apptainer.md`](reproducibilidad-apptainer.md).

---

## 1. Punto de partida y motivación

La memoria presentaba **Docker** como tecnología de despliegue, pero existían
`backend/Dockerfile` y `frontend/Dockerfile` **vacíos** (0 bytes): la
containerización estaba declarada pero nunca implementada. El despliegue real se
hacía solo con `serve.sh` (Conda + Node embebido + Uvicorn).

Surgió la pregunta de si convenía completar Docker o si había una alternativa
mejor, dado que el entorno real es un servidor con 2× A100 **sin privilegios
sudo**.

## 2. Investigación: Docker no es viable en el servidor

Se comprobó **empíricamente** (no por suposición):

| Comprobación | Resultado |
| --- | --- |
| Cliente Docker instalado | Sí (29.3.1, snap) |
| `docker build` (Dockerfile trivial) | ❌ `permission denied` en `/var/run/docker.sock` |
| Usuario en grupo `docker` | ❌ No; el grupo `docker` no existe |
| Daemon Docker | Corre como `root`; socket `root:root` |
| Docker rootless | ❌ Faltan `rootlesskit`/`slirp4netns`/`fuse-overlayfs` |
| Alternativas (podman/nerdctl) | ❌ No instaladas |

**Conclusión:** el bloqueo está en el acceso al *daemon* (root). Todas las
soluciones requieren `sudo`, del que no se dispone.

## 3. Solución adoptada: Apptainer

[Apptainer](https://apptainer.org) (antes Singularity) es el estándar de
contenedores en entornos HPC/GPU **sin root**. Se verificó que funciona en el
usuario actual (descarga, conversión a SIF y ejecución de una imagen de prueba),
con GPU nativa vía `--nv` e interoperable con Docker (`docker://`).

## 4. Arquitectura de reproducibilidad (dos capas)

El entorno real resultó ser un híbrido (conda + pip + git + ruta local) e
internamente inconsistente, así que la reproducción se hace en dos capas:

```
environment.yml        ← capa CONDA (Python, CUDA 11.8, MKL, ffmpeg, nodejs, libs)
requirements-lock.txt  ← capa PIP (conjunto exacto, instalado con --no-deps)
        │
        ▼
tfg.def  →  apptainer build --fakeroot  →  tfg.sif (imagen portable, sin root)
```

## 5. Problemas reales encontrados (y resueltos)

El proceso de *build* destapó que el entorno `tfg-baloncesto` **no era
trivialmente reproducible** — un hallazgo relevante en sí mismo:

1. **Conflicto de pins.** Fijar solo un subconjunto de paquetes provocaba
   `ResolutionImpossible` (numpy). → Se pasó a un *lockfile* completo.
2. **Metadatos violados.** `opencv-python==4.13` declara `numpy>=2`, pero el
   entorno usa `numpy==1.26.4`. El resolutor estricto de pip lo rechaza. → Se
   instala con `--no-deps` para reproducir el conjunto exacto ya validado.
3. **Metadatos de `torch` inconsistentes.** El registro decía `2.7.1+cu118`,
   pero Python carga `2.6.0+cu118`. → Anclado a la versión realmente importada.
4. **Paquetes residuales no usados:** `torchaudio` (roto, símbolo ABI), `sam3`
   (ruta local) y `pycuda` (sin *wheel*, requeriría toolkit CUDA). El pipeline
   no los importa → excluidos.
5. **Librerías de sistema de OpenCV** (`libGL.so.1`). → Añadidas vía `apt`
   (`libgl1`, `libglib2.0-0`).
6. **Entorno compartido y cargado** (~520 paquetes, con Django/Gradio/
   label-studio ajenos al TFG). El lock lo reproduce; adelgazarlo queda como
   mejora futura.

## 6. Validación (todo verificado de extremo a extremo)

- ✅ `apptainer build --fakeroot` → `tfg.sif` (~13 GB) **sin sudo**.
- ✅ Imports del pipeline dentro del contenedor: torch 2.6.0+cu118, torchvision
  0.21.0+cu118, cv2 4.13.0, numpy 1.26.4, supervision 0.28.0, transformers
  5.8.1, ultralytics 8.4.50, rfdetr, scikit-learn, umap, sports.
- ✅ GPU con `--nv`: `torch.cuda.is_available()` → True, **2× A100-SXM4-40GB**.
- ✅ `bundle_models.sh`: dereferencia symlinks de `models/` a ficheros reales.

## 7. Portabilidad de los pesos

La imagen reproduce **código + entorno**, no los pesos. En el servidor, varios
modelos de `models/` son *symlinks* al proyecto original que se rompen en otra
máquina. Solución:

- **`bundle_models.sh`** empaqueta los pesos (resolviendo symlinks): núcleo
  ~1,1 GB; con SAM3, ~7,7 GB.
- Ejecución en destino con `--bind` (o colocando `models/` junto al repo, ya que
  Apptainer monta `$PWD`).
- Para no mover los 6,5 GB de SAM3: ejecutar con `--tracker botsort` (no lo
  necesita), un flag de CLI ya existente.

## 8. Ficheros nuevos y modificados

**Nuevos (artefactos de despliegue, en `deploy/apptainer/`):**

| Fichero | Propósito |
| --- | --- |
| `environment.yml` | Capa conda (Python, CUDA 11.8, libs de sistema) |
| `requirements-lock.txt` | Capa pip exacta (instalada con `--no-deps`) |
| `tfg.def` | Definición de la imagen Apptainer |
| `bundle_models.sh` | Empaqueta los pesos para portar a otro host |

**Documentación nueva (en `docs/`):**

| Fichero | Propósito |
| --- | --- |
| `reproducibilidad-apptainer.md` | Documento técnico detallado |
| `resumen-cambios-reproducibilidad.md` | Este resumen |

**Modificados:**

- `.gitignore`: ignora `*.sif`, `deploy/apptainer/build.exit` y
  `deploy/apptainer/models_bundle/` (se versiona la receta, no los artefactos
  pesados).
- Memoria — sustitución de menciones engañosas a *Docker* por *Apptainer*
  (respetando el registro histórico de *commits* y los *logs* fechados):
  `memoria_tecnologias.md`, `memoria_fases_proyecto.md`, `estado-del-arte.md`,
  `plan-tfg.md`, `comparativa-tfg-junio-vs-baloncesto-tacticas.md`.

## 9. Cómo usarlo (resumen rápido)

```bash
# 1. Construir la imagen (sin sudo)
apptainer build --fakeroot deploy/apptainer/tfg.sif deploy/apptainer/tfg.def

# 2. Ejecutar el pipeline con GPU
apptainer run --nv deploy/apptainer/tfg.sif run.py data/clip.mp4

# 3. Tests
apptainer exec --nv deploy/apptainer/tfg.sif pytest

# 4. Portar a otra máquina: empaquetar pesos y mover .sif + bundle
bash deploy/apptainer/bundle_models.sh --with-sam3
scp deploy/apptainer/tfg.sif deploy/apptainer/models_bundle/models usuario@host:/destino/
```

## 10. Mejoras futuras (opcionales)

1. **Adelgazar el entorno** a un mínimo limpio (~15 dependencias reales) → imagen
   mucho menor que los 13 GB actuales.
2. **Descarga de SAM3 desde HuggingFace** (`facebook/sam3`) configurable, para no
   depender de los pesos locales (requeriría exponer `model_id` por env/CLI).
3. Completar la portabilidad de la **app web** (frontend + backend) en el mismo
   flujo de contenedor, si se desea un despliegue "llave en mano".
