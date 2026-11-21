"""丁逸晨【Kiss】。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.ai import card_keep_value
from src.models import (
    Card, JudgmentEvent, Player, SkillDefinition, SkillKind, SkillSourceType,
    SkillTiming,
)
from src.skill_modules.base import (
    JudgmentReplacementAction, JudgmentReplacementResult, owned_cards,
)

if TYPE_CHECKING:
    from src.engine import GameEngine


KISS_DEFINITION = SkillDefinition(
    skill_id="general.kiss",
    name="Kiss",
    source_type=SkillSourceType.GENERAL,
    source_name="Kiss",
    kind=SkillKind.TRIGGERED,
    timings=(SkillTiming.JUDGMENT_BEFORE_EFFECT,),
    mandatory=False,
    description="一名角色的判定牌生效前，你可以用一张手牌或装备牌替换之。",
)


class KissHandler:
    definition = KISS_DEFINITION

    def candidates(
        self, engine: GameEngine, controller: Player, event: JudgmentEvent
    ) -> list[Card]:
        if not controller.alive or event.current_card is None:
            return []
        return list(owned_cards(controller))

    def create_action(
        self, engine: GameEngine, controller: Player, event: JudgmentEvent
    ) -> JudgmentReplacementAction:
        return JudgmentReplacementAction(
            skill=self.definition,
            controller=controller,
            event=event,
            candidates=tuple(self.candidates(engine, controller, event)),
            prompt=(
                f"{controller.general.name} 是否发动【Kiss】，"
                "选择一张手牌或装备牌替换当前判定牌？"
            ),
        )

    @staticmethod
    def _desired_result(
        engine: GameEngine, controller: Player, event: JudgmentEvent
    ) -> bool:
        allied = not engine.are_enemies(controller, event.judging_player)
        if event.reason == "银河领主":
            return True
        if event.reason == "八卦阵":
            return allied
        if event.reason in ("乐不思蜀", "兵粮寸断", "闪电"):
            return not allied
        return allied

    def ai_choose_card(
        self, engine: GameEngine, action: JudgmentReplacementAction
    ) -> Card | None:
        event = action.event
        current = event.current_card
        if current is None:
            return None
        desired = self._desired_result(engine, action.controller, event)
        current_result = engine.matches_judgment(current, event.result_rule)
        if current_result == desired:
            return None
        candidates = [
            card for card in action.candidates
            if engine.matches_judgment(card, event.result_rule) == desired
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda card: (
                1 if card in action.controller.equipment else 0,
                card_keep_value(engine, action.controller, card),
                card.id,
            ),
        )

    def resolve(
        self, engine: GameEngine, action: JudgmentReplacementAction,
        replacement: Card,
    ) -> JudgmentReplacementResult:
        current_action = self.create_action(
            engine, action.controller, action.event
        )
        if replacement not in current_action.candidates:
            return JudgmentReplacementResult(
                action=current_action, event=action.event, applied=False
            )
        event, move = engine.replace_judgment_and_gain_original(
            action.event,
            action.controller,
            replacement,
            reason="Kiss替换判定牌",
        )
        if move is None:
            return JudgmentReplacementResult(
                action=current_action, event=action.event, applied=False
            )
        return JudgmentReplacementResult(
            action=current_action,
            event=event,
            applied=True,
            move_events=(move,),
            messages=(
                f"{action.controller.general.name} 发动【Kiss】，"
                f"以【{replacement.name}】替换判定牌并获得原判定牌",
            ),
        )


KISS_HANDLER = KissHandler()
