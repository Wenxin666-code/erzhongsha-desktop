import unittest
from pathlib import Path

from main import GameUI
from src.engine import GameEngine
from src.loader import load_generals
from src.models import (
    Card, CardKind, CardUseEvent, DamageEvent, DamageNature, General,
    GeneralSkillRef, Phase, Player, SkillTiming,
)


ROOT = Path(__file__).resolve().parents[1]


def make_card(
    card_id, name="测试牌", suit="heart", rank="7",
    kind=CardKind.BASIC,
):
    return Card(
        id=card_id,
        name=name,
        suit=suit,
        rank=rank,
        kind=kind,
    )


def make_player(seat, name, *, sunqinke=False, is_ai=False):
    skills = []
    if sunqinke:
        skills = [
            GeneralSkillRef(
                skill_id="general.sunqinke.novel", name="小说"
            ),
            GeneralSkillRef(
                skill_id="general.sunqinke.sunsun", name="孙孙"
            ),
            GeneralSkillRef(
                skill_id="general.sunqinke.kongju", name="控局"
            ),
        ]
    return Player(
        seat=seat,
        general=General(
            id="sunqinke" if sunqinke else f"general-{seat}",
            name=name,
            kingdom="神" if sunqinke else "魏",
            hp=4,
            gender="female" if sunqinke else "male",
            playable=True,
            skills=skills,
        ),
        hp=4,
        max_hp=4,
        is_ai=is_ai,
    )


class SunQinkeSkillTest(unittest.TestCase):
    def test_general_is_registered_and_playable(self):
        general = next(
            general for general in load_generals(
                ROOT / "data" / "generals.yml"
            )
            if general.id == "sunqinke"
        )
        self.assertTrue(general.playable)
        self.assertEqual(general.hp, 4)
        self.assertEqual(general.gender, "female")
        self.assertEqual(
            [skill.skill_id for skill in general.skills],
            [
                "general.sunqinke.novel",
                "general.sunqinke.sunsun",
                "general.sunqinke.kongju",
            ],
        )

    def test_novel_draws_two_then_distributes_each_card(self):
        sun = make_player(0, "孙沁珂", sunqinke=True)
        target = make_player(1, "目标")
        engine = GameEngine(
            [sun, target],
            [make_card("draw-a"), make_card("draw-b")],
        )
        action = engine.triggered_skill_actions(
            sun, SkillTiming.AFTER_DAMAGE,
            DamageEvent(amount=1, source_player=target),
        )[0]

        result = engine.resolve_triggered_skill(action)

        self.assertTrue(result.applied)
        self.assertEqual(len(sun.hand), 2)
        draw_event = engine.draw_event_history[-1]
        self.assertEqual(draw_event.player.seat, sun.seat)
        self.assertEqual(draw_event.count, 2)
        self.assertEqual(draw_event.reason, "小说摸牌")
        self.assertEqual(
            draw_event.cards,
            tuple(move.card for move in result.move_events),
        )
        self.assertEqual(
            len({move.batch_id for move in result.move_events}), 1
        )
        self.assertTrue(all(
            move.batch_size == 2
            for move in result.move_events
        ))
        self.assertEqual(result.request.kind, "choose_target")
        first_id = result.request.context["remaining_card_ids"][0]
        first_card = next(card for card in sun.hand if card.id == first_id)

        first_distribution = engine.skills.continue_triggered_action(
            engine, action, result.request, target
        )
        self.assertIn(first_card, target.hand)
        self.assertNotIn(first_card, sun.hand)
        self.assertIsNotNone(first_distribution.request)

        second_distribution = engine.skills.continue_triggered_action(
            engine, action, first_distribution.request, sun
        )
        self.assertIsNone(second_distribution.request)
        self.assertEqual(len(sun.hand), 1)
        self.assertEqual(len(target.hand), 1)

    def test_novel_ai_keeps_cards_in_one_on_one(self):
        sun = make_player(
            0, "孙沁珂", sunqinke=True, is_ai=True
        )
        enemy = make_player(1, "敌方")
        engine = GameEngine(
            [sun, enemy],
            [make_card("draw-a"), make_card("draw-b")],
        )
        action = engine.triggered_skill_actions(
            sun, SkillTiming.AFTER_DAMAGE,
            DamageEvent(amount=1, source_player=enemy),
        )[0]
        result = engine.resolve_triggered_skill(action)

        self.assertTrue(
            engine.skills.ai_should_activate_triggered(engine, action)
        )
        self.assertIs(
            engine.skills.ai_choose_triggered_target(
                engine, action, result.request
            ),
            sun,
        )

    def test_sunsun_matches_standard_suit_or_point(self):
        sun = make_player(0, "孙沁珂", sunqinke=True)
        enemy = make_player(1, "敌方")
        engine = GameEngine([sun, enemy], [make_card("draw")])
        previous = make_card("previous", suit="heart", rank="5")

        same_suit = CardUseEvent(
            player=sun,
            effective_card=make_card(
                "same-suit", suit="heart", rank="9"
            ),
            previous_card=previous,
        )
        same_rank = CardUseEvent(
            player=sun,
            effective_card=make_card(
                "same-rank", suit="spade", rank="5"
            ),
            previous_card=previous,
        )
        no_match = CardUseEvent(
            player=sun,
            effective_card=make_card(
                "different", suit="spade", rank="9"
            ),
            previous_card=previous,
        )

        self.assertEqual(len(engine.triggered_skill_actions(
            sun, SkillTiming.CARD_USE, same_suit
        )), 1)
        self.assertEqual(len(engine.triggered_skill_actions(
            sun, SkillTiming.CARD_USE, same_rank
        )), 1)
        self.assertEqual(engine.triggered_skill_actions(
            sun, SkillTiming.CARD_USE, no_match
        ), [])
        self.assertEqual(engine.triggered_skill_actions(
            sun, SkillTiming.AFTER_CARD_USE, same_suit
        ), [])

    def test_sunsun_does_not_treat_no_suit_as_a_matching_suit(self):
        sun = make_player(0, "孙沁珂", sunqinke=True)
        enemy = make_player(1, "敌方")
        engine = GameEngine([sun, enemy], [])
        event = CardUseEvent(
            player=sun,
            effective_card=make_card(
                "current", suit="no_suit", rank="8"
            ),
            previous_card=make_card(
                "previous", suit="no_suit", rank="9"
            ),
        )

        self.assertEqual(engine.triggered_skill_actions(
            sun, SkillTiming.CARD_USE, event
        ), [])

    def test_sunsun_only_triggers_during_owners_turn(self):
        current = make_player(0, "当前角色")
        sun = make_player(1, "孙沁珂", sunqinke=True)
        engine = GameEngine([current, sun], [])
        event = CardUseEvent(
            player=sun,
            effective_card=make_card("current", rank="5"),
            previous_card=make_card("previous", rank="5"),
        )

        self.assertEqual(engine.triggered_skill_actions(
            sun, SkillTiming.CARD_USE, event
        ), [])

    def test_nullification_used_in_owners_judgment_phase_counts_for_sunsun(self):
        sun = make_player(0, "孙沁珂", sunqinke=True)
        enemy = make_player(1, "敌方")
        engine = GameEngine(
            [sun, enemy], [make_card("draw")]
        )
        engine.state.phase = Phase.JUDGE
        previous = make_card(
            "previous", "桃", suit="spade", rank="7"
        )
        nullification = make_card(
            "nullification",
            "无懈可击",
            suit="spade",
            rank="J",
            kind=CardKind.TRICK,
        )

        engine.record_card_use(sun, previous, (previous,))
        event = engine.record_card_use(
            sun, nullification, (nullification,)
        )
        actions = engine.triggered_skill_actions(
            sun, SkillTiming.CARD_USE, event
        )

        self.assertEqual(len(actions), 1)
        self.assertEqual(
            actions[0].skill.skill_id,
            "general.sunqinke.sunsun",
        )
        self.assertEqual(
            sun.last_used_card.id, nullification.id
        )

    def test_third_sunsun_draw_opens_optional_fire_damage_target(self):
        sun = make_player(0, "孙沁珂", sunqinke=True)
        enemy = make_player(1, "敌方")
        engine = GameEngine(
            [sun, enemy],
            [
                make_card("draw-1"),
                make_card("draw-2"),
                make_card("draw-3"),
            ],
        )
        event = CardUseEvent(
            player=sun,
            effective_card=make_card("current", rank="5"),
            previous_card=make_card("previous", rank="5"),
        )
        third_result = None
        action = None
        for _ in range(3):
            action = engine.triggered_skill_actions(
                sun, SkillTiming.CARD_USE, event
            )[0]
            third_result = engine.resolve_triggered_skill(action)

        self.assertEqual(len(sun.hand), 3)
        self.assertEqual(third_result.request.kind, "choose_target")
        self.assertTrue(third_result.request.optional)

        damage_result = engine.skills.continue_triggered_action(
            engine, action, third_result.request, enemy
        )
        self.assertEqual(damage_result.request.kind, "damage")
        self.assertEqual(
            damage_result.request.context.nature,
            DamageNature.FIRE,
        )
        self.assertEqual(damage_result.request.context.amount, 1)
        self.assertIs(
            damage_result.request.context.source_player, sun
        )

    def test_card_use_record_freezes_previous_effective_card(self):
        sun = make_player(0, "孙沁珂", sunqinke=True)
        enemy = make_player(1, "敌方")
        engine = GameEngine([sun, enemy], [])
        first = make_card("first", "酒", suit="heart", rank="7")
        second = make_card("second", "桃", suit="heart", rank="9")

        first_event = engine.record_card_use(sun, first, (first,))
        second_event = engine.record_card_use(sun, second, (second,))

        self.assertIsNone(first_event.previous_card)
        self.assertEqual(second_event.previous_card.id, first.id)
        self.assertEqual(sun.last_used_card.id, second.id)

    def test_sunsun_card_use_window_precedes_slash_target_response(self):
        sun = make_player(0, "孙沁珂", sunqinke=True)
        enemy = make_player(1, "敌方")
        engine = GameEngine([sun, enemy], [make_card("draw")])
        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        ui.card_use_event_queue = []
        ui.card_use_trigger_in_progress = False
        ui.wd = False
        ui.dt = None
        ui.da = None
        ui.active_prompt = None
        ui.target_card_choice = None
        ui.five_grains_choice = None
        ui.borrowed_sword_choice = None
        ui.fire_attack_context = None
        ui.judgment_display_in_progress = False
        ui.animations = []
        ui.resolution_stack = []
        ui.next_prompt_id = 1
        ui.prompt_handlers = {}
        ui.skill_prompt_cards = []
        ui.skill_prompt_required_cards = 0
        ui.skill_prompt_selected = set()
        ui.skill_prompt_targets = []
        ui.skill_prompt_selected_target = None
        ui.response_time_remaining = 0
        ui.response_timer_last_tick = 0
        ui.ai_response_at = 0
        ui.ai_busy = False
        ui.go = False
        ui.hint = lambda *_args, **_kwargs: None
        engine.card_use_listener = ui._on_engine_card_use

        first = make_card("first", suit="heart", rank="7")
        second = make_card("second", "杀", suit="heart", rank="9")
        engine.record_card_use(sun, first)
        engine.record_card_use(sun, second)
        self.assertIsNone(ui.active_prompt)

        resumed = []
        ui._resolve_slash_targeted = (
            lambda *_args: resumed.append("slash_response")
        )
        ui._after_slash_targeted(enemy, sun, second)

        self.assertTrue(ui.card_use_trigger_in_progress)
        self.assertEqual(resumed, [])
        self.assertEqual(
            ui.active_prompt.skill_id,
            "general.sunqinke.sunsun",
        )

        prompt_id = ui.active_prompt.prompt_id
        ui.msg = lambda *_args, **_kwargs: None
        ui.play_equipment_sound = lambda *_args, **_kwargs: None
        ui.clear_hint = lambda: None
        ui._present_skill_resolution = (
            lambda _result, on_complete, action=None: on_complete()
        )

        self.assertTrue(ui._submit_skill_prompt(prompt_id, True))
        self.assertFalse(ui.card_use_trigger_in_progress)
        self.assertFalse(ui.wd)
        self.assertIsNone(ui.dt)
        self.assertIsNone(ui.da)
        self.assertIsNone(ui.active_prompt)
        self.assertEqual(resumed, ["slash_response"])

    def test_kongju_prohibits_three_named_cards_without_disabling_card(self):
        source = make_player(0, "来源")
        sun = make_player(1, "孙沁珂", sunqinke=True)
        sun.hand = [make_card("target-hand")]
        engine = GameEngine([source, sun], [])
        engine.state.phase = Phase.PLAY

        for index, name in enumerate(
            ("过河拆桥", "顺手牵羊", "乐不思蜀")
        ):
            card = make_card(
                f"trick-{index}", name, kind=CardKind.TRICK
            )
            source.hand = [card]
            self.assertTrue(engine.can_select_play_card(source, card))
            self.assertFalse(
                engine.is_legal_play_target(source, card, sun)
            )
            self.assertFalse(engine.play_card(source, card, sun))
            self.assertIn(card, source.hand)

        duel = make_card(
            "duel", "决斗", kind=CardKind.TRICK
        )
        source.hand = [duel]
        self.assertTrue(
            engine.is_legal_play_target(source, duel, sun)
        )


if __name__ == "__main__":
    unittest.main()
