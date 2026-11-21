"""曹操【奸雄】。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models import (
    DamageEvent, Player, SkillDefinition, SkillKind, SkillSourceType,
    SkillTiming,
)
from src.skill_modules.base import (
    SkillAIContext, SkillResolutionResult, TriggeredSkillAction,
)

if TYPE_CHECKING:
    from src.engine import GameEngine


JIANXIONG_DEFINITION = SkillDefinition(
    skill_id="general.jianxiong",
    name="奸雄",
    source_type=SkillSourceType.GENERAL,
    source_name="奸雄",
    kind=SkillKind.TRIGGERED,
    timings=(SkillTiming.AFTER_DAMAGE,),
    mandatory=False,
    description="当你受到伤害后，你可以获得造成此伤害的牌。",
)


class JianxiongHandler:
    """只处理奸雄的触发条件与规则移动，不包含界面或音效代码。"""

    definition = JIANXIONG_DEFINITION

    @staticmethod
    def _physical_cards(event: DamageEvent) -> tuple:
        if event.source_physical_cards:
            return event.source_physical_cards
        if event.source_card is not None:
            return (event.source_card,)
        return ()

    def can_trigger(
        self, engine: GameEngine, controller: Player, event: object
    ) -> bool:
        if (
            not isinstance(event, DamageEvent)
            or not controller.alive
            or event.amount <= 0
        ):
            return False
        physical_cards = self._physical_cards(event)
        return bool(
            physical_cards
            and all(
                card in engine.processing_area for card in physical_cards
            )
        )

    def create_action(
        self, engine: GameEngine, controller: Player, event: object
    ) -> TriggeredSkillAction:
        return TriggeredSkillAction(
            skill=self.definition,
            controller=controller,
            event=event,
            prompt=(
                f"{controller.general.name} 受到伤害后，"
                f"是否发动【{self.definition.name}】？"
            ),
        )

    def ai_should_activate(
        self, engine: GameEngine, action: TriggeredSkillAction,
        context: SkillAIContext,
    ) -> bool:
        """奸雄没有发动代价；实体伤害牌仍可获得时默认发动。"""
        return self.can_trigger(engine, action.controller, action.event)

    def resolve(
        self, engine: GameEngine, action: TriggeredSkillAction
    ) -> SkillResolutionResult:
        event = action.event
        if not self.can_trigger(engine, action.controller, event):
            return SkillResolutionResult(
                self.definition, action.controller, applied=False
            )
        moves = engine.gain_many_from_processing(
            action.controller,
            self._physical_cards(event),
            reason="奸雄获得造成伤害的牌",
            source_event_id=event.parent_slash_id,
            visibility="public",
        )
        if not moves:
            return SkillResolutionResult(
                self.definition, action.controller, applied=False
            )
        card_names = "、".join(f"【{move.card.name}】" for move in moves)
        return SkillResolutionResult(
            skill=self.definition,
            controller=action.controller,
            applied=True,
            move_events=tuple(moves),
            messages=(
                f"{action.controller.general.name} 发动【奸雄】，"
                f"获得造成伤害的牌{card_names}",
            ),
        )


JIANXIONG_HANDLER = JianxiongHandler()
