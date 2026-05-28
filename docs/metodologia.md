# Metodología: Kanban + CRISP-DM

## 1. Marco metodológico

Este TFG combina dos metodologías complementarias:

- **CRISP-DM** (*Cross Industry Standard Process for Data Mining*) como marco de proceso para proyectos de ciencia de datos e IA, que define seis fases iterativas: Business Understanding, Data Understanding, Data Preparation, Modeling, Evaluation y Deployment.
- **Kanban** como sistema de gestión del flujo de trabajo, limitando el trabajo en curso (WIP = 1 tarjeta activa) y haciendo visible el avance incremental.

La combinación es natural: CRISP-DM define *qué* hacer y en qué orden; Kanban define *cómo* gestionar el avance dentro de cada fase.

---

## 2. Tablero Kanban con fases CRISP-DM

El tablero se implementó como [GitHub Projects](https://github.com/bollicaolover/tfg-junio/issues) con una columna por fase CRISP-DM. Cada tarjeta corresponde a un módulo entregable, vinculado a un commit concreto del repositorio.

### Columnas y tarjetas completadas

| # | Tarjeta (issue) | Fase CRISP-DM | Commit |
|---|-----------------|---------------|--------|
| BU-1 | Definición del problema y alcance | Business Understanding | `e089e45` |
| BU-2 | Arquitectura modular y config global | Business Understanding | `9a122cb` |
| DU-1 | Exploración del dataset y modelos base | Data Understanding | `71f2465` |
| DP-1 | Detector RF-DETR local (11 clases) | Data Preparation | `261e036` |
| DP-2 | Geometría de cancha y keypoints | Data Preparation | `ddacadc` |
| M-1 | Homografía y modelo PnP | Modeling | `4277600` |
| M-2 | Render 2D, estabilizador, suavizado | Modeling | `9730a01` |
| M-3 | I/O de vídeo e interfaces de tracking | Modeling | `404127e` |
| M-4 | SAM3 tracker (prompt-once + re-prompt) | Modeling | `be5eca9` |
| M-5 | Ball tracker y punto de apoyo | Modeling | `6faee31` |
| M-6 | Clasificador de equipos SigLIP | Modeling | `7506f54` |
| M-7 | OCR de dorsal SmolVLM2 (voto IoS) | Modeling | `efc179e` |
| M-8 | Roster de jugadores y entrenamiento | Modeling | `0a129b2` |
| E-1 | Resolver de posesión | Evaluation | `2485a57` |
| E-2 | Shot tracker (eventos de canasta) | Evaluation | `65fb57e` |
| D-1 | Orquestador principal por frame | Deployment | `b4c7ca3` |
| D-2 | Entrypoints run.py y run_batch.sh | Deployment | `7e775bd` |
| D-3 | README y documentación | Deployment | `161c5f2` |
| E-3 | Segmentación de sesiones SAM (iteración) | Evaluation | `10e1736` |

---

## 3. Evidencia de la metodología Kanban

### 3.1 WIP limitado

El historial de commits muestra entregas de un módulo a la vez, con commits atómicos. Nunca hay dos módulos en desarrollo simultáneo: cada commit cierra una tarjeta antes de abrir la siguiente.

### 3.2 Flujo visible

Las etiquetas de los issues en GitHub (`CRISP-DM: Modeling`, `CRISP-DM: Evaluation`, etc.) junto con el estado `Kanban: Done` hacen visible el avance en todo momento.

### 3.3 Entrega incremental

Cada tarjeta deja el sistema en un estado ejecutable:
- Tras `M-3` (I/O + interfaces): el pipeline arranca aunque no produce salida útil.
- Tras `M-4` (SAM3): hay tracking real de jugadores.
- Tras `E-1` (posesión): el sistema produce estadísticas básicas.
- Tras `D-1` (orquestador): el pipeline es ejecutable de extremo a extremo.

---

## 4. Naturaleza iterativa de CRISP-DM

La tarjeta **E-3** ilustra el ciclo de retroalimentación central de CRISP-DM: un problema detectado durante el Deployment (degradación del tracking SAM en vídeos largos por acumulación de estado) genera una nueva iteración que recorre las fases Evaluation → Modeling antes de volver a Deployment.

```
Business Understanding
        ↓
Data Understanding
        ↓
Data Preparation
        ↓
  Modeling ←──────────────┐
        ↓                  │ iteración
  Evaluation ─── problema detectado ─── E-3
        ↓
  Deployment
```

Esto demuestra que el proceso no fue lineal sino iterativo-incremental, lo que es la característica definitoria de CRISP-DM frente a otros marcos de proceso.

---

## 5. Trazabilidad completa

Cada decisión metodológica tiene traza directa al código:

| Principio | Evidencia |
|-----------|-----------|
| Kanban WIP=1 | `git log --oneline`: un módulo por commit |
| Definición of Done explícita | Issues con checklist de criterios de aceptación |
| Fases CRISP-DM | Labels de GitHub en cada issue |
| Iteración CRISP-DM | Issue E-3 + commits `10e1736` / `301f6f3` |
| Entrega continua | `run.py` ejecutable desde el primer orquestador |
