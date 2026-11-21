"""关羽【武圣】。"""

from __future__ import annotations

from src.models import (
    Card, Player, SkillDefinition, SkillKind, SkillSourceType, SkillTiming,
)
from src.skill_modules.base import (
    SkillAIContext, build_converted_card, owned_cards,
)
from src.ai import card_keep_value


WUSHENG_DEFINITION = SkillDefinition(
    skill_id="general.wusheng",
    name="武圣",
    source_type=SkillSourceType.GENERAL,
    source_name="武圣",
    kind=SkillKind.ACTIVE,
    timings=(
        SkillTiming.SLASH_CONVERSION,
        SkillTiming.RESPONSE_CONVERSION,
    ),
    mandatory=False,
    description="你可以将一张红色牌当【杀】使用或打出。",
)


class WushengHandler:
    """提供武圣在使用与打出窗口共用的牌转化规则。"""

    definition = WUSHENG_DEFINITION
    effective_card_name = "杀"
    required_cards = 1
    entry_type = "general_skill"

    def candidates(
        self, player: Player, skill_is_effective: bool
    ) -> list[Card]:
        if not skill_is_effective:
            return []
        return [
            card for card in owned_cards(player)
            if card.suit in ("heart", "diamond")
        ]

    def validate(
        self, player: Player, cards: list[Card],
        skill_is_effective: bool,
    ) -> bool:
        return bool(
            skill_is_effective
            and len(cards) == self.required_cards
            and cards[0].suit in ("heart", "diamond")
            and cards[0] in owned_cards(player)
        )

    def build_effective_card(self, cards: list[Card]) -> Card:
        return build_converted_card(self.effective_card_name, cards)

    def ai_choose_cards(
        self, engine, player: Player, candidates: list[Card],
        context: SkillAIContext,
    ) -> list[Card]:
        """优先消耗低保留价值手牌，最后才考虑已装备的牌。"""
        ordered = sorted(
            candidates,
            key=lambda card: (
                1 if card in player.equipment else 0,
                card_keep_value(engine, player, card),
                card.id,
            ),
        )
        return ordered[:self.required_cards]

    def ai_choose_target(
        self, engine, player: Player, targets: list[Player],
        context: SkillAIContext,
    ) -> Player | None:
        """优先攻击低体力、低手牌的合法敌方目标。"""
        if not targets:
            return None
        return min(targets, key=lambda target: (target.hp, len(target.hand), target.seat))


WUSHENG_HANDLER = WushengHandler()
