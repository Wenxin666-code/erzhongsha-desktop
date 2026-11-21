"""孙沁珂【小说】。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models import (
    DamageEvent, Player, SkillDefinition, SkillKind, SkillSourceType,
    SkillTiming,
)
from src.skill_modules.base import (
    SkillAIContext, SkillResolutionRequest, SkillResolutionResult,
    TriggeredSkillAction,
)

if TYPE_CHECKING:
    from src.engine import GameEngine


NOVEL_DEFINITION = SkillDefinition(
    skill_id="general.sunqinke.novel",
    name="小说",
    source_type=SkillSourceType.GENERAL,
    source_name="小说",
    kind=SkillKind.TRIGGERED,
    timings=(SkillTiming.AFTER_DAMAGE,),
    mandatory=False,
    description="当你受到伤害后，你可以摸两张牌并将其分配给任意角色。",
)


class NovelHandler:
    definition = NOVEL_DEFINITION

    def can_trigger(
        self, engine: GameEngine, controller: Player, event: object
    ) -> bool:
        return bool(
            controller.alive
            and isinstance(event, DamageEvent)
            and event.amount > 0
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
                "是否发动【小说】摸两张牌并分配？"
            ),
        )

    @staticmethod
    def _distribution_request(
        engine: GameEngine, remaining_card_ids: tuple[str, ...]
    ) -> SkillResolutionRequest | None:
        if not remaining_card_ids:
            return None
        return SkillResolutionRequest(
            kind="choose_target",
            prompt=(
                "【小说】：请选择该张牌的分配目标"
                f"（剩余{len(remaining_card_ids)}张）"
            ),
            context={"remaining_card_ids": remaining_card_ids},
            legal_targets=tuple(engine.get_alive_players()),
            optional=False,
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
            controller, 2, reason="小说摸牌"
        )
        card_ids = tuple(move.card.id for move in moves)
        if not card_ids:
            return SkillResolutionResult(
                self.definition, controller, applied=False
            )
        return SkillResolutionResult(
            skill=self.definition,
            controller=controller,
            applied=True,
            move_events=tuple(moves),
            messages=(
                f"{controller.general.name} 发动【小说】，摸"
                f"{len(moves)}张牌并开始分配",
            ),
            request=self._distribution_request(engine, card_ids),
        )

    def continue_resolution(
        self, engine: GameEngine, action: TriggeredSkillAction,
        request: SkillResolutionRequest, choice,
    ) -> SkillResolutionResult:
        controller = action.controller
        remaining = tuple(
            request.context.get("remaining_card_ids", ())
            if isinstance(request.context, dict) else ()
        )
        if not remaining:
            return SkillResolutionResult(
                self.definition, controller, applied=True,
                announce=False,
            )
        target = (
            choice
            if isinstance(choice, Player)
            and choice in request.legal_targets
            and choice.alive
            else controller
        )
        card = next(
            (
                candidate for candidate in controller.hand
                if candidate.id == remaining[0]
            ),
            None,
        )
        moves = ()
        if card is not None and target.seat != controller.seat:
            move = engine.transfer_owned_card(
                controller, target, card, "小说分配"
            )
            moves = (move,) if move is not None else ()
        next_request = self._distribution_request(
            engine, remaining[1:]
        )
        return SkillResolutionResult(
            skill=self.definition,
            controller=controller,
            applied=True,
            move_events=moves,
            messages=(
                f"{controller.general.name} 将【小说】的一张牌"
                f"分配给{target.general.name}",
            ),
            request=next_request,
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
        # 暂无用户指定的分配策略；1v1默认保留给自己，不向敌方送牌。
        return (
            action.controller
            if action.controller in request.legal_targets else None
        )


NOVEL_HANDLER = NovelHandler()
