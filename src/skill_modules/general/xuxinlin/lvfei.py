"""徐欣琳【绿妃】。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models import (
    Player, SkillDefinition, SkillKind, SkillSourceType, SkillTiming,
    TrickCardDiscardEvent,
)
from src.skill_modules.base import (
    SkillAIContext, SkillResolutionResult, TriggeredSkillAction,
)

if TYPE_CHECKING:
    from src.engine import GameEngine


LVFEI_DEFINITION = SkillDefinition(
    skill_id="general.xuxinlin.lvfei",
    name="绿妃",
    source_type=SkillSourceType.GENERAL,
    source_name="绿妃",
    kind=SkillKind.TRIGGERED,
    timings=(SkillTiming.CARD_DISCARDED_BY_TRICK,),
    mandatory=False,
    description=(
        "每当有角色因【过河拆桥】被弃置牌时，若弃置的牌花色为梅花，"
        "你可以获得此牌。"
    ),
)


class LvfeiHandler:
    definition = LVFEI_DEFINITION

    def can_trigger(
        self, engine: GameEngine, controller: Player, event: object
    ) -> bool:
        return bool(
            controller.alive
            and isinstance(event, TrickCardDiscardEvent)
            and event.trick_name == "过河拆桥"
            and event.discarded_card.suit == "club"
            and event.discarded_card in engine.discard_pile
        )

    def create_action(
        self, engine: GameEngine, controller: Player,
        event: TrickCardDiscardEvent,
    ) -> TriggeredSkillAction:
        return TriggeredSkillAction(
            skill=self.definition,
            controller=controller,
            event=event,
            prompt=(
                f"{event.target.general.name} 因【过河拆桥】被弃置了"
                "一张梅花牌，是否发动【绿妃】获得此牌？"
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
        event = action.event
        move = engine.gain_from_discard_pile(
            action.controller,
            event.discarded_card,
            "绿妃获得",
            source_event_id=event.move_event.move_id,
            visibility="public",
        )
        return SkillResolutionResult(
            skill=self.definition,
            controller=action.controller,
            applied=move is not None,
            move_events=((move,) if move is not None else ()),
            messages=(
                f"{action.controller.general.name} 发动【绿妃】，"
                f"获得被弃置的【{event.discarded_card.name}】",
            ),
        )

    def ai_should_activate(
        self, engine: GameEngine, action: TriggeredSkillAction,
        context: SkillAIContext,
    ) -> bool:
        # 获得牌没有成本；所有合法牌的保留价值都为正。
        return self.can_trigger(
            engine, action.controller, action.event
        )


LVFEI_HANDLER = LvfeiHandler()
