"""Tests del reparto multi-GPU (`backend/app/chunking.py`).

Funciones puras: reparto de frames entre GPUs y fusión de metadatos. No
levantan FastAPI ni tocan ffmpeg/GPU, así que corren en CI sin hardware.
"""

from __future__ import annotations

from backend.app.chunking import chunk_ranges, merge_metadata


# ---------------------------------------------------------------------------
# chunk_ranges
# ---------------------------------------------------------------------------
def test_chunk_ranges_cubre_todo_sin_huecos_ni_solapes():
    total, n = 100, 3
    ranges = chunk_ranges(total, n)
    # Cobertura contigua [0, total): cada trozo arranca donde acaba el anterior.
    start = 0
    for s, count in ranges:
        assert s == start
        start += count
    assert start == total


def test_chunk_ranges_reparte_el_resto_en_los_primeros():
    # 100 / 3 = 33 con resto 1 → el primer trozo lleva el frame extra.
    ranges = chunk_ranges(100, 3)
    counts = [c for _, c in ranges]
    assert counts == [34, 33, 33]
    assert sum(counts) == 100


def test_chunk_ranges_division_exacta():
    ranges = chunk_ranges(90, 3)
    assert ranges == [(0, 30), (30, 30), (60, 30)]


def test_chunk_ranges_mas_gpus_que_frames_no_genera_trozos_vacios():
    # Con n > total, se omiten los trozos vacíos (no GPUs ociosas con 0 frames).
    ranges = chunk_ranges(2, 8)
    assert ranges == [(0, 1), (1, 1)]
    assert all(c > 0 for _, c in ranges)


def test_chunk_ranges_casos_limite():
    assert chunk_ranges(0, 4) == []
    assert chunk_ranges(50, 0) == []
    assert chunk_ranges(10, 1) == [(0, 10)]


# ---------------------------------------------------------------------------
# merge_metadata
# ---------------------------------------------------------------------------
def test_merge_metadata_desplaza_indices_y_recalcula_timestamp():
    chunk0 = [{"frame_index": 0}, {"frame_index": 1}]
    chunk1 = [{"frame_index": 0}, {"frame_index": 1}]
    merged = merge_metadata([chunk0, chunk1], frame_offsets=[0, 2], fps=10.0)

    indices = [f["frame_index"] for f in merged]
    assert indices == [0, 1, 2, 3]  # el segundo trozo se desplaza por su offset
    # timestamp = frame_index global / fps
    assert [f["timestamp"] for f in merged] == [0.0, 0.1, 0.2, 0.3]


def test_merge_metadata_ordena_por_indice_global():
    chunk0 = [{"frame_index": 1}, {"frame_index": 0}]
    merged = merge_metadata([chunk0], frame_offsets=[0], fps=30.0)
    assert [f["frame_index"] for f in merged] == [0, 1]


def test_merge_metadata_fps_invalido_usa_30_por_defecto():
    chunk0 = [{"frame_index": 30}]
    merged = merge_metadata([chunk0], frame_offsets=[0], fps=0.0)
    assert merged[0]["timestamp"] == 1.0  # 30 / 30 fps de respaldo
