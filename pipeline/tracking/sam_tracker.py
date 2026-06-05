"""Adaptador de SAM 3 (Segment Anything 3) como :class:`ITracker`.

Usa la API oficial de Hugging Face Transformers en modo streaming:

    Sam3TrackerVideoModel.from_pretrained("facebook/sam3")
    Sam3TrackerVideoProcessor.from_pretrained("facebook/sam3")

Diseño:

* **Lazy import** de ``transformers`` y ``cv2``. Si no hay ``transformers``,
  la factoría captura ``ImportError`` y devuelve ``None`` (el orquestador
  decide si abortar o caer a classic).
* **YOLO como prompter** — únicamente en el frame 0 y, a futuro, como
  re‑prompt tras pérdidas. SAM mantiene la identidad temporal entre frames
  vía su memory bank.
* **Streaming nativo** — ``init_video_session()`` sin ``video=`` y, por cada
  frame, ``model(inference_session=..., frame=pixel_values[0])``. Encaja con
  el bucle frame‑a‑frame de ``Pipeline.process_video`` sin precargar el clip.
* **Tensor masks en GPU** — las máscaras llegan ya en el device de SAM y se
  pasan tal cual a :class:`TrackedEntity.mask` para que ``MaskCropper`` y
  ``MaskFootPoint`` operen sin D2H intermedios.

Referencia: https://huggingface.co/facebook/sam3/blob/main/README.md
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Protocol

import numpy as np
import torch

from pipeline.config import PLAYER_CLASS, PLAYER_CLASSES, SAMSettings
from pipeline.tracking.tracker import ITracker
from pipeline.tracking.types import TrackedEntity

_LOG = logging.getLogger(__name__)


class _YoloPrompter(Protocol):
    """Subset duck‑typed de ``YOLODetector`` necesario para promptear SAM."""

    def detect(self, frame_bgr: np.ndarray) -> Any: ...  # devuelve sv.Detections


_DTYPE_MAP = {
    "float32": torch.float32,
    "float16": torch.float16,
    "bfloat16": torch.bfloat16,
}


def _import_sam3():
    """Lazy import de transformers + cv2. Aísla aquí los nombres del paquete."""
    try:
        from transformers import Sam3TrackerVideoModel, Sam3TrackerVideoProcessor
    except ImportError as exc:
        raise ImportError(
            "SAMTracker requiere `transformers` con soporte SAM 3. "
            "Instala con `pip install -U transformers` (≥ 5.x). "
            f"Detalle: {exc}"
        ) from exc
    try:
        import cv2  # type: ignore  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "SAMTracker necesita OpenCV (cv2) para BGR→RGB. "
            f"Detalle: {exc}"
        ) from exc
    return Sam3TrackerVideoModel, Sam3TrackerVideoProcessor


class SAMTracker(ITracker):
    """Tracker SAM 3 (HF transformers) con prompts iniciales de YOLO."""

    def __init__(self, sam_settings: SAMSettings, yolo_prompter: _YoloPrompter) -> None:
        self._settings = sam_settings
        self._yolo = yolo_prompter

        VideoModel, VideoProcessor = _import_sam3()
        dtype = _DTYPE_MAP.get(sam_settings.dtype, torch.bfloat16)
        self._dtype = dtype
        self._device = sam_settings.device

        self._model = VideoModel.from_pretrained(sam_settings.model_id).to(
            self._device, dtype=dtype,
        )
        self._model.eval()
        self._processor = VideoProcessor.from_pretrained(sam_settings.model_id)

        self._session: Optional[Any] = None
        self._sam_to_track: dict[int, int] = {}
        self._next_sam_obj_id: int = 1
        self._initialized: bool = False
        self._original_size: Optional[Any] = None

    # ------------------------------------------------------------------
    # ITracker hooks
    # ------------------------------------------------------------------
    def prepare_video(self, video_path: str) -> None:
        """Reinicia la sesión de inferencia para un vídeo nuevo.

        SAM 3 en modo streaming **no necesita** la ruta del vídeo (los frames
        se inyectan uno a uno con ``model(frame=...)``). El argumento se
        ignora; queda por compatibilidad con el hook del :class:`ITracker`.
        """
        del video_path  # streaming: no se usa
        self._session = self._processor.init_video_session(
            inference_device=self._device,
            dtype=self._dtype,
        )
        self._sam_to_track.clear()
        self._next_sam_obj_id = 1
        self._initialized = False
        self._original_size = None

    def update(self, frame_bgr: np.ndarray, frame_idx: int) -> List[TrackedEntity]:
        if self._session is None:
            raise RuntimeError(
                "SAMTracker.update() llamado antes de prepare_video(). "
                "El orquestador debe llamar prepare_video() una vez al "
                "abrir el vídeo."
            )

        # BGR (cv2) → RGB (transformers).
        import cv2

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        inputs = self._processor(
            images=frame_rgb, device=self._device, return_tensors="pt",
        )
        if self._original_size is None:
            self._original_size = inputs.original_sizes[0]

        if not self._initialized:
            self._prompt_with_yolo(frame_bgr, frame_idx)
            # Sólo "inicializado" cuando hay al menos un prompt; si YOLO no
            # detectó nada en este frame, reintentaremos en el siguiente.
            self._initialized = bool(self._sam_to_track)

        if not self._sam_to_track:
            # SAM 3 falla con "No objects are provided for tracking" si se
            # invoca sin objetos; nos saltamos el forward hasta que YOLO
            # consiga un prompt.
            return []

        with torch.inference_mode():
            sam_output = self._model(
                inference_session=self._session,
                frame=inputs.pixel_values[0],
            )

        return self._entities_from_output(sam_output)

    def reset(self) -> None:
        self._session = None
        self._sam_to_track.clear()
        self._next_sam_obj_id = 1
        self._initialized = False
        self._original_size = None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _prompt_with_yolo(self, frame_bgr: np.ndarray, frame_idx: int) -> None:
        """Detecta jugadores con YOLO y los inyecta como box prompts en SAM."""
        dets = self._yolo.detect(frame_bgr)
        if dets is None or len(dets) == 0:
            return
        keep = np.isin(dets.class_id, list(PLAYER_CLASSES))
        if not keep.any():
            return
        players = dets[keep]
        max_n = min(len(players), self._settings.max_objects)
        if max_n == 0:
            return

        # IMPORTANTE: todos los objetos se añaden en UNA sola llamada. El
        # ``clear_old_inputs=True`` (default) limpia los inputs pendientes de
        # los demás objetos, así que prompts separados por objeto dejarían a
        # todos menos el último sin marcar como "conditioning frame" y SAM
        # fallaría con "maskmem_features ... cannot be empty". El processor
        # espera ``obj_ids`` como lista e ``input_boxes`` con shape (1, n, 4).
        obj_ids = []
        boxes = []
        for i in range(max_n):
            sam_obj_id = self._next_sam_obj_id
            self._next_sam_obj_id += 1
            obj_ids.append(sam_obj_id)
            boxes.append([float(v) for v in players.xyxy[i]])
            self._sam_to_track[sam_obj_id] = sam_obj_id

        self._processor.add_inputs_to_inference_session(
            inference_session=self._session,
            frame_idx=frame_idx,
            obj_ids=obj_ids,
            input_boxes=[boxes],            # (1, n_objs, 4)
            original_size=self._original_size,
        )

    def _entities_from_output(self, sam_output: Any) -> List[TrackedEntity]:
        pred_masks = getattr(sam_output, "pred_masks", None)
        if pred_masks is None:
            return []

        # post_process_masks devuelve una lista (batch=1) de tensores con la
        # resolución original. ``binarize=False`` da logits → umbral con
        # mask_logits_threshold para preservar control numérico. Los tamaños
        # se leen del session como ints (F.interpolate no acepta tensores).
        h_orig = int(self._session.video_height)
        w_orig = int(self._session.video_width)
        masks_list = self._processor.post_process_masks(
            [pred_masks],
            original_sizes=[[h_orig, w_orig]],
            binarize=False,
        )
        if not masks_list:
            return []
        masks = masks_list[0]                    # tensor en device
        # Forma esperada: (N_obj, 1, H, W) o (N_obj, H, W). Aplastamos canal.
        if masks.ndim == 4:
            masks = masks.squeeze(1)
        masks_bool = masks > self._settings.mask_logits_threshold

        obj_ids = getattr(sam_output, "obj_ids", None)
        if obj_ids is None:
            # Fallback: asume orden por inserción.
            obj_ids = list(self._sam_to_track.keys())[: masks_bool.shape[0]]

        out: List[TrackedEntity] = []
        for i, sam_obj_id in enumerate(obj_ids):
            if i >= masks_bool.shape[0]:
                break
            m = masks_bool[i]
            if not bool(m.any()):
                continue
            ys, xs = torch.where(m)
            bbox = np.array(
                [
                    float(xs.min().item()),
                    float(ys.min().item()),
                    float(xs.max().item()),
                    float(ys.max().item()),
                ],
                dtype=np.float32,
            )
            track_id = self._sam_to_track.get(int(sam_obj_id), int(sam_obj_id))
            out.append(
                TrackedEntity(
                    track_id=track_id,
                    class_id=PLAYER_CLASS,
                    confidence=1.0,
                    bbox_xyxy=bbox,
                    mask=m,
                )
            )
        return out
