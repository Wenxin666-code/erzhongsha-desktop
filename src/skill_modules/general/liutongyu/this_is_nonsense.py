"""刘桐羽【这不扯淡吗】。"""

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


THIS_IS_NONSENSE_DEFINITION = SkillDefinition(
    skill_id="general.this_is_nonsense",
    name="这不扯淡吗",
    source_type=SkillSourceType.GENERAL,
    source_name="这不扯淡吗",
    kind=SkillKind.TRIGGERED,
    timings=(SkillTiming.AFTER_DAMAGE,),
    mandatory=False,
    description=(
        "每回合限2次，当你受到伤害后，你可以摸1张牌并"
        "展示全部手牌，若全部手牌颜色一致，你回复1点体力。"
    ),
)


class ThisIsNonsenseHandler:
    definition = THIS_IS_NONSENSE_DEFINITION
    turn_limit = 2

    def can_trigger(
        self, engine: GameEngine, controller: Player, event: object
    ) -> bool:
        return bool(
            isinstance(event, DamageEvent)
            and event.amount > 0
            and controller.alive
            and controller.skill_usage_counts.get(
                self.definition.skill_id, 0
            ) < self.turn_limit
        )

    def create_action(
        self, engine: GameEngine, controller: Player, event: object
    ) -> TriggeredSkillAction:
        used = controller.skill_usage_counts.get(
            self.definition.skill_id, 0
        )
        return TriggeredSkillAction(
            skill=self.definition,
            controller=controller,
            event=event,
            prompt=(
                f"{controller.general.name} 受到伤害后，是否发动"
                f"【{self.definition.name}】？"
                f"（本回合已发动{used}/{self.turn_limit}次）"
            ),
        )

    def ai_should_activate(
        self, engine: GameEngine, action: TriggeredSkillAction,
        context: SkillAIContext,
    ) -> bool:
        return self.can_trigger(engine, action.controller, action.event)

    def resolve(
        self, engine: GameEngine, action: TriggeredSkillAction
    ) -> SkillResolutionResult:
        controller = action.controller
        event = action.event
        if not self.can_trigger(engine, controller, event):
            return SkillResolutionResult(
                self.definition, controller, applied=False
            )
        controller.skill_usage_counts[self.definition.skill_id] = (
            controller.skill_usage_counts.get(self.definition.skill_id, 0) + 1
        )
        moves = engine.draw_to_hand(
            controller, 1, reason="这不扯淡吗摸牌"
        )
        reveals = tuple(
            reveal
            for card in controller.hand
            if (
                reveal := engine.reveal_card(
                    controller,
                    card,
                    "hand",
                    "这不扯淡吗展示全部手牌",
                    source_event_id=event.parent_slash_id,
                )
            ) is not None
        )
        colors = [card.color for card in controller.hand]
        same_color = bool(
            colors
            and colors[0] in ("red", "black")
            and all(color == colors[0] for color in colors)
        )
        recovered = engine.recover(controller, 1) if same_color else 0
        messages = [
            f"{controller.general.name} 发动【这不扯淡吗】，摸1张牌并展示全部手牌"
        ]
        if same_color:
            if recovered:
                messages.append(
                    f"{controller.general.name} 的全部手牌颜色一致，回复1点体力"
                )
            else:
                messages.append(
                    f"{controller.general.name} 的全部手牌颜色一致，但体力已满"
                )
        else:
            messages.append(
                f"{controller.general.name} 的全部手牌颜色不一致"
            )
        return SkillResolutionResult(
            skill=self.definition,
            controller=controller,
            applied=True,
            move_events=tuple(moves),
            reveal_events=reveals,
            messages=tuple(messages),
        )


THIS_IS_NONSENSE_HANDLER = ThisIsNonsenseHandler()
