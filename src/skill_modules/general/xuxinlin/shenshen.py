"""徐欣琳【肾肾】。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models import (
    PlayPhaseEndEvent, Player, SkillDefinition, SkillKind,
    SkillSourceType, SkillTiming,
)
from src.skill_modules.base import (
    SkillResolutionResult, TriggeredSkillAction,
)

if TYPE_CHECKING:
    from src.engine import GameEngine


SHENSHEN_DEFINITION = SkillDefinition(
    skill_id="general.xuxinlin.shenshen",
    name="肾肾",
    source_type=SkillSourceType.GENERAL,
    source_name="肾肾",
    kind=SkillKind.LOCKED,
    timings=(SkillTiming.PLAY_PHASE_END,),
    mandatory=True,
    description=(
        "锁定技，出牌阶段结束时，若你本阶段使用了至少4张"
        "【过河拆桥】，则你的下个摸牌阶段多摸1张牌。"
    ),
)


class ShenshenHandler:
    definition = SHENSHEN_DEFINITION

    def can_trigger(
        self, engine: GameEngine, controller: Player, event: object
    ) -> bool:
        return bool(
            controller.alive
            and isinstance(event, PlayPhaseEndEvent)
            and event.player.seat == controller.seat
            and event.card_use_counts.get("过河拆桥", 0) >= 4
        )

    def create_action(
        self, engine: GameEngine, controller: Player,
        event: PlayPhaseEndEvent,
    ) -> TriggeredSkillAction:
        return TriggeredSkillAction(
            skill=self.definition,
            controller=controller,
            event=event,
            prompt=(
                f"{controller.general.name} 本阶段使用了"
                f"{event.card_use_counts.get('过河拆桥', 0)}张"
                "【过河拆桥】，【肾肾】生效"
            ),
        )

    def resolve(
        self, engine: GameEngine, action: TriggeredSkillAction
    ) -> SkillResolutionResult:
        if not self.can_trigger(
            engine, action.controller, action.event
        ):
            return SkillResolutionResult(
                self.definition, action.controller, applied=False
            )
        action.controller.pending_draw_phase_bonus += 1
        return SkillResolutionResult(
            skill=self.definition,
            controller=action.controller,
            applied=True,
            messages=(
                f"{action.controller.general.name} 的【肾肾】生效，"
                "下个摸牌阶段多摸1张牌",
            ),
        )


SHENSHEN_HANDLER = ShenshenHandler()
