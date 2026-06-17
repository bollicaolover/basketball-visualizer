"""Adapter de KaliCalib como fuente alternativa de homografía.

KaliCalib (Maglo et al., MMSports 2022) usa un encoder-decoder ResNet-18
que genera 94 heatmaps (91 keypoints de cancha + 2 canastas + 1 fondo) a
1/4 de la resolución de entrada. A partir de los centros de masa de esos
heatmaps se corre un RANSAC+DLT para estimar la homografía.

Esta clase produce la misma interfaz que ``HomographyEstimator`` y
``PnPCameraEstimator`` (devuelve ``HomographyEstimate``) para poder
compararlos directamente en el benchmark sin tocar el resto del pipeline.

Referencias de KaliCalib:
  - Repo: https://github.com/CEA-LIST/KaliCalib
  - Pesos: third_party/KaliCalib/models/model_test.pth
  - Cancha FIBA: 2800 cm × 1500 cm (diferente a NBA 2865×1524).

Notas de integración:
  - Los 91 keypoints están en una cuadrícula 7×13 con espaciado
    perspective-aware (progresión aritmética, u0=175 cm, r=30 cm).
  - Las coordenadas mundo se expresan en pies para ser compatibles con el
    HomographyEstimate que consume el resto del pipeline.
  - El RANSAC interno usa reproj_threshold=35 px (sobre imagen 960×540);
    ajustable vía ``ransac_reproj_px``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
import torch
import torchvision.transforms as T

# Acceso al código de KaliCalib sin instalarlo como paquete.
_KALI_ROOT = Path(__file__).parents[2] / "third_party" / "KaliCalib"
if str(_KALI_ROOT) not in sys.path:
    sys.path.insert(0, str(_KALI_ROOT))

from kalicalib.model_resnet import makeModel  # noqa: E402

from pipeline.court.homography import HomographyEstimate, _reprojection_residual_px  # noqa: E402

_LOG = logging.getLogger(__name__)

# Dimensiones internas de inferencia de KaliCalib.
_INFER_W: int = 960
_INFER_H: int = 540
_HEATMAP_SCALE: int = 4   # los heatmaps son 1/4 de la imagen de inferencia

# Normalización ImageNet (idéntica a la de entrenamiento de KaliCalib).
_TRANSFORM = T.Compose([
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# cm → ft
_CM_TO_FT: float = 1.0 / 30.48


def _field_points_ft() -> np.ndarray:
    """91 keypoints de cancha FIBA en pies, shape (91, 2).

    Reproducción directa de ``getFieldPoints()`` de KaliCalib pero
    sin importar deepsport-utilities: puro numpy.
    Coordenadas X = longitud (0→91.86 ft), Y = anchura (0→49.21 ft).
    """
    FIELD_LENGTH_CM = 2800.0
    FIELD_WIDTH_CM  = 1500.0

    u0 = 175.0  # primera separación en cm
    r  = 30.0   # incremento (progresión aritmética)
    u  = u0
    s  = 0.0

    pts = []
    for _j in range(7):
        for i in range(13):
            x_cm = i * FIELD_LENGTH_CM / 12.0
            y_cm = FIELD_WIDTH_CM - s
            pts.append([x_cm * _CM_TO_FT, y_cm * _CM_TO_FT])
        s += u
        u += r

    return np.array(pts, dtype=np.float64)   # (91, 2)


# Pre-calculado una sola vez.
_WORLD_PTS_FT: np.ndarray = _field_points_ft()


class KaliCalibDetector:
    """Estima la homografía imagen→cancha usando el modelo KaliCalib.

    Interfaz de salida idéntica a ``HomographyEstimator``: método
    ``update(kp_xy, valid_mask) -> HomographyEstimate``.  Sin embargo,
    este estimador ignora los argumentos ``kp_xy``/``valid_mask`` (genera
    sus propios keypoints internamente a partir del frame) y expone un
    método ``update_from_frame(frame_bgr) -> HomographyEstimate`` que es
    el que se usa en el benchmark.
    """

    def __init__(
        self,
        checkpoint: str = "third_party/KaliCalib/models/model_challenge.pth",
        device: str = "cuda",
        ransac_reproj_px: float = 35.0,
        min_keypoints: int = 4,
        max_residual_px: float = 30.0,
    ) -> None:
        self._device = torch.device(device if torch.cuda.is_available() else "cpu")
        self._ransac_reproj = ransac_reproj_px
        self._min_kp = min_keypoints
        self._max_residual = max_residual_px

        self._model = makeModel().to(self._device)
        state = torch.load(checkpoint, map_location=self._device)
        self._model.load_state_dict(state)
        self._model.eval()

        _LOG.info(
            "KaliCalibDetector: cargado %s en %s (%.1fM params)",
            checkpoint, self._device, sum(p.numel() for p in self._model.parameters()) / 1e6,
        )

    # ------------------------------------------------------------------
    def update_from_frame(self, frame_bgr: np.ndarray) -> HomographyEstimate:
        """Estima H para un frame BGR de cualquier resolución."""
        orig_h, orig_w = frame_bgr.shape[:2]

        heatmaps = self._run_model(frame_bgr)          # (94, 135, 240)
        kp_img, kp_conf = self._extract_keypoints(heatmaps)  # (91,2), (91,)

        # Escalar coords de 960×540 a resolución original.
        kp_img[:, 0] *= orig_w / _INFER_W
        kp_img[:, 1] *= orig_h / _INFER_H

        return self._estimate_homography(kp_img, kp_conf, orig_w, orig_h)

    # ------------------------------------------------------------------
    def _run_model(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Inferencia: devuelve heatmaps numpy (94, H/4, W/4)."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (_INFER_W, _INFER_H))
        tensor = _TRANSFORM(rgb).unsqueeze(0).to(self._device)
        with torch.no_grad():
            out = self._model(tensor)
        return out[0].cpu().numpy()   # (94, 135, 240)

    def _extract_keypoints(
        self, heatmaps: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Centro de masa de los 91 heatmaps de keypoints de cancha.

        Devuelve:
          kp_img  (91, 2) – coordenadas (x, y) en espacio 960×540
          kp_conf (91,)   – valor máximo del heatmap como proxy de confianza
        """
        n_kp = 91
        kp_img  = np.zeros((n_kp, 2), dtype=np.float32)
        kp_conf = np.zeros(n_kp, dtype=np.float32)

        # Máscara: el píxel pertenece al keypoint i si su clase máxima es i.
        # (misma lógica que estimateCalibHM en KaliCalib)
        pixel_max_class = np.argmax(heatmaps, axis=0)   # (135, 240)

        for i in range(n_kp):
            mask = (pixel_max_class == i) & (heatmaps[i] > 0)
            kp_conf[i] = float(heatmaps[i].max())

            M = cv2.moments(mask.astype(np.uint8))
            if M["m00"] == 0:
                continue

            # Momentos dan (row, col); convertimos a (x, y) y escalamos ×4.
            cx = (M["m10"] / M["m00"]) * _HEATMAP_SCALE
            cy = (M["m01"] / M["m00"]) * _HEATMAP_SCALE
            kp_img[i] = [cx, cy]

        return kp_img, kp_conf

    def _estimate_homography(
        self,
        kp_img: np.ndarray,
        kp_conf: np.ndarray,
        orig_w: int,
        orig_h: int,
    ) -> HomographyEstimate:
        """RANSAC+DLT sobre los keypoints detectados → HomographyEstimate."""
        # Sólo usar keypoints con CoM encontrado (coord ≠ 0).
        valid = (kp_img[:, 0] != 0) | (kp_img[:, 1] != 0)
        n_valid = int(valid.sum())

        if n_valid < self._min_kp:
            return HomographyEstimate(
                H=None, confidence=0.0, num_inliers=0,
                residual_px=float("inf"), used_cached=False,
                reject_reason=f"kali: solo {n_valid} keypoints detectados",
            )

        src = _WORLD_PTS_FT[valid].astype(np.float32)   # (n, 2) world en ft
        dst = kp_img[valid].astype(np.float32)           # (n, 2) imagen

        # findHomography: src=mundo, dst=imagen → H_world→img
        H_w2i, inlier_mask = cv2.findHomography(
            src, dst,
            cv2.RANSAC,
            ransacReprojThreshold=self._ransac_reproj,
            maxIters=2000,
        )

        if H_w2i is None:
            return HomographyEstimate(
                H=None, confidence=0.0, num_inliers=0,
                residual_px=float("inf"), used_cached=False,
                reject_reason="kali: findHomography devolvió None",
            )

        num_inliers = int(inlier_mask.sum()) if inlier_mask is not None else n_valid

        # Invertir para obtener H imagen→mundo (pies), igual que el resto del pipeline.
        try:
            H_i2w = np.linalg.inv(H_w2i)
        except np.linalg.LinAlgError:
            return HomographyEstimate(
                H=None, confidence=0.0, num_inliers=0,
                residual_px=float("inf"), used_cached=False,
                reject_reason="kali: H singular",
            )

        if abs(H_i2w[2, 2]) < 1e-9 or not np.all(np.isfinite(H_i2w)):
            return HomographyEstimate(
                H=None, confidence=0.0, num_inliers=0,
                residual_px=float("inf"), used_cached=False,
                reject_reason="kali: H no finita",
            )

        H_i2w = H_i2w / H_i2w[2, 2]

        # Residual sobre los inliers en espacio imagen (misma métrica que HomographyEstimator).
        residual = _reprojection_residual_px(H_i2w, dst, src)

        max_kps = 91
        ratio    = min(num_inliers / max_kps, 1.0)
        res_term = max(0.0, 1.0 - residual / max(1e-6, self._max_residual))
        conf     = 0.6 * ratio + 0.4 * res_term

        return HomographyEstimate(
            H=H_i2w.astype(np.float64),
            confidence=conf,
            num_inliers=num_inliers,
            residual_px=residual,
            used_cached=False,
            reject_reason=None,
        )
