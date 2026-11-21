"""通用触发技动作与结算结果。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from src.models import (
    Card, CardKind, CardMoveEvent, CardRevealEvent, HpLossEvent,
    JudgmentEvent, Player, SkillDefinition,
)


def owned_cards(player: Player) -> list[Card]:
    """“你的牌”的公共区域语义：手牌区与装备区中的实体牌。"""
    return player.hand + player.equipment


def _rank_value(card: Card) -> int:
    rank = str(card.rank)
    return {"A": 1, "J": 11, "Q": 12, "K": 13}.get(
        rank, int(rank) if rank.isdigit() else 0
    )


def _effective_kind(card_name: str, fallback: CardKind) -> CardKind:
    if card_name in ("杀", "火杀", "雷杀", "闪", "桃", "酒"):
        return CardKind.BASIC
    if card_name in (
        "无中生有", "桃园结义", "五谷丰登", "南蛮入侵",
        "万箭齐发", "万剑齐发", "火攻", "决斗", "过河拆桥",
        "顺手牵羊", "借刀杀人", "铁索连环", "乐不思蜀",
        "兵粮寸断", "闪电", "无懈可击",
    ):
        return CardKind.TRICK
    return fallback


def build_converted_card(
    effective_card_name: str, physical_cards: list[Card]
) -> Card:
    """按官方规则由一张或多张实体牌构造转化后的有效牌面。"""
    if not physical_cards:
        raise ValueError("转化牌必须保存至少一张实体组成牌")
    first = physical_cards[0]
    update = {
        "name": effective_card_name,
        "kind": _effective_kind(effective_card_name, first.kind),
    }
    if len(physical_cards) == 1:
        return first.model_copy(update=update)

    colors = [card.color for card in physical_cards]
    effective_color = (
        colors[0]
        if colors[0] in ("red", "black")
        and all(color == colors[0] for color in colors)
        else "colorless"
    )
    point = min(
        13,
        max(1, sum(_rank_value(card) for card in physical_cards)),
    )
    rank = {1: "A", 11: "J", 12: "Q", 13: "K"}.get(
        point, str(point)
    )
    return first.model_copy(update={
        **update,
        "suit": "no_suit",
        "rank": rank,
        "color_override": effective_color,
    })


@dataclass(frozen=True)
class TriggeredSkillAction:
    """一次已满足触发条件、等待角色决定是否发动的技能动作。"""

    skill: SkillDefinition
    controller: Player
    event: Any
    prompt: str


@dataclass(frozen=True)
class ActiveSkillAction:
    """出牌阶段一次待提交的主动技能合法动作。"""

    skill: SkillDefinition
    controller: Player
    legal_cards: tuple[Card, ...]
    required_cards: int
    legal_targets: tuple[Player, ...]
    required_targets: int
    prompt: str
    # AI出牌阶段的通用调度优先级；数值越小越早尝试。
    ai_priority: int = 100


@dataclass(frozen=True)
class ActiveSkillAIDecision:
    """AI对通用主动技能动作选择的牌与目标。"""

    action: ActiveSkillAction
    cards: tuple[Card, ...]
    targets: tuple[Player, ...]


@dataclass(frozen=True)
class SkillResolutionRequest:
    """技能后续需要的通用选择；界面只按 kind 展示，不识别技能名。"""

    kind: str
    prompt: str
    context: Any = None
    judging_player: Optional[Player] = None
    judgment_reason: str = ""
    judgment_rule: str = ""
    source_player: Optional[Player] = None
    source_card: Optional[Card] = None
    legal_targets: tuple[Player, ...] = ()
    optional: bool = True


@dataclass(frozen=True)
class SkillResolutionResult:
    """技能规则层的结算结果；界面只消费消息、移动事件与表现。"""

    skill: SkillDefinition
    controller: Player
    applied: bool
    move_events: tuple[CardMoveEvent, ...] = ()
    reveal_events: tuple[CardRevealEvent, ...] = ()
    hp_loss_events: tuple[HpLossEvent, ...] = ()
    messages: tuple[str, ...] = ()
    request: Optional[SkillResolutionRequest] = None
    announce: bool = True


@dataclass(frozen=True)
class JudgmentReplacementAction:
    """判定牌生效前的一次合法替换机会。"""

    skill: SkillDefinition
    controller: Player
    event: JudgmentEvent
    candidates: tuple[Card, ...]
    prompt: str


@dataclass(frozen=True)
class JudgmentReplacementResult:
    """一次替换后的同一判定事件及其公开移动。"""

    action: JudgmentReplacementAction
    event: JudgmentEvent
    applied: bool
    move_events: tuple[CardMoveEvent, ...] = ()
    messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillAIContext:
    """技能AI只读取规则上下文，不接触界面控件或动画状态。"""

    window: str
    event: Any = None
    required_card_name: Optional[str] = None
    source_player: Optional[Player] = None
    legal_targets: tuple[Player, ...] = ()


@dataclass(frozen=True)
class SkillAIConversionDecision:
    """AI为一次牌转化选择的规则材料和目标。"""

    option: Any
    cards: tuple[Card, ...]
    target: Optional[Player] = None
