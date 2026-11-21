"""游戏核心引擎：回合流程、出牌逻辑、胜负判定"""

from __future__ import annotations

import random
from typing import Callable, Optional

from src.models import (
    ActiveCardUseEvent, Card, CardKind, CardMoveEvent, CardRevealEvent,
    CardUseEvent,
    DamageEvent, DamageNature, DrawCardsEvent, DrawPhaseEvent, GameState,
    HpLossEvent, JudgmentEvent, JudgmentStep, Phase, Player, PlayerChoice,
    PlayPhaseEndEvent, PromptContext, PromptType, RuleEvent, SkillTiming,
    SlashEvent, TrickCardDiscardEvent,
)
from src.skills import SkillApplication, SkillManager


DAMAGE_TRICK_NAMES = {
    "决斗", "南蛮入侵", "万箭齐发", "万剑齐发", "火攻",
}


class GameEngine:
    """管理游戏回合流程和核心规则"""

    def __init__(self, players: list[Player], cards: list[Card]):
        self.state = GameState(players=players)
        self.draw_pile = cards[:]
        self.discard_pile: list[Card] = []
        self.processing_area: list[Card] = []
        self._next_judgment_id = 1
        self._next_slash_id = 1
        self._next_move_id = 1
        self._next_move_batch_id = 1
        self._next_draw_id = 1
        self._next_reveal_id = 1
        self._next_rule_event_id = 1
        self.card_move_history: list[CardMoveEvent] = []
        self.draw_event_history: list[DrawCardsEvent] = []
        self.card_reveal_history: list[CardRevealEvent] = []
        self.rule_event_history: list[RuleEvent] = []
        self.pending_rule_events: list[RuleEvent] = []
        self.card_use_listener: Optional[
            Callable[[CardUseEvent], None]
        ] = None
        self.draw_cards_listener: Optional[
            Callable[[DrawCardsEvent], None]
        ] = None
        self.skills = SkillManager()
        random.shuffle(self.draw_pile)
        self.log: list[str] = []  # 操作日志，供 UI 显示
        # 核心规则只发布“技能实际生效”事件；动画、音效由界面订阅。
        self.skill_application_listener: Optional[
            Callable[[Player, SkillApplication], None]
        ] = None

    def publish_rule_event(
        self, event_type: str, *, actor_seat: Optional[int] = None,
        target_seats: tuple[int, ...] = (), card_ids: tuple[str, ...] = (),
        data: Optional[dict] = None, visibility: str = "public",
        recipient_seats: tuple[int, ...] = (),
    ) -> RuleEvent:
        """发布纯数据规则事件；客户端表现只能读取事件，不能回写规则结果。"""
        event = RuleEvent(
            event_id=self._next_rule_event_id,
            event_type=event_type,
            actor_seat=actor_seat,
            target_seats=target_seats,
            card_ids=card_ids,
            data=dict(data or {}),
            visibility=visibility,
            recipient_seats=recipient_seats,
        )
        self._next_rule_event_id += 1
        self.rule_event_history.append(event)
        self.pending_rule_events.append(event)
        return event

    def drain_rule_events(self) -> list[RuleEvent]:
        """返回尚未被客户端消费的事件；规则状态不依赖消费时机。"""
        events = self.pending_rule_events[:]
        self.pending_rule_events.clear()
        return events

    def record_card_use(
        self, player: Player, effective_card: Card,
        physical_cards: tuple[Card, ...] = (),
        target_seats: tuple[int, ...] = (),
    ) -> CardUseEvent:
        """记录“使用牌”并发布统一时机；打出牌与重铸不得调用。"""
        previous = player.last_used_card
        event = CardUseEvent(
            player=player,
            effective_card=effective_card,
            physical_cards=physical_cards,
            previous_card=previous,
            target_seats=target_seats,
        )
        player.last_used_card = effective_card.model_copy(deep=True)
        if (
            self.state.phase == Phase.PLAY
            and self.get_current_player().seat == player.seat
        ):
            player.play_phase_card_use_counts[effective_card.name] = (
                player.play_phase_card_use_counts.get(
                    effective_card.name, 0
                ) + 1
            )
        self.publish_rule_event(
            "card_used",
            actor_seat=player.seat,
            target_seats=target_seats,
            card_ids=tuple(card.id for card in physical_cards),
            data={
                "effective_card_name": effective_card.name,
                "effective_suit": effective_card.suit,
                "effective_rank": effective_card.rank,
                "previous_card_name": (
                    previous.name if previous is not None else None
                ),
            },
        )
        if self.card_use_listener is not None:
            self.card_use_listener(event)
        return event

    @staticmethod
    def validate_player_choice(
        prompt: PromptContext, choice: PlayerChoice
    ) -> bool:
        """按活动提示重新校验纯数据选择，供本地与未来服务器共同调用。"""
        if (
            choice.prompt_id != prompt.prompt_id
            or choice.player_seat != prompt.player_seat
        ):
            return False
        if not choice.confirmed:
            return not choice.card_ids and not choice.target_seats
        if (
            len(set(choice.card_ids)) != len(choice.card_ids)
            or len(set(choice.target_seats)) != len(choice.target_seats)
            or not set(choice.card_ids).issubset(prompt.legal_card_ids)
            or not set(choice.target_seats).issubset(
                prompt.legal_target_seats
            )
        ):
            return False
        required_cards = prompt.required_cards
        required_targets = prompt.required_targets
        # 兼容原有只用 required_cards 表达“选一名目标”的提示。
        if (
            prompt.prompt_type == PromptType.CHOOSE_TARGET
            and required_targets == 0
        ):
            required_targets = required_cards
            required_cards = 0
        return (
            len(choice.card_ids) == required_cards
            and len(choice.target_seats) == required_targets
        )

    # ---- 牌堆操作 ----

    def draw_cards(self, n: int = 1) -> list[Card]:
        drawn = []
        for _ in range(n):
            if not self.draw_pile:
                self._reshuffle()
            drawn.append(self.draw_pile.pop())
        return drawn

    def draw_to_hand(
        self, player: Player, n: int = 1, *, reason: str = "摸牌",
        visibility: str = "private",
        source_event_id: Optional[int] = None,
    ) -> list[CardMoveEvent]:
        """执行一次摸牌；单牌移动共享批次，并额外记录完整摸牌事件。"""
        if not player.alive or n <= 0:
            return []
        cards = self.draw_cards(n)
        draw_id = self._next_draw_id
        self._next_draw_id += 1
        batch_id = self._next_move_batch_id
        self._next_move_batch_id += 1
        events: list[CardMoveEvent] = []
        for index, card in enumerate(cards):
            player.hand.append(card)
            event = CardMoveEvent(
                move_id=self._next_move_id,
                card=card,
                to_player_seat=player.seat,
                from_zone="draw_pile",
                to_zone="hand",
                reason=reason,
                source_event_id=source_event_id,
                batch_id=batch_id,
                batch_index=index,
                batch_size=len(cards),
                visibility=visibility,
            )
            self._next_move_id += 1
            self.card_move_history.append(event)
            self.publish_rule_event(
                "card_moved",
                target_seats=(player.seat,),
                card_ids=(card.id,),
                data={
                    "move_id": event.move_id,
                    "from_zone": event.from_zone,
                    "to_zone": event.to_zone,
                    "reason": reason,
                    "source_event_id": source_event_id,
                    "batch_id": batch_id,
                    "batch_index": index,
                    "batch_size": len(cards),
                    "draw_id": draw_id,
                },
                visibility=visibility,
                recipient_seats=(
                    (player.seat,) if visibility == "private" else ()
                ),
            )
            events.append(event)
        draw_event = DrawCardsEvent(
            draw_id=draw_id,
            player=player,
            cards=tuple(cards),
            count=len(cards),
            reason=reason,
            source_event_id=source_event_id,
            move_ids=tuple(event.move_id for event in events),
        )
        self.draw_event_history.append(draw_event)
        self.publish_rule_event(
            "cards_drawn",
            actor_seat=player.seat,
            target_seats=(player.seat,),
            card_ids=tuple(card.id for card in cards),
            data={
                "draw_id": draw_id,
                "count": len(cards),
                "reason": reason,
                "source_event_id": source_event_id,
                "move_ids": draw_event.move_ids,
                "batch_id": batch_id,
            },
            visibility=visibility,
            recipient_seats=(
                (player.seat,) if visibility == "private" else ()
            ),
        )
        if self.draw_cards_listener is not None:
            self.draw_cards_listener(draw_event)
        return events

    def discard(self, card: Card):
        self.discard_pile.append(card)

    def begin_processing_card(self, card: Card) -> bool:
        """将正在结算的实体牌放入处理区，避免提前进入弃牌堆。"""
        if card in self.processing_area:
            return True
        if card in self.discard_pile:
            return False
        self.processing_area.append(card)
        return True

    def stage_owned_cards_for_use(
        self, player: Player, cards: list[Card],
        reason: str = "提交使用",
        source_event_id: Optional[int] = None,
    ) -> bool:
        """提交“使用”的实体牌，并发布角色区域到处理区的移动事件。"""
        if (
            not cards
            or len({card.id for card in cards}) != len(cards)
            or any(
                card not in player.hand and card not in player.equipment
                for card in cards
            )
        ):
            return False
        batch_id = self._next_move_batch_id
        self._next_move_batch_id += 1
        for index, card in enumerate(cards):
            if card in player.hand:
                from_zone = "hand"
                player.hand.remove(card)
            else:
                from_zone = "equipment"
                self.remove_equipment(player, card)
            self.begin_processing_card(card)
            move = CardMoveEvent(
                move_id=self._next_move_id,
                card=card,
                from_player_seat=player.seat,
                from_zone=from_zone,
                to_zone="processing",
                reason=reason,
                source_event_id=source_event_id,
                batch_id=batch_id,
                batch_index=index,
                batch_size=len(cards),
                visibility="public",
            )
            self._next_move_id += 1
            self.card_move_history.append(move)
            self.publish_rule_event(
                "card_moved",
                actor_seat=player.seat,
                card_ids=(card.id,),
                data={
                    "move_id": move.move_id,
                    "from_zone": from_zone,
                    "to_zone": "processing",
                    "reason": reason,
                    "source_event_id": source_event_id,
                    "batch_id": batch_id,
                    "batch_index": index,
                    "batch_size": len(cards),
                },
            )
        return True

    def finish_processing_card(self, card: Card) -> bool:
        """仅在牌仍处于处理区时，将其结算至弃牌堆。"""
        if card not in self.processing_area:
            return False
        self.processing_area.remove(card)
        if card not in self.discard_pile:
            self.discard(card)
        move = CardMoveEvent(
            move_id=self._next_move_id,
            card=card,
            from_zone="processing",
            to_zone="discard",
            reason="结算完毕",
            visibility="public",
        )
        self._next_move_id += 1
        self.card_move_history.append(move)
        self.publish_rule_event(
            "card_moved",
            card_ids=(card.id,),
            data={
                "move_id": move.move_id,
                "from_zone": "processing",
                "to_zone": "discard",
                "reason": move.reason,
            },
        )
        return True

    def gain_from_processing(
        self, player: Player, card: Card, reason: str,
        source_event_id: Optional[int] = None,
        visibility: str = "private",
        batch_id: Optional[int] = None,
        batch_index: int = 0,
        batch_size: int = 1,
    ) -> Optional[CardMoveEvent]:
        """统一执行处理区到角色手牌区的获得移动。"""
        if not player.alive or card not in self.processing_area:
            return None
        self.processing_area.remove(card)
        player.hand.append(card)
        event = CardMoveEvent(
            move_id=self._next_move_id,
            card=card,
            to_player_seat=player.seat,
            from_zone="processing",
            to_zone="hand",
            reason=reason,
            source_event_id=source_event_id,
            batch_id=batch_id,
            batch_index=batch_index,
            batch_size=batch_size,
            visibility=visibility,
        )
        self._next_move_id += 1
        self.card_move_history.append(event)
        self.publish_rule_event(
            "card_moved",
            target_seats=(player.seat,),
            card_ids=(card.id,),
            data={
                "move_id": event.move_id,
                "from_zone": event.from_zone,
                "to_zone": event.to_zone,
                "reason": reason,
                "source_event_id": source_event_id,
                "batch_id": batch_id,
                "batch_index": batch_index,
                "batch_size": batch_size,
            },
            visibility=visibility,
            recipient_seats=(
                (player.seat,) if visibility == "private" else ()
            ),
        )
        return event

    def gain_many_from_processing(
        self, player: Player, cards: tuple[Card, ...] | list[Card],
        reason: str, source_event_id: Optional[int] = None,
        visibility: str = "private",
    ) -> list[CardMoveEvent]:
        """把同一效果获得的多张处理区牌作为一个移动批次提交。"""
        valid_cards = [
            card for card in cards if card in self.processing_area
        ]
        if not player.alive or not valid_cards:
            return []
        batch_id = self._next_move_batch_id
        self._next_move_batch_id += 1
        events = []
        for index, card in enumerate(valid_cards):
            move = self.gain_from_processing(
                player,
                card,
                reason,
                source_event_id=source_event_id,
                visibility=visibility,
                batch_id=batch_id,
                batch_index=index,
                batch_size=len(valid_cards),
            )
            if move is not None:
                events.append(move)
        return events

    def gain_from_discard_pile(
        self, player: Player, card: Card, reason: str,
        source_event_id: Optional[int] = None,
        visibility: str = "public",
    ) -> Optional[CardMoveEvent]:
        """获得一张仍在弃牌堆中的牌；供弃置后的响应窗口统一使用。"""
        if not player.alive or card not in self.discard_pile:
            return None
        self.discard_pile.remove(card)
        player.hand.append(card)
        event = CardMoveEvent(
            move_id=self._next_move_id,
            card=card,
            to_player_seat=player.seat,
            from_zone="discard_pile",
            to_zone="hand",
            reason=reason,
            source_event_id=source_event_id,
            visibility=visibility,
        )
        self._next_move_id += 1
        self.card_move_history.append(event)
        self.publish_rule_event(
            "card_moved",
            target_seats=(player.seat,),
            card_ids=(card.id,),
            data={
                "move_id": event.move_id,
                "from_zone": event.from_zone,
                "to_zone": event.to_zone,
                "reason": reason,
                "source_event_id": source_event_id,
            },
            visibility=visibility,
        )
        return event

    def discard_from_zone(
        self, player: Player, card: Card, from_zone: str, reason: str,
        source_event_id: Optional[int] = None,
    ) -> Optional[CardMoveEvent]:
        """统一执行角色区域到弃牌堆的移动，并保存可审计原因。"""
        if from_zone == "hand":
            if card not in player.hand:
                return None
            player.hand.remove(card)
        elif from_zone == "equipment":
            if not self.remove_equipment(player, card):
                return None
        elif from_zone == "judgment":
            if card not in player.judgment_area:
                return None
            player.judgment_area.remove(card)
        else:
            raise ValueError(f"不支持从区域 {from_zone} 弃置")
        self.discard(card)
        event = CardMoveEvent(
            move_id=self._next_move_id,
            card=card,
            from_player_seat=player.seat,
            from_zone=from_zone,
            to_zone="discard_pile",
            reason=reason,
            source_event_id=source_event_id,
        )
        self._next_move_id += 1
        self.card_move_history.append(event)
        self.publish_rule_event(
            "card_moved",
            actor_seat=player.seat,
            card_ids=(card.id,),
            data={
                "move_id": event.move_id,
                "from_zone": event.from_zone,
                "to_zone": event.to_zone,
                "reason": reason,
                "source_event_id": source_event_id,
            },
        )
        return event

    def discard_from_hand(
        self, player: Player, card: Card, reason: str,
        source_event_id: Optional[int] = None,
    ) -> Optional[CardMoveEvent]:
        return self.discard_from_zone(
            player, card, "hand", reason, source_event_id
        )

    def transfer_owned_card(
        self, source: Player, recipient: Player, card: Card, reason: str,
        source_event_id: Optional[int] = None,
    ) -> Optional[CardMoveEvent]:
        """把一张手牌或装备交给另一名角色，并发布真实区域移动事件。"""
        if not source.alive or not recipient.alive or source == recipient:
            return None
        if card in source.hand:
            from_zone = "hand"
            source.hand.remove(card)
            visibility = "private"
        elif card in source.equipment:
            from_zone = "equipment"
            if not self.remove_equipment(source, card):
                return None
            visibility = "public"
        else:
            return None
        recipient.hand.append(card)
        event = CardMoveEvent(
            move_id=self._next_move_id,
            card=card,
            from_player_seat=source.seat,
            to_player_seat=recipient.seat,
            from_zone=from_zone,
            to_zone="hand",
            reason=reason,
            source_event_id=source_event_id,
            visibility=visibility,
        )
        self._next_move_id += 1
        self.card_move_history.append(event)
        self.publish_rule_event(
            "card_moved",
            actor_seat=source.seat,
            target_seats=(recipient.seat,),
            card_ids=(card.id,),
            data={
                "move_id": event.move_id,
                "from_zone": from_zone,
                "to_zone": "hand",
                "reason": reason,
                "source_event_id": source_event_id,
            },
            visibility=visibility,
            recipient_seats=(
                (recipient.seat,) if visibility == "private" else ()
            ),
        )
        return event

    def reveal_card(
        self, player: Player, card: Card, from_zone: str, reason: str,
        visibility: str = "public",
        source_event_id: Optional[int] = None,
    ) -> Optional[CardRevealEvent]:
        """建立公开信息事件；只公开牌面，不移动或复制规则实体。"""
        zone_cards = {
            "hand": player.hand,
            "equipment": player.equipment,
            "judgment": player.judgment_area,
        }.get(from_zone)
        if zone_cards is None:
            raise ValueError(f"不支持从区域 {from_zone} 展示牌")
        if card not in zone_cards:
            return None
        event = CardRevealEvent(
            reveal_id=self._next_reveal_id,
            card=card,
            owner_seat=player.seat,
            from_zone=from_zone,
            visibility=visibility,
            reason=reason,
            source_event_id=source_event_id,
        )
        self._next_reveal_id += 1
        self.card_reveal_history.append(event)
        self.publish_rule_event(
            "card_revealed",
            actor_seat=player.seat,
            card_ids=(card.id,),
            data={
                "reveal_id": event.reveal_id,
                "from_zone": from_zone,
                "reason": reason,
                "source_event_id": source_event_id,
            },
            visibility=visibility,
            recipient_seats=(
                (player.seat,) if visibility == "private" else ()
            ),
        )
        return event

    def _reshuffle(self):
        if not self.discard_pile:
            raise RuntimeError("牌堆已空，无法摸牌")
        self.draw_pile = self.discard_pile
        self.discard_pile = []
        random.shuffle(self.draw_pile)

    # ---- 玩家操作 ----

    def get_current_player(self) -> Player:
        return self.state.players[self.state.current_turn]

    def get_alive_players(self) -> list[Player]:
        return [p for p in self.state.players if p.alive]

    def get_alive_enemies(self, player: Player) -> list[Player]:
        return [
            p for p in self.state.players
            if p.alive and self.are_enemies(player, p)
        ]

    def get_peach_garden_targets(self, actor: Player) -> list[Player]:
        """按行动顺序返回【桃园结义】当前所有受伤角色。"""
        players = self.state.players
        start = players.index(actor)
        ordered = (
            players[start:] + players[:start]
        )
        return [
            player for player in ordered
            if player.alive and player.hp < player.max_hp
        ]

    @staticmethod
    def are_enemies(first: Player, second: Player) -> bool:
        """统一敌对关系；无组队数据时，不同座次互为敌对。"""
        if first.seat == second.seat:
            return False
        if first.side is not None and second.side is not None:
            return first.side != second.side
        return True

    @staticmethod
    def same_player(first: Optional[Player], second: Optional[Player]) -> bool:
        """角色身份只由稳定座次判断，不能依赖 Python 对象是否为同一实例。"""
        return bool(
            first is not None
            and second is not None
            and first.seat == second.seat
        )

    def get_armor(self, player: Player) -> Optional[Card]:
        """返回角色当前装备的防具。"""
        return next(
            (card for card in player.equipment if card.equipment_type == "armor"),
            None,
        )

    @staticmethod
    def is_red(card: Card) -> bool:
        return card.color == "red"

    @staticmethod
    def is_black(card: Card) -> bool:
        return card.color == "black"

    @staticmethod
    def rank_value(card: Card) -> int:
        rank = str(card.rank)
        return {"A": 1, "J": 11, "Q": 12, "K": 13}.get(
            rank, int(rank) if rank.isdigit() else 0
        )

    def matches_judgment(self, card: Card, rule: str) -> bool:
        """统一计算常用判定条件，业务代码不得自行重复换算。"""
        matchers = {
            "red": lambda value: self.is_red(value),
            "black": lambda value: self.is_black(value),
            "heart": lambda value: value.suit == "heart",
            "club": lambda value: value.suit == "club",
            "spade": lambda value: value.suit == "spade",
            "not_heart": lambda value: value.suit != "heart",
            "not_club": lambda value: value.suit != "club",
            "spade_2_9": lambda value: (
                value.suit == "spade" and 2 <= self.rank_value(value) <= 9
            ),
        }
        if rule not in matchers:
            raise ValueError(f"未知判定规则：{rule}")
        return bool(matchers[rule](card))

    def begin_judgment(
        self, judging_player: Player, reason: str, result_rule: str,
        source_player: Optional[Player] = None,
        source_card: Optional[Card] = None,
        parent_event_id: Optional[int] = None,
    ) -> JudgmentEvent:
        """创建并亮出一次独立判定，暂不处理最终牌去向。"""
        event = JudgmentEvent(
            judgment_id=self._next_judgment_id,
            judging_player=judging_player,
            reason=reason,
            result_rule=result_rule,
            source_player=source_player,
            source_card=source_card,
            parent_event_id=parent_event_id,
        )
        self._next_judgment_id += 1
        judged = self.draw_cards(1)[0]
        self.processing_area.append(judged)
        revealed = event.model_copy(update={
            "initial_card": judged,
            "current_card": judged,
            "step": JudgmentStep.REVEALED,
        })
        self.publish_rule_event(
            "judgment_revealed",
            actor_seat=judging_player.seat,
            card_ids=(judged.id,),
            data={
                "judgment_id": revealed.judgment_id,
                "reason": reason,
                "result_rule": result_rule,
            },
        )
        return revealed

    def replace_judgment_card(
        self, event: JudgmentEvent, replacement: Card
    ) -> JudgmentEvent:
        """替换当前判定牌；为后续改判技能保留统一入口。"""
        if event.step not in (JudgmentStep.REVEALED, JudgmentStep.MODIFYING):
            raise RuntimeError("当前判定已经不能改判")
        for player in self.state.players:
            if replacement in player.hand:
                player.hand.remove(replacement)
                break
            if replacement in player.judgment_area:
                player.judgment_area.remove(replacement)
                break
        if replacement not in self.processing_area:
            self.processing_area.append(replacement)
        replaced = event.replaced_cards[:]
        if event.current_card is not None:
            replaced.append(event.current_card)
        return event.model_copy(update={
            "current_card": replacement,
            "replaced_cards": replaced,
            "step": JudgmentStep.MODIFYING,
        })

    def replace_judgment_and_gain_original(
        self, event: JudgmentEvent, replacer: Player, replacement: Card,
        reason: str,
    ) -> tuple[JudgmentEvent, Optional[CardMoveEvent]]:
        """用角色的一张牌替换判定牌，并令其公开获得原判定牌。"""
        if event.step not in (JudgmentStep.REVEALED, JudgmentStep.MODIFYING):
            return event, None
        original = event.current_card
        if original is None or replacement is original:
            return event, None
        if replacement not in replacer.hand and replacement not in replacer.equipment:
            return event, None
        if not self.stage_owned_cards_for_use(replacer, [replacement]):
            return event, None
        move = self.gain_from_processing(
            replacer,
            original,
            reason=f"{reason}：获得原判定牌",
            source_event_id=event.judgment_id,
            visibility="public",
        )
        if move is None:
            # 只在极端非法状态下回滚替换牌，避免凭空丢牌。
            if replacement in self.processing_area:
                self.processing_area.remove(replacement)
            replacer.hand.append(replacement)
            return event, None
        updated = event.model_copy(update={
            "current_card": replacement,
            "step": JudgmentStep.MODIFYING,
        })
        self.publish_rule_event(
            "judgment_replaced",
            actor_seat=replacer.seat,
            target_seats=(event.judging_player.seat,),
            card_ids=(replacement.id, original.id),
            data={
                "judgment_id": event.judgment_id,
                "replacement_card_id": replacement.id,
                "original_card_id": original.id,
                "reason": reason,
            },
        )
        return updated, move

    def finalize_judgment(self, event: JudgmentEvent) -> JudgmentEvent:
        """冻结判定结果并统一处理所有判定牌的默认去向。"""
        if event.current_card is None:
            raise RuntimeError("判定事件没有有效判定牌")
        result = self.matches_judgment(event.current_card, event.result_rule)
        completed = event.model_copy(update={
            "result": result,
            "step": JudgmentStep.FINALIZED,
        })
        cards = []
        for card in [*completed.replaced_cards, completed.current_card]:
            if card is not None and card not in cards:
                cards.append(card)
        for card in cards:
            if card in self.processing_area:
                self.processing_area.remove(card)
            self.discard(card)
        completed = completed.model_copy(update={"step": JudgmentStep.COMPLETED})
        self.publish_rule_event(
            "judgment_completed",
            actor_seat=completed.judging_player.seat,
            card_ids=(completed.current_card.id,),
            data={
                "judgment_id": completed.judgment_id,
                "reason": completed.reason,
                "result": bool(completed.result),
            },
        )
        return completed

    def conduct_judgment(
        self, judging_player: Player, reason: str, result_rule: str,
        source_player: Optional[Player] = None,
        source_card: Optional[Card] = None,
        parent_event_id: Optional[int] = None,
    ) -> JudgmentEvent:
        """同步完成无改判的一次通用判定。"""
        event = self.begin_judgment(
            judging_player, reason, result_rule,
            source_player, source_card, parent_event_id
        )
        return self.finalize_judgment(event)

    def lose_hp(
        self, target: Player, amount: int, *, reason: str = "",
        source_skill_id: Optional[str] = None,
    ) -> Optional[HpLossEvent]:
        """令角色失去体力；不创建伤害事件，也不触发伤害修正或受伤技能。"""
        if not target.alive or amount <= 0:
            return None
        target.hp -= amount
        event = HpLossEvent(
            target=target,
            amount=amount,
            reason=reason,
            source_skill_id=source_skill_id,
        )
        self.publish_rule_event(
            "hp_lost",
            target_seats=(target.seat,),
            data={
                "amount": amount,
                "hp_after": target.hp,
                "reason": reason,
                "source_skill_id": source_skill_id,
            },
        )
        return event

    def armor_nullifies_response_source(
        self, target: Player, source_name: str, source_card: Optional[Card],
        source_player: Optional[Player] = None, ignore_armor: bool = False,
    ) -> Optional[str]:
        """返回令当前【杀】或群体锦囊对目标无效的防具名。"""
        if ignore_armor or (
            source_name == "杀" and source_player is not None
            and self.skills.slash_ignores_armor(source_player)
        ):
            return None
        skill = self.skills.nullifying_skill(target, source_name, source_card)
        return skill.name if skill else None

    def get_optional_response_skill(
        self, player: Player, required_card: str
    ):
        """返回此响应时机中应询问操作者的一个可选技能。"""
        return self.skills.optional_response_skill(player, required_card)

    def activate_optional_response_skill(
        self, player: Player, skill_id: str
    ) -> Optional[JudgmentEvent]:
        """执行操作者已经确认发动的响应技能。"""
        skill = self.skills.optional_response_skill(player, "闪")
        if skill is None or skill.skill_id != skill_id:
            return None
        if skill_id == "armor.bagua":
            return self.conduct_judgment(
                player, skill.name, "red",
                source_card=self.skills._source_equipment(player, skill),
            )
        return None

    def begin_optional_response_skill_judgment(
        self, player: Player, skill_id: str
    ) -> Optional[JudgmentEvent]:
        """开始响应技能判定，但把改判窗口和最终定案留给通用结算层。"""
        skill = self.skills.optional_response_skill(player, "闪")
        if skill is None or skill.skill_id != skill_id:
            return None
        if skill_id == "armor.bagua":
            return self.begin_judgment(
                player, skill.name, "red",
                source_card=self.skills._source_equipment(player, skill),
            )
        return None

    def resolve_bagua_judgment(self, player: Player) -> Optional[tuple[Card, bool]]:
        """八卦阵判定：翻开牌堆顶一张牌，红色视为打出【闪】。"""
        skill = self.get_optional_response_skill(player, "闪")
        if skill is None or skill.skill_id != "armor.bagua":
            return None
        event = self.activate_optional_response_skill(player, skill.skill_id)
        if event is None or event.current_card is None:
            return None
        return event.current_card, bool(event.result)

    def remove_equipment(self, player: Player, card: Card) -> bool:
        """令装备离开装备区，并结算白银狮子的离区回复。"""
        if card not in player.equipment:
            return False
        player.equipment.remove(card)
        for application in self.skills.equipment_lost(player, card):
            self.log.append(application.message)
            if self.skill_application_listener is not None:
                self.skill_application_listener(player, application)
        return True

    def get_chained_propagation_targets(self, damaged: Player) -> list[Player]:
        """从当前回合角色开始，按逆时针顺次返回其余横置角色。"""
        players = self.state.players
        start = self.state.current_turn
        ordered = [players[(start - offset) % len(players)] for offset in range(len(players))]
        return [p for p in ordered if p.alive and p.chained and p != damaged]

    def modify_damage(self, target: Player, event: DamageEvent) -> DamageEvent:
        """统一伤害修正入口；后续装备和技能应在这里修改每一段伤害。"""
        return self.modify_damage_with_skills(target, event)[0]

    def modify_causing_damage_with_skills(
        self, target: Player, event: DamageEvent
    ) -> tuple[DamageEvent, list[SkillApplication]]:
        """结算“造成伤害时”已有的来源方数值效果。"""
        if (
            event.source_player is not None and event.source_card is not None
            and event.source_card.name in ("杀", "火杀", "雷杀")
        ):
            return self.skills.before_slash_damage(
                event.source_player, target, event
            )
        return event, []

    def modify_receiving_damage_with_skills(
        self, target: Player, event: DamageEvent
    ) -> tuple[DamageEvent, list[SkillApplication]]:
        """结算受伤角色武将技之后的“受到伤害时”装备效果。"""
        return self.skills.modify_damage(target, event)

    def modify_damage_with_skills(
        self, target: Player, event: DamageEvent
    ) -> tuple[DamageEvent, list[SkillApplication]]:
        """兼容纯规则调用：依次结算造成伤害时、受到伤害时的既有数值效果。"""
        event, source_applications = self.modify_causing_damage_with_skills(
            target, event
        )
        if event.amount <= 0:
            return event, source_applications
        event, target_applications = self.modify_receiving_damage_with_skills(
            target, event
        )
        return event, [*source_applications, *target_applications]

    def can_use_slash(
        self, player: Player, excluded_cards: tuple[Card, ...] = ()
    ) -> bool:
        used = max(
            player.slash_use_count,
            1 if player.slash_used else 0,
        )
        return (
            used < 1 + player.active_slash_use_bonus
            or self.skills.slash_unlimited(player, excluded_cards)
        )

    def has_remaining_limited_slash_uses(self, player: Player) -> bool:
        """不计诸葛连弩时，当前出牌阶段是否仍有【杀】次数。"""
        used = max(
            player.slash_use_count,
            1 if player.slash_used else 0,
        )
        return used < 1 + player.active_slash_use_bonus

    def begin_play_phase(self, player: Player) -> None:
        """进入真实出牌阶段，并激活此前登记的额外【杀】次数。"""
        player.active_slash_use_bonus = player.pending_slash_use_bonus
        player.pending_slash_use_bonus = 0
        player.slash_use_count = 0
        player.slash_used = False
        player.play_phase_card_use_counts.clear()

    def end_play_phase(self, player: Player) -> PlayPhaseEndEvent:
        """冻结出牌阶段统计；阶段结束技在进入弃牌阶段前读取该事件。"""
        if (
            self.state.phase != Phase.PLAY
            or self.get_current_player().seat != player.seat
        ):
            raise ValueError("当前角色不在其出牌阶段")
        event = PlayPhaseEndEvent(
            player=player,
            card_use_counts=dict(player.play_phase_card_use_counts),
        )
        self.publish_rule_event(
            "play_phase_ended",
            actor_seat=player.seat,
            data={"card_use_counts": dict(event.card_use_counts)},
        )
        return event

    def can_select_play_card(self, player: Player, card: Card) -> bool:
        """牌能否进入出牌阶段的选择态；不得混入“是否存在目标”的判断。"""
        if not player.alive or card not in player.hand:
            return False
        if card.name in ("闪", "无懈可击"):
            return False
        if card.name in ("杀", "火杀", "雷杀"):
            return self.can_use_slash(player)
        if card.name == "桃":
            return player.hp < player.max_hp
        if card.name == "酒":
            return not player.wine_used
        return True

    @staticmethod
    def card_name_requires_manual_target(card_name: str) -> bool:
        """有效牌名是否要求操作者进入武将目标选择；不检查目标是否合法。"""
        if card_name in ("杀", "火杀", "雷杀", "铁索连环"):
            return True
        return card_name in {
            "火攻", "过河拆桥", "顺手牵羊", "借刀杀人", "决斗",
            "乐不思蜀", "兵粮寸断",
        }

    def card_requires_manual_target(self, card: Card) -> bool:
        """当前牌是否需要操作者在武将区域选择目标。"""
        return self.card_name_requires_manual_target(card.name)

    def is_legal_play_target(
        self, player: Player, card: Card, target: Optional[Player],
        excluded_cards: tuple[Card, ...] = (),
    ) -> bool:
        """统一判断一个角色能否成为当前牌的目标，不判断其他目标是否存在。"""
        if target is None or not target.alive:
            return False
        if self.skills.prohibits_card_target(
            self, player, target, card
        ):
            return False
        if card.name in ("杀", "火杀", "雷杀"):
            return (
                self.can_use_slash(player, excluded_cards)
                and self.in_attack_range(player, target, excluded_cards)
            )
        if card.name == "铁索连环":
            return True
        if card.name == "火攻":
            remaining_hand = len(target.hand) - (
                1
                if self.same_player(target, player)
                and card in player.hand else 0
            )
            return remaining_hand > 0
        if card.name in ("过河拆桥", "顺手牵羊"):
            if self.same_player(target, player):
                return False
            if not (target.hand or target.equipment or target.judgment_area):
                return False
            return (
                card.name != "顺手牵羊"
                or self.distance(player, target) <= 1
            )
        if card.name == "借刀杀人":
            weapon = next(
                (
                    equipped for equipped in target.equipment
                    if equipped.equipment_type == "weapon"
                ),
                None,
            )
            return bool(
                not self.same_player(target, player) and weapon
                and self.borrowed_sword_victims(target)
            )
        if card.name == "决斗":
            return not self.same_player(target, player)
        if card.name in ("乐不思蜀", "兵粮寸断"):
            return self.can_place_delayed_trick(player, card, target)
        return False

    def get_legal_play_targets(
        self, player: Player, card: Card,
        excluded_cards: tuple[Card, ...] = (),
    ) -> list[Player]:
        """按座次返回当前牌的合法目标；只供目标显示和策略选择使用。"""
        players = self.state.players
        start = players.index(player)
        ordered = players[start + 1:] + players[:start + 1]
        return [
            target for target in ordered
            if self.is_legal_play_target(
                player, card, target, excluded_cards
            )
        ]

    def can_submit_play_card(
        self, player: Player, card: Card,
        targets: tuple[Player, ...] = (),
    ) -> bool:
        """完整牌行动能否提交；提交前仍须由实际结算入口再次校验。"""
        if not self.can_select_play_card(player, card):
            return False
        unique_targets = {target.seat for target in targets}
        if len(unique_targets) != len(targets):
            return False
        if card.name == "铁索连环":
            return bool(
                not targets
                or (
                    1 <= len(targets) <= 2
                    and all(
                        self.is_legal_play_target(player, card, target)
                        for target in targets
                    )
                )
            )
        if card.name in ("杀", "火杀", "雷杀"):
            excluded_cards = (card,)
            target_limit = self.skills.slash_target_limit(
                player, len(player.hand) == 1, excluded_cards
            )
            return bool(
                1 <= len(targets) <= target_limit
                and all(
                    self.is_legal_play_target(
                        player, card, target, excluded_cards
                    )
                    for target in targets
                )
            )
        if card.name == "借刀杀人":
            if len(targets) != 2:
                return False
            wielder, victim = targets
            return bool(
                self.is_legal_play_target(player, card, wielder)
                and victim in self.borrowed_sword_victims(wielder)
            )
        if self.card_requires_manual_target(card):
            return bool(
                len(targets) == 1
                and self.is_legal_play_target(player, card, targets[0])
            )
        return not targets

    def can_submit_conversion(
        self, player: Player, option, cards: list[Card],
        targets: tuple[Player, ...],
    ) -> bool:
        """完整校验一次模块化牌转化行动，不识别具体技能。"""
        if not self.skills.validate_conversion(
            player, option, cards
        ):
            return False
        effective_card = self.skills.build_conversion_card(option, cards)
        if effective_card.name in ("杀", "火杀", "雷杀"):
            excluded_cards = tuple(cards)
            if not self.can_use_slash(player, excluded_cards):
                return False
            was_last = bool(player.hand) and all(
                card in player.hand for card in cards
            ) and len(player.hand) == len(cards)
            target_limit = self.skills.slash_target_limit(
                player, was_last, excluded_cards
            )
            return bool(
                1 <= len(targets) <= target_limit
                and len({target.seat for target in targets}) == len(targets)
                and all(
                    self.is_legal_play_target(
                        player, effective_card, target, excluded_cards
                    )
                    for target in targets
                )
            )
        return False

    def can_submit_active_conversion(
        self, player: Player, option, cards: list[Card],
        targets: tuple[Player, ...] = (),
    ) -> bool:
        """校验主动牌转化；按有效牌规则处理目标，不识别技能名。"""
        if (
            self.state.phase != Phase.PLAY
            or self.get_current_player().seat != player.seat
            or option.timing != SkillTiming.PLAY_CONVERSION
            or not self.skills.can_activate_play_conversion(
                self, player, option
            )
            or not self.skills.validate_conversion(player, option, cards)
        ):
            return False
        effective_card = self.skills.build_conversion_card(option, cards)
        excluded_cards = tuple(cards)
        if self.card_requires_manual_target(effective_card):
            return bool(
                len(targets) == 1
                and self.is_legal_play_target(
                    player, effective_card, targets[0], excluded_cards
                )
            )
        if targets:
            return False
        if effective_card.name == "桃":
            return player.hp < player.max_hp
        if effective_card.name in ("万箭齐发", "万剑齐发"):
            return any(
                target.alive and target.seat != player.seat
                for target in self.state.players
            )
        return False

    def submit_active_conversion(
        self, player: Player, option, cards: list[Card],
        targets: tuple[Player, ...] = (),
    ) -> ActiveCardUseEvent:
        """提交主动技能牌转化，规则状态先于任何动画完成。"""
        if not self.can_submit_active_conversion(
            player, option, cards, targets
        ):
            raise ValueError("主动技能的牌或发动条件已经失效")
        effective_card = self.skills.build_conversion_card(option, cards)
        if not self.stage_owned_cards_for_use(
            player, cards, reason=f"{option.skill.name}转化使用"
        ):
            raise ValueError("主动技能的实体牌已经失效")
        self.skills.record_play_conversion(self, player, option)
        if effective_card.name == "桃":
            self.recover(player)
        event = ActiveCardUseEvent(
            player=player,
            skill_id=option.skill.skill_id,
            skill_name=option.skill.name,
            effective_card=effective_card,
            physical_cards=tuple(cards),
            target_seats=tuple(target.seat for target in targets),
        )
        self.record_card_use(
            player,
            effective_card,
            tuple(cards),
            tuple(target.seat for target in targets),
        )
        self.publish_rule_event(
            "skill_resolved",
            actor_seat=player.seat,
            target_seats=tuple(target.seat for target in targets),
            card_ids=tuple(card.id for card in cards),
            data={
                "skill_id": option.skill.skill_id,
                "skill_name": option.skill.name,
                "window": "play_conversion",
                "effective_card_name": effective_card.name,
            },
        )
        return event

    def submit_play_conversion(
        self, player: Player, option, cards: list[Card],
        targets: tuple[Player, ...],
    ) -> SlashEvent:
        """校验并提交一次主动牌转化；界面不得自行移动实体牌。"""
        if not self.can_submit_conversion(player, option, cards, targets):
            raise ValueError("牌转化选择或目标已经失效")
        effective_card = self.skills.build_conversion_card(option, cards)
        event = self.create_slash_event(
            player,
            cards,
            list(targets),
            effective_card.name,
            conversion_already_validated=True,
        )
        self.publish_rule_event(
            "skill_resolved",
            actor_seat=player.seat,
            target_seats=tuple(target.seat for target in targets),
            card_ids=tuple(card.id for card in cards),
            data={
                "skill_id": option.skill.skill_id,
                "skill_name": option.skill.name,
                "window": "play_conversion",
                "effective_card_name": event.effective_name,
                "slash_id": event.slash_id,
            },
        )
        return event

    def submit_response_conversion(
        self, player: Player, option, cards: list[Card],
        *, response_action: str,
    ) -> Card:
        """提交一次响应转化并返回冻结后的虚拟牌面。"""
        if not self.skills.validate_conversion(player, option, cards):
            raise ValueError("用于牌转化的实体牌已经失效")
        if response_action == "使用":
            if not self.stage_owned_cards_for_use(
                player,
                cards,
                reason=f"{option.skill.name}响应使用",
            ):
                raise ValueError("用于牌转化的实体牌已经失效")
        else:
            for card in cards:
                from_zone = (
                    "hand" if card in player.hand else "equipment"
                    if card in player.equipment else ""
                )
                if not from_zone or self.discard_from_zone(
                    player,
                    card,
                    from_zone,
                    f"{option.skill.name}响应打出",
                ) is None:
                    raise ValueError("用于牌转化的实体牌已经失效")
        effective_card = self.skills.build_conversion_card(option, cards)
        self.publish_rule_event(
            "skill_resolved",
            actor_seat=player.seat,
            card_ids=tuple(card.id for card in cards),
            data={
                "skill_id": option.skill.skill_id,
                "skill_name": option.skill.name,
                "window": "response_conversion",
                "response_action": response_action,
                "effective_card_name": effective_card.name,
            },
        )
        return effective_card

    def weapon_skill_available(self, player: Player, skill_id: str) -> bool:
        """统一查询武器技能来源当前是否仍在装备区且有效。"""
        return self.skills.has_skill(player, skill_id)

    def cixiong_can_trigger(self, source: Player, target: Player) -> bool:
        return (
            source.general.gender != target.general.gender
            and self.weapon_skill_available(source, "weapon.cixiong")
        )

    def resolve_cixiong_choice(
        self, source: Player, target: Player, discarded: Optional[Card] = None
    ) -> bool:
        """目标弃一张手牌；未弃置则武器拥有者摸一张牌。"""
        if discarded is not None:
            if discarded not in target.hand:
                return False
            self.discard_from_hand(
                target, discarded, "雌雄双股剑弃置"
            )
            self.log.append(
                f"{target.general.name} 因【雌雄双股剑】弃置一张手牌"
            )
            return True
        moves = self.draw_to_hand(
            source, 1, reason="雌雄双股剑摸牌"
        )
        if not moves:
            return False
        self.log.append(
            f"{target.general.name} 选择令 {source.general.name} 摸一张牌"
        )
        return True

    def resolve_hanbing(
        self, source: Player, target: Player, chosen: list[Card]
    ) -> bool:
        """防止本次伤害并依次弃置目标至多两张现有牌。"""
        if not self.weapon_skill_available(source, "weapon.hanbing"):
            return False
        available = target.hand + target.equipment + target.judgment_area
        expected = min(2, len(available))
        unique = []
        for card in chosen:
            if all(existing.id != card.id for existing in unique):
                unique.append(card)
        if len(unique) != expected or any(card not in available for card in unique):
            return False
        for card in unique:
            if card in target.equipment:
                zone = "equipment"
            elif card in target.hand:
                zone = "hand"
            elif card in target.judgment_area:
                zone = "judgment"
            self.discard_from_zone(target, card, zone, "寒冰剑弃置")
        self.log.append(
            f"{source.general.name} 发动【寒冰剑】，防止伤害并弃置"
            f"{target.general.name} 的{len(unique)}张牌"
        )
        return True

    def discard_for_hanbing(self, target: Player, card: Card) -> bool:
        """逐次执行寒冰剑的弃牌，以便两次操作之间处理离区触发。"""
        if card in target.equipment:
            zone = "equipment"
        elif card in target.hand:
            zone = "hand"
        elif card in target.judgment_area:
            zone = "judgment"
        else:
            return False
        self.discard_from_zone(target, card, zone, "寒冰剑弃置")
        return True

    def resolve_guanshi(self, source: Player, chosen: list[Card]) -> bool:
        """弃置两张牌，令被【闪】抵消的【杀】继续生效。"""
        if not self.weapon_skill_available(source, "weapon.guanshi"):
            return False
        available = source.hand + [
            card for card in source.equipment if card.name != "贯石斧"
        ]
        unique = []
        for card in chosen:
            if all(existing.id != card.id for existing in unique):
                unique.append(card)
        if len(unique) != 2 or any(card not in available for card in unique):
            return False
        for card in unique:
            if card in source.equipment:
                zone = "equipment"
            else:
                zone = "hand"
            self.discard_from_zone(source, card, zone, "贯石斧技能代价")
        self.log.append(f"{source.general.name} 发动【贯石斧】，令【杀】仍生效")
        return True

    def resolve_qilin(
        self, source: Player, target: Player, mount: Card
    ) -> bool:
        if (
            not self.weapon_skill_available(source, "weapon.qilin")
            or mount not in target.equipment
            or mount.equipment_type not in ("offensive_mount", "defensive_mount")
        ):
            return False
        self.discard_from_zone(target, mount, "equipment", "麒麟弓弃置")
        self.log.append(
            f"{source.general.name} 发动【麒麟弓】，弃置"
            f"{target.general.name} 的【{mount.name}】"
        )
        return True

    def can_qinglong_follow_up(self, source: Player) -> bool:
        conversion_options = self.skills.play_conversion_options(
            source, "杀"
        )
        return (
            self.weapon_skill_available(source, "weapon.qinglong")
            and (
                any(card.name in ("杀", "火杀", "雷杀")
                    for card in source.hand)
                or any(
                    self.skills.conversion_candidates(
                        source, option
                    )
                    for option in conversion_options
                )
            )
        )

    def create_slash_event(
        self, player: Player, physical_cards: list[Card],
        targets: list[Player], effective_name: str = "杀",
        *, ignore_usage_limit: bool = False,
        ignore_distance: bool = False,
        consume_usage_limit: bool = True,
        cards_already_processing: bool = False,
        conversion_already_validated: bool = False,
    ) -> SlashEvent:
        """提交一张实体或转化【杀】，并冻结本次使用所需上下文。"""
        owned_cards = player.hand + player.equipment
        available_cards = (
            self.processing_area if cards_already_processing
            else owned_cards
        )
        if (
            not physical_cards
            or any(card not in available_cards for card in physical_cards)
        ):
            raise ValueError("用于【杀】的实体牌已经不在使用者区域内")
        excluded_cards = tuple(physical_cards)
        if (
            not ignore_usage_limit
            and not self.can_use_slash(player, excluded_cards)
        ):
            raise ValueError("本阶段使用【杀】的次数已达上限")
        was_last = (
            bool(player.hand) and not cards_already_processing
            and len(player.hand) == len(physical_cards)
            and all(card in player.hand for card in physical_cards)
        )
        limit = self.skills.slash_target_limit(
            player, was_last, excluded_cards
        )
        unique_targets = []
        for target in targets:
            if all(existing.seat != target.seat for existing in unique_targets):
                unique_targets.append(target)
        if (
            not unique_targets or len(unique_targets) > limit
            or any(
                not target.alive
                or self.same_player(target, player)
                for target in unique_targets
            )
        ):
            raise ValueError("【杀】的目标数量或目标状态不合法")
        for target in unique_targets:
            if not ignore_distance and not self.in_attack_range(
                player, target, excluded_cards
            ):
                raise ValueError("【杀】的目标不在攻击范围内")
        if len(physical_cards) == 2:
            if (
                not conversion_already_validated
                and not self.skills.can_convert_zhangba(
                    player, physical_cards
                )
            ):
                raise ValueError("当前不能发动【丈八蛇矛】")
            effective_name = "杀"
        elif len(physical_cards) != 1:
            raise ValueError("普通【杀】必须使用一张实体牌")
        elif effective_name != physical_cards[0].name:
            if conversion_already_validated or self.skills.can_convert_to(
                player, physical_cards, effective_name,
                SkillTiming.SLASH_CONVERSION,
            ):
                pass
            elif not (
                effective_name == "火杀"
                and self.skills.can_convert_zhuque(player, physical_cards[0])
            ):
                raise ValueError("当前不能改变【杀】的牌名或属性")
        physical = physical_cards[:]
        if not cards_already_processing and not self.stage_owned_cards_for_use(
            player,
            physical,
            reason="使用【杀】",
        ):
            raise ValueError("用于【杀】的实体牌已经不在使用者区域内")
        if consume_usage_limit:
            player.slash_use_count = max(
                player.slash_use_count,
                1 if player.slash_used else 0,
            ) + 1
            player.slash_used = True
        damage = max(1, player.turn_slash_base_damage) + (
            1 if player.drunk else 0
        )
        player.drunk = False
        nature = {
            "火杀": DamageNature.FIRE,
            "雷杀": DamageNature.THUNDER,
        }.get(effective_name, DamageNature.NORMAL)
        ignores = (
            {target.seat for target in unique_targets}
            if self.skills.slash_ignores_armor(
                player, excluded_cards
            ) else set()
        )
        effective_card = self.skills.build_effective_card(
            effective_name, physical
        )
        event = SlashEvent(
            slash_id=self._next_slash_id,
            source_player=player,
            physical_cards=physical,
            effective_name=effective_name,
            effective_card=effective_card,
            targets=unique_targets,
            damage=damage,
            nature=nature,
            ignores_armor_for=ignores,
            was_last_hand_card=was_last,
        )
        self.record_card_use(
            player,
            effective_card,
            tuple(physical),
            tuple(target.seat for target in unique_targets),
        )
        self._next_slash_id += 1
        self.publish_rule_event(
            "slash_created",
            actor_seat=player.seat,
            target_seats=tuple(target.seat for target in unique_targets),
            card_ids=tuple(card.id for card in physical),
            data={
                "slash_id": event.slash_id,
                "effective_card_name": event.effective_name,
                "damage": event.damage,
                "nature": event.nature.value,
            },
        )
        return event

    def create_forced_slash_event(
        self, player: Player, physical_cards: list[Card],
        target: Player, effective_name: str,
        *, ignore_distance: bool = False,
        cards_already_processing: bool = False,
        conversion_already_validated: bool = False,
    ) -> SlashEvent:
        """建立不受出牌阶段次数限制的【杀】使用事件。"""
        return self.create_slash_event(
            player,
            physical_cards,
            [target],
            effective_name,
            ignore_usage_limit=True,
            ignore_distance=ignore_distance,
            consume_usage_limit=False,
            cards_already_processing=cards_already_processing,
            conversion_already_validated=conversion_already_validated,
        )

    def toggle_chain(self, player: Player) -> bool:
        if not player.alive:
            return False
        player.chained = not player.chained
        state = "横置（连环）" if player.chained else "重置（解除连环）"
        self.log.append(f"{player.general.name} {state}")
        return True

    def play_iron_chain(
        self, player: Player, card: Card, targets: list[Player], apply_effect: bool = True
    ) -> bool:
        """使用铁索连环，依次切换一至两名角色的连环状态。"""
        unique_targets = []
        for target in targets:
            if target.alive and target not in unique_targets:
                unique_targets.append(target)
        if card not in player.hand or not 1 <= len(unique_targets) <= 2:
            return False
        player.hand.remove(card)
        self.discard(card)
        self.log.append(
            f"{player.general.name} 使用【铁索连环】，目标："
            + "、".join(target.general.name for target in unique_targets)
        )
        self.record_card_use(
            player,
            card,
            (card,),
            tuple(target.seat for target in unique_targets),
        )
        if apply_effect:
            for target in unique_targets:
                self.toggle_chain(target)
        return True

    def recast(self, player: Player, card: Card) -> Optional[Card]:
        """重铸铁索连环：弃置该牌并摸一张牌。"""
        if card not in player.hand or card.name != "铁索连环":
            return None
        player.hand.remove(card)
        self.discard(card)
        moves = self.draw_to_hand(
            player, 1, reason="铁索连环重铸摸牌"
        )
        if not moves:
            return None
        drawn = moves[0].card
        self.log.append(f"{player.general.name} 重铸【铁索连环】，摸一张牌")
        return drawn

    def get_next_alive(self, start: int) -> Optional[Player]:
        """从 start 开始找下一个存活的玩家"""
        n = len(self.state.players)
        for i in range(1, n + 1):
            idx = (start + i) % n
            if self.state.players[idx].alive:
                return self.state.players[idx]
        return None

    # ---- 距离与攻击范围 ----

    def seat_distance(self, source: Player, target: Player) -> int:
        """计算存活角色之间的基础座次距离；已阵亡角色不占距离。"""
        if self.same_player(source, target):
            return 0
        alive = [p for p in self.state.players if p.alive]
        alive_seats = [player.seat for player in alive]
        if (
            source.seat not in alive_seats
            or target.seat not in alive_seats
        ):
            return 999
        source_index = alive_seats.index(source.seat)
        target_index = alive_seats.index(target.seat)
        clockwise = (target_index - source_index) % len(alive)
        counterclockwise = (source_index - target_index) % len(alive)
        return min(clockwise, counterclockwise)

    def distance(self, source: Player, target: Player) -> int:
        """统一距离：基础座次距离－进攻马＋防御马，最小为1。"""
        if self.same_player(source, target):
            return 0
        result = self.seat_distance(source, target)
        if result >= 999:
            return result
        if any(card.equipment_type == "offensive_mount" for card in source.equipment):
            result -= 1
        if any(card.equipment_type == "defensive_mount" for card in target.equipment):
            result += 1
        return max(1, result)

    def attack_range(
        self, player: Player, excluded_cards: tuple[Card, ...] = ()
    ) -> int:
        """基础攻击范围为1；装备武器后使用对应武器范围。"""
        return self.skills.attack_range(player, excluded_cards)

    def in_attack_range(
        self, source: Player, target: Player,
        excluded_cards: tuple[Card, ...] = (),
    ) -> bool:
        return bool(
            target and target.alive
            and not self.same_player(source, target)
            and self.distance(source, target)
            <= self.attack_range(source, excluded_cards)
        )

    def get_slash_targets(self, player: Player) -> list[Player]:
        """按从当前角色顺时针的座次顺序返回可被杀的角色。"""
        n = len(self.state.players)
        ordered = [self.state.players[(player.seat + step) % n] for step in range(1, n)]
        return [target for target in ordered if self.in_attack_range(player, target)]

    def get_targets_within_distance(self, player: Player, maximum: int) -> list[Player]:
        n = len(self.state.players)
        ordered = [self.state.players[(player.seat + step) % n] for step in range(1, n)]
        return [target for target in ordered if target.alive and self.distance(player, target) <= maximum]

    def borrowed_sword_victims(self, wielder: Player) -> list[Player]:
        """借刀杀人中，返回持刀者攻击范围内可被指定的角色。"""
        return self.get_slash_targets(wielder)

    def transfer_weapon(self, source: Player, recipient: Player) -> Optional[Card]:
        weapon = next((card for card in source.equipment if card.equipment_type == "weapon"), None)
        if not weapon:
            return None
        self.remove_equipment(source, weapon)
        recipient.hand.append(weapon)
        self.log.append(f"{source.general.name} 将【{weapon.name}】交给 {recipient.general.name}")
        return weapon

    # ---- 回合流程 ----

    def start_turn(self):
        """开始当前玩家的回合"""
        player = self.get_current_player()
        # 重置本回合出杀标记
        for p in self.state.players:
            p.slash_used = False
            p.slash_use_count = 0
            p.active_slash_use_bonus = 0
            p.skill_usage_counts.clear()
            p.last_used_card = None
        player.wine_used = False
        player.draw_phase_card_count = 2
        player.turn_slash_base_damage = 1
        self.state.phase = Phase.PREPARE

    def begin_draw_phase(self, player: Player) -> DrawPhaseEvent:
        """建立摸牌阶段事件；技能只修改事件和角色回合状态。"""
        if (
            not player.alive
            or self.get_current_player().seat != player.seat
        ):
            raise ValueError("当前角色不能进入摸牌阶段")
        bonus = max(0, player.pending_draw_phase_bonus)
        player.pending_draw_phase_bonus = 0
        event = DrawPhaseEvent(
            player=player,
            base_draw_count=2 + bonus,
            draw_count=2 + bonus,
        )
        player.draw_phase_card_count = event.draw_count
        player.turn_slash_base_damage = 1
        self.skills.prepare_draw_phase(self, player, event)
        self.publish_rule_event(
            "draw_phase_started",
            actor_seat=player.seat,
            data={"draw_count": event.draw_count},
        )
        return event

    def place_delayed_trick(self, player: Player, card: Card, target: Optional[Player]) -> bool:
        """将延时锦囊置入判定区；同名延时锦囊不能重复存在。"""
        if card.name == "闪电":
            target = player if target is None else target
        if target is None or not target.alive:
            return False
        if (
            card.name in ("乐不思蜀", "兵粮寸断")
            and self.same_player(target, player)
        ):
            return False
        if card.name == "兵粮寸断" and self.distance(player, target) > 1:
            return False
        if any(existing.name == card.name for existing in target.judgment_area):
            return False
        target.judgment_area.append(card)
        self.log.append(f"{player.general.name} 将【{card.name}】置入 {target.general.name} 的判定区")
        return True

    def begin_next_judgment(self, player: Player) -> Optional[dict]:
        """开始判定区最先一张牌的判定，尚不冻结结果或执行牌效果。"""
        if not player.judgment_area:
            return None
        delayed = player.judgment_area.pop()
        rule = {
            "乐不思蜀": "not_heart",
            "兵粮寸断": "not_club",
            "闪电": "spade_2_9",
        }.get(delayed.name, "red")
        judgment = self.begin_judgment(
            player, delayed.name, rule, source_card=delayed
        )
        return {
            "delayed": delayed,
            "judged": judgment.current_card,
            "judgment": judgment,
            "effect": "none",
            "passed_to": None,
        }

    def finish_next_judgment(
        self, player: Player, result: dict, judgment: JudgmentEvent
    ) -> dict:
        """在所有替换结束后冻结判定，并执行延时锦囊的对应效果。"""
        if judgment.step != JudgmentStep.COMPLETED:
            judgment = self.finalize_judgment(judgment)
        delayed = result["delayed"]
        result["judgment"] = judgment
        result["judged"] = judgment.current_card
        if delayed.name == "乐不思蜀":
            if judgment.result:
                player.skip_play = True
                result["effect"] = "skip_play"
            self.discard(delayed)
        elif delayed.name == "兵粮寸断":
            if judgment.result:
                player.skip_draw = True
                result["effect"] = "skip_draw"
            self.discard(delayed)
        elif delayed.name == "闪电":
            if judgment.result:
                result["effect"] = "lightning_damage"
                self.begin_processing_card(delayed)
            else:
                next_player = self.get_next_alive(player.seat)
                if (
                    next_player
                    and not self.same_player(next_player, player)
                    and not any(
                        c.name == "闪电"
                        for c in next_player.judgment_area
                    )
                ):
                    next_player.judgment_area.append(delayed)
                    result["effect"] = "lightning_pass"
                    result["passed_to"] = next_player
                else:
                    result["effect"] = "lightning_return"
        else:
            self.discard(delayed)
        return result

    def resolve_next_judgment(self, player: Player) -> Optional[dict]:
        """同步结算无外部改判窗口的一张判定区牌。"""
        result = self.begin_next_judgment(player)
        if result is None:
            return None
        return self.finish_next_judgment(
            player, result, result["judgment"]
        )

    def transfer_lightning(
        self, current_owner: Player, lightning: Card
    ) -> Optional[Player]:
        """闪电效果被抵消或判定未命中后移入下一合法角色的判定区。"""
        if lightning not in current_owner.judgment_area:
            return None
        current_owner.judgment_area.remove(lightning)
        players = self.state.players
        for offset in range(1, len(players)):
            candidate = players[
                (current_owner.seat + offset) % len(players)
            ]
            if (
                candidate.alive
                and not any(
                    card.name == "闪电"
                    for card in candidate.judgment_area
                )
            ):
                candidate.judgment_area.append(lightning)
                return candidate
        current_owner.judgment_area.append(lightning)
        return current_owner

    def draw_phase(self, player: Player):
        """摸牌阶段：摸 2 张"""
        self.draw_to_hand(
            player,
            player.draw_phase_card_count,
            reason="摸牌阶段",
        )

    def play_card(self, player: Player, card: Card, target: Optional[Player] = None) -> bool:
        """玩家打出一张牌，返回是否成功"""
        if card not in player.hand:
            return False
        if (
            target is not None
            and self.skills.prohibits_card_target(
                self, player, target, card
            )
        ):
            return False
        card_index = player.hand.index(card)
        player.hand.remove(card)

        if card.name in ("杀", "火杀", "雷杀"):
            played = self._play_slash(player, target, card.name)
        elif card.name == "桃":
            played = self._play_peach(player, target)
        elif card.name == "闪":
            played = False  # 闪不能在出牌阶段主动打出
        elif card.name == "酒":
            if player.wine_used:
                played = False
            else:
                player.wine_used = True
                player.drunk = True
                self.log.append(f"{player.general.name} 使用【酒】")
                played = True
        elif card.kind == CardKind.EQUIPMENT:
            played = self._equip(player, card)
        elif card.kind == CardKind.TRICK:
            if card.name in ("乐不思蜀", "兵粮寸断", "闪电"):
                # 延时锦囊先离开手牌，无懈结算通过后再置入判定区。
                played = self.can_place_delayed_trick(player, card, target)
            else:
                played = self._play_trick(player, card, target)
        else:
            self.discard(card)
            played = True

        if not played:
            player.hand.insert(card_index, card)
        else:
            self.record_card_use(
                player,
                card,
                (card,),
                ((target.seat,) if target is not None else ()),
            )
            if (
                card.kind == CardKind.TRICK
                and card.name in (
                    *DAMAGE_TRICK_NAMES,
                    "过河拆桥",
                    "顺手牵羊",
                )
            ):
                self.begin_processing_card(card)
        return played

    def _equip(self, player: Player, card: Card) -> bool:
        """将装备放入对应槽位；同槽旧装备进入弃牌堆。"""
        if not card.equipment_type:
            return False
        old = next(
            (equipped for equipped in player.equipment
             if equipped.equipment_type == card.equipment_type),
            None,
        )
        if old is not None:
            self.remove_equipment(player, old)
            self.discard(old)
            self.log.append(f"{player.general.name} 替换了装备【{old.name}】")
        player.equipment.append(card)
        order = {"weapon": 0, "armor": 1, "offensive_mount": 2, "defensive_mount": 3}
        player.equipment.sort(key=lambda equipped: order.get(equipped.equipment_type, 99))
        self.log.append(f"{player.general.name} 装备了【{card.name}】")
        return True

    def _play_slash(self, player: Player, target: Optional[Player], card_name: str = "杀") -> bool:
        if target is None or not self.in_attack_range(player, target):
            return False
        # 一回合只能出一张杀
        if not self.can_use_slash(player):
            return False
        player.slash_use_count = max(
            player.slash_use_count,
            1 if player.slash_used else 0,
        ) + 1
        player.slash_used = True
        # 先建立【杀】的基础伤害，再逐项叠加增减伤修正。
        # 【酒】是独立的 +1，避免将最终伤害直接固定成 2。
        player.pending_slash_damage = max(
            1, player.turn_slash_base_damage
        )
        player.pending_slash_nature = {
            "火杀": DamageNature.FIRE,
            "雷杀": DamageNature.THUNDER,
        }.get(card_name, DamageNature.NORMAL)
        if player.drunk:
            player.pending_slash_damage += 1
        player.drunk = False
        self.log.append(f"{player.general.name} 对 {target.general.name} 使用【{card_name}】")
        # 是否出闪由外部处理
        return True

    def _play_peach(self, player: Player, target: Optional[Player]) -> bool:
        if target is None:
            target = player
        if target.hp < target.max_hp:
            target.hp += 1
            self.log.append(f"{target.general.name} 回复 1 点体力 ({target.hp}/{target.max_hp})")
            return True
        return False

    def _play_trick(self, player: Player, card: Card, target: Optional[Player]) -> bool:
        # 简化的锦囊处理
        if card.name == "铁索连环":
            # 铁索具有一至两名目标/重铸两种模式，调用专用接口处理。
            return False
        if card.name == "火攻":
            return bool(target and target.alive and target.hand)
        if card.name in ("过河拆桥", "顺手牵羊"):
            if (
                target is None or not target.alive
                or self.same_player(target, player)
                or not (
                    target.hand or target.equipment
                    or target.judgment_area
                )
            ):
                return False
            if card.name == "顺手牵羊" and self.distance(player, target) > 1:
                return False
            self.log.append(f"{player.general.name} 对 {target.general.name} 使用【{card.name}】")
            return True
        if card.name == "借刀杀人":
            weapon = next((c for c in target.equipment if c.equipment_type == "weapon"), None) if target else None
            if (
                target is None
                or self.same_player(target, player)
                or not target.alive or not weapon
                or not self.borrowed_sword_victims(target)
            ):
                return False
            self.log.append(f"{player.general.name} 对 {target.general.name} 使用【借刀杀人】")
            self.discard(card)
            return True
        if card.name == "五谷丰登":
            self.log.append(f"{player.general.name} 使用【五谷丰登】")
            self.discard(card)
            return True
        if card.name == "决斗":
            if (
                target is None or not target.alive
                or self.same_player(target, player)
            ):
                return False
            self._duel(player, target)
            return True
        if card.name in ("无中生有", "桃园结义", "南蛮入侵", "万箭齐发", "万剑齐发"):
            return True
        # 其他锦囊暂不处理
        self.discard(card)
        return True

    def can_place_delayed_trick(self, player: Player, card: Card, target: Optional[Player]) -> bool:
        """只校验延时锦囊目标，不在无懈结算前改变判定区。"""
        if card.name == "闪电":
            target = player if target is None else target
        if target is None or not target.alive:
            return False
        if self.skills.prohibits_card_target(
            self, player, target, card
        ):
            return False
        if (
            card.name in ("乐不思蜀", "兵粮寸断")
            and self.same_player(target, player)
        ):
            return False
        if card.name == "兵粮寸断" and self.distance(player, target) > 1:
            return False
        return not any(existing.name == card.name for existing in target.judgment_area)

    def resolve_target_card_trick(
        self, player: Player, trick_name: str, target: Player, card: Card,
        source_card: Optional[Card] = None,
    ) -> bool | TrickCardDiscardEvent:
        """结算过河拆桥/顺手牵羊中由界面选定的目标牌。"""
        if trick_name not in ("过河拆桥", "顺手牵羊"):
            return False
        if card in target.hand:
            zone = "hand"
        elif card in target.equipment:
            zone = "equipment"
        elif card in target.judgment_area:
            zone = "judgment"
        else:
            return False
        if trick_name == "过河拆桥":
            move = self.discard_from_zone(
                target, card, zone, "过河拆桥弃置"
            )
            if move is None:
                return False
            self.log.append(f"{player.general.name} 拆掉了 {target.general.name} 的一张牌")
            return TrickCardDiscardEvent(
                actor=player,
                target=target,
                trick_name=trick_name,
                source_card=source_card,
                discarded_card=card,
                move_event=move,
            )
        elif trick_name == "顺手牵羊":
            if zone == "hand":
                target.hand.remove(card)
            elif zone == "equipment":
                self.remove_equipment(target, card)
            else:
                target.judgment_area.remove(card)
            player.hand.append(card)
            self.log.append(f"{player.general.name} 获得了 {target.general.name} 的一张牌")
        return True

    def _dismantle(self, player: Player, target: Optional[Player]):
        if target and target.hand:
            removed = random.choice(target.hand)
            target.hand.remove(removed)
            self.discard(removed)
            self.log.append(f"{player.general.name} 拆掉了 {target.general.name} 的一张牌")

    def _snatch(self, player: Player, target: Optional[Player]):
        if target and target.hand:
            stolen = random.choice(target.hand)
            target.hand.remove(stolen)
            player.hand.append(stolen)
            self.log.append(f"{player.general.name} 顺走了 {target.general.name} 的一张牌")

    def _duel(self, player: Player, target: Optional[Player]):
        # 决斗的逐轮出【杀】与伤害结算由 UI 响应流程处理。
        if (
            target and target.alive
            and not self.same_player(target, player)
        ):
            self.log.append(f"{player.general.name} 对 {target.general.name} 发起【决斗】")

    def _amazing_grace(self):
        for p in self.get_alive_players():
            self.recover(p)
        self.log.append("桃园结义：全体回复 1 点体力")

    def _five_grains(self, player: Player):
        cards = self.draw_cards(len(self.get_alive_players()))
        for i, p in enumerate(self.get_alive_players()):
            if i < len(cards):
                p.hand.append(cards[i])

    # ---- 伤害与死亡 ----

    def recover(self, target: Player, amount: int = 1) -> int:
        """统一回复入口，返回实际回复量且不得超过体力上限。"""
        if not target.alive or amount <= 0:
            return 0
        before = target.hp
        target.hp = min(target.max_hp, target.hp + amount)
        return target.hp - before

    def take_damage(
        self, target: Player, damage: int = 1, check_death: bool = True,
        damage_event: Optional[DamageEvent] = None,
    ):
        target.hp -= damage
        physical_cards = (
            damage_event.source_physical_cards if damage_event else ()
        )
        source_card = damage_event.source_card if damage_event else None
        card_ids = tuple(card.id for card in physical_cards)
        if not card_ids and source_card is not None:
            card_ids = (source_card.id,)
        self.publish_rule_event(
            "damage_applied",
            actor_seat=(
                damage_event.source_player.seat
                if damage_event and damage_event.source_player else None
            ),
            target_seats=(target.seat,),
            card_ids=card_ids,
            data={
                "amount": damage,
                "hp_after": target.hp,
                "nature": (
                    damage_event.nature.value
                    if damage_event else DamageNature.NORMAL.value
                ),
            },
        )
        if check_death and target.hp <= 0:
            self._kill_check(target)

    def triggered_skill_actions(
        self, player: Player, timing, event: object
    ):
        return self.skills.triggered_actions(self, player, timing, event)

    def global_triggered_skill_actions(self, timing, event: object):
        return self.skills.global_triggered_actions(self, timing, event)

    def active_skill_actions(self, player: Player):
        return self.skills.active_skill_actions(self, player)

    def can_submit_active_skill(
        self, action, cards: tuple[Card, ...],
        targets: tuple[Player, ...],
    ) -> bool:
        return self.skills.validate_active_skill(
            self, action, cards, targets
        )

    def submit_active_skill(
        self, action, cards: tuple[Card, ...],
        targets: tuple[Player, ...],
    ):
        if not self.can_submit_active_skill(action, cards, targets):
            raise ValueError("主动技能的牌、目标或发动时机已经失效")
        result = self.skills.resolve_active_skill(
            self, action, cards, targets
        )
        if result.applied:
            self.publish_rule_event(
                "skill_resolved",
                actor_seat=action.controller.seat,
                target_seats=tuple(target.seat for target in targets),
                card_ids=tuple(card.id for card in cards),
                data={
                    "skill_id": action.skill.skill_id,
                    "skill_name": action.skill.name,
                    "window": "active_play",
                },
            )
        return result

    def resolve_triggered_skill(self, action):
        result = self.skills.resolve_triggered_action(self, action)
        if result.applied:
            self.publish_rule_event(
                "skill_resolved",
                actor_seat=action.controller.seat,
                data={
                    "skill_id": action.skill.skill_id,
                    "skill_name": action.skill.name,
                },
            )
        return result

    def _kill_check(self, target: Player):
        """简化死亡检查。UI 层会处理完整的濒死求桃流程。"""
        if target.hp > 0:
            return
        self.finalize_death(target)

    def finalize_death(self, target: Player) -> bool:
        """濒死结算确认失败后唯一允许正式宣告死亡的入口。"""
        if not target.alive or target.hp > 0:
            return False
        target.alive = False
        self.discard_all_player_cards(target)
        self.log.append(f"{target.general.name} 阵亡！")
        self.publish_rule_event(
            "player_died",
            actor_seat=target.seat,
            target_seats=(target.seat,),
            data={
                "general_id": target.general.id,
                "general_name": target.general.name,
                "skin_id": target.skin_id,
            },
        )
        self.check_winner()
        return True

    def discard_all_player_cards(self, player: Player):
        """死亡等系统清理统一经过牌区出口，避免装备残留或重复移动。"""
        for card in player.hand[:]:
            self.discard_from_zone(player, card, "hand", "死亡清理")
        for card in player.equipment[:]:
            self.discard_from_zone(
                player, card, "equipment", "死亡清理"
            )
        for card in player.judgment_area[:]:
            self.discard_from_zone(
                player, card, "judgment", "死亡清理"
            )

    # ---- 结束回合 ----

    def hand_limit(self, player: Optional[Player] = None) -> int:
        """当前手牌上限"""
        if player is None:
            player = self.get_current_player()
        return max(0, player.hp)

    def discard_cards(self, player: Player, cards: list[Card]):
        """弃掉指定手牌"""
        for card in cards:
            if card in player.hand:
                self.discard_from_hand(player, card, "弃牌阶段")

    def finish_turn(self):
        """真正结束回合，进入下一名玩家"""
        player = self.get_current_player()
        # 【酒】只在当前回合内有效；若本回合没有出杀，回合结束时清除。
        player.drunk = False
        player.pending_slash_damage = 1
        player.pending_slash_nature = DamageNature.NORMAL
        player.draw_phase_card_count = 2
        player.turn_slash_base_damage = 1

        # 检查胜利条件
        self.check_winner()
        if self.state.winner is not None:
            return

        # 轮到下一位
        n = len(self.state.players)
        for _ in range(n):
            self.state.current_turn = (self.state.current_turn + 1) % n
            if self.state.players[self.state.current_turn].alive:
                break
        self.state.turn_count += 1
        self.state.phase = Phase.PREPARE

    def check_winner(self) -> Optional[Player]:
        """敌对存活人数清零时立即记录获胜武将。"""
        if self.state.winner_seat is not None:
            return next(
                (
                    player for player in self.state.players
                    if player.seat == self.state.winner_seat
                ),
                None,
            )
        alive = self.get_alive_players()
        winner = next(
            (
                player for player in alive
                if not self.get_alive_enemies(player)
            ),
            None,
        )
        if winner is None:
            return None
        self.state.winner = winner.general.name
        self.state.winner_seat = winner.seat
        return winner



