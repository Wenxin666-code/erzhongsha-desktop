"""张艺严【尔我同心】。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models import (
    DamageEvent, DamageNature, DyingEvent, Player, SkillDefinition,
    SkillKind, SkillSourceType, SkillTiming,
)
from src.skill_modules.base import (
    SkillResolutionRequest, SkillResolutionResult, TriggeredSkillAction,
)

if TYPE_CHECKING:
    from src.engine import GameEngine


ERWO_TONGXIN_DEFINITION = SkillDefinition(
    skill_id="general.zhangyiyan.erwo_tongxin",
    name="尔我同心",
    source_type=SkillSourceType.GENERAL,
    source_name="尔我同心",
    kind=SkillKind.LOCKED,
    timings=(
        SkillTiming.AFTER_ANY_DAMAGE,
        SkillTiming.ENTER_DYING,
    ),
    mandatory=True,
    description=(
        "锁定技，一名角色受到1点伤害后，你摸1张牌；"
        "其他角色进入濒死状态时，若你的体力大于1，你受到1点伤害。"
    ),
)


class ErwoTongxinHandler:
    definition = ERWO_TONGXIN_DEFINITION

    def can_trigger(
        self, engine: GameEngine, controller: Player, event: object
    ) -> bool:
        if not controller.alive:
            return False
        if isinstance(event, DamageEvent):
            return event.amount > 0
        return bool(
            isinstance(event, DyingEvent)
            and event.target.alive
            and event.target.seat != controller.seat
            and controller.hp > 1
        )

    def create_action(
        self, engine: GameEngine, controller: Player, event: object
    ) -> TriggeredSkillAction:
        if isinstance(event, DamageEvent):
            prompt = (
                f"一名角色受到{event.amount}点伤害后，"
                f"{controller.general.name} 的【尔我同心】生效"
            )
        else:
            prompt = (
                f"{event.target.general.name} 进入濒死，"
                f"{controller.general.name} 的【尔我同心】生效"
            )
        return TriggeredSkillAction(
            skill=self.definition,
            controller=controller,
            event=event,
            prompt=prompt,
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
        if isinstance(event, DamageEvent):
            moves = engine.draw_to_hand(
                controller, event.amount, reason="尔我同心摸牌"
            )
            return SkillResolutionResult(
                skill=self.definition,
                controller=controller,
                applied=True,
                move_events=tuple(moves),
                messages=(
                    f"{controller.general.name} 的【尔我同心】生效，"
                    f"摸{len(moves)}张牌",
                ),
            )

        original_damage = event.damage_event
        inherited_source = (
            original_damage.source_player
            if original_damage is not None else None
        )
        damage_event = DamageEvent(
            amount=1,
            nature=DamageNature.NORMAL,
            source_player=inherited_source,
        )
        return SkillResolutionResult(
            skill=self.definition,
            controller=controller,
            applied=True,
            messages=(
                f"{event.target.general.name} 进入濒死，"
                f"{controller.general.name} 的【尔我同心】生效",
            ),
            request=SkillResolutionRequest(
                kind="damage",
                prompt=f"{controller.general.name} 受到1点伤害",
                context=damage_event,
                legal_targets=(controller,),
                optional=False,
            ),
        )


ERWO_TONGXIN_HANDLER = ErwoTongxinHandler()
