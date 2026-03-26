from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FSInputFile:
    path: str
    filename: str | None = None


InputFile = FSInputFile


@dataclass
class BufferedInputFile:
    data: bytes
    filename: str
