import json
import unittest

from src.engine import GameEngine
from src.models import (
    Card, CardKind, General, Player, PlayerChoice, PromptContext,
    PromptType,
)


def make_player(seat):
    return Player(
        seat=seat,
        general=General(
            id=f"g{seat}",
            name=f"角色{seat}",
            kingdom="魏",
            hp=4,
        ),
        hp=4,
        max_hp=4,
    )


def make_card(card_id):
    return Card(
        id=card_id,
        name="测试牌",
        suit="heart",
        rank="7",
        kind=CardKind.BASIC,
    )


class SerializableProtocolTest(unittest.TestCase):
    def test_prompt_context_contains_only_serializable_public_data(self):
        prompt = PromptContext(
            prompt_id=12,
            prompt_type=PromptType.CHOOSE_TARGET,
            player_seat=0,
            message="请选择目标",
            legal_card_ids=("card-1",),
            legal_target_seats=(1,),
            required_cards=1,
        )
        payload = json.loads(prompt.model_dump_json())
        self.assertEqual(payload["player_seat"], 0)
        self.assertEqual(payload["legal_target_seats"], [1])
        self.assertNotIn("player", payload)
        self.assertFalse(any(
            "callback" in key for key in payload
        ))

    def test_player_choice_round_trips_as_ids_and_seats(self):
        choice = PlayerChoice(
            prompt_id=12,
            player_seat=0,
            confirmed=True,
            card_ids=("card-1",),
            target_seats=(1,),
        )
        restored = PlayerChoice.model_validate_json(
            choice.model_dump_json()
        )
        self.assertEqual(restored, choice)

    def test_engine_rejects_stale_duplicate_and_illegal_choices(self):
        prompt = PromptContext(
            prompt_id=12,
            prompt_type=PromptType.CHOOSE_CARDS,
            player_seat=0,
            message="请选择一张牌",
            legal_card_ids=("card-1", "card-2"),
            required_cards=1,
        )
        valid = PlayerChoice(
            prompt_id=12,
            player_seat=0,
            confirmed=True,
            card_ids=("card-1",),
        )
        self.assertTrue(GameEngine.validate_player_choice(prompt, valid))
        self.assertFalse(GameEngine.validate_player_choice(
            prompt, valid.model_copy(update={"prompt_id": 11})
        ))
        self.assertFalse(GameEngine.validate_player_choice(
            prompt,
            valid.model_copy(update={"card_ids": ("card-1", "card-1")}),
        ))
        self.assertFalse(GameEngine.validate_player_choice(
            prompt,
            valid.model_copy(update={"card_ids": ("illegal",)}),
        ))

    def test_combined_card_and_target_choice_uses_one_command(self):
        prompt = PromptContext(
            prompt_id=21,
            prompt_type=PromptType.CONFIRM_ACTION,
            player_seat=0,
            message="请选择一张牌和一名目标",
            legal_card_ids=("red-card",),
            legal_target_seats=(1, 2),
            required_cards=1,
            required_targets=1,
            window="play_conversion",
        )
        choice = PlayerChoice(
            prompt_id=21,
            player_seat=0,
            confirmed=True,
            card_ids=("red-card",),
            target_seats=(2,),
            option_id="general.wusheng",
        )
        self.assertTrue(GameEngine.validate_player_choice(prompt, choice))
        self.assertFalse(GameEngine.validate_player_choice(
            prompt, choice.model_copy(update={"target_seats": ()})
        ))
        self.assertFalse(GameEngine.validate_player_choice(
            prompt, choice.model_copy(update={"card_ids": ()})
        ))

    def test_engine_rule_events_are_ordered_and_serializable(self):
        owner = make_player(0)
        target = make_player(1)
        moved = make_card("move-card")
        engine = GameEngine([owner, target], [])
        engine.processing_area.append(moved)
        engine.gain_from_processing(
            owner, moved, "测试获得", visibility="private"
        )
        hp_event = engine.lose_hp(
            target, 2, reason="协议测试"
        )
        self.assertIsNotNone(hp_event)
        events = engine.drain_rule_events()
        self.assertEqual(
            [event.event_type for event in events],
            ["card_moved", "hp_lost"],
        )
        self.assertEqual(
            [event.event_id for event in events], [1, 2]
        )
        self.assertEqual(events[0].recipient_seats, (owner.seat,))
        for event in events:
            json.loads(event.model_dump_json())
        self.assertEqual(engine.drain_rule_events(), [])


if __name__ == "__main__":
    unittest.main()
