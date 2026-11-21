import os
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from main import (
    ENEMY_EQUIPMENT_BOTTOM_INSET, ENEMY_EQUIPMENT_LEFT_INSET,
    ENEMY_EQUIPMENT_RIGHT_INSET, ENEMY_X, ENEMY_Y, ENEMY_H, ENEMY_W,
    GENERAL_STATE_FRAME_OUTSET,
    GENERAL_TOOLTIP_HOVER_MS,
    GAME_TITLE, GAME_TITLE_DISPLAY, JUDGMENT_ICON_SIZE,
    ME_X, ME_Y, SKILL_NOTICE_FADE_MS,
    SKILL_NOTICE_HOLD_MS, WAIT_AREA_H, WAIT_AREA_Y, GameUI,
)
from src.loader import load_generals
from src.models import Player, SkillKind


ROOT = Path(__file__).resolve().parents[1]


class ImageAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = GameUI()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_selected_card_and_equipment_assets_are_loaded(self):
        for card_name in ("杀", "无懈可击", "青釭剑", "八卦阵"):
            self.assertIn(card_name, self.ui.card_images)
        for equipment_name in ("贯石斧", "八卦阵", "赤兔"):
            self.assertIn(equipment_name, self.ui.equipment_images)

    def test_window_and_top_bar_share_erzhongsha_brand(self):
        self.assertEqual(GAME_TITLE, "二中杀")
        self.assertEqual(GAME_TITLE_DISPLAY, "二 中 杀")
        self.assertTrue(
            pygame.display.get_caption()[0].startswith(GAME_TITLE)
        )

    def test_public_diy_generals_render_without_personal_portraits(self):
        generals = {
            general.id: general
            for general in load_generals(ROOT / "data" / "generals.yml")
        }
        for general_id in ("dingyichen", "zhangyiyan"):
            general = generals[general_id]
            with self.subTest(general_id=general_id):
                self.assertIsNone(self.ui._general_skin_art(general))
                self.ui._draw_general_selection_card(
                    general, pygame.Rect(50, 50, 190, 270)
                )
                player = Player(
                    seat=0, general=general,
                    hp=general.hp, max_hp=general.hp,
                )
                self.ui.draw_general_card(player, 50, 50, 210, 286)

    def test_dingyichen_uses_own_frame_and_legacy_generals_can_opt_out(self):
        self.assertIn("dingyichen", self.ui.general_frame_images)
        frame = self.ui.general_frame_images["dingyichen"]
        self.assertEqual(frame.get_at(frame.get_rect().center).a, 0)
        dingyichen = SimpleNamespace(
            id="dingyichen", use_portrait_frame=True
        )
        guanyu = SimpleNamespace(
            id="guanyu", use_portrait_frame=False
        )
        caocao = SimpleNamespace(
            id="caocao", use_portrait_frame=False
        )
        self.assertIsNotNone(
            self.ui._general_frame_for(dingyichen)
        )
        self.assertIsNone(self.ui._general_frame_for(guanyu))
        self.assertIsNone(self.ui._general_frame_for(caocao))

        configured = {
            general.id: general
            for general in load_generals(ROOT / "data" / "generals.yml")
        }
        self.assertTrue(configured["dingyichen"].use_portrait_frame)
        self.assertFalse(configured["guanyu"].use_portrait_frame)
        self.assertFalse(configured["caocao"].use_portrait_frame)

        player = SimpleNamespace(
            hand=[object(), object(), object()],
            general=SimpleNamespace(name="丁逸晨"),
        )

        hand_text = self.ui._general_hand_text(player, 4)

        self.assertEqual(hand_text, "3/4")
        self.assertNotIn(player.general.name, hand_text)

    def test_confirmed_interface_asset_groups_are_loaded(self):
        self.assertIn("play", self.ui.phase_images)
        self.assertIn("round_start", self.ui.phase_images)
        self.assertIn("0", self.ui.hp_images)
        self.assertIn("1", self.ui.hp_images)
        self.assertIn("playing", self.ui.frame_images)
        self.assertIn("responding", self.ui.frame_images)
        self.assertIn("spade", self.ui.card_suit_images)
        self.assertIn("heart", self.ui.log_suit_images)
        self.assertIn("chain", self.ui.ui_images)
        for key in (
            "indulgence", "supply_shortage", "lightning"
        ):
            self.assertIn(key, self.ui.judgment_icon_images)
            self.assertEqual(
                self.ui.judgment_icon_images[key].get_size(),
                (28, 28),
            )
        self.assertIn("table_background", self.ui.ui_images)
        self.assertIn("card_back", self.ui.ui_images)
        self.assertEqual(self.ui.ui_images["card_back"].get_size(), (420, 572))
        for key in ("save-me", "wei", "shu", "wu", "qun", "careerist"):
            self.assertIn(key, self.ui.death_images)
        self.assertIn("12", self.ui.rank_images["red"])
        self.assertIn("13", self.ui.rank_images["black"])

    def test_all_general_state_frames_expand_outside_the_card(self):
        card = pygame.Rect(100, 120, 214, 300)
        frame = self.ui._general_state_frame_rect(*card)

        self.assertEqual(
            frame,
            card.inflate(
                GENERAL_STATE_FRAME_OUTSET * 2,
                GENERAL_STATE_FRAME_OUTSET * 2,
            ),
        )
        self.assertLess(frame.left, card.left)
        self.assertLess(frame.top, card.top)
        self.assertGreater(frame.right, card.right)
        self.assertGreater(frame.bottom, card.bottom)

    def test_enemy_equipment_panel_fits_inside_card_frame(self):
        panel = self.ui._enemy_equipment_panel_rect(
            ENEMY_X, ENEMY_Y, ENEMY_W, ENEMY_H
        )

        self.assertEqual(
            panel.bottom,
            ENEMY_Y + ENEMY_H - ENEMY_EQUIPMENT_BOTTOM_INSET,
        )
        self.assertEqual(
            panel.left,
            ENEMY_X + ENEMY_EQUIPMENT_LEFT_INSET,
        )
        self.assertEqual(
            panel.right,
            ENEMY_X + ENEMY_W - ENEMY_EQUIPMENT_RIGHT_INSET,
        )

    def test_judgment_marks_form_compact_row_below_general_card(self):
        indulgence = SimpleNamespace(
            id="delayed-indulgence", name="乐不思蜀"
        )
        lightning = SimpleNamespace(
            id="delayed-lightning", name="闪电"
        )
        player = SimpleNamespace(
            is_ai=True,
            judgment_area=[indulgence, lightning],
        )

        rects = self.ui._judgment_icon_rects(
            player, ENEMY_X, ENEMY_Y, ENEMY_W, ENEMY_H
        )

        self.assertEqual(
            [card for card, _rect in rects],
            [lightning, indulgence],
        )
        self.assertTrue(all(
            rect.size == (JUDGMENT_ICON_SIZE, JUDGMENT_ICON_SIZE)
            for _card, rect in rects
        ))
        self.assertEqual(
            rects[0][1].top,
            ENEMY_Y + ENEMY_H + 4,
        )
        self.assertEqual(
            self.ui._judgment_card_center(player, lightning),
            rects[0][1].center,
        )

        future_seat = SimpleNamespace(
            seat=3,
            is_ai=True,
            judgment_area=[lightning],
        )
        future_rect = pygame.Rect(420, 510, 150, 190)
        self.ui.player_card_rects[future_seat.seat] = future_rect
        future_center = self.ui._judgment_card_center(
            future_seat, lightning
        )
        self.assertEqual(
            future_center[1],
            future_rect.bottom + 4 + JUDGMENT_ICON_SIZE // 2,
        )

    def test_enemy_hand_count_uses_matching_name_column(self):
        framed = SimpleNamespace(
            id="dingyichen", use_portrait_frame=True
        )
        legacy = SimpleNamespace(
            id="guanyu", use_portrait_frame=False
        )

        framed_center = self.ui._enemy_hand_count_center(
            framed, ENEMY_X, ENEMY_Y, ENEMY_W, ENEMY_H
        )
        legacy_center = self.ui._enemy_hand_count_center(
            legacy, ENEMY_X, ENEMY_Y, ENEMY_W, ENEMY_H
        )

        self.assertEqual(
            framed_center[0],
            ENEMY_X + round(ENEMY_W * 0.075),
        )
        self.assertEqual(
            legacy_center[0],
            ENEMY_X + round(ENEMY_W * 0.145),
        )
        self.assertLess(framed_center[0], legacy_center[0])

    def test_animation_frames_and_future_skill_icons_are_indexed(self):
        for effect in (
            "slash_red", "jink", "duel", "judgegood",
            "judgebad", "killer", "remove", "seat", "skin_changing",
            "armor/eight_diagram",
            "armor/vineburn", "weapon/axe",
        ):
            self.assertGreater(len(self.ui.effect_frame_paths[effect]), 0)
        self.assertIn("compulsory/1-normal", self.ui.skill_icon_paths)
        self.assertIn("proactive/1-hover", self.ui.skill_icon_paths)

    def test_locked_skills_use_compulsory_button_art(self):
        locked = SimpleNamespace(
            kind=SkillKind.LOCKED, mandatory=True
        )
        optional = SimpleNamespace(
            kind=SkillKind.TRIGGERED, mandatory=False
        )
        self.assertEqual(
            self.ui._skill_button_asset_type(locked), "compulsory"
        )
        self.assertEqual(
            self.ui._skill_button_asset_type(optional), "proactive"
        )
        self.assertIn(
            "compulsory/2-normal", self.ui.skill_icon_paths
        )

    def test_enemy_skill_buttons_are_hidden_but_local_buttons_remain(self):
        enemy = SimpleNamespace(seat=1, is_ai=True)
        local = SimpleNamespace(seat=0, is_ai=False)

        self.assertFalse(
            self.ui._should_draw_persistent_skills(enemy, local)
        )
        self.assertTrue(
            self.ui._should_draw_persistent_skills(local, local)
        )

    def test_general_tooltip_appears_after_one_second_and_clears_on_leave(self):
        enemy = SimpleNamespace(seat=1, is_ai=True)
        local = SimpleNamespace(seat=0, is_ai=False)
        ui = GameUI.__new__(GameUI)
        ui.engine = SimpleNamespace(
            state=SimpleNamespace(players=[local, enemy])
        )
        ui.hover_general_seat = None
        ui.hover_general_started_at = 0
        enemy_position = (ENEMY_X + 10, ENEMY_Y + 10)

        self.assertIsNone(
            ui._update_general_hover(enemy_position, now=100)
        )
        self.assertIsNone(
            ui._update_general_hover(
                enemy_position,
                now=100 + GENERAL_TOOLTIP_HOVER_MS - 1,
            )
        )
        self.assertIs(
            ui._update_general_hover(
                enemy_position,
                now=100 + GENERAL_TOOLTIP_HOVER_MS,
            ),
            enemy,
        )

        self.assertIsNone(
            ui._update_general_hover((0, 0), now=1200)
        )
        self.assertIsNone(ui.hover_general_seat)

        local_position = (ME_X + 10, ME_Y + 10)
        self.assertIsNone(
            ui._update_general_hover(local_position, now=2000)
        )
        self.assertIs(
            ui._update_general_hover(
                local_position,
                now=2000 + GENERAL_TOOLTIP_HOVER_MS,
            ),
            local,
        )

    def test_top_right_exit_button_uses_same_exit_request_as_escape(self):
        button = self.ui.b_exit
        self.assertEqual(button.text, "退出")
        self.assertLessEqual(button.rect.right, self.ui.screen.get_width())
        self.assertLess(button.rect.bottom, 42)

        click = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"button": 1, "pos": button.rect.center},
        )
        escape = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_ESCAPE}
        )
        window_close = pygame.event.Event(pygame.QUIT)
        outside = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"button": 1, "pos": (0, 0)},
        )

        self.assertTrue(self.ui._event_requests_exit(click))
        self.assertTrue(self.ui._event_requests_exit(escape))
        self.assertTrue(
            self.ui._event_requests_exit(window_close)
        )
        self.assertFalse(self.ui._event_requests_exit(outside))

    def test_skill_notice_holds_fades_and_is_replaced_by_new_skill(self):
        ui = GameUI.__new__(GameUI)
        ui.skill_notice = None
        player = SimpleNamespace(
            general=SimpleNamespace(name="关羽")
        )

        ui._announce_skill_use(player, "武圣", now=100)
        self.assertEqual(
            ui.skill_notice["text"],
            "【关羽】使用了技能【武圣】",
        )
        self.assertEqual(
            ui._skill_notice_alpha(
                now=100 + SKILL_NOTICE_HOLD_MS
            ),
            255,
        )
        fading_alpha = ui._skill_notice_alpha(
            now=(
                100 + SKILL_NOTICE_HOLD_MS
                + SKILL_NOTICE_FADE_MS // 2
            )
        )
        self.assertGreater(fading_alpha, 0)
        self.assertLess(fading_alpha, 255)

        ui._announce_skill_use(player, "奸雄", now=500)
        self.assertEqual(
            ui.skill_notice["text"],
            "【关羽】使用了技能【奸雄】",
        )
        self.assertEqual(
            ui._skill_notice_alpha(
                now=500 + SKILL_NOTICE_HOLD_MS
            ),
            255,
        )
        self.assertEqual(
            ui._skill_notice_alpha(
                now=(
                    500 + SKILL_NOTICE_HOLD_MS
                    + SKILL_NOTICE_FADE_MS
                )
            ),
            0,
        )
        self.assertIsNone(ui.skill_notice)

    def test_waiting_area_is_lower_and_animation_slots_follow_it(self):
        ui = GameUI.__new__(GameUI)

        self.assertEqual(WAIT_AREA_Y, 432)
        self.assertEqual(
            ui._wait_slot_center(0)[1],
            WAIT_AREA_Y + WAIT_AREA_H // 2,
        )

    def test_enemy_decision_does_not_use_local_operation_hint_area(self):
        ui = GameUI.__new__(GameUI)
        local = SimpleNamespace(seat=0)
        enemy = SimpleNamespace(seat=1)
        ui.wd = True
        ui.dt = enemy
        ui.fire_attack_context = None
        ui.five_grains_choice = None
        ui.target_card_choice = None
        ui.borrowed_sword_choice = None

        self.assertTrue(
            ui._foreign_operation_in_progress(local, local)
        )

        ui.dt = local
        self.assertFalse(
            ui._foreign_operation_in_progress(local, enemy)
        )

        ui.wd = False
        ui.dt = None
        ui.five_grains_choice = {"chooser": enemy}
        self.assertTrue(
            ui._foreign_operation_in_progress(local, local)
        )

    def test_general_selection_grid_has_at_most_four_cards_per_row(self):
        rects = GameUI._general_selection_rects(8)

        self.assertEqual(len(rects), 8)
        self.assertEqual(
            len({rect.y for rect in rects}), 2
        )
        self.assertEqual(
            [rect.y for rect in rects].count(rects[0].y), 4
        )
        self.assertEqual(
            [rect.y for rect in rects].count(rects[-1].y), 4
        )

    def test_general_selection_title_is_independent_of_frame_style(self):
        dingyichen = SimpleNamespace(
            kingdom="神", name="丁逸晨", hp=4,
            use_portrait_frame=True,
        )
        guanyu = SimpleNamespace(
            kingdom="蜀", name="关羽", hp=4,
            use_portrait_frame=False,
        )

        self.assertEqual(
            self.ui._general_selection_title(dingyichen),
            "神·丁逸晨  体力4",
        )
        self.assertEqual(
            self.ui._general_selection_title(guanyu),
            "蜀·关羽  体力4",
        )

    def test_fire_attack_does_not_create_a_separate_choice_panel(self):
        ui = GameUI.__new__(GameUI)
        ui.fire_attack_context = {"choices": [object()]}
        ui.fire_attack_choice_rects = [(pygame.Rect(0, 0, 10, 10), object())]

        ui._draw_fire_attack_choice()

        self.assertEqual(ui.fire_attack_choice_rects, [])

    def test_fire_attack_discard_can_be_cancelled(self):
        ui = GameUI.__new__(GameUI)
        actor = SimpleNamespace(
            general=SimpleNamespace(name="测试武将")
        )
        ui.fire_attack_context = {
            "stage": "discard", "actor": actor, "choices": [object()]
        }
        ui.fire_attack_choice_rects = []
        ui.idx = 2
        messages = []
        finished = []
        ui.msg = messages.append
        ui._xd = lambda: finished.append(True)

        ui._cancel_fire_attack_discard()

        self.assertIsNone(ui.fire_attack_context)
        self.assertIsNone(ui.idx)
        self.assertTrue(finished)
        self.assertIn("放弃", messages[-1])

    def test_fire_attack_without_matching_suit_waits_for_cancel(self):
        ui = GameUI.__new__(GameUI)
        actor = SimpleNamespace(
            is_ai=False,
            hand=[SimpleNamespace(suit="spade")],
            general=SimpleNamespace(name="测试武将"),
        )
        revealed = SimpleNamespace(suit="heart")
        ui.fire_attack_context = {
            "actor": actor,
            "revealed": revealed,
        }
        hints = []
        finished = []
        ui.hint = lambda text, *_args: hints.append(text)
        ui._xd = lambda: finished.append(True)

        ui._offer_fire_attack_discard()

        self.assertEqual(ui.fire_attack_context["stage"], "discard")
        self.assertEqual(ui.fire_attack_context["choices"], [])
        self.assertIn("取消", hints[-1])
        self.assertFalse(finished)

    def test_fire_attack_reveal_cancel_only_clears_selection(self):
        ui = GameUI.__new__(GameUI)
        selected = object()
        ui.fire_attack_context = {
            "stage": "reveal",
            "selected": selected,
            "title": "请选择一张手牌展示",
        }
        ui.idx = 1
        hints = []
        ui.hint = lambda text, *_args: hints.append(text)

        ui._clear_fire_attack_reveal_selection()

        self.assertIsNotNone(ui.fire_attack_context)
        self.assertIsNone(ui.fire_attack_context["selected"])
        self.assertIsNone(ui.idx)
        self.assertIn("展示", hints[-1])

    def test_local_player_arrow_target_is_hand_area_bottom_center(self):
        ui = GameUI.__new__(GameUI)
        local_player = SimpleNamespace(is_ai=False)

        target = ui._arrow_target_center(local_player)

        self.assertEqual(target[1], 872 + 148)

    def test_local_player_arrow_source_matches_hand_area_target(self):
        ui = GameUI.__new__(GameUI)
        local_player = SimpleNamespace(is_ai=False)

        self.assertEqual(
            ui._play_arrow_source(local_player),
            ui._arrow_target_center(local_player),
        )
