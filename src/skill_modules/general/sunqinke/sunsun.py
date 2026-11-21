"""孙沁珂【孙孙】。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models import (
    CardUseEvent, DamageEvent, DamageNature, Player, SkillDefinition,
    SkillKind, SkillSourceType, SkillTiming,
)
from src.skill_modules.base import (
    SkillAIContext, SkillResolutionRequest, SkillResolutionResult,
    TriggeredSkillAction,
)

if TYPE_CHECKING:
    from src.engine import GameEngine


SUNSUN_DEFINITION = SkillDefinition(
    skill_id="general.sunqinke.sunsun",
    name="孙孙",
    source_type=SkillSourceType.GENERAL,
    source_name="孙孙",
    kind=SkillKind.TRIGGERED,
    timings=(SkillTiming.CARD_USE,),
    mandatory=False,
    description=(
        "当你于回合内使用牌时，若此牌的点数或花色与你本回合使用的"
        "上一张牌相同，你可以摸1张牌。你本回合因此法获得第3张牌后，"
        "你可以对一名角色造成1点火焰伤害。"
    ),
)

_STANDARD_SUITS = {"spade", "heart", "club", "diamond"}
_STANDARD_RANKS = {
    "A", "2", "3", "4", "5", "6", "7",
    "8", "9", "10", "J", "Q", "K",
}
_DRAW_COUNT_KEY = f"{SUNSUN_DEFINITION.skill_id}.draw_count"


class SunsunHandler:
    definition = SUNSUN_DEFINITION

    @staticmethod
    def _matches(event: CardUseEvent) -> bool:
        previous = event.previous_card
        current = event.effective_card
        if previous is None:
            return False
        same_suit = (
            current.suit in _STANDARD_SUITS
            and previous.suit in _STANDARD_SUITS
            and current.suit == previous.suit
        )
        same_rank = (
            str(current.rank) in _STANDARD_RANKS
            and str(previous.rank) in _STANDARD_RANKS
            and str(current.rank) == str(previous.rank)
        )
        return same_suit or same_rank

    def can_trigger(
        self, engine: GameEngine, controller: Player, event: object
    ) -> bool:
        return bool(
            controller.alive
            and isinstance(event, CardUseEvent)
            and event.player.seat == controller.seat
            and engine.get_current_player().seat == controller.seat
            and self._matches(event)
        )

    def create_action(
        self, engine: GameEngine, controller: Player,
        event: CardUseEvent,
    ) -> TriggeredSkillAction:
        return TriggeredSkillAction(
            skill=self.definition,
            controller=controller,
            event=event,
            prompt=(
                f"{controller.general.name} 使用的【{event.effective_card.name}】"
                "与上一张牌花色或点数相同，是否发动【孙孙】摸1张牌？"
            ),
        )

    def resolve(
        self, engine: GameEngine, action: TriggeredSkillAction
    ) -> SkillResolutionResult:
        controller = action.controller
        if not self.can_trigger(engine, controller, action.event):
            return SkillResolutionResult(
                self.definition, controller, applied=False
            )
        moves = engine.draw_to_hand(
            controller, 1, reason="孙孙摸牌"
        )
        if not moves:
            return SkillResolutionResult(
                self.definition, controller, applied=False
            )
        count = controller.skill_usage_counts.get(
            _DRAW_COUNT_KEY, 0
        ) + 1
        controller.skill_usage_counts[_DRAW_COUNT_KEY] = count
        request = None
        if count == 3:
            request = SkillResolutionRequest(
                kind="choose_target",
                prompt="【孙孙】：是否选择一名角色造成1点火焰伤害？",
                legal_targets=tuple(engine.get_alive_players()),
                optional=True,
            )
        return SkillResolutionResult(
            skill=self.definition,
            controller=controller,
            applied=True,
            move_events=tuple(moves),
            messages=(
                f"{controller.general.name} 发动【孙孙】摸1张牌"
                f"（本回合第{count}张）",
            ),
            request=request,
        )

    def continue_resolution(
        self, engine: GameEngine, action: TriggeredSkillAction,
        request: SkillResolutionRequest, choice,
    ) -> SkillResolutionResult:
        controller = action.controller
        if (
            not isinstance(choice, Player)
            or choice not in request.legal_targets
            or not choice.alive
        ):
            return SkillResolutionResult(
                self.definition, controller, applied=True,
                announce=False,
            )
        damage = DamageEvent(
            amount=1,
            nature=DamageNature.FIRE,
            source_player=controller,
        )
        return SkillResolutionResult(
            skill=self.definition,
            controller=controller,
            applied=True,
            messages=(
                f"{controller.general.name} 的【孙孙】令"
                f"{choice.general.name} 受到1点火焰伤害",
            ),
            request=SkillResolutionRequest(
                kind="damage",
                prompt=f"{choice.general.name} 受到1点火焰伤害",
                context=damage,
                legal_targets=(choice,),
                optional=False,
            ),
            announce=False,
        )

    def ai_should_activate(
        self, engine: GameEngine, action: TriggeredSkillAction,
        context: SkillAIContext,
    ) -> bool:
        return self.can_trigger(
            engine, action.controller, action.event
        )

    def ai_choose_target(
        self, engine: GameEngine, action: TriggeredSkillAction,
        request: SkillResolutionRequest,
    ) -> Player | None:
        from src.ai import choose_attack_target, choose_slash_plan

        enemies = [
            target for target in request.legal_targets
            if engine.are_enemies(action.controller, target)
        ]
        slash_plan = choose_slash_plan(engine, action.controller)
        if (
            slash_plan is not None
            and slash_plan.targets
            and slash_plan.targets[0] in enemies
        ):
            return slash_plan.targets[0]
        return choose_attack_target(
            engine, action.controller, enemies
        )


SUNSUN_HANDLER = SunsunHandler()
