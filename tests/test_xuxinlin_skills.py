import unittest
from pathlib import Path

from main import GameUI
from src.engine import GameEngine
from src.loader import load_generals
from src.models import (
    Card, CardKind, General, GeneralSkillRef, Phase, Player, PlayerChoice,
    SkillTiming, TrickCardDiscardEvent,
)


ROOT = Path(__file__).resolve().parents[1]


def make_card(
    card_id, name, suit="spade", rank="7",
    kind=CardKind.BASIC, equipment_type=None,
):
    return Card(
        id=card_id,
        name=name,
        suit=suit,
        rank=rank,
        kind=kind,
        equipment_type=equipment_type,
    )


def make_player(
    seat, name, *, xuxinlin=False, sunqinke=False, is_ai=False
):
    skills = []
    if xuxinlin:
        skills = [
            GeneralSkillRef(
                skill_id="general.xuxinlin.zhanglinghe",
                name="张凌赫",
            ),
            GeneralSkillRef(
                skill_id="general.xuxinlin.lvfei",
                name="绿妃",
            ),
            GeneralSkillRef(
                skill_id="general.xuxinlin.shenshen",
                name="肾肾",
            ),
        ]
    elif sunqinke:
        skills = [
            GeneralSkillRef(
                skill_id="general.sunqinke.kongju",
                name="控局",
            ),
        ]
    return Player(
        seat=seat,
        general=General(
            id=(
                "xuxinlin"
                if xuxinlin
                else "sunqinke" if sunqinke else f"general-{seat}"
            ),
            name=name,
            kingdom="神" if xuxinlin or sunqinke else "魏",
            hp=5 if xuxinlin else 4,
            gender="female" if xuxinlin or sunqinke else "male",
            skills=skills,
            playable=True,
        ),
        hp=5 if xuxinlin else 4,
        max_hp=5 if xuxinlin else 4,
        is_ai=is_ai,
    )


class XuxinlinSkillTests(unittest.TestCase):
    def setUp(self):
        self.xu = make_player(
            0, "徐欣琳", xuxinlin=True
        )
        self.enemy = make_player(1, "敌将")
        self.draw_cards = [
            make_card(f"draw-{index}", "杀", "heart")
            for index in range(10)
        ]
        self.engine = GameEngine(
            [self.xu, self.enemy], self.draw_cards
        )
        self.engine.state.current_turn = 0
        self.engine.state.phase = Phase.PLAY
        self.engine.begin_play_phase(self.xu)

    def _zhanglinghe_option(self):
        return next(
            option
            for option in
            self.engine.skills.active_play_conversion_options(
                self.engine, self.xu
            )
            if option.skill.skill_id
            == "general.xuxinlin.zhanglinghe"
        )

    def test_general_is_registered_with_exact_descriptions(self):
        general = next(
            general for general in load_generals(
                ROOT / "data" / "generals.yml"
            )
            if general.id == "xuxinlin"
        )
        self.assertTrue(general.playable)
        self.assertEqual(general.gender, "female")
        self.assertEqual(general.hp, 5)
        self.assertEqual(
            [skill.skill_id for skill in general.skills],
            [
                "general.xuxinlin.zhanglinghe",
                "general.xuxinlin.lvfei",
                "general.xuxinlin.shenshen",
            ],
        )
        definitions = [
            self.engine.skills.skill_definition(skill.skill_id)
            for skill in general.skills
        ]
        self.assertEqual(
            definitions[0].description,
            "你可以将一张装备牌或黑色手牌当作【过河拆桥】使用。"
            "若使用的是黑色装备牌，此牌结算后，你可以摸1张牌。",
        )
        self.assertEqual(
            definitions[1].description,
            "每当有角色因【过河拆桥】被弃置牌时，若弃置的牌花色为梅花，"
            "你可以获得此牌。",
        )
        self.assertEqual(
            definitions[2].description,
            "锁定技，出牌阶段结束时，若你本阶段使用了至少4张"
            "【过河拆桥】，则你的下个摸牌阶段多摸1张牌。",
        )

    def test_zhanglinghe_material_zones_and_targeted_submission(self):
        black_basic = make_card("black", "闪", "spade")
        red_basic = make_card("red", "桃", "heart")
        red_equip = make_card(
            "red-equip", "赤兔", "heart",
            kind=CardKind.EQUIPMENT,
            equipment_type="offensive_mount",
        )
        equipped = make_card(
            "equipped", "八卦阵", "diamond",
            kind=CardKind.EQUIPMENT,
            equipment_type="armor",
        )
        target_card = make_card("target", "杀", "club")
        self.xu.hand = [black_basic, red_basic, red_equip]
        self.xu.equipment = [equipped]
        self.enemy.hand = [target_card]

        option = self._zhanglinghe_option()
        candidates = self.engine.skills.conversion_candidates(
            self.xu, option
        )
        self.assertEqual(
            {card.id for card in candidates},
            {"black", "red-equip", "equipped"},
        )
        self.assertTrue(
            self.engine.can_submit_active_conversion(
                self.xu, option, [equipped], (self.enemy,)
            )
        )
        event = self.engine.submit_active_conversion(
            self.xu, option, [equipped], (self.enemy,)
        )
        self.assertEqual(event.effective_card.name, "过河拆桥")
        self.assertEqual(event.target_seats, (self.enemy.seat,))
        self.assertNotIn(equipped, self.xu.equipment)
        self.assertIn(equipped, self.engine.processing_area)
        self.assertEqual(
            self.xu.play_phase_card_use_counts["过河拆桥"], 1
        )

    def test_black_equipment_draw_is_after_resolution_trigger(self):
        material = make_card(
            "material", "仁王盾", "club",
            kind=CardKind.EQUIPMENT,
            equipment_type="armor",
        )
        self.xu.hand = [material]
        self.enemy.hand = [make_card("enemy-card", "杀")]
        option = self._zhanglinghe_option()
        event = self.engine.submit_active_conversion(
            self.xu, option, [material], (self.enemy,)
        )
        self.assertEqual(len(self.xu.hand), 0)
        actions = self.engine.triggered_skill_actions(
            self.xu, SkillTiming.AFTER_CARD_RESOLUTION, event
        )
        self.assertEqual(len(actions), 1)
        result = self.engine.resolve_triggered_skill(actions[0])
        self.assertTrue(result.applied)
        self.assertEqual(len(result.move_events), 1)
        self.assertEqual(len(self.xu.hand), 1)

    def test_human_conversion_prompt_submits_card_and_target_together(self):
        material = make_card(
            "material", "闪", "spade"
        )
        self.xu.hand = [material]
        self.enemy.hand = [make_card("enemy-card", "杀")]
        option = self._zhanglinghe_option()
        ui = GameUI.__new__(GameUI)
        ui.engine = self.engine
        ui.next_prompt_id = 1
        ui.pending_skill_action = None
        ui.active_prompt = None
        ui.wd = False
        ui.dt = None
        ui.da = None
        ui.idx = None
        ui.pending_target = None
        ui.pending_targets = []
        ui.borrowed_sword_choice = None
        ui.discard_selected = []
        ui.hint = lambda *_args, **_kwargs: None
        ui.clear_hint = lambda: None

        self.assertTrue(
            ui._begin_play_conversion_selection(self.xu, option)
        )
        prompt = ui.pending_skill_action["choice_prompt"]
        self.assertEqual(prompt.required_cards, 1)
        self.assertEqual(prompt.required_targets, 1)
        self.assertIn(self.enemy.seat, prompt.legal_target_seats)
        ui.pending_skill_action["cards"] = [material]
        ui.pending_target = self.enemy
        self.assertTrue(ui._can_confirm_play(self.xu))

        submitted = []
        ui._play_active_conversion = (
            lambda player, selected_option, cards=None, target=None:
            submitted.append(
                (player, selected_option, list(cards), target)
            ) or True
        )
        self.assertTrue(ui._submit_play_conversion_choice(
            PlayerChoice(
                prompt_id=prompt.prompt_id,
                player_seat=self.xu.seat,
                confirmed=True,
                card_ids=(material.id,),
                target_seats=(self.enemy.seat,),
                option_id=option.skill.skill_id,
            )
        ))
        self.assertEqual(submitted[0][2], [material])
        self.assertEqual(submitted[0][3], self.enemy)

    def test_kongju_only_disables_sunqinke_as_conversion_target(self):
        sun = make_player(1, "孙沁珂", sunqinke=True)
        sun.hand = [make_card("sun-hand", "闪")]
        engine = GameEngine([self.xu, sun], self.draw_cards)
        engine.state.current_turn = 0
        engine.state.phase = Phase.PLAY
        engine.begin_play_phase(self.xu)
        material = make_card("material", "闪", "spade")
        self.xu.hand = [material]

        option = next(
            candidate
            for candidate in engine.skills.active_play_conversion_options(
                engine, self.xu
            )
            if candidate.skill.skill_id
            == "general.xuxinlin.zhanglinghe"
        )
        self.assertIn(
            material,
            engine.skills.conversion_candidates(self.xu, option),
        )
        self.assertFalse(
            engine.can_submit_active_conversion(
                self.xu, option, [material], (sun,)
            )
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
        ui.borrowed_sword_choice = None
        ui.discard_selected = []
        ui.hint = lambda *_args, **_kwargs: None
        ui.clear_hint = lambda: None

        self.assertTrue(
            ui._begin_play_conversion_selection(self.xu, option)
        )
        prompt = ui.pending_skill_action["choice_prompt"]
        self.assertEqual(prompt.required_targets, 1)
        self.assertEqual(prompt.legal_target_seats, ())
        self.assertFalse(
            ui._play_conversion_card_disabled(self.xu, material)
        )
        self.assertFalse(
            ui._current_play_target_legality(self.xu, sun)
        )
        ui.pending_skill_action["cards"] = [material]
        self.assertFalse(
            ui._current_play_target_legality(self.xu, sun)
        )
        self.assertFalse(ui._can_confirm_play(self.xu))

    def test_red_equipment_does_not_offer_after_resolution_draw(self):
        material = make_card(
            "material", "赤兔", "heart",
            kind=CardKind.EQUIPMENT,
            equipment_type="offensive_mount",
        )
        self.xu.hand = [material]
        self.enemy.hand = [make_card("enemy-card", "杀")]
        option = self._zhanglinghe_option()
        event = self.engine.submit_active_conversion(
            self.xu, option, [material], (self.enemy,)
        )
        self.assertEqual(
            self.engine.triggered_skill_actions(
                self.xu,
                SkillTiming.AFTER_CARD_RESOLUTION,
                event,
            ),
            [],
        )

    def test_standalone_trigger_prompt_restores_clean_parent_state(self):
        material = make_card(
            "material", "仁王盾", "club",
            kind=CardKind.EQUIPMENT,
            equipment_type="armor",
        )
        self.xu.hand = [material]
        self.enemy.hand = [make_card("enemy-card", "杀")]
        option = self._zhanglinghe_option()
        event = self.engine.submit_active_conversion(
            self.xu, option, [material], (self.enemy,)
        )

        ui = GameUI.__new__(GameUI)
        ui.engine = self.engine
        ui.next_prompt_id = 1
        ui.prompt_handlers = {}
        ui.wd = False
        ui.dt = None
        ui.da = None
        ui.active_prompt = None
        ui.ai_response_at = 0
        ui.response_time_remaining = 0
        ui.response_timer_last_tick = 0
        ui.response_card_name = ""
        ui.response_source_name = ""
        ui.response_source_card = None
        ui.response_source_physical_cards = ()
        ui.response_action = "打出"
        ui.response_success_callback = None
        ui.response_failure_callback = None
        ui.skill_prompt_cards = []
        ui.skill_prompt_required_cards = 0
        ui.skill_prompt_selected = set()
        ui.skill_prompt_targets = []
        ui.skill_prompt_selected_target = None
        ui.hint = lambda *_args, **_kwargs: None
        ui.clear_hint = lambda: None
        ui.msg = lambda *_args, **_kwargs: None
        ui.play_equipment_sound = lambda *_args, **_kwargs: None
        ui._present_skill_resolution = (
            lambda _result, on_complete, action=None:
            on_complete()
        )
        completed = []

        ui._begin_triggered_skill_sequence(
            self.xu,
            SkillTiming.AFTER_CARD_RESOLUTION,
            event,
            lambda: completed.append(True),
        )
        self.assertTrue(ui.wd)
        prompt_id = ui.active_prompt.prompt_id
        self.assertTrue(ui._submit_skill_prompt(prompt_id, True))

        self.assertEqual(completed, [True])
        self.assertFalse(ui.wd)
        self.assertIsNone(ui.dt)
        self.assertIsNone(ui.da)
        self.assertIsNone(ui.active_prompt)
        self.assertEqual(ui.response_card_name, "")
        self.assertEqual(ui.response_source_name, "")
        self.assertEqual(self.xu.slash_use_count, 0)
        self.assertFalse(self.xu.slash_used)

    def test_lvfei_gains_club_discarded_by_dismantlement(self):
        club = make_card("club-card", "闪", "club")
        source = make_card(
            "dismantlement", "过河拆桥", "spade",
            kind=CardKind.TRICK,
        )
        self.enemy.hand = [club]
        event = self.engine.resolve_target_card_trick(
            self.enemy, "过河拆桥", self.enemy, club,
            source_card=source,
        )
        self.assertIsInstance(event, TrickCardDiscardEvent)
        self.assertIn(club, self.engine.discard_pile)
        actions = self.engine.global_triggered_skill_actions(
            SkillTiming.CARD_DISCARDED_BY_TRICK, event
        )
        self.assertEqual(len(actions), 1)
        result = self.engine.resolve_triggered_skill(actions[0])
        self.assertTrue(result.applied)
        self.assertIn(club, self.xu.hand)
        self.assertNotIn(club, self.engine.discard_pile)
        self.assertEqual(
            result.move_events[0].from_zone, "discard_pile"
        )

    def test_lvfei_does_not_trigger_for_non_club(self):
        spade = make_card("spade-card", "闪", "spade")
        self.enemy.hand = [spade]
        event = self.engine.resolve_target_card_trick(
            self.enemy, "过河拆桥", self.enemy, spade
        )
        self.assertEqual(
            self.engine.global_triggered_skill_actions(
                SkillTiming.CARD_DISCARDED_BY_TRICK, event
            ),
            [],
        )

    def test_shenshen_counts_effective_card_and_bonuses_next_draw(self):
        for index in range(4):
            self.engine.record_card_use(
                self.xu,
                make_card(
                    f"use-{index}", "过河拆桥",
                    kind=CardKind.TRICK,
                ),
            )
        event = self.engine.end_play_phase(self.xu)
        actions = self.engine.triggered_skill_actions(
            self.xu, SkillTiming.PLAY_PHASE_END, event
        )
        self.assertEqual(len(actions), 1)
        result = self.engine.resolve_triggered_skill(actions[0])
        self.assertTrue(result.applied)
        self.assertEqual(self.xu.pending_draw_phase_bonus, 1)

        self.engine.state.phase = Phase.DRAW
        draw_event = self.engine.begin_draw_phase(self.xu)
        self.assertEqual(draw_event.base_draw_count, 3)
        self.assertEqual(draw_event.draw_count, 3)
        self.assertEqual(self.xu.pending_draw_phase_bonus, 0)

    def test_shenshen_bonus_is_not_consumed_without_entering_draw_phase(self):
        self.xu.pending_draw_phase_bonus = 1
        self.engine.state.phase = Phase.JUDGE
        # 跳过摸牌阶段时不会调用 begin_draw_phase，奖励仍属于“下个摸牌阶段”。
        self.assertEqual(self.xu.pending_draw_phase_bonus, 1)
        self.engine.state.phase = Phase.DRAW
        event = self.engine.begin_draw_phase(self.xu)
        self.assertEqual(event.draw_count, 3)

    def test_ai_uses_public_values_without_sacrificing_high_value_peach(self):
        peach = make_card("peach", "桃", "spade")
        low_black_equip = make_card(
            "low-equip", "绝影", "club",
            kind=CardKind.EQUIPMENT,
            equipment_type="defensive_mount",
        )
        self.xu.is_ai = True
        self.xu.hand = [peach, low_black_equip]
        self.enemy.equipment = [
            make_card(
                "enemy-armor", "八卦阵", "heart",
                kind=CardKind.EQUIPMENT,
                equipment_type="armor",
            )
        ]
        option = self._zhanglinghe_option()
        decision = (
            self.engine.skills.ai_choose_active_play_conversion(
                self.engine, self.xu, option
            )
        )
        self.assertIsNotNone(decision)
        self.assertEqual(decision.cards, (low_black_equip,))
        self.assertEqual(decision.target, self.enemy)


if __name__ == "__main__":
    unittest.main()
