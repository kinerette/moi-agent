"""Logging structuré + buffer in-memory pour le dashboard."""

from __future__ import annotations

import logging
import sys
from collections import deque
from datetime import datetime

LOG_BUFFER: deque[dict] = deque(maxlen=500)


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        LOG_BUFFER.append({
            "ts": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "msg": self.format(record),
        })


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("moi")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("[%(asctime)s] %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    # Console (force UTF-8 on Windows)
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)
    logger.addHandler(sh)

    # In-memory buffer
    bh = _BufferHandler()
    bh.setFormatter(fmt)
    bh.setLevel(logging.DEBUG)
    logger.addHandler(bh)

    return logger


log = _setup_logger()
