import unittest
from types import SimpleNamespace

from main import GameUI
from src.engine import GameEngine
from src.models import (
    Card, CardKind, DamageEvent, DamageNature, General, GeneralSkillRef, Player,
    Phase, PromptContext, PromptType, SkillKind, SkillTiming,
)
from src.skills import SKILL_DEFINITIONS
from src.skill_modules.base import SkillAIContext


def card(name, equipment_type=None, suit="club"):
    return Card(
        id=f"{name}-{suit}", name=name, suit=suit, rank="2",
        kind=CardKind.EQUIPMENT if equipment_type else CardKind.BASIC,
        equipment_type=equipment_type,
    )


def player(seat, equipment=None):
    result = Player(
        seat=seat,
        general=General(
            id=str(seat), name=f"角色{seat}", kingdom="魏", hp=4, skills=[]
        ),
        hp=4,
        max_hp=4,
    )
    if equipment:
        result.equipment.append(equipment)
    return result


class SkillSystemTest(unittest.TestCase):
    def test_wusheng_replaces_unsubmitted_zhangba_play_prompt(self):
        zhangba = card("丈八蛇矛", "weapon", suit="spade")
        owner = player(0, zhangba)
        target = player(1)
        owner.general.skills = [
            GeneralSkillRef(
                skill_id="general.wusheng", name="武圣"
            )
        ]
        red_card = card("闪", suit="heart")
        other_card = card("桃", suit="spade")
        owner.hand = [red_card, other_card]
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([owner, target], [])
        ui.engine.state.phase = Phase.PLAY
        ui.wd = False
        ui.dt = None
        ui.da = None
        ui.active_prompt = None
        ui.next_prompt_id = 1
        ui.resolution_stack = []
        ui.response_time_remaining = 0
        ui.ai_response_at = 0
        ui.idx = None
        ui.pending_target = None
        ui.pending_targets = []
        ui.pending_skill_action = None
        ui.skill_prompt_confirm_callback = None
        ui.skill_prompt_cancel_callback = None
        ui.skill_prompt_cards = []
        ui.skill_prompt_required_cards = 0
        ui.skill_prompt_selected = set()
        ui.hint = lambda *_args, **_kwargs: None
        ui.skill_button_rects = {
            (owner.seat, "general.wusheng"):
                SimpleNamespace(
                    collidepoint=lambda position:
                        position == (10, 10)
                )
        }
        cancelled = []

        ui._open_skill_prompt(
            owner, "weapon.zhangba", "丈八蛇矛",
            "请选择两张手牌",
            lambda _cards: None,
            lambda: cancelled.append(True),
            selectable_cards=owner.hand,
            required_cards=2,
            window="play",
        )
        ui.skill_prompt_selected.add(red_card.id)

        self.assertTrue(
            ui._equipment_skill_prompt_active(owner, zhangba)
        )
        self.assertTrue(
            ui._try_replace_play_skill_prompt(owner, (10, 10))
        )
        self.assertFalse(cancelled)
        self.assertIsNone(ui.active_prompt)
        self.assertFalse(ui.wd)
        self.assertIsNone(ui.dt)
        self.assertEqual(ui.skill_prompt_selected, set())
        self.assertEqual(
            ui.pending_skill_action["option"].skill.skill_id,
            "general.wusheng",
        )
        self.assertEqual(
            ui.pending_skill_action["cards"], []
        )
        self.assertFalse(
            ui._equipment_skill_prompt_active(owner, zhangba)
        )

    def test_jianxiong_is_registered_as_optional_after_damage_skill(self):
        owner = player(0)
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.jianxiong", name="奸雄")
        ]
        engine = GameEngine([owner], [])
        skill = SKILL_DEFINITIONS["general.jianxiong"]

        self.assertEqual(skill.kind, SkillKind.TRIGGERED)
        self.assertEqual(skill.timings, (SkillTiming.AFTER_DAMAGE,))
        self.assertFalse(skill.mandatory)
        self.assertEqual(
            skill.description,
            "当你受到伤害后，你可以获得造成此伤害的牌。",
        )
        self.assertTrue(engine.skills.has_skill(owner, "general.jianxiong"))

    def test_jianxiong_gains_actual_damage_card_from_processing(self):
        owner = player(0)
        source = player(1)
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.jianxiong", name="奸雄")
        ]
        damage_card = card("杀", suit="spade")
        engine = GameEngine([owner, source], [])
        engine.begin_processing_card(damage_card)
        event = DamageEvent(
            amount=1, source_player=source, source_card=damage_card,
            parent_slash_id=12,
        )

        actions = engine.triggered_skill_actions(
            owner, SkillTiming.AFTER_DAMAGE, event
        )
        result = engine.resolve_triggered_skill(actions[0])

        self.assertTrue(result.applied)
        self.assertIn(damage_card, owner.hand)
        self.assertNotIn(damage_card, engine.processing_area)
        self.assertNotIn(damage_card, engine.discard_pile)
        self.assertIs(result.move_events[0].card, damage_card)
        self.assertEqual(result.move_events[0].from_zone, "processing")
        self.assertEqual(result.move_events[0].to_zone, "hand")
        self.assertEqual(result.move_events[0].to_player_seat, owner.seat)
        self.assertEqual(result.move_events[0].source_event_id, 12)
        self.assertEqual(result.move_events[0].visibility, "public")

    def test_jianxiong_public_card_is_gained_face_up_by_ai(self):
        owner = player(0)
        owner.is_ai = True
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.jianxiong", name="奸雄")
        ]
        damage_card = card("杀", suit="spade")
        engine = GameEngine([owner], [])
        engine.begin_processing_card(damage_card)
        event = DamageEvent(amount=1, source_card=damage_card)
        action = engine.triggered_skill_actions(
            owner, SkillTiming.AFTER_DAMAGE, event
        )[0]
        result = engine.resolve_triggered_skill(action)
        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        ui.waiting_cards = [{
            "card": damage_card,
            "pos": (320, 240),
        }]
        captured = []
        ui._queue_hand_gain_animation = (
            lambda recipient, gained_card, source, **kwargs:
            captured.append((
                recipient, gained_card, source, kwargs["face_up"]
            ))
        )

        ui._animate_skill_move_events(
            list(result.move_events), lambda: None
        )

        self.assertEqual(
            captured,
            [(owner, damage_card, (320, 240), True)],
        )
        self.assertFalse(ui.waiting_cards)

    def test_jianxiong_gains_wusheng_physical_card_not_virtual_slash(self):
        source = player(0)
        owner = player(1)
        source.general.skills = [
            GeneralSkillRef(skill_id="general.wusheng", name="武圣")
        ]
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.jianxiong", name="奸雄")
        ]
        red_card = card("闪", suit="heart")
        source.hand.append(red_card)
        engine = GameEngine([source, owner], [])
        slash_event = engine.create_slash_event(
            source, [red_card], [owner], "杀"
        )
        engine.begin_processing_card(red_card)
        virtual_slash = red_card.model_copy(update={"name": "杀"})
        damage_event = DamageEvent(
            amount=1,
            source_player=source,
            source_card=virtual_slash,
            source_physical_cards=tuple(slash_event.physical_cards),
            parent_slash_id=slash_event.slash_id,
        )

        actions = engine.triggered_skill_actions(
            owner, SkillTiming.AFTER_DAMAGE, damage_event
        )
        result = engine.resolve_triggered_skill(actions[0])

        self.assertTrue(result.applied)
        self.assertIn(red_card, owner.hand)
        self.assertIs(result.move_events[0].card, red_card)
        self.assertIsNot(result.move_events[0].card, virtual_slash)
        self.assertNotIn(red_card, engine.discard_pile)

    def test_jianxiong_gains_all_physical_cards_of_multi_card_slash(self):
        source = player(0, card("丈八蛇矛", "weapon"))
        owner = player(1)
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.jianxiong", name="奸雄")
        ]
        materials = [
            card("桃", suit="heart"),
            card("闪", suit="diamond"),
        ]
        source.hand.extend(materials)
        engine = GameEngine([source, owner], [])
        slash_event = engine.create_slash_event(
            source, materials, [owner], "杀"
        )
        for material in materials:
            engine.begin_processing_card(material)
        damage_event = DamageEvent(
            amount=1,
            source_player=source,
            source_card=materials[0].model_copy(update={"name": "杀"}),
            source_physical_cards=tuple(materials),
        )

        action = engine.triggered_skill_actions(
            owner, SkillTiming.AFTER_DAMAGE, damage_event
        )[0]
        result = engine.resolve_triggered_skill(action)

        self.assertTrue(result.applied)
        self.assertEqual([move.card for move in result.move_events], materials)
        self.assertEqual(
            len({move.batch_id for move in result.move_events}), 1
        )
        self.assertTrue(all(
            move.batch_size == 2
            for move in result.move_events
        ))
        self.assertTrue(all(material in owner.hand for material in materials))
        self.assertFalse(engine.processing_area)

        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        ui.waiting_cards = [
            {"card": materials[0], "pos": (210, 240)},
            {"card": materials[1], "pos": (300, 240)},
        ]
        queued = []
        ui._queue_hand_gain_animation = (
            lambda recipient, gained_card, source, **kwargs:
            queued.append((
                recipient, gained_card, source, kwargs.get("start")
            ))
        )
        ui._animate_skill_move_events(
            list(result.move_events), lambda: None
        )

        self.assertEqual(
            [item[1] for item in queued], materials
        )
        self.assertEqual(
            [item[2] for item in queued],
            [(210, 240), (300, 240)],
        )
        self.assertEqual(len({item[3] for item in queued}), 1)

    def test_jianxiong_does_not_trigger_without_available_damage_card(self):
        owner = player(0)
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.jianxiong", name="奸雄")
        ]
        damage_card = card("决斗", suit="spade")
        engine = GameEngine([owner], [])

        self.assertEqual(
            engine.triggered_skill_actions(
                owner,
                SkillTiming.AFTER_DAMAGE,
                DamageEvent(amount=1, source_card=damage_card),
            ),
            [],
        )
        self.assertEqual(
            engine.triggered_skill_actions(
                owner, SkillTiming.AFTER_DAMAGE, DamageEvent(amount=1)
            ),
            [],
        )

    def test_generic_trigger_prompt_cancel_and_confirm_share_same_path(self):
        owner = player(0)
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.jianxiong", name="奸雄")
        ]
        damage_card = card("火攻", suit="heart")
        engine = GameEngine([owner], [])
        engine.begin_processing_card(damage_card)
        event = DamageEvent(amount=1, source_card=damage_card)
        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        opened = []
        completed = []
        ui._open_skill_prompt = (
            lambda *args, **kwargs: opened.append((args, kwargs))
        )

        ui._begin_triggered_skill_sequence(
            owner, SkillTiming.AFTER_DAMAGE, event,
            lambda: completed.append("cancelled"),
        )
        opened[0][0][5]()

        self.assertEqual(completed, ["cancelled"])
        self.assertIn(damage_card, engine.processing_area)
        self.assertNotIn(damage_card, owner.hand)

        messages = []
        sounds = []
        animations = []
        opened.clear()
        completed.clear()
        ui.msg = messages.append
        ui.play_skill_sound = (
            lambda controller, skill_id:
            sounds.append((controller, skill_id))
        )
        ui.waiting_cards = [
            {"card": damage_card, "pos": (50, 60)}
        ]
        ui._player_center = lambda _player: (0, 0)

        def animate(recipient, moved, source, **kwargs):
            animations.append((recipient, moved, source))
            kwargs["on_complete"]()

        ui._queue_hand_gain_animation = animate
        ui._begin_triggered_skill_sequence(
            owner, SkillTiming.AFTER_DAMAGE, event,
            lambda: completed.append("confirmed"),
        )
        opened[0][0][4]([])

        self.assertEqual(completed, ["confirmed"])
        self.assertEqual(sounds, [(owner, "general.jianxiong")])
        self.assertEqual(animations, [(owner, damage_card, (50, 60))])
        self.assertTrue(any("发动【奸雄】" in message for message in messages))

    def test_slash_finalizer_does_not_discard_card_gained_mid_resolution(self):
        owner = player(0)
        damage_card = card("杀", suit="spade")
        owner.hand.append(damage_card)
        engine = GameEngine([owner], [])
        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        ui.active_slash_event = SimpleNamespace(
            physical_cards=[damage_card]
        )

        ui._finalize_active_slash()

        self.assertIn(damage_card, owner.hand)
        self.assertNotIn(damage_card, engine.discard_pile)

    def test_slash_damage_forwards_active_event_physical_cards(self):
        source = player(0)
        target = player(1)
        material = card("闪", suit="heart")
        source.hand.append(material)
        engine = GameEngine([source, target], [])
        source.general.skills = [
            GeneralSkillRef(skill_id="general.wusheng", name="武圣")
        ]
        slash_event = engine.create_slash_event(
            source, [material], [target], "杀"
        )
        ui = GameUI.__new__(GameUI)
        ui.engine = engine
        ui.active_slash_event = slash_event
        captured = {}
        ui._apply_damage = (
            lambda *args, **kwargs: captured.update(kwargs)
        )

        ui._apply_slash_damage_now(
            target,
            source,
            material.model_copy(update={"name": "杀"}),
            1,
            DamageNature.NORMAL,
        )

        self.assertEqual(
            captured["source_physical_cards"], (material,)
        )

    def test_damage_trick_stays_in_processing_until_resolution_finishes(self):
        source = player(0)
        target = player(1)
        duel = Card(
            id="duel-1", name="决斗", suit="spade", rank="A",
            kind=CardKind.TRICK,
        )
        source.hand.append(duel)
        engine = GameEngine([source, target], [])

        self.assertTrue(engine.play_card(source, duel, target))
        self.assertIn(duel, engine.processing_area)
        self.assertNotIn(duel, engine.discard_pile)

        self.assertTrue(engine.finish_processing_card(duel))
        self.assertNotIn(duel, engine.processing_area)
        self.assertIn(duel, engine.discard_pile)

    def test_lightning_damage_card_enters_processing_before_after_damage(self):
        owner = player(0)
        lightning = Card(
            id="lightning-1", name="闪电", suit="spade", rank="A",
            kind=CardKind.TRICK,
        )
        judged = Card(
            id="judged-1", name="杀", suit="spade", rank="5",
            kind=CardKind.BASIC,
        )
        owner.judgment_area.append(lightning)
        engine = GameEngine([owner], [judged])
        engine.draw_pile = [judged]

        result = engine.resolve_next_judgment(owner)

        self.assertEqual(result["effect"], "lightning_damage")
        self.assertIs(
            result["judgment"].judging_player, owner
        )
        self.assertIn(lightning, engine.processing_area)
        self.assertNotIn(lightning, engine.discard_pile)

    def test_wusheng_is_optional_general_skill_and_uses_owned_red_card(self):
        owner = player(0)
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.wusheng", name="武圣")
        ]
        red_hand = card("闪", suit="heart")
        red_armor = card("八卦阵", "armor", suit="diamond")
        black_hand = card("桃", suit="spade")
        owner.hand = [red_hand, black_hand]
        owner.equipment = [red_armor]
        engine = GameEngine([owner], [])
        skill = SKILL_DEFINITIONS["general.wusheng"]
        option = engine.skills.play_conversion_options(owner, "杀")[0]

        self.assertEqual(skill.kind, SkillKind.ACTIVE)
        self.assertFalse(skill.mandatory)
        self.assertEqual(
            engine.skills.conversion_candidates(owner, option),
            [red_hand, red_armor],
        )
        self.assertTrue(
            engine.skills.validate_conversion(
                owner, option, [red_hand]
            )
        )
        self.assertTrue(
            engine.skills.validate_conversion(
                owner, option, [red_armor]
            )
        )
        self.assertFalse(
            engine.skills.validate_conversion(
                owner, option, [black_hand]
            )
        )
        effective = engine.skills.build_conversion_card(
            option, [red_hand]
        )
        self.assertEqual(effective.name, "杀")
        self.assertEqual(effective.kind, CardKind.BASIC)
        self.assertEqual(effective.suit, red_hand.suit)
        self.assertEqual(effective.rank, red_hand.rank)
        self.assertEqual(effective.color, "red")
        # 转化动作在统一响应窗口内由玩家操作，不提前建立“是否发动”询问。
        self.assertIsNone(
            engine.get_optional_response_skill(owner, "杀")
        )

    def test_wusheng_submission_moves_before_presentation_and_emits_events(self):
        owner = player(0)
        target = player(1)
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.wusheng", name="武圣")
        ]
        material = card("闪", suit="heart")
        owner.hand = [material]
        engine = GameEngine([owner, target], [])
        engine.state.phase = Phase.PLAY
        option = engine.skills.play_conversion_options(owner, "杀")[0]

        slash_event = engine.submit_play_conversion(
            owner, option, [material], (target,)
        )

        self.assertNotIn(material, owner.hand)
        self.assertIn(material, engine.processing_area)
        self.assertEqual(slash_event.physical_cards, [material])
        self.assertEqual(slash_event.effective_card.name, "杀")
        events = engine.drain_rule_events()
        self.assertEqual(
            [event.event_type for event in events],
            [
                "card_moved", "card_used",
                "slash_created", "skill_resolved",
            ],
        )
        self.assertEqual(events[0].data["to_zone"], "processing")
        self.assertEqual(
            events[-1].data["skill_id"], "general.wusheng"
        )

    def test_jianxiong_consumes_wusheng_physical_card_after_rule_events(self):
        source = player(0)
        owner = player(1)
        source.general.skills = [
            GeneralSkillRef(skill_id="general.wusheng", name="武圣")
        ]
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.jianxiong", name="奸雄")
        ]
        material = card("闪", suit="heart")
        source.hand = [material]
        engine = GameEngine([source, owner], [])
        engine.state.phase = Phase.PLAY
        option = engine.skills.play_conversion_options(source, "杀")[0]
        slash_event = engine.submit_play_conversion(
            source, option, [material], (owner,)
        )
        damage = DamageEvent(
            amount=1,
            source_player=source,
            source_card=slash_event.effective_card,
            source_physical_cards=tuple(slash_event.physical_cards),
            parent_slash_id=slash_event.slash_id,
        )

        action = engine.triggered_skill_actions(
            owner, SkillTiming.AFTER_DAMAGE, damage
        )[0]
        result = engine.resolve_triggered_skill(action)

        self.assertTrue(result.applied)
        self.assertIn(material, owner.hand)
        self.assertNotIn(material, engine.processing_area)
        self.assertIs(result.move_events[0].card, material)
        self.assertEqual(
            [event.event_type for event in engine.rule_event_history],
            [
                "card_moved", "card_used",
                "slash_created", "skill_resolved",
                "card_moved", "skill_resolved",
            ],
        )

    def test_skill_ai_policy_chooses_wusheng_material_and_target(self):
        owner = player(0)
        weak_target = player(1)
        strong_target = player(2)
        owner.is_ai = True
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.wusheng", name="武圣")
        ]
        weak_target.hp = 1
        strong_target.hp = 3
        peach = card("桃", suit="heart")
        jink = card("闪", suit="diamond")
        owner.hand = [peach, jink]
        engine = GameEngine([owner, weak_target, strong_target], [])

        decision = engine.skills.ai_choose_conversion(
            engine,
            owner,
            "杀",
            SkillTiming.SLASH_CONVERSION,
            SkillAIContext(
                window="play",
                required_card_name="杀",
                legal_targets=(strong_target, weak_target),
            ),
        )

        self.assertIsNotNone(decision)
        self.assertEqual(decision.cards, (jink,))
        self.assertIs(decision.target, weak_target)

    def test_skill_ai_rechecks_target_after_wusheng_removes_weapon(self):
        owner = player(0)
        near_player = player(1)
        far_target = player(2)
        other_player = player(3)
        owner.is_ai = True
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.wusheng", name="武圣")
        ]
        red_weapon = card("麒麟弓", "weapon", suit="heart")
        owner.equipment = [red_weapon]
        engine = GameEngine(
            [owner, near_player, far_target, other_player], []
        )
        self.assertTrue(engine.in_attack_range(owner, far_target))

        decision = engine.skills.ai_choose_conversion(
            engine,
            owner,
            "杀",
            SkillTiming.SLASH_CONVERSION,
            SkillAIContext(
                window="play",
                required_card_name="杀",
                legal_targets=(far_target,),
            ),
        )

        self.assertIsNone(decision)

    def test_skill_ai_policy_activates_jianxiong_through_handler(self):
        owner = player(0)
        owner.is_ai = True
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.jianxiong", name="奸雄")
        ]
        damage_card = card("决斗", suit="spade")
        engine = GameEngine([owner], [])
        engine.begin_processing_card(damage_card)
        action = engine.triggered_skill_actions(
            owner,
            SkillTiming.AFTER_DAMAGE,
            DamageEvent(amount=1, source_card=damage_card),
        )[0]

        self.assertTrue(
            engine.skills.ai_should_activate_triggered(engine, action)
        )

    def test_ai_optional_skill_prompt_respects_module_decline(self):
        owner = player(0)
        owner.is_ai = True
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([owner], [])
        ui.judgment_display_in_progress = False
        ui.ai_response_at = 1
        ui.dt = owner
        ui.active_prompt = PromptContext(
            prompt_id=1,
            prompt_type=PromptType.ACTIVATE_SKILL,
            player_seat=owner.seat,
            message="是否发动？",
        )
        ui.prompt_handlers = {
            1: {"ai_confirm": lambda: False}
        }
        declined = []
        ui._decline_skill_prompt = lambda: declined.append(True)
        ui._xd = lambda: None

        ui._ad()

        self.assertEqual(declined, [True])

    def test_ai_response_dispatches_wusheng_through_skill_manager(self):
        owner = player(0)
        actor = player(1)
        owner.is_ai = True
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.wusheng", name="武圣")
        ]
        material = card("闪", suit="heart")
        owner.hand.append(material)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([owner, actor], [])
        ui.judgment_display_in_progress = False
        ui.ai_response_at = 1
        ui.dt = owner
        ui.da = actor
        ui.active_prompt = None
        ui.dying_target = None
        ui.response_card_name = "杀"
        ui.response_source_name = "南蛮入侵"
        ui.response_source_card = card("南蛮入侵")
        ui.nullification_context = None
        ui._allowed_response_names = lambda _player: ("杀",)
        selected = []
        ui._use_response_conversion = (
            lambda player_, actor_, source_name, source_card, option, cards:
            selected.append((option.skill.skill_id, tuple(cards)))
        )
        ui._xd = lambda: None

        ui._ad()

        self.assertEqual(
            selected, [("general.wusheng", (material,))]
        )

    def test_wusheng_response_use_keeps_physical_card_in_processing(self):
        source = player(0)
        target = player(1)
        source.general.skills = [
            GeneralSkillRef(skill_id="general.wusheng", name="武圣")
        ]
        material = card("闪", suit="heart")
        source.hand.append(material)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([source, target], [])
        option = ui.engine.skills.response_conversion_options(
            source, "杀"
        )[0]
        ui.response_action = "使用"
        ui.response_success_callback = None
        ui.wd = True
        ui.dt = source
        ui.da = target
        ui._owned_card_center = lambda *_args: (10, 20)
        ui.msg = lambda *_args: None
        ui.play_skill_sound = lambda *_args: None
        ui.play_card_sound = lambda *_args: None
        ui._xd = lambda: None
        callback_state = []

        def complete(player_, actor_, effective_card, physical_cards):
            callback_state.append((
                player_, actor_, effective_card.name, physical_cards,
                material in ui.engine.processing_area,
            ))

        ui.response_success_callback = complete
        ui._queue_discard_display = (
            lambda _cards, _sources, on_complete=None, **_kwargs:
            on_complete() if on_complete else None
        )

        ui._use_response_conversion(
            source, target, "青龙偃月刀", card("杀"),
            option, [material],
        )

        self.assertNotIn(material, source.hand)
        self.assertIn(material, ui.engine.processing_area)
        self.assertNotIn(material, ui.engine.discard_pile)
        self.assertEqual(
            callback_state,
            [(source, target, "杀", (material,), True)],
        )

    def test_wusheng_response_keeps_every_duel_round_connected(self):
        initiator = player(0)
        target = player(1)
        for owner in (initiator, target):
            owner.general.skills = [
                GeneralSkillRef(
                    skill_id="general.wusheng", name="武圣"
                )
            ]
        initiator_material = card("闪", suit="heart")
        target_material = card("桃", suit="diamond")
        initiator.hand.append(initiator_material)
        target.hand.append(target_material)
        duel = Card(
            id="duel-wusheng-chain",
            name="决斗",
            suit="spade",
            rank="A",
            kind=CardKind.TRICK,
        )
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([initiator, target], [])
        ui.duel_active = False
        ui.idx = None
        ui.pending_target = None
        ui.active_slash_event = None
        ui.active_prompt = None
        ui.dying_target = None
        ui.next_prompt_id = 1
        ui.msg = lambda *_args: None
        ui.hint = lambda *_args: None
        ui.play_skill_sound = lambda *_args: None
        ui.play_card_sound = lambda *_args: None
        ui._owned_card_center = lambda *_args: (10, 20)
        ui._queue_discard_display = (
            lambda _cards, _sources, on_complete=None, **_kwargs:
            on_complete() if on_complete else None
        )
        finished = []
        ui._xd = lambda: finished.append(True)

        ui._begin_duel(initiator, target, duel)
        target_option = ui.engine.skills.response_conversion_options(
            target, "杀"
        )[0]
        ui._use_response_conversion(
            target, initiator, "决斗", duel,
            target_option, [target_material],
        )

        self.assertIs(ui.dt, initiator)
        self.assertIs(ui.da, target)
        self.assertTrue(ui.duel_active)
        self.assertTrue(callable(ui.response_success_callback))

        initiator_option = (
            ui.engine.skills.response_conversion_options(
                initiator, "杀"
            )[0]
        )
        ui._use_response_conversion(
            initiator, target, "决斗", duel,
            initiator_option, [initiator_material],
        )

        self.assertIs(ui.dt, target)
        self.assertIs(ui.da, initiator)
        self.assertTrue(ui.duel_active)
        self.assertTrue(callable(ui.response_success_callback))
        self.assertFalse(finished)

    def test_forced_converted_slash_preserves_physical_context(self):
        source = player(0)
        target = player(1)
        source.general.skills = [
            GeneralSkillRef(skill_id="general.wusheng", name="武圣")
        ]
        material = card("闪", suit="heart")
        source.hand.append(material)
        engine = GameEngine([source, target], [])
        self.assertTrue(engine.stage_owned_cards_for_use(source, [material]))

        event = engine.create_forced_slash_event(
            source,
            [material],
            target,
            "杀",
            cards_already_processing=True,
            conversion_already_validated=True,
        )

        self.assertEqual(event.physical_cards, [material])
        self.assertIn(material, engine.processing_area)
        damage_event = DamageEvent(
            amount=event.damage,
            source_player=source,
            source_card=material.model_copy(update={"name": "杀"}),
            source_physical_cards=tuple(event.physical_cards),
            parent_slash_id=event.slash_id,
        )
        self.assertEqual(
            damage_event.source_physical_cards, (material,)
        )

    def test_wusheng_can_use_red_equipment_as_slash(self):
        owner = player(0)
        target = player(1)
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.wusheng", name="武圣")
        ]
        red_weapon = card("麒麟弓", "weapon", suit="heart")
        owner.equipment = [red_weapon]
        engine = GameEngine([owner, target], [])

        event = engine.create_slash_event(
            owner, [red_weapon], [target], "杀"
        )

        self.assertEqual(event.effective_name, "杀")
        self.assertEqual(event.physical_cards, [red_weapon])
        self.assertNotIn(red_weapon, owner.equipment)

    def test_wusheng_cannot_reuse_converted_crossbow_effect(self):
        owner = player(0)
        target = player(1)
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.wusheng", name="武圣")
        ]
        crossbow = card("诸葛连弩", "weapon", suit="diamond")
        owner.equipment = [crossbow]
        owner.slash_used = True
        engine = GameEngine([owner, target], [])

        self.assertTrue(engine.can_use_slash(owner))
        self.assertFalse(engine.can_use_slash(owner, (crossbow,)))
        with self.assertRaisesRegex(ValueError, "次数已达上限"):
            engine.create_slash_event(
                owner, [crossbow], [target], "杀"
            )

    def test_wusheng_sound_plays_only_after_successful_submission(self):
        owner = player(0)
        target = player(1)
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.wusheng", name="武圣")
        ]
        red_card = card("闪", suit="heart")
        owner.hand.append(red_card)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([owner, target], [])
        option = ui.engine.skills.play_conversion_options(owner, "杀")[0]
        ui.idx = 0
        ui.pending_skill_action = {
            "option": option, "cards": [red_card]
        }
        ui.pending_target = target
        ui.active_slash_event = None
        ui._owned_card_center = lambda *_args: (10, 20)
        ui._reset_play_timer = lambda: None
        ui._queue_discard_display = lambda *_args, **_kwargs: None
        ui._play_zhuge_for_extra_slash = lambda *_args: None
        ui.msg = lambda *_args: None
        skill_sounds = []
        card_sounds = []
        ui.play_skill_sound = (
            lambda source, skill_id:
            skill_sounds.append((source, skill_id))
        )
        ui.play_card_sound = (
            lambda source, card_name, physical=None:
            card_sounds.append((source, card_name, physical))
        )

        ui._play_conversion_slash(owner, option, [red_card], target)

        self.assertEqual(
            skill_sounds, [(owner, "general.wusheng")]
        )
        self.assertEqual(card_sounds[0][0:2], (owner, "杀"))

        invalid = card("桃", suit="spade")
        owner.hand.append(invalid)
        ui.pending_skill_action = {
            "option": option, "cards": [invalid]
        }
        ui.hint = lambda *_args: None
        ui._play_conversion_slash(owner, option, [invalid], target)

        self.assertEqual(
            skill_sounds, [(owner, "general.wusheng")]
        )

    def test_successful_skill_sound_creates_notice_from_definition(self):
        owner = player(0)
        owner.general.skills = [
            GeneralSkillRef(
                skill_id="general.wusheng", name="武圣"
            )
        ]
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([owner], [])
        ui.sound = None
        ui.skill_notice = None

        ui.play_skill_sound(owner, "general.wusheng")

        self.assertEqual(
            ui.skill_notice["text"],
            "【角色0】使用了技能【武圣】",
        )

    def test_equipment_effect_sound_does_not_create_general_skill_notice(self):
        owner = player(0, card("麒麟弓", "weapon"))
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([owner], [])
        ui.sound = None
        ui.skill_notice = None

        ui.play_equipment_sound("麒麟弓", owner, visual=False)

        self.assertIsNone(ui.skill_notice)

    def test_stale_prompt_id_cannot_submit_current_prompt(self):
        ui = GameUI.__new__(GameUI)
        owner = player(0)
        submitted = []
        ui.dt = owner
        ui.active_prompt = PromptContext(
            prompt_id=7,
            prompt_type=PromptType.ACTIVATE_SKILL,
            player_seat=owner.seat,
            message="是否发动？",
        )
        ui.prompt_handlers = {
            7: {"confirm": lambda cards: submitted.append(cards)}
        }

        self.assertFalse(ui._submit_skill_prompt(6, True))
        self.assertFalse(submitted)
        self.assertEqual(ui.active_prompt.prompt_id, 7)

    def test_general_uses_stable_skill_ids(self):
        owner = player(0)
        owner.general.skills = [
            GeneralSkillRef(skill_id="general.example", name="示例技能")
        ]
        engine = GameEngine([owner], [])

        self.assertEqual(
            engine.skills.general_skill_ids(owner), ("general.example",)
        )

    def test_optional_and_locked_skills_are_distinguished(self):
        bagua_owner = player(0, card("八卦阵", "armor"))
        renwang_owner = player(1, card("仁王盾", "armor"))
        engine = GameEngine([bagua_owner, renwang_owner], [])

        optional = engine.get_optional_response_skill(bagua_owner, "闪")
        locked = engine.skills.skills_at(
            renwang_owner, SkillTiming.EFFECT_VALIDITY
        )[0]

        self.assertEqual(optional.skill_id, "armor.bagua")
        self.assertEqual(optional.kind, SkillKind.TRIGGERED)
        self.assertFalse(optional.mandatory)
        self.assertEqual(locked.kind, SkillKind.LOCKED)
        self.assertTrue(locked.mandatory)
        self.assertIsNone(
            engine.get_optional_response_skill(renwang_owner, "闪")
        )

    def test_equipment_skill_disappears_after_leaving_equipment_area(self):
        armor = card("八卦阵", "armor")
        owner = player(0, armor)
        engine = GameEngine([owner], [])
        self.assertIsNotNone(engine.get_optional_response_skill(owner, "闪"))

        engine.remove_equipment(owner, armor)

        self.assertIsNone(engine.get_optional_response_skill(owner, "闪"))

    def test_weapon_attack_range_uses_state_skill(self):
        owner = player(0, card("麒麟弓", "weapon"))
        engine = GameEngine([owner], [])

        self.assertEqual(engine.attack_range(owner), 5)
        skills = engine.skills.skills_at(owner, SkillTiming.ATTACK_RANGE)
        self.assertEqual(skills[0].source_name, "麒麟弓")

    def test_damage_reports_each_applied_skill(self):
        owner = player(0, card("藤甲", "armor"))
        engine = GameEngine([owner], [])

        result, applications = engine.modify_damage_with_skills(
            owner, DamageEvent(amount=1, nature=DamageNature.FIRE)
        )

        self.assertEqual(result.amount, 2)
        self.assertEqual(
            [application.skill.skill_id for application in applications],
            ["armor.vine"],
        )


if __name__ == "__main__":
    unittest.main()
