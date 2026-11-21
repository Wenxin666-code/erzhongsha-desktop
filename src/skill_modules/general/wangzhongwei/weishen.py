"""王钟伟【伟神】。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models import (
    Phase, Player, SkillDefinition, SkillKind, SkillSourceType, SkillTiming,
)
from src.skill_modules.base import (
    ActiveSkillAction, ActiveSkillAIDecision, SkillResolutionRequest,
    SkillResolutionResult,
)

if TYPE_CHECKING:
    from src.engine import GameEngine


WEISHEN_DEFINITION = SkillDefinition(
    skill_id="general.wangzhongwei.weishen",
    name="伟神",
    source_type=SkillSourceType.GENERAL,
    source_name="伟神",
    kind=SkillKind.ACTIVE,
    timings=(SkillTiming.ACTIVE_PLAY,),
    mandatory=False,
    description=(
        "出牌阶段限1次，你可以令一名攻击范围内的角色选择一项："
        "1.打出一张【闪】；2.你获得其1张手牌或装备牌。"
    ),
)


class WeishenHandler:
    definition = WEISHEN_DEFINITION

    def create_action(
        self, engine: GameEngine, controller: Player
    ) -> ActiveSkillAction | None:
        if (
            not controller.alive
            or engine.state.phase != Phase.PLAY
            or engine.get_current_player().seat != controller.seat
            or controller.skill_usage_counts.get(
                self.definition.skill_id, 0
            ) >= 1
        ):
            return None
        targets = tuple(
            player for player in engine.get_alive_players()
            if player.seat != controller.seat
            and engine.in_attack_range(controller, player)
        )
        if not targets:
            return None
        return ActiveSkillAction(
            skill=self.definition,
            controller=controller,
            legal_cards=(),
            required_cards=0,
            legal_targets=targets,
            required_targets=1,
            prompt="【伟神】：请选择一名攻击范围内的角色",
            ai_priority=10,
        )

    def validate(
        self, engine: GameEngine, action: ActiveSkillAction,
        cards: tuple, targets: tuple[Player, ...],
    ) -> bool:
        current = self.create_action(engine, action.controller)
        return bool(
            current is not None
            and not cards
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
        controller.skill_usage_counts[self.definition.skill_id] = 1
        return SkillResolutionResult(
            skill=self.definition,
            controller=controller,
            applied=True,
            messages=(
                f"{controller.general.name} 对"
                f"{target.general.name} 发动【伟神】",
            ),
            request=SkillResolutionRequest(
                kind="jink_or_gain",
                prompt=(
                    f"{target.general.name}：请选择一张【闪】打出；"
                    f"取消则由{controller.general.name}获得你的一张"
                    "手牌或装备牌"
                ),
                source_player=controller,
                legal_targets=(target,),
                optional=False,
            ),
        )

    def ai_decide(
        self, engine: GameEngine, action: ActiveSkillAction
    ) -> ActiveSkillAIDecision | None:
        controller = action.controller
        candidates = [
            target for target in action.legal_targets
            if engine.are_enemies(controller, target)
            and (target.hand or target.equipment)
        ]
        if not candidates:
            return None
        # 只读取体力、手牌数、座次等公开状态，禁止查看敌方手牌牌面。
        from src.ai import choose_attack_target, choose_slash_plan

        slash_plan = choose_slash_plan(engine, controller)
        target = (
            slash_plan.targets[0]
            if (
                slash_plan is not None
                and slash_plan.targets
                and slash_plan.targets[0] in candidates
            )
            else choose_attack_target(engine, controller, candidates)
        )
        if target is None:
            return None
        return ActiveSkillAIDecision(
            action=action,
            cards=(),
            targets=(target,),
        )


WEISHEN_HANDLER = WeishenHandler()
