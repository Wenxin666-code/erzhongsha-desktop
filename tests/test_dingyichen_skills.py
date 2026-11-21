import unittest
from pathlib import Path

from main import GameUI
from src.audio import SoundManager
from src.engine import GameEngine
from src.loader import load_generals
from src.models import (
    Card, CardKind, CardMoveEvent, CardResponseEvent, DamageEvent, General,
    GeneralSkillRef, JudgmentStep, Player, SkillTiming,
)


ROOT = Path(__file__).resolve().parents[1]


def card(card_id, suit="heart", rank="7", equipment_type=None):
    return Card(
        id=card_id,
        name="测试牌",
        suit=suit,
        rank=rank,
        kind=CardKind.EQUIPMENT if equipment_type else CardKind.BASIC,
        equipment_type=equipment_type,
    )


def player(seat, name, skills=(), *, is_ai=False):
    return Player(
        seat=seat,
        general=General(
            id=name,
            name=name,
            kingdom="神" if name == "丁逸晨" else "魏",
            hp=4,
            playable=True,
            skills=[
                GeneralSkillRef(skill_id=skill_id, name=skill_name)
                for skill_id, skill_name in skills
            ],
        ),
        hp=4,
        max_hp=4,
        is_ai=is_ai,
    )


class DingYichenSkillTest(unittest.TestCase):
    def setUp(self):
        self.ding = player(
            0,
            "丁逸晨",
            (
                ("general.yinhe_lord", "银河领主"),
                ("general.kiss", "Kiss"),
            ),
        )
        self.enemy = player(1, "敌将")
        self.engine = GameEngine(
            [self.ding, self.enemy],
            [card("draw", "club")],
        )

    def test_general_is_playable_and_uses_registered_skills(self):
        ding = next(
            general for general in load_generals(ROOT / "data" / "generals.yml")
            if general.name == "丁逸晨"
        )
        self.assertTrue(ding.playable)
        self.assertEqual(ding.kingdom, "神")
        self.assertEqual(ding.hp, 4)
        self.assertEqual(
            [skill.skill_id for skill in ding.skills],
            ["general.yinhe_lord", "general.kiss"],
        )

    def test_yinhe_lord_only_triggers_outside_turn_for_jink_or_damage(self):
        self.engine.state.current_turn = self.enemy.seat
        jink = card("jink")
        jink.name = "闪"
        response = CardResponseEvent(
            player=self.ding,
            effective_card=jink,
            action="打出",
        )
        self.assertEqual(
            len(self.engine.triggered_skill_actions(
                self.ding, SkillTiming.AFTER_CARD_RESPONSE, response
            )),
            1,
        )
        response_used = response.model_copy(update={"action": "使用"})
        self.assertFalse(self.engine.triggered_skill_actions(
            self.ding, SkillTiming.AFTER_CARD_RESPONSE, response_used
        ))
        self.assertEqual(
            len(self.engine.triggered_skill_actions(
                self.ding,
                SkillTiming.AFTER_DAMAGE,
                DamageEvent(amount=2),
            )),
            1,
        )
        self.engine.state.current_turn = self.ding.seat
        self.assertFalse(self.engine.triggered_skill_actions(
            self.ding, SkillTiming.AFTER_CARD_RESPONSE, response
        ))

    def test_yinhe_lord_builds_judgment_then_hp_loss_request(self):
        self.engine.state.current_turn = self.enemy.seat
        action = self.engine.triggered_skill_actions(
            self.ding,
            SkillTiming.AFTER_DAMAGE,
            DamageEvent(amount=1),
        )[0]
        result = self.engine.resolve_triggered_skill(action)
        self.assertEqual(result.request.kind, "judgment")
        self.assertEqual(result.request.judgment_rule, "spade")

        judged = card("spade-judge", "spade")
        event = self.engine.begin_judgment(
            self.ding, "银河领主", "spade"
        )
        original = event.current_card
        self.engine.processing_area.remove(original)
        self.engine.processing_area.append(judged)
        event = event.model_copy(update={"current_card": judged})
        event = self.engine.finalize_judgment(event)
        target_result = self.engine.skills.continue_triggered_action(
            self.engine, action, result.request, event
        )
        self.assertEqual(target_result.request.kind, "choose_target")
        hp_result = self.engine.skills.continue_triggered_action(
            self.engine,
            action,
            target_result.request,
            self.enemy,
        )
        self.assertEqual(hp_result.hp_loss_events[0].amount, 2)
        self.assertEqual(self.enemy.hp, 2)
        self.assertEqual(
            self.engine.rule_event_history[-1].event_type, "hp_lost"
        )

    def test_kiss_replacement_gains_old_judgment_face_up(self):
        old = card("old-judge", "heart")
        replacement = card("replacement", "spade")
        self.ding.hand.append(replacement)
        self.engine.draw_pile = [old]
        event = self.engine.begin_judgment(
            self.enemy, "银河领主", "spade"
        )
        action = self.engine.skills.judgment_replacement_actions(
            self.engine, event
        )[0]
        result = self.engine.skills.resolve_judgment_replacement(
            self.engine, action, replacement
        )
        self.assertTrue(result.applied)
        self.assertIs(result.event.current_card, replacement)
        self.assertIn(old, self.ding.hand)
        self.assertNotIn(old, self.engine.processing_area)
        self.assertEqual(result.move_events[0].visibility, "public")
        completed = self.engine.finalize_judgment(result.event)
        self.assertEqual(completed.step, JudgmentStep.COMPLETED)
        self.assertTrue(completed.result)
        self.assertIn(replacement, self.engine.discard_pile)
        self.assertNotIn(old, self.engine.discard_pile)

    def test_kiss_accepts_equipment_and_ai_only_changes_to_desired_result(self):
        equipment = card("armor", "spade", equipment_type="armor")
        self.ding.equipment.append(equipment)
        self.engine.draw_pile = [card("old", "heart")]
        event = self.engine.begin_judgment(
            self.ding, "银河领主", "spade"
        )
        action = self.engine.skills.judgment_replacement_actions(
            self.engine, event
        )[0]
        self.assertIs(
            self.engine.skills.ai_choose_judgment_replacement(
                self.engine, action
            ),
            equipment,
        )
        result = self.engine.skills.resolve_judgment_replacement(
            self.engine, action, equipment
        )
        self.assertTrue(result.applied)
        self.assertNotIn(equipment, self.ding.equipment)

    def test_hp_loss_ui_has_sound_but_no_damage_or_hit_animation(self):
        ui = GameUI.__new__(GameUI)
        ui.engine = self.engine
        sounds = []
        messages = []
        completed = []
        ui.play_system_sound = lambda key, volume=None: sounds.append(key)
        ui.msg = messages.append
        ui._begin_dying = lambda *args, **kwargs: self.fail(
            "未进入濒死时不应调用求桃"
        )
        ui._start_hit_animation = lambda *_: self.fail(
            "失去体力不得播放受伤位移动画"
        )
        ui._play_visual_effect = lambda *_args, **_kwargs: self.fail(
            "失去体力不得播放受伤特效"
        )
        hp_event = self.engine.lose_hp(
            self.enemy, 2, reason="银河领主"
        )
        ui._apply_hp_loss_events(
            [hp_event],
            lambda: completed.append(True),
        )
        self.assertEqual(self.enemy.hp, 2)
        self.assertEqual(sounds, ["damage2"])
        self.assertTrue(completed)

    def test_public_diy_audio_is_absent_and_playback_safely_skips(self):
        sound = SoundManager(Path(__file__).parents[1] / "sound")
        for skill_id in ("general.yinhe_lord", "general.kiss"):
            self.assertFalse(sound.skill_voice_paths(
                "dingyichen", "default", skill_id
            ))
            self.assertFalse(sound.play_skill(
                "dingyichen", "default", skill_id
            ))
        self.assertIsNone(sound.death_voice_path("dingyichen", "default"))
        self.assertFalse(sound.play_death("dingyichen", "default"))

    def test_judgment_replacement_prompt_keeps_confirm_cancel_visible(self):
        ui = GameUI.__new__(GameUI)
        ui.wd = True
        ui.dt = self.ding
        ui.judgment_display_in_progress = True
        ui.active_prompt = object()
        self.assertTrue(
            ui._should_draw_response_buttons(self.ding, False)
        )
        ui.active_prompt = None
        self.assertFalse(
            ui._should_draw_response_buttons(self.ding, False)
        )

    def test_skill_selected_target_uses_normal_target_frame_state(self):
        ui = GameUI.__new__(GameUI)
        ui.pending_targets = []
        ui.pending_target = None
        ui.skill_prompt_selected_target = self.enemy
        self.assertTrue(ui._is_selected_target(self.enemy))
        self.assertFalse(ui._is_selected_target(self.ding))

    def test_judgment_replacement_flies_to_current_card_position(self):
        ui = GameUI.__new__(GameUI)
        original = card("original")
        replacement = card("replacement")
        original_position = (631, 402)
        ui.waiting_cards = [{
            "card": original,
            "pos": original_position,
        }]
        ui.animations = []
        ui._queue_card_animation(
            replacement,
            source=(100, 900),
            waiting_position=ui._waiting_card_position(original),
        )
        self.assertEqual(ui.animations[0]["dest"], original_position)

    def test_gained_judgment_card_is_hidden_until_gain_animation_ends(self):
        ui = GameUI.__new__(GameUI)
        ui.engine = self.engine
        ui.hidden_draw_cards = set()
        gained = card("gained-judgment")
        move = CardMoveEvent(
            move_id=1,
            card=gained,
            to_player_seat=self.ding.seat,
            from_zone="processing",
            to_zone="hand",
            reason="Kiss获得原判定牌",
            visibility="public",
        )
        ui._hide_skill_hand_gains_until_animated((move,))
        self.assertIn(ui._card_token(gained), ui.hidden_draw_cards)


if __name__ == "__main__":
    unittest.main()
