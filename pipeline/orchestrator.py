"""Orquestador del pipeline `tfg-junio`.

Combina el flujo de detección/identidad del cuaderno (RF-DETR local → SAM →
equipos SigLIP → OCR dorsal) con la proyección al plano 2D y el tracking de
balón portados del proyecto original. Expone `process_video(input, output)`.

Etapas por frame:
  1. Detección RF-DETR (11 clases) → reparto por class-id.
  2. Cancha: keypoints → estabilización → homografía.
  3. Tracking SAM (prompt-once con RF-DETR) → entidades con máscara + track_id.
  4. Equipos (SigLIP, voto por track).
  5. Dorsal (SmolVLM2 local, IoS número→máscara, voto por track) + nombre roster.
  6. Balón (BallTracker).
  7. Proyección 2D (punto de apoyo por máscara → H → suavizado).
  8. Render: vídeo anotado + mapa cenital.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import cv2
import numpy as np
import supervision as sv

from pipeline.config import (
    BALL_CLASSES,
    BALL_IN_BASKET_CLASS,
    CLASS_NAMES,
    IN_POSSESSION_CLASS,
    NUMBER_CLASS,
    PLAYER_CLASSES,
    REFEREE_CLASS,
    RIM_CLASS,
    SHOT_ACTION_CLASSES,
    Settings,
)
from pipeline.context import FrameContext
from pipeline.court.geometry import COURT
from pipeline.court.camera_model import PnPCameraEstimator
from pipeline.court.homography import HomographyEstimator, project_image_points
from pipeline.court.keypoint_detector import CourtKeypointDetector
from pipeline.court.renderer import CourtRenderer, PlayerDot
from pipeline.court.smoothing import WorldTrackSmoother
from pipeline.court.stabilizer import KeypointStabilizer
from pipeline.detection.rfdetr_detector import RFDETRDetector
from pipeline.identity.number_ocr import JerseyNumberOCR
import pipeline.identity.roster as roster_mod
from pipeline.identity.roster import player_name
from pipeline.io.video import open_video_writer
from pipeline.strategy import build_ball_tracker, build_foot_point, build_sam_tracker
from pipeline.teams.team_classifier import TeamClassifier
from pipeline.possession.resolver import PossessionResolver
from pipeline.profiling import StageTimer
from pipeline.scoring.shot_tracker import ShotTracker
from pipeline.scoring.release_detector import ReleaseDetector
from pipeline.pose.pose_estimator import PoseEstimator
from pipeline.metadata_writer import MetadataWriter
from pipeline.tracking.dedup import deduplicate_player_detections
from pipeline.tracking.player_tracker import PlayerTracker
from pipeline.tracking.tracker import tracked_entities_from_detections
from pipeline.tracking.types import TrackedEntity


@dataclass
class VideoIO:
    cap: cv2.VideoCapture
    fps: float
    width: int
    height: int
    total_frames: int


def _map_output_path(output_path: str) -> str:
    import os

    root, ext = os.path.splitext(output_path)
    return f"{root}_map{ext or '.mp4'}"


def _metadata_output_path(output_path: str) -> str:
    import os

    root, _ = os.path.splitext(output_path)
    return f"{root}_metadata.json"


class Pipeline:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings.default()
        mode = self.settings.tracker_mode
        if mode not in ("sam", "botsort"):
            raise ValueError(f"tracker_mode inválido: {mode!r} (usa 'sam' o 'botsort')")

        self.detector = RFDETRDetector(self.settings.detection)
        self._sam_tracker = build_sam_tracker(self.settings, yolo_prompter=self.detector)
        if mode == "sam" and self._sam_tracker is None:
            raise RuntimeError(
                "tracker_mode='sam' pero SAM 3 no se pudo cargar. "
                "Usa --tracker botsort o revisa models/sam3."
            )
        self.player_tracker = (
            PlayerTracker(self.settings.player_tracking)
            if mode == "botsort"
            else None
        )
        print(f"[INFO] tracking: {mode}", flush=True)
        self.ball_tracker = build_ball_tracker(self.settings)
        print(f"[INFO] ball tracker: {self.settings.ball_tracking.method}", flush=True)
        self.possession = PossessionResolver(self.settings.possession)
        self.shot_tracker = ShotTracker(self.settings.score)
        # Detección de suelta por pose (opt-in): pose del poseedor + separación
        # mano→balón hacia arriba. Refuerza el trigger del tiro y siembra la 3D.
        self.pose_estimator = PoseEstimator(self.settings.pose)
        self.release_detector = ReleaseDetector(self.settings.release)
        if self.settings.pose.enabled:
            print("[INFO] pose/release: activado", flush=True)

        self.court_kp = CourtKeypointDetector(self.settings.court)
        self.kp_stabilizer = KeypointStabilizer(self.settings.court)
        # Estimador de homografía: PnP paramétrico (flag) o RANSAC clásico (default).
        self.homography = (
            PnPCameraEstimator(self.settings.court)
            if self.settings.court.use_pnp
            else HomographyEstimator(self.settings.court)
        )

        self.teams = TeamClassifier(self.settings.teams)
        self.identity = (
            JerseyNumberOCR(self.settings.identity)
            if self.settings.identity.enabled else None
        )

        self.foot_point = build_foot_point(self.settings)
        self.player_smoother = WorldTrackSmoother(self.settings.smoothing)

        rp = self.settings.identity.roster_path
        if rp:
            from pathlib import Path
            if Path(rp).exists():
                roster_mod.load(rp)
        self.renderer = CourtRenderer(self.settings.render)
        self._label_annotator = sv.LabelAnnotator()
        self.timer = StageTimer(cuda_sync=self.settings.profile_cuda_sync)

    # ------------------------------------------------------------------
    def process_video(self, input_path: str, output_path: str) -> None:
        print("[STAGE] calibrate teams", flush=True)
        with self.timer.stage("calibración"):
            self._calibrate_teams(input_path)
            self._orient_names_by_roster_color()

        print("[STAGE] decode", flush=True)
        io = self._open_video(input_path)
        map_path = _map_output_path(output_path)
        out_main = (
            open_video_writer(output_path, io.fps, io.width, io.height)
            if self.settings.write_overlay_video else None
        )
        out_map = (
            open_video_writer(map_path, io.fps, *self.renderer.canvas_size)
            if self.settings.write_map_video else None
        )
        metadata_writer = (
            MetadataWriter(
                _metadata_output_path(output_path), io.fps,
                team_names=self.settings.metadata_team_names,
            )
            if self.settings.write_metadata else None
        )

        # SAM necesita el vídeo entero; BoT-SORT es streaming frame a frame.
        if self._sam_tracker is not None:
            self._sam_tracker.prepare_video(input_path)
        self.possession.reset()
        self.shot_tracker.reset()
        self.release_detector.reset()
        # PnP necesita el centro de imagen (punto principal) para construir K.
        if isinstance(self.homography, PnPCameraEstimator):
            self.homography.set_image_size(io.width, io.height)

        print("[STAGE] ai", flush=True)
        try:
            frame_index = 0
            while True:
                with self.timer.stage("decodificación"):
                    ok, frame = io.cap.read()
                if not ok:
                    break
                ctx = FrameContext(
                    frame_index=frame_index,
                    frame_bgr=frame,
                    frame_height=io.height,
                    frame_width=io.width,
                )
                self._process_frame(ctx)
                with self.timer.stage("escritura"):
                    if out_main is not None and ctx.overlay_frame is not None:
                        out_main.write(ctx.overlay_frame)
                    if out_map is not None and ctx.map_frame is not None:
                        out_map.write(ctx.map_frame)
                    if metadata_writer is not None:
                        metadata_writer.write(ctx)
                frame_index += 1
                if frame_index % self.settings.progress_every == 0:
                    print(f"  {frame_index}/{io.total_frames} frames", flush=True)
        finally:
            io.cap.release()
            if out_main is not None:
                out_main.release()
            if out_map is not None:
                out_map.release()
            if metadata_writer is not None:
                print("[STAGE] metadata", flush=True)
                metadata_writer.close()

        print(f"[INFO] Vídeo anotado: {output_path}", flush=True)
        if self.settings.write_map_video:
            print(f"[INFO] Mapa 2D:       {map_path}", flush=True)
        self._print_identity_summary()
        self._print_possession_summary()
        self._print_score_summary()
        self._print_timing_summary(frame_index)

        if self.settings.shot3d.enabled and self.settings.write_metadata:
            self._run_shot3d(input_path, output_path)

        if self.settings.tactics.enabled and self.settings.write_metadata:
            self._run_tactics(output_path)

    def _run_tactics(self, output_path: str) -> None:
        """Reconoce pantallas (Chen et al. 2012) sobre el metadata ya escrito."""
        from pathlib import Path

        from pipeline.tactics.run import run_tactics, tactics_output_path

        meta_path = Path(_metadata_output_path(output_path))
        if not meta_path.is_file():
            print("[WARN] tácticas omitidas: no hay metadata", flush=True)
            return
        json_out = tactics_output_path(meta_path) if self.settings.tactics.write_json else None
        print("[STAGE] tactics", flush=True)
        with self.timer.stage("tactics"):
            doc = run_tactics(meta_path, json_out=json_out, settings=self.settings.tactics)
        counts = doc.get("screen_counts", {})
        total = sum(counts.values())
        detail = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "ninguna"
        print(f"[RESUMEN] pantallas: {total} ({detail})", flush=True)

    def _run_shot3d(self, input_path: str, output_path: str) -> None:
        from pathlib import Path

        from pipeline.shot3d.reconstruct import Shot3DError, run_shot3d, shot3d_output_paths

        video_out, json_out = shot3d_output_paths(output_path)
        if not self.settings.shot3d.write_video:
            video_out = None
        if not self.settings.shot3d.write_json:
            json_out = None
        meta_path = Path(_metadata_output_path(output_path))
        print("[STAGE] shot3d", flush=True)
        with self.timer.stage("shot3d"):
            try:
                run_shot3d(
                    input_video=Path(input_path),
                    metadata_path=meta_path,
                    video_out=video_out,
                    json_out=json_out,
                    min_segment=self.settings.shot3d.min_segment,
                    pose_release=self.settings.shot3d.pose_release,
                    extend_to_release=self.settings.shot3d.extend_to_release,
                    device=self.settings.detection.device,
                )
            except Shot3DError as exc:
                print(f"[WARN] reconstrucción 3D omitida: {exc}", flush=True)

    def _print_possession_summary(self) -> None:
        """Reparto de posesión: frames por equipo (y por track) en el vídeo."""
        frames = self.possession.possession_frames()
        total = sum(frames.values())
        if total == 0:
            print("[RESUMEN] posesión: sin frames con poseedor asignado", flush=True)
            return
        by_team: Dict[str, int] = {}
        for tid, n in frames.items():
            team = self.teams.team_name(tid) or "desconocido"
            by_team[team] = by_team.get(team, 0) + n
        print(f"[RESUMEN] posesión ({total} frames con poseedor):", flush=True)
        for team, n in sorted(by_team.items(), key=lambda kv: -kv[1]):
            print(f"  {team}: {100.0 * n / total:.1f}%  ({n} frames)", flush=True)

    def _print_timing_summary(self, frames: int) -> None:
        """Desglose de tiempos por etapa: total, % y ms/frame."""
        if not self.settings.profile:
            return
        totals = self.timer.totals()
        grand = self.timer.total
        if grand <= 0 or frames <= 0:
            return
        sync_note = "" if self.settings.profile_cuda_sync else "  (GPU aprox.)"
        print(f"[RESUMEN] tiempos por etapa{sync_note}:", flush=True)
        for name, dt in sorted(totals, key=lambda kv: -kv[1]):
            pct = 100.0 * dt / grand
            ms = 1000.0 * dt / frames
            print(f"  {name:<20} {dt:8.1f}s  {pct:5.1f}%  {ms:7.1f} ms/frame",
                  flush=True)
        fps = frames / grand
        print(f"  {'TOTAL':<20} {grand:8.1f}s  100.0%  "
              f"{1000.0 * grand / frames:7.1f} ms/frame  ({fps:.1f} fps, "
              f"{frames} frames)", flush=True)

    def _print_score_summary(self) -> None:
        """Resumen de tiros: intentos, aciertos, % y reparto por equipo/lado."""
        if not self.settings.score.enabled:
            return
        st = self.shot_tracker
        att = st.attempts
        pct = (100.0 * st.makes / att) if att else 0.0
        print(f"[RESUMEN] tiros: {st.makes}/{att} aciertos ({pct:.0f}%), "
              f"{st.misses} fallos", flush=True)
        if att == 0:
            return
        names = self.settings.teams.team_names
        label_by_color = {
            "white": names[0] if len(names) > 0 else "Equipo 0",
            "dark": names[1] if len(names) > 1 else "Equipo 1",
            "desconocido": "desconocido",
        }
        for color, c in sorted(st.counts_by_team().items(),
                               key=lambda kv: -(kv[1]["made"] + kv[1]["missed"])):
            a = c["made"] + c["missed"]
            p = (100.0 * c["made"] / a) if a else 0.0
            print(f"  {label_by_color.get(color, color)}: "
                  f"{c['made']}/{a} ({p:.0f}%)", flush=True)
        sides = st.counts_by_side()
        for side, name in (("left", "izquierda"), ("right", "derecha")):
            c = sides[side]
            a = c["made"] + c["missed"]
            if a:
                print(f"  aro {name}: {c['made']}/{a}", flush=True)

    def _print_identity_summary(self) -> None:
        """Resumen de los dorsales fijados (track -> #num, equipo, nombre)."""
        if self.identity is None:
            return
        nums = self.identity.locked_numbers()
        print(f"[RESUMEN] dorsales fijados: {len(nums)}", flush=True)
        for tid, num in sorted(nums.items()):
            tname = self.teams.team_name(tid)
            name = player_name(tname, num)
            print(f"  track {tid}: #{num}  {tname}  -> {name}", flush=True)

    # ------------------------------------------------------------------
    def _calibrate_teams(self, input_path: str) -> None:
        """Muestrea frames, detecta jugadores y ajusta el TeamClassifier."""
        ts = self.settings.teams
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"No se pudo abrir el vídeo: {input_path}")
        crops: List[np.ndarray] = []
        idx = 0
        sampled = 0
        while sampled < ts.calibration_max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % ts.calibration_stride == 0:
                raw = self.detector.detect(frame)
                players = self._subset(raw, PLAYER_CLASSES)
                ents = self._entities_from_boxes(players)
                crops.extend(self.teams.collect_crops(frame, ents))
                sampled += 1
            idx += 1
        cap.release()
        print(f"  recortes de calibración: {len(crops)}", flush=True)
        self.teams.fit(crops)

    # ------------------------------------------------------------------
    def _orient_names_by_roster_color(self) -> None:
        """Asigna cada nombre de equipo al cluster correcto comparando el color
        del roster con el color medio de camiseta detectado. Resuelve qué nombre
        es el del equipo claro/oscuro de forma determinista (no posicional)."""
        names = list(self.settings.teams.team_names)
        if len(names) < 2:
            return
        colors = {n: roster_mod.team_color(n) for n in names[:2]}
        if not all(colors.values()):
            return  # roster sin colores → se respeta el orden recibido
        c_white = self.teams.semantic_mean_color(0)  # cluster claro (BGR)
        c_dark = self.teams.semantic_mean_color(1)   # cluster oscuro (BGR)
        if c_white is None or c_dark is None:
            return

        def _hex_bgr(h: str):
            h = h.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return np.array([b, g, r], dtype=float)

        def _dist(hex_str, bgr):
            return float(np.sum((_hex_bgr(hex_str) - bgr) ** 2))

        a, b = names[0], names[1]
        direct = _dist(colors[a], c_white) + _dist(colors[b], c_dark)
        swapped = _dist(colors[b], c_white) + _dist(colors[a], c_dark)
        ordered = (a, b) if direct <= swapped else (b, a)
        if tuple(names[:2]) != ordered:
            print(f"[INFO] equipos reorientados por color de roster: "
                  f"claro={ordered[0]}, oscuro={ordered[1]}", flush=True)
        self.settings.teams.team_names = ordered
        if self.settings.metadata_team_names is not None:
            self.settings.metadata_team_names = ordered

    # ------------------------------------------------------------------
    def _process_frame(self, ctx: FrameContext) -> None:
        with self.timer.stage("detección"):
            raw = self.detector.detect(ctx.frame_bgr)
            ctx.player_detections = self._subset(raw, PLAYER_CLASSES)
            ctx.number_detections = self._subset(raw, {NUMBER_CLASS})
            ctx.hoop_detections = self._subset(raw, {RIM_CLASS})
            ctx.referee_detections = self._subset(raw, {REFEREE_CLASS})

        # 2. Cancha + homografía
        with self.timer.stage("cancha"):
            kp = self.court_kp.predict(ctx.frame_bgr)
            stab = self.kp_stabilizer.update(kp.xy, kp.confidence)
            ctx.court_keypoints = stab.xy
            ctx.court_keypoint_valid_mask = stab.valid_mask
            est = self.homography.update(stab.xy, stab.valid_mask)
            ctx.homography = est.H
            ctx.homography_confidence = est.confidence

        # 3. Tracking de jugadores (SAM 3 o BoT-SORT)
        with self.timer.stage("tracking"):
            if self._sam_tracker is not None:
                ctx.tracked_entities = self._sam_tracker.update(
                    ctx.frame_bgr, ctx.frame_index,
                )
            else:
                pt = self.settings.player_tracking
                tracked = self.player_tracker.update(ctx.player_detections, ctx.frame_bgr)
                tracked = deduplicate_player_detections(
                    tracked,
                    min_iou=pt.dedup_min_iou,
                    enabled=pt.dedup_enabled,
                )
                ctx.tracked_entities = tracked_entities_from_detections(tracked)

        # 4. Equipos (voto por track)
        with self.timer.stage("equipos"):
            self.teams.update(ctx.frame_bgr, ctx.tracked_entities)

        # 5. Dorsal + nombre
        if (
            self.identity is not None
            and self.identity.available()
            and ctx.frame_index % max(1, self.settings.identity.ocr_every) == 0
        ):
            with self.timer.stage("dorsal"):
                self.identity.update(ctx.frame_bgr, ctx.number_detections, ctx.tracked_entities)

        with self.timer.stage("balón/posesión/tiro"):
            # 6. Balón
            ctx.ball_detections = self.ball_tracker.update(raw)

            # 6.5. Posesión: qué track tiene el balón (clase-5 + proximidad en imagen).
            in_possession = self._subset(raw, {IN_POSSESSION_CLASS})
            in_possession = self._filter_confidence(
                in_possession, self.settings.possession.class5_score_threshold,
            )
            # Velocidad y flag de extrapolación del balón (P1): el tracker los
            # expone; con backends sin esta interfaz se degrada a (None, False).
            ball_velocity = getattr(self.ball_tracker, "last_velocity", lambda: None)()
            ball_predicted = getattr(self.ball_tracker, "last_predicted", lambda: False)()
            ctx.possessor_track_id = self.possession.update(
                ctx.ball_detections, ctx.tracked_entities, in_possession,
                hoop_detections=ctx.hoop_detections,
                ball_velocity=ball_velocity, ball_predicted=ball_predicted,
            )

            # 6.55. Suelta por pose (opt-in): muñecas del poseedor + balón.
            release_now = self._detect_release(ctx)

            # 6.6. Tiro: acierto/fallo a partir de balón + aro + `ball-in-basket`.
            # El equipo se lee del clasificador (ctx.team_by_track aún no está poblado).
            ball_in_basket = self._subset(raw, {BALL_IN_BASKET_CLASS})
            shot_actions = self._subset(raw, SHOT_ACTION_CLASSES)
            possessor_team = (
                self.teams.color_name(ctx.possessor_track_id)
                if ctx.possessor_track_id is not None else None
            )
            shot = self.shot_tracker.update(
                ctx.ball_detections,
                ctx.hoop_detections,
                ball_in_basket,
                ctx.homography,
                ctx.frame_index,
                possessor_team,
                ctx.frame_width,
                shot_actions,
                release_now=release_now,
            )
            if shot is not None:
                ctx.shot_side = shot.side
                ctx.shot_made = shot.made
            else:
                ctx.shot_side = None
                ctx.shot_made = None

        # Identidad consolidada por track
        numbers = self.identity.locked_numbers() if self.identity is not None else {}
        for e in ctx.tracked_entities:
            tid = e.track_id
            color = self.teams.color_name(tid)
            if color is not None:
                ctx.team_by_track[tid] = color
            num = numbers.get(tid)
            if num is not None:
                ctx.player_numbers[tid] = num
                name = player_name(self.teams.team_name(tid), num)
                if name is not None:
                    ctx.player_names[tid] = name

        # 7. Proyección al plano 2D
        with self.timer.stage("proyección"):
            self._project_world(ctx)

        # 8. Render
        with self.timer.stage("render"):
            if self.settings.write_overlay_video:
                ctx.overlay_frame = self._draw_overlay(ctx)
            if self.settings.write_map_video:
                ctx.map_frame = self._draw_map(ctx)

    # ------------------------------------------------------------------
    def _project_world(self, ctx: FrameContext) -> None:
        ctx.players_world = []
        ctx.possessor_world = None
        if ctx.homography is None:
            ctx.players_world = self.player_smoother.update(ctx.frame_index, observations={})
            return

        H = ctx.homography
        observations: Dict[int, dict] = {}
        if ctx.tracked_entities:
            feet = np.stack([self.foot_point.estimate(e) for e in ctx.tracked_entities])
            world = project_image_points(H, feet)
            margin = self.settings.smoothing.in_bounds_margin_ft
            for e, xy in zip(ctx.tracked_entities, world):
                xy_t = (float(xy[0]), float(xy[1]))
                if not self._inside_court(xy_t, margin):
                    continue
                observations[e.track_id] = {
                    "xy_ft": xy_t,
                    "team": ctx.team_by_track.get(e.track_id),
                }
        ctx.players_world = self.player_smoother.update(ctx.frame_index, observations)

        # Balón en el mapa: solo se proyecta si el render lo pide. Por defecto no
        # se representa el balón (su proyección al suelo sufre parallax cuando
        # está en el aire); el mapa muestra únicamente la posesión vía el anillo
        # del jugador poseedor.
        if (
            self.settings.render.draw_possession_ball
            and ctx.ball_detections is not None
            and len(ctx.ball_detections) > 0
        ):
            b = ctx.ball_detections.xyxy[0]
            center = np.array([[(b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0]], dtype=np.float32)
            bw = project_image_points(H, center)[0]
            bw_t = (float(bw[0]), float(bw[1]))
            if self._inside_court(bw_t, self.settings.smoothing.in_bounds_margin_ft):
                ctx.possessor_world = np.array(bw_t, dtype=np.float32)

    # ------------------------------------------------------------------
    def _draw_overlay(self, ctx: FrameContext) -> np.ndarray:
        frame = ctx.frame_bgr.copy()
        # Jugadores trackeados (cajas por equipo + etiqueta).
        for e in ctx.tracked_entities:
            tid = e.track_id
            box = e.bbox_xyxy.astype(int)
            color = self._team_bgr(ctx.team_by_track.get(tid))
            cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), color, 2)
            if tid == ctx.possessor_track_id:
                ring = self.settings.render.possessor_ring_bgr
                cv2.rectangle(frame, (box[0] - 3, box[1] - 3), (box[2] + 3, box[3] + 3),
                              ring, self.settings.render.possessor_ring_thickness)
            num = ctx.player_numbers.get(tid)
            name = ctx.player_names.get(tid)
            label = f"#{num} {name}" if name else (f"#{num}" if num is not None else f"ID:{tid}")
            cv2.putText(frame, label, (box[0], max(14, box[1] - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(frame, label, (box[0], max(14, box[1] - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        # Balón
        if ctx.ball_detections is not None and len(ctx.ball_detections) > 0:
            b = ctx.ball_detections.xyxy[0].astype(int)
            cv2.rectangle(frame, (b[0], b[1]), (b[2], b[3]), (0, 140, 255), 2)
        # Aro(s)
        rim_bgr = self.settings.render.rim_bgr
        if ctx.hoop_detections is not None and len(ctx.hoop_detections) > 0:
            for hoop_box in ctx.hoop_detections.xyxy:
                hb = hoop_box.astype(int)
                cv2.rectangle(frame, (hb[0], hb[1]), (hb[2], hb[3]), rim_bgr, 2)
                cv2.putText(frame, "ARO", (hb[0], max(14, hb[1] - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(frame, "ARO", (hb[0], max(14, hb[1] - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, rim_bgr, 1, cv2.LINE_AA)
        # Marcador (esquina superior izquierda) + banner del resultado del tiro.
        self._draw_scoreboard(frame)
        if ctx.shot_made is not None:
            self._draw_shot_banner(frame, ctx.shot_made)
        return frame

    def _draw_scoreboard(self, frame: np.ndarray) -> None:
        """Marcador de tiros (aciertos/intentos) por equipo arriba a la izquierda."""
        if not self.settings.score.enabled:
            return
        st = self.shot_tracker
        counts = st.counts_by_team()
        names = self.settings.teams.team_names

        def _row(label: str, color_key: str):
            c = counts.get(color_key, {"made": 0, "missed": 0})
            made, att = c["made"], c["made"] + c["missed"]
            return f"{label}: {made}/{att}"

        rows = [
            _row(names[0] if len(names) > 0 else "Equipo 0", "white"),
            _row(names[1] if len(names) > 1 else "Equipo 1", "dark"),
        ]

        x, y = 12, 12
        line_h = 24
        width = 240
        height = line_h * (len(rows) + 1) + 8
        overlay = frame.copy()
        cv2.rectangle(overlay, (x, y), (x + width, y + height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

        cv2.putText(frame, f"TIROS  {st.makes}/{st.attempts}",
                    (x + 10, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (255, 255, 255), 1, cv2.LINE_AA)
        for i, text in enumerate(rows):
            ty = y + 20 + line_h * (i + 1)
            cv2.putText(frame, text, (x + 10, ty),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    def _draw_shot_banner(self, frame: np.ndarray, made: bool) -> None:
        """Banner centrado arriba: CANASTA (verde) o FALLO (rojo)."""
        s = self.settings.render
        color = s.made_rim_highlight_bgr if made else s.missed_rim_highlight_bgr
        label = s.made_label if made else s.missed_label
        h, w = frame.shape[:2]
        scale = 1.4
        thickness = 3
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, scale, thickness)
        cx = (w - tw) // 2
        cy = th + 24
        pad = 14
        overlay = frame.copy()
        cv2.rectangle(overlay, (cx - pad, cy - th - pad),
                      (cx + tw + pad, cy + pad), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)
        cv2.putText(frame, label, (cx, cy), cv2.FONT_HERSHEY_DUPLEX,
                    scale, color, thickness, cv2.LINE_AA)

    def _draw_map(self, ctx: FrameContext) -> np.ndarray:
        dots = [
            PlayerDot(
                xy_ft=p["xy_ft"],
                team=p.get("team"),
                track_id=p["track_id"],
                is_possessor=(p["track_id"] == ctx.possessor_track_id),
                number=ctx.player_numbers.get(p["track_id"]),
            )
            for p in ctx.players_world
        ]
        return self.renderer.draw(
            players=dots,
            possessor_xy_ft=(
                tuple(ctx.possessor_world) if ctx.possessor_world is not None else None
            ),
            basket_side=ctx.shot_side,
            basket_made=ctx.shot_made,
        )

    # ------------------------------------------------------------------
    def _detect_release(self, ctx: FrameContext) -> bool:
        """Suelta del tiro por pose del poseedor (opt-in). Rellena
        ``ctx.release_event`` y devuelve True si hay suelta en este frame."""
        if not self.settings.pose.enabled:
            return False
        # Centro del balón (tracker dedicado).
        if ctx.ball_detections is None or len(ctx.ball_detections) == 0:
            self.release_detector.update(ctx.frame_index, [], None)
            return False
        b = ctx.ball_detections.xyxy[0]
        ball_xy = np.array([(b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0], dtype=np.float32)
        # Bbox del poseedor (si lo hay).
        possessor_box = None
        if ctx.possessor_track_id is not None:
            for e in ctx.tracked_entities:
                if e.track_id == ctx.possessor_track_id:
                    possessor_box = e.bbox_xyxy
                    break
        if possessor_box is None:
            self.release_detector.update(ctx.frame_index, [], ball_xy)
            return False
        wrists = self.pose_estimator.wrists(ctx.frame_bgr, possessor_box).wrists()
        event = self.release_detector.update(ctx.frame_index, wrists, ball_xy)
        ctx.release_event = event
        return event is not None

    @staticmethod
    def _subset(raw: sv.Detections, classes) -> sv.Detections:
        if raw is None or len(raw) == 0:
            return sv.Detections.empty()
        mask = np.isin(raw.class_id, list(classes))
        if not mask.any():
            return sv.Detections.empty()
        return raw[mask]

    @staticmethod
    def _filter_confidence(
        dets: sv.Detections, min_confidence: float,
    ) -> sv.Detections:
        if dets is None or len(dets) == 0:
            return sv.Detections.empty()
        if dets.confidence is None:
            return dets
        mask = dets.confidence >= min_confidence
        if not mask.any():
            return sv.Detections.empty()
        return dets[mask]

    @staticmethod
    def _entities_from_boxes(dets: sv.Detections) -> List[TrackedEntity]:
        out: List[TrackedEntity] = []
        if dets is None or len(dets) == 0:
            return out
        for i in range(len(dets)):
            out.append(
                TrackedEntity(
                    track_id=i,
                    class_id=int(dets.class_id[i]),
                    confidence=float(dets.confidence[i]) if dets.confidence is not None else 0.0,
                    bbox_xyxy=dets.xyxy[i].astype(np.float32),
                    mask=None,
                )
            )
        return out

    @staticmethod
    def _inside_court(xy_ft: tuple, margin_ft: float) -> bool:
        return (
            -margin_ft <= xy_ft[0] <= COURT.length_ft + margin_ft
            and -margin_ft <= xy_ft[1] <= COURT.width_ft + margin_ft
        )

    @staticmethod
    def _team_bgr(team: Optional[str]):
        if team == "white":
            return (0, 0, 255)
        if team == "dark":
            return (255, 255, 0)
        return (166, 184, 20)

    # ------------------------------------------------------------------
    def _open_video(self, path: str) -> VideoIO:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise FileNotFoundError(f"No se pudo abrir el vídeo: {path}")
        return VideoIO(
            cap=cap,
            fps=cap.get(cv2.CAP_PROP_FPS) or 30.0,
            width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            total_frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        )
