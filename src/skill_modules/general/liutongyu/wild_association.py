"""刘桐羽【瞎联想】。"""

from __future__ import annotations

from src.models import (
    Card, Phase, Player, SkillDefinition, SkillKind, SkillSourceType,
    SkillTiming,
)
from src.skill_modules.base import SkillAIContext, build_converted_card


WILD_ASSOCIATION_DEFINITION = SkillDefinition(
    skill_id="general.wild_association",
    name="瞎联想",
    source_type=SkillSourceType.GENERAL,
    source_name="瞎联想",
    kind=SkillKind.ACTIVE,
    timings=(SkillTiming.PLAY_CONVERSION,),
    mandatory=False,
    description="出牌阶段限3次，你可以将全部黑色手牌当【万箭齐发】使用。",
)


class WildAssociationHandler:
    definition = WILD_ASSOCIATION_DEFINITION
    effective_card_name = "万箭齐发"
    required_cards = 0
    entry_type = "general_skill"
    phase_limit = 3
    fixed_materials = True

    @staticmethod
    def candidates(
        player: Player, skill_is_effective: bool
    ) -> list[Card]:
        if not skill_is_effective:
            return []
        return [card for card in player.hand if card.color == "black"]

    @staticmethod
    def required_count(player: Player, candidates: list[Card]) -> int:
        return len(candidates)

    def validate(
        self, player: Player, cards: list[Card],
        skill_is_effective: bool,
    ) -> bool:
        expected = self.candidates(player, skill_is_effective)
        return bool(
            expected
            and len(cards) == len(expected)
            and {card.id for card in cards} == {card.id for card in expected}
        )

    def can_activate(self, engine, player: Player) -> bool:
        return bool(
            player.alive
            and engine.state.phase == Phase.PLAY
            and engine.get_current_player().seat == player.seat
            and player.skill_usage_counts.get(
                self.definition.skill_id, 0
            ) < self.phase_limit
            and self.candidates(player, True)
        )

    def record_use(self, engine, player: Player) -> None:
        player.skill_usage_counts[self.definition.skill_id] = (
            player.skill_usage_counts.get(self.definition.skill_id, 0) + 1
        )

    def build_effective_card(self, cards: list[Card]) -> Card:
        return build_converted_card(self.effective_card_name, cards)

    def ai_choose_cards(
        self, engine, player: Player, candidates: list[Card],
        context: SkillAIContext,
    ) -> list[Card]:
        return list(candidates)


WILD_ASSOCIATION_HANDLER = WildAssociationHandler()
