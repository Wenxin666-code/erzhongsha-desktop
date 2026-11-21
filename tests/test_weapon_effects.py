import unittest

from main import GameUI, EQUIP_Y
from src.engine import GameEngine
from src.models import (
    Card, CardKind, DamageEvent, DamageNature, General, Player, SkillKind,
)
from src.skills import WEAPON_EFFECT_SKILLS


def make_card(
    name, kind=CardKind.BASIC, equipment_type=None, suit="spade",
    ident=None, rank="7",
):
    return Card(
        id=ident or f"{name}-{suit}", name=name, suit=suit, rank=rank,
        kind=kind, equipment_type=equipment_type,
    )


def make_player(seat, gender="male", weapon=None):
    result = Player(
        seat=seat,
        general=General(
            id=str(seat), name=f"角色{seat}", kingdom="魏", hp=4,
            gender=gender, skills=[],
        ),
        hp=4, max_hp=4,
    )
    if weapon:
        result.equipment.append(weapon)
    return result


def weapon(name):
    return make_card(name, CardKind.EQUIPMENT, "weapon")


class WeaponEffectsTest(unittest.TestCase):
    def test_all_weapon_effects_are_registered(self):
        self.assertEqual(
            {skill.source_name for skill in WEAPON_EFFECT_SKILLS},
            {
                "诸葛连弩", "雌雄双股剑", "青釭剑", "寒冰剑", "古锭刀",
                "青龙偃月刀", "丈八蛇矛", "贯石斧", "方天画戟",
                "朱雀羽扇", "麒麟弓",
            },
        )
        locked = {
            skill.source_name for skill in WEAPON_EFFECT_SKILLS
            if skill.kind == SkillKind.LOCKED
        }
        self.assertEqual(locked, {"青釭剑", "古锭刀"})

    def test_zhuge_removes_slash_count_limit(self):
        source = make_player(0, weapon=weapon("诸葛连弩"))
        target = make_player(1)
        source.slash_used = True
        engine = GameEngine([source, target], [])

        self.assertTrue(engine.can_use_slash(source))

    def test_zhuge_effect_is_shown_only_for_extra_slash(self):
        source = make_player(0, weapon=weapon("诸葛连弩"))
        target = make_player(1)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([source, target], [])
        played = []
        ui.play_equipment_sound = (
            lambda name, player=None, visual=True: played.append(name)
        )

        ui._play_zhuge_for_extra_slash(source, False)
        ui._play_zhuge_for_extra_slash(source, True)

        self.assertEqual(played, ["诸葛连弩"])

    def test_qinggang_ignores_armor_for_slash(self):
        source = make_player(0, weapon=weapon("青釭剑"))
        target = make_player(1)
        target.equipment.append(make_card("仁王盾", CardKind.EQUIPMENT, "armor"))
        slash = make_card("杀")
        engine = GameEngine([source, target], [])

        self.assertIsNone(
            engine.armor_nullifies_response_source(
                target, "杀", slash, source
            )
        )

    def test_guding_increases_damage_to_empty_hand_target(self):
        source = make_player(0, weapon=weapon("古锭刀"))
        target = make_player(1)
        slash = make_card("杀")
        engine = GameEngine([source, target], [])

        result, applications = engine.modify_damage_with_skills(
            target, DamageEvent(
                amount=1, source_player=source, source_card=slash
            )
        )

        self.assertEqual(result.amount, 2)
        self.assertEqual(applications[0].skill.skill_id, "weapon.guding")

    def test_zhuque_converts_normal_slash_to_fire_slash(self):
        source = make_player(0, weapon=weapon("朱雀羽扇"))
        target = make_player(1)
        slash = make_card("杀")
        source.hand.append(slash)
        engine = GameEngine([source, target], [])

        event = engine.create_slash_event(source, [slash], [target], "火杀")

        self.assertEqual(event.nature, DamageNature.FIRE)
        self.assertEqual(event.effective_name, "火杀")

    def test_ai_zhuque_prompt_does_not_select_local_hand_index(self):
        source = make_player(0, weapon=weapon("朱雀羽扇"))
        source.is_ai = True
        card = make_card("杀")
        ui = GameUI.__new__(GameUI)
        ui.idx = 3
        ui.wd = True
        ui.dt = source
        ui.da = object()
        resumed = []
        ui.ps = lambda *args, **kwargs: resumed.append((args, kwargs))

        ui._resume_zhuque_slash(
            source, card, [make_player(1)], "火杀", None
        )

        self.assertIsNone(ui.idx)
        self.assertEqual(resumed[0][1]["effective_name"], "火杀")

    def test_zhangba_uses_two_hand_cards_as_slash(self):
        source = make_player(0, weapon=weapon("丈八蛇矛"))
        target = make_player(1)
        first = make_card("桃", ident="peach")
        second = make_card("闪", ident="dodge")
        source.hand.extend([first, second])
        engine = GameEngine([source, target], [])

        event = engine.create_slash_event(source, [first, second], [target])

        self.assertEqual(event.physical_cards, [first, second])
        self.assertFalse(source.hand)
        self.assertTrue(source.slash_used)

    def test_zhangba_effective_color_suit_and_point_follow_composite_rules(self):
        cases = (
            ("two-black", ("spade", "club"), "black", "仁王盾"),
            ("two-red", ("heart", "diamond"), "red", None),
            ("mixed", ("spade", "heart"), None, None),
        )
        for label, suits, expected_color, expected_armor in cases:
            with self.subTest(label=label):
                source = make_player(0, weapon=weapon("丈八蛇矛"))
                target = make_player(1)
                target.equipment.append(
                    make_card(
                        "仁王盾", CardKind.EQUIPMENT, "armor",
                        ident=f"{label}-armor",
                    )
                )
                first = make_card(
                    "桃", suit=suits[0], ident=f"{label}-a", rank="7"
                )
                second = make_card(
                    "闪", suit=suits[1], ident=f"{label}-b", rank="9"
                )
                source.hand.extend([first, second])
                engine = GameEngine([source, target], [])

                event = engine.create_slash_event(
                    source, [first, second], [target]
                )
                effective = event.effective_card

                self.assertEqual(effective.name, "杀")
                self.assertEqual(effective.kind, CardKind.BASIC)
                self.assertEqual(effective.suit, "no_suit")
                self.assertEqual(effective.color, expected_color)
                self.assertEqual(effective.rank, "K")
                self.assertEqual(
                    engine.armor_nullifies_response_source(
                        target, "杀", effective, source
                    ),
                    expected_armor,
                )

    def test_zhangba_response_is_played_not_used(self):
        source = make_player(0, weapon=weapon("丈八蛇矛"))
        actor = make_player(1)
        cards = [
            make_card("桃", ident="response-a"),
            make_card("闪", ident="response-b"),
        ]
        source.hand.extend(cards)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([source, actor], [])
        messages = []
        finished = []
        ui.wd = True
        ui.dt = source
        ui.da = actor
        ui.msg = messages.append
        ui.play_equipment_sound = lambda *_args: None
        ui._xd = lambda: finished.append(True)
        displayed = []
        ui._queue_discard_display = (
            lambda shown, _sources, on_complete=None, **_kwargs: (
                displayed.extend(shown),
                on_complete() if on_complete else None,
            )
        )

        ui._use_zhangba_response(
            source, actor, "南蛮入侵",
            make_card("南蛮入侵", CardKind.TRICK),
            cards,
        )

        self.assertFalse(source.slash_used)
        self.assertTrue(finished)
        self.assertEqual(displayed, cards)
        self.assertIn("打出", messages[-1])

    def test_zhangba_response_passes_composite_effective_card(self):
        source = make_player(0, weapon=weapon("丈八蛇矛"))
        actor = make_player(1)
        cards = [
            make_card("桃", suit="spade", ident="black-a", rank="7"),
            make_card("闪", suit="club", ident="black-b", rank="9"),
        ]
        source.hand.extend(cards)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([source, actor], [])
        ui.response_action = "打出"
        ui.wd = True
        ui.dt = source
        ui.da = actor
        ui.msg = lambda *_args: None
        ui.play_equipment_sound = lambda *_args: None
        ui._hand_card_center = lambda *_args: (0, 0)
        received = []
        ui.response_success_callback = (
            lambda _player, _actor, effective, physical:
            received.append((effective, physical))
        )
        ui._queue_discard_display = (
            lambda _cards, _sources, on_complete=None, **_kwargs:
            on_complete() if on_complete else None
        )

        ui._use_zhangba_response(
            source, actor, "南蛮入侵",
            make_card("南蛮入侵", CardKind.TRICK),
            cards,
        )

        effective, physical = received[0]
        self.assertEqual(effective.suit, "no_suit")
        self.assertEqual(effective.color, "black")
        self.assertEqual(effective.rank, "K")
        self.assertEqual(physical, tuple(cards))

    def test_play_phase_zhangba_prompt_cannot_cause_response_damage(self):
        source = make_player(0, weapon=weapon("丈八蛇矛"))
        cards = [
            make_card("桃", ident="zhangba-a"),
            make_card("闪", ident="zhangba-b"),
        ]
        source.hand.extend(cards)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([source], [])
        ui.wd = False
        ui.dt = None
        ui.da = None
        ui.active_prompt = None
        ui.next_prompt_id = 1
        ui.response_time_remaining = 0
        ui.ai_response_at = 0
        ui.idx = None
        ui.pending_target = None
        ui.pending_skill_action = None
        ui.skill_prompt_confirm_callback = None
        ui.skill_prompt_cancel_callback = None
        ui.skill_prompt_cards = []
        ui.skill_prompt_required_cards = 0
        ui.skill_prompt_selected = set()
        ui.hint = lambda *_args: None
        ui.msg = lambda *_args: None

        ui._open_skill_prompt(
            source, "weapon.zhangba", "丈八蛇矛",
            "请选择两张手牌",
            lambda selected: None,
            ui._cancel_zhangba_play_prompt,
            selectable_cards=cards,
            required_cards=2,
        )

        self.assertGreater(ui.response_time_remaining, 0)
        self.assertTrue(ui.wd)
        self.assertEqual(source.hp, 4)

        ui._decline_skill_prompt()

        self.assertFalse(ui.wd)
        self.assertIsNone(ui.dt)
        self.assertEqual(source.hp, 4)

    def test_fangtian_allows_three_targets_only_with_last_hand_slash(self):
        source = make_player(0, weapon=weapon("方天画戟"))
        targets = [make_player(i) for i in (1, 2, 3)]
        slash = make_card("杀")
        source.hand.append(slash)
        engine = GameEngine([source, *targets], [])

        event = engine.create_slash_event(source, [slash], targets)

        self.assertEqual(event.targets, targets)
        self.assertTrue(event.was_last_hand_card)

    def test_fangtian_target_selection_uses_generic_target_prompt(self):
        source = make_player(0, weapon=weapon("方天画戟"))
        targets = [make_player(i) for i in (1, 2, 3)]
        slash = make_card("杀")
        source.hand.append(slash)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([source, *targets], [])

        self.assertEqual(
            ui._current_multi_target_limit(source, slash), 3
        )
        hint = ui._selected_targets_hint(targets[:2])
        self.assertEqual(hint, "已选目标：角色1、角色2")
        self.assertNotIn("铁索", hint)

    def test_cixiong_target_can_discard_or_let_source_draw(self):
        source = make_player(0, "male", weapon("雌雄双股剑"))
        target = make_player(1, "female")
        hand = make_card("闪")
        reward = make_card("桃", suit="heart")
        target.hand.append(hand)
        engine = GameEngine([source, target], [reward])
        self.assertTrue(engine.cixiong_can_trigger(source, target))

        engine.resolve_cixiong_choice(source, target, hand)
        engine.resolve_cixiong_choice(source, target)

        self.assertIn(hand, engine.discard_pile)
        self.assertIn(reward, source.hand)

    def test_hanbing_prevents_damage_and_discards_two_cards(self):
        source = make_player(0, weapon=weapon("寒冰剑"))
        target = make_player(1)
        first = make_card("桃", ident="a")
        second = make_card("闪", ident="b")
        target.hand.extend([first, second])
        engine = GameEngine([source, target], [])

        self.assertTrue(engine.resolve_hanbing(source, target, [first, second]))
        self.assertFalse(target.hand)
        self.assertEqual(engine.discard_pile, [first, second])

    def test_hanbing_moves_each_card_immediately(self):
        source = make_player(0, weapon=weapon("寒冰剑"))
        target = make_player(1)
        lion = make_card("白银狮子", CardKind.EQUIPMENT, "armor")
        other = make_card("闪")
        target.hp = 2
        target.equipment.append(lion)
        target.hand.append(other)
        engine = GameEngine([source, target], [])

        self.assertTrue(engine.discard_for_hanbing(target, lion))
        self.assertEqual(target.hp, 3)
        self.assertNotIn(lion, target.equipment)
        self.assertTrue(engine.discard_for_hanbing(target, other))

    def test_hanbing_waits_for_each_discard_animation_before_next_choice(self):
        source = make_player(0, weapon=weapon("寒冰剑"))
        target = make_player(1)
        card = make_card("闪")
        target.hand.append(card)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([source, target], [])
        ui._hand_card_center = lambda player, index: (100, 200)
        ui.msg = lambda message: None
        queued = []
        resumed = []
        ui._queue_card_animation = lambda *args, **kwargs: queued.append(
            (args, kwargs)
        )
        ui._begin_hanbing_choices = lambda *args: resumed.append(args)

        ui._choose_hanbing_card(source, target, card, [], card)

        self.assertIn(card, ui.engine.discard_pile)
        self.assertEqual(len(queued), 1)
        self.assertTrue(queued[0][1]["blocking"])
        self.assertFalse(resumed)
        queued[0][1]["on_complete"]()
        self.assertEqual(resumed[0][-1], [card])

    def test_guanshi_discards_two_cards(self):
        source = make_player(0, weapon=weapon("贯石斧"))
        cards = [make_card("桃", ident="a"), make_card("闪", ident="b")]
        source.hand.extend(cards)
        engine = GameEngine([source], [])

        self.assertTrue(engine.resolve_guanshi(source, cards))
        self.assertFalse(source.hand)

    def test_guanshi_discard_cards_wait_in_center_before_damage(self):
        source = make_player(0, weapon=weapon("贯石斧"))
        target = make_player(1)
        cards = [
            make_card("桃", ident="cost-a"),
            make_card("闪", ident="cost-b"),
        ]
        source.hand.extend(cards)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([source, target], [])
        ui.wd = True
        ui.dt = source
        ui._hand_card_center = lambda player, index: (100 + index * 20, 200)
        ui._equipment_card_center = lambda player, index: (50, 100)
        ui._player_center = lambda player: (80, 120)
        ui.msg = lambda message: None
        ui._xd = lambda: None
        queued = []
        damaged = []
        ui._queue_card_animation = lambda *args, **kwargs: queued.append(
            (args, kwargs)
        )
        ui._deal_slash_damage = lambda *args: damaged.append(args)

        ui._finish_guanshi(source, target, make_card("杀"), cards)

        self.assertEqual(ui.engine.discard_pile, cards)
        self.assertEqual(len(queued), 2)
        self.assertTrue(all(item[1]["face_up"] for item in queued))
        self.assertTrue(all(item[1]["blocking"] for item in queued))
        self.assertFalse(damaged)
        queued[0][1]["on_complete"]()
        self.assertFalse(damaged)
        queued[1][1]["on_complete"]()
        self.assertEqual(len(damaged), 1)

    def test_guanshi_uses_visible_own_hand_and_equipment_selection(self):
        source = make_player(0, weapon=weapon("贯石斧"))
        target = make_player(1)
        hand_cards = [
            make_card("桃", ident="hand-a"),
            make_card("闪", ident="hand-b"),
        ]
        armor = make_card(
            "八卦阵", CardKind.EQUIPMENT, "armor", ident="armor-a"
        )
        source.hand.extend(hand_cards)
        source.equipment.append(armor)
        engine = GameEngine([source, target], [])
        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        ui.wd = False
        ui.dt = None
        ui.active_prompt = None
        ui.skill_prompt_confirm_callback = None
        ui.skill_prompt_cancel_callback = None
        ui.skill_prompt_cards = []
        ui.skill_prompt_required_cards = 0
        ui.skill_prompt_selected = set()
        ui.next_prompt_id = 1
        ui.target_card_choice = None
        ui.hidden_equipment_cards = set()
        ui.idx = None
        ui.discard_selected = set()
        ui.hint = lambda *_args: None
        ui._xd = lambda: None

        ui._on_slash_dodged(target, source, make_card("杀"))

        self.assertEqual(ui.active_prompt.skill_name, "贯石斧")
        self.assertEqual(ui.skill_prompt_required_cards, 2)
        self.assertEqual(ui.skill_prompt_cards, hand_cards + [armor])
        self.assertIsNone(ui.target_card_choice)
        self.assertFalse(ui._skill_prompt_selection_ready())

        ui.gci = lambda _pos, _player: 0
        ui.hd((0, 0))
        self.assertIn(hand_cards[0].id, ui.skill_prompt_selected)
        self.assertFalse(ui._skill_prompt_selection_ready())
        self.assertLess(ui.hrects(source)[0].y, ui.hrects(source)[1].y)

        ui.gci = lambda _pos, _player: None
        armor_slot_center = (100, EQUIP_Y + 8 + 47 + 16)
        ui.hd(armor_slot_center)
        self.assertIn(armor.id, ui.skill_prompt_selected)
        self.assertTrue(ui._skill_prompt_selection_ready())

    def test_qilin_discards_mount_after_damage(self):
        source = make_player(0, weapon=weapon("麒麟弓"))
        target = make_player(1)
        mount = make_card("赤兔", CardKind.EQUIPMENT, "offensive_mount")
        target.equipment.append(mount)
        engine = GameEngine([source, target], [])

        self.assertTrue(engine.resolve_qilin(source, target, mount))
        self.assertNotIn(mount, target.equipment)
        self.assertIn(mount, engine.discard_pile)

    def test_ai_qilin_does_not_open_a_visible_skill_prompt(self):
        source = make_player(0, weapon=weapon("麒麟弓"))
        source.is_ai = True
        target = make_player(1)
        mount = make_card("赤兔", CardKind.EQUIPMENT, "offensive_mount")
        target.equipment.append(mount)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([source, target], [])
        ui.active_prompt = None
        ui.play_equipment_sound = lambda *_args, **_kwargs: None
        calls = []
        ui._begin_qilin_choice = (
            lambda actor, victim, mounts, on_complete=None: calls.append(
                (actor, victim, mounts)
            )
        )

        ui._deal_slash_damage(source=source, target=target, source_card=make_card("杀"))

        self.assertEqual(calls, [(source, target, [mount])])
        self.assertIsNone(ui.active_prompt)

    def test_qinglong_requires_another_slash(self):
        source = make_player(0, weapon=weapon("青龙偃月刀"))
        source.hand.append(make_card("雷杀"))
        engine = GameEngine([source], [])

        self.assertTrue(engine.can_qinglong_follow_up(source))


if __name__ == "__main__":
    unittest.main()
