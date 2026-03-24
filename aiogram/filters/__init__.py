from __future__ import annotations

from typing import Any


class StateFilter:
    def __init__(self, *states: Any):
        self.states = states


from .command import Command, CommandStart

__all__ = ["StateFilter", "Command", "CommandStart"]
