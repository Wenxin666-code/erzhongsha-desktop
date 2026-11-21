import unittest

from main import (
    ARROW_ANIM_MS, ARROW_HOLD_MS,
    BORROWED_SWORD_ARROW_GAP_MS, GameUI,
)
from src.engine import GameEngine
from src.models import (
    Card, CardKind, General, JudgmentStep, Phase, Player,
)


def make_card(identifier, suit="spade", rank="2"):
    return Card(
        id=identifier,
        name=identifier,
        suit=suit,
        rank=rank,
        kind=CardKind.BASIC,
    )


def make_player(seat=0):
    general = General(
        id=f"g{seat}",
        name=f"角色{seat}",
        kingdom="魏",
        hp=4,
        skills=[],
    )
    return Player(
        seat=seat,
        general=general,
        hp=4,
        max_hp=4,
    )


class FlowAndJudgmentTest(unittest.TestCase):
    def test_resolution_frames_preserve_parent_relationship(self):
        ui = GameUI.__new__(GameUI)
        ui.resolution_stack = []
        ui.next_resolution_event_id = 1

        parent = ui._push_resolution_frame("card_use", {"name": "决斗"})
        child = ui._push_resolution_frame("dying", {"hp": 0})

        self.assertEqual(child.parent_event_id, parent.event_id)
        self.assertEqual(
            ui._pop_resolution_frame("dying").state, {"hp": 0}
        )
        self.assertEqual(
            ui._pop_resolution_frame("card_use").state, {"name": "决斗"}
        )

    def test_discard_move_records_zone_and_reason(self):
        owner = make_player(0)
        card = Card(
            id="discarded", name="闪", suit="heart", rank="2",
            kind=CardKind.BASIC,
        )
        owner.hand.append(card)
        engine = GameEngine([owner], [])

        event = engine.discard_from_hand(owner, card, "技能弃置")

        self.assertEqual(event.from_zone, "hand")
        self.assertEqual(event.to_zone, "discard_pile")
        self.assertEqual(event.reason, "技能弃置")
        self.assertEqual(engine.card_move_history, [event])

    def test_peach_garden_targets_only_wounded_players(self):
        actor = make_player(0)
        healthy = make_player(1)
        wounded = make_player(2)
        wounded.hp = 2
        engine = GameEngine([actor, healthy, wounded], [])

        self.assertEqual(
            engine.get_peach_garden_targets(actor), [wounded]
        )

    def test_target_availability_does_not_disable_card_selection(self):
        source = make_player(0)
        others = [make_player(index) for index in range(1, 4)]
        for target in others:
            target.equipment.append(
                Card(
                    id=f"mount-{target.seat}",
                    name="防御马",
                    suit="heart",
                    rank="K",
                    kind=CardKind.EQUIPMENT,
                    equipment_type="defensive_mount",
                )
            )
        slash = make_card("杀")
        supply = Card(
            id="supply",
            name="兵粮寸断",
            suit="spade",
            rank="10",
            kind=CardKind.TRICK,
        )
        source.hand.extend([slash, supply])
        engine = GameEngine([source, *others], [])

        self.assertTrue(engine.can_select_play_card(source, slash))
        self.assertTrue(engine.can_select_play_card(source, supply))
        self.assertEqual(engine.get_legal_play_targets(source, slash), [])
        self.assertEqual(engine.get_legal_play_targets(source, supply), [])
        self.assertFalse(engine.can_submit_play_card(source, slash))
        self.assertFalse(engine.can_submit_play_card(source, supply))

    def test_same_seat_snapshot_can_never_be_slash_target(self):
        source = make_player(0)
        enemy = make_player(1)
        slash = make_card("杀")
        source.hand = [slash]
        engine = GameEngine([source, enemy], [])
        engine.state.phase = Phase.PLAY
        snapshot = source.model_copy(update={"is_ai": True})

        self.assertTrue(engine.same_player(source, snapshot))
        self.assertFalse(
            engine.in_attack_range(source, snapshot)
        )
        self.assertFalse(
            engine.is_legal_play_target(
                source, slash, snapshot
            )
        )
        self.assertFalse(
            engine.can_submit_play_card(
                source, slash, (snapshot,)
            )
        )
        with self.assertRaises(ValueError):
            engine.create_slash_event(
                source, [slash], [snapshot]
            )

    def test_card_and_target_legality_are_independent_queries(self):
        source = make_player(0)
        near = make_player(1)
        far = make_player(2)
        blocker = make_player(3)
        supply = Card(
            id="supply-target-test",
            name="兵粮寸断",
            suit="club",
            rank="4",
            kind=CardKind.TRICK,
        )
        source.hand.append(supply)
        engine = GameEngine([source, near, far, blocker], [])

        self.assertTrue(engine.can_select_play_card(source, supply))
        self.assertTrue(engine.is_legal_play_target(source, supply, near))
        self.assertFalse(engine.is_legal_play_target(source, supply, far))
        self.assertTrue(
            engine.can_submit_play_card(source, supply, (near,))
        )
        self.assertFalse(
            engine.can_submit_play_card(source, supply, (far,))
        )
        near.judgment_area.append(
            supply.model_copy(update={"id": "existing-supply"})
        )
        self.assertFalse(engine.is_legal_play_target(source, supply, near))

    def test_discard_visual_is_tagged_by_card_move_reason(self):
        card = make_card("弃牌")
        ui = GameUI.__new__(GameUI)
        ui.animations = []
        ui.waiting_cards = []
        ui._wait_slot_center = lambda _index: (100, 100)

        ui._queue_discard_display([card], [(10, 20)])

        self.assertEqual(ui.animations[0]["visual_reason"], "discard")

    def test_public_reveal_keeps_rule_card_in_hand_and_uses_visual_copy(self):
        owner = make_player(0)
        card = make_card("展示牌", suit="heart")
        owner.hand.append(card)
        engine = GameEngine([owner], [])

        event = engine.reveal_card(
            owner, card, "hand", "测试公开展示"
        )

        self.assertIsNotNone(event)
        self.assertIn(card, owner.hand)
        self.assertEqual(engine.card_move_history, [])
        self.assertEqual(engine.card_reveal_history, [event])

        ui = GameUI.__new__(GameUI)
        ui.animations = []
        ui.waiting_cards = []
        ui._wait_slot_center = lambda _index: (100, 100)
        display_id = ui._queue_public_reveal(event, (10, 20))
        animation = ui.animations[0]

        self.assertIsNot(animation["card"], card)
        self.assertEqual(animation["card"].id, card.id)
        self.assertEqual(animation["visual_reason"], "public_reveal")
        self.assertEqual(
            animation["waiting_metadata"]["source_card_id"], card.id
        )
        self.assertEqual(
            animation["waiting_metadata"]["display_id"], display_id
        )

    def test_clearing_public_reveal_removes_only_visual_copy(self):
        card = make_card("公开副本")
        other = make_card("其他等待牌")
        ui = GameUI.__new__(GameUI)
        ui.animations = []
        ui.waiting_cards = [
            {
                "card": card.model_copy(deep=True),
                "pos": (100, 100),
                "display_id": "reveal:1",
                "is_visual_copy": True,
            },
            {"card": other, "pos": (200, 100)},
        ]

        ui._clear_public_reveal("reveal:1")

        self.assertEqual(
            [item["card"] for item in ui.waiting_cards], [other]
        )
        self.assertEqual(ui.animations[0]["type"], "fade")
        self.assertEqual(
            ui.animations[0]["visual_reason"], "public_reveal_end"
        )

    def test_helping_another_dying_player_plays_peach_visual_and_card_animation(self):
        helper = make_player(0)
        target = make_player(1)
        target.hp = 0
        peach = make_card("桃", suit="heart")
        helper.hand.append(peach)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([helper, target], [])
        ui.dying_target = target
        ui.dying_queue = []
        played = []
        animations = []
        continued = []
        ui._hand_card_center = lambda *_args: (10, 20)
        ui._arrow_target_center = lambda *_args: (30, 40)
        ui._play_arrow_source = lambda *_args: (50, 60)
        ui.play_card_sound = (
            lambda player, card_name, card=None:
            played.append((player, card_name, card))
        )
        ui._queue_card_animation = (
            lambda card, source, target_pos=None, **kwargs:
            animations.append((card, source, target_pos, kwargs))
        )
        ui._continue_dying_queue = lambda: continued.append(True)
        ui.msg = lambda *_args: None

        ui._use_peach_for_dying(helper, peach)

        self.assertEqual(played, [(helper, "桃", peach)])
        self.assertEqual(animations[0][:3], (peach, (10, 20), (30, 40)))
        self.assertTrue(animations[0][3]["blocking"])
        animations[0][3]["on_complete"]()
        self.assertEqual(continued, [True])
        self.assertEqual(target.hp, 1)
        self.assertIn(peach, ui.engine.discard_pile)

    def test_borrowed_sword_animation_has_two_target_segments(self):
        actor = make_player(0)
        wielder = make_player(1)
        victim = make_player(2)
        card = Card(
            id="borrowed-sword",
            name="借刀杀人",
            suit="club",
            rank="Q",
            kind=CardKind.TRICK,
        )
        ui = GameUI.__new__(GameUI)
        ui.animations = []
        ui.waiting_cards = []
        ui._wait_slot_center = lambda _index: (500, 400)
        ui._play_arrow_source = lambda _player: (100, 100)
        centers = {
            wielder.seat: (200, 200),
            victim.seat: (300, 300),
        }
        ui._player_center = lambda player: centers[player.seat]
        ui._arrow_target_center = lambda player: centers[player.seat]

        ui._queue_borrowed_sword_animation(
            card, (120, 120), actor, wielder, victim
        )

        animation = ui.animations[-1]
        self.assertEqual(animation["type"], "borrowed_sword")
        self.assertEqual(
            animation["segments"],
            (((100, 100), (200, 200)), ((200, 200), (300, 300))),
        )
        self.assertEqual(
            animation["segment_gap"],
            BORROWED_SWORD_ARROW_GAP_MS,
        )
        self.assertEqual(
            animation["duration"],
            ARROW_ANIM_MS * 2
            + BORROWED_SWORD_ARROW_GAP_MS
            + ARROW_HOLD_MS,
        )

    def test_borrowed_sword_waits_for_final_confirmation(self):
        actor = make_player(0)
        wielder = make_player(1)
        victim = make_player(2)
        card = Card(
            id="borrowed-sword",
            name="借刀杀人",
            suit="club",
            rank="Q",
            kind=CardKind.TRICK,
        )
        weapon = Card(
            id="weapon",
            name="青龙偃月刀",
            suit="spade",
            rank="5",
            kind=CardKind.EQUIPMENT,
            equipment_type="weapon",
        )
        actor.hand.append(card)
        wielder.equipment.append(weapon)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([actor, wielder, victim], [])
        ui.idx = 0
        ui.pending_target = None
        ui.pending_targets = []
        ui.pending_skill_action = None
        ui.borrowed_sword_choice = None
        ui.borrowed_sword_resolution = None
        ui.discard_selected = set()
        ui._hand_card_center = lambda *_args: (120, 120)
        ui.hint = lambda *_args, **_kwargs: None
        ui.clear_hint = lambda: None

        self.assertTrue(
            ui._begin_borrowed_sword_target_choice(
                actor, card, wielder
            )
        )
        self.assertIn(card, actor.hand)
        self.assertNotIn(card, ui.engine.discard_pile)
        self.assertFalse(
            ui.engine.can_submit_play_card(
                actor, card, (wielder,)
            )
        )

        self.assertTrue(
            ui._select_borrowed_sword_victim(victim)
        )
        self.assertTrue(ui._can_confirm_borrowed_sword())
        self.assertIn(card, actor.hand)
        self.assertNotIn(card, ui.engine.discard_pile)

        queued = []
        played_sounds = []
        ui._reset_play_timer = lambda: None
        ui.play_card_sound = (
            lambda player, name, played_card=None:
            played_sounds.append((player, name, played_card))
        )
        ui._queue_borrowed_sword_animation = (
            lambda *args, **kwargs:
            queued.append((args, kwargs))
        )
        ui.msg = lambda *_args: None

        ui._resolve_borrowed_sword_target()

        self.assertNotIn(card, actor.hand)
        self.assertIn(card, ui.engine.discard_pile)
        self.assertEqual(
            played_sounds, [(actor, "借刀杀人", card)]
        )
        self.assertEqual(len(queued), 1)
        self.assertIs(
            ui.borrowed_sword_resolution["victim"], victim
        )

    def test_iron_chain_animation_plays_on_each_resolved_target(self):
        source = make_player(0)
        target = make_player(1)
        iron_chain = Card(
            id="iron-chain",
            name="铁索连环",
            suit="club",
            rank="K",
            kind=CardKind.TRICK,
        )
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([source, target], [])
        effects = []
        continued = []
        ui._play_visual_effect = (
            lambda effect, player: effects.append((effect, player))
        )
        ui.msg = lambda *_args: None
        ui._continue_iron_chain_targets = (
            lambda actor, card, targets:
            continued.append((actor, card, targets))
        )

        ui._resolve_iron_chain_target(source, iron_chain, target, [])

        self.assertTrue(target.chained)
        self.assertEqual(effects, [("chain", target)])
        self.assertEqual(continued, [(source, iron_chain, [])])

    def test_ai_savage_assault_slash_finishes_parent_response(self):
        source = make_player(0)
        target = make_player(1)
        target.is_ai = True
        slash = Card(
            id="ai-slash-response",
            name="杀",
            suit="spade",
            rank="7",
            kind=CardKind.BASIC,
        )
        savage_assault = Card(
            id="ai-savage-assault",
            name="南蛮入侵",
            suit="spade",
            rank="7",
            kind=CardKind.TRICK,
        )
        target.hand.append(slash)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([source, target], [])
        ui.dt = target
        ui.da = source
        ui.dying_target = None
        ui.active_prompt = None
        ui.nullification_context = None
        ui.borrowed_sword_resolution = None
        ui.weapon_followup_context = None
        ui.response_card_name = "杀"
        ui.response_source_name = "南蛮入侵"
        ui.response_source_card = savage_assault
        ui.duel_active = False
        ui.judgment_display_in_progress = False
        ui.ai_response_at = 1
        ui.response_finished = False
        ui._hand_card_center = lambda *_args: (0, 0)
        ui._queue_card_animation = (
            lambda _card, _source, *args, **kwargs:
            kwargs["on_complete"]()
        )
        ui._xd = lambda: setattr(ui, "response_finished", True)
        ui.msg = lambda *_args: None
        ui.play_card_sound = lambda *_args: None

        ui._ad()

        self.assertTrue(ui.response_finished)
        self.assertNotIn(slash, target.hand)
        self.assertIn(slash, ui.engine.discard_pile)

    def test_savage_assault_slash_does_not_enter_stale_duel(self):
        source = make_player(0)
        target = make_player(1)
        slash = Card(
            id="slash-response",
            name="杀",
            suit="spade",
            rank="7",
            kind=CardKind.BASIC,
        )
        savage_assault = Card(
            id="savage-assault",
            name="南蛮入侵",
            suit="spade",
            rank="7",
            kind=CardKind.TRICK,
        )
        target.hand.append(slash)
        ui = GameUI.__new__(GameUI)
        ui.engine = GameEngine([source, target], [])
        ui.dt = target
        ui.da = source
        ui.idx = 0
        ui.dying_target = None
        ui.borrowed_sword_resolution = None
        ui.nullification_context = None
        ui.response_card_name = "杀"
        ui.response_source_name = "南蛮入侵"
        ui.response_source_card = savage_assault
        # 模拟此前一次决斗残留的全局状态；响应仍必须服从当前父事件。
        ui.duel_active = True
        ui.response_finished = False
        ui.duel_continued = False
        ui._hand_card_center = lambda *_args: (0, 0)
        ui._queue_card_animation = (
            lambda _card, _source, *args, **kwargs:
            kwargs["on_complete"]()
        )
        ui._xd = lambda: setattr(ui, "response_finished", True)
        ui._continue_duel = (
            lambda *_args: setattr(ui, "duel_continued", True)
        )
        ui.msg = lambda *_args: None
        ui.play_card_sound = lambda *_args: None

        ui._confirm_human_response()

        self.assertTrue(ui.response_finished)
        self.assertFalse(ui.duel_continued)
        self.assertNotIn(slash, target.hand)
        self.assertIn(slash, ui.engine.discard_pile)

    def test_winner_is_declared_immediately_when_enemies_reach_zero(self):
        winner = make_player(0)
        defeated = make_player(1)
        engine = GameEngine([winner, defeated], [])

        engine.take_damage(defeated, defeated.hp)

        self.assertFalse(defeated.alive)
        self.assertEqual(engine.state.winner, winner.general.name)
        self.assertEqual(engine.state.winner_seat, winner.seat)

    def test_allied_survivors_have_no_living_enemies(self):
        first = make_player(0)
        ally = make_player(1)
        enemy = make_player(2)
        first.side = ally.side = "A"
        enemy.side = "B"
        engine = GameEngine([first, ally, enemy], [])

        engine.take_damage(enemy, enemy.hp)
        winner = engine.check_winner()

        self.assertIn(winner, (first, ally))
        self.assertEqual(engine.get_alive_enemies(first), [])

    def test_turn_starts_and_finishes_in_prepare_phase(self):
        players = [make_player(0), make_player(1)]
        engine = GameEngine(players, [])

        engine.start_turn()
        self.assertEqual(engine.state.phase, Phase.PREPARE)

        engine.finish_turn()
        self.assertEqual(engine.state.phase, Phase.PREPARE)
        self.assertEqual(engine.state.current_turn, 1)

    def test_judgment_can_run_outside_judgment_phase(self):
        player = make_player()
        judged = make_card("red-card", suit="heart")
        engine = GameEngine([player], [judged])
        engine.state.phase = Phase.PLAY

        event = engine.conduct_judgment(player, "阶段外技能", "red")

        self.assertTrue(event.result)
        self.assertIs(event.judging_player, player)
        self.assertEqual(event.step, JudgmentStep.COMPLETED)
        self.assertEqual(engine.state.phase, Phase.PLAY)
        self.assertIn(judged, engine.discard_pile)
        self.assertNotIn(judged, engine.processing_area)

    def test_judgments_have_unique_ids_and_do_not_share_cards(self):
        player = make_player()
        first = make_card("first", suit="heart")
        second = make_card("second", suit="club")
        engine = GameEngine([player], [])
        engine.draw_pile = [second, first]

        first_event = engine.conduct_judgment(player, "第一次", "red")
        second_event = engine.conduct_judgment(player, "第二次", "red")

        self.assertNotEqual(first_event.judgment_id, second_event.judgment_id)
        self.assertIs(first_event.current_card, first)
        self.assertIs(second_event.current_card, second)
        self.assertTrue(first_event.result)
        self.assertFalse(second_event.result)

    def test_replacement_card_becomes_only_final_result(self):
        player = make_player()
        initial = make_card("initial", suit="spade")
        replacement = make_card("replacement", suit="diamond")
        player.hand.append(replacement)
        engine = GameEngine([player], [initial])

        event = engine.begin_judgment(player, "改判测试", "red")
        event = engine.replace_judgment_card(event, replacement)
        event = engine.finalize_judgment(event)

        self.assertTrue(event.result)
        self.assertIs(event.current_card, replacement)
        self.assertEqual(event.replaced_cards, [initial])
        self.assertNotIn(replacement, player.hand)
        self.assertIn(initial, engine.discard_pile)
        self.assertIn(replacement, engine.discard_pile)
        self.assertEqual(engine.processing_area, [])

    def test_rank_rules_use_shared_conversion(self):
        player = make_player()
        engine = GameEngine([player], [])

        self.assertEqual(engine.rank_value(make_card("ace", rank="A")), 1)
        self.assertEqual(engine.rank_value(make_card("queen", rank="Q")), 12)
        self.assertTrue(
            engine.matches_judgment(
                make_card("lightning-hit", suit="spade", rank="9"),
                "spade_2_9",
            )
        )
        self.assertFalse(
            engine.matches_judgment(
                make_card("lightning-miss", suit="spade", rank="K"),
                "spade_2_9",
            )
        )

    def test_nullified_lightning_moves_to_next_judgment_area(self):
        current = make_player(0)
        next_player = make_player(1)
        lightning = Card(
            id="lightning",
            name="闪电",
            suit="spade",
            rank="A",
            kind=CardKind.TRICK,
        )
        current.judgment_area.append(lightning)
        engine = GameEngine([current, next_player], [])

        passed_to = engine.transfer_lightning(current, lightning)

        self.assertIs(passed_to, next_player)
        self.assertNotIn(lightning, current.judgment_area)
        self.assertIn(lightning, next_player.judgment_area)
        self.assertNotIn(lightning, engine.discard_pile)

    def test_death_cleanup_moves_all_owned_cards_to_discard(self):
        player = make_player()
        hand_card = make_card("hand")
        armor = Card(
            id="armor",
            name="白银狮子",
            suit="club",
            rank="A",
            kind=CardKind.EQUIPMENT,
            equipment_type="armor",
        )
        delayed = Card(
            id="delayed",
            name="闪电",
            suit="spade",
            rank="A",
            kind=CardKind.TRICK,
        )
        player.hand.append(hand_card)
        player.equipment.append(armor)
        player.judgment_area.append(delayed)
        player.hp = 0
        engine = GameEngine([player], [])

        engine._kill_check(player)

        self.assertFalse(player.alive)
        self.assertEqual(player.hand, [])
        self.assertEqual(player.equipment, [])
        self.assertEqual(player.judgment_area, [])
        self.assertCountEqual(
            engine.discard_pile, [hand_card, armor, delayed]
        )
        self.assertEqual(player.hp, 0)
        self.assertEqual(
            engine.rule_event_history[-1].event_type, "player_died"
        )
        self.assertEqual(
            engine.rule_event_history[-1].data["general_id"],
            player.general.id,
        )
        self.assertEqual(
            engine.rule_event_history[-1].data["skin_id"],
            "default",
        )


if __name__ == "__main__":
    unittest.main()
