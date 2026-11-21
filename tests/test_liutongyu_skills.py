import unittest

import pygame

from main import GameUI
from src.engine import GameEngine
from src.models import (
    Card, CardKind, CardRevealEvent, DamageEvent, DamageNature, General,
    GeneralSkillRef, Phase, Player, PlayerChoice, SkillTiming,
)


def make_card(card_id, suit, name="测试牌", kind=CardKind.BASIC):
    return Card(
        id=card_id,
        name=name,
        suit=suit,
        rank="2",
        kind=kind,
    )


def make_player(seat, *, liutongyu=False, hp=4, is_ai=False):
    skills = []
    general_id = f"general-{seat}"
    name = f"角色{seat}"
    gender = "male"
    if liutongyu:
        general_id = "liutongyu"
        name = "刘桐羽"
        gender = "female"
        skills = [
            GeneralSkillRef(
                skill_id="general.this_is_nonsense", name="这不扯淡吗"
            ),
            GeneralSkillRef(
                skill_id="general.wild_association", name="瞎联想"
            ),
            GeneralSkillRef(skill_id="general.jinren", name="金仁"),
        ]
    return Player(
        seat=seat,
        general=General(
            id=general_id,
            name=name,
            kingdom="神" if liutongyu else "魏",
            hp=4,
            gender=gender,
            skills=skills,
        ),
        hp=hp,
        max_hp=4,
        is_ai=is_ai,
    )


class LiuTongyuSkillTest(unittest.TestCase):
    def test_after_damage_is_distinct_from_when_damaged(self):
        owner = make_player(1, liutongyu=True, hp=2)
        current = make_player(0)
        owner.hand = [make_card("old-red", "heart")]
        engine = GameEngine([current, owner], [])
        engine.draw_pile = [make_card("drawn-red", "diamond")]
        event = DamageEvent(amount=1, source_player=current)

        before = engine.triggered_skill_actions(
            owner, SkillTiming.WHEN_DAMAGED, event
        )
        engine.take_damage(
            owner, event.amount,
            check_death=False, damage_event=event,
        )
        after = engine.triggered_skill_actions(
            owner, SkillTiming.AFTER_DAMAGE, event
        )
        result = engine.resolve_triggered_skill(after[0])

        self.assertEqual(before, [])
        self.assertEqual(len(after), 1)
        self.assertEqual(owner.hp, 2)
        self.assertEqual(len(owner.hand), 2)
        self.assertEqual(len(result.move_events), 1)
        self.assertEqual(len(result.reveal_events), 2)
        self.assertTrue(all(card in owner.hand for card in owner.hand))

    def test_after_damage_limit_is_twice_each_turn_including_own_turn(self):
        current = make_player(0)
        owner = make_player(1, liutongyu=True)
        engine = GameEngine([current, owner], [])
        engine.draw_pile = [
            make_card("draw-3", "spade"),
            make_card("draw-2", "spade"),
            make_card("draw-1", "spade"),
        ]
        event = DamageEvent(amount=1, source_player=current)

        for _ in range(2):
            actions = engine.triggered_skill_actions(
                owner, SkillTiming.AFTER_DAMAGE, event
            )
            self.assertEqual(len(actions), 1)
            engine.resolve_triggered_skill(actions[0])
        self.assertEqual(
            engine.triggered_skill_actions(
                owner, SkillTiming.AFTER_DAMAGE, event
            ),
            [],
        )

        engine.state.current_turn = owner.seat
        engine.start_turn()
        self.assertEqual(
            len(engine.triggered_skill_actions(
                owner, SkillTiming.AFTER_DAMAGE, event
            )),
            1,
        )

        engine.state.current_turn = current.seat
        engine.start_turn()
        self.assertEqual(
            len(engine.triggered_skill_actions(
                owner, SkillTiming.AFTER_DAMAGE, event
            )),
            1,
        )

    def test_mixed_hand_is_revealed_but_does_not_recover(self):
        current = make_player(0)
        owner = make_player(1, liutongyu=True, hp=2)
        owner.hand = [make_card("black", "club")]
        engine = GameEngine([current, owner], [])
        engine.draw_pile = [make_card("red", "heart")]
        action = engine.triggered_skill_actions(
            owner, SkillTiming.AFTER_DAMAGE, DamageEvent(amount=1)
        )[0]

        result = engine.resolve_triggered_skill(action)

        self.assertEqual(owner.hp, 2)
        self.assertEqual(len(result.reveal_events), 2)
        self.assertTrue(any("颜色不一致" in message for message in result.messages))

    def test_skill_reveals_use_separate_panel_not_waiting_area(self):
        owner = make_player(0, liutongyu=True)
        cards = [
            make_card("shown-red", "heart"),
            make_card("shown-black", "club"),
        ]
        owner.hand = cards[:]
        engine = GameEngine([owner], [])
        events = [
            CardRevealEvent(
                reveal_id=index + 1,
                card=card,
                owner_seat=owner.seat,
                from_zone="hand",
                visibility="public",
                reason="这不扯淡吗展示全部手牌",
            )
            for index, card in enumerate(cards)
        ]
        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        ui.skill_reveal_panel = None
        ui._queue_public_reveal = lambda *_args, **_kwargs: self.fail(
            "技能展示牌不应进入中央等待区"
        )
        continued = []

        ui._animate_skill_reveal_events(
            events, lambda: continued.append(True)
        )

        self.assertEqual(continued, [True])
        self.assertEqual(ui.skill_reveal_panel["cards"], cards)
        self.assertIn("这不扯淡吗", ui.skill_reveal_panel["title"])
        self.assertGreater(
            ui.skill_reveal_panel["expires_at"],
            pygame.time.get_ticks(),
        )

    def test_general_skill_triggers_after_vine_and_hp_reduction(self):
        current = make_player(0)
        owner = make_player(1, liutongyu=True, hp=4)
        owner.chained = True
        owner.hand = [make_card("old-red", "heart")]
        owner.equipment = [
            Card(
                id="vine",
                name="藤甲",
                suit="club",
                rank="2",
                kind=CardKind.EQUIPMENT,
                equipment_type="armor",
            )
        ]
        engine = GameEngine([current, owner], [])
        engine.draw_pile = [make_card("drawn-red", "diamond")]
        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        ui.hit_animations = {}
        ui.msg = lambda *_args: None
        ui.play_equipment_sound = lambda *_args, **_kwargs: None
        ui.play_system_sound = lambda *_args, **_kwargs: None
        ui._play_visual_effect = lambda *_args, **_kwargs: None
        observed = []
        owner_chain_states = {}

        def resolve_window(controller, timing, event, on_complete):
            observed.append((timing, event.amount, controller.hp))
            if controller is owner:
                owner_chain_states[timing] = owner.chained
            actions = engine.triggered_skill_actions(
                controller, timing, event
            )
            if actions:
                engine.resolve_triggered_skill(actions[0])
            on_complete()

        ui._begin_triggered_skill_sequence = resolve_window
        ui._begin_dying = lambda *_args, **_kwargs: None

        ui._apply_damage(
            owner,
            1,
            actor=current,
            nature=DamageNature.FIRE,
        )

        receiving = next(
            item for item in observed
            if item[0] == SkillTiming.WHEN_DAMAGED
        )
        # “受到伤害时”没有此技能；藤甲先把火焰伤害从1点增加到2点。
        self.assertEqual(
            receiving,
            (SkillTiming.WHEN_DAMAGED, 1, 4),
        )
        self.assertEqual(
            [item[0] for item in observed],
            [
                SkillTiming.DAMAGE_START,
                SkillTiming.CAUSING_DAMAGE,
                SkillTiming.WHEN_DAMAGED,
                SkillTiming.AFTER_CAUSING_DAMAGE,
                SkillTiming.AFTER_DAMAGE,
                SkillTiming.DAMAGE_END,
            ],
        )
        self.assertEqual(
            [item[1] for item in observed],
            [1, 1, 1, 2, 2, 2],
        )
        # 先承受藤甲修正后的2点伤害，再于“受到伤害后”回复1点体力。
        self.assertEqual(owner.hp, 3)
        self.assertTrue(
            owner_chain_states[SkillTiming.AFTER_DAMAGE]
        )
        self.assertTrue(
            owner_chain_states[SkillTiming.DAMAGE_END]
        )
        self.assertFalse(owner.chained)

    def test_wild_association_uses_every_black_hand_card_and_limit_three(self):
        owner = make_player(0, liutongyu=True)
        target = make_player(1)
        engine = GameEngine([owner, target], [])
        engine.state.phase = Phase.PLAY

        for index in range(3):
            black = [
                make_card(f"black-{index}-1", "spade"),
                make_card(f"black-{index}-2", "club"),
            ]
            red = make_card(f"red-{index}", "heart")
            owner.hand = black + [red]
            option = next(
                option
                for option in engine.skills.active_play_conversion_options(
                    engine, owner
                )
                if option.skill.skill_id == "general.wild_association"
            )
            self.assertFalse(
                engine.can_submit_active_conversion(
                    owner, option, [black[0]]
                )
            )
            event = engine.submit_active_conversion(owner, option, black)
            self.assertEqual(event.effective_card.name, "万箭齐发")
            self.assertEqual(event.effective_card.color, "black")
            self.assertEqual(event.physical_cards, tuple(black))
            self.assertEqual(owner.hand, [red])
            for card in event.physical_cards:
                engine.finish_processing_card(card)

        owner.hand = [make_card("fourth-black", "spade")]
        self.assertFalse(any(
            option.skill.skill_id == "general.wild_association"
            for option in engine.skills.active_play_conversion_options(
                engine, owner
            )
        ))

    def test_wild_association_damage_keeps_all_cards_for_jianxiong(self):
        owner = make_player(0, liutongyu=True)
        caocao = make_player(1)
        caocao.general.skills = [
            GeneralSkillRef(
                skill_id="general.jianxiong", name="奸雄"
            )
        ]
        black_cards = [
            make_card("wild-jianxiong-1", "spade"),
            make_card("wild-jianxiong-2", "club"),
        ]
        owner.hand = list(black_cards)
        engine = GameEngine([owner, caocao], [])
        engine.state.phase = Phase.PLAY
        option = next(
            option
            for option in engine.skills.active_play_conversion_options(
                engine, owner
            )
            if option.skill.skill_id == "general.wild_association"
        )
        use_event = engine.submit_active_conversion(
            owner, option, black_cards
        )

        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        ui.response_queue = []
        response = {}

        def capture_response(
            target, actor, required_card="闪", source_name="杀",
            source_card=None, response_action="打出", on_success=None,
            source_physical_cards=(),
        ):
            response.update({
                "target": target,
                "actor": actor,
                "source_name": source_name,
                "source_card": source_card,
                "source_physical_cards": tuple(source_physical_cards),
            })

        ui._start_response = capture_response
        ui._begin_area_response(
            owner,
            [caocao],
            "闪",
            "万箭齐发",
            use_event.effective_card,
            source_physical_cards=use_event.physical_cards,
        )

        self.assertEqual(
            response["source_physical_cards"],
            tuple(black_cards),
        )

        ui.dt = response["target"]
        ui.da = response["actor"]
        ui.duel_active = False
        ui.response_source_name = response["source_name"]
        ui.response_source_card = response["source_card"]
        ui.response_source_physical_cards = (
            response["source_physical_cards"]
        )
        ui.msg = lambda *_args, **_kwargs: None
        captured_damage = {}

        def capture_damage(
            target, amount=1, actor=None, source_card=None,
            source_physical_cards=None, **_kwargs,
        ):
            captured_damage.update({
                "target": target,
                "amount": amount,
                "actor": actor,
                "source_card": source_card,
                "source_physical_cards":
                    tuple(source_physical_cards or ()),
            })

        ui._apply_damage = capture_damage
        ui._resolve_human_no_dodge()
        self.assertEqual(
            captured_damage["source_physical_cards"],
            tuple(black_cards),
        )

        damage_event = DamageEvent(
            amount=captured_damage["amount"],
            source_player=captured_damage["actor"],
            source_card=captured_damage["source_card"],
            source_physical_cards=(
                captured_damage["source_physical_cards"]
            ),
        )
        actions = engine.triggered_skill_actions(
            caocao, SkillTiming.AFTER_DAMAGE, damage_event
        )
        self.assertEqual(len(actions), 1)
        result = engine.resolve_triggered_skill(actions[0])

        self.assertTrue(result.applied)
        self.assertEqual(caocao.hand, black_cards)
        self.assertTrue(all(
            card not in engine.processing_area
            for card in black_cards
        ))

    def test_jinren_requires_injury_and_uses_every_red_hand_card(self):
        owner = make_player(0, liutongyu=True)
        target = make_player(1)
        engine = GameEngine([owner, target], [])
        engine.state.phase = Phase.PLAY
        owner.hand = [
            make_card("red-1", "heart"),
            make_card("red-2", "diamond"),
            make_card("black", "club"),
        ]
        self.assertFalse(any(
            option.skill.skill_id == "general.jinren"
            for option in engine.skills.active_play_conversion_options(
                engine, owner
            )
        ))

        owner.hp = 2
        option = next(
            option
            for option in engine.skills.active_play_conversion_options(
                engine, owner
            )
            if option.skill.skill_id == "general.jinren"
        )
        red_cards = owner.hand[:2]
        event = engine.submit_active_conversion(
            owner, option, red_cards
        )

        self.assertEqual(event.effective_card.name, "桃")
        self.assertEqual(owner.hp, 3)
        self.assertEqual(owner.hand, [make_card("black", "club")])
        self.assertFalse(any(
            candidate.skill.skill_id == "general.jinren"
            for candidate in engine.skills.active_play_conversion_options(
                engine, owner
            )
        ))

    def test_active_skill_waits_for_confirm_and_greys_other_color(self):
        owner = make_player(0, liutongyu=True, hp=2)
        target = make_player(1)
        red_cards = [
            make_card("confirm-red-1", "heart"),
            make_card("confirm-red-2", "diamond"),
        ]
        black = make_card("confirm-black", "club")
        owner.hand = [*red_cards, black]
        engine = GameEngine([owner, target], [])
        engine.state.phase = Phase.PLAY
        option = next(
            option
            for option in engine.skills.active_play_conversion_options(
                engine, owner
            )
            if option.skill.skill_id == "general.jinren"
        )
        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        ui.next_prompt_id = 1
        ui.pending_skill_action = None
        ui.active_prompt = None
        ui.wd = False
        ui.dt = None
        ui.da = None
        ui.idx = None
        ui.pending_target = None
        ui.pending_targets = []
        ui.discard_selected = []
        ui.hint = lambda *_args, **_kwargs: None
        ui.clear_hint = lambda: None

        self.assertTrue(
            ui._begin_play_conversion_selection(owner, option)
        )
        self.assertEqual(owner.hand, [*red_cards, black])
        self.assertEqual(owner.skill_usage_counts, {})
        self.assertTrue(
            ui.pending_skill_action["fixed_materials"]
        )
        self.assertEqual(
            ui.pending_skill_action["cards"], red_cards
        )
        self.assertFalse(
            ui._play_conversion_card_disabled(owner, red_cards[0])
        )
        self.assertTrue(
            ui._play_conversion_card_disabled(owner, black)
        )
        self.assertTrue(ui._can_confirm_play(owner))

        prompt = ui.pending_skill_action["choice_prompt"]
        submitted = []
        ui._play_active_conversion = (
            lambda player, selected_option, cards=None:
            submitted.append((player, selected_option, list(cards)))
            or True
        )
        self.assertTrue(ui._submit_play_conversion_choice(
            PlayerChoice(
                prompt_id=prompt.prompt_id,
                player_seat=owner.seat,
                confirmed=True,
                card_ids=tuple(card.id for card in red_cards),
                target_seats=(),
                option_id=option.skill.skill_id,
            )
        ))
        self.assertEqual(submitted[0][2], red_cards)

        # 取消只清除确认态，不移动牌、不消耗次数。
        ui.clear_selection()
        self.assertIsNone(ui.pending_skill_action)
        self.assertEqual(owner.hand, [*red_cards, black])
        self.assertEqual(owner.skill_usage_counts, {})


if __name__ == "__main__":
    unittest.main()
