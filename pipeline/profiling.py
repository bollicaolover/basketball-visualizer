"""Cronómetro acumulativo por etapa del pipeline.

Mide el tiempo de pared (wall-clock) que consume cada etapa a lo largo de todo
el vídeo y produce un desglose al final (segundos totales, % y ms/frame).

Nota sobre la GPU: las operaciones CUDA son asíncronas, así que el tiempo de
una etapa que lanza trabajo en GPU puede contabilizarse cuando el resultado se
sincroniza (normalmente al convertirlo a numpy en la misma etapa). Para una
medición exacta por etapa, activar ``cuda_sync`` (serializa la GPU en cada
frontera, lo que ralentiza algo el conjunto pero atribuye el tiempo con
precisión).
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable, Dict, List, Tuple


class StageTimer:
    def __init__(self, cuda_sync: bool = False) -> None:
        self._acc: Dict[str, float] = {}
        self._order: List[str] = []
        self._sync: Callable[[], None] = (
            self._make_cuda_sync() if cuda_sync else (lambda: None)
        )

    @staticmethod
    def _make_cuda_sync() -> Callable[[], None]:
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                return torch.cuda.synchronize
        except Exception:
            pass
        return lambda: None

    @contextmanager
    def stage(self, name: str):
        self._sync()
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self._sync()
            self.add(name, time.perf_counter() - t0)

    def add(self, name: str, seconds: float) -> None:
        if name not in self._acc:
            self._acc[name] = 0.0
            self._order.append(name)
        self._acc[name] += seconds

    def totals(self) -> List[Tuple[str, float]]:
        """(nombre, segundos) en orden de primera aparición."""
        return [(n, self._acc[n]) for n in self._order]

    @property
    def total(self) -> float:
        return sum(self._acc.values())
