"""OCR de dorsal: empareja la caja `number` de RF-DETR con la máscara SAM del
jugador (IoS, como el cuaderno) y lee el número con un VLM **SmolVLM2 local**
entrenado por el usuario (`scripts/train_jersey_ocr.py`).

Flujo por frame (cada `ocr_every` frames):
  1. máscaras de jugador (SAM) + máscaras de las cajas `number` → IoS.
  2. para cada número que cae dentro de un jugador (IoS ≥ umbral): recorta,
     pad + resize 224, y lo lee el SmolVLM2 con el prompt "Read the number.".
  3. vota la lectura por `track_id` (`ConsecutiveValueTracker`); el número se
     fija tras N lecturas coincidentes.

Degradación elegante: si no existe el checkpoint del SmolVLM2, `available()`
es False y el orquestador omite los números (a menos que `fallback_parseq`).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import supervision as sv

from pipeline.config import IdentitySettings
from pipeline.tracking.types import TrackedEntity

_DIGITS = re.compile(r"\d{1,2}")


class JerseyNumberOCR:
    def __init__(self, settings: IdentitySettings) -> None:
        self._s = settings
        self._model = None
        self._processor = None
        self._available = False

        from sports import ConsecutiveValueTracker

        self._votes = ConsecutiveValueTracker(n_consecutive=settings.votes_to_lock)
        self._locked: Dict[int, int] = {}

        if settings.enabled:
            self._try_load_smolvlm()

    # ------------------------------------------------------------------
    def _try_load_smolvlm(self) -> None:
        model_dir = Path(self._s.ocr_model_dir)
        if not model_dir.exists():
            print(
                f"[INFO] OCR dorsal: no hay SmolVLM2 en {model_dir}; números "
                "desactivados. Entrena con scripts/train_jersey_ocr.py."
            )
            return
        try:
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor

            self._processor = AutoProcessor.from_pretrained(str(model_dir))
            self._model = AutoModelForImageTextToText.from_pretrained(
                str(model_dir), torch_dtype=torch.bfloat16,
            ).to(self._s.device)
            self._model.eval()
            self._available = True
            print(f"[INFO] OCR dorsal: SmolVLM2 cargado <- {model_dir}")
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] OCR dorsal: no se pudo cargar SmolVLM2 ({exc}).")
            self._available = False

    def available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    def update(
        self,
        frame_bgr: np.ndarray,
        number_detections: Optional[sv.Detections],
        entities: List[TrackedEntity],
    ) -> None:
        """Lee y vota los dorsales de este frame (si hay números y jugadores)."""
        if not self._available or not entities:
            return
        if number_detections is None or len(number_detections) == 0:
            return

        h, w = frame_bgr.shape[:2]
        player_masks = self._entity_masks(entities, h, w)
        if player_masks is None:
            return
        number_masks = sv.xyxy_to_mask(
            boxes=number_detections.xyxy, resolution_wh=(w, h),
        )

        ios = sv.mask_iou_batch(
            masks_true=player_masks,
            masks_detection=number_masks,
            overlap_metric=sv.OverlapMetric.IOS,
        )  # (n_players, n_numbers)

        tids: List[int] = []
        values: List[Optional[str]] = []
        for num_idx in range(ios.shape[1]):
            col = ios[:, num_idx]
            player_idx = int(np.argmax(col))
            if col[player_idx] < self._s.number_match_ios:
                continue
            crop = self._crop_number(frame_bgr, number_detections.xyxy[num_idx], w, h)
            if crop is None:
                continue
            number = self._read(crop)
            if number is None:
                continue
            tids.append(int(entities[player_idx].track_id))
            values.append(str(number))

        if tids:
            self._votes.update(tracker_ids=tids, values=values)
            for tid in tids:
                v = self._votes.get_validated(tid)
                if v is not None:
                    self._locked[tid] = int(v)

    # ------------------------------------------------------------------
    def locked_numbers(self) -> Dict[int, int]:
        return dict(self._locked)

    # ------------------------------------------------------------------
    @staticmethod
    def _entity_masks(
        entities: List[TrackedEntity], h: int, w: int,
    ) -> Optional[np.ndarray]:
        masks = []
        for e in entities:
            if e.mask is None:
                return None
            m = e.mask
            try:
                import torch

                if isinstance(m, torch.Tensor):
                    m = m.detach().cpu().numpy()
            except ImportError:
                pass
            m = np.asarray(m).astype(bool)
            if m.shape != (h, w):
                return None
            masks.append(m)
        if not masks:
            return None
        return np.stack(masks, axis=0)

    def _crop_number(
        self, frame_bgr: np.ndarray, box_xyxy: np.ndarray, w: int, h: int,
    ) -> Optional[np.ndarray]:
        padded = sv.pad_boxes(
            xyxy=np.asarray([box_xyxy], dtype=np.float32),
            px=self._s.crop_pad_px, py=self._s.crop_pad_px,
        )
        clipped = sv.clip_boxes(padded, (w, h))[0]
        crop = sv.crop_image(frame_bgr, clipped)
        if crop.size == 0:
            return None
        res = self._s.crop_resolution
        return sv.resize_image(crop, resolution_wh=(res, res))

    # ------------------------------------------------------------------
    def _read(self, crop_bgr: np.ndarray) -> Optional[int]:
        """Lee el número con el SmolVLM2 local. Devuelve int 0-99 o None."""
        import cv2
        import torch
        from PIL import Image

        image = Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB))
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": self._s.ocr_prompt},
                ],
            }
        ]
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Kwargs passed to")
            inputs = self._processor.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            ).to(self._s.device)
        with torch.inference_mode():
            generated = self._model.generate(**inputs, max_new_tokens=8, do_sample=False)
        text = self._processor.batch_decode(
            generated[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True,
        )[0]
        m = _DIGITS.search(text)
        if not m:
            return None
        value = int(m.group())
        return value if 0 <= value <= 99 else None
