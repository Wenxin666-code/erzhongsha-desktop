import unittest
from pathlib import Path

from src.engine import GameEngine
from src.loader import load_generals
from src.models import (
    Card, CardKind, General, GeneralSkillRef, Phase, Player, SkillTiming,
)


ROOT = Path(__file__).resolve().parents[1]


def make_card(card_id, name="测试牌", *, equipment_type=None):
    return Card(
        id=card_id,
        name=name,
        suit="spade",
        rank="7",
        kind=(
            CardKind.EQUIPMENT if equipment_type else CardKind.BASIC
        ),
        equipment_type=equipment_type,
    )


def make_player(seat, name, *, wangzhongwei=False, is_ai=False):
    skills = []
    hp = 4
    if wangzhongwei:
        hp = 5
        skills = [
            GeneralSkillRef(
                skill_id="general.wangzhongwei.study_1_4",
                name="1：4学习法",
            ),
            GeneralSkillRef(
                skill_id="general.wangzhongwei.weishen",
                name="伟神",
            ),
        ]
    return Player(
        seat=seat,
        general=General(
            id="wangzhongwei" if wangzhongwei else f"general-{seat}",
            name=name,
            kingdom="神" if wangzhongwei else "魏",
            hp=hp,
            playable=True,
            skills=skills,
        ),
        hp=hp,
        max_hp=hp,
        is_ai=is_ai,
    )


class WangZhongweiSkillTest(unittest.TestCase):
    def test_general_is_registered_and_playable(self):
        general = next(
            general for general in load_generals(
                ROOT / "data" / "generals.yml"
            )
            if general.id == "wangzhongwei"
        )
        self.assertTrue(general.playable)
        self.assertEqual(general.hp, 5)
        self.assertEqual(
            [skill.skill_id for skill in general.skills],
            [
                "general.wangzhongwei.study_1_4",
                "general.wangzhongwei.weishen",
            ],
        )

    def test_study_default_branch_draws_two_and_sets_slash_damage_two(self):
        wang = make_player(0, "王钟伟", wangzhongwei=True)
        enemy = make_player(1, "敌方")
        engine = GameEngine([wang, enemy], [])

        event = engine.begin_draw_phase(wang)
        actions = engine.triggered_skill_actions(
            wang, SkillTiming.DRAW_PHASE, event
        )

        self.assertEqual(event.draw_count, 2)
        self.assertEqual(wang.draw_phase_card_count, 2)
        self.assertEqual(wang.turn_slash_base_damage, 2)
        self.assertEqual(len(actions), 1)

    def test_draw_phase_records_one_multi_card_draw_event(self):
        wang = make_player(0, "王钟伟", wangzhongwei=True)
        enemy = make_player(1, "敌方")
        engine = GameEngine(
            [wang, enemy],
            [
                make_card("draw-a"),
                make_card("draw-b"),
                make_card("draw-c"),
            ],
        )
        observed = []
        engine.draw_cards_listener = observed.append

        engine.draw_phase(wang)

        self.assertEqual(len(wang.hand), 2)
        self.assertEqual(len(engine.draw_event_history), 1)
        draw_event = engine.draw_event_history[0]
        self.assertEqual(draw_event.player.seat, wang.seat)
        self.assertEqual(draw_event.count, 2)
        self.assertEqual(draw_event.reason, "摸牌阶段")
        self.assertEqual(observed, [draw_event])
        moves = [
            move for move in engine.card_move_history
            if move.move_id in draw_event.move_ids
        ]
        self.assertEqual(len(moves), 2)
        self.assertEqual(len({move.batch_id for move in moves}), 1)
        published = [
            event for event in engine.rule_event_history
            if event.event_type == "cards_drawn"
        ]
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].data["count"], 2)

    def test_study_reduced_draw_branch_sets_slash_damage_four(self):
        wang = make_player(0, "王钟伟", wangzhongwei=True)
        enemy = make_player(1, "敌方")
        engine = GameEngine([wang, enemy], [])
        event = engine.begin_draw_phase(wang)
        action = engine.triggered_skill_actions(
            wang, SkillTiming.DRAW_PHASE, event
        )[0]

        result = engine.resolve_triggered_skill(action)

        self.assertTrue(result.applied)
        self.assertEqual(event.draw_count, 1)
        self.assertEqual(wang.draw_phase_card_count, 1)
        self.assertEqual(wang.turn_slash_base_damage, 4)

    def test_study_ai_only_reduces_draw_with_physical_slash_in_hand(self):
        wang = make_player(
            0, "王钟伟", wangzhongwei=True, is_ai=True
        )
        enemy = make_player(1, "敌方")
        engine = GameEngine([wang, enemy], [])
        event = engine.begin_draw_phase(wang)
        action = engine.triggered_skill_actions(
            wang, SkillTiming.DRAW_PHASE, event
        )[0]

        wang.hand = [make_card("jink", "闪")]
        self.assertFalse(
            engine.skills.ai_should_activate_triggered(engine, action)
        )
        wang.hand.append(make_card("slash", "杀"))
        self.assertTrue(
            engine.skills.ai_should_activate_triggered(engine, action)
        )

    def test_study_damage_is_used_by_slash_and_wine_stacks(self):
        wang = make_player(0, "王钟伟", wangzhongwei=True)
        enemy = make_player(1, "敌方")
        engine = GameEngine([wang, enemy], [])
        event = engine.begin_draw_phase(wang)
        action = engine.triggered_skill_actions(
            wang, SkillTiming.DRAW_PHASE, event
        )[0]
        engine.resolve_triggered_skill(action)
        slash = make_card("slash", "杀")
        wang.hand = [slash]
        wang.drunk = True

        slash_event = engine.create_slash_event(
            wang, [slash], [enemy], ignore_distance=True
        )

        self.assertEqual(slash_event.damage, 5)

    def test_study_state_resets_at_turn_end(self):
        wang = make_player(0, "王钟伟", wangzhongwei=True)
        enemy = make_player(1, "敌方")
        engine = GameEngine([wang, enemy], [])
        wang.turn_slash_base_damage = 4
        wang.draw_phase_card_count = 1

        engine.finish_turn()

        self.assertEqual(wang.turn_slash_base_damage, 1)
        self.assertEqual(wang.draw_phase_card_count, 2)

    def test_weishen_is_once_per_play_phase_and_returns_choice_request(self):
        wang = make_player(0, "王钟伟", wangzhongwei=True)
        enemy = make_player(1, "敌方")
        enemy.hand = [make_card("jink", "闪")]
        engine = GameEngine([wang, enemy], [])
        engine.state.phase = Phase.PLAY
        action = next(
            action for action in engine.active_skill_actions(wang)
            if action.skill.skill_id == "general.wangzhongwei.weishen"
        )

        result = engine.submit_active_skill(
            action, (), (enemy,)
        )

        self.assertTrue(result.applied)
        self.assertEqual(result.request.kind, "jink_or_gain")
        self.assertIs(result.request.source_player, wang)
        self.assertEqual(result.request.legal_targets, (enemy,))
        self.assertFalse(any(
            candidate.skill.skill_id == "general.wangzhongwei.weishen"
            for candidate in engine.active_skill_actions(wang)
        ))

    def test_transfer_owned_card_moves_hand_or_equipment_to_recipient(self):
        wang = make_player(0, "王钟伟", wangzhongwei=True)
        enemy = make_player(1, "敌方")
        armor = make_card("armor", "八卦阵", equipment_type="armor")
        enemy.equipment = [armor]
        engine = GameEngine([wang, enemy], [])

        move = engine.transfer_owned_card(
            enemy, wang, armor, "伟神获得"
        )

        self.assertIsNotNone(move)
        self.assertEqual(move.from_zone, "equipment")
        self.assertEqual(move.to_zone, "hand")
        self.assertNotIn(armor, enemy.equipment)
        self.assertIn(armor, wang.hand)
        self.assertIn(move, engine.card_move_history)

    def test_weishen_ai_uses_public_slash_target_priority(self):
        wang = make_player(
            0, "王钟伟", wangzhongwei=True, is_ai=True
        )
        low_hp_with_jink = make_player(1, "低体力有闪")
        high_hp_without_jink = make_player(2, "高体力无闪")
        low_hp_with_jink.hp = 1
        high_hp_without_jink.hp = 3
        low_hp_with_jink.hand = [make_card("jink", "闪")]
        high_hp_without_jink.hand = [make_card("peach", "桃")]
        engine = GameEngine(
            [wang, low_hp_with_jink, high_hp_without_jink], []
        )
        engine.state.phase = Phase.PLAY
        action = next(
            action for action in engine.active_skill_actions(wang)
            if action.skill.skill_id == "general.wangzhongwei.weishen"
        )

        decision = engine.skills.ai_decide_active_skill(engine, action)

        self.assertIsNotNone(decision)
        self.assertEqual(decision.targets, (low_hp_with_jink,))

        # 只替换同数量的隐藏手牌牌面，不得改变AI选择。
        low_hp_with_jink.hand = [make_card("hidden-a", "桃")]
        high_hp_without_jink.hand = [make_card("hidden-b", "闪")]
        decision_after_hidden_change = (
            engine.skills.ai_decide_active_skill(engine, action)
        )
        self.assertEqual(
            decision_after_hidden_change.targets,
            (low_hp_with_jink,),
        )


if __name__ == "__main__":
    unittest.main()
