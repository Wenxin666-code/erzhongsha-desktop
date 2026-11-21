"""张艺严【小爷是一】。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models import (
    Phase, Player, SkillDefinition, SkillKind, SkillSourceType, SkillTiming,
)
from src.skill_modules.base import (
    ActiveSkillAction, ActiveSkillAIDecision, SkillResolutionResult,
)

if TYPE_CHECKING:
    from src.engine import GameEngine


XIAOYE_SHIYI_DEFINITION = SkillDefinition(
    skill_id="general.zhangyiyan.xiaoye_shiyi",
    name="小爷是一",
    source_type=SkillSourceType.GENERAL,
    source_name="小爷是一",
    kind=SkillKind.ACTIVE,
    timings=(SkillTiming.ACTIVE_PLAY,),
    mandatory=False,
    description=(
        "出牌阶段，你可以弃置2张牌，令一名角色在其下个"
        "出牌阶段使用【杀】的次数上限+1。"
    ),
)


class XiaoyeShiyiHandler:
    definition = XIAOYE_SHIYI_DEFINITION

    def create_action(
        self, engine: GameEngine, controller: Player
    ) -> ActiveSkillAction | None:
        owned = tuple(controller.hand + controller.equipment)
        if (
            not controller.alive
            or engine.state.phase != Phase.PLAY
            or engine.get_current_player().seat != controller.seat
            or len(owned) < 2
        ):
            return None
        return ActiveSkillAction(
            skill=self.definition,
            controller=controller,
            legal_cards=owned,
            required_cards=2,
            legal_targets=tuple(engine.get_alive_players()),
            required_targets=1,
            prompt=(
                "【小爷是一】：请选择2张牌和一名角色；"
                "该角色下个出牌阶段使用【杀】的次数上限+1"
            ),
        )

    def validate(
        self, engine: GameEngine, action: ActiveSkillAction,
        cards: tuple, targets: tuple[Player, ...],
    ) -> bool:
        current = self.create_action(engine, action.controller)
        if current is None:
            return False
        return bool(
            len(cards) == 2
            and len({card.id for card in cards}) == 2
            and all(card in current.legal_cards for card in cards)
            and len(targets) == 1
            and targets[0] in current.legal_targets
        )

    def resolve(
        self, engine: GameEngine, action: ActiveSkillAction,
        cards: tuple, targets: tuple[Player, ...],
    ) -> SkillResolutionResult:
        if not self.validate(engine, action, cards, targets):
            return SkillResolutionResult(
                self.definition, action.controller, applied=False
            )
        controller = action.controller
        target = targets[0]
        moves = []
        for card in cards:
            zone = "hand" if card in controller.hand else "equipment"
            move = engine.discard_from_zone(
                controller, card, zone, "小爷是一弃置"
            )
            if move is not None:
                moves.append(move)
        if len(moves) != 2:
            return SkillResolutionResult(
                self.definition, controller, applied=False
            )
        target.pending_slash_use_bonus += 1
        controller.skill_usage_counts[self.definition.skill_id] = (
            controller.skill_usage_counts.get(self.definition.skill_id, 0) + 1
        )
        return SkillResolutionResult(
            skill=self.definition,
            controller=controller,
            applied=True,
            move_events=tuple(moves),
            messages=(
                f"{controller.general.name} 发动【小爷是一】，令"
                f"{target.general.name} 下个出牌阶段使用【杀】"
                "的次数上限+1",
            ),
        )

    def ai_decide(
        self, engine: GameEngine, action: ActiveSkillAction
    ) -> ActiveSkillAIDecision | None:
        controller = action.controller
        # 无明确用户策略时采用保守收尾策略：每回合至多主动选择一次。
        if controller.skill_usage_counts.get(self.definition.skill_id, 0):
            return None
        from src.ai import choose_low_value_cards

        cards = tuple(
            choose_low_value_cards(
                engine, controller, list(action.legal_cards), 2
            )
        )
        if len(cards) != 2:
            return None
        friendly = [
            target for target in action.legal_targets
            if not engine.are_enemies(controller, target)
        ]
        if not friendly:
            return None
        target = max(
            friendly,
            key=lambda player: (
                player.seat == controller.seat,
                len(player.hand),
                -player.seat,
            ),
        )
        remaining = [
            card for card in controller.hand if card not in cards
        ]
        slash_count = sum(
            card.name in ("杀", "火杀", "雷杀") for card in remaining
        )
        if target is controller and slash_count < 2:
            return None
        return ActiveSkillAIDecision(
            action=action,
            cards=cards,
            targets=(target,),
        )


XIAOYE_SHIYI_HANDLER = XiaoyeShiyiHandler()
