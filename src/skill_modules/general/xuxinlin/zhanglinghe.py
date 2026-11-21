"""徐欣琳【张凌赫】。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models import (
    ActiveCardUseEvent, Card, CardKind, Phase, Player, SkillDefinition,
    SkillKind, SkillSourceType, SkillTiming,
)
from src.skill_modules.base import (
    SkillAIContext, SkillResolutionResult, TriggeredSkillAction,
    build_converted_card,
)

if TYPE_CHECKING:
    from src.engine import GameEngine


ZHANGLINGHE_DEFINITION = SkillDefinition(
    skill_id="general.xuxinlin.zhanglinghe",
    name="张凌赫",
    source_type=SkillSourceType.GENERAL,
    source_name="张凌赫",
    kind=SkillKind.CONVERSION,
    timings=(
        SkillTiming.PLAY_CONVERSION,
        SkillTiming.AFTER_CARD_RESOLUTION,
    ),
    mandatory=False,
    description=(
        "你可以将一张装备牌或黑色手牌当作【过河拆桥】使用。"
        "若使用的是黑色装备牌，此牌结算后，你可以摸1张牌。"
    ),
)


class ZhanglingheHandler:
    definition = ZHANGLINGHE_DEFINITION
    effective_card_name = "过河拆桥"
    required_cards = 1
    entry_type = "general_skill"
    fixed_materials = False

    @staticmethod
    def candidates(
        player: Player, skill_is_effective: bool
    ) -> list[Card]:
        if not skill_is_effective:
            return []
        hand = [
            card for card in player.hand
            if card.kind == CardKind.EQUIPMENT or card.color == "black"
        ]
        return hand + list(player.equipment)

    def validate(
        self, player: Player, cards: list[Card],
        skill_is_effective: bool,
    ) -> bool:
        return bool(
            len(cards) == 1
            and cards[0] in self.candidates(
                player, skill_is_effective
            )
        )

    def can_activate(
        self, engine: GameEngine, player: Player
    ) -> bool:
        return bool(
            player.alive
            and engine.state.phase == Phase.PLAY
            and engine.get_current_player().seat == player.seat
            and self.candidates(player, True)
        )

    @staticmethod
    def build_effective_card(cards: list[Card]) -> Card:
        return build_converted_card("过河拆桥", cards)

    @staticmethod
    def _material_cost(
        engine: GameEngine, player: Player, card: Card
    ) -> int:
        from src.ai import card_keep_value

        cost = card_keep_value(engine, player, card)
        if card in player.equipment:
            cost += {
                "armor": 48,
                "weapon": 34,
                "offensive_mount": 28,
                "defensive_mount": 32,
            }.get(card.equipment_type, 25)
        if card.kind == CardKind.EQUIPMENT and card.color == "black":
            # 结算后的补牌显著降低材料净成本，但不能抹去失去场上装备的代价。
            cost -= 38
        return max(1, cost)

    def ai_choose_cards(
        self, engine: GameEngine, player: Player,
        candidates: list[Card], context: SkillAIContext,
    ) -> list[Card]:
        from src.ai import choose_control_target

        target = choose_control_target(
            engine, player, context.legal_targets
        )
        if target is None:
            return []
        card = min(
            candidates,
            key=lambda candidate: (
                self._material_cost(engine, player, candidate),
                candidate.id,
            ),
            default=None,
        )
        if card is None:
            return []

        # 装备区、判定区是公开且通常更值得拆除的目标；只拆未知手牌时更保守。
        benefit = 76 if (
            target.equipment or target.judgment_area
        ) else 46
        used = player.play_phase_card_use_counts.get(
            "过河拆桥", 0
        )
        if used == 3:
            # 本次能兑现【肾肾】下个摸牌阶段的额外一牌。
            benefit += 42
        if any(card.suit == "club" for card in target.equipment):
            # 与【绿妃】的公开梅花装备联动；不读取敌方隐藏手牌牌面。
            benefit += 28
        return (
            [card]
            if self._material_cost(engine, player, card) <= benefit
            else []
        )

    @staticmethod
    def ai_choose_target(
        engine: GameEngine, player: Player,
        legal_targets: list[Player], context: SkillAIContext,
    ) -> Player | None:
        from src.ai import choose_control_target

        return choose_control_target(engine, player, legal_targets)

    @staticmethod
    def _is_black_equipment_material(
        event: ActiveCardUseEvent
    ) -> bool:
        return bool(
            event.skill_id == ZHANGLINGHE_DEFINITION.skill_id
            and event.effective_card.name == "过河拆桥"
            and len(event.physical_cards) == 1
            and event.physical_cards[0].kind == CardKind.EQUIPMENT
            and event.physical_cards[0].color == "black"
        )

    def can_trigger(
        self, engine: GameEngine, controller: Player, event: object
    ) -> bool:
        return bool(
            controller.alive
            and isinstance(event, ActiveCardUseEvent)
            and event.player.seat == controller.seat
            and self._is_black_equipment_material(event)
        )

    def create_action(
        self, engine: GameEngine, controller: Player,
        event: ActiveCardUseEvent,
    ) -> TriggeredSkillAction:
        return TriggeredSkillAction(
            skill=self.definition,
            controller=controller,
            event=event,
            prompt=(
                "【张凌赫】使用的黑色装备牌已结算，"
                "是否发动技能摸1张牌？"
            ),
        )

    def resolve(
        self, engine: GameEngine, action: TriggeredSkillAction
    ) -> SkillResolutionResult:
        if not self.can_trigger(
            engine, action.controller, action.event
        ):
            return SkillResolutionResult(
                self.definition, action.controller, applied=False
            )
        moves = engine.draw_to_hand(
            action.controller, 1, reason="张凌赫摸牌"
        )
        return SkillResolutionResult(
            skill=self.definition,
            controller=action.controller,
            applied=bool(moves),
            move_events=tuple(moves),
            messages=(
                f"{action.controller.general.name} 发动【张凌赫】，"
                "摸1张牌",
            ),
        )

    def ai_should_activate(
        self, engine: GameEngine, action: TriggeredSkillAction,
        context: SkillAIContext,
    ) -> bool:
        return self.can_trigger(
            engine, action.controller, action.event
        )


ZHANGLINGHE_HANDLER = ZhanglingheHandler()
