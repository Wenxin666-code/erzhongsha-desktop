import unittest

from main import GameUI
from src.engine import GameEngine
from src.models import Card, CardKind, DamageEvent, DamageNature, General, Player


def make_card(name, suit="club", kind=CardKind.EQUIPMENT, equipment_type="armor"):
    return Card(
        id=f"{name}-{suit}",
        name=name,
        suit=suit,
        rank="2",
        kind=kind,
        equipment_type=equipment_type,
    )


def make_player(seat, armor=None, hp=4):
    player = Player(
        seat=seat,
        general=General(
            id=str(seat), name=f"角色{seat}", kingdom="魏", hp=4, skills=[]
        ),
        hp=hp,
        max_hp=4,
    )
    if armor:
        player.equipment.append(armor)
    return player


class ArmorEffectsTest(unittest.TestCase):
    def test_successful_bagua_uses_same_slash_dodged_hook_as_jink(self):
        target = make_player(1, make_card("八卦阵"))
        ui = GameUI.__new__(GameUI)
        ui.active_judgment_id = 9
        ui.judgment_result_tip = "判定成功"
        ui.judgment_result_success = True
        ui.judgment_display_in_progress = True
        dodged = []
        ui._on_slash_dodged = lambda *args: dodged.append(args)

        ui._finish_response_judgment_result(
            9, make_card("判定牌", "heart"), True,
            target, self.source, make_card("杀"), "杀",
        )

        self.assertEqual(dodged[0][0], target)
        self.assertEqual(dodged[0][1], self.source)

    def setUp(self):
        self.source = make_player(0)

    def test_renwang_shield_nullifies_only_black_slash(self):
        target = make_player(1, make_card("仁王盾"))
        engine = GameEngine([self.source, target], [])
        black_slash = make_card("杀", "spade", CardKind.BASIC, None)
        red_slash = make_card("杀", "heart", CardKind.BASIC, None)

        self.assertEqual(
            engine.armor_nullifies_response_source(target, "杀", black_slash),
            "仁王盾",
        )
        self.assertIsNone(
            engine.armor_nullifies_response_source(target, "杀", red_slash)
        )

    def test_vine_nullifies_aoe_and_normal_slash(self):
        target = make_player(1, make_card("藤甲"))
        engine = GameEngine([self.source, target], [])
        normal_slash = make_card("杀", "heart", CardKind.BASIC, None)
        fire_slash = make_card("火杀", "heart", CardKind.BASIC, None)

        self.assertEqual(
            engine.armor_nullifies_response_source(
                target, "南蛮入侵", make_card("南蛮入侵", kind=CardKind.TRICK, equipment_type=None)
            ),
            "藤甲",
        )
        self.assertEqual(
            engine.armor_nullifies_response_source(target, "杀", normal_slash),
            "藤甲",
        )
        self.assertIsNone(
            engine.armor_nullifies_response_source(target, "杀", fire_slash)
        )

    def test_vine_increases_fire_damage(self):
        target = make_player(1, make_card("藤甲"))
        engine = GameEngine([self.source, target], [])

        result = engine.modify_damage(
            target, DamageEvent(amount=1, nature=DamageNature.FIRE)
        )

        self.assertEqual(result.amount, 2)

    def test_damage_log_reports_only_final_vine_damage(self):
        target = make_player(1, make_card("藤甲"))
        engine = GameEngine([self.source, target], [])
        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        ui.hit_animations = {}
        messages = []
        ui.msg = messages.append
        ui.play_equipment_sound = lambda *_args, **_kwargs: None
        ui.play_system_sound = lambda *_args, **_kwargs: None
        ui._play_visual_effect = lambda *_args, **_kwargs: None

        ui._apply_damage(
            target, 1, actor=self.source,
            nature=DamageNature.FIRE,
        )

        self.assertIn(f"{target.general.name} 受到2点火焰伤害", messages)
        self.assertFalse(any("藤甲" in message for message in messages))
        self.assertFalse(any("+1" in message for message in messages))

    def test_damage_sound_depends_on_amount_except_for_lightning(self):
        target = make_player(1, hp=20)
        engine = GameEngine([self.source, target], [])
        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        ui.hit_animations = {}
        sounds = []
        ui.msg = lambda *_args: None
        ui.play_equipment_sound = lambda *_args, **_kwargs: None
        ui.play_system_sound = lambda event, **_kwargs: sounds.append(event)
        ui._play_visual_effect = lambda *_args, **_kwargs: None

        ui._apply_damage(target, 1, actor=self.source)
        ui._apply_damage(target, 2, actor=self.source)
        ui._apply_damage(target, 4, actor=self.source)
        ui._apply_damage(
            target, 3, actor=None,
            source_card=make_card(
                "闪电", kind=CardKind.TRICK, equipment_type=None
            ),
            nature=DamageNature.THUNDER,
        )

        self.assertEqual(
            sounds, ["damage1", "damage2", "damage2", "damage3"]
        )

    def test_silver_lion_caps_damage_and_heals_when_lost(self):
        silver_lion = make_card("白银狮子")
        target = make_player(1, silver_lion, hp=2)
        engine = GameEngine([self.source, target], [])
        applications = []
        engine.skill_application_listener = (
            lambda player, application: applications.append(
                (player, application.skill.source_name)
            )
        )

        result = engine.modify_damage(target, DamageEvent(amount=3))
        removed = engine.remove_equipment(target, silver_lion)

        self.assertEqual(result.amount, 1)
        self.assertTrue(removed)
        self.assertEqual(target.hp, 3)
        self.assertEqual(applications, [(target, "白银狮子")])

    def test_replacing_silver_lion_triggers_recovery(self):
        silver_lion = make_card("白银狮子")
        replacement = make_card("藤甲", "spade")
        target = make_player(1, silver_lion, hp=2)
        engine = GameEngine([self.source, target], [])

        equipped = engine._equip(target, replacement)

        self.assertTrue(equipped)
        self.assertEqual(target.hp, 3)
        self.assertIn(silver_lion, engine.discard_pile)
        self.assertEqual(target.equipment, [replacement])

    def test_snatching_silver_lion_triggers_recovery_then_gain(self):
        silver_lion = make_card("白银狮子")
        target = make_player(1, silver_lion, hp=2)
        engine = GameEngine([self.source, target], [])

        resolved = engine.resolve_target_card_trick(
            self.source, "顺手牵羊", target, silver_lion
        )

        self.assertTrue(resolved)
        self.assertEqual(target.hp, 3)
        self.assertNotIn(silver_lion, target.equipment)
        self.assertIn(silver_lion, self.source.hand)

    def test_bagua_red_judgment_counts_as_dodge(self):
        target = make_player(1, make_card("八卦阵"))
        red_card = make_card("判定牌", "diamond", CardKind.BASIC, None)
        engine = GameEngine([self.source, target], [red_card])

        event = engine.activate_optional_response_skill(
            target, "armor.bagua"
        )

        self.assertIs(event.judging_player, target)
        self.assertIs(event.current_card, red_card)
        self.assertTrue(event.result)
        self.assertIn(red_card, engine.discard_pile)

    def make_response_ui(self, engine):
        """构造不启动窗口的最小 UI，用于验证响应状态转换。"""
        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        ui.idx = None
        ui.pending_target = None
        ui.pending_targets = []
        ui.wd = False
        ui.dt = None
        ui.da = None
        ui.response_card_name = "闪"
        ui.response_source_name = "杀"
        ui.response_source_card = None
        ui.response_time_remaining = 0
        ui.response_timer_last_tick = 0
        ui.ai_response_at = 0
        ui.active_prompt = None
        ui.next_prompt_id = 1
        ui.dying_target = None
        ui.duel_active = False
        ui.messages = []
        ui.hints = []
        ui.animations = []
        ui.waiting_cards = []
        ui.effect_frame_paths = {
            "judgegood": [object()],
            "judgebad": [object()],
        }
        ui.visual_effects = []
        ui.active_judgment_id = None
        ui.judgment_result_tip = None
        ui.judgment_display_in_progress = False
        ui.phase_transition_callback = None
        ui.phase_transition_at = 0
        ui.msg = ui.messages.append
        ui.hint = lambda text, duration=3000: ui.hints.append(text)
        ui.finished_response = False
        ui._xd = lambda: setattr(ui, "finished_response", True)
        return ui

    def test_bagua_waits_for_confirmation_before_judgment(self):
        target = make_player(1, make_card("八卦阵"))
        judged_card = make_card("判定牌", "heart", CardKind.BASIC, None)
        engine = GameEngine([self.source, target], [judged_card])
        ui = self.make_response_ui(engine)
        slash = make_card("杀", "heart", CardKind.BASIC, None)

        ui._start_response(target, self.source, "闪", "杀", slash)

        self.assertEqual(ui.active_prompt.skill_name, "八卦阵")
        self.assertEqual(engine.draw_pile, [judged_card])
        self.assertTrue(ui.wd)

    def test_declining_bagua_keeps_normal_dodge_response(self):
        target = make_player(1, make_card("八卦阵"))
        judged_card = make_card("判定牌", "heart", CardKind.BASIC, None)
        engine = GameEngine([self.source, target], [judged_card])
        ui = self.make_response_ui(engine)
        slash = make_card("杀", "heart", CardKind.BASIC, None)
        ui._start_response(target, self.source, "闪", "杀", slash)

        ui._decline_skill_prompt()

        self.assertIsNone(ui.active_prompt)
        self.assertEqual(engine.draw_pile, [judged_card])
        self.assertTrue(ui.wd)
        self.assertFalse(ui.finished_response)

    def test_failed_bagua_returns_to_normal_dodge_response(self):
        target = make_player(1, make_card("八卦阵"))
        black_card = make_card("判定牌", "spade", CardKind.BASIC, None)
        engine = GameEngine([self.source, target], [black_card])
        ui = self.make_response_ui(engine)
        slash = make_card("杀", "heart", CardKind.BASIC, None)
        ui._start_response(target, self.source, "闪", "杀", slash)

        ui._confirm_skill_prompt()

        self.assertIsNone(ui.active_prompt)
        self.assertIn(black_card, engine.processing_area)
        animation = ui.animations[-1]
        ui.waiting_cards.append({
            "card": black_card, "pos": animation["dest"]
        })
        animation["on_complete"]()
        self.assertIn(black_card, engine.discard_pile)
        self.assertTrue(ui.wd)
        self.assertFalse(ui.finished_response)
        self.assertTrue(ui.judgment_display_in_progress)
        self.assertEqual(ui.animations[-1]["card"], black_card)

    def test_bagua_judgment_shows_card_and_result_before_resuming(self):
        target = make_player(1, make_card("八卦阵"))
        red_card = make_card("判定牌", "heart", CardKind.BASIC, None)
        engine = GameEngine([self.source, target], [red_card])
        ui = self.make_response_ui(engine)
        slash = make_card("杀", "heart", CardKind.BASIC, None)
        ui._start_response(target, self.source, "闪", "杀", slash)

        ui._confirm_skill_prompt()
        animation = ui.animations.pop()
        ui.waiting_cards.append({"card": red_card, "pos": animation["dest"]})
        animation["on_complete"]()

        self.assertIn("视为打出【闪】", ui.judgment_result_tip)
        self.assertFalse(ui.finished_response)
        self.assertEqual(ui.visual_effects[-1]["key"], "judgegood")
        self.assertEqual(ui.visual_effects[-1]["position"], animation["dest"])

        ui.phase_transition_callback()

        self.assertTrue(ui.finished_response)
        self.assertIsNone(ui.judgment_result_tip)
        self.assertIn(
            red_card, [item["card"] for item in ui.waiting_cards]
        )

    def test_bagua_can_satisfy_custom_jink_response_request(self):
        target = make_player(1, make_card("八卦阵"))
        red_card = make_card(
            "判定牌", "heart", CardKind.BASIC, None
        )
        engine = GameEngine([self.source, target], [red_card])
        ui = self.make_response_ui(engine)
        succeeded = []
        failed = []

        ui._start_response(
            target,
            self.source,
            required_card="闪",
            source_name="伟神",
            on_success=lambda *args: succeeded.append(args),
            on_failure=lambda: failed.append(True),
        )

        self.assertEqual(ui.active_prompt.skill_name, "八卦阵")
        ui._confirm_skill_prompt()
        animation = ui.animations.pop()
        ui.waiting_cards.append({
            "card": red_card, "pos": animation["dest"]
        })
        animation["on_complete"]()
        ui.phase_transition_callback()

        self.assertEqual(len(succeeded), 1)
        self.assertEqual(succeeded[0][0], target)
        self.assertEqual(succeeded[0][2].name, "闪")
        self.assertEqual(failed, [])

    def test_failed_custom_jink_response_uses_failure_branch(self):
        target = make_player(1)
        engine = GameEngine([self.source, target], [])
        ui = self.make_response_ui(engine)
        failed = []
        damage_calls = []
        ui._apply_damage = lambda *args, **kwargs: damage_calls.append(
            (args, kwargs)
        )

        ui._start_response(
            target,
            self.source,
            required_card="闪",
            source_name="伟神",
            on_failure=lambda: failed.append(True),
        )
        ui._resolve_human_no_dodge("选择令对方获得一张牌")

        self.assertEqual(failed, [True])
        self.assertEqual(damage_calls, [])


if __name__ == "__main__":
    unittest.main()
