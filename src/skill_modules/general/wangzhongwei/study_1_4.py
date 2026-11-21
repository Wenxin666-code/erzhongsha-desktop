"""王钟伟【1：4学习法】。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models import (
    DrawPhaseEvent, Player, SkillDefinition, SkillKind, SkillSourceType,
    SkillTiming,
)
from src.skill_modules.base import (
    SkillAIContext, SkillResolutionResult, TriggeredSkillAction,
)

if TYPE_CHECKING:
    from src.engine import GameEngine


STUDY_1_4_DEFINITION = SkillDefinition(
    skill_id="general.wangzhongwei.study_1_4",
    name="1：4学习法",
    source_type=SkillSourceType.GENERAL,
    source_name="1：4学习法",
    kind=SkillKind.TRIGGERED,
    timings=(SkillTiming.DRAW_PHASE,),
    mandatory=False,
    description=(
        "摸牌阶段，你可以少摸1张牌，令你本回合使用的【杀】"
        "伤害为4点；否则，你本回合使用的【杀】伤害为2点。"
    ),
)


class Study14Handler:
    definition = STUDY_1_4_DEFINITION

    def prepare_draw_phase(
        self, engine: GameEngine, controller: Player, event: DrawPhaseEvent
    ) -> None:
        """进入摸牌阶段即声明“不少摸”分支的默认效果。"""
        if event.player.seat != controller.seat:
            return
        event.draw_count = event.base_draw_count
        controller.draw_phase_card_count = event.draw_count
        controller.turn_slash_base_damage = 2

    def can_trigger(
        self, engine: GameEngine, controller: Player, event: object
    ) -> bool:
        return bool(
            controller.alive
            and isinstance(event, DrawPhaseEvent)
            and event.player.seat == controller.seat
            and event.draw_count > 0
        )

    def create_action(
        self, engine: GameEngine, controller: Player, event: DrawPhaseEvent
    ) -> TriggeredSkillAction:
        return TriggeredSkillAction(
            skill=self.definition,
            controller=controller,
            event=event,
            prompt=(
                "是否发动【1：4学习法】少摸1张牌？"
                "若发动，本回合使用的【杀】伤害为4点；"
                "否则为2点"
            ),
        )

    def resolve(
        self, engine: GameEngine, action: TriggeredSkillAction
    ) -> SkillResolutionResult:
        controller = action.controller
        event = action.event
        if not self.can_trigger(engine, controller, event):
            return SkillResolutionResult(
                self.definition, controller, applied=False
            )
        event.draw_count = max(0, event.base_draw_count - 1)
        controller.draw_phase_card_count = event.draw_count
        controller.turn_slash_base_damage = 4
        return SkillResolutionResult(
            skill=self.definition,
            controller=controller,
            applied=True,
            messages=(
                f"{controller.general.name} 发动【1：4学习法】，"
                f"本阶段摸{event.draw_count}张牌，本回合使用的"
                "【杀】伤害为4点",
            ),
        )

    def ai_should_activate(
        self, engine: GameEngine, action: TriggeredSkillAction,
        context: SkillAIContext,
    ) -> bool:
        """用户指定策略：有实体【杀】少摸，否则正常摸牌。"""
        return any(
            card.name in ("杀", "火杀", "雷杀")
            for card in action.controller.hand
        )


STUDY_1_4_HANDLER = Study14Handler()
