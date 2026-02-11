"""Subpaquete de cancha: geometría, keypoints, homografía y render 2D.

La geometría definida en `pipeline.court.geometry` reproduce la convención
de 33 keypoints del dataset `basketball-court-detection-2` (Roboflow) sin
depender de paquetes externos.

Módulos principales:
    geometry          — coordenadas NBA en pies, edges, índices semánticos
    keypoint_detector — wrapper YOLO-Pose para detectar los 33 keypoints
    stabilizer        — EMA + rechazo de saltos por punto
    segments          — detección de panes/cortes de cámara
    homography        — RANSAC + pooling multi-frame + holdover
    smoothing         — EMA de posiciones proyectadas al plano de la cancha
    renderer          — mapa táctico cenital 2D
"""

