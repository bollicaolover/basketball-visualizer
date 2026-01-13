"""Configuración global del pipeline `tfg-junio`.

Proyecto modular que combina el flujo del cuaderno de Roboflow
(RF-DETR 11 clases → SAM tracking → equipos SigLIP → OCR dorsal) con la
proyección al plano 2D y el tracking de balón portados del proyecto original.

Las constantes de clases siguen el dataset local `basketball-player-detection`
(11 clases, idénticas al cuaderno). Las dataclasses de cancha/render/smoothing
son las mismas que consumen los módulos portados en `pipeline/court/*` y
`pipeline/tracking/*`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Tuple

from pipeline.court.smoothing import SmoothingSettings


# ---------------------------------------------------------------------------
# Clases del detector RF-DETR (dataset `basketball-player-detection`, 11 clases)
# ---------------------------------------------------------------------------
CLASS_NAMES: Tuple[str, ...] = (
    "basketball",            # 0
    "ball",                  # 1
    "ball-in-basket",        # 2
    "number",                # 3
    "player",                # 4
    "player-in-possession",  # 5
    "player-jump-shot",      # 6
    "player-layup-dunk",     # 7
    "player-shot-block",     # 8
    "referee",               # 9
    "rim",                   # 10
)

# El dataset distingue "basketball" (0) y "ball" (1): ambos son el balón.
BASKETBALL_CLASS: int = 0
BALL_CLASSES: FrozenSet[int] = frozenset({0, 1})
BALL_IN_BASKET_CLASS: int = 2
NUMBER_CLASS: int = 3
# Clase canónica de jugador para las entidades trackeadas (SAM).
PLAYER_CLASS: int = 4
# Detección de "jugador en posesión" del propio RF-DETR: señal entrenada que
# el resolutor de posesión usa como pista primaria (ver pipeline/possession/).
IN_POSSESSION_CLASS: int = 5
# Todas las variantes "player*" (incl. acciones) cuentan como jugador.
PLAYER_CLASSES: FrozenSet[int] = frozenset({4, 5, 6, 7, 8})
# Acciones de tiro del detector (lanzamiento exterior y entrada/mate).
JUMP_SHOT_CLASS: int = 6
LAYUP_DUNK_CLASS: int = 7
SHOT_BLOCK_CLASS: int = 8
# Clases que disparan la ventana de tiro (tiro exterior + entrada/mate).
SHOT_ACTION_CLASSES: FrozenSet[int] = frozenset({JUMP_SHOT_CLASS, LAYUP_DUNK_CLASS})
REFEREE_CLASS: int = 9
RIM_CLASS: int = 10
HOOP_CLASS: int = RIM_CLASS  # alias compatible con código de cancha/eventos

# Clases de acción del detector (para eventos de tiro, fase opcional).
ACTION_CLASSES: dict = {
    5: "in_possession",
    6: "jump_shot",
    7: "layup_dunk",
    8: "shot_block",
}

# Normalización ImageNet (recortes de camiseta, si se usara CLIP local).
IMAGENET_MEANS: Tuple[float, float, float] = (0.485, 0.456, 0.406)
IMAGENET_STDS: Tuple[float, float, float] = (0.229, 0.224, 0.225)


# ---------------------------------------------------------------------------
# Detección (RF-DETR local)
# ---------------------------------------------------------------------------
@dataclass
class DetectionSettings:
    """RF-DETR entrenado sobre las 11 clases (paquete `rfdetr`)."""

    # Checkpoint local entrenado (copiado por scripts/fetch_models.py).
    checkpoint_path: str = "models/detection/checkpoint_best_ema.pth"
    # Variante de arquitectura del checkpoint: "base" | "nano" | "medium".
    variant: str = "base"
    resolution: int = 672
    score_threshold: float = 0.4
    iou_threshold: float = 0.9
    device: str = "cuda"


# ---------------------------------------------------------------------------
# Tracking del balón (portado del proyecto original)
# ---------------------------------------------------------------------------
@dataclass
class BallTrackingSettings:
    simple: bool = False
    ema_alpha: float = 0.55
    max_jump_px: float = 180.0
    holdover_frames: int = 18
    match_distance_px: float = 120.0
    min_confidence: float = 0.25


# ---------------------------------------------------------------------------
# Posesión del balón (resolutor híbrido: clase-5 + proximidad en imagen)
# ---------------------------------------------------------------------------
@dataclass
class PossessionSettings:
    """Determina qué track tiene el balón cada frame.

    La decisión se toma en **espacio imagen** (no proyectando el balón al
    suelo: la homografía asume punto sobre el plano y un balón en mano sufre
    parallax de varios pies). Señal primaria: la detección entrenada
    ``player-in-possession`` (clase 5) asociada al track por IoU. Señal
    secundaria: distancia balón→jugador normalizada por la altura del bbox
    del jugador (invariante a la perspectiva). Una máquina de estados con
    histéresis estabiliza la salida y modela el balón suelto (pases/tiros).
    """

    enabled: bool = True
    # IoU mínimo para asociar una caja `player-in-possession` con un track.
    class5_iou: float = 0.30
    # Distancia balón→jugador máxima, en múltiplos de la altura del bbox del
    # jugador (≈6.5 ft de alto). 0.6 ≈ el balón a poco menos de una cabeza.
    max_ball_distance_heights: float = 0.6
    # Histéresis: frames consecutivos que un nuevo candidato debe ganar para
    # arrebatar la posesión (evita parpadeo en forcejeos).
    switch_frames: int = 3
    # Frames sin ningún candidato válido para declarar "balón suelto" (None).
    loose_frames: int = 5
    # Margen en píxeles que se añade al bbox del jugador antes de medir
    # distancia al balón (absorbe imprecisión de SAM en los bordes del bbox).
    bbox_margin_px: float = 15.0


# ---------------------------------------------------------------------------
# Detección de tiro: acierto vs. fallo (señales `ball`, `rim`, `ball-in-basket`)
# ---------------------------------------------------------------------------
@dataclass
class ScoreSettings:
    """Decide el resultado de cada tiro que llega al aro (ver ``pipeline/scoring/``).

    El balón llegando al aro abre una ventana; ``ball-in-basket`` confirmada la
    cierra como ACIERTO, y el balón alejándose (o la ventana expirando) como
    FALLO. Una máquina de estados con cooldown evita recontar rebotes.
    """

    enabled: bool = True
    # Confianza mínima de la caja `ball-in-basket` para considerarla.
    min_confidence: float = 0.30
    # Frames consecutivos de `ball-in-basket` para confirmar un ACIERTO.
    confirm_frames: int = 2
    # Confianza mínima de la caja `rim` para usarla como referencia.
    rim_min_confidence: float = 0.30
    # "Balón en el aro" si dist(balón, centro aro) < factor × alto del aro.
    rim_dist_factor: float = 1.8
    # Disparar la ventana también con las acciones `jump-shot`/`layup-dunk`
    # (clases 6/7): capta entradas y mates fallados aunque el balón esté
    # ocluido por el cuerpo y no se vea llegar al aro.
    use_action_trigger: bool = True
    action_min_confidence: float = 0.40
    # Ventana máxima (frames) que un tiro permanece sin resolver -> FALLO.
    # Algo más larga que con solo balón-en-aro: el disparo por acción ocurre en
    # el lanzamiento, así que hay que cubrir el vuelo del balón hasta el aro.
    resolve_frames: int = 40
    # Frames con el balón lejos del aro (sin canasta) para declarar FALLO.
    # Solo se aplica tras confirmar que el balón llegó al aro.
    clear_frames: int = 4
    # Frames de cooldown tras resolver un tiro (evita recontar el rebote).
    cooldown_frames: int = 30
    # Frames que se mantiene el resalte del resultado en vídeo y mapa.
    display_frames: int = 25


# ---------------------------------------------------------------------------
# Cancha / homografía (portado verbatim — mismos campos que el original)
# ---------------------------------------------------------------------------
@dataclass
class CourtSettings:
    model_path: str = "models/court-keypoints/best.pt"
    engine_path: str = "models/export/court-keypoints_fp16.engine"
    prefer_tensorrt: bool = False
    input_resolution: int = 640
    num_keypoints: int = 33

    min_confidence: float = 0.35
    ema_alpha: float = 0.30
    outlier_max_jump_px: float = 65.0

    ransac_reproj_threshold: float = 5.0
    min_inliers: int = 5
    max_residual_px: float = 15.0
    min_world_x_span_ft: float = 18.0
    min_world_y_span_ft: float = 12.0

    h_ema_alpha: float = 0.35
    h_max_holdover_frames: int = 30

    h_buffer_frames: int = 25
    h_min_buffer_frames: int = 6
    h_move_threshold_px: float = 20.0
    h_move_window_frames: int = 6
    h_move_cumulative_threshold_px: float = 25.0

    # --- Modelo de cámara paramétrico (PnP) ---------------------------------
    # Estimador alternativo de homografía vía pose de cámara (cv2.solvePnP) +
    # filtro de Kalman. Con `use_pnp=False` el pipeline usa el HomographyEstimator
    # clásico (findHomography) — comportamiento por defecto, intacto.
    use_pnp: bool = True
    # Frames con buen fit RANSAC que se acumulan para fijar la focal al arranque.
    pnp_focal_calib_frames: int = 30
    # >0 ⇒ usa esta focal (px) directamente y salta la auto-estimación.
    pnp_focal_override: float = 0.0
    # Mínimo de keypoints válidos para intentar PnP (si no, fallback).
    pnp_min_points: int = 6
    # Umbral de reproyección (px) del RANSAC de solvePnPRansac.
    pnp_ransac_reproj_px: float = 5.0
    # Frames que el Kalman predice sin medición (PnP fallido) antes de caer a fallback.
    pnp_max_holdover_frames: int = 30
    # Ruido de proceso/medición del Kalman (rotación rvec / traslación tvec).
    kf_process_noise_rot: float = 1e-4
    kf_process_noise_trans: float = 1e-2
    kf_measure_noise_rot: float = 1e-3
    kf_measure_noise_trans: float = 1e-1

    verbose: bool = False


# ---------------------------------------------------------------------------
# Equipos (sports.TeamClassifier — SigLIP, fit no supervisado)
# ---------------------------------------------------------------------------
@dataclass
class TeamSettings:
    device: str = "cuda"
    # Frames de calibración: se muestrean recortes de jugador para fit().
    calibration_stride: int = 30
    calibration_max_frames: int = 40
    # Recorte central (como el cuaderno: scale_boxes factor 0.4) para el fit.
    crop_scale: float = 0.4
    # Nombres y colores de equipo (mapeo team_id 0/1 -> equipo del roster).
    # Se asignan tras calibrar (el clustering no garantiza qué id es cada uno).
    team_names: Tuple[str, str] = ("Equipo 0", "Equipo 1")
    # Voto temporal: nº de lecturas consecutivas para fijar el equipo por track.
    votes_to_lock: int = 1


# ---------------------------------------------------------------------------
# Identidad: OCR de dorsal (SmolVLM2 local entrenado) + roster
# ---------------------------------------------------------------------------
@dataclass
class IdentitySettings:
    enabled: bool = True
    # Checkpoint local del SmolVLM2 fine-tuneado (scripts/train_jersey_ocr.py).
    ocr_model_dir: str = "models/jersey-ocr"
    ocr_prompt: str = "Read the number."
    device: str = "cuda"
    # Cadencia: corre OCR 1 de cada N frames (acota latencia del VLM).
    ocr_every: int = 5
    # Recorte del número antes del OCR.
    crop_pad_px: int = 10
    crop_resolution: int = 224
    # Fichero JSON con rosters y colores (vacío = sin lookup de nombres).
    roster_path: str = ""
    # IoS mínimo para emparejar una caja `number` con la máscara de un jugador.
    number_match_ios: float = 0.9
    # Voto temporal: lecturas consecutivas para fijar el número por track.
    votes_to_lock: int = 3
    # Puente de bootstrap: si no hay SmolVLM2 entrenado, usar PARSeq existente.
    fallback_parseq: bool = False


# ---------------------------------------------------------------------------
# SAM 3 (tracking por máscara — portado del proyecto original)
# ---------------------------------------------------------------------------
@dataclass
class SAMSettings:
    model_id: str = "models/sam3"
    device: str = "cuda:0"
    dtype: str = "bfloat16"
    max_objects: int = 24
    mask_logits_threshold: float = 0.0
    reprompt_iou_threshold: float = 0.4
    reprompt_min_frames: int = 5


# ---------------------------------------------------------------------------
# Render del mapa 2D (portado verbatim)
# ---------------------------------------------------------------------------
@dataclass
class RenderSettings:
    map_width_px: int = 940
    map_height_px: int = 540
    padding_ft: float = 4.0

    background_bgr: Tuple[int, int, int] = (37, 21, 17)
    floor_bgr: Tuple[int, int, int] = (142, 178, 208)
    key_bgr: Tuple[int, int, int] = (98, 132, 172)
    line_bgr: Tuple[int, int, int] = (248, 250, 252)
    rim_bgr: Tuple[int, int, int] = (0, 120, 245)
    line_thickness: int = 2
    floor_plank_spacing_px: int = 14
    floor_plank_shade_bgr: Tuple[int, int, int] = (128, 162, 192)

    player_radius_px: int = 11
    player_outline_bgr: Tuple[int, int, int] = (0, 0, 0)
    team_white_fill_bgr: Tuple[int, int, int] = (0, 0, 255)
    team_dark_fill_bgr: Tuple[int, int, int] = (255, 255, 0)
    team_unknown_fill_bgr: Tuple[int, int, int] = (166, 184, 20)

    # Dibujar el punto del balón en el mapa 2D. Desactivado: solo se representa
    # la posesión (anillo alrededor del jugador poseedor), no el balón — su
    # proyección al suelo sufre parallax cuando está en el aire. Con `True` se
    # vuelve a dibujar el balón proyectado.
    draw_possession_ball: bool = False
    possession_ball_radius_px: int = 7
    possession_ball_bgr: Tuple[int, int, int] = (0, 140, 255)
    possessor_ring_bgr: Tuple[int, int, int] = (0, 215, 255)
    possessor_ring_thickness: int = 4

    # Resalte del resultado del tiro (verde = acierto, rojo = fallo).
    score_rim_highlight_radius_px: int = 14
    made_rim_highlight_bgr: Tuple[int, int, int] = (60, 200, 60)
    missed_rim_highlight_bgr: Tuple[int, int, int] = (60, 60, 230)
    made_label: str = "CANASTA"
    missed_label: str = "FALLO"


# ---------------------------------------------------------------------------
# Settings global
# ---------------------------------------------------------------------------
@dataclass
class Settings:
    detection: DetectionSettings = field(default_factory=DetectionSettings)
    ball_tracking: BallTrackingSettings = field(default_factory=BallTrackingSettings)
    possession: PossessionSettings = field(default_factory=PossessionSettings)
    score: ScoreSettings = field(default_factory=ScoreSettings)
    court: CourtSettings = field(default_factory=CourtSettings)
    smoothing: SmoothingSettings = field(default_factory=SmoothingSettings)
    teams: TeamSettings = field(default_factory=TeamSettings)
    identity: IdentitySettings = field(default_factory=IdentitySettings)
    sam: SAMSettings = field(default_factory=SAMSettings)
    render: RenderSettings = field(default_factory=RenderSettings)

    write_overlay_video: bool = True
    write_map_video: bool = True
    progress_every: int = 50
    # Desglose de tiempos por etapa al terminar el vídeo.
    profile: bool = True
    # Sincroniza la GPU en cada frontera de etapa (medición exacta pero más
    # lenta). Si es False, los tiempos de etapas en GPU son aproximados.
    profile_cuda_sync: bool = False
    # Limpieza de trayectorias (sports.clean_paths) en post-proceso del mapa.
    clean_paths: bool = False

    @classmethod
    def default(cls) -> "Settings":
        return cls()
