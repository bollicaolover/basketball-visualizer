"""Backend FastAPI para la aplicación web de análisis táctico de baloncesto.

Endpoints:
    POST /api/upload              — Sube vídeo, lanza pipeline, devuelve job_id
    GET  /api/jobs/{job_id}       — Estado del trabajo (incluye tasks y progress)
    GET  /api/system/stats        — CPU y GPU en tiempo real
    GET  /api/outputs/{job_id}/overlay.mp4    — Vídeo anotado (streaming)
    GET  /api/outputs/{job_id}/metadata.json  — Metadatos tácticos por frame
    POST /api/outputs/{job_id}/annotations    — Guarda anotaciones del usuario
    GET  /api/outputs/{job_id}/annotations    — Lee anotaciones guardadas

Arquitectura: un único Lock por GPU evita trabajos concurrentes. Sin Celery
ni Redis; se usa BackgroundTasks + subprocess para ejecutar el pipeline.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import os
import secrets as _secrets
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

try:  # paquete completo (uvicorn backend.app.main:app)
    from backend.app.chunking import (
        chunk_ranges,
        concat_videos,
        merge_metadata,
        probe_video,
        split_video,
        transcode_clean,
    )
except ImportError:  # lanzado como app.main desde backend/
    from app.chunking import (  # type: ignore
        chunk_ranges,
        concat_videos,
        merge_metadata,
        probe_video,
        split_video,
        transcode_clean,
    )

# ---------------------------------------------------------------------------
# Paths base (relativos a la raíz del proyecto, no al directorio del backend)
# ---------------------------------------------------------------------------
PROJECT_ROOT      = Path(__file__).resolve().parents[2]
DATA_UPLOADS      = PROJECT_ROOT / "data" / "uploads"
DATA_JOBS         = PROJECT_ROOT / "data" / "jobs"
DATA_OUTPUTS      = PROJECT_ROOT / "data" / "outputs"
DATA_TEST_VIDEOS  = PROJECT_ROOT / "data" / "test_videos"
# Roster por defecto para los vídeos de prueba (todos son Celtics vs Knicks):
# dorsales → nombres + colores de equipo. Se aplica automáticamente al lanzar
# un clip de ejemplo, sin que el usuario tenga que subir el JSON.
DEFAULT_TEST_ROSTER = PROJECT_ROOT / "rosters" / "knicks-celtics.json"
STATIC_DIR        = Path(__file__).parent / "static"

for _d in (DATA_UPLOADS, DATA_JOBS, DATA_OUTPUTS, STATIC_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Basketball Tactics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir frontend compilado (Vue 3 build) desde "/"
_frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")

# Archivos estáticos del backend (court.png, etc.)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# GPU lock: un trabajo a la vez para no saturar la A100
_gpu_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Auth (contraseña de acceso opcional via APP_PASSWORD env var)
# ---------------------------------------------------------------------------

_APP_PASSWORD   = os.environ.get("APP_PASSWORD", "")
_SESSION_SECRET = os.environ.get("SESSION_SECRET", _secrets.token_hex(32))
_COOKIE_NAME    = "b2d_session"
_SKIP_PATHS     = {"/api/auth/login"}
_SKIP_PREFIXES  = ("/assets/", "/static/")


def _make_token() -> str:
    return _hmac.new(_SESSION_SECRET.encode(), _APP_PASSWORD.encode(), hashlib.sha256).hexdigest()


def _valid_session(token: str) -> bool:
    if not _APP_PASSWORD:
        return True
    return _hmac.compare_digest(token, _make_token())


@app.middleware("http")
async def _auth_guard(request: Request, call_next):
    if not _APP_PASSWORD:
        return await call_next(request)
    path = request.url.path
    if path in _SKIP_PATHS or any(path.startswith(p) for p in _SKIP_PREFIXES):
        return await call_next(request)
    if not _valid_session(request.cookies.get(_COOKIE_NAME, "")):
        # Solo bloquea rutas API — las rutas SPA pasan para que Vue cargue
        # y muestre la pantalla de login por su cuenta
        if path.startswith("/api/"):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


# ---------------------------------------------------------------------------
# Helpers de estado
# ---------------------------------------------------------------------------

def _job_path(job_id: str) -> Path:
    return DATA_JOBS / f"{job_id}.json"


def _read_job(job_id: str) -> dict:
    p = _job_path(job_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return json.loads(p.read_text())


def _write_job(job_id: str, data: dict) -> None:
    p = _job_path(job_id)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(p)


# ---------------------------------------------------------------------------
# Task definitions (order matters — index = display order)
# ---------------------------------------------------------------------------

_TASK_DEFS = [
    {"id": "upload",   "label": "Subiendo archivo al servidor..."},
    {"id": "decode",   "label": "Preparando pipeline de análisis..."},
    {"id": "ai",       "label": "Analizando vídeo con IA..."},
    {"id": "finalize", "label": "Generando salida..."},
]


def _make_tasks(running: Optional[str] = None, done_ids: Optional[set] = None,
                ai_progress: int = 0) -> list:
    done_ids = done_ids or set()
    result = []
    for t in _TASK_DEFS:
        tid = t["id"]
        if tid in done_ids:
            status = "done"
        elif tid == running:
            status = "running"
        else:
            status = "pending"
        task = {"id": tid, "label": t["label"], "status": status}
        if tid == "ai" and status == "running":
            task["progress"] = ai_progress
        result.append(task)
    return result


# ---------------------------------------------------------------------------
# Pipeline runner (ejecutado en hilo background)
# ---------------------------------------------------------------------------

def _run_worker(
    input_path: Path,
    overlay_path: Path,
    gpu: str,
    mem_fraction: float,
    on_progress,
    worker_id: int = 0,
    team_names: Optional[list] = None,
    roster_path: Optional[str] = None,
    tracker: str = "sam",
) -> tuple[int, str]:
    """Lanza un subproceso ``pipeline.run`` en la GPU ``gpu`` y reporta progreso.

    ``on_progress(worker_id, cur=?, tot=?, stage=?)`` se invoca con las líneas
    ``[STAGE]`` y ``Procesados cur/tot`` del worker. Devuelve
    ``(returncode, stderr)``.
    """
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": str(gpu)}
    cmd = [
        sys.executable, "-m", "pipeline.run",
        "--input", str(input_path),
        "--output", str(overlay_path),
        "--metadata",
        "--no-map",
        "--shot3d",
        "--mem-fraction", str(mem_fraction),
        "--tracker", tracker,
    ]
    if team_names and len(team_names) == 2 and all(n.strip() for n in team_names):
        # El CLI separa por la primera coma → se sanea para no romper el parseo.
        a, b = (n.strip().replace(",", " ") for n in team_names)
        cmd += ["--team-names", f"{a},{b}"]
    if roster_path:
        cmd += ["--roster", str(roster_path)]
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    stderr_lines: list[str] = []

    def _drain_stderr():
        for line in proc.stderr:
            stderr_lines.append(line)

    _t = threading.Thread(target=_drain_stderr, daemon=True)
    _t.start()

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        if line.startswith("[STAGE]"):
            parts = line.split()
            on_progress(worker_id, stage=parts[1] if len(parts) > 1 else None)
        elif line.endswith("frames") and "/" in line:
            # Línea de progreso del orchestrator: "  150/3000 frames"
            for part in line.split():
                if "/" in part:
                    try:
                        cur, tot = part.split("/")
                        on_progress(worker_id, cur=int(cur), tot=int(tot))
                    except (ValueError, ZeroDivisionError):
                        pass
                    break

    proc.wait()
    _t.join(timeout=3)
    return proc.returncode, "".join(stderr_lines)[-3000:]


def _done_job_payload(job_id: str) -> dict:
    out_dir = DATA_OUTPUTS / job_id
    payload = {
        "status": "done",
        "job_id": job_id,
        "progress": 100,
        "tasks": _make_tasks(done_ids={"upload", "decode", "ai", "finalize"}),
        "overlay_url": f"/api/outputs/{job_id}/overlay.mp4",
        "clean_url": f"/api/outputs/{job_id}/clean.mp4",
        "metadata_url": f"/api/outputs/{job_id}/metadata.json",
        "annotations_url": f"/api/outputs/{job_id}/annotations",
    }
    if (out_dir / "shot3d.mp4").exists():
        payload["shot3d_url"] = f"/api/outputs/{job_id}/shot3d.mp4"
    if (out_dir / "shot3d.json").exists():
        payload["shot3d_json_url"] = f"/api/outputs/{job_id}/shot3d.json"
    return payload


def _run_single(
    job_id: str, input_path: Path, overlay_path: Path, gpu: str, mem_fraction: float,
    team_names: Optional[list] = None,
    roster_path: Optional[str] = None,
    tracker: str = "sam",
) -> None:
    """Una GPU: procesa el vídeo completo sin partir (continuidad de identidad)."""
    state = {"done": {"upload"}, "stage": "decode", "progress": 0}

    _write_job(job_id, {
        "status": "processing", "job_id": job_id, "progress": 0,
        "tasks": _make_tasks(running="decode", done_ids={"upload"}),
    })

    def on_progress(_wid, cur=None, tot=None, stage=None):
        if stage == "decode":
            state["stage"] = "decode"
        elif stage == "ai":
            state["done"].add("decode"); state["stage"] = "ai"; state["progress"] = 0
        elif stage in ("render", "metadata"):
            state["done"].update({"decode", "ai"}); state["stage"] = "finalize"
        elif stage == "shot3d":
            state["done"].update({"decode", "ai"}); state["stage"] = "finalize"
        if cur is not None and tot:
            state["progress"] = min(99, int(cur / tot * 100))
        _write_job(job_id, {
            "status": "processing", "job_id": job_id, "progress": state["progress"],
            "tasks": _make_tasks(
                running=state["stage"], done_ids=state["done"],
                ai_progress=state["progress"],
            ),
        })

    rc, err = _run_worker(
        input_path, overlay_path, gpu, mem_fraction, on_progress,
        team_names=team_names, roster_path=roster_path, tracker=tracker,
    )
    if rc != 0:
        raise RuntimeError(err)

    # Vídeo limpio (sin cajas horneadas) para la capa interactiva del frontend.
    # Es opcional: si el transcode falla, el reproductor cae al overlay.mp4.
    _write_job(job_id, {
        "status": "processing", "job_id": job_id, "progress": 99,
        "tasks": _make_tasks(running="finalize", done_ids={"upload", "decode", "ai"}),
    })
    try:
        transcode_clean(str(input_path), str(overlay_path.parent / "clean.mp4"))
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] vídeo limpio no generado: {exc}", flush=True)

    _write_job(job_id, _done_job_payload(job_id))


def _run_chunked(
    job_id: str, input_path: Path, output_dir: Path, overlay_path: Path,
    gpus: list, mem_fraction: float,
) -> None:
    """Varias GPUs: parte el vídeo, procesa cada trozo en una GPU y concatena."""
    fps, total = probe_video(str(input_path))
    ranges = chunk_ranges(total, len(gpus))
    if not ranges:
        raise RuntimeError("Vídeo sin frames legibles")
    gpus = gpus[:len(ranges)]  # vídeo corto: menos trozos que GPUs

    chunk_dirs = [output_dir / f"chunk_{i}" for i in range(len(ranges))]
    for d in chunk_dirs:
        d.mkdir(parents=True, exist_ok=True)
    chunk_inputs = [d / "input.mp4" for d in chunk_dirs]
    chunk_outputs = [d / "overlay.mp4" for d in chunk_dirs]

    # --- decode: partir el vídeo en segmentos exactos -----------------------
    _write_job(job_id, {
        "status": "processing", "job_id": job_id, "progress": 0,
        "tasks": _make_tasks(running="decode", done_ids={"upload"}),
    })
    split_video(str(input_path), [str(p) for p in chunk_inputs], ranges, fps)

    # --- ai: workers en paralelo, progreso agregado -------------------------
    progress = {i: {"cur": 0, "tot": 0} for i in range(len(ranges))}
    plock = threading.Lock()
    errors: dict = {}

    def on_progress(wid, cur=None, tot=None, stage=None):
        with plock:
            if cur is not None:
                progress[wid]["cur"] = cur
            if tot is not None:
                progress[wid]["tot"] = tot
            tot_sum = sum(p["tot"] for p in progress.values())
            cur_sum = sum(p["cur"] for p in progress.values())
            pct = min(99, int(cur_sum / tot_sum * 100)) if tot_sum > 0 else 0
        _write_job(job_id, {
            "status": "processing", "job_id": job_id, "progress": pct,
            "tasks": _make_tasks(
                running="ai", done_ids={"upload", "decode"}, ai_progress=pct,
            ),
        })

    def worker(wid):
        rc, err = _run_worker(
            chunk_inputs[wid], chunk_outputs[wid], gpus[wid], mem_fraction,
            on_progress, wid,
        )
        if rc != 0:
            errors[wid] = err

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(ranges))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise RuntimeError(next(iter(errors.values())))

    # --- finalize: concatenar overlays + fusionar metadatos -----------------
    _write_job(job_id, {
        "status": "processing", "job_id": job_id, "progress": 99,
        "tasks": _make_tasks(running="finalize", done_ids={"upload", "decode", "ai"}),
    })
    concat_videos([str(p) for p in chunk_outputs], str(overlay_path))
    starts = [r[0] for r in ranges]
    chunk_meta = []
    team_names = None
    for d in chunk_dirs:
        mp = d / "overlay_metadata.json"
        if not mp.exists():
            chunk_meta.append([])
            continue
        data = json.loads(mp.read_text())
        # Formato nuevo: {team_names, frames}; antiguo: array plano.
        if isinstance(data, dict):
            chunk_meta.append(data.get("frames", []))
            team_names = team_names or data.get("team_names")
        else:
            chunk_meta.append(data)
    merged = merge_metadata(chunk_meta, starts, fps)
    (output_dir / "overlay_metadata.json").write_text(
        json.dumps({"team_names": team_names, "frames": merged}, separators=(",", ":"))
    )
    try:
        transcode_clean(str(input_path), str(output_dir / "clean.mp4"))
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] vídeo limpio no generado: {exc}", flush=True)

    _write_job(job_id, _done_job_payload(job_id))


def _run_pipeline(
    job_id: str, input_path: Path, output_dir: Path,
    gpus: list, mem_fraction: float, team_names: Optional[list] = None,
    roster_path: Optional[str] = None,
    tracker: str = "sam",
) -> None:
    overlay_path = output_dir / "overlay.mp4"
    try:
        # SAM mantiene un memory bank por vídeo completo: el chunking rompe la
        # continuidad de identidad en el corte (track IDs y equipos se reinician).
        # Se usa una sola GPU: de entre las candidatas, la de más memoria libre.
        gpu = _resolve_gpu(gpus)
        if len(gpus) > 1:
            if tracker == "sam":
                print(
                    f"[INFO] GPUs candidatas {gpus}; SAM necesita el vídeo completo "
                    f"→ se usa la más libre: GPU {gpu}.",
                    flush=True,
                )
            else:
                print(
                    f"[INFO] GPUs candidatas {gpus}; tracker={tracker} "
                    f"→ se usa la más libre: GPU {gpu}.",
                    flush=True,
                )
        _run_single(
            job_id, input_path, overlay_path,
            gpu, mem_fraction,
            team_names=team_names, roster_path=roster_path, tracker=tracker,
        )
        input_path.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        _write_job(job_id, {"status": "error", "job_id": job_id, "error": str(exc)})
        shutil.rmtree(output_dir, ignore_errors=True)
    finally:
        _gpu_lock.release()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/auth/check")
async def auth_check():
    return {"ok": True}


@app.post("/api/auth/login")
async def auth_login(payload: dict, response: Response):
    password = payload.get("password", "")
    if not _APP_PASSWORD:
        return {"ok": True}
    if not _hmac.compare_digest(password.encode(), _APP_PASSWORD.encode()):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    response.set_cookie(
        _COOKIE_NAME, _make_token(),
        httponly=True, samesite="lax", max_age=86400 * 30,
    )
    return {"ok": True}


@app.post("/api/auth/logout")
async def auth_logout(response: Response):
    response.delete_cookie(_COOKIE_NAME)
    return {"ok": True}


def _list_gpus() -> list:
    """Enumera las GPUs disponibles: ``[{index, name, memory_total_gb}]``."""
    gpus: list = []
    try:
        import pynvml  # noqa: PLC0415
        pynvml.nvmlInit()
        for i in range(pynvml.nvmlDeviceGetCount()):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            raw_name = pynvml.nvmlDeviceGetName(handle)
            name = raw_name.decode() if isinstance(raw_name, bytes) else raw_name
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpus.append({
                "index": i,
                "name": name,
                "memory_total_gb": round(mem.total / 1024 ** 3, 1),
            })
        return gpus
    except Exception:
        pass
    try:
        res = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
        for line in res.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                try:
                    gpus.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "memory_total_gb": round(float(parts[2]) / 1024, 1),
                    })
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass
    return gpus


def _gpu_free_memory() -> dict:
    """Memoria libre por GPU: ``{index(int): free_MiB(int)}``. Vacío si falla."""
    free: dict = {}
    try:
        import pynvml  # noqa: PLC0415
        pynvml.nvmlInit()
        for i in range(pynvml.nvmlDeviceGetCount()):
            mem = pynvml.nvmlDeviceGetMemoryInfo(pynvml.nvmlDeviceGetHandleByIndex(i))
            free[i] = int(mem.free / 1024 ** 2)
        return free
    except Exception:
        pass
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
        for line in res.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                try:
                    free[int(parts[0])] = int(float(parts[1]))
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass
    return free


def _resolve_gpu(candidates: list) -> str:
    """De entre los índices candidatos, elige la GPU con más memoria libre.

    Evita lanzar sobre una GPU ocupada por otro proceso (OOM). Si no se puede
    consultar la memoria, usa el primer candidato.
    """
    if not candidates:
        return "0"
    free = _gpu_free_memory()
    if not free:
        return str(candidates[0])
    best = max(candidates, key=lambda g: free.get(int(g), -1))
    return str(best)


@app.get("/api/system/gpus")
async def get_gpus():
    """Lista de GPUs disponibles para que la web ofrezca la selección."""
    return JSONResponse({"gpus": _list_gpus()})


@app.get("/api/system/stats")
async def get_system_stats():
    stats: dict = {"cpu_percent": 0, "gpus": []}

    try:
        import psutil  # noqa: PLC0415
        stats["cpu_percent"] = round(psutil.cpu_percent(interval=None), 1)
    except Exception:
        pass

    try:
        import pynvml  # noqa: PLC0415
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            raw_name = pynvml.nvmlDeviceGetName(handle)
            name = raw_name.decode() if isinstance(raw_name, bytes) else raw_name
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            stats["gpus"].append({
                "name": name,
                "memory_total_gb": round(mem.total / 1024 ** 3, 1),
                "utilization": util.gpu,
            })
    except Exception:
        try:
            res = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=name,memory.total,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3,
            )
            for line in res.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    try:
                        stats["gpus"].append({
                            "name": parts[0],
                            "memory_total_gb": round(float(parts[1]) / 1024, 1),
                            "utilization": int(parts[2]),
                        })
                    except (ValueError, IndexError):
                        pass
        except Exception:
            pass

    return JSONResponse(stats)

VALID_TRACKERS = frozenset({"sam", "botsort"})


def _parse_tracker(tracker: str) -> str:
    t = (tracker or "sam").strip().lower()
    if t not in VALID_TRACKERS:
        raise HTTPException(status_code=400, detail=f"Tracker inválido: {tracker!r} (usa sam o botsort)")
    return t


def _parse_team_names(team1: str, team2: str) -> Optional[list]:
    """Dos nombres de equipo del formulario → ``[a, b]`` o None.

    Solo se devuelve si ambos vienen con contenido; así la metadata queda con
    ``team_names: null`` y el frontend usa "Equipo 1/2" por defecto.
    """
    a, b = (team1 or "").strip(), (team2 or "").strip()
    return [a, b] if a and b else None


def _parse_gpus(raw: str) -> list:
    """CSV de índices → lista validada contra las GPUs disponibles.

    Fallback a ``["0"]`` si no hay selección válida.
    """
    available_list = [str(g["index"]) for g in _list_gpus()]
    available = set(available_list)
    # "auto" → todas las GPUs como candidatas; _resolve_gpu elegirá la más libre.
    if (raw or "").strip().lower() == "auto":
        return available_list or ["0"]
    selected = []
    seen = set()
    for tok in (raw or "").split(","):
        tok = tok.strip()
        if not tok or tok in seen:
            continue
        if not available or tok in available:
            selected.append(tok)
            seen.add(tok)
    return selected or ["0"]


@app.get("/api/test-videos")
async def list_test_videos():
    if not DATA_TEST_VIDEOS.exists():
        return {"videos": []}
    videos = sorted(DATA_TEST_VIDEOS.glob("*.mp4"))
    return {"videos": [{"name": v.name, "size": v.stat().st_size} for v in videos]}


@app.post("/api/test-videos/{filename}/process")
async def process_test_video(
    filename: str,
    background_tasks: BackgroundTasks,
    gpus: str = Query("0"),
    mem_fraction: float = Query(1.0),
    team1: str = Query(""),
    team2: str = Query(""),
    tracker: str = Query("sam"),
):
    # Evitar path traversal: el fichero debe estar exactamente en DATA_TEST_VIDEOS
    src = (DATA_TEST_VIDEOS / filename).resolve()
    if not str(src).startswith(str(DATA_TEST_VIDEOS.resolve())):
        raise HTTPException(status_code=400, detail="Nombre de fichero no válido")
    if not src.exists():
        raise HTTPException(status_code=404, detail="Vídeo de prueba no encontrado")

    sel_gpus = _parse_gpus(gpus)
    mem_frac = max(0.05, min(1.0, mem_fraction))
    team_names = _parse_team_names(team1, team2)
    tracker_mode = _parse_tracker(tracker)

    job_id = str(uuid.uuid4())
    upload_path = DATA_UPLOADS / f"{job_id}.mp4"
    output_dir = DATA_OUTPUTS / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(src, upload_path)

    # Roster por defecto (Celtics vs Knicks): se copia junto al output para que
    # el pipeline queme los nombres y la vista de resultados pueda releerlo.
    roster_path: Optional[str] = None
    if DEFAULT_TEST_ROSTER.exists():
        try:
            roster_bytes = DEFAULT_TEST_ROSTER.read_bytes()
            roster_doc = json.loads(roster_bytes.decode("utf-8"))
            roster_file = output_dir / "roster.json"
            roster_file.write_bytes(roster_bytes)
            roster_path = str(roster_file)
            if team_names is None:
                team_names = list(roster_doc.keys())[:2]
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            roster_path = None   # roster corrupto: se sigue sin él

    _write_job(job_id, {"status": "pending", "job_id": job_id})

    acquired = _gpu_lock.acquire(blocking=False)
    if not acquired:
        background_tasks.add_task(
            _wait_and_run, job_id, upload_path, output_dir, sel_gpus, mem_frac,
            team_names, roster_path, tracker_mode,
        )
    else:
        background_tasks.add_task(
            _run_pipeline, job_id, upload_path, output_dir, sel_gpus, mem_frac,
            team_names, roster_path, tracker_mode,
        )

    return {"job_id": job_id}


@app.post("/api/upload")
async def upload_video(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    gpus: str = Form("0"),
    mem_fraction: float = Form(1.0),
    team1: str = Form(""),
    team2: str = Form(""),
    tracker: str = Form("sam"),
    roster: Optional[UploadFile] = File(None),
):
    if not file.filename or not file.filename.lower().endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .mp4")

    sel_gpus = _parse_gpus(gpus)
    mem_frac = max(0.05, min(1.0, mem_fraction))
    team_names = _parse_team_names(team1, team2)
    tracker_mode = _parse_tracker(tracker)

    job_id = str(uuid.uuid4())
    upload_path = DATA_UPLOADS / f"{job_id}.mp4"
    output_dir = DATA_OUTPUTS / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Guardar vídeo subido
    content = await file.read()
    upload_path.write_bytes(content)

    # Roster opcional (mismo formato que el CLI). Se guarda junto al output y, si
    # no se dieron nombres de equipo, se derivan de las claves del roster (orden
    # posicional → equipo claro/oscuro; el frontend lo reorienta si hace falta).
    roster_path: Optional[str] = None
    if roster is not None and roster.filename:
        try:
            roster_bytes = await roster.read()
            roster_doc = json.loads(roster_bytes.decode("utf-8"))
            if not isinstance(roster_doc, dict) or len(roster_doc) < 2:
                raise ValueError("el roster debe ser un objeto con dos equipos")
            roster_file = output_dir / "roster.json"
            roster_file.write_bytes(roster_bytes)
            roster_path = str(roster_file)
            if team_names is None:
                team_names = list(roster_doc.keys())[:2]
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"Roster no válido: {exc}")

    # Registrar trabajo como pending
    _write_job(job_id, {"status": "pending", "job_id": job_id})

    # Adquirir lock (no bloqueante) y lanzar pipeline en background
    acquired = _gpu_lock.acquire(blocking=False)
    if not acquired:
        # Ya hay un trabajo corriendo; encolar de forma simple (espera bloqueante)
        background_tasks.add_task(
            _wait_and_run, job_id, upload_path, output_dir, sel_gpus, mem_frac,
            team_names, roster_path, tracker_mode,
        )
    else:
        background_tasks.add_task(
            _run_pipeline, job_id, upload_path, output_dir, sel_gpus, mem_frac,
            team_names, roster_path, tracker_mode,
        )

    return {"job_id": job_id}


def _wait_and_run(
    job_id: str, input_path: Path, output_dir: Path, gpus: list, mem_fraction: float,
    team_names: Optional[list] = None,
    roster_path: Optional[str] = None,
    tracker: str = "sam",
) -> None:
    _gpu_lock.acquire()  # espera a que termine el trabajo anterior
    _run_pipeline(job_id, input_path, output_dir, gpus, mem_fraction,
                  team_names=team_names, roster_path=roster_path, tracker=tracker)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    return JSONResponse(_read_job(job_id))


@app.get("/api/outputs/{job_id}/overlay.mp4")
async def get_overlay(job_id: str):
    job = _read_job(job_id)
    if job.get("status") != "done":
        raise HTTPException(status_code=202, detail="El vídeo aún no está listo")
    path = DATA_OUTPUTS / job_id / "overlay.mp4"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    return FileResponse(str(path), media_type="video/mp4", filename="overlay.mp4")


@app.get("/api/outputs/{job_id}/clean.mp4")
async def get_clean(job_id: str):
    job = _read_job(job_id)
    if job.get("status") != "done":
        raise HTTPException(status_code=202, detail="El vídeo aún no está listo")
    path = DATA_OUTPUTS / job_id / "clean.mp4"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    return FileResponse(str(path), media_type="video/mp4", filename="clean.mp4")


@app.get("/api/outputs/{job_id}/shot3d.mp4")
async def get_shot3d_video(job_id: str):
    job = _read_job(job_id)
    if job.get("status") != "done":
        raise HTTPException(status_code=202, detail="La trayectoria 3D aún no está lista")
    path = DATA_OUTPUTS / job_id / "shot3d.mp4"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sin reconstrucción 3D para este análisis")
    return FileResponse(str(path), media_type="video/mp4", filename="shot3d.mp4")


@app.get("/api/outputs/{job_id}/shot3d.json")
async def get_shot3d_json(job_id: str):
    job = _read_job(job_id)
    if job.get("status") != "done":
        raise HTTPException(status_code=202, detail="La trayectoria 3D aún no está lista")
    path = DATA_OUTPUTS / job_id / "shot3d.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sin datos 3D para este análisis")
    return FileResponse(str(path), media_type="application/json")


@app.get("/api/outputs/{job_id}/metadata.json")
async def get_metadata(job_id: str):
    job = _read_job(job_id)
    if job.get("status") != "done":
        raise HTTPException(status_code=202, detail="Los metadatos aún no están listos")
    # El MetadataWriter escribe overlay_metadata.json junto al overlay
    path = DATA_OUTPUTS / job_id / "overlay_metadata.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Metadatos no encontrados")
    return FileResponse(str(path), media_type="application/json")


@app.get("/api/outputs/{job_id}/roster.json")
async def get_roster(job_id: str):
    """Roster guardado para el análisis (colores + nombres). 404 si no hubo."""
    _read_job(job_id)  # valida que el job existe
    path = DATA_OUTPUTS / job_id / "roster.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sin roster para este análisis")
    return FileResponse(str(path), media_type="application/json")


@app.get("/api/outputs/{job_id}/annotations")
async def get_annotations(job_id: str):
    _read_job(job_id)  # valida que el job existe
    path = DATA_OUTPUTS / job_id / "annotations.json"
    if not path.exists():
        return JSONResponse([])
    return JSONResponse(json.loads(path.read_text()))


@app.post("/api/outputs/{job_id}/annotations")
async def save_annotations(job_id: str, payload: dict):
    _read_job(job_id)  # valida que el job existe
    path = DATA_OUTPUTS / job_id / "annotations.json"
    annotations = payload.get("annotations", [])
    path.write_text(json.dumps(annotations))
    return {"saved": len(annotations)}


# ---------------------------------------------------------------------------
# SPA fallback: cualquier ruta no-API devuelve el index.html de Vue
# ---------------------------------------------------------------------------

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    index = _frontend_dist / "index.html" if _frontend_dist.exists() else None
    if index and index.exists():
        return FileResponse(str(index))
    return JSONResponse({"status": "API running"})
