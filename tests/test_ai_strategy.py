import unittest

from main import GameUI
from src.ai import (
    choose_borrowed_sword_plan, choose_control_card_choice,
    choose_control_target, choose_equipment_to_play,
    choose_fire_attack_target, choose_low_value_cards,
    choose_slash_plan, choose_zhangba_plan,
    should_use_analeptic_for_slash, should_use_five_grains,
    should_use_peach_for_dying, should_use_peach_garden,
)
from src.engine import GameEngine
from src.models import (
    Card, CardKind, General, GeneralSkillRef, Player, SkillTiming,
)
from src.skill_modules.base import SkillAIContext


def make_card(
    name, *, ident=None, suit="heart", kind=CardKind.BASIC,
    equipment_type=None,
):
    return Card(
        id=ident or f"{name}-{suit}",
        name=name,
        suit=suit,
        rank="7",
        kind=kind,
        equipment_type=equipment_type,
    )


def equipment(name, equipment_type, ident=None):
    return make_card(
        name,
        ident=ident,
        suit="spade",
        kind=CardKind.EQUIPMENT,
        equipment_type=equipment_type,
    )


def trick(name, ident=None, suit="club"):
    return make_card(
        name,
        ident=ident,
        suit=suit,
        kind=CardKind.TRICK,
    )


def make_player(seat, *, side=None, hp=4):
    return Player(
        seat=seat,
        general=General(
            id=f"g{seat}",
            name=f"角色{seat}",
            kingdom="魏",
            hp=4,
            skills=[],
        ),
        hp=hp,
        max_hp=4,
        side=side,
    )


class AIStrategyTest(unittest.TestCase):
    def test_dying_peach_only_saves_self_or_ally(self):
        helper = make_player(0, side="a")
        ally = make_player(1, side="a")
        enemy = make_player(2, side="b")
        engine = GameEngine([helper, ally, enemy], [])

        self.assertTrue(
            should_use_peach_for_dying(engine, helper, helper)
        )
        self.assertTrue(
            should_use_peach_for_dying(engine, helper, ally)
        )
        self.assertFalse(
            should_use_peach_for_dying(engine, helper, enemy)
        )

    def test_ai_does_not_use_peach_on_dying_enemy(self):
        dying = make_player(0)
        helper = make_player(1)
        helper.is_ai = True
        dying.hp = 0
        peach = make_card("桃", ident="enemy-peach")
        helper.hand.append(peach)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([dying, helper], [])
        ui.dt = helper
        ui.dying_target = dying
        ui.active_prompt = None
        ui.judgment_display_in_progress = False
        ui.ai_response_at = 1
        used = []
        skipped = []
        ui._use_peach_for_dying = (
            lambda *_args: used.append(True)
        )
        ui._skip_dying_peach = (
            lambda player: skipped.append(player)
        )

        ui._ad()

        self.assertFalse(used)
        self.assertEqual(skipped, [helper])
        self.assertIn(peach, helper.hand)

    def test_dying_resolution_rejects_ai_peach_on_enemy(self):
        dying = make_player(0)
        helper = make_player(1)
        helper.is_ai = True
        dying.hp = 0
        peach = make_card("桃", ident="guarded-enemy-peach")
        helper.hand.append(peach)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([dying, helper], [])
        ui.dying_target = dying
        skipped = []
        ui._skip_dying_peach = (
            lambda player: skipped.append(player)
        )

        ui._use_peach_for_dying(helper, peach)

        self.assertEqual(skipped, [helper])
        self.assertEqual(dying.hp, 0)
        self.assertIn(peach, helper.hand)
        self.assertNotIn(peach, ui.engine.discard_pile)

    def test_play_phase_category_order_stops_after_first_action(self):
        source = make_player(0)
        ui = GameUI.__new__(GameUI)
        calls = []
        names = [
            "_ai_try_early_active_skills",
            "_ai_try_wuzhong",
            "_ai_try_iron_chain",
            "_ai_try_control_trick",
            "_ai_try_borrowed_sword",
            "_ai_try_fire_attack",
            "_ai_try_global_benefit",
            "_ai_try_equipment",
            "_ai_try_peach",
            "_ai_try_damage_trick",
            "_ai_try_slash",
            "_ai_try_delayed_trick",
        ]
        for name in names:
            setattr(
                ui,
                name,
                lambda _player, name=name: (
                    calls.append(name) or name == "_ai_try_fire_attack"
                ),
            )

        self.assertTrue(ui._ap(source))
        self.assertEqual(calls, names[:6])

    def test_fire_attack_is_not_used_as_only_hand_card(self):
        source = make_player(0, side="a")
        target = make_player(1, side="b")
        fire_attack = trick("火攻", "fire-attack", "heart")
        target.hand = [make_card("闪", ident="target-card")]
        source.hand = [fire_attack]
        engine = GameEngine([source, target], [])

        self.assertIsNone(
            choose_fire_attack_target(engine, source)
        )

        source.hand.append(make_card("闪", ident="payment"))
        self.assertIs(
            choose_fire_attack_target(engine, source), target
        )

    def test_global_benefit_cards_compare_both_sides(self):
        source = make_player(0, side="a")
        friend = make_player(1, side="a")
        enemy = make_player(2, side="b")
        engine = GameEngine([source, friend, enemy], [])

        self.assertTrue(should_use_five_grains(engine, source))
        enemy_two = make_player(3, side="b")
        enemy_three = make_player(4, side="b")
        engine = GameEngine(
            [source, friend, enemy, enemy_two, enemy_three], []
        )
        self.assertFalse(should_use_five_grains(engine, source))

        source.hp = 3
        enemy.hp = 3
        self.assertTrue(should_use_peach_garden(engine, source))
        enemy_two.hp = 3
        self.assertFalse(should_use_peach_garden(engine, source))

    def test_borrowed_sword_self_victim_requires_defense(self):
        source = make_player(0, side="a")
        wielder = make_player(1, side="b")
        wielder.equipment.append(
            equipment("青龙偃月刀", "weapon")
        )
        engine = GameEngine([source, wielder], [])

        self.assertIsNone(
            choose_borrowed_sword_plan(engine, source)
        )

        source.hand = [make_card("闪", ident="jink")]
        plan = choose_borrowed_sword_plan(engine, source)
        self.assertIs(plan.wielder, wielder)
        self.assertIs(plan.victim, source)

        source.hand.clear()
        source.equipment.append(equipment("八卦阵", "armor"))
        plan = choose_borrowed_sword_plan(engine, source)
        self.assertIs(plan.victim, source)

        wielder.equipment[0] = equipment("青釭剑", "weapon")
        self.assertIsNone(
            choose_borrowed_sword_plan(engine, source)
        )

    def test_borrowed_sword_prefers_enemy_attacking_enemy(self):
        source = make_player(0, side="a")
        wielder = make_player(1, side="b")
        victim = make_player(2, side="b")
        wielder.equipment.append(
            equipment("青龙偃月刀", "weapon")
        )
        source.hand = [make_card("闪", ident="jink")]
        engine = GameEngine([source, wielder, victim], [])

        plan = choose_borrowed_sword_plan(engine, source)

        self.assertIs(plan.wielder, wielder)
        self.assertIs(plan.victim, victim)

    def test_low_value_selection_preserves_peach_and_dodge(self):
        source = make_player(0)
        target = make_player(1)
        old_mount = equipment("赤兔", "offensive_mount", "old-mount")
        extra_mount = equipment("大宛", "offensive_mount", "extra-mount")
        lightning = trick("闪电", "lightning")
        peach = make_card("桃", ident="peach")
        dodge = make_card("闪", ident="dodge")
        source.equipment.append(old_mount)
        source.hand = [peach, dodge, extra_mount, lightning]
        engine = GameEngine([source, target], [])

        chosen = choose_low_value_cards(
            engine, source, source.hand, 2
        )

        self.assertEqual(chosen, [extra_mount, lightning])

    def test_ai_discard_entry_uses_shared_keep_value(self):
        source = make_player(0)
        target = make_player(1)
        old_mount = equipment("赤兔", "offensive_mount", "old-mount")
        extra_mount = equipment("大宛", "offensive_mount", "extra-mount")
        peach = make_card("桃", ident="peach")
        source.equipment.append(old_mount)
        source.hand = [peach, extra_mount]
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([source, target], [])
        ui._queue_card_animation = lambda *_args, **_kwargs: None
        ui._player_center = lambda _player: (0, 0)
        ui.msg = lambda *_args: None
        ui._schedule_phase_transition = (
            lambda *_args, **_kwargs: None
        )

        ui._perform_ai_discard(source, 1)

        self.assertIn(extra_mount, ui.engine.discard_pile)
        self.assertIn(peach, source.hand)

    def test_zhangba_uses_low_value_pair_that_can_pass_renwang(self):
        source = make_player(0)
        target = make_player(1)
        source.equipment.append(equipment("丈八蛇矛", "weapon"))
        target.equipment.append(equipment("仁王盾", "armor"))
        black_first = trick("闪电", "black-first", "spade")
        black_second = trick("桃园结义", "black-second", "club")
        red_material = trick("五谷丰登", "red-material", "heart")
        peach = make_card("桃", ident="peach", suit="heart")
        source.hand = [
            black_first, black_second, red_material, peach
        ]
        engine = GameEngine([source, target], [])

        plan = choose_zhangba_plan(engine, source)

        self.assertIsNotNone(plan)
        self.assertNotIn(peach, plan.cards)
        effective = engine.skills.build_effective_card(
            "杀", list(plan.cards)
        )
        self.assertNotEqual(effective.color, "black")
        self.assertIs(plan.target, target)

    def test_slash_strategy_avoids_armor_nullification(self):
        source = make_player(0)
        target = make_player(1)
        target.equipment.append(equipment("仁王盾", "armor"))
        black_slash = make_card(
            "杀", ident="black-slash", suit="spade"
        )
        source.hand = [black_slash]
        engine = GameEngine([source, target], [])

        self.assertIsNone(choose_slash_plan(engine, source))

        red_slash = make_card(
            "杀", ident="red-slash", suit="heart"
        )
        source.hand.append(red_slash)
        plan = choose_slash_plan(engine, source)
        self.assertIs(plan.card, red_slash)

    def test_zhuque_converts_vine_slash_only_for_positive_net_benefit(self):
        source = make_player(0, side="a")
        target = make_player(1, side="b")
        source.equipment.append(equipment("朱雀羽扇", "weapon"))
        target.equipment.append(equipment("藤甲", "armor"))
        slash = make_card("杀", ident="slash", suit="spade")
        source.hand = [slash]
        engine = GameEngine([source, target], [])

        plan = choose_slash_plan(engine, source)
        self.assertEqual(plan.effective_name, "火杀")

        friend_one = make_player(2, side="a")
        friend_two = make_player(3, side="a")
        for player in (target, friend_one, friend_two):
            player.chained = True
        engine = GameEngine(
            [source, target, friend_one, friend_two], []
        )
        self.assertIsNone(choose_slash_plan(engine, source))

    def test_control_tricks_prioritize_armor_then_mount_then_weapon(self):
        source = make_player(0)
        weapon_owner = make_player(1)
        mount_owner = make_player(2)
        armor_owner = make_player(3)
        weapon_card = equipment("青龙偃月刀", "weapon")
        mount_card = equipment("赤兔", "offensive_mount")
        armor_card = equipment("八卦阵", "armor")
        weapon_owner.equipment.append(weapon_card)
        mount_owner.equipment.append(mount_card)
        armor_owner.equipment.append(armor_card)
        engine = GameEngine(
            [source, weapon_owner, mount_owner, armor_owner], []
        )

        target = choose_control_target(
            engine,
            source,
            [weapon_owner, mount_owner, armor_owner],
        )
        choice = choose_control_card_choice([
            ("hand", 0, make_card("闪", ident="hidden")),
            ("equipment", 0, weapon_card),
            ("equipment", 1, mount_card),
            ("equipment", 2, armor_card),
        ])

        self.assertIs(target, armor_owner)
        self.assertIs(choice[2], armor_card)

    def test_equipment_plan_replaces_weapon_only_for_tactical_gain(self):
        source = make_player(0)
        target = make_player(1)
        target.equipment.append(equipment("藤甲", "armor"))
        source.equipment.append(equipment("青龙偃月刀", "weapon"))
        fan = equipment("朱雀羽扇", "weapon")
        slash = make_card("杀", ident="slash")
        source.hand = [fan, slash]
        engine = GameEngine([source, target], [])

        before_hand = source.hand[:]
        before_equipment = source.equipment[:]
        self.assertIs(choose_equipment_to_play(engine, source), fan)
        self.assertEqual(source.hand, before_hand)
        self.assertEqual(source.equipment, before_equipment)

        target.equipment = [equipment("仁王盾", "armor")]
        axe = equipment("贯石斧", "weapon")
        source.hand = [axe, slash]
        self.assertIs(choose_equipment_to_play(engine, source), axe)

    def test_equipment_plan_uses_zhangba_crossbow_and_range_check(self):
        source = make_player(0)
        target = make_player(1)
        zhangba = equipment("丈八蛇矛", "weapon")
        source.hand = [
            zhangba, trick("闪电", "cost-a"),
            trick("桃园结义", "cost-b"),
        ]
        engine = GameEngine([source, target], [])
        self.assertIs(choose_equipment_to_play(engine, source), zhangba)

        crossbow = equipment("诸葛连弩", "weapon")
        source.hand = [
            crossbow,
            make_card("杀", ident="slash-a"),
            make_card("杀", ident="slash-b"),
        ]
        self.assertIs(choose_equipment_to_play(engine, source), crossbow)

        source = make_player(0, side="a")
        friends = [
            make_player(1, side="a"),
            make_player(2, side="a"),
        ]
        distant_enemy = make_player(3, side="b")
        friends += [
            make_player(4, side="a"),
            make_player(5, side="a"),
        ]
        crossbow = equipment("诸葛连弩", "weapon")
        source.hand = [
            crossbow,
            make_card("杀", ident="far-slash-a"),
            make_card("杀", ident="far-slash-b"),
        ]
        engine = GameEngine(
            [source, *friends[:2], distant_enemy, *friends[2:]], []
        )
        self.assertIsNone(choose_equipment_to_play(engine, source))

    def test_mount_is_not_replaced_below_limit_but_can_clear_overflow(self):
        source = make_player(0)
        target = make_player(1)
        source.equipment.append(
            equipment("赤兔", "offensive_mount", "old")
        )
        replacement = equipment(
            "大宛", "offensive_mount", "replacement"
        )
        source.hand = [replacement]
        engine = GameEngine([source, target], [])

        self.assertIsNone(choose_equipment_to_play(engine, source))

        source.hp = 1
        source.hand.extend([
            trick("闪电", "overflow-a"),
            trick("桃园结义", "overflow-b"),
        ])
        self.assertIs(
            choose_equipment_to_play(engine, source), replacement
        )

    def test_armor_plan_avoids_vine_against_fan_and_uses_it_in_adversity(self):
        source = make_player(0)
        target = make_player(1)
        target.equipment.append(equipment("朱雀羽扇", "weapon"))
        vine = equipment("藤甲", "armor", "vine")
        renwang = equipment("仁王盾", "armor", "renwang")
        bagua = equipment("八卦阵", "armor", "bagua")
        source.hand = [vine, bagua, renwang]
        engine = GameEngine([source, target], [])

        self.assertIs(choose_equipment_to_play(engine, source), renwang)

        target.equipment.clear()
        source.hp = 2
        self.assertIs(choose_equipment_to_play(engine, source), vine)

    def test_wounded_silver_lion_owner_prioritizes_armor_replacement(self):
        source = make_player(0, hp=2)
        target = make_player(1)
        source.equipment.append(
            equipment("白银狮子", "armor", "silver-lion")
        )
        replacement = equipment("八卦阵", "armor", "replacement")
        tactical_weapon = equipment("丈八蛇矛", "weapon", "zhangba")
        source.hand = [
            tactical_weapon,
            trick("闪电", "material-a"),
            trick("桃园结义", "material-b"),
            replacement,
        ]
        engine = GameEngine([source, target], [])

        self.assertIs(
            choose_equipment_to_play(engine, source), replacement
        )

    def test_ai_does_not_drink_when_silver_lion_wastes_bonus_damage(self):
        source = make_player(0)
        lion_target = make_player(1)
        other_target = make_player(2)
        lion_target.equipment.append(
            equipment("白银狮子", "armor")
        )
        slash = make_card("杀", ident="slash")
        source.hand = [slash]

        lion_plan = choose_slash_plan(
            GameEngine([source, lion_target], []),
            source,
            [slash],
        )
        self.assertFalse(
            should_use_analeptic_for_slash(lion_plan)
        )

        mixed_plan = lion_plan.__class__(
            slash, (lion_target, other_target), "杀"
        )
        self.assertTrue(
            should_use_analeptic_for_slash(mixed_plan)
        )

    def test_wusheng_ai_does_not_remove_qinggang_then_attack_vine(self):
        source = make_player(0)
        target = make_player(1)
        source.general.skills = [
            GeneralSkillRef(
                skill_id="general.wusheng", name="武圣"
            )
        ]
        red_qinggang = equipment("青釭剑", "weapon")
        red_qinggang = red_qinggang.model_copy(
            update={"suit": "heart"}
        )
        source.equipment.append(red_qinggang)
        target.equipment.append(equipment("藤甲", "armor"))
        engine = GameEngine([source, target], [])
        option = engine.skills.play_conversion_options(
            source, "杀"
        )[0]

        decision = engine.skills.ai_choose_conversion(
            engine,
            source,
            "杀",
            SkillTiming.SLASH_CONVERSION,
            SkillAIContext(
                window="play",
                required_card_name="杀",
                legal_targets=(target,),
            ),
        )

        self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
