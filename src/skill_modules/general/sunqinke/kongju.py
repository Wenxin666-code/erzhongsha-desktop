"""孙沁珂【控局】。"""

from __future__ import annotations

from src.models import (
    Card, Player, SkillDefinition, SkillKind, SkillSourceType, SkillTiming,
)


KONGJU_DEFINITION = SkillDefinition(
    skill_id="general.sunqinke.kongju",
    name="控局",
    source_type=SkillSourceType.GENERAL,
    source_name="控局",
    kind=SkillKind.LOCKED,
    timings=(SkillTiming.EFFECT_VALIDITY,),
    mandatory=True,
    description=(
        "你不能成为【过河拆桥】、【顺手牵羊】和【乐不思蜀】的目标。"
    ),
)


class KongjuHandler:
    definition = KONGJU_DEFINITION
    prohibited_names = {"过河拆桥", "顺手牵羊", "乐不思蜀"}

    def prohibits_target(
        self, engine, controller: Player, source: Player,
        card: Card,
    ) -> bool:
        return bool(
            controller.alive
            and source.seat != controller.seat
            and card.name in self.prohibited_names
        )


KONGJU_HANDLER = KongjuHandler()
