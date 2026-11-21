"""普通牌、装备和公共选择共用的 AI 估值与轻量推演。"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Optional, TYPE_CHECKING

from src.models import Card, CardKind, Player

if TYPE_CHECKING:
    from src.engine import GameEngine


SLASH_NAMES = ("杀", "火杀", "雷杀")
_CURRENT_WEAPON = object()

BASE_KEEP_VALUES = {
    "桃": 100,
    "无懈可击": 90,
    "闪": 75,
    "无中生有": 72,
    "顺手牵羊": 68,
    "酒": 62,
    "过河拆桥": 60,
    "火攻": 56,
    "杀": 50,
    "火杀": 55,
    "雷杀": 53,
    "决斗": 50,
    "南蛮入侵": 48,
    "万箭齐发": 48,
    "万剑齐发": 48,
    "借刀杀人": 46,
    "乐不思蜀": 45,
    "兵粮寸断": 45,
    "铁索连环": 40,
    "五谷丰登": 38,
    "桃园结义": 36,
    "闪电": 30,
}


@dataclass(frozen=True)
class SlashPlan:
    card: Card
    targets: tuple[Player, ...]
    effective_name: str


@dataclass(frozen=True)
class ZhangbaPlan:
    cards: tuple[Card, Card]
    target: Player


@dataclass(frozen=True)
class BorrowedSwordPlan:
    wielder: Player
    victim: Player


def _equipped(player: Player, equipment_type: str) -> Optional[Card]:
    return next(
        (
            card for card in player.equipment
            if card.equipment_type == equipment_type
        ),
        None,
    )


def _weapon(player: Player) -> Optional[Card]:
    return _equipped(player, "weapon")


def _armor(player: Player) -> Optional[Card]:
    return _equipped(player, "armor")


def should_use_analeptic_for_slash(plan: SlashPlan) -> bool:
    """酒的额外伤害至少能作用于一个目标时才值得使用。"""
    return any(
        (armor := _armor(target)) is None
        or armor.name != "白银狮子"
        for target in plan.targets
    )


def should_use_peach_for_dying(
    engine: GameEngine, helper: Player, dying_target: Player
) -> bool:
    """默认只救自己或友方；敌方即使持有桃也放弃响应。"""
    return (
        helper.seat == dying_target.seat
        or not engine.are_enemies(helper, dying_target)
    )


def _enemies(engine: GameEngine, player: Player) -> list[Player]:
    return [
        target for target in engine.get_alive_players()
        if engine.are_enemies(player, target)
    ]


def _allies(engine: GameEngine, player: Player) -> list[Player]:
    return [
        target for target in engine.get_alive_players()
        if not engine.are_enemies(player, target)
    ]


def _target_priority(target: Player) -> tuple[int, int, int]:
    """越小越值得优先攻击。"""
    return target.hp, len(target.hand), target.seat


def choose_attack_target(
    engine: GameEngine, player: Player, targets: Iterable[Player],
) -> Optional[Player]:
    """仅按公开状态选择与【杀】相同优先级的攻击目标。"""
    candidates = [
        target for target in targets
        if target.alive and engine.are_enemies(player, target)
    ]
    return min(candidates, key=_target_priority) if candidates else None


def _range_with_weapon(engine: GameEngine, weapon: Optional[Card]) -> int:
    return engine.skills.attack_range_for_weapon(weapon)


def _distance_with_equipment(
    engine: GameEngine, source: Player, target: Player,
    equipment: Optional[Card] = None,
) -> int:
    distance = engine.distance(source, target)
    if (
        equipment is not None
        and equipment.equipment_type == "offensive_mount"
        and _equipped(source, "offensive_mount") is None
    ):
        distance = max(1, distance - 1)
    return distance


def _target_in_range_with_weapon(
    engine: GameEngine, source: Player, target: Player,
    weapon: Optional[Card],
) -> bool:
    return (
        target.alive
        and engine.are_enemies(source, target)
        and engine.distance(source, target)
        <= _range_with_weapon(engine, weapon)
    )


def _slash_effective_against(
    engine: GameEngine, source: Player, target: Player,
    effective_card: Card, weapon=_CURRENT_WEAPON,
) -> bool:
    weapon = _weapon(source) if weapon is _CURRENT_WEAPON else weapon
    if weapon is not None and weapon.name == "青釭剑":
        return True
    armor = _armor(target)
    if armor is None:
        return True
    if armor.name == "仁王盾" and effective_card.color == "black":
        return False
    if armor.name == "藤甲" and effective_card.name == "杀":
        return False
    return True


def _fire_chain_benefit(
    engine: GameEngine, source: Player, target: Player,
) -> int:
    """只估计本次火焰伤害的直接防具收益与铁索净收益。"""
    score = 45 if (_armor(target) and _armor(target).name == "藤甲") else 0
    if not target.chained:
        return score
    for chained in engine.get_alive_players():
        if chained is target or not chained.chained:
            continue
        score += 18 if engine.are_enemies(source, chained) else -25
    return score


def should_convert_zhuque(
    engine: GameEngine, source: Player, card: Card, target: Player,
    weapon=_CURRENT_WEAPON,
) -> bool:
    """朱雀羽扇只在火焰属性有正净收益时发动。"""
    weapon = _weapon(source) if weapon is _CURRENT_WEAPON else weapon
    return bool(
        card.name == "杀"
        and weapon is not None
        and weapon.name == "朱雀羽扇"
        and _fire_chain_benefit(engine, source, target) > 0
    )


def _effective_slash(
    engine: GameEngine, source: Player, card: Card, target: Player,
    weapon=_CURRENT_WEAPON,
) -> tuple[str, Card]:
    if should_convert_zhuque(engine, source, card, target, weapon):
        return "火杀", card.model_copy(update={"name": "火杀"})
    return card.name, card


def viable_slash_targets(
    engine: GameEngine, source: Player, effective_card: Card,
    targets: Iterable[Player], weapon=_CURRENT_WEAPON,
    excluded_cards: Iterable[Card] = (),
) -> list[Player]:
    if weapon is _CURRENT_WEAPON:
        weapon = _weapon(source)
        if weapon in tuple(excluded_cards):
            weapon = None
    return [
        target for target in targets
        if engine.are_enemies(source, target)
        and _slash_effective_against(
            engine, source, target, effective_card, weapon
        )
    ]


def choose_slash_plan(
    engine: GameEngine, player: Player,
    cards: Optional[Iterable[Card]] = None,
) -> Optional[SlashPlan]:
    """在所有实体杀与合法目标之间选择一项有效行动。"""
    weapon = _weapon(player)
    candidates = [
        card for card in (cards if cards is not None else player.hand)
        if card in player.hand and card.name in SLASH_NAMES
    ]
    plans = []
    for card in candidates:
        legal_targets = engine.get_legal_play_targets(
            player, card, (card,)
        )
        for target in legal_targets:
            if not engine.are_enemies(player, target):
                continue
            effective_name, effective_card = _effective_slash(
                engine, player, card, target, weapon
            )
            if not _slash_effective_against(
                engine, player, target, effective_card, weapon
            ):
                continue
            fire_bonus = (
                _fire_chain_benefit(engine, player, target)
                if effective_name == "火杀" else 0
            )
            plans.append((
                (
                    -target.hp,
                    -len(target.hand),
                    fire_bonus,
                    -card_keep_value(engine, player, card),
                    -target.seat,
                    card.id,
                ),
                card,
                target,
                effective_name,
                effective_card,
            ))
    if not plans:
        return None
    _, card, first_target, effective_name, effective_card = max(
        plans, key=lambda item: item[0]
    )
    targets = [first_target]
    if (
        len(player.hand) == 1
        and weapon is not None
        and weapon.name == "方天画戟"
    ):
        legal_targets = engine.get_legal_play_targets(
            player, card, (card,)
        )
        extra = viable_slash_targets(
            engine, player, effective_card, legal_targets, weapon
        )
        extra.sort(key=_target_priority)
        targets = extra[:3]
    return SlashPlan(card, tuple(targets), effective_name)


def _armor_score(
    engine: GameEngine, player: Player, armor: Card,
) -> int:
    enemies = _enemies(engine, player)
    enemy_has_fan = any(
        _weapon(enemy) is not None
        and _weapon(enemy).name == "朱雀羽扇"
        for enemy in enemies
    )
    adversity = (
        player.hp <= 2
        or len(player.hand) <= max(1, len(enemies))
    )
    if armor.name == "藤甲":
        if enemy_has_fan:
            return -50
        return 100 if adversity else 60
    if armor.name == "仁王盾":
        return 85
    if armor.name == "八卦阵":
        return 75
    if armor.name == "白银狮子":
        return 80 if player.hp < player.max_hp else 65
    return 55


def _weapon_tactical_score(
    engine: GameEngine, player: Player, weapon: Card,
    hand_after_equipping: list[Card],
) -> int:
    enemies = [
        target for target in _enemies(engine, player)
        if _target_in_range_with_weapon(engine, player, target, weapon)
    ]
    if not enemies:
        return 0

    slashes = [
        card for card in hand_after_equipping
        if card.name in SLASH_NAMES
    ]
    can_use = (
        engine.has_remaining_limited_slash_uses(player)
        or weapon.name == "诸葛连弩"
    )
    effective_slashes = [
        (card, target)
        for card in slashes
        for target in enemies
        if _slash_effective_against(
            engine,
            player,
            target,
            _effective_slash(
                engine, player, card, target, weapon
            )[1],
            weapon,
        )
    ] if can_use else []

    if weapon.name == "朱雀羽扇":
        if any(
            card.name == "杀"
            and should_convert_zhuque(
                engine, player, card, target, weapon
            )
            for card in slashes for target in enemies
        ):
            return 130
    if weapon.name == "贯石斧" and effective_slashes:
        if any(
            _armor(target) is not None
            and _armor(target).name != "藤甲"
            for _, target in effective_slashes
        ):
            return 112
    if weapon.name == "丈八蛇矛" and can_use and not slashes:
        for first, second in combinations(hand_after_equipping, 2):
            effective = engine.skills.build_effective_card(
                "杀", [first, second]
            )
            if any(
                _slash_effective_against(
                    engine, player, target, effective, weapon
                )
                for target in enemies
            ):
                return 118
    if weapon.name == "诸葛连弩" and effective_slashes:
        if len(slashes) >= 2 or player.slash_used:
            return 115 + min(20, len(slashes) * 5)
    if effective_slashes:
        return (
            55
            + min(20, len(slashes) * 4)
            + _range_with_weapon(engine, weapon)
        )
    return 0


def _offensive_mount_has_target(
    engine: GameEngine, player: Player, mount: Card,
) -> bool:
    weapon = _weapon(player)
    if not any(card.name in SLASH_NAMES for card in player.hand):
        return False
    if not engine.has_remaining_limited_slash_uses(player) and not (
        weapon is not None and weapon.name == "诸葛连弩"
    ):
        return False
    return any(
        _distance_with_equipment(engine, player, enemy, mount)
        <= engine.attack_range(player)
        for enemy in _enemies(engine, player)
    )


def _equipment_keep_value(
    engine: GameEngine, player: Player, card: Card,
    equipment_overrides: Optional[dict[str, Card]] = None,
) -> int:
    equipment_overrides = equipment_overrides or {}
    current = equipment_overrides.get(
        card.equipment_type,
        _equipped(player, card.equipment_type)
        if card.equipment_type else None,
    )
    if current is not None and current.name == card.name:
        return 18
    if card.equipment_type == "armor":
        score = _armor_score(engine, player, card)
        if current is None:
            return max(20, score)
        return 58 if score > _armor_score(engine, player, current) else 28
    if card.equipment_type == "weapon":
        candidate_score = _weapon_tactical_score(
            engine, player, card,
            [hand for hand in player.hand if hand is not card],
        )
        if current is None:
            return max(30, min(80, candidate_score))
        current_score = _weapon_tactical_score(
            engine, player, current, list(player.hand)
        )
        return 60 if candidate_score > current_score else 28
    if card.equipment_type in ("offensive_mount", "defensive_mount"):
        return 45 if current is None else 22
    return 25


def card_keep_value(
    engine: GameEngine, player: Player, card: Card,
    *, weapon_override=_CURRENT_WEAPON,
    equipment_overrides: Optional[dict[str, Card]] = None,
) -> int:
    """牌留在手中的相对价值；数值越低越适合弃置或作为代价。"""
    if card.kind == CardKind.EQUIPMENT:
        return _equipment_keep_value(
            engine, player, card, equipment_overrides
        )
    value = BASE_KEEP_VALUES.get(card.name, 20)
    if card.name in SLASH_NAMES:
        weapon = (
            _weapon(player)
            if weapon_override is _CURRENT_WEAPON
            else weapon_override
        )
        can_use = (
            engine.has_remaining_limited_slash_uses(player)
            or (
                weapon is not None
                and weapon.name == "诸葛连弩"
            )
        )
        if not can_use:
            value -= 22
        else:
            effective_targets = []
            for target in _enemies(engine, player):
                if not _target_in_range_with_weapon(
                    engine, player, target, weapon
                ):
                    continue
                _, effective = _effective_slash(
                    engine, player, card, target, weapon
                )
                if _slash_effective_against(
                    engine, player, target, effective, weapon
                ):
                    effective_targets.append(target)
            if not effective_targets:
                value -= 25
        if (
            weapon is not None and weapon.name == "诸葛连弩"
            and sum(
                hand.name in SLASH_NAMES for hand in player.hand
            ) >= 2
        ):
            value += 8
    return max(1, value)


def remaining_hand_value(
    engine: GameEngine, player: Player,
    cards: Optional[Iterable[Card]] = None,
    *, weapon_override=_CURRENT_WEAPON,
    equipment_overrides: Optional[dict[str, Card]] = None,
) -> int:
    return sum(
        card_keep_value(
            engine,
            player,
            card,
            weapon_override=weapon_override,
            equipment_overrides=equipment_overrides,
        )
        for card in (cards if cards is not None else player.hand)
    )


def choose_low_value_cards(
    engine: GameEngine, player: Player,
    cards: Iterable[Card], count: int,
) -> list[Card]:
    candidates = [card for card in cards if card in player.hand]
    candidates.sort(
        key=lambda card: (
            card_keep_value(engine, player, card),
            card.id,
        )
    )
    return candidates[:count]


def choose_zhangba_plan(
    engine: GameEngine, player: Player,
) -> Optional[ZhangbaPlan]:
    weapon = _weapon(player)
    if (
        weapon is None or weapon.name != "丈八蛇矛"
        or len(player.hand) < 2
        or not engine.can_use_slash(player)
    ):
        return None
    plans = []
    for pair in combinations(player.hand, 2):
        cards = list(pair)
        effective = engine.skills.build_effective_card("杀", cards)
        legal_targets = engine.get_legal_play_targets(
            player, effective, tuple(cards)
        )
        targets = viable_slash_targets(
            engine, player, effective, legal_targets, weapon
        )
        if not targets:
            continue
        target = min(targets, key=_target_priority)
        cost = sum(
            card_keep_value(engine, player, card) for card in pair
        )
        plans.append((
            (
                cost,
                target.hp,
                len(target.hand),
                target.seat,
                pair[0].id,
                pair[1].id,
            ),
            pair,
            target,
        ))
    if not plans:
        return None
    _, pair, target = min(plans, key=lambda item: item[0])
    return ZhangbaPlan(pair, target)


def choose_zhangba_response_cards(
    engine: GameEngine, player: Player,
) -> list[Card]:
    return choose_low_value_cards(
        engine, player, player.hand, 2
    )


def should_use_zhangba_response(
    engine: GameEngine, player: Player,
) -> bool:
    cards = choose_zhangba_response_cards(engine, player)
    if len(cards) != 2:
        return False
    direct = [
        card for card in player.hand if card.name in SLASH_NAMES
    ]
    if not direct:
        return True
    pair_cost = sum(
        card_keep_value(engine, player, card) for card in cards
    )
    direct_cost = min(
        card_keep_value(engine, player, card) for card in direct
    )
    return pair_cost < direct_cost


def _control_equipment_priority(card: Card) -> int:
    if card.equipment_type == "armor":
        return 0
    if card.equipment_type in ("offensive_mount", "defensive_mount"):
        return 1
    if card.equipment_type == "weapon":
        return 2
    if card.kind == CardKind.EQUIPMENT:
        return 3
    return 9


def choose_control_target(
    engine: GameEngine, player: Player,
    targets: Iterable[Player],
) -> Optional[Player]:
    candidates = [
        target for target in targets
        if target.alive and engine.are_enemies(player, target)
        and (target.hand or target.equipment or target.judgment_area)
    ]
    if not candidates:
        return None

    def target_key(target: Player):
        equipment_priority = min(
            (
                _control_equipment_priority(card)
                for card in target.equipment
            ),
            default=9,
        )
        fallback = 4 if target.hand else 5
        return (
            min(equipment_priority, fallback),
            target.hp,
            len(target.hand),
            target.seat,
        )

    return min(candidates, key=target_key)


def choose_control_card_choice(choices: Iterable[tuple]) -> Optional[tuple]:
    choices = list(choices)
    if not choices:
        return None

    def choice_key(choice):
        zone, index, card = choice
        if zone == "equipment":
            priority = _control_equipment_priority(card)
            stable_id = card.id
        elif zone == "hand":
            priority = 4
            # 手牌牌面属于隐藏信息：只能按其公开位置选择。
            stable_id = ""
        else:
            priority = 5
            stable_id = card.id
        return priority, index, stable_id

    return min(choices, key=choice_key)


def can_use_fire_attack(engine: GameEngine, player: Player) -> bool:
    """火攻离手后至少还须有一张手牌，才存在弃同花色牌的可能。"""
    return bool(
        len(player.hand) > 1
        and any(
            target.hand for target in _enemies(engine, player)
        )
    )


def choose_fire_attack_target(
    engine: GameEngine, player: Player,
) -> Optional[Player]:
    if not can_use_fire_attack(engine, player):
        return None
    targets = [
        target for target in _enemies(engine, player)
        if target.hand
    ]
    return min(targets, key=_target_priority) if targets else None


def should_use_five_grains(
    engine: GameEngine, player: Player,
) -> bool:
    allies = _allies(engine, player)
    enemies = _enemies(engine, player)
    return bool(enemies and len(allies) >= len(enemies))


def should_use_peach_garden(
    engine: GameEngine, player: Player,
) -> bool:
    wounded_allies = sum(
        target.hp < target.max_hp for target in _allies(engine, player)
    )
    wounded_enemies = sum(
        target.hp < target.max_hp for target in _enemies(engine, player)
    )
    return bool(
        wounded_allies + wounded_enemies > 0
        and wounded_allies >= wounded_enemies
    )


def _can_defend_borrowed_slash(
    engine: GameEngine, actor: Player, wielder: Player,
) -> bool:
    if any(card.name == "闪" for card in actor.hand):
        return True
    armor = _armor(actor)
    if armor is None:
        return False
    wielded_weapon = _weapon(wielder)
    if wielded_weapon is not None and wielded_weapon.name == "青釭剑":
        return False
    if armor.name == "八卦阵":
        return True
    if armor.name == "仁王盾":
        return True
    if armor.name == "藤甲":
        return not (
            wielded_weapon is not None
            and wielded_weapon.name == "朱雀羽扇"
        )
    return False


def choose_borrowed_sword_plan(
    engine: GameEngine, actor: Player,
) -> Optional[BorrowedSwordPlan]:
    """优先令敌方互杀；只能指定自己时必须先具备防杀条件。"""
    for wielder in sorted(
        (
            target for target in _enemies(engine, actor)
            if _weapon(target) is not None
        ),
        key=lambda target: target.seat,
    ):
        victims = engine.borrowed_sword_victims(wielder)
        enemy_victims = [
            victim for victim in victims
            if victim is not actor
            and engine.are_enemies(actor, victim)
        ]
        if enemy_victims:
            return BorrowedSwordPlan(
                wielder,
                min(enemy_victims, key=_target_priority),
            )
        if (
            actor in victims
            and _can_defend_borrowed_slash(
                engine, actor, wielder
            )
        ):
            return BorrowedSwordPlan(wielder, actor)
    return None


def choose_equipment_to_play(
    engine: GameEngine, player: Player,
) -> Optional[Card]:
    """一层轻量推演：比较即时战术收益、替换损失和剩余手牌价值。"""
    candidates = [
        card for card in player.hand
        if card.kind == CardKind.EQUIPMENT and card.equipment_type
    ]
    if not candidates:
        return None
    overflow = len(player.hand) > engine.hand_limit(player)
    scored = []
    for index, card in enumerate(candidates):
        current = _equipped(player, card.equipment_type)
        hand_after = [hand for hand in player.hand if hand is not card]
        score = 0

        if card.equipment_type == "weapon":
            score = _weapon_tactical_score(
                engine, player, card, hand_after
            )
            if score <= 0:
                continue
            if current is not None:
                current_score = _weapon_tactical_score(
                    engine, player, current, list(player.hand)
                )
                strategic_upgrade = score >= current_score + 10
                overflow_swap = overflow and score >= current_score
                if not strategic_upgrade and not overflow_swap:
                    continue

        elif card.equipment_type == "armor":
            score = _armor_score(engine, player, card)
            replace_silver_for_recovery = (
                current is not None
                and current.name == "白银狮子"
                and player.hp < player.max_hp
            )
            if score <= 0 and not replace_silver_for_recovery:
                continue
            if replace_silver_for_recovery:
                # 受伤时替换白银狮子可立即回复1点体力。
                score = 180 + max(-20, score)
            elif current is not None:
                current_score = _armor_score(
                    engine, player, current
                )
                strategic_upgrade = score >= current_score + 12
                overflow_swap = overflow and score >= current_score
                if not strategic_upgrade and not overflow_swap:
                    continue

        elif card.equipment_type == "offensive_mount":
            if current is not None and not overflow:
                continue
            score = (
                48 if _offensive_mount_has_target(
                    engine, player, card
                ) else 32
            )
            if current is not None:
                score = 24

        elif card.equipment_type == "defensive_mount":
            if current is not None and not overflow:
                continue
            score = 42 if current is None else 24

        else:
            if current is not None and not overflow:
                continue
            score = 30

        equipment_overrides = {card.equipment_type: card}
        residual = remaining_hand_value(
            engine,
            player,
            hand_after,
            weapon_override=(
                card if card.equipment_type == "weapon"
                else _CURRENT_WEAPON
            ),
            equipment_overrides=equipment_overrides,
        )
        scored.append(((score, residual, -index), card))

    if not scored:
        return None
    return max(scored, key=lambda item: item[0])[1]
