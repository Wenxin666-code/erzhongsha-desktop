import unittest
from pathlib import Path

from src.engine import GameEngine
from src.loader import load_generals
from src.models import (
    Card, CardKind, DamageEvent, DyingEvent, General, GeneralSkillRef,
    Phase, Player, SkillTiming,
)


ROOT = Path(__file__).resolve().parents[1]


def make_card(card_id, *, name="测试牌", equipment_type=None):
    return Card(
        id=card_id,
        name=name,
        suit="heart",
        rank="7",
        kind=(
            CardKind.EQUIPMENT
            if equipment_type else CardKind.BASIC
        ),
        equipment_type=equipment_type,
    )


def make_player(seat, name, *, zhangyiyan=False):
    skills = []
    if zhangyiyan:
        skills = [
            GeneralSkillRef(
                skill_id="general.zhangyiyan.erwo_tongxin",
                name="尔我同心",
            ),
            GeneralSkillRef(
                skill_id="general.zhangyiyan.xiaoye_shiyi",
                name="小爷是一",
            ),
        ]
    hp = 3 if zhangyiyan else 4
    return Player(
        seat=seat,
        general=General(
            id="zhangyiyan" if zhangyiyan else f"general-{seat}",
            name=name,
            kingdom="神" if zhangyiyan else "魏",
            hp=hp,
            gender="male",
            playable=True,
            skills=skills,
        ),
        hp=hp,
        max_hp=hp,
    )


class ZhangYiyanSkillTest(unittest.TestCase):
    def test_general_is_registered_and_playable(self):
        general = next(
            general for general in load_generals(
                ROOT / "data" / "generals.yml"
            )
            if general.id == "zhangyiyan"
        )
        self.assertTrue(general.playable)
        self.assertEqual(general.hp, 3)
        self.assertEqual(
            [skill.skill_id for skill in general.skills],
            [
                "general.zhangyiyan.erwo_tongxin",
                "general.zhangyiyan.xiaoye_shiyi",
            ],
        )

    def test_erwo_tongxin_draws_one_card_per_damage_point(self):
        current = make_player(0, "当前角色")
        zhang = make_player(1, "张艺严", zhangyiyan=True)
        engine = GameEngine(
            [current, zhang],
            [
                make_card("drawn_1"),
                make_card("drawn_2"),
                make_card("drawn_3"),
            ],
        )
        one_damage = DamageEvent(
            amount=1, source_player=current
        )
        actions = engine.global_triggered_skill_actions(
            SkillTiming.AFTER_ANY_DAMAGE, one_damage
        )
        self.assertEqual(len(actions), 1)
        result = engine.resolve_triggered_skill(actions[0])
        self.assertTrue(result.applied)
        self.assertEqual(len(zhang.hand), 1)

        two_damage = DamageEvent(
            amount=2, source_player=current
        )
        actions = engine.global_triggered_skill_actions(
            SkillTiming.AFTER_ANY_DAMAGE, two_damage
        )
        self.assertEqual(len(actions), 1)
        result = engine.resolve_triggered_skill(actions[0])
        self.assertTrue(result.applied)
        self.assertEqual(len(zhang.hand), 3)
        self.assertEqual(
            {card.id for card in zhang.hand},
            {"drawn_1", "drawn_2", "drawn_3"},
        )

    def test_erwo_tongxin_inherits_original_damage_source(self):
        source = make_player(0, "伤害来源")
        dying = make_player(1, "濒死角色")
        zhang = make_player(2, "张艺严", zhangyiyan=True)
        engine = GameEngine([source, dying, zhang], [])
        original = DamageEvent(
            amount=1, source_player=source
        )
        event = DyingEvent(
            target=dying, damage_event=original
        )

        actions = engine.global_triggered_skill_actions(
            SkillTiming.ENTER_DYING, event
        )
        self.assertEqual(len(actions), 1)
        result = engine.resolve_triggered_skill(actions[0])

        self.assertTrue(result.applied)
        self.assertEqual(result.request.kind, "damage")
        self.assertIs(
            result.request.context.source_player,
            source,
        )
        self.assertIs(result.request.legal_targets[0], zhang)

    def test_erwo_tongxin_preserves_source_less_dying(self):
        dying = make_player(0, "濒死角色")
        zhang = make_player(1, "张艺严", zhangyiyan=True)
        engine = GameEngine([dying, zhang], [])
        event = DyingEvent(
            target=dying,
            damage_event=DamageEvent(amount=1),
        )
        action = engine.global_triggered_skill_actions(
            SkillTiming.ENTER_DYING, event
        )[0]
        result = engine.resolve_triggered_skill(action)

        self.assertIsNone(result.request.context.source_player)
        zhang.hp = 1
        self.assertEqual(
            engine.global_triggered_skill_actions(
                SkillTiming.ENTER_DYING, event
            ),
            [],
        )

    def test_xiaoye_shiyi_discards_owned_cards_and_grants_next_phase(self):
        zhang = make_player(0, "张艺严", zhangyiyan=True)
        target = make_player(1, "目标")
        hand = make_card("hand-cost")
        armor = make_card("armor-cost", equipment_type="armor")
        zhang.hand = [hand]
        zhang.equipment = [armor]
        engine = GameEngine([zhang, target], [])
        engine.state.phase = Phase.PLAY

        action = engine.active_skill_actions(zhang)[0]
        self.assertTrue(
            engine.can_submit_active_skill(
                action, (hand, armor), (target,)
            )
        )
        result = engine.submit_active_skill(
            action, (hand, armor), (target,)
        )

        self.assertTrue(result.applied)
        self.assertEqual(zhang.hand, [])
        self.assertEqual(zhang.equipment, [])
        self.assertEqual(target.pending_slash_use_bonus, 1)
        self.assertEqual(target.active_slash_use_bonus, 0)
        self.assertEqual(
            {card.id for card in engine.discard_pile},
            {"hand-cost", "armor-cost"},
        )

    def test_xiaoye_shiyi_bonus_allows_one_extra_slash_next_play_phase(self):
        target = make_player(0, "目标")
        enemy = make_player(1, "敌方")
        engine = GameEngine([target, enemy], [])
        target.pending_slash_use_bonus = 1
        engine.begin_play_phase(target)
        self.assertEqual(target.pending_slash_use_bonus, 0)
        self.assertEqual(target.active_slash_use_bonus, 1)

        first = make_card("slash-1", name="杀")
        second = make_card("slash-2", name="杀")
        third = make_card("slash-3", name="杀")
        target.hand = [first, second, third]
        for card in (first, second):
            event = engine.create_slash_event(
                target,
                [card],
                [enemy],
                ignore_distance=True,
            )
            engine.finish_processing_card(event.physical_cards[0])
        self.assertFalse(engine.can_use_slash(target))
        with self.assertRaises(ValueError):
            engine.create_slash_event(
                target,
                [third],
                [enemy],
                ignore_distance=True,
            )


if __name__ == "__main__":
    unittest.main()
