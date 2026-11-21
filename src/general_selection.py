"""开局选将的顺位、候选池和占用状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Optional

from src.models import General


MAX_GENERAL_CANDIDATES = 8


@dataclass
class GeneralSelectionState:
    candidates: tuple[General, ...]
    seat_is_ai: tuple[bool, ...]
    selected_by_seat: dict[int, General] = field(default_factory=dict)
    current_seat: int = 0

    @classmethod
    def create(
        cls,
        generals: list[General],
        seat_is_ai: tuple[bool, ...],
        rng: Optional[random.Random] = None,
    ) -> "GeneralSelectionState":
        playable = [general for general in generals if general.playable]
        if len(playable) < len(seat_is_ai):
            raise ValueError("可用武将数量少于参与选将的座位数")
        chooser = rng or random
        candidates = tuple(
            chooser.sample(
                playable,
                min(MAX_GENERAL_CANDIDATES, len(playable)),
            )
        )
        return cls(candidates, seat_is_ai)

    @property
    def complete(self) -> bool:
        return self.current_seat >= len(self.seat_is_ai)

    @property
    def current_is_ai(self) -> bool:
        return bool(
            not self.complete
            and self.seat_is_ai[self.current_seat]
        )

    def is_selected(self, general: General) -> bool:
        return any(
            selected.id == general.id
            for selected in self.selected_by_seat.values()
        )

    def selected_seat(self, general: General) -> Optional[int]:
        return next(
            (
                seat for seat, selected in self.selected_by_seat.items()
                if selected.id == general.id
            ),
            None,
        )

    def available_generals(self) -> list[General]:
        return [
            general for general in self.candidates
            if not self.is_selected(general)
        ]

    def choose(self, seat: int, general: General) -> bool:
        if (
            self.complete
            or seat != self.current_seat
            or general not in self.candidates
            or self.is_selected(general)
        ):
            return False
        self.selected_by_seat[seat] = general
        self.current_seat += 1
        return True

    def choose_current_ai(
        self, rng: Optional[random.Random] = None
    ) -> Optional[General]:
        if not self.current_is_ai:
            return None
        available = self.available_generals()
        if not available:
            return None
        general = (rng or random).choice(available)
        return general if self.choose(self.current_seat, general) else None

    def ordered_selections(self) -> tuple[General, ...]:
        if not self.complete:
            raise RuntimeError("所有座位选将完成后才能建立对局")
        return tuple(
            self.selected_by_seat[seat]
            for seat in range(len(self.seat_is_ai))
        )
