"""丁逸晨【银河领主】。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models import (
    CardResponseEvent, DamageEvent, JudgmentEvent, Player,
    SkillDefinition, SkillKind, SkillSourceType, SkillTiming,
)
from src.skill_modules.base import (
    SkillAIContext, SkillResolutionRequest, SkillResolutionResult,
    TriggeredSkillAction,
)

if TYPE_CHECKING:
    from src.engine import GameEngine


YINHE_LORD_DEFINITION = SkillDefinition(
    skill_id="general.yinhe_lord",
    name="银河领主",
    source_type=SkillSourceType.GENERAL,
    source_name="银河领主",
    kind=SkillKind.TRIGGERED,
    timings=(
        SkillTiming.AFTER_CARD_RESPONSE,
        SkillTiming.AFTER_DAMAGE,
    ),
    mandatory=False,
    description=(
        "你的回合外，当你打出【闪】或受到伤害后，你可以进行判定。"
        "若判定结果为黑桃，你可以令一名角色失去2点体力。"
    ),
)


class YinheLordHandler:
    definition = YINHE_LORD_DEFINITION

    def can_trigger(
        self, engine: GameEngine, controller: Player, event: object
    ) -> bool:
        if (
            not controller.alive
            or engine.get_current_player().seat == controller.seat
        ):
            return False
        if isinstance(event, DamageEvent):
            return event.amount > 0
        return bool(
            isinstance(event, CardResponseEvent)
            and event.player.seat == controller.seat
            and event.effective_card.name == "闪"
            and event.action == "打出"
        )

    def create_action(
        self, engine: GameEngine, controller: Player, event: object
    ) -> TriggeredSkillAction:
        cause = "打出【闪】" if isinstance(event, CardResponseEvent) else "受到伤害"
        return TriggeredSkillAction(
            skill=self.definition,
            controller=controller,
            event=event,
            prompt=(
                f"{controller.general.name} 在回合外{cause}，"
                f"是否发动【{self.definition.name}】？"
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
        if not self.can_trigger(engine, action.controller, action.event):
            return SkillResolutionResult(
                self.definition, action.controller, applied=False
            )
        return SkillResolutionResult(
            skill=self.definition,
            controller=action.controller,
            applied=True,
            messages=(
                f"{action.controller.general.name} 发动【银河领主】，进行判定",
            ),
            request=SkillResolutionRequest(
                kind="judgment",
                prompt="【银河领主】判定中",
                context="yinhe_judgment",
                judging_player=action.controller,
                judgment_reason=self.definition.name,
                judgment_rule="spade",
                source_player=action.controller,
            ),
        )

    def continue_resolution(
        self, engine: GameEngine, action: TriggeredSkillAction,
        request: SkillResolutionRequest, choice,
    ) -> SkillResolutionResult:
        if request.context == "yinhe_judgment":
            judgment = choice
            if not isinstance(judgment, JudgmentEvent) or not judgment.result:
                return SkillResolutionResult(
                    self.definition, action.controller, applied=True,
                    messages=("【银河领主】判定结果不是黑桃",),
                    announce=False,
                )
            targets = tuple(player for player in engine.state.players if player.alive)
            return SkillResolutionResult(
                self.definition,
                action.controller,
                applied=True,
                request=SkillResolutionRequest(
                    kind="choose_target",
                    prompt="【银河领主】：请选择一名角色失去2点体力",
                    context="yinhe_target",
                    legal_targets=targets,
                    optional=True,
                ),
                announce=False,
            )
        if request.context == "yinhe_target":
            target = choice
            if target not in request.legal_targets or not target.alive:
                return SkillResolutionResult(
                    self.definition, action.controller, applied=True,
                    messages=(
                        f"{action.controller.general.name} 未指定【银河领主】目标",
                    ),
                    announce=False,
                )
            hp_loss = engine.lose_hp(
                target,
                2,
                reason="银河领主",
                source_skill_id=self.definition.skill_id,
            )
            if hp_loss is None:
                return SkillResolutionResult(
                    self.definition, action.controller, applied=False,
                    announce=False,
                )
            return SkillResolutionResult(
                self.definition,
                action.controller,
                applied=True,
                hp_loss_events=(hp_loss,),
                messages=(
                    f"{action.controller.general.name} 令"
                    f"{target.general.name} 失去2点体力",
                ),
                announce=False,
            )
        return SkillResolutionResult(
            self.definition, action.controller, applied=False, announce=False
        )

    def ai_choose_target(
        self, engine: GameEngine, action: TriggeredSkillAction,
        request: SkillResolutionRequest,
    ) -> Player | None:
        enemies = [
            target for target in request.legal_targets
            if engine.are_enemies(action.controller, target)
        ]
        if not enemies:
            return None
        return min(
            enemies,
            key=lambda target: (target.hp > 2, target.hp, len(target.hand), target.seat),
        )


YINHE_LORD_HANDLER = YinheLordHandler()
