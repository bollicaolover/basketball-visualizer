# Análisis de paralelización del pipeline ML

Documento de decisión técnica sobre si conviene semiparalelizar las etapas del
pipeline de visión (`pipeline/orchestrator.py`). Conclusión anticipada: **no
merece la pena** implementar paralelismo intra-frame en el estado actual del
proyecto.

Diagrama de flujo de datos corregido: [`uml/dfd_ml_pipeline.svg`](uml/dfd_ml_pipeline.svg).

---

## 1. Contexto

El DFD inicial del pipeline representaba dos ramas paralelas a partir de la
extracción de frames:

- **2.0** Detección y tracking (RF-DETR · SAM 3)
- **3.0** Geometría e identidad (Homografía · SigLIP · OCR)

Esa disposición sugería que ambas ramas podían ejecutarse de forma independiente
antes de converger en la analítica táctica. Tras revisar el código y las métricas
de rendimiento medidas, se concluye que:

1. El flujo real es **secuencial por frame**, con dependencias cruzadas.
2. El único solapamiento teórico (homografía ∥ RF-DETR, SigLIP ∥ OCR) ahorraría
   menos de un **4 %** del tiempo total.
3. Los cuellos de botella (SAM 3 y SmolVLM2) permanecen en el camino crítico
   aunque se paralelicen etapas periféricas.

---

## 2. Flujo real implementado

Orden de ejecución en `_process_frame` (`pipeline/orchestrator.py`):

| Paso | Etapa | Depende de |
|------|-------|------------|
| 0 (pre-bucle) | Calibración SigLIP + `SAM.prepare_video()` | Vídeo completo |
| 1 | Decodificación de frame | — |
| 2 | Detección RF-DETR | Frame |
| 3 | Keypoints + homografía | Frame |
| 4 | Tracking SAM 3 / BoT-SORT | Frame (+ RF-DETR si BoT-SORT) |
| 5 | Clasificación de equipos (SigLIP) | Tracklets |
| 6 | OCR de dorsal (SmolVLM2) | Tracklets + cajas `number` |
| 7 | Balón, posesión y tiros | RF-DETR + tracklets + homografía |
| 8 | Proyección 2D + render | Homografía + tracklets + equipos |
| 9 (post-bucle) | Táctica (pantallas) + tiro 3D | Metadata JSON |

La analítica no es un bloque monolítico posterior: **posesión y tiros** se
calculan en el bucle; **pantallas y reconstrucción 3D** son post-proceso sobre el
JSON ya escrito.

---

## 3. Dependencias que impiden el paralelismo pleno

```
frame
  ├─► RF-DETR ──► SAM ──► SigLIP ──┐
  │                  └─► OCR ───────┼─► proyección 2D ──► render
  ├─► homografía ──────────────────┘
  └─► (balón desde RF-DETR) ──► posesión / tiros
```

- **SigLIP y OCR** necesitan `track_id` y máscaras de SAM; no pueden preceder al
  tracking.
- **Proyección 2D** necesita homografía **y** tracklets; no es salida exclusiva
  del bloque de geometría.
- **SAM 3** propaga máscaras de forma **temporal** (frame a frame); no admite
  paralelismo entre frames en la implementación actual.
- **OCR** empareja cajas `number` (RF-DETR) con máscaras de jugador (SAM) por
  IoS; requiere ambas ramas.

---

## 4. Semiparalelización teórica evaluada

### 4.1 Opciones viables

| Paralelización | Ahorro estimado | Observación |
|----------------|-----------------|-------------|
| Homografía ∥ RF-DETR | ~31 ms/frame | H (~31 ms) queda oculta bajo RF-DETR (~92 ms) |
| SigLIP ∥ OCR (frames con OCR) | ~20 ms/frame amortizado | OCR cada 5 frames; ahorro ~102 ms en 1/5 |
| Balón ∥ SAM | <2 ms/frame | Etapa de balón despreciable |
| `shot3d` ∥ `tactics` (post-proceso) | Segundos/clip | Fuera del bucle principal |
| Decode ∥ inferencia (doble buffer) | 5–15 ms/frame | Ganancia incierta en clips cortos |

**Total estimado en el bucle principal:** ~50 ms/frame sobre **1.402 ms/frame**
medidos → **≈ 3,5 %** de mejora.

Fuente: clip `boston-celtics-…-q2-10.36-10.32.mp4` (109 frames), NVIDIA A100,
16 jun 2026 — ver [`datos-reales-tfg.md`](datos-reales-tfg.md).

### 4.2 Desglose de tiempos (referencia)

| Etapa | ms/frame | % del total |
|-------|----------|-------------|
| OCR SmolVLM2 | 550,5* | 39,3 |
| Tracking SAM 3 | 424,4 | 30,3 |
| SigLIP equipos | 101,5 | 7,2 |
| RF-DETR | 91,5 | 6,5 |
| Cancha / homografía | 31,3 | 2,2 |
| Resto (render, posesión, I/O) | <10 c/u | <5 |

\* OCR se ejecuta cada 5 frames (`ocr_every=5`); el valor es el coste en frames
activos.

---

## 5. Por qué no compensa paralelizar

### 5.1 Ley de Amdahl

El 69 % del tiempo se concentra en SAM 3 + OCR, etapas **secuenciales y
dependientes**. Paralelizar el 31 % restante tiene un techo teórico bajo: incluso
eliminar por completo homografía, SigLIP y decode apenas acercaría el sistema al
60 % del tiempo actual, no a tiempo real.

### 5.2 Complejidad vs. beneficio

Implementar CUDA streams, doble buffer de frames y joins explícitos entre
etapas:

- Aumenta la superficie de bugs (condiciones de carrera, sincronización GPU).
- Dificulta el profiling (`StageTimer` deja de ser trivial).
- Exige validar VRAM con modelos concurrentes (pico medido ≈ 7,8 GB en A100).

A cambio, el ahorro esperado (~3,5 %) no altera la naturaleza del sistema:
**procesado por lotes a ~0,7 fps**, no tiempo real.

### 5.3 Alternativas con mejor relación coste/beneficio

| Vía | Impacto esperado | Estado |
|-----|------------------|--------|
| Chunking multi-GPU | 1,48× en clip corto; →2× en clips largos | Implementado |
| Reducir frecuencia OCR (`ocr_every`) | Lineal con llamadas al VLM | Configurable |
| Cuantización / optimización SAM y VLM | Potencialmente 30–40 % | No implementado |
| BoT-SORT en lugar de SAM 3 | −424 ms/frame tracking | Alternativa existente |

La inversión de esfuerzo en optimización de modelos o en escalado horizontal
(chunking) rinde más que micro-paralelismo intra-frame.

---

## 6. Decisión

**Se mantiene el pipeline secuencial** tal como está en `orchestrator.py`.

- No se implementará semiparalelización intra-frame en esta versión del TFG.
- El DFD se ha corregido para reflejar el **flujo secuencial** y las
  dependencias reales (ver diagrama actualizado).
- Para la memoria: el diagrama anterior se consideraba una **abstracción
  lógica** por dominios funcionales; el diagrama corregido representa el
  **orden de ejecución** fiel al código.

### Excepción menor (no prioritaria)

El post-proceso `shot3d` y `tactics` podrían ejecutarse en paralelo entre sí
(lecturas independientes del metadata). El ahorro es de segundos por clip, no
por frame, y no justifica por sí solo un rediseño del orquestador.

---

## 7. DFD — modelo snowball (versión definitiva)

El diagrama final aplica el patrón **snowball** (contexto acumulativo): cada
proceso enriquece un único paquete de datos que fluye en cascada, equivalente al
`FrameContext` mutable de `pipeline/context.py`. Así se evita el *clutter* de
flechas laterales sin perder rigor técnico.

| Transición | Contenido del contexto |
|------------|------------------------|
| 1.0 → 2.0 | `frame` |
| 2.0 → 3.0 | `frame` + detecciones RF-DETR |
| 3.0 → 4.0 | + homografía |
| 4.0 → 5.0 | + tracklets · balón |
| 5.0 → 6.0 | contexto completo (tracks · H · equipos · dorsales · balón) |
| 6.0 → 6.1 | metadata JSON (post-proceso) |

Cambios respecto a versiones anteriores del DFD:

| Antes | Ahora |
|-------|-------|
| Ramas paralelas 2.0 ∥ 3.0 | Cascada vertical única |
| Flechas laterales cruzadas | Contexto acumulativo por etapa |
| 6.0 con entradas múltiples sueltas | 5.0 entrega el paquete completo a 6.0 |
| Homografía como entrada del tracking | Homografía viaja en el contexto; el tracking no la consume como input directo |
| OCR genérico | SmolVLM2 (OCR de dorsal) |
| Salida solo API | FastAPI + SPA Vue 3 |

---

## 8. Referencias

- Orquestador: `pipeline/orchestrator.py`
- Métricas de rendimiento: `docs/datos-reales-tfg.md`
- Arquitectura web: `docs/arquitectura.md`
- Diagrama: `docs/uml/dfd_ml_pipeline.svg`
