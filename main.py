"""二中杀 1v1：古风卡牌对战游戏。"""

import sys, math, random
from pathlib import Path
import pygame
from src.loader import load_cards, load_generals
from src.models import (
    ActiveCardUseEvent, Card, CardKind, CardResponseEvent, DamageEvent,
    DamageNature, DyingEvent, Phase, Player, PlayerChoice, PromptContext,
    PromptType, ResolutionFrame, SkillKind, SkillTiming,
    TrickCardDiscardEvent,
)
from src.engine import GameEngine
from src.audio import SoundManager
from src.general_selection import GeneralSelectionState
from src.skill_modules.base import SkillAIContext
from src.ai import (
    choose_borrowed_sword_plan, choose_control_card_choice,
    choose_control_target, choose_fire_attack_target,
    choose_equipment_to_play, choose_low_value_cards, choose_slash_plan,
    choose_zhangba_plan, should_use_five_grains,
    should_use_analeptic_for_slash, should_use_peach_garden,
    should_use_peach_for_dying,
    should_use_zhangba_response,
)

ROOT = Path(__file__).parent
IMAGE_ROOT = ROOT / "images"
SOUND_ROOT = ROOT / "sound"
GAME_TITLE = "二中杀"
GAME_TITLE_DISPLAY = " ".join(GAME_TITLE)

W, H = 1707, 1067
FPS = 60
AI_DELAY_MS = 1100
AUTO_DRAW_DELAY_MS = 550
ARROW_ANIM_MS = 260
ARROW_HOLD_MS = 650
BORROWED_SWORD_ARROW_GAP_MS = 600
CARD_MOVE_MS = 360
DRAW_CARD_MOVE_MS = 950
CARD_FADE_MS = 420
PLAY_TIME_LIMIT_MS = 15000
HIT_ANIM_MS = 260
HIT_OFFSET = 10
JUDGMENT_RESULT_HOLD_MS = 1000
AI_DISCARD_THINK_MS = 850
FIVE_GRAINS_REVEAL_HOLD_MS = 900
SKILL_REVEAL_PANEL_HOLD_MS = 2000
GENERAL_TOOLTIP_HOVER_MS = 1000
SKILL_NOTICE_HOLD_MS = 2000
SKILL_NOTICE_FADE_MS = 600
GENERAL_SELECTION_AI_DELAY_MS = 700
GENERAL_SELECTION_COMPLETE_HOLD_MS = 700
JUDGMENT_ICON_SIZE = 28
JUDGMENT_ICON_GAP = 5
# 选将操作者与进入对局后的座位控制权是两套独立配置。
# 当前测试模式由本地玩家依次为两个座位选将，但二号位进入游戏后仍由 AI 控制。
GENERAL_SELECTION_SEAT_IS_AI = (False, False)
GAMEPLAY_SEAT_IS_AI = (False, True)
# 状态框的高亮线必须落在武将牌外侧，不能压住边框内的势力字或姓名。
GENERAL_STATE_FRAME_OUTSET = 24

# ========== 古风配色 ==========
# 主背景 - 深棕木质
C_BG = (38, 28, 22)
C_BG_GRAD = (58, 42, 32)
# 顶部栏
C_TOP = (30, 22, 16)
C_TOP_BORDER = (139, 105, 20)
# 金色系
C_GOLD = (218, 165, 32)
C_GOLD_LIGHT = (255, 215, 0)
C_GOLD_DARK = (184, 134, 11)
# 红色系 - 蜀
C_RED = (178, 34, 34)
C_RED_LIGHT = (220, 80, 60)
# 蓝色系 - 魏
C_BLUE = (30, 80, 160)
C_BLUE_LIGHT = (70, 130, 200)
# 绿色系 - 吴
C_GREEN = (46, 139, 87)
C_GREEN_LIGHT = (80, 180, 100)
# 灰色系 - 群
C_GREY = (128, 128, 128)
C_GREY_LIGHT = (169, 169, 169)
# 文字颜色
C_W = (245, 222, 179)  # 小麦色
C_W_DARK = (210, 180, 140)
C_GY = (160, 140, 110)
# 卡牌底色
C_CD = (245, 235, 220)  # 米黄色
C_CD_BORDER = (139, 115, 85)
# 按钮
C_BTN = (101, 67, 33)  # 深棕
C_BTN_H = (139, 90, 43)  # 浅棕
C_BTN_BORDER = (218, 165, 32)  # 金边

# 势力颜色
KC = {
    "蜀": (180, 50, 50),
    "魏": (50, 80, 160),
    "吴": (50, 140, 90),
    "群": (140, 120, 80),
    "神": (135, 90, 175),
}
KC_LIGHT = {
    "蜀": (220, 80, 70),
    "魏": (80, 120, 200),
    "吴": (80, 180, 120),
    "群": (180, 160, 110),
    "神": (185, 135, 225),
}
SS = {"spade":"♠","heart":"♥","club":"♣","diamond":"♦"}
SUIT_CN = {"spade":"黑桃","heart":"红桃","club":"梅花","diamond":"方块"}
SC = {"spade":(20,20,20),"heart":(180,30,30),"club":(20,20,20),"diamond":(180,30,30)}
def _resolve_ui_font():
    preferred = Path("C:/Windows/Fonts/simhei.ttf")
    if preferred.is_file():
        return str(preferred)
    return pygame.font.match_font(
        "microsoftyahei,msyahei,simsun,dengxian,notosanscjksc,wenquanyizenhei"
    )


FONT = _resolve_ui_font()

# ========== 布局常量 ==========
# 参考端游牌桌：中央留给战场，右侧日志，底部手牌与操作区
TOP_BAR_H = 42
BOTTOM_BAR_Y = 796
BOTTOM_BAR_H = H - BOTTOM_BAR_Y
TABLE_L, TABLE_T = 0, TOP_BAR_H
TABLE_R, TABLE_B = 1405, BOTTOM_BAR_Y
TABLE_CX = (TABLE_L + TABLE_R) // 2
TABLE_CY = (TABLE_T + TABLE_B) // 2

# 敌方武将 - 上方偏中
ENEMY_W, ENEMY_H = 214, 300
ENEMY_X, ENEMY_Y = TABLE_CX - ENEMY_W//2, 48
ENEMY_EQUIPMENT_ROW_H = 18
ENEMY_EQUIPMENT_LEFT_INSET = 30
ENEMY_EQUIPMENT_RIGHT_INSET = 28
ENEMY_EQUIPMENT_BOTTOM_INSET = 10
# 我方武将 - 右下
ME_W, ME_H = 206, 252
ME_X, ME_Y = 1480, 804
# 卡牌尺寸
CARD_W, CARD_H = 98, 148
# 中央等待区
WAIT_AREA_X, WAIT_AREA_Y = TABLE_CX - 280, 432
WAIT_AREA_W, WAIT_AREA_H = 560, 156
WAIT_CARD_W, WAIT_CARD_H = 72, 108
DRAW_SOURCE_POS = (TABLE_R - 60, 21)
# 按钮位置
BTN_Y = 742
# 手牌区域
HAND_Y = 872
HAND_LEFT_X = 222
HAND_SPACING = 76
SELECTED_CARD_RISE = 62
# 装备区
EQUIP_Y = 826
# 侧边栏
SIDEBAR_L = 1405


def draw_rounded_rect(surface, color, rect, radius=8, border=0, border_color=None):
    """绘制圆角矩形"""
    x, y, w, h = rect
    if border > 0 and border_color:
        pygame.draw.rect(surface, border_color, (x-border, y-border, w+border*2, h+border*2), border_radius=radius+border)
    pygame.draw.rect(surface, color, rect, border_radius=radius)


def draw_gold_border(surface, rect, width=2):
    """绘制金色装饰边框"""
    x, y, w, h = rect
    pygame.draw.rect(surface, C_GOLD_DARK, (x, y, w, h), width, border_radius=8)
    pygame.draw.rect(surface, C_GOLD, (x+1, y+1, w-2, h-2), 1, border_radius=7)
    # 四角装饰
    corner_size = 12
    for cx, cy in [(x, y), (x+w-corner_size, y), (x, y+h-corner_size), (x+w-corner_size, y+h-corner_size)]:
        pygame.draw.rect(surface, C_GOLD_LIGHT, (cx, cy, corner_size, 3))
        pygame.draw.rect(surface, C_GOLD_LIGHT, (cx, cy, 3, corner_size))


def draw_vertical_gradient(surface, rect, top, bottom):
    """绘制垂直渐变矩形"""
    x, y, w, h = rect
    if h <= 0: return
    for i in range(h):
        ratio = i / max(1, h - 1)
        c = (
            int(top[0] * (1-ratio) + bottom[0] * ratio),
            int(top[1] * (1-ratio) + bottom[1] * ratio),
            int(top[2] * (1-ratio) + bottom[2] * ratio),
        )
        pygame.draw.line(surface, c, (x, y+i), (x+w, y+i))


def draw_jade(surface, x, y, filled=True, color=None):
    """绘制逗号形勾玉；空体力显示为暗色轮廓。"""
    jade_color = color if filled and color else ((72, 62, 54) if not filled else C_RED)
    border_color = (238, 217, 144) if filled else (105, 91, 76)
    # 圆润的玉身与向右下弯曲的玉尾组成逗号形，不使用阴阳鱼贴图。
    pygame.draw.circle(surface, jade_color, (x-2, y-2), 9)
    pygame.draw.polygon(
        surface, jade_color,
        [(x-1, y+4), (x+10, y+1), (x+12, y+10), (x+3, y+7)]
    )
    pygame.draw.circle(surface, border_color, (x-2, y-2), 9, 2)
    pygame.draw.lines(
        surface, border_color, False,
        [(x-1, y+5), (x+10, y+1), (x+12, y+10), (x+3, y+7)],
        2
    )
    # 小高光强调玉石质感，不绘制阴阳鱼式的反色圆点。
    highlight = tuple(min(255, channel + 52) for channel in jade_color)
    pygame.draw.circle(surface, highlight, (x-5, y-5), 2)


class Button:
    def __init__(self, x, y, w, h, text):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.visible = True
        self.enabled = True
    def draw(self, screen, font, mp=None):
        if not self.visible: return
        h = self.enabled and mp and self.rect.collidepoint(mp)
        if self.enabled:
            c1 = (88, 80, 74) if h else (54, 49, 46)
            c2 = (35, 31, 30) if h else (22, 20, 19)
            border = (185, 164, 126)
            text_color = (255, 245, 220) if h else (238, 220, 180)
        else:
            c1, c2 = (43, 41, 39), (25, 24, 23)
            border = (91, 85, 76)
            text_color = (105, 101, 94)
        draw_rounded_rect(screen, (9, 8, 7), self.rect, radius=5, border=2, border_color=border)
        draw_vertical_gradient(screen, self.rect.inflate(-6, -6), c1, c2)
        pygame.draw.rect(screen, border, self.rect.inflate(-8, -8), 1, border_radius=4)
        img = font.render(self.text, True, text_color)
        screen.blit(img, img.get_rect(center=self.rect.center))
    def click(self, p):
        if not self.visible or not self.enabled: return False
        return self.rect.collidepoint(p)


class GameUI:
    def __init__(self):
        pygame.init()
        self.sound = SoundManager(SOUND_ROOT)
        self.sound.play_bgm("main_theme")
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption(f"{GAME_TITLE} - 1v1")
        self.clock = pygame.time.Clock()
        self.f = {}
        for n,s in [("t",42),("b",24),("s",18),("ts",14),("c",20),("cl",14),("n",22),("btn",22),("h",16),("card_name",22)]:
            self.f[n] = pygame.font.Font(FONT, s)
        self.idx = None
        self.pending_target = None
        self.pending_targets = []
        self.logs = []
        self.hint_text = ""
        self.hint_until = 0
        self.engine = None
        self.go = False
        self.game_over_announced = False
        self.wd = False; self.dt = None; self.da = None
        self.response_card_name = "闪"
        self.response_source_name = "杀"
        self.response_source_card = None
        self.response_source_physical_cards = ()
        self.response_action = "打出"
        self.response_success_callback = None
        self.response_failure_callback = None
        self.card_use_event_queue = []
        self.card_use_trigger_in_progress = False
        self.active_prompt = None
        self.skill_prompt_cards = []
        self.skill_prompt_required_cards = 0
        self.skill_prompt_selected = set()
        self.skill_prompt_targets = []
        self.skill_prompt_selected_target = None
        self.skill_prompt_ai_select_target_callback = None
        self.prompt_handlers = {}
        self.active_slash_event = None
        self.active_trick_cards = []
        self.active_conversion_resolution_events = []
        self.weapon_followup_context = None
        self.pending_skill_action = None
        self.slash_target_queue = []
        self.next_prompt_id = 1
        self.response_queue = []
        self.duel_active = False
        self.dying_target = None
        self.dying_queue = []
        self.dying_complete_callback = None
        self.resolution_stack = []
        self.next_resolution_event_id = 1
        self.ai_busy = False; self.ai_step = 0
        self.ai_next_action_at = 0
        self.ai_response_at = 0
        self.player_draw_at = 0
        self.draw_finish_at = 0
        self.draw_animating = False
        self.draw_phase_pending_seat = None
        self.initial_deal_animating = False
        self.first_turn_started = False
        self.waiting_cards = []
        self.animations = []
        self.hit_animations = {}
        self.target_card_choice = None
        self.target_card_choice_rects = []
        self.skill_reveal_panel = None
        self.five_grains_choice = None
        self.five_grains_choice_rects = []
        self.five_grains_reveal_at = 0
        self.borrowed_sword_choice = None
        self.borrowed_sword_resolution = None
        self.nullification_context = None
        self.nullification_ai_player = None
        self.fire_attack_context = None
        self.fire_attack_choice_rects = []
        self.hidden_draw_cards = set()
        self.hidden_judgment_cards = set()
        self.hidden_equipment_cards = set()
        self.delayed_trick_sources = {}
        self.discard_selected = []
        self.fade_waiting_when_idle = False
        self.play_time_remaining = PLAY_TIME_LIMIT_MS
        self.play_timer_last_tick = pygame.time.get_ticks()
        self.response_time_remaining = 0
        self.response_timer_last_tick = pygame.time.get_ticks()
        self.phase_transition_at = 0
        self.phase_transition_callback = None
        self.judgment_cards_remaining = 0
        self.active_judgment_id = None
        self.judgment_result_tip = None
        self.judgment_result_success = None
        self.judgment_display_in_progress = False
        self.card_images = {}
        self.general_images = {}
        self.general_frame_images = {}
        self.ui_images = {}
        self.equipment_images = {}
        self.phase_images = {}
        self.judgment_icon_images = {}
        self.hp_images = {}
        self.frame_images = {}
        self.death_images = {}
        self.card_suit_images = {}
        self.log_suit_images = {}
        self.rank_images = {"red": {}, "black": {}}
        self.hp_tint_cache = {}
        self.effect_frame_paths = {}
        self.effect_surface_cache = {}
        self.skill_icon_paths = {}
        self.skill_button_rects = {}
        self.player_card_rects = {}
        self.hover_general_seat = None
        self.hover_general_started_at = 0
        self.skill_notice = None
        self.visual_effects = []
        self.scaled_images = {}
        self._load_image_assets()
        self.scroll = 0
        # 按钮
        btn_w, btn_h = 110, 50
        self.btn_w = btn_w
        self.btn_h = btn_h
        self.end_btn_w = 84
        self.button_gap = 26
        self.b_end = Button(TABLE_CX + 273, BTN_Y, self.end_btn_w, btn_h, "结束")
        self.b_step = Button(TABLE_CX - btn_w//2, BTN_Y, btn_w, btn_h, "摸牌")
        self.b_cancel = Button(TABLE_CX - self.button_gap//2 - btn_w, BTN_Y, btn_w, btn_h, "取消")
        self.b_confirm = Button(TABLE_CX + self.button_gap//2, BTN_Y, btn_w, btn_h, "确定")
        self.b_exit = Button(W - 90, 6, 76, 30, "退出")
        self.b_end.visible = True; self.b_step.visible = True

    def _layout_single_button(self, button):
        # 确认类固定在中央偏左；结束、取消、放弃类固定在中央偏右。
        progress_left = TABLE_CX - 220
        progress_right = TABLE_CX + 220
        if button is self.b_confirm:
            button.rect.x = progress_left
        else:
            button.rect.x = progress_right - self.btn_w
        button.rect.y = BTN_Y

    def _layout_pair_buttons(self):
        progress_left = TABLE_CX - 220
        progress_right = TABLE_CX + 220
        self.b_confirm.rect.x = progress_left
        self.b_confirm.rect.y = BTN_Y
        self.b_cancel.rect.x = progress_right - self.btn_w
        self.b_cancel.rect.y = BTN_Y

    def _layout_end_button(self):
        """独立结束按钮：位于进度条右端外侧，与其他操作按钮等高。"""
        progress_right = TABLE_CX + 255
        self.b_end.rect.x = progress_right + 18
        self.b_end.rect.y = BTN_Y
        self.b_end.rect.w = self.end_btn_w
        self.b_end.rect.h = self.btn_h

    def _event_requests_exit(self, event):
        """窗口关闭、Esc与右上角按钮统一返回退出请求。"""
        if event.type == pygame.QUIT:
            return True
        if (
            event.type == pygame.KEYDOWN
            and event.key == pygame.K_ESCAPE
        ):
            return True
        return bool(
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.b_exit.click(event.pos)
        )

    @staticmethod
    def _general_selection_rects(count):
        """按每行最多四张返回居中的两行选将牌位置。"""
        card_w, card_h = 190, 270
        gap_x, gap_y = 34, 38
        rows = []
        remaining = max(0, min(8, count))
        while remaining:
            row_count = min(4, remaining)
            row_width = row_count * card_w + (row_count - 1) * gap_x
            start_x = (W - row_width) // 2
            rows.append([
                pygame.Rect(
                    start_x + column * (card_w + gap_x),
                    170 + len(rows) * (card_h + gap_y),
                    card_w,
                    card_h,
                )
                for column in range(row_count)
            ])
            remaining -= row_count
        return [rect for row in rows for rect in row]

    def _draw_general_selection_card(
        self, general, rect, selected_seat=None, hovered=False
    ):
        shadow = pygame.Surface(
            (rect.w + 10, rect.h + 10), pygame.SRCALPHA
        )
        pygame.draw.rect(
            shadow, (0, 0, 0, 150), shadow.get_rect(),
            border_radius=10,
        )
        self.screen.blit(shadow, (rect.x - 3, rect.y - 2))
        # 选将阶段尚未选择皮肤，始终展示武将配置的默认皮肤。
        art = self._general_skin_art(
            general, general.default_skin_id
        )
        if art:
            self.screen.blit(
                self._scaled_cover(
                    (
                        f"selection:{general.id}:"
                        f"{general.default_skin_id}"
                    ),
                    art,
                    rect.w,
                    rect.h,
                ),
                rect.topleft,
            )
        else:
            draw_vertical_gradient(
                self.screen,
                rect,
                KC_LIGHT.get(general.kingdom, (120, 100, 80)),
                (34, 27, 23),
            )
            self.drw(
                general.name[:1], "t",
                rect.centerx, rect.centery - 18,
                C_GOLD_LIGHT, center=True,
            )
        info = pygame.Surface(
            (rect.w, 76), pygame.SRCALPHA
        )
        pygame.draw.rect(
            info, (8, 7, 6, 205), info.get_rect(),
            border_radius=7,
        )
        self.screen.blit(info, (rect.x, rect.bottom - 76))
        self._draw_general_frame(
            general, rect.x, rect.y, rect.w, rect.h
        )
        self.drw(
            self._general_selection_title(general),
            "s", rect.centerx, rect.bottom - 57,
            C_GOLD_LIGHT, center=True,
        )
        skill_names = " / ".join(
            skill.name for skill in general.skills
        ) or "无技能"
        self.drw(
            skill_names, "ts",
            rect.centerx, rect.bottom - 27,
            C_W, center=True,
        )
        border = C_GOLD_LIGHT if hovered else (205, 185, 144)
        pygame.draw.rect(
            self.screen, border, rect,
            4 if hovered else 2, border_radius=8,
        )
        if selected_seat is not None:
            shade = pygame.Surface(
                (rect.w, rect.h), pygame.SRCALPHA
            )
            shade.fill((35, 35, 35, 188))
            self.screen.blit(shade, rect.topleft)
            pygame.draw.rect(
                self.screen, (105, 105, 105), rect,
                3, border_radius=8,
            )
            self.drw(
                f"{selected_seat + 1}号位已选择",
                "b", rect.centerx, rect.centery,
                (205, 205, 205), center=True,
            )

    @staticmethod
    def _general_selection_title(general):
        """选将信息栏统一显示公开身份信息，不受边框类型影响。"""
        return f"{general.kingdom}·{general.name}  体力{general.hp}"

    def _draw_general_selection(self, state, mouse_pos):
        draw_vertical_gradient(
            self.screen, (0, 0, W, H),
            (68, 50, 34), (20, 16, 14),
        )
        table_art = self.ui_images.get("table_background")
        if table_art:
            background = self._scaled(
                "selection:background", table_art, W, H
            ).copy()
            background.set_alpha(115)
            self.screen.blit(background, (0, 0))
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((10, 8, 7, 72))
        self.screen.blit(veil, (0, 0))
        self.drw(
            "武 将 选 择", "t",
            W // 2, 52, C_GOLD_LIGHT, center=True,
        )
        if state.complete:
            prompt = "选将完成，即将开始游戏"
        elif state.current_is_ai:
            prompt = f"{state.current_seat + 1}号位正在选择武将……"
        else:
            prompt = f"请为 {state.current_seat + 1}号位选择一名武将"
        self.drw(
            prompt, "b", W // 2, 112,
            C_W, center=True,
        )
        rects = self._general_selection_rects(
            len(state.candidates)
        )
        for general, rect in zip(state.candidates, rects):
            selected_seat = state.selected_seat(general)
            self._draw_general_selection_card(
                general,
                rect,
                selected_seat=selected_seat,
                hovered=(
                    selected_seat is None
                    and not state.complete
                    and not state.current_is_ai
                    and rect.collidepoint(mouse_pos)
                ),
            )
        self.drw(
            "已选武将会变为灰色，后续座位不能重复选择",
            "s", W // 2, H - 55,
            C_W_DARK, center=True,
        )
        self.b_exit.draw(self.screen, self.f["btn"], mouse_pos)
        return rects

    def choose_generals(
        self, generals,
        seat_is_ai=GENERAL_SELECTION_SEAT_IS_AI,
    ):
        """运行独立开局选将阶段；退出时返回 None。"""
        state = GeneralSelectionState.create(
            generals, tuple(seat_is_ai)
        )
        ai_choose_at = (
            pygame.time.get_ticks() + GENERAL_SELECTION_AI_DELAY_MS
            if state.current_is_ai else 0
        )
        complete_at = 0
        while True:
            now = pygame.time.get_ticks()
            mouse_pos = pygame.mouse.get_pos()
            rects = self._draw_general_selection(
                state, mouse_pos
            )
            pygame.display.flip()
            for event in pygame.event.get():
                if self._event_requests_exit(event):
                    return None
                if (
                    event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1
                    and not state.complete
                    and not state.current_is_ai
                ):
                    selected = next(
                        (
                            general
                            for general, rect in zip(
                                state.candidates, rects
                            )
                            if rect.collidepoint(event.pos)
                        ),
                        None,
                    )
                    if (
                        selected is not None
                        and state.choose(
                            state.current_seat, selected
                        )
                    ):
                        if state.complete:
                            complete_at = (
                                now
                                + GENERAL_SELECTION_COMPLETE_HOLD_MS
                            )
                        elif state.current_is_ai:
                            ai_choose_at = (
                                now + GENERAL_SELECTION_AI_DELAY_MS
                            )
            if (
                not state.complete
                and state.current_is_ai
                and ai_choose_at
                and now >= ai_choose_at
            ):
                state.choose_current_ai()
                ai_choose_at = 0
                if state.complete:
                    complete_at = (
                        now + GENERAL_SELECTION_COMPLETE_HOLD_MS
                    )
                elif state.current_is_ai:
                    ai_choose_at = (
                        now + GENERAL_SELECTION_AI_DELAY_MS
                    )
            if state.complete and complete_at and now >= complete_at:
                return state.ordered_selections()
            self.clock.tick(FPS)

    def _load_surface(self, path):
        try:
            return pygame.image.load(str(path)).convert_alpha()
        except (pygame.error, FileNotFoundError):
            return None

    def _load_image_assets(self):
        cards_dir = IMAGE_ROOT / "cards"
        if cards_dir.exists():
            for path in cards_dir.rglob("*"):
                if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                    surf = self._load_surface(path)
                    if surf:
                        self.card_images[path.stem] = surf
            # 素材包使用了旧译名，映射到牌堆中的标准牌名。
            card_aliases = {"青釭剑": "青钢剑", "雌雄双股剑": "雌雄双剑"}
            for card_name, asset_name in card_aliases.items():
                if card_name not in self.card_images and asset_name in self.card_images:
                    self.card_images[card_name] = self.card_images[asset_name]

        generals_dir = IMAGE_ROOT / "generals"
        if generals_dir.exists():
            for path in generals_dir.iterdir():
                if path.is_file() and path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                    surf = self._load_surface(path)
                    if surf:
                        self.general_images[path.stem] = surf
                elif path.is_dir():
                    general_id = path.name
                    for skin_dir in path.iterdir():
                        if not skin_dir.is_dir():
                            continue
                        card_path = next(
                            (
                                candidate
                                for candidate in skin_dir.iterdir()
                                if candidate.is_file()
                                and candidate.stem == "card"
                                and candidate.suffix.lower() in (
                                    ".png", ".jpg", ".jpeg", ".webp", ".bmp"
                                )
                            ),
                            None,
                        )
                        if card_path is None:
                            continue
                        surf = self._load_surface(card_path)
                        if surf:
                            self.general_images[
                                (general_id, skin_dir.name)
                            ] = surf
            if "许诸" in self.general_images and "许褚" not in self.general_images:
                self.general_images["许褚"] = self.general_images["许诸"]

        general_frames_dir = IMAGE_ROOT / "general_frames" / "runtime"
        if general_frames_dir.exists():
            for path in general_frames_dir.iterdir():
                if (
                    path.is_file()
                    and path.suffix.lower()
                    in (".png", ".jpg", ".jpeg", ".webp", ".bmp")
                ):
                    surf = self._load_surface(path)
                    if surf:
                        self.general_frame_images[path.stem] = surf

        ui_dir = IMAGE_ROOT / "ui"
        if ui_dir.exists():
            for path in ui_dir.iterdir():
                if path.is_file() and path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                    surf = self._load_surface(path)
                    if surf:
                        self.ui_images[path.stem] = surf

        equipment_dir = IMAGE_ROOT / "equipment_icons"
        equipment_aliases = {
            "Axe": "贯石斧", "Blade": "青龙偃月刀", "ChiTu": "赤兔",
            "Crossbow": "诸葛连弩", "DaYuan": "大宛", "DiLu": "的卢",
            "DoubleSword": "雌雄双股剑", "EightDiagram": "八卦阵",
            "Fan": "朱雀羽扇", "Halberd": "方天画戟", "IceSword": "寒冰剑",
            "JueYing": "绝影", "KylinBow": "麒麟弓", "QinggangSword": "青釭剑",
            "RenwangShield": "仁王盾", "SilverLion": "白银狮子",
            "Spear": "丈八蛇矛", "Vine": "藤甲",
            "ZhuaHuangFeiDian": "爪黄飞电", "ZiXing": "紫骍",
        }
        if equipment_dir.exists():
            for path in equipment_dir.iterdir():
                surf = self._load_surface(path)
                name = equipment_aliases.get(path.stem)
                if surf and name:
                    self.equipment_images[name] = surf

        ui_assets = IMAGE_ROOT / "ui_assets"
        groups = (
            ("阶段", self.phase_images),
            ("判定标志", self.judgment_icon_images),
            ("体力", self.hp_images),
            ("状态边框", self.frame_images),
            ("卡面花色", self.card_suit_images),
            ("日志花色", self.log_suit_images),
        )
        for folder, destination in groups:
            directory = ui_assets / folder
            if not directory.exists():
                continue
            for path in directory.iterdir():
                surf = self._load_surface(path)
                if surf:
                    destination[path.stem] = surf
        core_dir = ui_assets / "核心界面"
        for name in ("chain", "enabled", "disabled"):
            art = self._load_surface(core_dir / f"{name}.png")
            if art:
                self.ui_images[name] = art

        effects_dir = IMAGE_ROOT / "effects"
        if effects_dir.exists():
            for directory in (path for path in effects_dir.rglob("*") if path.is_dir()):
                frames = [
                    path for path in directory.iterdir()
                    if path.is_file() and path.stem.isdigit()
                    and path.suffix.lower() == ".png"
                ]
                if frames:
                    key = directory.relative_to(effects_dir).as_posix()
                    self.effect_frame_paths[key] = sorted(
                        frames, key=lambda path: int(path.stem)
                    )

        skill_icons_dir = IMAGE_ROOT / "skill_icons"
        if skill_icons_dir.exists():
            for path in skill_icons_dir.rglob("*.png"):
                key = path.relative_to(skill_icons_dir).with_suffix("").as_posix()
                self.skill_icon_paths[key] = path

        card_marks_dir = IMAGE_ROOT / "card_marks"
        for color in ("red", "black"):
            directory = card_marks_dir / color
            if directory.exists():
                for path in directory.glob("*.png"):
                    surf = self._load_surface(path)
                    if surf:
                        self.rank_images[color][path.stem] = surf
        marks_suits = card_marks_dir / "suits"
        if marks_suits.exists():
            for path in marks_suits.glob("*.png"):
                surf = self._load_surface(path)
                if surf:
                    self.card_suit_images[path.stem] = surf

        components_dir = ui_assets / "系统部件"
        component_keys = {
            "tableBg": "table_background",
        }
        if components_dir.exists():
            for path in components_dir.iterdir():
                if not path.is_file():
                    continue
                surf = self._load_surface(path)
                if surf:
                    key = component_keys.get(path.stem, f"system:{path.stem}")
                    self.ui_images[key] = surf

        death_dir = ui_assets / "死亡"
        if death_dir.exists():
            for path in death_dir.glob("*.png"):
                surf = self._load_surface(path)
                if surf:
                    self.death_images[path.stem] = surf

    def _scaled(self, key, surf, w, h):
        cache_key = (key, w, h)
        if cache_key not in self.scaled_images:
            self.scaled_images[cache_key] = pygame.transform.smoothscale(surf, (w, h))
        return self.scaled_images[cache_key]

    def _scaled_cover(self, key, surf, w, h):
        """保持原图比例并居中裁切到目标尺寸，避免皮肤牌面被拉伸。"""
        cache_key = (f"cover:{key}", w, h)
        if cache_key in self.scaled_images:
            return self.scaled_images[cache_key]
        source_w, source_h = surf.get_size()
        target_ratio = w / h
        source_ratio = source_w / source_h
        if source_ratio > target_ratio:
            crop_w = max(1, round(source_h * target_ratio))
            crop_rect = pygame.Rect(
                (source_w - crop_w) // 2, 0, crop_w, source_h
            )
        else:
            crop_h = max(1, round(source_w / target_ratio))
            crop_rect = pygame.Rect(
                0, (source_h - crop_h) // 2, source_w, crop_h
            )
        cropped = surf.subsurface(crop_rect)
        self.scaled_images[cache_key] = pygame.transform.smoothscale(
            cropped, (w, h)
        )
        return self.scaled_images[cache_key]

    def _draw_hp_jades(self, player, x, y, w, h):
        """使用现成阴阳鱼素材，并按当前体力切换绿、黄、红三档。"""
        hp_y = y + h - 24
        hp_color = (
            (62, 190, 91) if player.hp >= 3
            else (232, 182, 48) if player.hp == 2
            else (215, 55, 46)
        )
        color_key = "green" if player.hp >= 3 else "yellow" if player.hp == 2 else "red"
        filled_art = self.hp_images.get("1")
        empty_art = self.hp_images.get("0")
        for index in range(player.max_hp):
            filled = index < max(0, player.hp)
            center_y = hp_y - index * 26
            art = filled_art if filled else empty_art
            if art:
                if filled:
                    cache_key = (color_key, id(filled_art))
                    colored = self.hp_tint_cache.get(cache_key)
                    if colored is None:
                        colored = self._tint_yinyang(filled_art, hp_color)
                        self.hp_tint_cache[cache_key] = colored
                    art = colored
                jade = self._scaled(
                    f"hp-yinyang:{color_key if filled else 'empty'}",
                    art, 22, 22
                )
                self.screen.blit(jade, (x+w-29, center_y-11))
            else:
                draw_jade(
                    self.screen, x+w-18, center_y,
                    filled=filled, color=hp_color
                )

    def _tint_yinyang(self, source, color):
        """只替换素材中的彩色玉身，保留黑白阴阳细节和透明边缘。"""
        result = source.copy()
        result.lock()
        try:
            for px in range(result.get_width()):
                for py in range(result.get_height()):
                    red, green, blue, alpha = source.get_at((px, py))
                    if alpha == 0:
                        continue
                    spread = max(red, green, blue) - min(red, green, blue)
                    # 黑、白、灰属于阴阳纹理和高光，不参与换色。
                    if spread < 24:
                        continue
                    luminance = (red*30 + green*59 + blue*11) / 100
                    factor = max(0.48, min(1.18, 0.48 + luminance/330))
                    result.set_at(
                        (px, py),
                        (
                            min(255, round(color[0]*factor)),
                            min(255, round(color[1]*factor)),
                            min(255, round(color[2]*factor)),
                            alpha,
                        )
                    )
        finally:
            result.unlock()
        return result

    def _draw_chain_overlay(self, player, x, y, w, h):
        """将横置标记覆盖在武将牌正中央。"""
        if not player.chained:
            return
        art = self.ui_images.get("chain")
        if art:
            chain_w = w
            chain_h = max(14, round(chain_w * art.get_height() / art.get_width()))
            chain = self._scaled("ui:chain", art, chain_w, chain_h)
            self.screen.blit(
                chain,
                (x, y + (h-chain_h)//2),
            )
        else:
            self.drw(
                "⛓ 横置", "s", x+w//2, y+h//2,
                C_GOLD_LIGHT, center=True
            )

    def _draw_state_frame(self, player, x, y, w, h, local_player=None):
        """按结算状态覆盖端游状态边框；优先级从濒死到普通行动。"""
        frame_name = None
        if self.dying_target is player:
            frame_name = "sos"
        elif self._is_selected_target(player):
            frame_name = "dashboardSelected" if player is local_player else "photoSelected"
        elif self.wd and self.dt is player:
            frame_name = "responding"
        elif self.wd and self.da is player:
            frame_name = "responsing"
        elif self.engine and self.engine.get_current_player() is player:
            frame_name = "playing"
        art = self.frame_images.get(frame_name)
        if art:
            frame_rect = self._general_state_frame_rect(x, y, w, h)
            frame = self._scaled(
                f"frame:{frame_name}",
                art,
                frame_rect.w,
                frame_rect.h,
            )
            self.screen.blit(frame, frame_rect.topleft)

    @staticmethod
    def _general_state_frame_rect(x, y, w, h):
        """所有武将状态框统一向外扩张，避免内沿遮挡牌面文字。"""
        return pygame.Rect(x, y, w, h).inflate(
            GENERAL_STATE_FRAME_OUTSET * 2,
            GENERAL_STATE_FRAME_OUTSET * 2,
        )

    def _is_selected_target(self, player):
        """主动出牌与通用技能选择共用同一种目标边框。"""
        return bool(
            player in self.pending_targets
            or self.pending_target is player
            or getattr(self, "skill_prompt_selected_target", None) is player
        )

    def _draw_dying_or_death_marker(self, player, x, y, w, h):
        """在武将牌上展示濒死求救或对应势力的阵亡标识。"""
        if self.dying_target is player and player.alive:
            art = self.death_images.get("save-me")
            if art:
                marker_w = min(w - 12, art.get_width())
                marker_h = max(
                    1, round(marker_w * art.get_height() / art.get_width())
                )
                marker = self._scaled(
                    f"death:save-me:{marker_w}", art, marker_w, marker_h
                )
                self.screen.blit(
                    marker,
                    marker.get_rect(center=(x + w // 2, y + h // 2)),
                )
            return
        if player.alive:
            return
        key = {
            "魏": "wei", "蜀": "shu", "吴": "wu", "群": "qun",
            "野心家": "careerist",
        }.get(player.general.kingdom)
        art = self.death_images.get(key)
        if not art:
            self.drw(
                "阵 亡", "b", x + w // 2, y + h // 2,
                C_RED_LIGHT, center=True,
            )
            return
        marker_w = min(w - 16, art.get_width())
        marker_h = min(
            h - 16,
            max(1, round(marker_w * art.get_height() / art.get_width())),
        )
        marker = self._scaled(
            f"death:{key}:{marker_w}:{marker_h}",
            art, marker_w, marker_h,
        )
        self.screen.blit(
            marker,
            marker.get_rect(center=(x + w // 2, y + h // 2)),
        )

    def clear_selection(self):
        self.idx = None
        self.pending_target = None
        self.pending_targets = []
        self.pending_skill_action = None
        self.discard_selected.clear()
        self.clear_hint()

    def msg(self, s):
        """写入右侧牌局记录；只记录已经发生的牌局事件。"""
        self.logs.append(s)
        if len(self.logs) > 200: self.logs = self.logs[-100:]

    def play_card_sound(self, player, card_name, card=None):
        sound = getattr(self, "sound", None)
        if sound and player:
            sound.play_card(card_name, player.general.gender)
        card_effects = {
            "火杀": "fire_slash",
            "雷杀": "thunder_slash",
            "闪": "jink",
            "桃": "peach",
            "酒": "analeptic",
            "决斗": "duel",
        }
        if card_name == "杀":
            effect = (
                "slash_red"
                if card is not None and card.suit in ("heart", "diamond")
                else "slash_black"
            )
        else:
            effect = card_effects.get(card_name)
        if effect:
            self._play_visual_effect(effect, player)

    def _announce_skill_use(
        self, player, skill_name, now=None
    ):
        """后发动的技能直接覆盖当前提示并重新开始计时。"""
        if player is None or not skill_name:
            return
        self.skill_notice = {
            "text": (
                f"【{player.general.name}】使用了技能"
                f"【{skill_name}】"
            ),
            "start": (
                pygame.time.get_ticks() if now is None else now
            ),
        }

    def _skill_notice_alpha(self, now=None):
        notice = getattr(self, "skill_notice", None)
        if not notice:
            return 0
        now = pygame.time.get_ticks() if now is None else now
        elapsed = now - notice["start"]
        if elapsed < 0:
            return 0
        if elapsed <= SKILL_NOTICE_HOLD_MS:
            return 255
        fade_elapsed = elapsed - SKILL_NOTICE_HOLD_MS
        if fade_elapsed >= SKILL_NOTICE_FADE_MS:
            self.skill_notice = None
            return 0
        return max(
            0,
            round(
                255 * (
                    1 - fade_elapsed / SKILL_NOTICE_FADE_MS
                )
            ),
        )

    def _draw_skill_notice(self):
        """在等待区上方绘制独立黄字，不占用普通操作提示。"""
        alpha = self._skill_notice_alpha()
        notice = getattr(self, "skill_notice", None)
        if alpha <= 0 or not notice:
            return
        font = self.f["b"]
        text_surface = font.render(
            notice["text"], True, C_GOLD_LIGHT
        )
        shadow = font.render(
            notice["text"], True, (30, 20, 8)
        )
        text_surface.set_alpha(alpha)
        shadow.set_alpha(alpha)
        center = (TABLE_CX, WAIT_AREA_Y - 30)
        self.screen.blit(
            shadow,
            shadow.get_rect(
                center=(center[0] + 2, center[1] + 2)
            ),
        )
        self.screen.blit(
            text_surface,
            text_surface.get_rect(center=center),
        )

    def play_equipment_sound(
        self, equipment_name, player=None, visual=True,
    ):
        sound = getattr(self, "sound", None)
        if sound:
            sound.play_equipment(equipment_name)
        equipment_effects = {
            "八卦阵": "armor/eight_diagram",
            "仁王盾": "armor/renwang_shield",
            "白银狮子": "armor/silver_lion",
            "藤甲": "armor/vine",
            "藤甲燃烧": "armor/vineburn",
            "贯石斧": "weapon/axe",
            "青龙偃月刀": "weapon/blade",
            "诸葛连弩": "weapon/crossbow",
            "雌雄双股剑": "weapon/double_sword",
            "朱雀羽扇": "weapon/fan",
            "古锭刀": "weapon/guding_blade",
            "方天画戟": "weapon/halberd",
            "寒冰剑": "weapon/ice_sword",
            "麒麟弓": "weapon/kylin_bow",
            "青釭剑": "weapon/qinggang_sword",
            "丈八蛇矛": "weapon/spear",
        }
        effect = equipment_effects.get(equipment_name)
        if effect and visual:
            if player is None and getattr(self, "engine", None):
                player = self.engine.get_current_player()
            self._play_visual_effect(effect, player)

    def _on_engine_skill_application(self, player, application):
        """接收核心规则确认已生效的装备技能，并统一展示声音和动画。"""
        skill = getattr(application, "skill", None)
        if skill and getattr(skill, "source_name", None):
            self.play_equipment_sound(skill.source_name, player)

    def play_equip_action_sound(self, equipment_type):
        sound = getattr(self, "sound", None)
        if sound:
            sound.play_equip_action(equipment_type)

    def play_system_sound(self, event, volume=None):
        sound = getattr(self, "sound", None)
        if sound:
            sound.play_system(event, volume=volume)

    def play_skill_sound(self, player, skill_id):
        """只在技能已经合法提交并进入结算后播放对应技能语音。"""
        sound = getattr(self, "sound", None)
        if sound and player:
            sound.play_skill(
                player.general.id, player.skin_id, skill_id
            )
        engine = getattr(self, "engine", None)
        definition = (
            engine.skills.skill_definition(skill_id)
            if engine is not None else None
        )
        if player is not None and definition is not None:
            self._announce_skill_use(player, definition.name)

    def play_general_death_sound(self, player):
        """在死亡规则事件已经成立后，按稳定武将 ID 播放阵亡语音。"""
        sound = getattr(self, "sound", None)
        if sound and player:
            sound.play_death(player.general.id, player.skin_id)

    def _load_effect_surface(self, path):
        surface = self.effect_surface_cache.get(path)
        if surface is None:
            surface = self._load_surface(path)
            if surface:
                self.effect_surface_cache[path] = surface
        return surface

    def _play_visual_effect(self, effect_key, player=None, position=None):
        """播放非阻塞逐帧展示；素材缺失时静默跳过。"""
        frame_paths = getattr(self, "effect_frame_paths", {}).get(effect_key)
        if not frame_paths:
            return
        if position is None:
            position = (
                self._player_center(player)
                if player is not None
                else (TABLE_CX, TABLE_CY)
            )
        self.visual_effects.append({
            "key": effect_key,
            "frames": frame_paths,
            "position": position,
            "start": pygame.time.get_ticks(),
            "frame_ms": 55,
        })

    def _waiting_card_position(self, card):
        item = next(
            (
                item for item in getattr(self, "waiting_cards", [])
                if item["card"] is card
            ),
            None,
        )
        return (
            item["pos"]
            if item else (TABLE_CX, WAIT_AREA_Y + WAIT_AREA_H//2)
        )

    def _draw_visual_effects(self):
        now = pygame.time.get_ticks()
        active = []
        for effect in self.visual_effects:
            index = (now - effect["start"]) // effect["frame_ms"]
            if index < 0 or index >= len(effect["frames"]):
                continue
            surface = self._load_effect_surface(effect["frames"][index])
            if surface:
                self.screen.blit(
                    surface,
                    surface.get_rect(center=effect["position"])
                )
            active.append(effect)
        self.visual_effects = active

    def hint(self, text, duration=3000):
        """显示临时操作提示，不写入右侧牌局记录。"""
        self.hint_text = text
        self.hint_until = pygame.time.get_ticks() + duration

    def clear_hint(self):
        self.hint_text = ""
        self.hint_until = 0

    def _schedule_ai_action(self):
        self.ai_next_action_at = pygame.time.get_ticks() + AI_DELAY_MS

    def _start_ai_turn(self):
        self.ai_busy = True
        self.ai_step = 0
        self._schedule_ai_action()

    def _start_player_draw_timer(self):
        self.player_draw_at = pygame.time.get_ticks() + AUTO_DRAW_DELAY_MS

    def _phase_label(self, p=None):
        if not self.engine:
            return ""
        if not self.first_turn_started:
            return "游戏准备"
        if p is None:
            p = self.engine.get_current_player()
        names = {
            Phase.PREPARE: "准备阶段",
            Phase.JUDGE: "判定阶段",
            Phase.DRAW: "摸牌阶段",
            Phase.PLAY: "出牌阶段",
            Phase.DISCARD: "弃牌阶段",
            Phase.END: "结束阶段",
        }
        return f"{p.general.name}：{names.get(self.engine.state.phase, self.engine.state.phase.value)}"

    def _draw_phase_indicator(self, current_player, local_player):
        """用小型阶段图标指示当前阶段，不承担文字提示。"""
        if (
            not self.first_turn_started
            or not current_player
            or self.judgment_result_tip
        ):
            return
        phase_names = {
            Phase.PREPARE: "round_start",
            Phase.JUDGE: "judge",
            Phase.DRAW: "draw",
            Phase.PLAY: "play",
            Phase.DISCARD: "discard",
            Phase.END: "finish",
        }
        phase_key = phase_names.get(self.engine.state.phase)
        phase_art = self.phase_images.get(phase_key)
        if not phase_art:
            return
        is_local_turn = bool(
            local_player and current_player.seat == local_player.seat
        )
        icon_w = 150 if is_local_turn else 105
        icon_h = max(
            10,
            round(icon_w * phase_art.get_height() / phase_art.get_width()),
        )
        icon = self._scaled(
            f"phase-indicator:{phase_key}:{icon_w}",
            phase_art,
            icon_w,
            icon_h,
        )
        if is_local_turn:
            center = (TABLE_CX, BOTTOM_BAR_Y + 5 + icon_h//2)
        else:
            center = (
                ENEMY_X + ENEMY_W//2,
                ENEMY_Y + ENEMY_H + 1 + icon_h//2,
            )
        self.screen.blit(icon, icon.get_rect(center=center))

    def drw(self, t, k, x, y, c=C_W, center=False, right=False):
        img = self.f[k].render(t, True, c)
        r = img.get_rect()
        if center: r.center = (x, y)
        elif right: r.topright = (x, y)
        else: r.topleft = (x, y)
        self.screen.blit(img, r)

    def draw_background(self):
        """绘制接近端游的牌桌背景"""
        draw_vertical_gradient(self.screen, (0, 0, W, H), (37, 31, 25), (21, 18, 15))

        table = pygame.Rect(TABLE_L, TABLE_T, TABLE_R-TABLE_L, TABLE_B-TABLE_T)
        draw_vertical_gradient(self.screen, table, (126, 105, 78), (88, 70, 50))
        table_art = self.ui_images.get("table_background")
        if table_art:
            self.screen.blit(
                self._scaled(
                    "ui:table_background", table_art, table.w, table.h
                ),
                table.topleft
            )

        # 中央圆形纹理，模拟牌桌压纹。
        cx, cy = TABLE_CX, TABLE_CY + 10
        for r, a in [(410, 32), (315, 24), (210, 18)]:
            pygame.draw.circle(self.screen, (222, 196, 146, a), (cx, cy), r, 2)
        for i in range(16):
            ang = i * math.pi / 8
            x1 = cx + math.cos(ang) * 90
            y1 = cy + math.sin(ang) * 70
            x2 = cx + math.cos(ang) * 390
            y2 = cy + math.sin(ang) * 300
            pygame.draw.line(self.screen, (55, 43, 32, 40), (x1, y1), (x2, y2), 1)

        # 桌面暗角与轻微高光
        shade = pygame.Surface((TABLE_R, TABLE_B-TOP_BAR_H), pygame.SRCALPHA)
        pygame.draw.ellipse(shade, (210, 178, 118, 22), (-140, 70, TABLE_R+280, TABLE_B-160))
        pygame.draw.rect(shade, (0, 0, 0, 28), (0, 0, TABLE_R, 58))
        pygame.draw.rect(shade, (0, 0, 0, 34), (0, TABLE_B-TOP_BAR_H-86, TABLE_R, 86))
        self.screen.blit(shade, (0, TOP_BAR_H))

        # 底部手牌托盘
        bottom = pygame.Rect(0, BOTTOM_BAR_Y, TABLE_R, BOTTOM_BAR_H)
        draw_vertical_gradient(self.screen, bottom, (58, 41, 25), (22, 18, 15))
        pygame.draw.line(self.screen, (246, 202, 44), (0, BOTTOM_BAR_Y), (TABLE_R, BOTTOM_BAR_Y), 3)
        pygame.draw.line(self.screen, (156, 45, 24), (180, BOTTOM_BAR_Y+5), (930, BOTTOM_BAR_Y+5), 8)

    # ===== 卡牌绘制 =====
    def _draw_card_corner_marks(self, card, x, y, w, h):
        """按卡牌实例覆盖左上角点数和花色。"""
        rank_map = {"A": "1", "J": "11", "Q": "12", "K": "13"}
        rank_key = rank_map.get(str(card.rank).upper(), str(card.rank))
        color_key = "red" if card.suit in ("heart", "diamond") else "black"
        rank_art = self.rank_images.get(color_key, {}).get(rank_key)
        suit_art = self.card_suit_images.get(card.suit)
        scale_x, scale_y = w / 93, h / 130
        if rank_art:
            rank_w = max(15, round(27 * scale_x))
            rank_h = max(16, round(28 * scale_y))
            rank_image = self._scaled(
                f"rank:{color_key}:{rank_key}", rank_art, rank_w, rank_h
            )
            self.screen.blit(rank_image, (x+max(1, round(2*scale_x)), y+1))
        else:
            display_rank = {"1": "A", "11": "J", "12": "Q", "13": "K"}.get(
                rank_key, rank_key
            )
            self.drw(
                display_rank, "b", x+max(5, round(9*scale_x)), y+3,
                SC.get(card.suit, (20,20,20))
            )
        if suit_art:
            suit_w = max(12, round(21 * scale_x))
            suit_h = max(10, round(17 * scale_y))
            suit_image = self._scaled(
                f"corner-suit:{card.suit}", suit_art, suit_w, suit_h
            )
            self.screen.blit(
                suit_image,
                (x+max(2, round(5*scale_x)), y+max(18, round(27*scale_y)))
            )
        else:
            self.drw(
                SS.get(card.suit, "?"), "b",
                x+max(5, round(9*scale_x)), y+max(22, round(29*scale_y)),
                SC.get(card.suit, (20,20,20))
            )

    def dc(self, card, x, y, w=CARD_W, h=CARD_H, up=True, sel=False, hl=False):
        rect = (x, y, w, h)
        # 选中/高亮效果
        if sel:
            glow_surf = pygame.Surface((w+16, h+16), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (*C_GOLD_LIGHT, 100), (0,0,w+16,h+16), border_radius=10)
            self.screen.blit(glow_surf, (x-8, y-18))
        if hl:
            glow_surf = pygame.Surface((w+12, h+12), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (*C_GREEN_LIGHT, 120), (0,0,w+12,h+12), border_radius=10)
            self.screen.blit(glow_surf, (x-6, y-6))
        if not up:
            card_back = self.ui_images.get("card_back")
            if card_back:
                self.screen.blit(self._scaled("ui:card_back", card_back, w, h), (x, y))
                return
            # 牌背 - 古风红色
            draw_rounded_rect(self.screen, (120, 30, 30), rect, radius=8)
            draw_rounded_rect(self.screen, (150, 40, 40), (x+4,y+4,w-8,h-8), radius=6)
            # 牌背图案 - 菱形花纹
            cx, cy = x+w//2, y+h//2
            pygame.draw.polygon(self.screen, C_GOLD, [
                (cx, cy-30), (cx+25, cy), (cx, cy+30), (cx-25, cy)
            ], 2)
            self.drw("杀", "b", cx, cy, C_GOLD, center=True)
            return
        card_art = self.card_images.get(card.name)
        if card_art:
            self.screen.blit(self._scaled(f"card:{card.name}", card_art, w, h), (x, y))
            self._draw_card_corner_marks(card, x, y, w, h)
            return
        # 牌面
        draw_rounded_rect(self.screen, C_CD, rect, radius=8)
        draw_rounded_rect(self.screen, C_CD_BORDER, rect, radius=8, border=2)
        draw_rounded_rect(self.screen, (235, 225, 205), (x+3,y+3,w-6,h-6), radius=6)
        sc = SC.get(card.suit,(20,20,20))
        # 卡牌名称 - 中央
        name_color = sc if card.name in ("杀", "闪", "桃", "酒") else (40,40,40)
        self.drw(card.name, "card_name", x+w//2, y+h//2-15, name_color, center=True)
        # 锦囊牌标记
        if card.kind == CardKind.TRICK:
            pygame.draw.rect(self.screen, (180, 140, 60), (x+w//2-20, y+h//2+10, 40, 20), border_radius=3)
            self.drw("锦囊", "ts", x+w//2, y+h//2+20, C_W, center=True)
        self._draw_card_corner_marks(card, x, y, w, h)

    def _draw_disabled_card(self, rect):
        shade = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        shade.fill((38, 38, 38, 168))
        self.screen.blit(shade, rect.topleft)
        pygame.draw.rect(self.screen, (91,91,91), rect, 2, border_radius=8)

    def _draw_disabled_player(self, x, y, w, h, text="超出攻击范围"):
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        shade.fill((35,35,35,158))
        self.screen.blit(shade, (x,y))
        self.drw(text, "s", x+w//2, y+h//2, (175,175,175), center=True)

    # ===== 武将牌绘制 =====
    def _general_skin_art(self, general, skin_id="default"):
        """读取武将皮肤牌面；现有按中文名保存的素材视为 default。"""
        keyed_art = self.general_images.get((general.id, skin_id))
        if keyed_art is not None:
            return keyed_art
        if skin_id == general.default_skin_id:
            return self.general_images.get(general.name)
        return None

    @staticmethod
    def _general_hand_text(player, hand_limit):
        """武将牌底部只显示手牌数，不把姓名混进手牌信息。"""
        return f"{len(player.hand)}/{hand_limit}"

    def _draw_outlined_text(
        self, text, font_key, center, color, outline=(18, 14, 12)
    ):
        """在复杂皮肤上绘制清晰的描边文字。"""
        font = self.f[font_key]
        outline_image = font.render(text, True, outline)
        for offset_x, offset_y in (
            (-2, 0), (2, 0), (0, -2), (0, 2),
            (-1, -1), (1, -1), (-1, 1), (1, 1),
        ):
            self.screen.blit(
                outline_image,
                outline_image.get_rect(
                    center=(center[0] + offset_x, center[1] + offset_y)
                ),
            )
        image = font.render(text, True, color)
        self.screen.blit(image, image.get_rect(center=center))

    def _general_frame_for(self, general):
        """按稳定 general_id 读取专用边框；旧武将可由数据显式关闭。"""
        if not general.use_portrait_frame:
            return None
        return self.general_frame_images.get(general.id)

    def _draw_general_frame(self, general, x, y, w, h):
        """在皮肤之上叠加已经包含势力字和竖排姓名的透明边框。"""
        frame = self._general_frame_for(general)
        if frame is None:
            return False
        self.screen.blit(
            self._scaled(
                f"general-frame:{general.id}", frame, w, h
            ),
            (x, y),
        )
        return True

    def draw_general_card(self, p, x, y, w, h, is_enemy=False):
        """绘制武将牌 - 参考端游卡框"""
        hand_limit = (
            self.engine.hand_limit(p) if self.engine else max(0, p.hp)
        )
        hand_numbers = self._general_hand_text(p, hand_limit)
        general_art = self._general_skin_art(
            p.general, p.skin_id
        )
        if general_art:
            shadow = pygame.Surface((w+8, h+8), pygame.SRCALPHA)
            pygame.draw.rect(shadow, (0,0,0,145), (4,4,w,h), border_radius=6)
            self.screen.blit(shadow, (x-4, y-4))
            self.screen.blit(
                self._scaled_cover(
                    f"general:{p.general.id}:{p.skin_id}",
                    general_art,
                    w,
                    h,
                ),
                (x, y),
            )
            uses_frame = self._draw_general_frame(
                p.general, x, y, w, h
            )
            if is_enemy:
                if not uses_frame:
                    pygame.draw.rect(
                        self.screen, (205, 185, 144),
                        (x+2, y+2, w-4, h-4),
                        2, border_radius=5
                    )
                self._draw_enemy_hand_count(
                    p.general, hand_numbers, x, y, w, h
                )
            elif uses_frame:
                self._draw_outlined_text(
                    hand_numbers, "s",
                    (x+w//2, y+h-24), C_GOLD_LIGHT
                )
            else:
                pygame.draw.rect(
                    self.screen, (205, 185, 144),
                    (x+2, y+2, w-4, h-4), 2, border_radius=5
                )
                info = pygame.Surface((w-16, 42), pygame.SRCALPHA)
                pygame.draw.rect(
                    info, (0, 0, 0, 118), info.get_rect(),
                    border_radius=5
                )
                self.screen.blit(info, (x+8, y+h-50))
                self.drw(
                    hand_numbers, "s",
                    x+w//2, y+h-35, C_GOLD_LIGHT, center=True
                )
            hp_panel = pygame.Surface((28, min(112, h-20)), pygame.SRCALPHA)
            pygame.draw.rect(
                hp_panel, (12, 10, 9, 176), hp_panel.get_rect(),
                border_radius=10
            )
            self.screen.blit(hp_panel, (x+w-32, y+h-hp_panel.get_height()-10))
            self._draw_hp_jades(p, x, y, w, h)
            if p.drunk:
                self._draw_drunk_effect(x, y, w, h)
            self._draw_chain_overlay(p, x, y, w, h)
            if not p.alive:
                s=pygame.Surface((w,h),pygame.SRCALPHA)
                s.fill((0,0,0,160))
                self.screen.blit(s,(x,y))
            self._draw_dying_or_death_marker(p, x, y, w, h)
            return

        shadow = pygame.Surface((w+8, h+8), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0,0,0,145), (4,4,w,h), border_radius=6)
        self.screen.blit(shadow, (x-4, y-4))

        frame = self._general_frame_for(p.general)
        kc = KC.get(p.general.kingdom, C_W)
        kc_light = KC_LIGHT.get(p.general.kingdom, C_W)
        pygame.draw.rect(self.screen, (9, 8, 8), (x, y, w, h), border_radius=5)
        if frame is None:
            pygame.draw.rect(
                self.screen, (205, 185, 144),
                (x+2, y+2, w-4, h-4), 2, border_radius=5
            )
            pygame.draw.rect(
                self.screen, kc, (x+7, y+7, 34, h-14),
                border_radius=3
            )
            draw_vertical_gradient(
                self.screen, (x+42, y+7, w-49, h-14),
                (84, 67, 49), (31, 26, 22)
            )
            self.drw(
                p.general.kingdom, "n", x+24, y+34,
                (255, 244, 191), center=True
            )
            self.drw(
                "势", "s", x+24, y+68,
                (255, 244, 191), center=True
            )
            av_x, av_y = x+48, y+14
            av_w, av_h = w-60, h-86
        else:
            draw_vertical_gradient(
                self.screen, (x+7, y+7, w-14, h-14),
                kc_light, (31, 26, 22)
            )
            av_x, av_y = x+14, y+14
            av_w, av_h = w-28, h-56

        # 头像区域
        draw_vertical_gradient(self.screen, (av_x, av_y, av_w, av_h), kc_light, (44, 34, 30))
        pygame.draw.rect(self.screen, (18, 15, 14), (av_x, av_y, av_w, av_h), 2)
        for yy in range(0, av_h, 9):
            pygame.draw.line(self.screen, (255, 255, 255, 18), (av_x, av_y+yy), (av_x+av_w, av_y+yy), 1)
        name_char = p.general.name[0] if len(p.general.name) > 0 else "?"
        self.drw(name_char, "t", av_x+av_w//2, av_y+av_h//2-12, (255, 238, 170), center=True)

        if frame is not None:
            self._draw_general_frame(p.general, x, y, w, h)
            if is_enemy:
                self._draw_enemy_hand_count(
                    p.general, hand_numbers, x, y, w, h
                )
            else:
                self._draw_outlined_text(
                    hand_numbers, "n",
                    (x+w//2, y+h-24), C_GOLD_LIGHT
                )
        elif is_enemy:
            self._draw_enemy_hand_count(
                p.general, hand_numbers, x, y, w, h
            )
        else:
            name_rect = (x+46, y+h-66, w-58, 34)
            draw_vertical_gradient(
                self.screen, name_rect,
                (42, 37, 34), (13, 12, 12)
            )
            pygame.draw.rect(
                self.screen, (205, 185, 144), name_rect, 1
            )
            self.drw(
                hand_numbers, "n",
                x+w//2+12, y+h-53,
                C_GOLD_LIGHT, center=True
            )

        # 体力勾玉沿右边排列
        self._draw_hp_jades(p, x, y, w, h)

        if p.drunk:
            self._draw_drunk_effect(x, y, w, h)
        self._draw_chain_overlay(p, x, y, w, h)

        if not p.alive:
            s=pygame.Surface((w,h),pygame.SRCALPHA)
            s.fill((0,0,0,180))
            self.screen.blit(s,(x,y))
        self._draw_dying_or_death_marker(p, x, y, w, h)

    def _enemy_hand_count_center(self, general, x, y, w, h):
        """按姓名栏类型返回敌方手牌数字的中心点。"""
        if self._general_frame_for(general) is not None:
            return (
                x + round(w * 0.075),
                y + round(h * 0.52),
            )
        return (
            x + round(w * 0.145),
            y + round(h * 0.63),
        )

    def _draw_enemy_hand_count(
        self, general, hand_numbers, x, y, w, h
    ):
        """将敌方手牌数放在原画左侧竖排姓名下方。"""
        self._draw_outlined_text(
            hand_numbers,
            "ts",
            self._enemy_hand_count_center(
                general, x, y, w, h
            ),
            C_GOLD_LIGHT,
        )

    @staticmethod
    def _enemy_equipment_panel_rect(x, y, w, h):
        """敌方装备栏贴住牌面内侧，并避开左右装饰与体力勾玉。"""
        panel_h = 4 * ENEMY_EQUIPMENT_ROW_H + 10
        return pygame.Rect(
            x + ENEMY_EQUIPMENT_LEFT_INSET,
            y + h - panel_h - ENEMY_EQUIPMENT_BOTTOM_INSET,
            (
                w
                - ENEMY_EQUIPMENT_LEFT_INSET
                - ENEMY_EQUIPMENT_RIGHT_INSET
            ),
            panel_h,
        )

    def _draw_enemy_equipment(self, p, x, y, w, h):
        """按武器、防具、进攻马、防御马四个固定槽展示敌方装备。"""
        slots = (
            ("weapon", "武器"),
            ("armor", "防具"),
            ("offensive_mount", "进攻马"),
            ("defensive_mount", "防御马"),
        )
        row_h = ENEMY_EQUIPMENT_ROW_H
        panel_rect = self._enemy_equipment_panel_rect(
            x, y, w, h
        )
        panel_w, panel_h = panel_rect.size
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (12, 10, 9, 205), panel.get_rect(), border_radius=6)
        pygame.draw.rect(panel, (*C_GOLD_DARK, 220), panel.get_rect(), 1, border_radius=6)
        panel_x, panel_y = panel_rect.topleft
        self.screen.blit(panel, panel_rect.topleft)
        for i, (equipment_type, slot_name) in enumerate(slots):
            row_y = panel_y + 6 + i * row_h
            card = next(
                (
                    item for item in p.equipment
                    if item.equipment_type == equipment_type
                    and self._card_token(item)
                    not in self.hidden_equipment_cards
                ),
                None,
            )
            if card is None:
                self.drw(slot_name, "ts", panel_x + 9, row_y, C_GY)
                continue
            art = self.equipment_images.get(card.name)
            if art:
                icon_w = min(panel_w-14, 145)
                icon_h = min(
                    row_h,
                    max(12, round(icon_w * art.get_height() / art.get_width()))
                )
                icon = self._scaled(
                    f"equip-enemy:{card.name}", art, icon_w, icon_h
                )
                self.screen.blit(icon, (panel_x+7, row_y+(row_h-icon_h)//2))
            else:
                self.drw(slot_name, "ts", panel_x + 9, row_y, C_GY)
                self.drw(card.name, "ts", panel_x + 55, row_y, C_GOLD_LIGHT)

    def _draw_drunk_effect(self, x, y, w, h):
        """饮酒状态：让武将牌持续泛红，直到酒效消失。"""
        tint = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(tint, (190, 20, 12, 62), tint.get_rect(), border_radius=6)
        self.screen.blit(tint, (x, y))
        pygame.draw.rect(self.screen, (245, 62, 42), (x-2, y-2, w+4, h+4), 3, border_radius=8)

    def _judgment_icon_rects(
        self, p, x, y, w, h, *, include_hidden=False
    ):
        """返回紧贴武将牌下沿的判定标志位置，供绘制和移动动画共用。"""
        cards = list(reversed(p.judgment_area))
        if not include_hidden:
            cards = [
                card for card in cards
                if self._card_token(card)
                not in self.hidden_judgment_cards
            ]
        if not cards:
            return []
        total_w = (
            len(cards) * JUDGMENT_ICON_SIZE
            + max(0, len(cards) - 1) * JUDGMENT_ICON_GAP
        )
        row_x = x + (w - total_w) // 2
        # 通常位于牌框下方；本地武将贴近屏幕底部时自动贴住下沿，
        # 仍不再占用一整块独立判定区。
        row_y = min(
            y + h + 4,
            H - JUDGMENT_ICON_SIZE - 4,
        )
        return [
            (
                card,
                pygame.Rect(
                    row_x + index * (
                        JUDGMENT_ICON_SIZE + JUDGMENT_ICON_GAP
                    ),
                    row_y,
                    JUDGMENT_ICON_SIZE,
                    JUDGMENT_ICON_SIZE,
                ),
            )
            for index, card in enumerate(cards)
        ]

    def _draw_judgment_icons(self, p, x, y, w, h):
        """只显示延时锦囊小标志，不再绘制独立判定区面板。"""
        icon_keys = {
            "乐不思蜀": "indulgence",
            "兵粮寸断": "supply_shortage",
            "闪电": "lightning",
        }
        for card, rect in self._judgment_icon_rects(
            p, x, y, w, h
        ):
            key = icon_keys.get(card.name)
            art = self.judgment_icon_images.get(key)
            if art:
                icon = self._scaled(
                    f"judgment-icon:{key}",
                    art,
                    rect.w,
                    rect.h,
                )
                self.screen.blit(icon, rect.topleft)
                continue
            # 未来新增延时锦囊缺少素材时仍保留紧凑占位，不恢复大面板。
            pygame.draw.circle(
                self.screen,
                (35, 30, 24),
                rect.center,
                rect.w // 2,
            )
            pygame.draw.circle(
                self.screen,
                C_GOLD_DARK,
                rect.center,
                rect.w // 2,
                1,
            )
            self.drw(
                card.name[:1],
                "ts",
                rect.centerx,
                rect.centery,
                C_GOLD_LIGHT,
                center=True,
            )

    def _skill_button_rect(self, p, x, y, index, is_left=True):
        """武将技能按钮的稳定命中区域。"""
        width, height = 59, 26
        tx = x - 79 if is_left else x - 69
        return pygame.Rect(tx, y + 52 + index * 40, width, height)

    @staticmethod
    def _skill_button_asset_type(definition):
        """技能性质只决定按钮外观；交互性仍由当前合法动作单独判断。"""
        if definition is not None:
            if (
                definition.kind == SkillKind.LOCKED
                or definition.mandatory
            ):
                return "compulsory"
            if definition.kind == SkillKind.LIMITED:
                return "oneoff"
        return "proactive"

    def draw_skills(self, p, x, y, is_left=True):
        """按技能是否需要自主操作绘制对应类型的技能按钮。"""
        for i, sk in enumerate(p.general.skills):
            rect = self._skill_button_rect(p, x, y, i, is_left)
            self.skill_button_rects[(p.seat, sk.skill_id)] = rect
            definition = self.engine.skills.skill_definition(
                sk.skill_id
            )
            response_option_ids = {
                option.skill.skill_id
                for option in self.engine.skills.response_conversion_options(
                    p, self.response_card_name
                )
            } if self.wd and self.dt is p else set()
            play_options = (
                (
                    self.engine.skills.play_conversion_options(p, "杀")
                    + self.engine.skills.active_play_conversion_options(
                        self.engine, p
                    )
                )
                if (
                    self.engine.state.phase == Phase.PLAY
                    and self.engine.get_current_player().seat == p.seat
                )
                else []
            )
            active_skill_actions = (
                self.engine.active_skill_actions(p)
                if (
                    self.engine.state.phase == Phase.PLAY
                    and self.engine.get_current_player().seat == p.seat
                )
                else []
            )
            playable_option_ids = {
                option.skill.skill_id
                for option in play_options
                if self.engine.skills.conversion_candidates(
                    p, option
                )
            }
            active_option_ids = {
                option.skill.skill_id
                for option in play_options
                if option.timing == SkillTiming.PLAY_CONVERSION
            }
            interactive = (
                not p.is_ai
                and (
                    (
                        sk.skill_id in playable_option_ids
                        and (
                            sk.skill_id in active_option_ids
                            or self.engine.can_use_slash(p)
                        )
                    )
                    or (
                        self.wd and self.dt is p
                        and sk.skill_id in response_option_ids
                        and not self.active_prompt
                    )
                    or any(
                        action.skill.skill_id == sk.skill_id
                        for action in active_skill_actions
                    )
                )
            )
            state = "disabled"
            if interactive:
                state = (
                    "hover" if rect.collidepoint(pygame.mouse.get_pos())
                    else "normal"
                )
            asset_type = self._skill_button_asset_type(definition)
            # 锁定技是常驻生效说明，不是一个“当前不可操作”的主动按钮。
            # 使用带锁标识的普通态素材，同时继续禁止点击。
            if asset_type == "compulsory":
                state = "normal"
            path = self.skill_icon_paths.get(
                f"{asset_type}/2-{state}"
            )
            art = self._load_surface(path) if path else None
            if art:
                self.screen.blit(
                    self._scaled(f"skill:{sk.skill_id}:{state}", art,
                                 rect.w, rect.h),
                    rect,
                )
            else:
                draw_rounded_rect(
                    self.screen, (77, 50, 30), rect, radius=3,
                    border=1, border_color=(130, 96, 55)
                )
            # 技能名使用深色描边和亮金白字，避免绿色按钮上白字失去边界。
            # 所有文字层都以按钮矩形中心定位，不能用手工基线偏移。
            font = self.f["h"]
            text_color = (
                (231, 231, 226)
                if asset_type == "compulsory"
                else (
                    (255, 246, 188)
                    if interactive else (210, 207, 196)
                )
            )
            text_center = (
                rect.centerx + (4 if asset_type == "compulsory" else 0),
                rect.centery,
            )
            outline = font.render(sk.name, True, (28, 20, 10))
            for ox, oy in (
                (-1, -1), (0, -1), (1, -1), (-1, 0),
                (1, 0), (-1, 1), (0, 1), (1, 1),
            ):
                self.screen.blit(
                    outline,
                    outline.get_rect(
                        center=(
                            text_center[0] + ox,
                            text_center[1] + oy,
                        )
                    ),
                )
            label = font.render(sk.name, True, text_color)
            self.screen.blit(
                label, label.get_rect(center=text_center)
            )

    @staticmethod
    def _should_draw_persistent_skills(player, local_player):
        """常驻技能按钮只属于本地玩家；敌方技能通过悬停说明查看。"""
        return bool(
            local_player
            and not player.is_ai
            and player.seat == local_player.seat
        )

    @staticmethod
    def _general_display_rect(player):
        if player.is_ai:
            return pygame.Rect(
                ENEMY_X, ENEMY_Y, ENEMY_W, ENEMY_H
            )
        return pygame.Rect(ME_X, ME_Y, ME_W, ME_H)

    def _general_at_position(self, position):
        """只在当前实际绘制的敌我武将牌区域中识别悬停对象。"""
        if not self.engine:
            return None
        displayed = (
            next(
                (
                    player for player in self.engine.state.players
                    if player.is_ai
                ),
                None,
            ),
            next(
                (
                    player for player in self.engine.state.players
                    if not player.is_ai
                ),
                None,
            ),
        )
        return next(
            (
                player for player in displayed
                if player is not None
                and self._general_display_rect(player).collidepoint(
                    position
                )
            ),
            None,
        )

    def _update_general_hover(self, position, now=None):
        """连续悬停满一秒才返回武将；移出后立即清空计时。"""
        now = pygame.time.get_ticks() if now is None else now
        player = self._general_at_position(position)
        if player is None:
            self.hover_general_seat = None
            self.hover_general_started_at = 0
            return None
        if getattr(self, "hover_general_seat", None) != player.seat:
            self.hover_general_seat = player.seat
            self.hover_general_started_at = now
            return None
        if (
            now - getattr(self, "hover_general_started_at", now)
            < GENERAL_TOOLTIP_HOVER_MS
        ):
            return None
        return player

    def _general_skill_details(self, player):
        """从统一技能定义读取悬停框所需的名称、类型和标准描述。"""
        details = []
        for reference in player.general.skills:
            definition = self.engine.skills.skill_definition(
                reference.skill_id
            )
            details.append({
                "name": reference.name,
                "type": (
                    "锁"
                    if definition and definition.mandatory
                    else "技"
                ),
                "description": (
                    definition.description
                    if definition and definition.description
                    else "暂无技能说明。"
                ),
            })
        return details

    @staticmethod
    def _wrap_general_tooltip_text(text, font, maximum_width):
        """按实际字体宽度逐字换行，兼容没有空格的中文规则文字。"""
        lines = []
        current = ""
        for character in text:
            if character == "\n":
                lines.append(current)
                current = ""
                continue
            candidate = current + character
            if current and font.size(candidate)[0] > maximum_width:
                lines.append(current)
                current = character
            else:
                current = candidate
        if current or not lines:
            lines.append(current)
        return lines

    def _draw_general_tooltip(self, player):
        """绘制参考端游样式的武将资料与技能说明浮层。"""
        if player is None:
            return
        panel_w = 500
        header_h = 62
        description_font = self.f["ts"]
        description_w = panel_w - 132
        skill_rows = []
        for detail in self._general_skill_details(player):
            lines = self._wrap_general_tooltip_text(
                detail["description"],
                description_font,
                description_w,
            )
            row_h = max(52, len(lines) * 22 + 16)
            skill_rows.append((detail, lines, row_h))
        if not skill_rows:
            skill_rows = [(
                {
                    "name": "无技能",
                    "type": "—",
                    "description": "该武将没有技能。",
                },
                ["该武将没有技能。"],
                52,
            )]
        panel_h = header_h + sum(
            row[2] for row in skill_rows
        ) + 14
        general_rect = self._general_display_rect(player)
        if general_rect.centerx < W // 2:
            panel_x = general_rect.right + 18
        else:
            panel_x = general_rect.left - panel_w - 18
        panel_x = max(12, min(W - panel_w - 12, panel_x))
        panel_y = max(
            TOP_BAR_H + 8,
            min(H - panel_h - 12, general_rect.top),
        )
        panel_rect = pygame.Rect(
            panel_x, panel_y, panel_w, panel_h
        )
        panel = pygame.Surface(
            (panel_w, panel_h), pygame.SRCALPHA
        )
        pygame.draw.rect(
            panel, (22, 18, 15, 238), panel.get_rect(),
            border_radius=7,
        )
        pygame.draw.rect(
            panel, (138, 111, 72, 235), panel.get_rect(),
            2, border_radius=7,
        )
        pygame.draw.rect(
            panel,
            (*KC.get(player.general.kingdom, C_GOLD_DARK), 235),
            (0, 0, 8, panel_h),
            border_radius=5,
        )
        self.screen.blit(panel, panel_rect.topleft)
        self.drw(
            player.general.name, "b",
            panel_x + 22, panel_y + 13,
            C_GOLD_LIGHT,
        )
        self.drw(
            f"{player.general.kingdom}  体力{player.general.hp}",
            "s", panel_x + 138, panel_y + 18, C_W,
        )
        pygame.draw.line(
            self.screen, (112, 91, 61),
            (panel_x + 16, panel_y + 50),
            (panel_x + panel_w - 16, panel_y + 50),
            1,
        )
        row_y = panel_y + header_h
        for detail, lines, row_h in skill_rows:
            skill_rect = pygame.Rect(
                panel_x + 18, row_y + 7, 78, 30
            )
            draw_vertical_gradient(
                self.screen, skill_rect,
                (72, 184, 91), (24, 94, 49),
            )
            pygame.draw.rect(
                self.screen, (158, 220, 145),
                skill_rect, 2, border_radius=4,
            )
            self.drw(
                detail["name"], "s",
                skill_rect.centerx, skill_rect.centery,
                (236, 255, 222), center=True,
            )
            type_rect = pygame.Rect(
                panel_x + 101, row_y + 10, 24, 24
            )
            pygame.draw.rect(
                self.screen, (111, 83, 45),
                type_rect, border_radius=3,
            )
            self.drw(
                detail["type"], "ts",
                type_rect.centerx, type_rect.centery,
                (255, 239, 179), center=True,
            )
            for index, line in enumerate(lines):
                self.drw(
                    line, "ts",
                    panel_x + 132,
                    row_y + 9 + index * 22,
                    C_W_DARK,
                )
            row_y += row_h

    def draw_target_highlight(self, x, y, w, h):
        rect = pygame.Rect(x-8, y-8, w+16, h+16)
        glow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(glow, (255, 216, 80, 90), (0, 0, rect.w, rect.h), border_radius=10)
        self.screen.blit(glow, rect.topleft)
        pygame.draw.rect(self.screen, C_GOLD_LIGHT, rect, 3, border_radius=10)

    def _player_center(self, p):
        return self._general_card_rect(p).center

    def _general_card_rect(self, p):
        """返回角色当前武将牌矩形；以后多人布局只需登记各座位矩形。"""
        seat = getattr(p, "seat", None)
        registered = getattr(
            self, "player_card_rects", {}
        ).get(seat)
        if registered is not None:
            return pygame.Rect(registered)
        return pygame.Rect(
            (
                ENEMY_X, ENEMY_Y, ENEMY_W, ENEMY_H
            )
            if p.is_ai
            else (ME_X, ME_Y, ME_W, ME_H)
        )

    def _arrow_target_center(self, p):
        """箭头指向本地玩家时落在手牌区中间底部。"""
        if p.is_ai:
            return self._player_center(p)
        hand_right = ME_X
        return (
            (HAND_LEFT_X + hand_right) // 2,
            HAND_Y + CARD_H,
        )

    def _hand_card_center(self, p, idx):
        if p.is_ai or idx is None or idx < 0:
            return self._player_center(p)
        rects = self.hrects(p)
        if idx >= len(rects):
            return self._player_center(p)
        return rects[idx].center

    def _equipment_card_center(self, p, idx):
        if p.is_ai:
            return (ENEMY_X + ENEMY_W//2, ENEMY_Y + ENEMY_H//2 + 16 + idx*20)
        eq_y, eq_h, gap = EQUIP_Y, 196, 8
        slot_h = (eq_h - gap * 5) // 4
        return (105, eq_y + gap + idx * (slot_h + gap) + slot_h // 2)

    def _owned_card_center(self, player, card):
        if card in player.hand:
            return self._hand_card_center(player, player.hand.index(card))
        if card in player.equipment:
            return self._equipment_card_center(
                player, player.equipment.index(card)
            )
        return self._player_center(player)

    def _judgment_card_center(self, p, card):
        general_rect = self._general_card_rect(p)
        x, y, w, h = general_rect
        rects = self._judgment_icon_rects(
            p, x, y, w, h, include_hidden=True
        )
        return next(
            (
                rect.center for candidate, rect in rects
                if candidate is card or candidate.id == card.id
            ),
            (x + w // 2, min(y + h + 18, H - 18)),
        )

    def _play_arrow_source(self, p):
        """出牌指示箭头的固定起点，不跟随具体手牌的位置。"""
        if p.is_ai:
            return self._player_center(p)
        return self._arrow_target_center(p)

    def _wait_slot_center(self, idx):
        columns = 6
        gap = 88
        x = WAIT_AREA_X + 60 + (idx % columns) * gap
        y = WAIT_AREA_Y + WAIT_AREA_H//2 + (idx // columns) * 18
        return (x, y)

    def _make_card_surface(self, card, w, h, alpha=255, face_up=True):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        old_screen = self.screen
        self.screen = surf
        self.dc(card, 0, 0, w, h, up=face_up)
        self.screen = old_screen
        surf.set_alpha(alpha)
        return surf

    def _ease_out_cubic(self, progress):
        return 1 - (1 - progress) ** 3

    def _start_hit_animation(self, player):
        self.hit_animations[player.seat] = pygame.time.get_ticks()

    def _general_hit_offset(self, player):
        started = self.hit_animations.get(player.seat)
        if started is None:
            return (0, 0)
        progress = (pygame.time.get_ticks() - started) / HIT_ANIM_MS
        if progress >= 1:
            self.hit_animations.pop(player.seat, None)
            return (0, 0)
        # 前半程向右下受击，后半程迅速复位。
        distance = int(HIT_OFFSET * math.sin(math.pi * max(0, progress)))
        return (distance, distance)

    def _apply_damage(self, player, amount=1, actor=None, source_card=None,
                      source_physical_cards=None,
                      on_complete=None, nature=DamageNature.NORMAL,
                      damage_event=None):
        """结算单次伤害；每个目标都独立经过装备/技能伤害修正入口。"""
        if damage_event is None:
            physical_cards = tuple(source_physical_cards or ())
            if (
                not physical_cards
                and source_card is not None
                and source_card in self.engine.processing_area
            ):
                physical_cards = (source_card,)
            event = DamageEvent(
                amount=amount,
                nature=DamageNature(nature),
                source_player=actor,
                source_card=source_card,
                source_physical_cards=physical_cards,
            )
        else:
            event = damage_event
        should_reset_chain = False

        def play_applications(applications, controller):
            for application in applications:
                vine_burning = (
                    application.skill.name == "藤甲"
                    and event.nature == DamageNature.FIRE
                )
                self.play_equipment_sound(
                    "藤甲燃烧" if vine_burning
                    else application.skill.name,
                    controller,
                )

        def finish_damage_event(received_damage):
            """伤害结算结束时重置连环，结束后才产生下一段连环伤害。"""
            if received_damage and should_reset_chain and player.chained:
                player.chained = False
                self.msg(f"{player.general.name} 解除连环状态")
            propagation = (
                self.engine.get_chained_propagation_targets(player)
                if (
                    received_damage
                    and should_reset_chain
                    and not event.is_chain_transfer
                )
                else []
            )
            if propagation:
                names = "、".join(
                    target.general.name for target in propagation
                )
                self.msg(f"属性伤害沿铁索传导：{names}")
                transfer_event = event.model_copy(update={
                    "chain_origin": player,
                    "is_chain_transfer": True,
                })
                self._continue_chain_damage(
                    propagation, transfer_event, on_complete
                )
            elif on_complete:
                on_complete()

        def begin_damage_end(received_damage):
            callback = lambda: finish_damage_event(received_damage)
            if player.alive:
                self._begin_triggered_skill_sequence(
                    player, SkillTiming.DAMAGE_END, event, callback
                )
            else:
                callback()

        def begin_received_after():
            def begin_global_received_after():
                self._begin_global_triggered_skill_sequence(
                    SkillTiming.AFTER_ANY_DAMAGE,
                    event,
                    lambda: begin_damage_end(True),
                )

            if player.alive:
                self._begin_triggered_skill_sequence(
                    player,
                    SkillTiming.AFTER_DAMAGE,
                    event,
                    begin_global_received_after,
                )
            else:
                begin_global_received_after()

        def begin_causing_after():
            source = event.source_player
            if source is not None and source.alive:
                self._begin_triggered_skill_sequence(
                    source,
                    SkillTiming.AFTER_CAUSING_DAMAGE,
                    event,
                    begin_received_after,
                )
            else:
                begin_received_after()

        def commit_damage():
            """收到伤害时全部结算完毕后，插入扣减体力与濒死事件。"""
            nonlocal should_reset_chain
            final_amount = event.amount
            nature = event.nature
            if final_amount <= 0:
                self.msg(f"{player.general.name} 防止了此次伤害")
                begin_damage_end(False)
                return
            should_reset_chain = bool(
                nature != DamageNature.NORMAL and player.chained
            )
            nature_label = {
                DamageNature.FIRE: "火焰",
                DamageNature.THUNDER: "雷电",
            }.get(nature, "")
            transfer_label = "传导的" if event.is_chain_transfer else ""
            self.msg(
                f"{player.general.name} 受到{transfer_label}{final_amount}点"
                f"{nature_label}伤害"
            )
            is_lightning = bool(
                event.source_card and event.source_card.name == "闪电"
            )
            self.play_system_sound(
                "damage3" if is_lightning
                else "damage1" if final_amount == 1
                else "damage2"
            )
            self._play_visual_effect("damage", player)
            self._start_hit_animation(player)
            self.engine.take_damage(
                player,
                final_amount,
                check_death=False,
                damage_event=event,
            )
            if player.hp <= 0:
                self._begin_dying(
                    player, event.source_player or player,
                    damage_event=event,
                    on_complete=begin_causing_after,
                )
                return
            begin_causing_after()

        def apply_receiving_equipment():
            nonlocal event
            if event.amount <= 0:
                commit_damage()
                return
            event, applications = (
                self.engine.modify_receiving_damage_with_skills(
                    player, event
                )
            )
            play_applications(applications, player)
            commit_damage()

        def begin_receiving_damage():
            if event.amount <= 0:
                commit_damage()
                return
            # 单角色同一时机：武将技能优先于装备技能。每项完成后重新检查。
            self._begin_triggered_skill_sequence(
                player,
                SkillTiming.WHEN_DAMAGED,
                event,
                apply_receiving_equipment,
            )

        def apply_causing_equipment():
            nonlocal event
            if event.amount <= 0:
                commit_damage()
                return
            event, applications = (
                self.engine.modify_causing_damage_with_skills(
                    player, event
                )
            )
            play_applications(
                applications, event.source_player or player
            )
            begin_receiving_damage()

        def begin_causing_damage():
            source = event.source_player
            if source is not None and source.alive:
                self._begin_triggered_skill_sequence(
                    source,
                    SkillTiming.CAUSING_DAMAGE,
                    event,
                    apply_causing_equipment,
                )
            else:
                apply_causing_equipment()

        if player.alive:
            self._begin_triggered_skill_sequence(
                player,
                SkillTiming.DAMAGE_START,
                event,
                begin_causing_damage,
            )
        else:
            begin_causing_damage()
        return False

    def _continue_chain_damage(self, queue, event, on_complete):
        while queue and not queue[0].alive:
            queue.pop(0)
        if not queue:
            if on_complete:
                on_complete()
            return
        target = queue.pop(0)
        self._apply_damage(
            target, damage_event=event,
            on_complete=lambda: self._continue_chain_damage(queue, event, on_complete)
        )

    def _has_blocking_animation(self):
        return any(a.get("blocking") for a in self.animations)

    def _has_draw_animation(self):
        return any(a.get("type") == "draw" for a in self.animations)

    def _reset_play_timer(self):
        self.play_time_remaining = PLAY_TIME_LIMIT_MS
        self.play_timer_last_tick = pygame.time.get_ticks()

    def _schedule_phase_transition(self, callback, delay=480):
        self.phase_transition_callback = callback
        self.phase_transition_at = pygame.time.get_ticks() + delay

    def _update_phase_transition(self):
        if not self.phase_transition_callback or pygame.time.get_ticks() < self.phase_transition_at:
            return
        callback = self.phase_transition_callback
        self.phase_transition_callback = None
        self.phase_transition_at = 0
        callback()

    def _update_play_timer(self):
        now = pygame.time.get_ticks()
        if self.judgment_display_in_progress:
            self.play_timer_last_tick = now
            self.response_timer_last_tick = now
            return
        if self.wd and self.dt and not self.judgment_result_tip:
            self.play_timer_last_tick = now
            if self._has_blocking_animation():
                self.response_timer_last_tick = now
                return
            elapsed = max(0, now - self.response_timer_last_tick)
            self.response_timer_last_tick = now
            self.response_time_remaining = max(0, self.response_time_remaining - elapsed)
            if self.response_time_remaining <= 0:
                responder = self.dt
                self.msg(f"{responder.general.name} 响应时间到")
                if self.active_prompt:
                    self._decline_skill_prompt()
                elif self.dying_target:
                    self._skip_dying_peach(responder)
                elif self.nullification_context and self.response_source_name == "无懈可击":
                    self._pass_nullification()
                elif self.response_source_name == "借刀杀人":
                    self._refuse_borrowed_sword()
                else:
                    self._resolve_human_no_dodge(f"未在时限内打出【{self.response_card_name}】")
            return
        self.response_timer_last_tick = now
        if not self.engine or self.go or self.engine.state.phase not in (Phase.PLAY, Phase.DISCARD):
            self.play_timer_last_tick = now
            return
        # 响应和动画期间不占用当前玩家的出牌时间。
        if self.wd or self.target_card_choice or self.five_grains_choice or self.borrowed_sword_choice or self.fire_attack_context or self._has_blocking_animation():
            self.play_timer_last_tick = now
            return
        elapsed = max(0, now - self.play_timer_last_tick)
        self.play_timer_last_tick = now
        self.play_time_remaining = max(0, self.play_time_remaining - elapsed)
        if self.play_time_remaining <= 0:
            p = self.engine.get_current_player()
            if self.engine.state.phase == Phase.PLAY:
                self.msg(f"{p.general.name} 出牌时间到")
                self._enter_discard_phase(p)
            else:
                self.msg(f"{p.general.name} 弃牌时间到")
                self._auto_discard_timeout(p)

    def _queue_card_animation(
        self, card, source, target=None, face_up=True, on_complete=None,
        blocking=False, arrow_source=None, visual_reason="use_or_reveal",
        waiting_metadata=None, waiting_position=None,
    ):
        """展示已由规则事件确认的可见牌移动；本函数不决定牌的规则去向。"""
        pending = sum(1 for a in self.animations if a.get("to_wait"))
        slot = (
            waiting_position
            if waiting_position is not None
            else self._wait_slot_center(len(self.waiting_cards) + pending)
        )
        now = pygame.time.get_ticks()
        if target:
            self.animations.append({
                "type": "arrow", "card": card, "source": source,
                "arrow_source": arrow_source or source,
                "target": target, "dest": slot, "start": now,
                "duration": ARROW_ANIM_MS + ARROW_HOLD_MS, "to_wait": True,
                "face_up": face_up, "on_complete": on_complete,
                "blocking": blocking or bool(on_complete),
                "visual_reason": visual_reason,
                "waiting_metadata": dict(waiting_metadata or {}),
            })
        else:
            self.animations.append({
                "type": "move", "card": card, "source": source,
                "dest": slot, "start": now, "duration": CARD_MOVE_MS,
                "to_wait": True, "face_up": face_up,
                "on_complete": on_complete,
                "blocking": blocking or bool(on_complete),
                "visual_reason": visual_reason,
                "waiting_metadata": dict(waiting_metadata or {}),
            })

    def _queue_public_reveal(
        self, reveal_event, source, on_complete=None, blocking=True
    ):
        """让公开展示副本飞入等待区；规则实体仍停留在原区域。"""
        display_card = reveal_event.card.model_copy(deep=True)
        display_id = f"reveal:{reveal_event.reveal_id}"
        self._queue_card_animation(
            display_card,
            source,
            face_up=True,
            on_complete=on_complete,
            blocking=blocking,
            visual_reason="public_reveal",
            waiting_metadata={
                "display_id": display_id,
                "is_visual_copy": True,
                "source_card_id": reveal_event.card.id,
                "source_zone": reveal_event.from_zone,
                "visibility": reveal_event.visibility,
                "reveal_reason": reveal_event.reason,
            },
        )
        return display_id

    def _clear_public_reveal(self, display_id):
        """只淡出指定公开展示副本，不移动或清除其规则实体。"""
        if not display_id:
            return
        now = pygame.time.get_ticks()
        kept = []
        for item in self.waiting_cards:
            if item.get("display_id") != display_id:
                kept.append(item)
                continue
            self.animations.append({
                "type": "fade",
                "card": item["card"],
                "pos": item["pos"],
                "start": now,
                "duration": CARD_FADE_MS,
                "visual_reason": "public_reveal_end",
            })
        self.waiting_cards = kept

    def _queue_discard_display(
        self, cards, sources, on_complete=None, sequential=False,
        visual_reason="discard",
    ):
        """统一展示弃牌；全部牌完成中央等待区动画后再恢复父结算。"""
        pairs = list(zip(cards, sources))
        if not pairs:
            if on_complete:
                on_complete()
            return
        if sequential:
            def queue_next(index=0):
                if index >= len(pairs):
                    if on_complete:
                        on_complete()
                    return
                card, source = pairs[index]
                self._queue_card_animation(
                    card, source, face_up=True, blocking=True,
                    on_complete=lambda: queue_next(index + 1),
                    visual_reason=visual_reason,
                )
            queue_next()
            return
        remaining = [len(pairs)]

        def finish_one():
            remaining[0] -= 1
            if remaining[0] == 0 and on_complete:
                on_complete()

        for card, source in pairs:
            self._queue_card_animation(
                card, source, face_up=True, blocking=True,
                on_complete=finish_one,
                visual_reason=visual_reason,
            )

    def _queue_area_card_animation(self, card, source, targets, face_up=True, on_complete=None, blocking=False, arrow_source=None):
        target_points = [
            self._arrow_target_center(target)
            for target in targets if target.alive
        ]
        if not target_points:
            self._queue_card_animation(card, source, None, face_up=face_up, on_complete=on_complete, blocking=blocking)
            return
        pending = sum(1 for a in self.animations if a.get("to_wait"))
        slot = self._wait_slot_center(len(self.waiting_cards) + pending)
        self.animations.append({
            "type": "area_arrow", "card": card, "source": source,
            "arrow_source": arrow_source or source,
            "targets": target_points, "dest": slot,
            "start": pygame.time.get_ticks(),
            "duration": ARROW_ANIM_MS + ARROW_HOLD_MS,
            "to_wait": True, "face_up": face_up,
            "on_complete": on_complete,
            "blocking": blocking or bool(on_complete)
        })

    def _queue_borrowed_sword_animation(
        self, card, source, actor, wielder, victim, on_complete=None
    ):
        """借刀杀人同时冻结两个目标，并依次展示两段指向箭头。"""
        pending = sum(1 for anim in self.animations if anim.get("to_wait"))
        slot = self._wait_slot_center(len(self.waiting_cards) + pending)
        self.animations.append({
            "type": "borrowed_sword",
            "card": card,
            "source": source,
            "dest": slot,
            "segments": (
                (
                    self._play_arrow_source(actor),
                    self._arrow_target_center(wielder),
                ),
                (
                    self._player_center(wielder),
                    self._arrow_target_center(victim),
                ),
            ),
            "start": pygame.time.get_ticks(),
            "segment_gap": BORROWED_SWORD_ARROW_GAP_MS,
            "duration": (
                ARROW_ANIM_MS * 2
                + BORROWED_SWORD_ARROW_GAP_MS
                + ARROW_HOLD_MS
            ),
            "to_wait": True,
            "face_up": True,
            "on_complete": on_complete,
            "blocking": True,
        })

    def _card_token(self, card):
        return id(card)

    def _queue_draw_animation(self, card, dest, hide_until_done=False, face_up=True, source=None, blocking=False, start=None, on_complete=None):
        if hide_until_done:
            self.hidden_draw_cards.add(self._card_token(card))
        self.animations.append({
            "type": "draw", "card": card, "source": source or DRAW_SOURCE_POS,
            "dest": dest, "start": start if start is not None else pygame.time.get_ticks(),
            "duration": DRAW_CARD_MOVE_MS, "hidden_id": self._card_token(card) if hide_until_done else None,
            "face_up": face_up, "w": CARD_W, "h": CARD_H,
            "blocking": blocking, "on_complete": on_complete
        })

    def _queue_zone_slam_animation(self, card, source, dest, on_complete=None, delay=0, use_waypoint=True):
        """卡牌先向右上方蓄势，再带缩放快速冲入固定区域。"""
        self.animations.append({
            "type": "zone_slam", "card": card, "source": source, "dest": dest,
            "waypoint": (source[0] + 82, source[1] - 68),
            "use_waypoint": use_waypoint,
            "start": pygame.time.get_ticks() + delay, "duration": 520,
            "face_up": True, "blocking": True, "on_complete": on_complete,
        })

    def _start_waiting_cards_fade(self):
        if not self.waiting_cards:
            return
        now = pygame.time.get_ticks()
        for item in self.waiting_cards:
            self.animations.append({
                "type": "fade", "card": item["card"], "pos": item["pos"],
                "start": now, "duration": CARD_FADE_MS
            })
        self.waiting_cards = []

    def _request_waiting_cards_fade(self):
        self.fade_waiting_when_idle = True
        if not any(a.get("to_wait") for a in self.animations):
            self._start_waiting_cards_fade()
            self.fade_waiting_when_idle = False

    def _draw_arrow(self, start, end, progress):
        sx, sy = start
        ex, ey = end
        mx = sx + (ex - sx) * progress
        my = sy + (ey - sy) * progress
        pygame.draw.line(self.screen, C_GOLD_LIGHT, (sx, sy), (mx, my), 5)
        ang = math.atan2(my - sy, mx - sx)
        head = 15
        p1 = (mx, my)
        p2 = (mx - math.cos(ang - 0.55) * head, my - math.sin(ang - 0.55) * head)
        p3 = (mx - math.cos(ang + 0.55) * head, my - math.sin(ang + 0.55) * head)
        pygame.draw.polygon(self.screen, C_GOLD_LIGHT, [p1, p2, p3])

    def _draw_waiting_area(self):
        rect = pygame.Rect(WAIT_AREA_X, WAIT_AREA_Y, WAIT_AREA_W, WAIT_AREA_H)
        panel = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (24, 18, 13, 112), panel.get_rect(), border_radius=8)
        pygame.draw.rect(panel, (178, 142, 78, 150), panel.get_rect(), 1, border_radius=8)
        self.screen.blit(panel, rect.topleft)
        self.drw("等待区","ts",rect.x+12,rect.y+8,C_GOLD)
        for item in self.waiting_cards:
            x, y = item["pos"]
            self.dc(item["card"], int(x-WAIT_CARD_W//2), int(y-WAIT_CARD_H//2), WAIT_CARD_W, WAIT_CARD_H)

    def _draw_target_card_choice(self):
        context = self.target_card_choice
        if not context or context["actor"].is_ai:
            self.target_card_choice_rects = []
            return
        choices = context["choices"]
        card_w, card_h, gap = 88, 132, 22
        panel_w = min(TABLE_R - 100, max(620, len(choices) * (card_w + gap) + 80))
        panel_h = 226
        panel_x = TABLE_CX - panel_w // 2
        panel_y = TABLE_CY - panel_h // 2
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (24, 18, 13, 238), panel.get_rect(), border_radius=10)
        pygame.draw.rect(panel, (*C_GOLD, 220), panel.get_rect(), 2, border_radius=10)
        self.screen.blit(panel, (panel_x, panel_y))
        self.drw(f"选择 {context['target'].general.name} 的一张手牌、装备或判定牌", "b", TABLE_CX, panel_y+24, C_GOLD_LIGHT, center=True)
        available_w = panel_w - 64
        step = card_w + gap
        if len(choices) > 1:
            step = min(step, (available_w - card_w) / (len(choices) - 1))
        total_w = card_w + max(0, len(choices)-1)*step
        start_x = TABLE_CX - total_w//2
        self.target_card_choice_rects = []
        for i, choice in enumerate(choices):
            zone, _, card = choice
            rect = pygame.Rect(int(start_x+i*step), panel_y+58, card_w, card_h)
            self.dc(card, rect.x, rect.y, card_w, card_h, up=(zone != "hand"))
            zone_label = {"hand": "手牌", "equipment": "装备", "judgment": "判定区"}.get(zone, "牌")
            self.drw(zone_label, "ts", rect.centerx, rect.bottom+6, C_W_DARK, center=True)
            self.target_card_choice_rects.append((rect, choice))

    def _draw_skill_reveal_panel(self):
        """在拆顺式独立框中公开技能展示牌，不占用中央等待区。"""
        context = self.skill_reveal_panel
        if not context:
            return
        if pygame.time.get_ticks() >= context["expires_at"]:
            self.skill_reveal_panel = None
            return
        cards = context["cards"]
        card_w, card_h, gap = 88, 132, 22
        panel_w = min(
            TABLE_R - 100,
            max(620, len(cards) * (card_w + gap) + 80),
        )
        panel_h = 226
        panel_x = TABLE_CX - panel_w // 2
        panel_y = TABLE_CY - panel_h // 2
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(
            panel, (24, 18, 13, 238), panel.get_rect(),
            border_radius=10,
        )
        pygame.draw.rect(
            panel, (*C_GOLD, 220), panel.get_rect(), 2,
            border_radius=10,
        )
        self.screen.blit(panel, (panel_x, panel_y))
        self.drw(
            context["title"], "b", TABLE_CX, panel_y + 24,
            C_GOLD_LIGHT, center=True,
        )
        available_w = panel_w - 64
        step = card_w + gap
        if len(cards) > 1:
            step = min(
                step,
                (available_w - card_w) / (len(cards) - 1),
            )
        total_w = card_w + max(0, len(cards) - 1) * step
        start_x = TABLE_CX - total_w // 2
        for index, card in enumerate(cards):
            x = int(start_x + index * step)
            self.dc(
                card, x, panel_y + 58,
                card_w, card_h, up=True,
            )

    def _draw_five_grains_choice(self):
        context = self.five_grains_choice
        if not context:
            self.five_grains_choice_rects = []
            return
        cards = context["cards"]
        chooser = context.get("chooser")
        card_w, card_h, gap = 98, 148, 26
        panel_w = min(TABLE_R - 100, max(620, len(cards)*(card_w+gap)+90))
        panel_h = 250
        panel_x, panel_y = TABLE_CX-panel_w//2, TABLE_CY-panel_h//2
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (24, 18, 13, 242), panel.get_rect(), border_radius=12)
        pygame.draw.rect(panel, (*C_GOLD, 230), panel.get_rect(), 2, border_radius=12)
        self.screen.blit(panel, (panel_x, panel_y))
        title = f"五谷丰登 · 请 {chooser.general.name} 选择一张" if chooser else "五谷丰登"
        self.drw(title, "b", TABLE_CX, panel_y+25, C_GOLD_LIGHT, center=True)
        available_w = panel_w-70
        step = card_w+gap
        if len(cards)>1:
            step = min(step, (available_w-card_w)/(len(cards)-1))
        total_w = card_w + max(0, len(cards)-1)*step
        start_x = TABLE_CX-total_w//2
        self.five_grains_choice_rects = []
        for i, card in enumerate(cards):
            rect = pygame.Rect(int(start_x+i*step), panel_y+62, card_w, card_h)
            self.dc(card, rect.x, rect.y, card_w, card_h, up=True)
            self.five_grains_choice_rects.append((rect, card))

    def _draw_fire_attack_choice(self):
        # 本地玩家直接在常驻手牌区明牌选择，不建立重复的弹窗牌区。
        self.fire_attack_choice_rects = []

    def _begin_fire_attack(self, actor, trick_card, target):
        if not target.hand:
            self.hint("没有手牌的角色不能成为【火攻】目标")
            self._xd()
            return
        context = {
            "actor": actor, "card": trick_card, "target": target,
            "chooser": target, "choices": target.hand[:], "stage": "reveal",
            "selected": None,
            "title": f"{target.general.name}：请选择一张手牌展示",
        }
        self.fire_attack_context = context
        if target.is_ai:
            self._resolve_fire_attack_choice(random.choice(target.hand))
        else:
            self.hint(context["title"], 5000)

    def _resolve_fire_attack_choice(self, card):
        context = self.fire_attack_context
        if not context or card not in context.get("choices", []):
            return
        self.clear_hint()
        if context["stage"] == "reveal":
            target = context["target"]
            reveal_event = self.engine.reveal_card(
                target, card, "hand", "火攻展示", visibility="public"
            )
            if reveal_event is None:
                self.hint("所选展示牌已不在手牌区")
                return
            source = self._hand_card_center(
                target, target.hand.index(card)
            )
            context["selected"] = None
            self.idx = None
            context["revealed"] = card
            context["reveal_event"] = reveal_event
            self.msg(f"{context['target'].general.name} 展示【{card.name}】（{SUIT_CN.get(card.suit, card.suit)}{card.rank}）")
            self.fire_attack_choice_rects=[]
            context["reveal_display_id"] = self._queue_public_reveal(
                reveal_event, source, blocking=True,
                on_complete=self._offer_fire_attack_discard,
            )
            return
        actor = context["actor"]
        if card not in actor.hand or card.suit != context["revealed"].suit:
            self.hint("请选择与展示牌花色相同的手牌")
            return
        self.engine.discard_from_hand(actor, card, "火攻弃牌")
        self.msg(f"{actor.general.name} 为【火攻】弃置【{card.name}】")
        target, trick_card = context["target"], context["card"]
        reveal_display_id = context.get("reveal_display_id")
        self.fire_attack_context=None
        self.fire_attack_choice_rects=[]
        self.idx = None
        self._clear_public_reveal(reveal_display_id)
        self._queue_card_animation(
            card, self._player_center(actor), blocking=True,
            on_complete=lambda: self._apply_damage(
                target, 1, actor=actor, source_card=trick_card,
                nature=DamageNature.FIRE, on_complete=self._xd
            )
        )

    def _offer_fire_attack_discard(self):
        context = self.fire_attack_context
        if not context:
            return
        actor, revealed = context["actor"], context["revealed"]
        choices = [card for card in actor.hand if card.suit == revealed.suit]
        if not choices:
            if actor.is_ai:
                self.msg(
                    f"{actor.general.name} 没有与展示牌同花色的手牌，"
                    "【火攻】结束"
                )
                self._clear_public_reveal(
                    context.get("reveal_display_id")
                )
                self.fire_attack_context = None
                self._xd()
                return
            context.update({
                "chooser": actor,
                "choices": [],
                "stage": "discard",
                "selected": None,
                "title": "没有与展示牌同花色的手牌，请点击【取消】",
            })
            self.hint(context["title"], 5000)
            return
        context.update({
            "chooser": actor, "choices": choices, "stage": "discard",
            "selected": None,
            "title": f"请选择一张{SUIT_CN.get(revealed.suit, revealed.suit)}手牌弃置",
        })
        if actor.is_ai:
            self._resolve_fire_attack_choice(choices[0])
        else:
            self.hint(context["title"], 5000)

    def _cancel_fire_attack_discard(self):
        """火攻使用者放弃弃置同花色牌，本次火攻不造成伤害。"""
        context = self.fire_attack_context
        if not context or context.get("stage") != "discard":
            return
        actor = context["actor"]
        if context.get("choices"):
            self.msg(f"{actor.general.name} 放弃为【火攻】弃置同花色手牌")
        else:
            self.msg(
                f"{actor.general.name} 没有与展示牌同花色的手牌，"
                "【火攻】结束"
            )
        self._clear_public_reveal(context.get("reveal_display_id"))
        self.fire_attack_context = None
        self.fire_attack_choice_rects = []
        self.idx = None
        self._xd()

    def _clear_fire_attack_reveal_selection(self):
        """撤销火攻展示牌的当前选择，但不跳过强制展示步骤。"""
        context = self.fire_attack_context
        if not context or context.get("stage") != "reveal":
            return
        context["selected"] = None
        self.idx = None
        self.hint(context["title"], 5000)

    def _begin_five_grains(self, actor, trick_card):
        alive = self.engine.get_alive_players()
        cards = self.engine.draw_cards(len(alive))
        order = [p for p in self._players_from_actor(actor) if p.alive]
        self.five_grains_choice = {"cards": cards, "order": order, "index": 0, "chooser": None, "revealing": True, "actor": actor, "trick_card": trick_card}
        self.five_grains_reveal_at = pygame.time.get_ticks() + FIVE_GRAINS_REVEAL_HOLD_MS
        self.msg(f"五谷丰登亮出{len(cards)}张牌")

    def _update_five_grains_reveal(self):
        context = self.five_grains_choice
        if not context or not context.get("revealing") or pygame.time.get_ticks() < self.five_grains_reveal_at:
            return
        context["revealing"] = False
        self.five_grains_reveal_at = 0
        self._advance_five_grains()

    def _advance_five_grains(self):
        context = self.five_grains_choice
        if not context:
            return
        if context["index"] >= len(context["order"]) or not context["cards"]:
            self.five_grains_choice = None
            self.five_grains_choice_rects = []
            self.five_grains_reveal_at = 0
            self.msg("五谷丰登结算完毕")
            return
        chooser = context["order"][context["index"]]
        context["chooser"] = chooser
        self._begin_nullification(
            context["actor"], context["trick_card"], chooser,
            self._offer_five_grains_choice,
            on_cancel=self._skip_five_grains_choice,
        )

    def _offer_five_grains_choice(self):
        context = self.five_grains_choice
        if not context:
            return
        chooser = context["chooser"]
        self.hint(f"轮到 {chooser.general.name} 选择五谷丰登牌", 5000)
        if chooser.is_ai:
            self._resolve_five_grains_choice(random.choice(context["cards"]), None)

    def _skip_five_grains_choice(self):
        context = self.five_grains_choice
        if not context:
            return
        chooser = context["chooser"]
        self.msg(f"{chooser.general.name} 的【五谷丰登】效果被抵消")
        context["index"] += 1
        self._advance_five_grains()

    def _resolve_five_grains_choice(self, card, source_rect):
        context = self.five_grains_choice
        if not context or card not in context["cards"]:
            return
        self.clear_hint()
        chooser = context["chooser"]
        source = source_rect.center if source_rect else (TABLE_CX, TABLE_CY)
        context["cards"].remove(card)
        context["index"] += 1
        chooser.hand.append(card)
        self.msg(f"{chooser.general.name} 从五谷丰登中获得【{card.name}】")
        self._queue_hand_gain_animation(
            chooser, card, source, face_up=True,
            on_complete=self._advance_five_grains
        )

    def _draw_animations(self):
        now = pygame.time.get_ticks()
        kept = []
        completed_callbacks = []
        for anim in self.animations:
            progress = min(1, max(0, (now - anim["start"]) / max(1, anim["duration"])))
            if anim["type"] in ("arrow", "area_arrow"):
                elapsed = now - anim["start"]
                arrow_progress = min(1, max(0, elapsed / max(1, ARROW_ANIM_MS)))
                arrow_source = anim.get("arrow_source", anim["source"])
                if anim["type"] == "area_arrow":
                    for target in anim["targets"]:
                        self._draw_arrow(arrow_source, target, arrow_progress)
                else:
                    self._draw_arrow(arrow_source, anim["target"], arrow_progress)

                # 出牌与箭头使用同一开始时间：牌飞向等待区时箭头同步展开。
                sx, sy = anim["source"]
                dx, dy = anim["dest"]
                move_progress = min(1, max(0, elapsed / max(1, CARD_MOVE_MS)))
                eased = self._ease_out_cubic(move_progress)
                x = sx + (dx - sx) * eased
                y = sy + (dy - sy) * eased
                surf = self._make_card_surface(anim["card"], WAIT_CARD_W, WAIT_CARD_H, face_up=anim.get("face_up", True))
                self.screen.blit(surf, surf.get_rect(center=(x, y)))
                if elapsed >= anim["duration"]:
                    waiting_item = {
                        "card": anim["card"], "pos": anim["dest"]
                    }
                    waiting_item.update(anim.get("waiting_metadata", {}))
                    self.waiting_cards.append(waiting_item)
                    callback = anim.get("on_complete")
                    if callback:
                        completed_callbacks.append(callback)
                else:
                    kept.append(anim)
            elif anim["type"] == "borrowed_sword":
                elapsed = now - anim["start"]
                segment_gap = anim.get("segment_gap", 0)
                first_progress = min(
                    1, max(0, elapsed / max(1, ARROW_ANIM_MS))
                )
                second_progress = min(
                    1,
                    max(
                        0,
                        (
                            elapsed - ARROW_ANIM_MS - segment_gap
                        ) / max(1, ARROW_ANIM_MS),
                    ),
                )
                first, second = anim["segments"]
                self._draw_arrow(first[0], first[1], first_progress)
                if second_progress > 0:
                    self._draw_arrow(second[0], second[1], second_progress)
                sx, sy = anim["source"]
                dx, dy = anim["dest"]
                move_progress = min(
                    1, max(0, elapsed / max(1, CARD_MOVE_MS))
                )
                eased = self._ease_out_cubic(move_progress)
                x = sx + (dx - sx) * eased
                y = sy + (dy - sy) * eased
                surface = self._make_card_surface(
                    anim["card"], WAIT_CARD_W, WAIT_CARD_H, face_up=True
                )
                self.screen.blit(surface, surface.get_rect(center=(x, y)))
                if elapsed >= anim["duration"]:
                    self.waiting_cards.append({
                        "card": anim["card"], "pos": anim["dest"]
                    })
                    callback = anim.get("on_complete")
                    if callback:
                        completed_callbacks.append(callback)
                else:
                    kept.append(anim)
            elif anim["type"] == "move":
                sx, sy = anim["source"]
                dx, dy = anim["dest"]
                eased = self._ease_out_cubic(progress)
                x = sx + (dx - sx) * eased
                y = sy + (dy - sy) * eased
                surf = self._make_card_surface(anim["card"], WAIT_CARD_W, WAIT_CARD_H, face_up=anim.get("face_up", True))
                self.screen.blit(surf, surf.get_rect(center=(x, y)))
                if progress >= 1:
                    waiting_item = {
                        "card": anim["card"], "pos": anim["dest"]
                    }
                    waiting_item.update(anim.get("waiting_metadata", {}))
                    self.waiting_cards.append(waiting_item)
                    callback = anim.get("on_complete")
                    if callback:
                        completed_callbacks.append(callback)
                else:
                    kept.append(anim)
            elif anim["type"] == "draw":
                sx, sy = anim["source"]
                dx, dy = anim["dest"]
                eased = self._ease_out_cubic(progress)
                x = sx + (dx - sx) * eased
                y = sy + (dy - sy) * eased
                surf = self._make_card_surface(anim["card"], anim.get("w", CARD_W), anim.get("h", CARD_H), face_up=anim.get("face_up", True))
                self.screen.blit(surf, surf.get_rect(center=(x, y)))
                if progress >= 1:
                    hidden_id = anim.get("hidden_id")
                    if hidden_id:
                        self.hidden_draw_cards.discard(hidden_id)
                    callback = anim.get("on_complete")
                    if callback:
                        completed_callbacks.append(callback)
                else:
                    kept.append(anim)
            elif anim["type"] == "fade":
                x, y = anim["pos"]
                alpha = int(255 * (1 - progress))
                surf = self._make_card_surface(anim["card"], WAIT_CARD_W, WAIT_CARD_H, alpha)
                self.screen.blit(surf, surf.get_rect(center=(x, y)))
                if progress < 1:
                    kept.append(anim)
            elif anim["type"] == "zone_slam":
                sx, sy = anim["source"]
                dx, dy = anim["dest"]
                wx, wy = anim["waypoint"]
                if not anim.get("use_waypoint", True):
                    travel = self._ease_out_cubic(progress)
                    x = sx + (dx - sx) * travel
                    y = sy + (dy - sy) * travel
                    scale = (1 - progress) + 0.42 * progress + 0.22 * math.sin(math.pi * progress)
                elif progress < 0.34:
                    phase = self._ease_out_cubic(progress / 0.34)
                    x = sx + (wx - sx) * phase
                    y = sy + (wy - sy) * phase
                    scale = 1 + 0.08 * math.sin(math.pi * phase)
                else:
                    phase = (progress - 0.34) / 0.66
                    travel = self._ease_out_cubic(phase)
                    x = wx + (dx - wx) * travel
                    y = wy + (dy - wy) * travel
                    scale = (1 - phase) + 0.42 * phase + 0.22 * math.sin(math.pi * phase)
                card_w = max(24, int(WAIT_CARD_W * scale))
                card_h = max(36, int(WAIT_CARD_H * scale))
                surf = self._make_card_surface(anim["card"], card_w, card_h, face_up=True)
                self.screen.blit(surf, surf.get_rect(center=(x, y)))
                if progress >= 1:
                    callback = anim.get("on_complete")
                    if callback:
                        completed_callbacks.append(callback)
                else:
                    kept.append(anim)
        self.animations = kept
        if self.fade_waiting_when_idle and not any(a.get("to_wait") for a in self.animations):
            self._start_waiting_cards_fade()
            self.fade_waiting_when_idle = False
        for callback in completed_callbacks:
            callback()

    # ===== 手牌区域计算 =====
    def hrects(self, p=None):
        if not self.engine: return []
        if p is None:
            p=self.engine.get_current_player()
        if not p: return []
        n=len(p.hand)
        if n==0: return []
        rs=[]
        for i in range(n):
            x = HAND_LEFT_X + i * HAND_SPACING
            discard_selected = bool(
                self.engine.state.phase == Phase.DISCARD
                and i in self.discard_selected
            )
            skill_selected = bool(
                getattr(self, "active_prompt", None)
                and getattr(self, "dt", None) is p
                and p.hand[i].id in getattr(
                    self, "skill_prompt_selected", set()
                )
            )
            raised = (
                i == getattr(self, "idx", None)
                or discard_selected or skill_selected
            )
            by = HAND_Y - (SELECTED_CARD_RISE if raised else 0)
            rs.append(pygame.Rect(int(x), int(by), CARD_W, CARD_H))
        return rs

    def gci(self, pos, p=None):
        if not self.engine: return None
        if p is None:
            p=self.engine.get_current_player()
        if not p: return None
        rs=self.hrects(p)
        for i,r in enumerate(rs):
            if r.collidepoint(pos) and i<len(p.hand): return i
        return None

    def gpl(self, pos):
        if not self.engine: return None
        for p in self.engine.state.players:
            if not p.alive: continue
            if p.is_ai:
                if pygame.Rect(ENEMY_X,ENEMY_Y,ENEMY_W,ENEMY_H).collidepoint(pos): return p
            else:
                if pygame.Rect(ME_X,ME_Y,ME_W,ME_H).collidepoint(pos): return p
        return None

    def _cards_added_after(self, before_tokens, cards):
        return [card for card in cards if self._card_token(card) not in before_tokens]

    def _hide_added_cards(self, before_tokens, cards):
        for card in self._cards_added_after(before_tokens, cards):
            self.hidden_draw_cards.add(self._card_token(card))

    def _cards_removed_after(self, before_cards, after_cards):
        after_ids = {card.id for card in after_cards}
        return [card for card in before_cards if card.id not in after_ids]

    def _hand_gain_dest(self, p, card):
        if p.is_ai:
            return self._player_center(p)
        idx = p.hand.index(card) if card in p.hand else len(p.hand)
        rects = self.hrects(p)
        if idx < len(rects):
            return rects[idx].center
        return (HAND_LEFT_X + idx * HAND_SPACING + CARD_W//2, HAND_Y + CARD_H//2)

    def _queue_hand_gain_animation(
        self, p, card, source, face_up=True, on_complete=None,
        dest=None, start=None,
    ):
        hide = not p.is_ai
        dest = dest or self._hand_gain_dest(p, card)
        self._queue_draw_animation(
            card, dest, hide_until_done=hide, face_up=face_up,
            source=source, blocking=True, start=start,
            on_complete=on_complete,
        )

    # ===== 游戏逻辑 =====
    def _play_zhuge_for_extra_slash(self, player, zhuge_was_required):
        """仅在诸葛连弩实际突破【杀】的阶段次数限制时提示发动。"""
        if (
            zhuge_was_required
            and self.engine.weapon_skill_available(player, "weapon.zhuge")
        ):
            self.play_equipment_sound("诸葛连弩", player)

    def ps(self, p, c, t, effective_name=None, skip_conversion_prompt=False):
        targets = t if isinstance(t, list) else [t]
        t = targets[0] if targets else None
        if (
            not skip_conversion_prompt and effective_name is None
            and self.engine.skills.can_convert_zhuque(p, c)
        ):
            # AI 的牌选择不得占用本地玩家共用的手牌选中下标。
            source_index = None if p.is_ai else self.idx
            self._open_skill_prompt(
                p, "weapon.zhuque", "朱雀羽扇",
                f"{p.general.name} 是否将普通【杀】当火【杀】使用？",
                lambda _cards: self._resume_zhuque_slash(
                    p, c, targets, "火杀", source_index
                ),
                lambda: self._resume_zhuque_slash(
                    p, c, targets, "杀", source_index
                ),
            )
            return
        if not self.engine.can_use_slash(p):
            self.hint("本回合已经使用过【杀】"); return
        if not self.engine.in_attack_range(p, t):
            self.hint(f"距离{self.engine.distance(p, t)}，超出攻击范围{self.engine.attack_range(p)}")
            return
        source = self._hand_card_center(p, self.idx)
        effective_name = effective_name or c.name
        zhuge_was_required = (
            not self.engine.has_remaining_limited_slash_uses(p)
        )
        try:
            slash_event = self.engine.create_slash_event(
                p, [c], targets, effective_name
            )
        except ValueError as exc:
            self.hint(str(exc))
            return
        self.active_slash_event = slash_event
        p.pending_slash_damage = slash_event.damage
        p.pending_slash_nature = slash_event.nature
        effective_card = slash_event.effective_card
        self.slash_target_queue = [
            (target, p, effective_card) for target in targets[1:]
        ]
        self._reset_play_timer()
        self._queue_card_animation(
            c, source, self._arrow_target_center(t),
            on_complete=lambda: self._after_slash_targeted(t, p, effective_card),
            blocking=True, arrow_source=self._play_arrow_source(p)
        )
        self.clear_selection()
        self.msg(f"{p.general.name} → {t.general.name} 【{effective_name}】")
        self.play_card_sound(p, effective_name, c)
        self._play_zhuge_for_extra_slash(p, zhuge_was_required)
        if len(targets) > 1 and self.engine.weapon_skill_available(
            p, "weapon.fangtian"
        ):
            self.play_equipment_sound("方天画戟", p)

    def _resume_zhuque_slash(self, player, card, target, effective_name, source_index):
        self.wd = False
        self.dt = None
        self.da = None
        self.idx = None if player.is_ai else source_index
        self.ps(
            player, card, target, effective_name=effective_name,
            skip_conversion_prompt=True,
        )

    def _after_slash_targeted(self, target, source, source_card):
        """【杀】完成使用表现后，先结算“使用牌时”，再进入目标响应。"""
        self._begin_card_use_trigger_window(
            lambda: self._resolve_slash_targeted(
                target, source, source_card
            )
        )

    def _resolve_slash_targeted(self, target, source, source_card):
        """指定目标后的统一武器技能窗口。"""
        if self.engine.weapon_skill_available(source, "weapon.qinggang"):
            self.play_equipment_sound("青釭剑", source)
        if self.engine.cixiong_can_trigger(source, target):
            self._open_skill_prompt(
                source, "weapon.cixiong", "雌雄双股剑",
                f"{source.general.name} 是否发动【雌雄双股剑】？",
                lambda _cards: self._begin_cixiong_target_choice(
                    source, target, source_card
                ),
                lambda: self._resume_slash_response(target, source, source_card),
            )
            return
        self._resume_slash_response(target, source, source_card)

    def _begin_cixiong_target_choice(self, source, target, source_card):
        self.wd = False
        self.dt = None
        if not target.hand:
            self._finish_cixiong_choice(source, target, source_card, None)
            return
        if target.is_ai:
            discarded = target.hand[0] if target.hand else None
            discard_source = (
                self._hand_card_center(target, target.hand.index(discarded))
                if discarded in target.hand else self._player_center(target)
            )
            self.engine.resolve_cixiong_choice(source, target, discarded)
            for message in self.engine.log:
                self.msg(message)
            self.engine.log.clear()
            if discarded is not None:
                self._queue_discard_display(
                    [discarded], [discard_source],
                    on_complete=lambda: self._resume_slash_response(
                        target, source, source_card
                    ),
                )
            else:
                self._resume_slash_response(target, source, source_card)
            return
        self._open_skill_prompt(
            target, "weapon.cixiong.choice", "雌雄双股剑",
            "请选择一张手牌后确定弃置，或取消令对方摸一张牌",
            lambda cards: self._finish_cixiong_choice(
                source, target, source_card, cards[0]
            ),
            lambda: self._finish_cixiong_choice(
                source, target, source_card, None
            ),
            selectable_cards=target.hand,
            required_cards=1,
            prompt_type=PromptType.CHOOSE_OPTION,
        )

    def _finish_cixiong_choice(self, source, target, source_card, discarded):
        self.wd = False
        self.dt = None
        discard_source = (
            self._hand_card_center(target, target.hand.index(discarded))
            if discarded in target.hand else self._player_center(target)
        )
        self.engine.resolve_cixiong_choice(source, target, discarded)
        for message in self.engine.log:
            self.msg(message)
        self.engine.log.clear()
        if discarded is not None:
            self._queue_discard_display(
                [discarded], [discard_source],
                on_complete=lambda: self._resume_slash_response(
                    target, source, source_card
                ),
            )
        else:
            self._resume_slash_response(target, source, source_card)

    def _resume_slash_response(self, target, source, source_card):
        self.wd = False
        self.dt = None
        self.ed(target, source, source_card)

    def _play_iron_chain(self, p, c, targets):
        source = self._hand_card_center(p, self.idx)
        log_start = len(self.engine.log)
        if not self.engine.play_iron_chain(p, c, targets, apply_effect=False):
            self.hint("【铁索连环】需要选择一至两名存活角色")
            return
        self._reset_play_timer()
        self.play_card_sound(p, "铁索连环")
        centers = [self._arrow_target_center(target) for target in targets]
        destination = centers[0] if centers else None
        self._queue_card_animation(
            c, source, destination, blocking=True, arrow_source=self._play_arrow_source(p),
            on_complete=lambda: self._continue_iron_chain_targets(p, c, targets[:]),
        )
        for message in self.engine.log[log_start:]:
            self.msg(message)
        self.engine.log.clear()
        self.clear_selection()

    def _continue_iron_chain_targets(self, actor, card, targets):
        self._begin_card_use_trigger_window(
            lambda: self._resolve_iron_chain_targets(
                actor, card, targets
            )
        )

    def _resolve_iron_chain_targets(self, actor, card, targets):
        if not targets:
            self.engine.log.clear()
            self._xd()
            return
        target = targets.pop(0)
        self._begin_nullification(
            actor, card, target,
            lambda target=target, targets=targets: self._resolve_iron_chain_target(actor, card, target, targets),
            on_cancel=lambda targets=targets: self._continue_iron_chain_targets(actor, card, targets),
        )

    def _resolve_iron_chain_target(self, actor, card, target, targets):
        self.engine.toggle_chain(target)
        self.play_system_sound("chain")
        self._play_visual_effect("chain", target)
        self.msg(f"{target.general.name} {'横置' if target.chained else '重置'}")
        self._continue_iron_chain_targets(actor, card, targets)

    def _recast_iron_chain(self, p, c):
        source = self._hand_card_center(p, self.idx)
        before = {self._card_token(card) for card in p.hand}
        drawn = self.engine.recast(p, c)
        if not drawn:
            self.hint("无法重铸【铁索连环】")
            return
        self._reset_play_timer()
        self._hide_added_cards(before, p.hand)
        self._queue_card_animation(
            c, source, blocking=True,
            on_complete=lambda: self._queue_hand_gain_animation(p, drawn, DRAW_SOURCE_POS, face_up=True)
        )
        self.msg(f"{p.general.name} 重铸【铁索连环】，摸一张牌")
        sound = getattr(self, "sound", None)
        if sound:
            sound.play_recast(p.general.gender)
        self.clear_selection()

    def pp(self, p, c, t):
        source = self._hand_card_center(p, self.idx)
        if not self.engine.play_card(p,c,t): self.hint("当前无法使用【桃】"); return
        self._reset_play_timer()
        self._queue_card_animation(c, source)
        self.clear_selection(); self.msg(f"{p.general.name} 使用【桃】")
        self.play_card_sound(p, "桃")

    def pw(self, p, c):
        source = self._hand_card_center(p, self.idx)
        if not self.engine.play_card(p, c, p):
            self.hint("本阶段已经使用过【酒】")
            return
        self._reset_play_timer()
        self._queue_card_animation(c, source, blocking=True)
        self.clear_selection()
        self.msg(f"{p.general.name} 使用【酒】，下一张杀伤害+1")
        self.play_card_sound(p, "酒")

    def pe(self, p, c):
        source = self._hand_card_center(p, self.idx)
        old = next((card for card in p.equipment if card.equipment_type == c.equipment_type), None)
        if not self.engine.play_card(p, c, p):
            self.hint("当前无法装备此牌")
            return
        self._reset_play_timer()
        slot_index = {"weapon": 0, "armor": 1, "offensive_mount": 2, "defensive_mount": 3}.get(c.equipment_type, 0)
        dest = self._equipment_card_center(p, slot_index)
        self.hidden_equipment_cards.add(self._card_token(c))
        self._queue_zone_slam_animation(
            c, source, dest,
            on_complete=lambda c=c, old=old, dest=dest: self._finish_equipment_slam(c, old, dest)
        )
        self.clear_selection()
        self.msg(f"{p.general.name} 装备了【{c.name}】")
        self.play_equip_action_sound(c.equipment_type)

    def _finish_equipment_slam(self, card, old, dest):
        self.hidden_equipment_cards.discard(self._card_token(card))
        if old:
            self._queue_card_animation(old, dest, blocking=True)

    def pt(self, p, c, t):
        source = self._hand_card_center(p, self.idx)
        before_player_ids = {self._card_token(card) for card in p.hand}
        before_target = t.hand[:] if t else []
        if not self.engine.play_card(p,c,t): self.hint("当前无法使用此牌"); return
        self._reset_play_timer()
        if not p.is_ai:
            self._hide_added_cards(before_player_ids, p.hand)
        callback = lambda p=p, c=c, t=t, before_player_ids=before_player_ids, before_target=before_target: self._begin_trick_resolution(p, c, t, before_player_ids, before_target)
        if c.name in ("南蛮入侵", "万箭齐发", "万剑齐发"):
            targets = [target for target in self.engine.get_alive_players() if target != p]
            self._queue_area_card_animation(c, source, targets, on_complete=callback, blocking=True, arrow_source=self._play_arrow_source(p))
        elif c.name in ("乐不思蜀", "兵粮寸断", "闪电"):
            delayed_target = t or p
            animation_target = (
                None if delayed_target is p
                else self._arrow_target_center(delayed_target)
            )
            self._queue_card_animation(
                c, source, animation_target,
                on_complete=lambda p=p, c=c, delayed_target=delayed_target:
                    self._begin_delayed_resolution(p, c, delayed_target),
                blocking=True, arrow_source=self._play_arrow_source(p)
            )
        else:
            trick_target = t or (p if c.name == "闪电" else None)
            self._queue_card_animation(
                c, source,
                self._arrow_target_center(trick_target)
                if trick_target else None,
                on_complete=callback, blocking=True,
                arrow_source=self._play_arrow_source(p)
            )
        self.clear_selection()
        if t is not None:
            self.msg(f"{p.general.name} 对 {t.general.name} 使用【{c.name}】")
        else:
            self.msg(f"{p.general.name} 使用【{c.name}】")
        self.play_card_sound(p, c.name, c)

    def _begin_trick_resolution(
        self, actor, card, target, before_player_ids, before_target
    ):
        """普通锦囊完成使用表现后，先结算“使用牌时”，再处理牌效果。"""
        self._begin_card_use_trigger_window(
            lambda: self._resolve_trick_after_card_use(
                actor, card, target, before_player_ids, before_target
            )
        )

    def _resolve_trick_after_card_use(
        self, actor, card, target, before_player_ids, before_target
    ):
        if (
            card in self.engine.processing_area
            and card not in getattr(self, "active_trick_cards", [])
        ):
            if not hasattr(self, "active_trick_cards"):
                self.active_trick_cards = []
            self.active_trick_cards.append(card)
        callback = lambda: self._queue_trick_effect_animations(
            actor, card, target, before_player_ids, before_target
        )
        # 群体锦囊需要对每个目标分别无懈，在各自的目标队列中处理。
        if card.name in ("南蛮入侵", "万箭齐发", "万剑齐发", "桃园结义", "五谷丰登"):
            callback()
            return
        self._begin_nullification(actor, card, target, callback)

    def _begin_delayed_resolution(self, actor, card, target):
        # 延时锦囊也先开放“使用牌时”窗口，再进入判定区；无懈询问
        # 仍推迟到其开始判定时。
        self._begin_card_use_trigger_window(
            lambda: self._place_delayed_after_nullification(
                actor, card, target
            )
        )

    def _place_delayed_after_nullification(self, actor, card, target):
        if not self.engine.place_delayed_trick(actor, card, target):
            self._cancel_trick(card, target)
            return
        self.delayed_trick_sources[self._card_token(card)] = actor
        self.hidden_judgment_cards.add(self._card_token(card))
        self._move_delayed_to_judgment_area(card, target)

    def _cancel_trick(self, card, target=None):
        if not self.engine.finish_processing_card(card) and card not in self.engine.discard_pile:
            self.engine.discard(card)
        target_text = f"对 {target.general.name} 的" if target else ""
        self.msg(f"{target_text}【{card.name}】被【无懈可击】抵消")
        self._xd()

    def _move_delayed_to_judgment_area(self, card, target):
        item = next((item for item in self.waiting_cards if item["card"] is card), None)
        source = item["pos"] if item else self._player_center(target)
        if item:
            self.waiting_cards.remove(item)
        self._queue_zone_slam_animation(
            card, source, self._judgment_card_center(target, card),
            on_complete=lambda card=card: self.hidden_judgment_cards.discard(self._card_token(card)),
            delay=360, use_waypoint=False
        )

    def _queue_trick_effect_animations(
        self, p, c, t, before_player_ids, before_target,
        source_physical_cards=None,
    ):
        physical_cards = tuple(source_physical_cards or ())
        if (
            not physical_cards
            and self.engine
            and c in self.engine.processing_area
        ):
            physical_cards = (c,)
        if c.name == "无中生有":
            moves = self.engine.draw_to_hand(
                p, 2, reason="无中生有摸牌"
            )
            gained = [move.card for move in moves]
            self._hide_added_cards(before_player_ids, p.hand)
            batch_start = pygame.time.get_ticks()
            for index, card in enumerate(gained):
                dest = None
                if p.is_ai:
                    center = self._player_center(p)
                    dest = (center[0] + int((index - (len(gained) - 1) / 2) * 44), center[1])
                self._queue_hand_gain_animation(
                    p, card, DRAW_SOURCE_POS,
                    face_up=not p.is_ai, dest=dest,
                    start=batch_start,
                )
        elif c.name == "南蛮入侵":
            targets = [target for target in self.engine.get_alive_players() if target != p]
            self._begin_area_response(
                p, targets, "杀", "南蛮入侵", c,
                source_physical_cards=physical_cards,
            )
        elif c.name in ("万箭齐发", "万剑齐发"):
            targets = [target for target in self.engine.get_alive_players() if target != p]
            self._begin_area_response(
                p, targets, "闪", "万箭齐发", c,
                source_physical_cards=physical_cards,
            )
        elif c.name == "五谷丰登":
            self._begin_five_grains(p, c)
        elif c.name == "桃园结义":
            targets = self.engine.get_peach_garden_targets(p)
            self._continue_peach_garden(p, c, targets)
        elif c.name == "火攻" and t:
            self._begin_fire_attack(p, c, t)
        elif c.name in ("过河拆桥", "顺手牵羊") and t:
            self._begin_target_card_choice(
                p, c.name, t, source_card=c
            )
        elif c.name == "决斗" and t:
            self._begin_duel(p, t, c)

    def _continue_peach_garden(self, actor, card, targets):
        if not targets:
            self._xd()
            return
        target = targets.pop(0)
        self._begin_nullification(
            actor, card, target,
            lambda target=target, targets=targets: self._resolve_peach_garden_target(actor, card, target, targets),
            on_cancel=lambda targets=targets: self._continue_peach_garden(actor, card, targets),
        )

    def _resolve_peach_garden_target(self, actor, card, target, targets):
        if target.hp < target.max_hp:
            self.engine.recover(target)
            self.msg(f"{target.general.name} 受到【桃园结义】影响，回复1点体力")
        self._continue_peach_garden(actor, card, targets)

    def _begin_borrowed_sword_target_choice(
        self, actor, card, wielder
    ):
        """选择持刀者后进入第二目标选择；此时尚未提交或移动牌。"""
        if not self.engine.is_legal_play_target(
            actor, card, wielder
        ):
            self.hint("请选择有武器且攻击范围内存在目标的其他角色")
            return False
        victims = self.engine.borrowed_sword_victims(wielder)
        self.borrowed_sword_choice = {
            "actor": actor,
            "card": card,
            "wielder": wielder,
            "victims": victims,
            "victim": None,
            "source": self._hand_card_center(actor, self.idx),
        }
        self.pending_target = wielder
        self.pending_targets = []
        self.hint(
            f"请选择 {wielder.general.name} 要使用【杀】的目标，"
            "然后点击【确定】",
            5000,
        )
        return True

    def _select_borrowed_sword_victim(self, victim):
        context = self.borrowed_sword_choice
        if not context:
            return False
        fresh_victims = self.engine.borrowed_sword_victims(
            context["wielder"]
        )
        context["victims"] = fresh_victims
        if victim not in fresh_victims:
            self.hint("请选择持刀者攻击范围内的角色")
            return False
        context["victim"] = victim
        self.pending_targets = [victim]
        self.hint(
            f"已选择 {context['wielder'].general.name} 对 "
            f"{victim.general.name} 使用【杀】，点击【确定】执行",
            5000,
        )
        return True

    def _can_confirm_borrowed_sword(self):
        context = self.borrowed_sword_choice
        if not context:
            return False
        victim = context.get("victim")
        return bool(
            victim
            and self.engine.can_submit_play_card(
                context["actor"],
                context["card"],
                (context["wielder"], victim),
            )
        )

    def _cancel_borrowed_sword_target_choice(self):
        self.borrowed_sword_choice = None
        self.pending_target = None
        self.pending_targets = []
        self.hint("已取消【借刀杀人】的目标选择")

    def _resolve_borrowed_sword_target(self, victim=None):
        context = self.borrowed_sword_choice
        if not context:
            return
        victim = victim or context.get("victim")
        actor = context["actor"]
        card = context["card"]
        wielder = context["wielder"]
        source = context["source"]
        if (
            victim is None
            or not self.engine.can_submit_play_card(
                actor, card, (wielder, victim)
            )
        ):
            self.hint("【借刀杀人】的目标已经失效，请重新选择")
            return
        self.borrowed_sword_choice = None
        if not self.engine.play_card(actor, card, wielder):
            self.hint("【借刀杀人】使用失败")
            return
        self._reset_play_timer()
        self.play_card_sound(actor, card.name, card)
        self.borrowed_sword_resolution = {"actor": actor, "card": card, "wielder": wielder, "victim": victim}
        self.clear_selection()
        self._queue_borrowed_sword_animation(
            card, source, actor, wielder, victim,
            on_complete=self._begin_borrowed_sword_response,
        )
        self.msg(f"{actor.general.name} 令 {wielder.general.name} 对 {victim.general.name} 使用【杀】")

    def _begin_borrowed_sword_response(self):
        self._begin_card_use_trigger_window(
            self._resolve_borrowed_sword_after_card_use
        )

    def _resolve_borrowed_sword_after_card_use(self):
        context = self.borrowed_sword_resolution
        if not context:
            return
        self._begin_nullification(
            context["actor"], context["card"], context["wielder"],
            lambda: self._start_response(
                context["wielder"], context["actor"], "杀", "借刀杀人",
                context["card"], response_action="使用",
                on_success=self._complete_borrowed_sword_slash_response,
            ),
            on_cancel=self._cancel_borrowed_sword,
        )

    def _cancel_borrowed_sword(self):
        context = self.borrowed_sword_resolution
        if context:
            self.msg(f"对 {context['wielder'].general.name} 的【借刀杀人】被抵消")
        self.borrowed_sword_resolution = None
        self._xd()

    def _use_borrowed_sword_slash(self, wielder, slash, source):
        context = self.borrowed_sword_resolution
        if not context:
            self._xd()
            return
        victim = context["victim"]
        if not self._activate_forced_slash_event(
            wielder, [slash], victim, slash.name
        ):
            self._xd()
            return
        self.borrowed_sword_resolution = None
        self.wd = False; self.dt = None; self.da = None
        self._queue_card_animation(
            slash, source,
            on_complete=lambda victim=victim, wielder=wielder, slash=slash: self.ed(victim, wielder, slash),
            blocking=True
        )
        self.msg(f"{wielder.general.name} 被迫对 {victim.general.name} 使用【杀】")

    def _refuse_borrowed_sword(self):
        context = self.borrowed_sword_resolution
        if not context:
            self._xd()
            return
        actor, wielder = context["actor"], context["wielder"]
        weapon = self.engine.transfer_weapon(wielder, actor)
        self.borrowed_sword_resolution = None
        self.wd = False; self.dt = None; self.da = None
        self.ai_response_at = 0
        if weapon:
            self.msg(f"{wielder.general.name} 未出【杀】，将【{weapon.name}】交给 {actor.general.name}")
        self._xd()

    def _begin_target_card_choice(
        self, actor, trick_name, target, on_choice=None, choices=None,
        on_choice_with_context=False, source_card=None,
    ):
        if choices is None:
            choices = [("hand", i, card) for i, card in enumerate(target.hand)]
            choices += [("equipment", i, card) for i, card in enumerate(target.equipment)]
            choices += [("judgment", i, card) for i, card in enumerate(target.judgment_area)]
        if not choices:
            return
        self.target_card_choice = {
            "actor": actor, "trick": trick_name, "target": target,
            "choices": choices, "on_choice": on_choice,
            "on_choice_with_context": on_choice_with_context,
            "source_card": source_card,
        }
        self.target_card_choice_rects = []
        if actor.is_ai:
            choice = (
                choose_control_card_choice(choices)
                if trick_name in ("过河拆桥", "顺手牵羊", "技能获得")
                else choices[0]
            )
            self._resolve_target_card_choice(choice, None)
        else:
            self.hint(
                f"请选择 {target.general.name} 的一张手牌、装备或判定牌",
                5000,
            )

    def _resolve_target_card_choice(self, choice, source_rect):
        context = self.target_card_choice
        if not context:
            return
        actor, target, trick_name = context["actor"], context["target"], context["trick"]
        zone, index, card = choice
        if zone == "hand" and not target.is_ai:
            source = self._hand_card_center(target, index)
        elif zone == "equipment" and not target.is_ai:
            source = self._equipment_card_center(target, index)
        elif source_rect:
            source = source_rect.center
        else:
            source = self._player_center(target)
        self.target_card_choice = None
        self.target_card_choice_rects = []
        if context.get("on_choice"):
            if context.get("on_choice_with_context"):
                context["on_choice"](card, zone, source)
            else:
                context["on_choice"](card)
            return
        result = self.engine.resolve_target_card_trick(
            actor,
            trick_name,
            target,
            card,
            source_card=context.get("source_card"),
        )
        if not result:
            return
        face_up = zone != "hand"
        if trick_name == "顺手牵羊":
            self._queue_hand_gain_animation(
                actor,
                card,
                source,
                face_up=True,
                on_complete=self._xd,
            )
        else:
            def after_discard_animation():
                if isinstance(result, TrickCardDiscardEvent):
                    self._begin_global_triggered_skill_sequence(
                        SkillTiming.CARD_DISCARDED_BY_TRICK,
                        result,
                        self._xd,
                    )
                else:
                    self._xd()

            self._queue_card_animation(
                card,
                source,
                face_up=face_up,
                blocking=True,
                on_complete=after_discard_animation,
            )

    def _complete_snatch_animation(self, actor, card):
        item = next((item for item in self.waiting_cards if item["card"] is card), None)
        source = item["pos"] if item else self._player_center(actor)
        if item:
            self.waiting_cards.remove(item)
        self.hidden_draw_cards.discard(self._card_token(card))
        self._queue_hand_gain_animation(actor, card, source, face_up=not actor.is_ai)

    # ===== 无懈可击 =====
    def _begin_nullification(self, actor, trick_card, target, on_resolve, on_cancel=None):
        """建立逐张响应链；每张无懈直接响应当前链顶的牌。"""
        if not any(
            p.alive and any(card.name == "无懈可击" for card in p.hand)
            for p in self.engine.state.players
        ):
            on_resolve()
            return
        self.nullification_context = {
            "actor": actor, "card": trick_card, "target": target,
            "on_resolve": on_resolve, "on_cancel": on_cancel,
            "effect_active": True,
            "chain_top": trick_card,
            "chain": [trick_card],
        }
        self._advance_nullification()

    def _advance_nullification(self):
        """每张【无懈可击】使用时的技能结算完毕后再开放下一轮响应。"""
        self._begin_card_use_trigger_window(
            self._resolve_nullification_after_card_use
        )

    def _resolve_nullification_after_card_use(self):
        """同时向全场开放响应窗口，不公开任何角色是否持有无懈。"""
        context = self.nullification_context
        if not context:
            return
        holders = [
            p for p in self._players_from_actor(self.engine.get_current_player())
            if p.alive and any(card.name == "无懈可击" for card in p.hand)
        ]
        if not holders:
            self._finish_nullification_chain()
            return

        human_holder = next((p for p in holders if not p.is_ai), None)
        willing_ai = next(
            (p for p in holders if p.is_ai and self._should_ai_play_nullification(p)),
            None,
        )
        # 有人类可响应时，只让“决定出牌”的 AI 参与抢先；无人类持有时，
        # 即使 AI 决定放弃，也保留一个短暂的全场响应窗口后再结束。
        self.nullification_ai_player = willing_ai
        if human_holder is None and self.nullification_ai_player is None:
            self.nullification_ai_player = next((p for p in holders if p.is_ai), None)

        self.idx = None
        self.pending_target = None
        self.wd = True
        self.dt = human_holder or self.nullification_ai_player
        self.da = context["actor"]
        self.response_card_name = "无懈可击"
        self.response_source_name = "无懈可击"
        self.response_source_card = context["chain_top"]
        self.response_time_remaining = PLAY_TIME_LIMIT_MS
        self.response_timer_last_tick = pygame.time.get_ticks()
        self.ai_response_at = (
            pygame.time.get_ticks() + AI_DELAY_MS
            if self.nullification_ai_player else 0
        )
        effect_text = (
            f"{context['target'].general.name} 的【{context['chain_top'].name}】效果"
            if context["target"] else f"【{context['chain_top'].name}】"
        )
        self.hint(f"是否有角色对{effect_text}使用【无懈可击】？", 5000)

    def _finish_nullification_chain(self):
        context = self.nullification_context
        if not context:
            return
        effect_active = context["effect_active"]
        callback = context["on_resolve"] if effect_active else context["on_cancel"]
        card, target = context["card"], context["target"]
        self.nullification_context = None
        self.nullification_ai_player = None
        self.wd = False; self.dt = None; self.da = None
        self.ai_response_at = 0
        self.response_source_card = None
        if not effect_active:
            if callback:
                callback()
            else:
                self._cancel_trick(card, target)
        elif callback:
            callback()

    def _resolve_ai_nullification_window(self):
        player = self.nullification_ai_player
        self.nullification_ai_player = None
        self.ai_response_at = 0
        if not player or not self.nullification_context:
            return
        card = next((c for c in player.hand if c.name == "无懈可击"), None)
        if card and self._should_ai_play_nullification(player):
            self._play_nullification(
                player, card, self._hand_card_center(player, player.hand.index(card))
            )
        else:
            self._finish_nullification_chain()

    def _play_nullification(self, player, card, source):
        context = self.nullification_context
        if not context or card not in player.hand:
            return
        self.clear_hint()
        countered = context["chain_top"]
        self.engine.discard_from_hand(player, card, "打出无懈可击")
        context["effect_active"] = not context["effect_active"]
        context["chain_top"] = card
        context["chain"].append(card)
        self.nullification_ai_player = None
        self.wd = False; self.dt = None; self.da = None
        self.ai_response_at = 0
        self.engine.record_card_use(
            player,
            card,
            (card,),
            (
                (context["target"].seat,)
                if context.get("target") is not None else ()
            ),
        )
        self.msg(f"{player.general.name} 对【{countered.name}】打出【无懈可击】")
        self.play_card_sound(player, "无懈可击")
        self._queue_card_animation(
            card, source, blocking=True, on_complete=self._advance_nullification
        )

    def _pass_nullification(self):
        player = self.dt
        # 人类放弃只代表自己不抢先响应；若 AI 决定响应，仍等待其延迟出牌。
        if player and not player.is_ai and self.nullification_ai_player:
            self.idx = None
            self.dt = self.nullification_ai_player
            self.response_time_remaining = PLAY_TIME_LIMIT_MS
            self.response_timer_last_tick = pygame.time.get_ticks()
            self.hint("等待其他角色响应【无懈可击】……", 5000)
            return
        self._finish_nullification_chain()

    def _ai_wants_original_trick_effect(self, player, context):
        """判断原锦囊保持生效是否符合该 AI 的利益。"""
        card = context["card"]
        actor = context.get("actor")
        target = context.get("target")

        def is_friend(other):
            return bool(
                other and (
                    other.seat == player.seat
                    or other.general.kingdom == player.general.kingdom
                )
            )

        beneficial = {"无中生有", "桃园结义", "五谷丰登"}
        harmful = {
            "火攻", "决斗", "南蛮入侵", "万箭齐发", "万剑齐发",
            "过河拆桥", "顺手牵羊", "借刀杀人", "乐不思蜀", "兵粮寸断",
        }

        if card.name in beneficial:
            beneficiary = target or actor
            return is_friend(beneficiary)
        if card.name in harmful:
            # 有害锦囊命中敌方符合利益，命中自己或友方则应抵消。
            return not is_friend(target)
        if card.name == "铁索连环" and target:
            # 对友方：已横置时希望生效以解除；对敌方则相反。
            return target.chained if is_friend(target) else not target.chained
        if card.name == "闪电":
            return not is_friend(target)
        # 未专门分类的锦囊：支持友方使用的牌，阻止敌方针对友方的牌。
        if target:
            return not is_friend(target)
        return is_friend(actor)

    def _should_ai_play_nullification(self, player):
        context = self.nullification_context
        if not context:
            return False
        desired_active = self._ai_wants_original_trick_effect(player, context)
        # 每张无懈响应当前链顶并翻转原锦囊状态；仅在翻转后更符合利益时使用。
        return context["effect_active"] != desired_active

    def _begin_area_response(
        self, actor, targets, required_card, source_name, source_card=None,
        source_physical_cards=(),
    ):
        living_targets = [target for target in targets if target.alive]
        if not living_targets:
            return
        physical_cards = tuple(source_physical_cards)
        self.response_queue = [
            (
                target, actor, required_card, source_name, source_card,
                physical_cards,
            )
            for target in living_targets
        ]
        self._continue_response_queue()

    def _begin_duel(self, actor, target, source_card=None):
        if not actor or not target or not actor.alive or not target.alive:
            return
        self.duel_active = True
        self.msg(f"{actor.general.name} 与 {target.general.name} 开始决斗")
        self._start_response(
            target, actor, "杀", "决斗", source_card,
            on_success=lambda player, opponent, _card, _physical_cards:
                self._continue_duel(player, opponent),
        )

    def _continue_duel(self, player, opponent):
        if not self.duel_active or not player.alive or not opponent.alive:
            self.duel_active = False
            self._xd()
            return
        self._start_response(
            opponent, player, "杀", "决斗", self.response_source_card,
            on_success=lambda responder, challenger, _card, _physical_cards:
                self._continue_duel(responder, challenger),
        )

    def _resolve_duel_failure(self, loser, reason):
        winner = self.da
        self.duel_active = False
        self.msg(f"{loser.general.name} {reason}，决斗失败")
        self._apply_damage(
            loser, 1, actor=winner, source_card=self.response_source_card,
            on_complete=self._xd
        )

    def _continue_response_queue(self):
        while self.response_queue:
            (
                target, actor, required_card, source_name, source_card,
                source_physical_cards,
            ) = self.response_queue.pop(0)
            if target.alive:
                self._begin_nullification(
                    actor, source_card, target,
                    lambda target=target, actor=actor, required_card=required_card,
                           source_name=source_name, source_card=source_card,
                           source_physical_cards=source_physical_cards:
                        self._start_response(
                            target, actor, required_card, source_name,
                            source_card,
                            source_physical_cards=source_physical_cards,
                        ),
                    on_cancel=lambda target=target, source_card=source_card:
                        self._cancel_area_target(target, source_card),
                )
                return True
        return False

    def _cancel_area_target(self, target, source_card):
        self.msg(f"{target.general.name} 的【{source_card.name}】效果被抵消")
        self._continue_response_queue()

    def _players_from_actor(self, actor):
        players = self.engine.state.players
        if not players:
            return []
        start = actor.seat if actor else self.engine.state.current_turn
        return [players[(start + i) % len(players)] for i in range(len(players))]

    def _push_resolution_frame(self, event_type, state):
        """冻结当前父结算，并返回具有稳定编号的通用结算帧。"""
        stack = getattr(self, "resolution_stack", None)
        if stack is None:
            stack = []
            self.resolution_stack = stack
        event_id = getattr(self, "next_resolution_event_id", 1)
        self.next_resolution_event_id = event_id + 1
        parent_event_id = stack[-1].event_id if stack else None
        frame = ResolutionFrame(
            event_id=event_id,
            event_type=event_type,
            parent_event_id=parent_event_id,
            state=state,
        )
        stack.append(frame)
        return frame

    def _pop_resolution_frame(self, event_type):
        stack = getattr(self, "resolution_stack", [])
        if not stack:
            return None
        frame = stack[-1]
        if frame.event_type != event_type:
            raise RuntimeError(
                f"结算栈顶为 {frame.event_type}，不能按 {event_type} 恢复"
            )
        return stack.pop()

    def _begin_dying(
        self, target, actor, on_complete=None, damage_event=None
    ):
        if target.hp > 0:
            if on_complete:
                on_complete()
            return
        # 暂停当前结算。每次濒死都拥有独立上下文，因此可在濒死中继续插入濒死。
        self._push_resolution_frame("dying", {
            "dying_target": self.dying_target,
            "dying_queue": self.dying_queue,
            "dying_complete_callback": self.dying_complete_callback,
            "response_queue": self.response_queue,
            "wd": self.wd,
            "dt": self.dt,
            "da": self.da,
            "response_card_name": self.response_card_name,
            "response_source_name": self.response_source_name,
            "response_source_card": self.response_source_card,
            "response_source_physical_cards":
                getattr(self, "response_source_physical_cards", ()),
            "active_prompt": self.active_prompt,
            "ai_response_at": self.ai_response_at,
            "response_time_remaining": self.response_time_remaining,
            "idx": self.idx,
            "pending_target": self.pending_target,
        })
        self.response_queue = []
        self.active_prompt = None
        self.wd = False
        self.dt = None
        self.da = None
        self.dying_target = target
        self.dying_complete_callback = on_complete
        self.dying_queue = []
        self.msg(f"{target.general.name} 进入濒死，开始求桃")
        event = DyingEvent(
            target=target,
            damage_event=damage_event,
        )
        self._begin_global_triggered_skill_sequence(
            SkillTiming.ENTER_DYING,
            event,
            lambda target=target, actor=actor:
                self._start_dying_rescue(target, actor),
        )

    def _start_dying_rescue(self, target, actor):
        """进入濒死时技能结算完毕后，再建立本次求桃顺序。"""
        if self.dying_target is not target:
            return
        if target.hp > 0:
            self._finish_dying(saved=True)
            return
        self.dying_queue = [
            player for player in self._players_from_actor(actor)
            if player.alive
        ]
        self._continue_dying_queue()

    def _continue_dying_queue(self):
        if not self.dying_target or self.dying_target.hp > 0:
            self._finish_dying(saved=True)
            return True
        while self.dying_queue:
            helper = self.dying_queue.pop(0)
            if helper.alive:
                self._start_response(helper, self.dying_target, "桃", "濒死求桃")
                allowed = self._dying_response_names(helper)
                self.hint(f"询问 {helper.general.name} 是否使用【{'】或【'.join(allowed)}】救 {self.dying_target.general.name}", 5000)
                return True
        self._finish_dying(saved=False)
        return False

    def _finish_dying(self, saved):
        target = self.dying_target
        callback = self.dying_complete_callback
        if target and not saved and target.hp <= 0:
            discarded_cards = (
                target.hand[:] + target.equipment[:]
                + target.judgment_area[:]
            )
            discard_sources = []
            for card in discarded_cards:
                if card in target.hand:
                    discard_sources.append(
                        self._hand_card_center(
                            target, target.hand.index(card)
                        )
                    )
                elif card in target.equipment:
                    discard_sources.append(
                        self._equipment_card_center(
                            target, target.equipment.index(card)
                        )
                    )
                else:
                    discard_sources.append(self._player_center(target))
            died = self.engine.finalize_death(target)
            if died:
                self.play_general_death_sound(target)
            self._queue_discard_display(
                discarded_cards, discard_sources
            )
            for message in self.engine.log:
                self.msg(message)
            self.engine.log.clear()
            self._play_visual_effect("killer", target)
            self._cg()
            if self.go:
                callback = None
        elif target and saved:
            self.msg(f"{target.general.name} 脱离濒死")
        resolution_frame = self._pop_resolution_frame("dying")
        frame = resolution_frame.state if resolution_frame else None
        if frame:
            self.dying_target = frame["dying_target"]
            self.dying_queue = frame["dying_queue"]
            self.dying_complete_callback = frame["dying_complete_callback"]
            self.response_queue = frame["response_queue"]
            self.wd = frame["wd"]
            self.dt = frame["dt"]
            self.da = frame["da"]
            self.response_card_name = frame["response_card_name"]
            self.response_source_name = frame["response_source_name"]
            self.response_source_card = frame["response_source_card"]
            self.response_source_physical_cards = (
                frame.get("response_source_physical_cards", ())
            )
            self.active_prompt = frame["active_prompt"]
            self.ai_response_at = frame["ai_response_at"]
            self.response_time_remaining = frame["response_time_remaining"]
            self.response_timer_last_tick = pygame.time.get_ticks()
            self.idx = frame["idx"]
            self.pending_target = frame["pending_target"]
        else:
            self.dying_target = None
            self.dying_queue = []
            self.dying_complete_callback = None
            self.response_queue = []
            self.wd = False
            self.dt = None
            self.da = None
            self.ai_response_at = 0
            self.response_time_remaining = 0
            self.response_source_card = None
            self.response_source_physical_cards = ()
            self.response_action = "打出"
            self.response_success_callback = None
            self.active_prompt = None
        if self.go:
            self.dying_target = None
            self.dying_queue = []
            self.dying_complete_callback = None
            self.response_queue = []
            self.wd = False
            self.dt = None
            self.da = None
            self.active_prompt = None
        if callback:
            callback()

    def _use_peach_for_dying(self, helper, peach, source=None):
        target = self.dying_target
        if not target:
            self._xd()
            return
        # AI意愿必须在真正改变规则状态前再次校验。濒死可以嵌套，响应询问与
        # 实际提交之间的当前濒死者也可能发生变化，不能只依赖询问阶段的判断。
        # 真人仍可按规则自行选择是否救敌方。
        if (
            helper.is_ai
            and not should_use_peach_for_dying(
                self.engine, helper, target
            )
        ):
            self._skip_dying_peach(helper)
            return
        if (
            peach not in helper.hand
            or peach.name not in self._dying_response_names(helper)
        ):
            self._skip_dying_peach(helper)
            return
        if source is None:
            source = self._hand_card_center(helper, helper.hand.index(peach) if peach in helper.hand else -1)
        self.engine.discard_from_hand(helper, peach, "濒死救援使用牌")
        self.engine.recover(target)
        self.engine.record_card_use(
            helper, peach, (peach,), (target.seat,)
        )
        self.play_card_sound(helper, peach.name, peach)
        # 负体力时可能需要多张桃/酒；当前救援者仍有机会继续救援。
        if target.hp <= 0 and helper.alive:
            self.dying_queue.insert(0, helper)
        self._queue_card_animation(
            peach, source, self._arrow_target_center(target),
            on_complete=lambda: self._begin_card_use_trigger_window(
                self._continue_dying_queue
            ),
            blocking=True,
            arrow_source=self._play_arrow_source(helper)
        )
        self.msg(f"{helper.general.name} 使用【{peach.name}】救 {target.general.name}")

    def _dying_response_names(self, helper):
        """濒死者本人可以用酒自救；其他角色只能使用桃。"""
        if self.dying_target and helper and helper.seat == self.dying_target.seat:
            return ("桃", "酒")
        return ("桃",)

    def _skip_dying_peach(self, helper):
        target = self.dying_target
        if helper and target:
            allowed = self._dying_response_names(helper)
            self.msg(f"{helper.general.name} 不使用【{'】或【'.join(allowed)}】")
        self.wd = False
        self.dt = None
        self.da = None
        self.ai_response_at = 0
        self._continue_dying_queue()

    def ed(self, t, a, source_card=None):
        self._start_response(t, a, "闪", "杀", source_card)

    def _start_response(
        self, t, a, required_card="闪", source_name="杀", source_card=None,
        response_action="打出", on_success=None, on_failure=None,
        source_physical_cards=(),
    ):
        self.idx = None
        self.pending_target = None
        nullifying_armor = self.engine.armor_nullifies_response_source(
            t, source_name, source_card, a,
            ignore_armor=bool(
                source_name == "杀" and getattr(self, "active_slash_event", None)
                and t.seat in self.active_slash_event.ignores_armor_for
            ),
        )
        if nullifying_armor:
            self.play_equipment_sound(nullifying_armor, t)
            self.msg(
                f"{t.general.name} 的【{nullifying_armor}】令"
                f"【{source_name}】对其无效"
            )
            self._xd()
            return
        self.wd=True
        self.dt=t
        self.da=a
        self.response_card_name = required_card
        self.response_source_name = source_name
        self.response_source_card = source_card
        self.response_source_physical_cards = tuple(source_physical_cards)
        self.response_action = response_action
        self.response_success_callback = on_success
        self.response_failure_callback = on_failure
        self.response_time_remaining = PLAY_TIME_LIMIT_MS
        self.response_timer_last_tick = pygame.time.get_ticks()
        skill = self.engine.get_optional_response_skill(t, required_card)
        if skill:
            if skill.skill_id == "weapon.zhangba":
                self._open_skill_prompt(
                    t, skill.skill_id, skill.name,
                    f"{t.general.name} 是否将两张手牌当【杀】打出？",
                    lambda cards: self._use_zhangba_response(
                        t, a, source_name, source_card, cards
                    ),
                    self._show_regular_response_prompt,
                    selectable_cards=t.hand,
                    required_cards=2,
                    ai_confirm_callback=lambda:
                        should_use_zhangba_response(self.engine, t),
                    ai_select_cards_callback=lambda cards, count:
                        choose_low_value_cards(
                            self.engine, t, cards, count
                        ),
                )
                return
            self.active_prompt = PromptContext(
                prompt_id=self.next_prompt_id,
                prompt_type=PromptType.ACTIVATE_SKILL,
                player_seat=t.seat,
                message=f"{t.general.name} 是否发动【{skill.name}】？",
                skill_id=skill.skill_id,
                skill_name=skill.name,
            )
            self.skill_prompt_cards = []
            self.skill_prompt_required_cards = 0
            self.skill_prompt_selected = set()
            self.skill_prompt_targets = []
            self.skill_prompt_selected_target = None
            self.next_prompt_id += 1
            self.hint(self.active_prompt.message, 5000)
            if t.is_ai:
                self.ai_response_at = pygame.time.get_ticks() + AI_DELAY_MS
            return
        self.active_prompt = None
        self._show_regular_response_prompt()

    def _response_conversion_entry_hit(self, player, option, pos):
        """主界面只识别通用入口类型，不识别具体技能名称。"""
        if option.entry_type == "general_skill":
            rect = self.skill_button_rects.get(
                (player.seat, option.skill.skill_id)
            )
            return bool(rect and rect.collidepoint(pos))
        if option.entry_type == "equipment":
            equipment = self._equipment_at_position(player, pos)
            return bool(
                equipment
                and equipment.name == option.skill.source_name
            )
        return False

    def _play_conversion_option_at(self, player, pos):
        """返回出牌阶段被点击的通用转化入口。"""
        options = (
            self.engine.skills.play_conversion_options(player, "杀")
            + self.engine.skills.active_play_conversion_options(
                self.engine, player
            )
        )
        return next(
            (
                option
                for option in options
                if (
                    option.entry_type == "general_skill"
                    and self._response_conversion_entry_hit(
                        player, option, pos
                    )
                )
            ),
            None,
        )

    def _active_skill_action_at(self, player, pos):
        """返回出牌阶段被点击的通用主动技能动作。"""
        return next(
            (
                action for action in self.engine.active_skill_actions(player)
                if (
                    (rect := self.skill_button_rects.get(
                        (player.seat, action.skill.skill_id)
                    ))
                    and rect.collidepoint(pos)
                )
            ),
            None,
        )

    def _play_conversion_card_disabled(self, player, card):
        """确认态只允许规则指定的材料保持明亮；灰暗不等于移动或弃置。"""
        action = self.pending_skill_action
        if not action:
            return False
        if action.get("action_type") == "active_skill":
            active_action = action.get("active_action")
            return bool(
                active_action and card not in active_action.legal_cards
            )
        if action.get("option") is None:
            return False
        return card not in self.engine.skills.conversion_candidates(
            player, action["option"]
        )

    def _begin_active_skill_selection(self, player, action):
        """建立一次同时选择代价牌与目标的可序列化主动技能提示。"""
        prompt = PromptContext(
            prompt_id=self.next_prompt_id,
            prompt_type=PromptType.CONFIRM_ACTION,
            player_seat=player.seat,
            message=action.prompt,
            skill_id=action.skill.skill_id,
            skill_name=action.skill.name,
            legal_card_ids=tuple(
                card.id for card in action.legal_cards
            ),
            legal_target_seats=tuple(
                target.seat for target in action.legal_targets
            ),
            required_cards=action.required_cards,
            required_targets=action.required_targets,
            window="active_play",
        )
        self.next_prompt_id += 1
        self.pending_skill_action = {
            "action_type": "active_skill",
            "active_action": action,
            "cards": [],
            "choice_prompt": prompt,
        }
        self.idx = None
        self.pending_target = None
        self.pending_targets = []
        self.hint(action.prompt, 5000)
        return True

    def _begin_play_conversion_selection(
        self, player, option, *, replace_active_prompt=False
    ):
        """进入出牌转化选牌；可原子替换另一个尚未提交的出牌提示。"""
        if option.timing == SkillTiming.PLAY_CONVERSION:
            if replace_active_prompt:
                self.active_prompt = None
                self._clear_skill_prompt_callbacks()
                self.wd = False
                self.dt = None
                self.da = None
            candidates = self.engine.skills.conversion_candidates(
                player, option
            )
            if not candidates:
                self.hint(
                    f"当前没有可用于【{option.skill.name}】的牌",
                    4000,
                )
                return False
            fixed_materials = option.fixed_materials
            selected_cards = (
                list(candidates) if fixed_materials else []
            )
            sample_groups = (
                [list(candidates)]
                if fixed_materials
                else (
                    [[candidate] for candidate in candidates]
                    if option.required_cards == 1 else []
                )
            )
            legal_targets = tuple(
                target.seat
                for target in self.engine.state.players
                if any(
                    self.engine.can_submit_active_conversion(
                        player, option, group, (target,)
                    )
                    for group in sample_groups
                )
            )
            # “有效牌需要目标”是牌规则；“当前存在合法目标”是目标规则。
            # 即使全场目标都因距离或禁止指定效果而非法，技能入口和材料仍可选择。
            requires_target = (
                self.engine.card_name_requires_manual_target(
                    option.effective_card_name
                )
            )
            prompt = PromptContext(
                prompt_id=self.next_prompt_id,
                prompt_type=PromptType.CONFIRM_ACTION,
                player_seat=player.seat,
                message=(
                    f"【{option.skill.name}】：请选择"
                    f"{option.required_cards}张牌"
                    + ("和一名目标" if requires_target else "")
                    + f"，当【{option.effective_card_name}】使用"
                ),
                skill_id=option.skill.skill_id,
                skill_name=option.skill.name,
                legal_card_ids=tuple(card.id for card in candidates),
                legal_target_seats=legal_targets,
                required_cards=option.required_cards,
                required_targets=1 if requires_target else 0,
                window="play_conversion",
            )
            self.next_prompt_id += 1
            self.pending_skill_action = {
                "option": option,
                "cards": selected_cards,
                "choice_prompt": prompt,
                "fixed_materials": fixed_materials,
            }
            self.idx = None
            self.pending_target = None
            self.pending_targets = []
            if fixed_materials:
                self.hint(
                    f"【{option.skill.name}】：技能所需的全部牌已纳入，"
                    "请点击【确定】或【取消】",
                    5000,
                )
            else:
                self.hint(prompt.message, 5000)
            return True
        candidates = self.engine.skills.conversion_candidates(
            player, option
        )
        if not self.engine.can_use_slash(player):
            self.hint("本阶段使用【杀】的次数已达上限", 4000)
            return False
        if not candidates:
            self.hint(
                f"当前没有可用于【{option.skill.name}】的牌",
                4000,
            )
            return False
        if replace_active_prompt:
            prompt = self.active_prompt
            if (
                prompt is None
                or prompt.player_seat != player.seat
                or prompt.window != "play"
            ):
                return False
            self.active_prompt = None
            self._clear_skill_prompt_callbacks()
            self.wd = False
            self.dt = None
            self.da = None
            self.response_time_remaining = 0
            self.ai_response_at = 0
        legal_targets = tuple(
            target.seat
            for target in self.engine.state.players
            if any(
                self.engine.can_submit_conversion(
                    player, option, [candidate], (target,)
                )
                for candidate in candidates
            )
        )
        choice_prompt = PromptContext(
            prompt_id=self.next_prompt_id,
            prompt_type=PromptType.CONFIRM_ACTION,
            player_seat=player.seat,
            message=(
                f"【{option.skill.name}】：请选择"
                f"{option.required_cards}张牌和一名目标"
            ),
            skill_id=option.skill.skill_id,
            skill_name=option.skill.name,
            legal_card_ids=tuple(card.id for card in candidates),
            legal_target_seats=legal_targets,
            required_cards=option.required_cards,
            required_targets=1,
            window="play_conversion",
        )
        self.next_prompt_id += 1
        self.pending_skill_action = {
            "option": option,
            "cards": [],
            "choice_prompt": choice_prompt,
        }
        self.idx = None
        self.pending_target = None
        self.pending_targets = []
        self.hint(
            f"【{option.skill.name}】："
            f"请选择{option.required_cards}张牌",
            5000,
        )
        return True

    def _try_replace_play_skill_prompt(self, player, pos):
        """点击另一转化入口时，以新选牌状态覆盖旧的出牌阶段提示。"""
        prompt = self.active_prompt
        if (
            prompt is None
            or prompt.player_seat != player.seat
            or prompt.window != "play"
        ):
            return False
        option = self._play_conversion_option_at(player, pos)
        if option is None:
            return False
        return self._begin_play_conversion_selection(
            player, option, replace_active_prompt=True
        )

    def _use_response_conversion(
        self, player, actor, source_name, source_card, option, cards
    ):
        """执行响应窗口提交的通用牌转化动作。"""
        card_sources = [
            self._owned_card_center(player, card) for card in cards
        ]
        response_action = getattr(self, "response_action", "打出")
        is_use = response_action == "使用"
        try:
            effective_card = self.engine.submit_response_conversion(
                player,
                option,
                cards,
                response_action=response_action,
            )
        except ValueError:
            self._show_regular_response_prompt()
            return
        success_callback = getattr(
            self, "response_success_callback", None
        )
        action_word = getattr(self, "response_action", "打出")
        self.wd = False
        self.dt = None
        self.da = None
        self.msg(
            f"{player.general.name} 发动【{option.skill.name}】，"
            f"将{len(cards)}张牌当【{option.effective_card_name}】"
            f"{action_word}"
        )
        if option.entry_type == "equipment":
            self.play_equipment_sound(option.skill.source_name, player)
        else:
            self.play_skill_sound(player, option.skill.skill_id)
            self.play_card_sound(
                player, option.effective_card_name, effective_card
            )

        def finish_response():
            if success_callback:
                continuation = lambda: success_callback(
                    player, actor, effective_card, tuple(cards)
                )
            else:
                continuation = self._xd
            self._after_successful_response(
                player,
                actor,
                effective_card,
                tuple(cards),
                continuation,
            )

        self._queue_discard_display(
            cards,
            card_sources,
            on_complete=finish_response,
            visual_reason="use" if is_use else "discard",
        )

    def _use_zhangba_response(
        self, player, actor, source_name, source_card, cards
    ):
        if not self.engine.skills.can_convert_zhangba(player, cards):
            self._show_regular_response_prompt()
            return
        card_sources = [
            self._hand_card_center(player, player.hand.index(card))
            for card in cards
        ]
        is_use = getattr(self, "response_action", "打出") == "使用"
        if is_use:
            if not self.engine.stage_owned_cards_for_use(player, cards):
                self._show_regular_response_prompt()
                return
        else:
            for card in cards:
                self.engine.discard_from_hand(
                    player, card, "丈八蛇矛响应转化"
                )
        self.wd = False
        self.dt = None
        self.da = None
        self.msg(f"{player.general.name} 发动【丈八蛇矛】，将两张手牌当【杀】打出")
        self.play_equipment_sound("丈八蛇矛", player)
        success_callback = getattr(
            self, "response_success_callback", None
        )
        virtual_slash = self.engine.skills.build_effective_card("杀", cards)

        def finish_response():
            if success_callback:
                success_callback(
                    player, actor, virtual_slash, tuple(cards)
                )
            else:
                self._xd()

        self._queue_discard_display(
            cards,
            card_sources,
            on_complete=finish_response,
            visual_reason="use" if is_use else "discard",
        )

    def _after_successful_response(
        self, player, actor, effective_card, physical_cards, on_complete
    ):
        """成功提交响应后的统一触发点，实体牌与转化牌共用。"""
        if getattr(self, "engine", None) is None:
            on_complete()
            return
        event = CardResponseEvent(
            player=player,
            effective_card=effective_card,
            physical_cards=tuple(physical_cards),
            action=getattr(self, "response_action", "打出"),
            source_player=actor,
            source_name=getattr(self, "response_source_name", ""),
            source_card=getattr(self, "response_source_card", None),
        )
        self._begin_triggered_skill_sequence(
            player, SkillTiming.AFTER_CARD_RESPONSE, event, on_complete
        )

    def _on_engine_card_use(self, event):
        """缓存牌使用事件；由父牌在效果处理前开放统一“使用时”窗口。"""
        queue = getattr(self, "card_use_event_queue", None)
        if queue is None:
            queue = []
            self.card_use_event_queue = queue
        queue.append(event)

    def _finish_card_use_trigger_window(self):
        """释放一次独立的“使用牌时”技能窗口占用的界面响应状态。"""
        self.card_use_trigger_in_progress = False
        self.active_prompt = None
        self.wd = False
        self.dt = None
        self.da = None
        self.ai_response_at = 0
        self.response_time_remaining = 0
        self._clear_skill_prompt_callbacks()
        self.clear_hint()

    def _begin_card_use_trigger_window(self, on_complete):
        """依次处理待决的“使用牌时”事件，完成后恢复父牌结算。"""
        if getattr(self, "card_use_trigger_in_progress", False):
            return False
        queue = getattr(self, "card_use_event_queue", [])
        while queue:
            event = queue.pop(0)
            actions = self.engine.triggered_skill_actions(
                event.player, SkillTiming.CARD_USE, event
            )
            if actions:
                break
        else:
            on_complete()
            return False
        self.card_use_trigger_in_progress = True

        def finish():
            self._finish_card_use_trigger_window()
            # 同一同步提交中可能连续登记多次使用牌事件；当前技能完整
            # 结算后继续按登记顺序处理，最后才恢复父牌效果。
            self._begin_card_use_trigger_window(on_complete)

        self._continue_triggered_skill_sequence(actions, finish)
        return True

    def _update_card_use_trigger_queue(self):
        """没有专用父牌回调的牌，在下一安全点补开“使用牌时”窗口。"""
        if (
            getattr(self, "card_use_trigger_in_progress", False)
            or self.wd
            or getattr(self, "target_card_choice", None)
            or getattr(self, "five_grains_choice", None)
            or getattr(self, "borrowed_sword_choice", None)
            or getattr(self, "fire_attack_context", None)
            or getattr(self, "judgment_display_in_progress", False)
            or bool(getattr(self, "animations", []))
            or not getattr(self, "card_use_event_queue", [])
        ):
            return
        current = self.engine.get_current_player()

        def finish():
            if (
                current and current.is_ai and self.ai_busy
                and not self.wd and not self.go
            ):
                self._schedule_ai_action()

        self._begin_card_use_trigger_window(finish)

    def _open_skill_prompt(
        self, controller, skill_id, skill_name, message,
        on_confirm, on_cancel, selectable_cards=None, required_cards=0,
        prompt_type=PromptType.ACTIVATE_SKILL,
        ai_confirm_callback=None, ai_select_cards_callback=None,
        selectable_targets=None, ai_select_target_callback=None,
        window="generic",
    ):
        """建立统一可选技能询问，并暂停调用它的父结算。"""
        self.wd = True
        self.dt = controller
        stack = getattr(self, "resolution_stack", [])
        parent_event_id = stack[-1].event_id if stack else None
        prompt_cards = list(selectable_cards or [])
        self.active_prompt = PromptContext(
            prompt_id=self.next_prompt_id,
            prompt_type=prompt_type,
            player_seat=controller.seat,
            message=message,
            skill_id=skill_id,
            skill_name=skill_name,
            parent_event_id=parent_event_id,
            legal_card_ids=tuple(card.id for card in prompt_cards),
            legal_target_seats=tuple(
                target.seat for target in (selectable_targets or [])
            ),
            required_cards=required_cards,
            window=window,
        )
        handlers = getattr(self, "prompt_handlers", None)
        if handlers is None:
            handlers = {}
            self.prompt_handlers = handlers
        handlers[self.next_prompt_id] = {
            "confirm": on_confirm,
            "cancel": on_cancel,
            "ai_confirm": ai_confirm_callback,
            "ai_select_cards": ai_select_cards_callback,
            "ai_select_target": ai_select_target_callback,
        }
        self.next_prompt_id += 1
        self.skill_prompt_cards = prompt_cards
        self.skill_prompt_required_cards = required_cards
        self.skill_prompt_selected = set()
        self.skill_prompt_targets = list(selectable_targets or [])
        self.skill_prompt_selected_target = None
        self.skill_prompt_ai_select_target_callback = ai_select_target_callback
        self.response_time_remaining = PLAY_TIME_LIMIT_MS
        self.response_timer_last_tick = pygame.time.get_ticks()
        self.hint(message, 5000)
        if controller.is_ai:
            self.ai_response_at = pygame.time.get_ticks() + AI_DELAY_MS

    def _begin_triggered_skill_sequence(
        self, controller, timing, event, on_complete
    ):
        """按统一时机依次处理触发技，主流程不识别具体技能名称。"""
        actions = self.engine.triggered_skill_actions(
            controller, timing, event
        )
        self._continue_triggered_skill_sequence_with_state(
            actions, on_complete
        )

    def _begin_global_triggered_skill_sequence(
        self, timing, event, on_complete
    ):
        """按当前回合角色起始的座次顺序处理全场同一时机。"""
        actions = self.engine.global_triggered_skill_actions(
            timing, event
        )
        self._continue_triggered_skill_sequence_with_state(
            actions, on_complete
        )

    def _capture_trigger_prompt_state(self):
        """保存父窗口；技能询问结束后不得遗留成默认【杀】响应状态。"""
        now = pygame.time.get_ticks()
        ai_at = getattr(self, "ai_response_at", 0)
        return {
            "wd": getattr(self, "wd", False),
            "dt": getattr(self, "dt", None),
            "da": getattr(self, "da", None),
            "active_prompt": getattr(self, "active_prompt", None),
            "ai_response_delay": (
                max(0, ai_at - now) if ai_at else 0
            ),
            "response_time_remaining": getattr(
                self, "response_time_remaining", 0
            ),
            "response_card_name": getattr(
                self, "response_card_name", "闪"
            ),
            "response_source_name": getattr(
                self, "response_source_name", "杀"
            ),
            "response_source_card": getattr(
                self, "response_source_card", None
            ),
            "response_source_physical_cards": getattr(
                self, "response_source_physical_cards", ()
            ),
            "response_action": getattr(
                self, "response_action", "打出"
            ),
            "response_success_callback": getattr(
                self, "response_success_callback", None
            ),
            "response_failure_callback": getattr(
                self, "response_failure_callback", None
            ),
            "skill_prompt_cards": list(
                getattr(self, "skill_prompt_cards", [])
            ),
            "skill_prompt_required_cards": getattr(
                self, "skill_prompt_required_cards", 0
            ),
            "skill_prompt_selected": set(
                getattr(self, "skill_prompt_selected", set())
            ),
            "skill_prompt_targets": list(
                getattr(self, "skill_prompt_targets", [])
            ),
            "skill_prompt_selected_target": getattr(
                self, "skill_prompt_selected_target", None
            ),
        }

    def _restore_trigger_prompt_state(self, state):
        now = pygame.time.get_ticks()
        self.wd = state["wd"]
        self.dt = state["dt"]
        self.da = state["da"]
        self.active_prompt = state["active_prompt"]
        delay = state["ai_response_delay"]
        self.ai_response_at = now + delay if delay else 0
        self.response_time_remaining = state[
            "response_time_remaining"
        ]
        self.response_timer_last_tick = now
        self.response_card_name = state["response_card_name"]
        self.response_source_name = state["response_source_name"]
        self.response_source_card = state["response_source_card"]
        self.response_source_physical_cards = state[
            "response_source_physical_cards"
        ]
        self.response_action = state["response_action"]
        self.response_success_callback = state[
            "response_success_callback"
        ]
        self.response_failure_callback = state[
            "response_failure_callback"
        ]
        self.skill_prompt_cards = state["skill_prompt_cards"]
        self.skill_prompt_required_cards = state[
            "skill_prompt_required_cards"
        ]
        self.skill_prompt_selected = state["skill_prompt_selected"]
        self.skill_prompt_targets = state["skill_prompt_targets"]
        self.skill_prompt_selected_target = state[
            "skill_prompt_selected_target"
        ]

    def _continue_triggered_skill_sequence_with_state(
        self, actions, on_complete
    ):
        """技能提示临时覆盖父窗口，序列结束时原子恢复父上下文。"""
        state = self._capture_trigger_prompt_state()

        def finish():
            self._restore_trigger_prompt_state(state)
            on_complete()

        self._continue_triggered_skill_sequence(actions, finish)

    def _continue_triggered_skill_sequence(self, actions, on_complete):
        if not actions:
            on_complete()
            return
        action = actions.pop(0)

        def continue_sequence():
            self._continue_triggered_skill_sequence(actions, on_complete)

        def resolve_action(_selected_cards=None):
            result = self.engine.resolve_triggered_skill(action)
            self._present_skill_resolution(
                result, continue_sequence, action=action
            )

        if action.skill.mandatory:
            resolve_action()
            return
        self._open_skill_prompt(
            action.controller,
            action.skill.skill_id,
            action.skill.name,
            action.prompt,
            resolve_action,
            continue_sequence,
            ai_confirm_callback=lambda action=action:
                self.engine.skills.ai_should_activate_triggered(
                    self.engine, action
                ),
        )

    def _present_skill_resolution(self, result, on_complete, action=None):
        """把规则层结果转换成通用日志、选择、移动和体力表现。"""
        if not result.applied:
            on_complete()
            return
        self._hide_skill_hand_gains_until_animated(result.move_events)
        for message in result.messages:
            self.msg(message)
        if result.announce:
            self.play_skill_sound(result.controller, result.skill.skill_id)

        def continue_after_effects():
            if result.request is None or action is None:
                on_complete()
                return
            self._begin_skill_resolution_request(
                action, result.request, on_complete
            )

        self._animate_skill_move_events(
            list(result.move_events),
            lambda: self._animate_skill_reveal_events(
                list(result.reveal_events),
                lambda: self._apply_hp_loss_events(
                    list(result.hp_loss_events), continue_after_effects
                ),
            ),
        )

    def _animate_skill_reveal_events(self, events, on_complete):
        """用独立展示框消费技能公开事件；不移动实体或占用等待区。"""
        if not events:
            on_complete()
            return
        first = events[0]
        owner = next(
            (
                player for player in self.engine.state.players
                if player.seat == first.owner_seat
            ),
            None,
        )
        owner_name = owner.general.name if owner else "一名角色"
        reason = first.reason or "技能展示"
        self.skill_reveal_panel = {
            "cards": [event.card for event in events],
            "title": f"{owner_name} 展示牌 · {reason}",
            "expires_at": (
                pygame.time.get_ticks()
                + SKILL_REVEAL_PANEL_HOLD_MS
            ),
        }
        # 规则效果已经由引擎提交；展示框只消费公开事件，不承担规则推进。
        on_complete()

    def _apply_hp_loss_events(self, events, on_complete):
        if not events:
            on_complete()
            return
        event = events.pop(0)
        target = event.target
        if not target.alive or event.amount <= 0:
            self._apply_hp_loss_events(events, on_complete)
            return
        self.play_system_sound(
            "damage1" if event.amount == 1 else "damage2"
        )
        self.msg(
            f"{target.general.name} 失去{event.amount}点体力"
            f"（{target.hp}/{target.max_hp}）"
        )

        def finish():
            self._apply_hp_loss_events(events, on_complete)

        if target.hp <= 0:
            self._begin_dying(target, target, on_complete=finish)
        else:
            finish()

    def _begin_skill_resolution_request(
        self, action, request, on_complete
    ):
        if request.kind == "jink_or_gain":
            self._begin_jink_or_gain_request(
                action, request, on_complete
            )
            return
        if request.kind == "damage":
            if (
                not request.legal_targets
                or not isinstance(request.context, DamageEvent)
            ):
                on_complete()
                return
            target = request.legal_targets[0]
            self._apply_damage(
                target,
                damage_event=request.context,
                on_complete=on_complete,
            )
            return
        if request.kind == "judgment":
            event = self.engine.begin_judgment(
                request.judging_player,
                request.judgment_reason,
                request.judgment_rule,
                source_player=request.source_player,
                source_card=request.source_card,
            )
            judged = event.current_card
            if judged is None:
                on_complete()
                return
            self.active_judgment_id = event.judgment_id
            self.judgment_display_in_progress = True
            self.judgment_result_tip = request.prompt
            self._queue_card_animation(
                judged,
                DRAW_SOURCE_POS,
                blocking=True,
                on_complete=lambda: self._begin_judgment_replacement_window(
                    event,
                    lambda final_event: self._finish_skill_judgment_request(
                        action, request, final_event, on_complete
                    ),
                ),
            )
            return
        if request.kind == "choose_target":
            chooser = lambda _targets: (
                self.engine.skills.ai_choose_triggered_target(
                    self.engine, action, request
                )
            )
            self._open_skill_prompt(
                action.controller,
                action.skill.skill_id,
                action.skill.name,
                request.prompt,
                lambda target: self._continue_skill_resolution_request(
                    action, request, target, on_complete
                ),
                lambda: self._continue_skill_resolution_request(
                    action,
                    request,
                    (
                        None
                        if request.optional
                        else (
                            request.legal_targets[0]
                            if request.legal_targets else None
                        )
                    ),
                    on_complete,
                ),
                required_cards=1,
                prompt_type=PromptType.CHOOSE_TARGET,
                selectable_targets=list(request.legal_targets),
                ai_confirm_callback=lambda: chooser([]) is not None,
                ai_select_target_callback=chooser,
            )
            return
        on_complete()

    def _begin_jink_or_gain_request(
        self, action, request, on_complete
    ):
        """通过统一响应窗口处理“打出闪，否则对方获得一张牌”。"""
        if not request.legal_targets or request.source_player is None:
            on_complete()
            return
        target = request.legal_targets[0]
        source = request.source_player
        if not target.alive or not source.alive:
            on_complete()
            return
        self._start_response(
            target,
            source,
            required_card="闪",
            source_name=action.skill.name,
            response_action="打出",
            on_success=lambda *_args:
                self._finish_jink_or_gain_response(on_complete),
            on_failure=lambda:
                self._continue_jink_or_gain_with_gain(
                    source, target, on_complete
                ),
        )
        if self.active_prompt is None and not target.is_ai:
            self.hint(request.prompt, 5000)

    def _finish_jink_or_gain_response(self, on_complete):
        self._finish_skill_request_state()
        on_complete()

    def _continue_jink_or_gain_with_gain(
        self, source, target, on_complete
    ):
        self._finish_skill_request_state()
        self._begin_skill_gain_from_target(
            source, target, on_complete
        )

    def _begin_skill_gain_from_target(
        self, recipient, target, on_complete
    ):
        choices = [
            ("hand", index, card)
            for index, card in enumerate(target.hand)
        ] + [
            ("equipment", index, card)
            for index, card in enumerate(target.equipment)
        ]
        if not choices:
            self.msg(
                f"{target.general.name} 没有可被获得的手牌或装备牌"
            )
            self._finish_skill_request_state()
            on_complete()
            return
        self._begin_target_card_choice(
            recipient,
            "技能获得",
            target,
            on_choice=lambda card, zone, card_source:
                self._resolve_skill_gain_card(
                    recipient, target, card, zone, card_source, on_complete
                ),
            choices=choices,
            on_choice_with_context=True,
        )

    def _resolve_skill_gain_card(
        self, recipient, target, card, zone, card_source, on_complete
    ):
        move = self.engine.transfer_owned_card(
            target, recipient, card, "技能获得"
        )
        if move is None:
            self._finish_skill_request_state()
            on_complete()
            return
        self.msg(
            f"{recipient.general.name} 获得"
            f"{target.general.name} 的一张{('装备牌' if zone == 'equipment' else '手牌')}"
        )

        def finish():
            self._finish_skill_request_state()
            on_complete()

        self._queue_hand_gain_animation(
            recipient,
            card,
            card_source,
            face_up=(zone == "equipment" or not recipient.is_ai),
            on_complete=finish,
        )

    def _finish_skill_request_state(self):
        self.wd = False
        self.dt = None
        self.da = None
        self.active_prompt = None
        self.ai_response_at = 0
        self.response_time_remaining = 0
        self.response_success_callback = None
        self.response_failure_callback = None

    def _continue_skill_resolution_request(
        self, action, request, choice, on_complete
    ):
        result = self.engine.skills.continue_triggered_action(
            self.engine, action, request, choice
        )
        self._present_skill_resolution(
            result, on_complete, action=action
        )

    def _finish_skill_judgment_request(
        self, action, request, event, on_complete
    ):
        final_event = self.engine.finalize_judgment(event)
        judged = final_event.current_card
        if judged is not None:
            suit_name = SUIT_CN.get(judged.suit, judged.suit)
            self.msg(
                f"{final_event.judging_player.general.name} 的"
                f"【{final_event.reason}】判定为{suit_name}{judged.rank}"
            )
            self.judgment_result_success = bool(final_event.result)
            self.judgment_result_tip = (
                f"【{final_event.reason}】判定"
                f"{'成功' if final_event.result else '失败'}"
            )
            self._play_visual_effect(
                "judgegood" if final_event.result else "judgebad",
                position=self._waiting_card_position(judged),
            )

        def finish():
            self.judgment_result_tip = None
            self.judgment_result_success = None
            self.judgment_display_in_progress = False
            self.active_judgment_id = None
            self._continue_skill_resolution_request(
                action, request, final_event, on_complete
            )

        self._schedule_phase_transition(
            finish, delay=JUDGMENT_RESULT_HOLD_MS
        )

    def _begin_judgment_replacement_window(
        self, event, on_complete, handled=None, saved_state=None
    ):
        """依座次处理通用改判机会；主流程不识别任何改判技能名。"""
        handled = set(handled or ())
        if saved_state is None:
            saved_state = {
                "wd": self.wd,
                "dt": self.dt,
                "da": self.da,
                "active_prompt": self.active_prompt,
            }
        actions = [
            action for action in
            self.engine.skills.judgment_replacement_actions(
                self.engine, event
            )
            if (action.controller.seat, action.skill.skill_id) not in handled
        ]
        if not actions:
            self.wd = saved_state["wd"]
            self.dt = saved_state["dt"]
            self.da = saved_state["da"]
            self.active_prompt = saved_state["active_prompt"]
            self.response_timer_last_tick = pygame.time.get_ticks()
            on_complete(event)
            return
        action = actions[0]
        key = (action.controller.seat, action.skill.skill_id)
        next_handled = handled | {key}

        def continue_window(next_event):
            self._begin_judgment_replacement_window(
                next_event, on_complete, next_handled, saved_state
            )

        def apply_replacement(cards):
            if len(cards) != 1:
                continue_window(event)
                return
            replacement = cards[0]
            source = self._owned_card_center(
                action.controller, replacement
            )
            replacement_position = self._waiting_card_position(
                event.current_card
            )
            current_action = next(
                (
                    candidate for candidate in
                    self.engine.skills.judgment_replacement_actions(
                        self.engine, event
                    )
                    if candidate.controller.seat == action.controller.seat
                    and candidate.skill.skill_id == action.skill.skill_id
                ),
                action,
            )
            result = self.engine.skills.resolve_judgment_replacement(
                self.engine, current_action, replacement
            )
            if not result.applied:
                continue_window(event)
                return
            self._hide_skill_hand_gains_until_animated(
                result.move_events
            )
            for message in result.messages:
                self.msg(message)
            self.play_skill_sound(
                result.action.controller, result.action.skill.skill_id
            )
            self._queue_card_animation(
                replacement,
                source,
                blocking=True,
                waiting_position=replacement_position,
                on_complete=lambda: self._animate_skill_move_events(
                    list(result.move_events),
                    lambda: continue_window(result.event),
                ),
            )

        ai_card = self.engine.skills.ai_choose_judgment_replacement(
            self.engine, action
        )
        self._open_skill_prompt(
            action.controller,
            action.skill.skill_id,
            action.skill.name,
            action.prompt,
            apply_replacement,
            lambda: continue_window(event),
            selectable_cards=list(action.candidates),
            required_cards=1,
            ai_confirm_callback=lambda: ai_card is not None,
            ai_select_cards_callback=lambda _cards, _required: (
                [ai_card] if ai_card is not None else []
            ),
            window="judgment_replacement",
        )

    def _hide_skill_hand_gains_until_animated(self, move_events):
        """规则已获得但动画未开始的真人手牌，先从手牌绘制层隐藏。"""
        hidden_cards = getattr(self, "hidden_draw_cards", None)
        if hidden_cards is None:
            hidden_cards = set()
            self.hidden_draw_cards = hidden_cards
        players = {
            player.seat: player for player in self.engine.state.players
        }
        for move in move_events:
            if move.to_zone != "hand" or move.to_player_seat is None:
                continue
            recipient = players.get(move.to_player_seat)
            if recipient is not None and not recipient.is_ai:
                hidden_cards.add(self._card_token(move.card))

    def _animate_skill_move_events(self, events, on_complete):
        if not events:
            on_complete()
            return
        move = events.pop(0)
        if (
            move.batch_id is not None
            and move.batch_size > 1
            and move.to_zone == "hand"
            and move.to_player_seat is not None
        ):
            batch = [move]
            while (
                events
                and events[0].batch_id == move.batch_id
                and events[0].to_zone == "hand"
                and events[0].to_player_seat == move.to_player_seat
            ):
                batch.append(events.pop(0))
            self._animate_skill_hand_gain_batch(
                batch,
                lambda: self._animate_skill_move_events(
                    events, on_complete
                ),
            )
            return
        if move.to_zone in ("discard", "discard_pile"):
            owner = next(
                (
                    player for player in self.engine.state.players
                    if player.seat == move.from_player_seat
                ),
                None,
            )
            source = (
                self._player_center(owner)
                if owner is not None else DRAW_SOURCE_POS
            )
            self._queue_card_animation(
                move.card,
                source,
                face_up=True,
                blocking=True,
                visual_reason="skill_cost_discard",
                on_complete=lambda: self._animate_skill_move_events(
                    events, on_complete
                ),
            )
            return
        if move.to_zone != "hand" or move.to_player_seat is None:
            self._animate_skill_move_events(events, on_complete)
            return
        recipient = next(
            (
                player for player in self.engine.state.players
                if player.seat == move.to_player_seat
            ),
            None,
        )
        if recipient is None:
            self._animate_skill_move_events(events, on_complete)
            return
        source_owner = next(
            (
                player for player in self.engine.state.players
                if player.seat == move.from_player_seat
            ),
            None,
        )
        waiting_item = next(
            (
                item for item in getattr(self, "waiting_cards", [])
                if item.get("card") is move.card
                and not item.get("is_visual_copy")
            ),
            None,
        )
        source = (
            waiting_item["pos"] if waiting_item
            else DRAW_SOURCE_POS if move.from_zone == "draw_pile"
            else (
                self._player_center(source_owner)
                if source_owner is not None
                else self._player_center(recipient)
            )
        )
        if waiting_item:
            self.waiting_cards.remove(waiting_item)
        self._queue_hand_gain_animation(
            recipient,
            move.card,
            source,
            face_up=(
                move.visibility == "public"
                or not recipient.is_ai
            ),
            on_complete=lambda: self._animate_skill_move_events(
                events, on_complete
            ),
        )

    def _animate_skill_hand_gain_batch(self, moves, on_complete):
        """同一规则批次获得多张牌时，让所有主体动画同时开始。"""
        if not moves:
            on_complete()
            return
        recipient = next(
            (
                player for player in self.engine.state.players
                if player.seat == moves[0].to_player_seat
            ),
            None,
        )
        if recipient is None:
            on_complete()
            return
        batch_start = pygame.time.get_ticks()
        remaining = [len(moves)]

        def finish_one():
            remaining[0] -= 1
            if remaining[0] == 0:
                on_complete()

        for index, move in enumerate(moves):
            source_owner = next(
                (
                    player for player in self.engine.state.players
                    if player.seat == move.from_player_seat
                ),
                None,
            )
            waiting_item = next(
                (
                    item for item in getattr(self, "waiting_cards", [])
                    if item.get("card") is move.card
                    and not item.get("is_visual_copy")
                ),
                None,
            )
            source = (
                waiting_item["pos"] if waiting_item
                else DRAW_SOURCE_POS if move.from_zone == "draw_pile"
                else (
                    self._player_center(source_owner)
                    if source_owner is not None
                    else self._player_center(recipient)
                )
            )
            if waiting_item:
                self.waiting_cards.remove(waiting_item)
            dest = None
            if recipient.is_ai:
                center = self._player_center(recipient)
                offset = int(
                    (index - (len(moves) - 1) / 2) * 28
                )
                dest = (center[0] + offset, center[1])
            self._queue_hand_gain_animation(
                recipient,
                move.card,
                source,
                face_up=(
                    move.visibility == "public"
                    or not recipient.is_ai
                ),
                on_complete=finish_one,
                dest=dest,
                start=batch_start,
            )

    def _prompt_handler(self, prompt_id):
        return getattr(self, "prompt_handlers", {}).get(prompt_id, {})

    def _clear_skill_prompt_callbacks(self, prompt_id=None):
        handlers = getattr(self, "prompt_handlers", None)
        if handlers is not None:
            if prompt_id is None:
                handlers.clear()
            else:
                handlers.pop(prompt_id, None)
        self.skill_prompt_cards = []
        self.skill_prompt_required_cards = 0
        self.skill_prompt_selected = set()
        self.skill_prompt_targets = []
        self.skill_prompt_selected_target = None
        self.skill_prompt_ai_select_target_callback = None

    def _show_regular_response_prompt(self):
        """显示当前响应所需的手牌选择，不改变父结算上下文。"""
        t = self.dt
        if not t:
            return
        self.hint(f"{t.general.name} 需要打出【{self.response_card_name}】", 5000)
        if t.is_ai:
            self.ai_response_at = pygame.time.get_ticks() + AI_DELAY_MS
        else:
            allowed = self._allowed_response_names(t)
            names = "】或【".join(allowed)
            options = self.engine.skills.response_conversion_options(
                t, self.response_card_name
            )
            conversion_entries = [
                f"【{option.skill.name}】" for option in options
            ]
            if any(c.name in allowed for c in t.hand) or conversion_entries:
                suffix = (
                    f"，也可点击{'或'.join(conversion_entries)}进行转化"
                    if conversion_entries else ""
                )
                self.hint(
                    f"请选择【{names}】后点击【确定】{suffix}，"
                    "或点击【取消】",
                    5000,
                )
            else:
                self.hint(f"没有可用的【{names}】，请点击【取消】", 5000)

    def _confirm_skill_prompt(self):
        """确认当前可选技能提示；界面不参与具体技能规则分派。"""
        t = self.dt
        prompt = self.active_prompt
        if (
            not t or not prompt
            or prompt.prompt_type not in (
                PromptType.ACTIVATE_SKILL, PromptType.CHOOSE_OPTION,
                PromptType.CHOOSE_TARGET,
            )
            or prompt.player_seat != t.seat
        ):
            return
        self.active_prompt = None
        callback = self._prompt_handler(prompt.prompt_id).get("confirm")
        if callback:
            if prompt.prompt_type == PromptType.CHOOSE_TARGET:
                selected = self.skill_prompt_selected_target
                selection_count = 1 if selected is not None else 0
            else:
                selected = [
                    card for card in self.skill_prompt_cards
                    if card.id in self.skill_prompt_selected
                ]
                selection_count = len(selected)
            if selection_count != prompt.required_cards:
                self.active_prompt = prompt
                self.hint(
                    (
                        "请选择一名角色后确定"
                        if prompt.prompt_type == PromptType.CHOOSE_TARGET
                        else f"请选择{prompt.required_cards}张牌后确定"
                    ),
                    3000,
                )
                return
            self._clear_skill_prompt_callbacks(prompt.prompt_id)
            if prompt.prompt_type == PromptType.ACTIVATE_SKILL:
                self.msg(f"{t.general.name} 选择发动【{prompt.skill_name}】")
                self.play_equipment_sound(prompt.skill_name or "", t)
            callback(selected)
            return
        self.msg(f"{t.general.name} 选择发动【{prompt.skill_name}】")
        self.play_equipment_sound(prompt.skill_name or "", t)
        judgment = self.engine.begin_optional_response_skill_judgment(
            t, prompt.skill_id or ""
        )
        if not judgment:
            self._show_regular_response_prompt()
            return
        judged = judgment.current_card
        if judged is None:
            self._show_regular_response_prompt()
            return
        judgment_id = judgment.judgment_id
        self.active_judgment_id = judgment_id
        self.judgment_display_in_progress = True
        self.ai_response_at = 0
        self.judgment_result_tip = f"【{prompt.skill_name}】正在判定……"
        self._queue_card_animation(
            judged, DRAW_SOURCE_POS,
            on_complete=lambda: self._begin_judgment_replacement_window(
                judgment,
                lambda final_event:
                    self._complete_response_judgment_after_replacements(
                        final_event, t, prompt.skill_name or "技能"
                    ),
            ),
            blocking=True,
        )

    def _complete_response_judgment_after_replacements(
        self, judgment, player, skill_name
    ):
        judgment = self.engine.finalize_judgment(judgment)
        judged = judgment.current_card
        if judged is None:
            self.judgment_display_in_progress = False
            self._show_regular_response_prompt()
            return
        suit_name = SUIT_CN.get(judged.suit, judged.suit)
        self.msg(
            f"{player.general.name} 的【{skill_name}】判定为"
            f"{suit_name}{judged.rank}"
        )
        self._hold_response_judgment_result(
            judgment.judgment_id,
            player,
            skill_name,
            judged,
            bool(judgment.result),
        )

    def _skill_prompt_selection_ready(self):
        """当前技能选牌数量是否已经满足提交条件。"""
        if not self.active_prompt:
            return False
        required = self.active_prompt.required_cards
        if required <= 0:
            return True
        if self.active_prompt.prompt_type == PromptType.CHOOSE_TARGET:
            return self.skill_prompt_selected_target in self.skill_prompt_targets
        valid_ids = set(self.active_prompt.legal_card_ids)
        selected = self.skill_prompt_selected & valid_ids
        return len(selected) == required

    def _should_draw_response_buttons(self, local_player, blocking_animation):
        """判定展示中若存在改判提示，仍须显示该提示的确定/取消按钮。"""
        return bool(
            self.wd
            and self.dt == local_player
            and not blocking_animation
            and (
                not self.judgment_display_in_progress
                or self.active_prompt is not None
            )
        )

    def _hold_response_judgment_result(
        self, judgment_id, player, skill_name, judged, success
    ):
        """在中央等待区停留并显示阶段外判定的最终结果。"""
        if judgment_id != self.active_judgment_id:
            return
        color = "红色" if self.engine.is_red(judged) else "黑色"
        self.judgment_result_success = success
        self._play_visual_effect(
            "judgegood" if success else "judgebad",
            position=self._waiting_card_position(judged)
        )
        self.judgment_result_tip = (
            f"【{skill_name}】判定为{color}：视为打出【闪】"
            if success
            else f"【{skill_name}】判定为{color}：判定失败"
        )
        response_source = self.da
        response_source_card = self.response_source_card
        response_source_name = self.response_source_name
        response_success_callback = getattr(
            self, "response_success_callback", None
        )
        self._schedule_phase_transition(
            lambda: self._finish_response_judgment_result(
                judgment_id, judged, success, player,
                response_source, response_source_card,
                response_source_name, response_success_callback,
            ),
            delay=JUDGMENT_RESULT_HOLD_MS,
        )

    def _finish_response_judgment_result(
        self, judgment_id, judged, success, player=None,
        response_source=None, response_source_card=None,
        response_source_name=None, response_success_callback=None,
    ):
        if judgment_id != self.active_judgment_id:
            return
        # 阶段外判定牌已经进入弃牌堆，但展示实体继续留在中央等待区；
        # 它与本回合其他已结算牌一起在统一清理时机淡出。
        self.judgment_result_tip = None
        self.judgment_result_success = None
        self.judgment_display_in_progress = False
        self.active_judgment_id = None
        if success:
            virtual_jink = Card(
                id=f"virtual-bagua-{judgment_id}",
                name="闪",
                suit="no_suit",
                rank="0",
                kind=CardKind.BASIC,
                color_override="colorless",
            )
            if response_success_callback is not None:
                continuation = lambda: response_success_callback(
                    player, response_source, virtual_jink, ()
                )
            elif response_source_name == "杀":
                continuation = lambda: self._on_slash_dodged(
                    player, response_source, response_source_card
                )
            else:
                continuation = self._xd
            self._after_successful_response(
                player,
                response_source,
                virtual_jink,
                (),
                continuation,
            )
            return
        self.response_time_remaining = PLAY_TIME_LIMIT_MS
        self.response_timer_last_tick = pygame.time.get_ticks()
        self._show_regular_response_prompt()

    def _decline_skill_prompt(self):
        """取消当前可选技能提示，恢复其父响应。"""
        t = self.dt
        prompt = self.active_prompt
        if not t or not prompt or prompt.player_seat != t.seat:
            return
        self.active_prompt = None
        if prompt.prompt_type == PromptType.ACTIVATE_SKILL:
            self.msg(f"{t.general.name} 不发动【{prompt.skill_name or '技能'}】")
        callback = self._prompt_handler(prompt.prompt_id).get("cancel")
        self._clear_skill_prompt_callbacks(prompt.prompt_id)
        if callback:
            callback()
            return
        self.response_time_remaining = PLAY_TIME_LIMIT_MS
        self.response_timer_last_tick = pygame.time.get_ticks()
        self._show_regular_response_prompt()

    def _current_player_choice(self, confirmed):
        prompt = self.active_prompt
        if prompt is None:
            return None
        selected_cards = tuple(
            card.id for card in self.skill_prompt_cards
            if card.id in self.skill_prompt_selected
        )
        selected_targets = (
            (self.skill_prompt_selected_target.seat,)
            if self.skill_prompt_selected_target is not None else ()
        )
        return PlayerChoice(
            prompt_id=prompt.prompt_id,
            player_seat=prompt.player_seat,
            confirmed=confirmed,
            card_ids=selected_cards if confirmed else (),
            target_seats=selected_targets if confirmed else (),
        )

    def _submit_player_choice(self, choice):
        """真人、AI和未来网络客户端统一通过纯数据选择提交。"""
        prompt = self.active_prompt
        if (
            prompt is None
            or choice.prompt_id != prompt.prompt_id
            or choice.player_seat != prompt.player_seat
        ):
            return False
        if not self.engine.validate_player_choice(prompt, choice):
            return False
        if not choice.confirmed:
            self._decline_skill_prompt()
            return True
        if prompt.prompt_type == PromptType.CHOOSE_TARGET:
            self.skill_prompt_selected_target = next(
                (
                    target for target in self.skill_prompt_targets
                    if target.seat == choice.target_seats[0]
                ),
                None,
            )
            if self.skill_prompt_selected_target is None:
                return False
        else:
            self.skill_prompt_selected = set(choice.card_ids)
        self._confirm_skill_prompt()
        return True

    def _submit_skill_prompt(self, prompt_id, confirmed):
        """兼容旧调用；内部立即转换为可序列化 PlayerChoice。"""
        prompt = self.active_prompt
        if prompt is None or prompt.prompt_id != prompt_id:
            return False
        choice = self._current_player_choice(confirmed)
        if choice is None:
            return False
        return self._submit_player_choice(choice)

    def _ad(self):
        if self.judgment_display_in_progress and not self.active_prompt:
            return
        self.ai_response_at = 0
        t=self.dt
        if not t or not t.alive: self._xd(); return
        if self.active_prompt:
            prompt = self.active_prompt
            handler = self._prompt_handler(prompt.prompt_id)
            ai_confirm = handler.get("ai_confirm")
            if (
                ai_confirm is not None
                and not ai_confirm()
            ):
                self._submit_player_choice(PlayerChoice(
                    prompt_id=prompt.prompt_id,
                    player_seat=prompt.player_seat,
                    confirmed=False,
                ))
                return
            if prompt.required_cards:
                if prompt.prompt_type == PromptType.CHOOSE_TARGET:
                    chooser = handler.get("ai_select_target")
                    self.skill_prompt_selected_target = (
                        chooser(list(self.skill_prompt_targets))
                        if chooser is not None else
                        (self.skill_prompt_targets[0]
                         if self.skill_prompt_targets else None)
                    )
                    if self.skill_prompt_selected_target not in self.skill_prompt_targets:
                        self._submit_player_choice(PlayerChoice(
                            prompt_id=prompt.prompt_id,
                            player_seat=prompt.player_seat,
                            confirmed=False,
                        ))
                        return
                else:
                    card_chooser = handler.get("ai_select_cards")
                    selected_cards = (
                        card_chooser(
                            list(self.skill_prompt_cards),
                            prompt.required_cards,
                        )
                        if card_chooser is not None
                        else self.skill_prompt_cards[:prompt.required_cards]
                    )
                    self.skill_prompt_selected = {
                        card.id for card in selected_cards
                        if card in self.skill_prompt_cards
                    }
                    if len(self.skill_prompt_selected) != prompt.required_cards:
                        self._submit_player_choice(PlayerChoice(
                            prompt_id=prompt.prompt_id,
                            player_seat=prompt.player_seat,
                            confirmed=False,
                        ))
                        return
            self._submit_player_choice(
                self._current_player_choice(True)
            )
            return
        if self.dying_target:
            recovery = (
                next(
                    (
                        card for card in t.hand
                        if card.name in self._dying_response_names(t)
                    ),
                    None,
                )
                if should_use_peach_for_dying(
                    self.engine, t, self.dying_target
                )
                else None
            )
            if recovery:
                self._use_peach_for_dying(t, recovery)
            else:
                self._skip_dying_peach(t)
            return
        d=[c for c in t.hand if c.name in self._allowed_response_names(t)]
        if not d:
            decision = self.engine.skills.ai_choose_conversion(
                self.engine,
                t,
                self.response_card_name,
                SkillTiming.RESPONSE_CONVERSION,
                SkillAIContext(
                    window="response",
                    event=self.response_source_card,
                    required_card_name=self.response_card_name,
                    source_player=self.da,
                ),
            )
            if decision is not None:
                self._use_response_conversion(
                    t, self.da, self.response_source_name,
                    self.response_source_card, decision.option,
                    list(decision.cards),
                )
                return
        if self.nullification_context and self.response_source_name == "无懈可击":
            if d and self._should_ai_play_nullification(t):
                self._play_nullification(t, d[0], self._hand_card_center(t, t.hand.index(d[0])))
            else:
                self._pass_nullification()
            return
        if self.response_source_name == "借刀杀人":
            if d:
                self._use_borrowed_sword_slash(t, d[0], self._hand_card_center(t, t.hand.index(d[0])))
            else:
                self._refuse_borrowed_sword()
            return
        if self.response_source_name == "青龙偃月刀":
            if d:
                self._use_qinglong_slash(
                    t, d[0], self._hand_card_center(t, t.hand.index(d[0]))
                )
            else:
                self.weapon_followup_context = None
                self._xd()
            return
        if d:
            idx = t.hand.index(d[0])
            source = self._hand_card_center(t, idx)
            self.engine.discard_from_hand(t, d[0], "响应打出")
            opponent = self.da
            success_callback = getattr(
                self, "response_success_callback", None
            )
            if success_callback:
                continuation = lambda: success_callback(
                    t, opponent, d[0], (d[0],)
                )
            elif self.response_source_name == "杀":
                continuation = lambda: self._on_slash_dodged(
                    t, opponent, self.response_source_card
                )
            else:
                continuation = self._xd
            callback = lambda: self._after_successful_response(
                t, opponent, d[0], (d[0],), continuation
            )
            if self.duel_active and self.response_source_name == "决斗":
                self._queue_card_animation(
                    d[0], source, self._arrow_target_center(opponent),
                    on_complete=callback,
                    blocking=True, arrow_source=self._play_arrow_source(t)
                )
            else:
                self._queue_card_animation(
                    d[0], source, on_complete=callback, blocking=True
                )
            self.msg(f"{t.general.name} 打出【{self.response_card_name}】")
            self.play_card_sound(t, d[0].name, d[0])
            return
        else:
            failure_callback = getattr(
                self, "response_failure_callback", None
            )
            if failure_callback is not None:
                failure_callback()
                return
            if self.duel_active and self.response_source_name == "决斗":
                self._resolve_duel_failure(t, "无【杀】")
                return
            if self.response_source_name == "杀":
                self._deal_slash_damage(t, self.da, self.response_source_card)
            else:
                self.msg(f"{t.general.name} 无【{self.response_card_name}】")
                self._apply_damage(
                    t, 1, actor=self.da, source_card=self.response_source_card,
                    source_physical_cards=getattr(
                        self, "response_source_physical_cards", ()
                    ),
                    on_complete=self._xd
                )
            return
        self._xd()

    def hd(self, pos):
        p=self.dt
        if not p or not p.alive: self._xd(); return
        ci=self.gci(pos, p)
        if ci is not None:
            if self.active_prompt and getattr(self, "skill_prompt_cards", None):
                chosen = p.hand[ci]
                if chosen not in self.skill_prompt_cards:
                    self.hint("这张牌不能用于当前技能")
                    return
                self._toggle_skill_prompt_card(chosen)
                return
            allowed = self._allowed_response_names(p)
            if p.hand[ci].name in allowed:
                self.idx = None if self.idx == ci else ci
                self.hint(f"已选择【{p.hand[ci].name}】，请点击【确定】")
            else:
                self.hint(f"请选择绿色高亮的【{'】或【'.join(allowed)}】")
            return
        if self.active_prompt and getattr(self, "skill_prompt_cards", None):
            equipment = self._equipment_at_position(p, pos)
            if equipment is not None:
                if equipment not in self.skill_prompt_cards:
                    self.hint("这张装备不能用于当前技能")
                    return
                self._toggle_skill_prompt_card(equipment)

    def _toggle_skill_prompt_card(self, card):
        if card.id in self.skill_prompt_selected:
            self.skill_prompt_selected.remove(card.id)
        elif len(self.skill_prompt_selected) < self.skill_prompt_required_cards:
            self.skill_prompt_selected.add(card.id)
        self.hint(
            f"已选择{len(self.skill_prompt_selected)}/"
            f"{self.skill_prompt_required_cards}张牌"
        )

    def _equipment_skill_prompt_active(self, player, equipment):
        """装备技能正在等待选择时，装备本身保持统一的选中表现。"""
        prompt = self.active_prompt
        return bool(
            self.wd
            and self.dt is not None
            and self.dt.seat == player.seat
            and prompt is not None
            and prompt.player_seat == player.seat
            and prompt.skill_name == equipment.name
            and (prompt.skill_id or "").startswith(
                ("weapon.", "armor.", "mount.", "treasure.")
            )
        )

    def _equipment_at_position(self, player, pos):
        if player.is_ai:
            return None
        slot_types = ["weapon", "armor", "offensive_mount", "defensive_mount"]
        eq_x, eq_y, eq_w, eq_h = 0, EQUIP_Y, 210, 196
        gap = 8
        slot_h = (eq_h-gap*5)//4
        for index, equipment_type in enumerate(slot_types):
            sy = eq_y + gap + index*(slot_h+gap)
            if pygame.Rect(eq_x+8, sy, eq_w-16, slot_h).collidepoint(pos):
                return next(
                    (
                        card for card in player.equipment
                        if card.equipment_type == equipment_type
                        and self._card_token(card) not in self.hidden_equipment_cards
                    ),
                    None,
                )
        return None

    def _confirm_human_response(self):
        p = self.dt
        allowed = self._allowed_response_names(p)
        if not p or self.idx is None or self.idx >= len(p.hand) or p.hand[self.idx].name not in allowed:
            self.hint(f"请先选择一张【{'】或【'.join(allowed)}】")
            return
        ci = self.idx
        source = self._hand_card_center(p, ci)
        self.idx = None
        if self.dying_target:
            self._use_peach_for_dying(p, p.hand[ci], source=source)
            return
        if self.response_source_name == "借刀杀人":
            self._use_borrowed_sword_slash(p, p.hand[ci], source)
            return
        if self.response_source_name == "青龙偃月刀":
            self._use_qinglong_slash(p, p.hand[ci], source)
            return
        if self.nullification_context and self.response_source_name == "无懈可击":
            self._play_nullification(p, p.hand[ci], source)
            return
        c = p.hand[ci]
        self.engine.discard_from_hand(p, c, "AI响应打出")
        opponent = self.da
        success_callback = getattr(
            self, "response_success_callback", None
        )
        if success_callback:
            continuation = lambda: success_callback(
                p, opponent, c, (c,)
            )
        elif self.response_source_name == "杀":
            continuation = lambda: self._on_slash_dodged(
                p, opponent, self.response_source_card
            )
        else:
            continuation = self._xd
        callback = lambda: self._after_successful_response(
            p, opponent, c, (c,), continuation
        )
        if self.duel_active and self.response_source_name == "决斗":
            self._queue_card_animation(
                c, source, self._arrow_target_center(opponent),
                on_complete=callback,
                blocking=True, arrow_source=self._play_arrow_source(p)
            )
        else:
            self._queue_card_animation(c, source, on_complete=callback, blocking=True)
        self.msg(f"{p.general.name} 打出【{c.name}】")
        self.play_card_sound(p, c.name, c)

    def _on_slash_dodged(self, target, source, source_card):
        """【闪】抵消【杀】后的武器触发窗口。"""
        if source and self.engine.can_qinglong_follow_up(source):
            self._open_skill_prompt(
                source, "weapon.qinglong", "青龙偃月刀",
                f"{source.general.name} 是否再对 {target.general.name} 使用一张【杀】？",
                lambda _cards: self._begin_qinglong_response(
                    source, target, source_card
                ),
                self._xd,
            )
            return
        available = []
        if source and self.engine.weapon_skill_available(source, "weapon.guanshi"):
            available = source.hand + [
                card for card in source.equipment if card.name != "贯石斧"
            ]
        if len(available) >= 2:
            self._open_skill_prompt(
                source, "weapon.guanshi", "贯石斧",
                f"{source.general.name} 可在自己的手牌区或装备区明牌选择两张牌，"
                "确定后弃置并令此【杀】仍生效",
                lambda cards: self._finish_guanshi(
                    source, target, source_card, cards
                ),
                self._xd,
                selectable_cards=available,
                required_cards=2,
                prompt_type=PromptType.ACTIVATE_SKILL,
            )
            return
        self._xd()

    def _begin_qinglong_response(self, source, target, original_card):
        self._finalize_active_slash()
        self.weapon_followup_context = {
            "source": source, "target": target, "original_card": original_card
        }
        self.active_prompt = None
        self._clear_skill_prompt_callbacks()
        self._start_response(
            source, target, "杀", "青龙偃月刀", original_card,
            response_action="使用",
            on_success=self._complete_qinglong_slash_response,
        )

    def _complete_borrowed_sword_slash_response(
        self, player, _actor, effective_slash, physical_cards
    ):
        context = self.borrowed_sword_resolution
        if not context:
            self._xd()
            return
        victim = context["victim"]
        self.borrowed_sword_resolution = None
        if not self._activate_forced_slash_event(
            player,
            list(physical_cards),
            victim,
            effective_slash.name,
            cards_already_processing=True,
            conversion_already_validated=True,
        ):
            self._xd()
            return
        self._after_slash_targeted(victim, player, effective_slash)

    def _complete_qinglong_slash_response(
        self, player, _actor, effective_slash, physical_cards
    ):
        context = self.weapon_followup_context
        if not context or context["source"] != player:
            self._xd()
            return
        target = context["target"]
        self.weapon_followup_context = None
        if not self._activate_forced_slash_event(
            player,
            list(physical_cards),
            target,
            effective_slash.name,
            ignore_distance=True,
            cards_already_processing=True,
            conversion_already_validated=True,
        ):
            self._xd()
            return
        self._after_slash_targeted(target, player, effective_slash)

    def _activate_forced_slash_event(
        self, player, cards, target, effective_name,
        *, ignore_distance=False, cards_already_processing=False,
        conversion_already_validated=False,
    ):
        """为强制或追加使用的【杀】建立与正常使用相同的实体上下文。"""
        try:
            event = self.engine.create_forced_slash_event(
                player,
                cards,
                target,
                effective_name,
                ignore_distance=ignore_distance,
                cards_already_processing=cards_already_processing,
                conversion_already_validated=conversion_already_validated,
            )
        except ValueError as exc:
            if cards_already_processing:
                for card in cards:
                    self.engine.finish_processing_card(card)
            self.hint(str(exc))
            return False
        self.active_slash_event = event
        for card in cards:
            self.engine.begin_processing_card(card)
        player.pending_slash_damage = event.damage
        player.pending_slash_nature = event.nature
        return True

    def _use_qinglong_slash(self, source, slash, source_pos):
        context = self.weapon_followup_context
        if not context or context["source"] != source:
            self._xd()
            return
        target = context["target"]
        if not self._activate_forced_slash_event(
            source, [slash], target, slash.name, ignore_distance=True
        ):
            self._xd()
            return
        self.weapon_followup_context = None
        self.wd = False
        self.dt = None
        self.da = None
        self._queue_card_animation(
            slash, source_pos, self._arrow_target_center(target),
            on_complete=lambda: self._after_slash_targeted(target, source, slash),
            blocking=True, arrow_source=self._play_arrow_source(source),
        )
        self.msg(
            f"{source.general.name} 发动【青龙偃月刀】，再次使用【{slash.name}】"
        )
        self.play_equipment_sound("青龙偃月刀", source)
        self.play_card_sound(source, slash.name, slash)

    def _finish_guanshi(self, source, target, source_card, cards):
        self.wd = False
        self.dt = None
        card_sources = []
        for card in cards:
            if card in source.hand:
                card_sources.append(
                    self._hand_card_center(source, source.hand.index(card))
                )
            elif card in source.equipment:
                card_sources.append(
                    self._equipment_card_center(
                        source, source.equipment.index(card)
                    )
                )
            else:
                card_sources.append(self._player_center(source))
        if not self.engine.resolve_guanshi(source, cards):
            self._xd()
            return
        for message in self.engine.log:
            self.msg(message)
        self.engine.log.clear()
        # 贯石斧的两张代价牌同属一次弃置事件：一起正面进入中央
        # 等待区，两张均展示完成后才令原【杀】继续生效。
        self._queue_discard_display(
            cards, card_sources,
            on_complete=lambda: self._deal_slash_damage(
                target, source, source_card
            ),
        )

    def _has_selected_response_card(self):
        p = self.dt
        allowed = self._allowed_response_names(p)
        return bool(
            p and self.idx is not None and self.idx < len(p.hand)
            and p.hand[self.idx].name in allowed
        )

    def _allowed_response_names(self, player):
        if self.dying_target:
            return self._dying_response_names(player)
        # 火杀、雷杀均可作为【杀】打出，以响应南蛮入侵、决斗等事件。
        if self.response_card_name == "杀":
            return ("杀", "火杀", "雷杀")
        return (self.response_card_name,)

    def _resolve_human_no_dodge(self, reason="无【闪】"):
        p = self.dt
        if not p or not p.alive:
            self._xd()
            return
        if self.duel_active and self.response_source_name == "决斗":
            self._resolve_duel_failure(p, reason)
            return
        failure_callback = getattr(
            self, "response_failure_callback", None
        )
        if failure_callback is not None:
            self.msg(f"{p.general.name} {reason}")
            failure_callback()
            return
        if self.response_source_name == "杀":
            self.msg(f"{p.general.name} {reason}")
            self._deal_slash_damage(p, self.da, self.response_source_card)
        else:
            self.msg(f"{p.general.name} {reason}")
            self._apply_damage(
                p, 1, actor=self.da, source_card=self.response_source_card,
                source_physical_cards=getattr(
                    self, "response_source_physical_cards", ()
                ),
                on_complete=self._xd
            )

    def _deal_slash_damage(self, target, source, source_card):
        damage = source.pending_slash_damage if source else 1
        nature = source.pending_slash_nature if source else DamageNature.NORMAL
        cards = target.hand + target.equipment + target.judgment_area
        if (
            source and cards
            and self.engine.weapon_skill_available(source, "weapon.hanbing")
        ):
            self._open_skill_prompt(
                source, "weapon.hanbing", "寒冰剑",
                f"{source.general.name} 是否防止此伤害并依次弃置"
                f"{target.general.name} 的两张牌？",
                lambda _cards: self._begin_hanbing_choices(
                    source, target, source_card, []
                ),
                lambda: self._apply_slash_damage_now(
                    target, source, source_card, damage, nature
                ),
            )
            return
        mounts = [
            card for card in target.equipment
            if card.equipment_type in (
                "offensive_mount", "defensive_mount"
            )
        ]
        if (
            source and mounts
            and self.engine.weapon_skill_available(
                source, "weapon.qilin"
            )
        ):
            continue_damage = lambda: self._apply_slash_damage_now(
                target, source, source_card, damage, nature
            )
            if source.is_ai:
                self.play_equipment_sound("麒麟弓", source)
                self._begin_qilin_choice(
                    source, target, mounts, continue_damage
                )
                return
            self._open_skill_prompt(
                source,
                "weapon.qilin",
                "麒麟弓",
                f"{source.general.name} 是否弃置 "
                f"{target.general.name} 的一张坐骑牌？",
                lambda _cards: self._begin_qilin_choice(
                    source, target, mounts, continue_damage
                ),
                continue_damage,
            )
            return
        self._apply_slash_damage_now(
            target, source, source_card, damage, nature
        )

    def _begin_hanbing_choices(self, source, target, source_card, chosen):
        self.wd = False
        self.dt = None
        available = [
            ("hand", i, card) for i, card in enumerate(target.hand)
            if card not in chosen
        ]
        available += [
            ("equipment", i, card) for i, card in enumerate(target.equipment)
            if card not in chosen
        ]
        available += [
            ("judgment", i, card) for i, card in enumerate(target.judgment_area)
            if card not in chosen
        ]
        if len(chosen) >= 2 or not available:
            self.msg(
                f"{source.general.name} 发动【寒冰剑】，防止伤害并弃置"
                f"{target.general.name} 的{len(chosen)}张牌"
            )
            self._xd()
            return
        self._begin_target_card_choice(
            source, "寒冰剑", target,
            on_choice=lambda card: self._choose_hanbing_card(
                source, target, source_card, chosen, card
            ),
            choices=available,
        )

    def _choose_hanbing_card(
        self, source, target, source_card, chosen, card
    ):
        if card in target.hand:
            card_source = self._hand_card_center(
                target, target.hand.index(card)
            )
        elif card in target.equipment:
            card_source = self._equipment_card_center(
                target, target.equipment.index(card)
            )
        else:
            card_source = self._player_center(target)
        if not self.engine.discard_for_hanbing(target, card):
            self._deal_slash_damage(target, source, source_card)
            return
        for message in self.engine.log:
            self.msg(message)
        self.engine.log.clear()
        # 寒冰剑逐张弃置：每张实体牌先移动并停留在中央等待区，
        # 动画完成后才开放下一张牌的选择，避免两个子事件视觉重叠。
        self._queue_discard_display(
            [card],
            [card_source],
            sequential=True,
            on_complete=lambda: self._begin_hanbing_choices(
                source, target, source_card, chosen + [card]
            ),
        )

    def _apply_slash_damage_now(
        self, target, source, source_card, damage, nature
    ):
        physical_cards = tuple(
            self.active_slash_event.physical_cards
            if self.active_slash_event else ()
        )
        self._apply_damage(
            target, damage, actor=source, source_card=source_card,
            source_physical_cards=physical_cards,
            nature=nature,
            on_complete=lambda: self._after_slash_damage(
                source, target, source_card
            ),
        )

    def _after_slash_damage(self, source, target, source_card):
        self._xd()

    def _begin_qilin_choice(
        self, source, target, mounts, on_complete=None
    ):
        self.wd = False
        self.dt = None
        choices = [
            ("equipment", target.equipment.index(card), card)
            for card in mounts if card in target.equipment
        ]
        self._begin_target_card_choice(
            source, "麒麟弓", target,
            on_choice=lambda card: self._finish_qilin(
                source, target, card, on_complete
            ),
            choices=choices,
        )

    def _finish_qilin(
        self, source, target, mount, on_complete=None
    ):
        mount_source = (
            self._equipment_card_center(
                target, target.equipment.index(mount)
            )
            if mount in target.equipment else self._player_center(target)
        )
        self.engine.resolve_qilin(source, target, mount)
        for message in self.engine.log:
            self.msg(message)
        self.engine.log.clear()
        self._queue_discard_display(
            [mount],
            [mount_source],
            on_complete=on_complete or self._xd,
        )

    def _xd(self):
        self.clear_hint()
        was_ai_turn = False
        if self.engine:
            p = self.engine.get_current_player()
            was_ai_turn = bool(p and p.is_ai and self.ai_busy)
        self.ai_response_at = 0
        self.response_time_remaining = 0
        self.idx = None
        self.pending_target = None
        self.pending_targets = []
        self.wd=False; self.dt=None; self.da=None
        self.response_source_card = None
        self.response_source_physical_cards = ()
        self.response_success_callback = None
        self.response_failure_callback = None
        self.active_prompt = None
        if self.slash_target_queue:
            target, source, source_card = self.slash_target_queue.pop(0)
            if target.alive:
                self._after_slash_targeted(target, source, source_card)
                return
        self._finalize_active_slash()
        if not self.go and self._continue_response_queue():
            return
        self._finalize_active_trick_cards()
        resolution_events = list(
            getattr(
                self, "active_conversion_resolution_events", []
            )
        )
        self.active_conversion_resolution_events = []
        if resolution_events:
            self._continue_active_conversion_resolution_events(
                resolution_events, was_ai_turn
            )
            return
        if was_ai_turn:
            self._schedule_ai_action()

    def _continue_active_conversion_resolution_events(
        self, events, was_ai_turn
    ):
        """实体牌入弃牌堆后，依次开放通用的“此牌结算后”窗口。"""
        if not events:
            if was_ai_turn and not self.go:
                self._schedule_ai_action()
            return
        event = events.pop(0)
        self._begin_triggered_skill_sequence(
            event.player,
            SkillTiming.AFTER_CARD_RESOLUTION,
            event,
            lambda: self._continue_active_conversion_resolution_events(
                events, was_ai_turn
            ),
        )

    def _finalize_active_slash(self):
        event = self.active_slash_event
        if not event:
            return
        for card in event.physical_cards:
            if card in self.engine.processing_area:
                self.engine.finish_processing_card(card)
        self.active_slash_event = None

    def _finalize_active_trick_cards(self):
        cards = list(getattr(self, "active_trick_cards", []))
        self.active_trick_cards = []
        for card in cards:
            self.engine.finish_processing_card(card)

    # ===== AI =====
    def _pa(self):
        if self.go: self.ai_busy=False; return
        p=self.engine.get_current_player()
        if not p or not p.alive or not p.is_ai: self.ai_busy=False; return
        if self.wd or self.five_grains_choice or self.target_card_choice or self.borrowed_sword_choice or self.fire_attack_context: return
        if self._has_blocking_animation(): return
        if pygame.time.get_ticks() < self.ai_next_action_at: return
        ph=self.engine.state.phase
        if ph==Phase.DRAW:
            if self.draw_animating or self.draw_phase_pending_seat != p.seat:
                return
            self._draw_phase_ui(p)
        elif ph==Phase.PLAY:
            self.ai_step+=1
            if self.ai_step>50: self.ai_busy=False; return
            a=self._ap(p)
            for m in self.engine.log:
                if p.is_ai and (
                    "装备了【" in m or "替换了装备【" in m
                ):
                    continue
                self.msg(m)
            self.engine.log.clear()
            if not a: self._fa(p)
            elif not self.wd:
                self._schedule_ai_action()
        if not self.ai_busy and not self.go: self._nx()

    def _ap(self, p):
        """按AI策略文档定义的稳定优先级尝试一个出牌动作。"""
        for action in (
            self._ai_try_early_active_skills,
            self._ai_try_wuzhong,
            self._ai_try_iron_chain,
            self._ai_try_control_trick,
            self._ai_try_borrowed_sword,
            self._ai_try_fire_attack,
            self._ai_try_global_benefit,
            self._ai_try_equipment,
            self._ai_try_peach,
            self._ai_try_damage_trick,
            self._ai_try_slash,
            self._ai_try_delayed_trick,
            # 普通主动技能仍是收尾动作；声明为高优先级的技能会在上方先尝试。
            self._ai_try_active_skills,
            self._ai_try_active_conversions,
        ):
            if action(p):
                return True
        return False

    def _ai_try_early_active_skills(self, player):
        """优先处理技能模块明确声明的早期主动技能。"""
        return self._ai_try_active_skills(
            player, priority_max=20
        )

    def _ai_try_wuzhong(self, p):
        for c in p.hand[:]:
            if c.name != "无中生有":
                continue
            before_player_ids = {
                self._card_token(card) for card in p.hand
            }
            if self.engine.play_card(p, c, None):
                self.play_card_sound(p, c.name, c)
                self._reset_play_timer()
                self._queue_card_animation(
                    c, self._player_center(p),
                    on_complete=lambda p=p, c=c,
                    before_player_ids=before_player_ids:
                        self._begin_trick_resolution(
                            p, c, None, before_player_ids, []
                        ),
                    blocking=True,
                )
                return True
        return False

    def _ai_try_iron_chain(self, p):
        for c in p.hand[:]:
            if c.name != "铁索连环":
                continue
            alive_enemies = self.engine.get_alive_enemies(p)
            chain_targets = [
                target for target in alive_enemies
                if not target.chained
            ]
            if (
                len(alive_enemies) > 1 and chain_targets
                and self.engine.play_iron_chain(
                    p, c, chain_targets[:2], apply_effect=False
                )
            ):
                self.play_card_sound(p, c.name, c)
                self._reset_play_timer()
                targets = chain_targets[:2]
                self._queue_area_card_animation(
                    c, self._player_center(p), targets,
                    blocking=True,
                    arrow_source=self._play_arrow_source(p),
                    on_complete=lambda p=p, c=c, targets=targets:
                        self._continue_iron_chain_targets(
                            p, c, targets[:]
                        ),
                )
                return True
            drawn = self.engine.recast(p, c)
            if drawn:
                sound = getattr(self, "sound", None)
                if sound:
                    sound.play_recast(p.general.gender)
                self._reset_play_timer()
                self._queue_card_animation(
                    c, self._player_center(p), blocking=True,
                    on_complete=lambda p=p, drawn=drawn:
                        self._queue_hand_gain_animation(
                            p, drawn, DRAW_SOURCE_POS, face_up=False
                        ),
                )
                return True
        return False

    def _ai_try_control_trick(self, p):
        for c in p.hand[:]:
            if c.name not in ("过河拆桥", "顺手牵羊"):
                continue
            candidates = self.engine.get_legal_play_targets(p, c)
            target = choose_control_target(
                self.engine, p, candidates
            )
            before_player_ids = {
                self._card_token(card) for card in p.hand
            }
            before_target = target.hand[:] if target else []
            if (
                target and self.engine.play_card(p, c, target)
            ):
                self.play_card_sound(p, c.name, c)
                self._reset_play_timer()
                self._queue_card_animation(
                    c, self._player_center(p),
                    self._arrow_target_center(target),
                    on_complete=lambda p=p, c=c, target=target,
                    before_player_ids=before_player_ids,
                    before_target=before_target:
                        self._begin_trick_resolution(
                            p, c, target,
                            before_player_ids, before_target
                        ),
                    blocking=True,
                    arrow_source=self._play_arrow_source(p),
                )
                return True
        return False

    def _ai_try_borrowed_sword(self, p):
        for c in p.hand[:]:
            if c.name != "借刀杀人":
                continue
            plan = choose_borrowed_sword_plan(self.engine, p)
            if (
                plan is not None
                and self.engine.can_submit_play_card(
                    p, c, (plan.wielder, plan.victim)
                )
                and self.engine.play_card(p, c, plan.wielder)
            ):
                self.play_card_sound(p, c.name, c)
                self.borrowed_sword_resolution = {
                    "actor": p,
                    "card": c,
                    "wielder": plan.wielder,
                    "victim": plan.victim,
                }
                self._reset_play_timer()
                self._queue_borrowed_sword_animation(
                    c, self._player_center(p), p,
                    plan.wielder, plan.victim,
                    on_complete=self._begin_borrowed_sword_response,
                )
                return True
        return False

    def _ai_try_fire_attack(self, p):
        for c in p.hand[:]:
            if c.name != "火攻":
                continue
            target = choose_fire_attack_target(self.engine, p)
            if target and self.engine.play_card(p, c, target):
                self.play_card_sound(p, c.name, c)
                self._reset_play_timer()
                self._queue_card_animation(
                    c, self._player_center(p),
                    self._arrow_target_center(target),
                    on_complete=lambda p=p, c=c, target=target:
                        self._begin_nullification(
                            p, c, target,
                            lambda: self._begin_fire_attack(
                                p, c, target
                            ),
                        ),
                    blocking=True,
                    arrow_source=self._play_arrow_source(p),
                )
                return True
        return False

    def _ai_try_global_benefit(self, p):
        if should_use_five_grains(self.engine, p):
            card = next(
                (
                    card for card in p.hand
                    if card.name == "五谷丰登"
                ),
                None,
            )
            if card and self.engine.play_card(p, card, None):
                self.play_card_sound(p, card.name, card)
                self._reset_play_timer()
                self._queue_card_animation(
                    card, self._player_center(p),
                    on_complete=lambda p=p, card=card:
                        self._begin_five_grains(p, card),
                    blocking=True,
                )
                return True
        if should_use_peach_garden(self.engine, p):
            card = next(
                (
                    card for card in p.hand
                    if card.name == "桃园结义"
                ),
                None,
            )
            if card and self.engine.play_card(p, card, None):
                self.play_card_sound(p, card.name, card)
                self._reset_play_timer()
                self._queue_card_animation(
                    card, self._player_center(p), blocking=True,
                    on_complete=lambda p=p, card=card:
                        self._queue_trick_effect_animations(
                            p, card, None, set(), []
                        ),
                )
                return True
        return False

    def _ai_try_equipment(self, p):
        equipment = choose_equipment_to_play(self.engine, p)
        if equipment is not None:
            old = next(
                (
                    card for card in p.equipment
                    if card.equipment_type == equipment.equipment_type
                ),
                None,
            )
            if self.engine.play_card(p, equipment, p):
                self.play_equip_action_sound(equipment.equipment_type)
                self._reset_play_timer()
                slot_index = {
                    "weapon": 0, "armor": 1,
                    "offensive_mount": 2, "defensive_mount": 3,
                }.get(equipment.equipment_type, 0)
                dest = self._equipment_card_center(p, slot_index)
                self.hidden_equipment_cards.add(
                    self._card_token(equipment)
                )
                self._queue_zone_slam_animation(
                    equipment, self._player_center(p), dest,
                    on_complete=lambda c=equipment, old=old, dest=dest:
                        self._finish_equipment_slam(c, old, dest)
                )
                return True
        return False

    def _ai_try_peach(self, p):
        if p.hp<p.max_hp:
            for c in p.hand[:]:
                if c.name=="桃":
                    if self.engine.play_card(p,c,p):
                        self.play_card_sound(p, c.name, c)
                        self._reset_play_timer()
                        self._queue_card_animation(c, self._player_center(p), blocking=True)
                        return True
        return False

    def _ai_try_damage_trick(self, p):
        for c in p.hand[:]:
            if c.name in (
                "南蛮入侵", "万箭齐发", "万剑齐发"
            ):
                before_player_ids = {self._card_token(card) for card in p.hand}
                if self.engine.play_card(p,c,None):
                    self.play_card_sound(p, c.name, c)
                    self._reset_play_timer()
                    targets = [target for target in self.engine.get_alive_players() if target != p]
                    self._queue_area_card_animation(
                        c, self._player_center(p), targets,
                        on_complete=lambda p=p, c=c, before_player_ids=before_player_ids:
                            self._queue_trick_effect_animations(p, c, None, before_player_ids, []),
                        blocking=True, arrow_source=self._play_arrow_source(p)
                    )
                    return True
        for c in p.hand[:]:
            if c.name != "决斗":
                continue
            target = next(
                iter(self.engine.get_alive_enemies(p)), None
            )
            if target and self.engine.play_card(p, c, target):
                self.play_card_sound(p, c.name, c)
                self._reset_play_timer()
                self._queue_card_animation(
                    c, self._player_center(p),
                    self._arrow_target_center(target),
                    on_complete=lambda target=target, p=p, c=c:
                        self._begin_nullification(
                            p, c, target,
                            lambda: self._begin_duel(p, target, c),
                        ),
                    blocking=True,
                    arrow_source=self._play_arrow_source(p),
                )
                return True
        return False

    def _ai_try_slash(self, p):
        h = p.hand[:]
        if self.engine.can_use_slash(p):
            wine = next((card for card in h if card.name == "酒"), None)
            slash_plan = choose_slash_plan(self.engine, p, h)
            if (
                wine
                and slash_plan
                and should_use_analeptic_for_slash(slash_plan)
                and self.engine.play_card(p, wine, p)
            ):
                self.play_card_sound(p, wine.name, wine)
                self._reset_play_timer()
                self._queue_card_animation(wine, self._player_center(p), blocking=True)
                return True
            if slash_plan:
                self.ps(
                    p,
                    slash_plan.card,
                    list(slash_plan.targets),
                    effective_name=slash_plan.effective_name,
                    skip_conversion_prompt=True,
                )
                return True
            zhangba_plan = choose_zhangba_plan(self.engine, p)
            if zhangba_plan is not None:
                self._play_zhangba_slash(
                    p,
                    list(zhangba_plan.cards),
                    zhangba_plan.target,
                )
                return True
            legal_targets = tuple(self.engine.get_slash_targets(p))
            decision = self.engine.skills.ai_choose_conversion(
                self.engine,
                p,
                "杀",
                SkillTiming.SLASH_CONVERSION,
                SkillAIContext(
                    window="play",
                    required_card_name="杀",
                    legal_targets=legal_targets,
                ),
            )
            if decision is not None and decision.target is not None:
                self._play_conversion_slash(
                    p,
                    decision.option,
                    list(decision.cards),
                    decision.target,
                )
                return True
        return False

    def _ai_try_delayed_trick(self, p):
        for c in p.hand[:]:
            if c.name in ("乐不思蜀", "兵粮寸断", "闪电"):
                if c.name == "闪电":
                    t = None
                else:
                    candidates = self.engine.get_legal_play_targets(p, c)
                    t = next(
                        (
                            target for target in candidates
                            if self.engine.are_enemies(p, target)
                        ),
                        None,
                    )
                    if not t:
                        continue
                if self.engine.play_card(p, c, t):
                    self.play_card_sound(p, c.name, c)
                    self._reset_play_timer()
                    target = t or p
                    animation_target = (
                        None if target is p
                        else self._arrow_target_center(target)
                    )
                    self._queue_card_animation(
                        c, self._player_center(p), animation_target,
                        on_complete=lambda p=p, c=c, target=target: self._begin_delayed_resolution(p, c, target),
                        blocking=True, arrow_source=self._play_arrow_source(p)
                    )
                    return True
        return False

    def _ai_try_active_conversions(self, p):
        """按技能模块估值尝试主动转化，目标型与无目标型共用提交入口。"""
        for option in self.engine.skills.active_play_conversion_options(
            self.engine, p
        ):
            decision = (
                self.engine.skills.ai_choose_active_play_conversion(
                    self.engine, p, option
                )
            )
            if (
                decision is not None
                and self.engine.can_submit_active_conversion(
                    p,
                    option,
                    list(decision.cards),
                    (
                        (decision.target,)
                        if decision.target is not None else ()
                    ),
                )
                and self._play_active_conversion(
                    p,
                    option,
                    cards=list(decision.cards),
                    target=decision.target,
                )
            ):
                return True
        return False

    def _ai_try_active_skills(self, player, priority_max=None):
        """由技能模块选择材料和目标，再提交真人共用的主动技能命令。"""
        for action in self.engine.active_skill_actions(player):
            if priority_max is None:
                if action.ai_priority <= 20:
                    continue
            elif action.ai_priority > priority_max:
                continue
            decision = self.engine.skills.ai_decide_active_skill(
                self.engine, action
            )
            if decision is None:
                continue
            self._begin_active_skill_selection(player, action)
            pending = self.pending_skill_action
            if not pending:
                return False
            pending["cards"] = list(decision.cards)
            self.pending_target = (
                decision.targets[0] if decision.targets else None
            )
            prompt = pending["choice_prompt"]
            return self._submit_active_skill_choice(PlayerChoice(
                prompt_id=prompt.prompt_id,
                player_seat=player.seat,
                confirmed=True,
                card_ids=tuple(card.id for card in decision.cards),
                target_seats=tuple(
                    target.seat for target in decision.targets
                ),
                option_id=action.skill.skill_id,
            ))
        return False

    def _fa(self, p):
        self._enter_discard_phase(p)

    def _nx(self):
        if self.go: return
        self._cg()
        if self.go: return
        n=self.engine.get_current_player()
        self.engine.start_turn()
        self.msg(f"第{self.engine.state.turn_count+1}回合：{n.general.name}")
        if n.is_ai:
            self._start_ai_turn()
        self._begin_prepare_phase(n)

    def _begin_first_turn(self):
        if self.first_turn_started:
            return
        self.first_turn_started = True
        f=self.engine.get_current_player()
        self.engine.start_turn()
        self.msg(f"第1回合：{f.general.name}")
        if f.is_ai:
            self._start_ai_turn()
        self._begin_prepare_phase(f)

    def _begin_prepare_phase(self, p):
        """进入真实存在的准备阶段；所有准备阶段事件结束后再进判定阶段。"""
        self.clear_hint()
        self.phase_transition_callback = None
        self.phase_transition_at = 0
        self.engine.state.phase = Phase.PREPARE
        self.msg(f"{p.general.name} 进入准备阶段")
        self._schedule_phase_transition(
            lambda p=p: self._begin_judgment_phase(p), delay=360
        )

    def _begin_judgment_phase(self, p):
        self.clear_hint()
        # 新回合的判定阶段拥有唯一推进链，清除上一阶段可能遗留的定时回调。
        self.phase_transition_callback = None
        self.phase_transition_at = 0
        self.play_timer_last_tick = pygame.time.get_ticks()
        self.response_timer_last_tick = self.play_timer_last_tick
        self.engine.state.phase = Phase.JUDGE
        self.msg(f"{p.general.name} 进入判定阶段")
        if not p.judgment_area:
            self._advance_after_judgments(p)
            return
        self.judgment_in_progress = False
        self.judgment_cards_remaining = len(p.judgment_area)
        self._resolve_next_judgment(p)

    def _resolve_next_judgment(self, p):
        if self.engine.state.phase != Phase.JUDGE:
            return
        if self.judgment_in_progress:
            return
        if not p.alive:
            self._finish_turn_ui(p)
            return
        if self.judgment_cards_remaining <= 0:
            self._advance_after_judgments(p)
            return
        if not p.judgment_area:
            self._advance_after_judgments(p)
            return
        self.judgment_in_progress = True
        delayed = p.judgment_area[-1]
        self.msg(f"开始判定 {p.general.name} 的【{delayed.name}】")
        actor = self.delayed_trick_sources.get(self._card_token(delayed))
        self._begin_nullification(
            actor, delayed, p,
            lambda p=p: self._perform_judgment(p),
            on_cancel=lambda p=p, delayed=delayed: self._cancel_judgment_card(p, delayed),
        )

    def _perform_judgment(self, p):
        pending_delayed = p.judgment_area[-1] if p.judgment_area else None
        original_actor = self.delayed_trick_sources.get(self._card_token(pending_delayed)) if pending_delayed else None
        delayed_source = self._judgment_card_center(p, pending_delayed) if pending_delayed else self._player_center(p)
        result = self.engine.begin_next_judgment(p)
        if result is None:
            self.judgment_in_progress = False
            self._advance_after_judgments(p)
            return
        self.judgment_cards_remaining -= 1
        self.active_judgment_id = result["judgment"].judgment_id
        result["delayed_source"] = delayed_source
        result["original_actor"] = original_actor
        delayed, judged = result["delayed"], result["judged"]
        self.delayed_trick_sources.pop(self._card_token(delayed), None)
        self._queue_card_animation(
            delayed, delayed_source,
            on_complete=lambda p=p, result=result: self._show_judgment_result(p, result),
            blocking=True
        )

    def _cancel_judgment_card(self, p, delayed):
        source = self._judgment_card_center(p, delayed)
        if delayed.name == "闪电":
            passed_to = self.engine.transfer_lightning(p, delayed)
            self.judgment_cards_remaining = max(
                0, self.judgment_cards_remaining - 1
            )
            self.judgment_in_progress = False
            if passed_to is not None:
                self.hidden_judgment_cards.add(
                    self._card_token(delayed)
                )
                self.msg(
                    f"【无懈可击】抵消【闪电】对"
                    f"{p.general.name} 的效果，移至"
                    f"{passed_to.general.name} 的判定区"
                )
                self._queue_zone_slam_animation(
                    delayed,
                    source,
                    self._judgment_card_center(passed_to, delayed),
                    on_complete=lambda p=p, delayed=delayed: (
                        self.hidden_judgment_cards.discard(
                            self._card_token(delayed)
                        ),
                        self._resolve_next_judgment(p),
                    ),
                    use_waypoint=False,
                )
                return
        self.engine.discard_from_zone(
            p, delayed, "judgment", "延时锦囊被无懈可击抵消"
        )
        self.delayed_trick_sources.pop(self._card_token(delayed), None)
        self.judgment_cards_remaining = max(0, self.judgment_cards_remaining - 1)
        self.judgment_in_progress = False
        self.msg(f"{p.general.name} 判定区的【{delayed.name}】被【无懈可击】抵消")
        self._queue_card_animation(
            delayed, source, blocking=True,
            on_complete=lambda p=p: self._resolve_next_judgment(p),
        )

    def _show_judgment_result(self, p, result):
        if result["judgment"].judgment_id != self.active_judgment_id:
            return
        judged = result["judged"]
        self._queue_card_animation(
            judged, DRAW_SOURCE_POS,
            on_complete=lambda p=p, result=result:
                self._begin_judgment_replacement_window(
                    result["judgment"],
                    lambda final_event:
                        self._complete_delayed_judgment_replacements(
                            p, result, final_event
                        ),
                ),
            blocking=True
        )

    def _complete_delayed_judgment_replacements(
        self, p, result, judgment
    ):
        result = self.engine.finish_next_judgment(
            p, result, judgment
        )
        delayed, judged = result["delayed"], result["judged"]
        if result["effect"] in ("lightning_pass", "lightning_return"):
            self.delayed_trick_sources[
                self._card_token(delayed)
            ] = result.get("original_actor")
        suit_name = SUIT_CN.get(judged.suit, judged.suit)
        self.msg(
            f"{p.general.name} 的【{delayed.name}】判定为"
            f"{suit_name}{judged.rank}"
        )
        self._hold_judgment_result(p, result)

    def _hold_judgment_result(self, p, result):
        if result["judgment"].judgment_id != self.active_judgment_id:
            return
        delayed, effect = result["delayed"], result["effect"]
        if delayed.name == "乐不思蜀":
            self.judgment_result_tip = "【乐不思蜀】生效" if effect == "skip_play" else "【乐不思蜀】未生效"
        elif delayed.name == "兵粮寸断":
            self.judgment_result_tip = "【兵粮寸断】生效" if effect == "skip_draw" else "【兵粮寸断】未生效"
        elif effect == "lightning_damage":
            self.judgment_result_tip = "【闪电】生效：受到3点雷电伤害"
        elif effect == "lightning_pass":
            self.judgment_result_tip = "【闪电】未生效：传给下家"
        elif effect == "lightning_return":
            self.judgment_result_tip = "【闪电】未生效：返回判定区"
        else:
            self.judgment_result_tip = f"【{delayed.name}】未生效"
        self.judgment_result_success = effect in {
            "skip_play", "skip_draw", "lightning_damage"
        }
        self._play_visual_effect(
            "judgegood" if self.judgment_result_success else "judgebad",
            position=self._waiting_card_position(result["judged"])
        )
        self._schedule_phase_transition(
            lambda p=p, result=result: self._finish_judgment_result(p, result),
            delay=JUDGMENT_RESULT_HOLD_MS
        )

    def _clear_judgment_waiting_cards(self, result, keep_delayed=False):
        """清掉本次判定在中央区的牌，避免与下一次判定混在一起。"""
        delayed = result["delayed"]
        judged = result["judged"]
        self.waiting_cards = [
            item for item in self.waiting_cards
            if item["card"] is not judged and (keep_delayed or item["card"] is not delayed)
        ]

    def _finish_judgment_result(self, p, result):
        # 判定动画可能跨越多个帧；过期回调不得把已经推进的阶段拉回摸牌阶段。
        if (
            self.engine.state.phase != Phase.JUDGE
            or result["judgment"].judgment_id != self.active_judgment_id
        ):
            self.judgment_result_tip = None
            self.judgment_result_success = None
            return
        self.judgment_result_tip = None
        self.judgment_result_success = None
        effect = result["effect"]
        delayed = result["delayed"]
        if delayed.name == "乐不思蜀":
            self._clear_judgment_waiting_cards(result)
            self.msg("乐不思蜀生效，本回合将跳过出牌阶段" if effect == "skip_play" else "乐不思蜀失效，本回合不跳过出牌阶段")
            self._schedule_phase_transition(
                lambda p=p: self._continue_judgment_sequence(p),
                delay=480
            )
            return
        elif delayed.name == "兵粮寸断":
            self._clear_judgment_waiting_cards(result)
            self.msg("兵粮寸断生效，跳过摸牌阶段" if effect == "skip_draw" else "兵粮寸断判定成功，不受影响")
            self._schedule_phase_transition(
                lambda p=p: self._continue_judgment_sequence(p),
                delay=480
            )
            return
        elif effect == "lightning_damage":
            # 命中的闪电在伤害结算期间仍是公共可见的处理区牌；
            # 若被获得，通用牌移动动画会从中央等待区飞向获得者手牌。
            self._clear_judgment_waiting_cards(result, keep_delayed=True)
            self.msg(f"闪电命中 {p.general.name}")
            self.judgment_in_progress = False
            self._apply_damage(
                p, 3, actor=None, source_card=result["delayed"],
                nature=DamageNature.THUNDER,
                on_complete=lambda p=p, delayed=delayed:
                    self._finish_lightning_damage(p, delayed)
            )
            return
        elif effect == "lightning_pass":
            passed_to = result["passed_to"]
            self.msg(f"闪电未命中，移动至 {passed_to.general.name} 的判定区")
            item = next((item for item in self.waiting_cards if item["card"] is delayed), None)
            source = item["pos"] if item else result["delayed_source"]
            self._clear_judgment_waiting_cards(result)
            self.hidden_judgment_cards.add(self._card_token(delayed))
            self._queue_zone_slam_animation(
                delayed, source, self._judgment_card_center(passed_to, delayed),
                on_complete=lambda p=p, delayed=delayed: self._finish_lightning_pass_animation(p, delayed),
                use_waypoint=False
            )
            return
        elif effect == "lightning_return":
            self.msg("闪电未命中且无法传递，返回原角色判定区")
            item = next((item for item in self.waiting_cards if item["card"] is delayed), None)
            source = item["pos"] if item else result["delayed_source"]
            self._clear_judgment_waiting_cards(result)
            self.hidden_judgment_cards.add(self._card_token(delayed))
            self._queue_zone_slam_animation(
                delayed, source, self._judgment_card_center(p, delayed),
                on_complete=lambda p=p, delayed=delayed: self._finish_lightning_return_animation(p, delayed),
                use_waypoint=False
            )
            return
        else:
            self._clear_judgment_waiting_cards(result)
            self.msg("闪电未命中并离开判定区")
            self._continue_judgment_sequence(p)

    def _continue_judgment_sequence(self, player):
        self.active_judgment_id = None
        self.judgment_in_progress = False
        self._resolve_next_judgment(player)

    def _finish_lightning_damage(self, player, lightning):
        """闪电伤害结算后，仅弃置仍留在处理区的实体牌。"""
        self.engine.finish_processing_card(lightning)
        self._continue_judgment_sequence(player)

    def _finish_lightning_pass_animation(self, player, lightning):
        self.active_judgment_id = None
        self.hidden_judgment_cards.discard(self._card_token(lightning))
        self.judgment_in_progress = False
        self._resolve_next_judgment(player)

    def _finish_lightning_return_animation(self, player, lightning):
        self.active_judgment_id = None
        player.judgment_area.insert(0, lightning)
        self.hidden_judgment_cards.discard(self._card_token(lightning))
        self.judgment_in_progress = False
        self._resolve_next_judgment(player)

    def _advance_after_judgments(self, p):
        # 阶段推进只允许从判定阶段发生一次。
        if self.engine.state.phase != Phase.JUDGE:
            return
        self.clear_hint()
        self.active_judgment_id = None
        self.judgment_in_progress = False
        self.player_draw_at = 0
        self.draw_phase_pending_seat = None
        if p.skip_draw:
            p.skip_draw = False
            self.msg(f"{p.general.name} 跳过摸牌阶段")
            self._enter_play_after_draw(p)
            return
        self.engine.state.phase = Phase.DRAW
        self.draw_phase_pending_seat = p.seat
        self.msg(f"{p.general.name} 进入摸牌阶段")
        draw_event = self.engine.begin_draw_phase(p)

        def begin_actual_draw():
            # 可选阶段技结算完毕后，才允许摸牌动作和计时器继续。
            self.wd = False
            self.dt = None
            self.da = None
            self.active_prompt = None
            self.ai_response_at = 0
            if p.is_ai:
                self._schedule_ai_action()
            else:
                self._start_player_draw_timer()

        self._begin_triggered_skill_sequence(
            p, SkillTiming.DRAW_PHASE, draw_event, begin_actual_draw
        )

    def _enter_play_after_draw(self, p):
        self.clear_hint()
        self.draw_phase_pending_seat = None
        self.player_draw_at = 0
        if p.skip_play:
            p.skip_play = False
            self.msg(f"{p.general.name} 跳过出牌阶段")
            self._enter_discard_phase(p)
            return
        self.engine.begin_play_phase(p)
        self.engine.state.phase = Phase.PLAY
        self._reset_play_timer()
        self.msg(f"{p.general.name} 进入出牌阶段")
        if p.is_ai and self.ai_busy:
            self._schedule_ai_action()

    def _start_initial_deal(self, count=4):
        self.initial_deal_animating = True
        start = pygame.time.get_ticks()
        for p in self.engine.state.players:
            cards = self.engine.draw_cards(count)
            if p.is_ai:
                center = self._player_center(p)
                for i, card in enumerate(cards):
                    dest = (center[0] + (i - (count - 1) / 2) * 22, center[1])
                    self._queue_draw_animation(
                        card, dest, face_up=False, start=start,
                        blocking=True, on_complete=lambda card=card, p=p: p.hand.append(card)
                    )
            else:
                old_len = len(p.hand)
                for i, card in enumerate(cards):
                    idx = old_len + i
                    dest = (HAND_LEFT_X + idx*HAND_SPACING + CARD_W//2, HAND_Y + CARD_H//2)
                    self._queue_draw_animation(
                        card, dest, start=start,
                        blocking=True, on_complete=lambda card=card, p=p: p.hand.append(card)
                    )
        self.msg(f"双方各摸{count}张起始手牌")

    def _complete_initial_deal(self):
        if not self.initial_deal_animating or self._has_draw_animation():
            return
        self.initial_deal_animating = False
        self._begin_first_turn()

    def _draw_phase_ui(self, p, count=None):
        if self.engine.state.phase != Phase.DRAW or self.draw_phase_pending_seat != p.seat:
            return False
        if count is None:
            count = p.draw_phase_card_count
        self.clear_hint()
        # 摸牌是进入摸牌阶段时产生的一次阶段动作；开始执行后立刻消费。
        self.draw_phase_pending_seat = None
        self.player_draw_at = 0
        old_len = len(p.hand)
        moves = self.engine.draw_to_hand(
            p, count, reason="摸牌阶段"
        )
        cards = [move.card for move in moves]
        self.msg(f"{p.general.name} 摸{len(cards)}张牌")
        anim_start = pygame.time.get_ticks()
        if p.is_ai:
            dest = self._player_center(p)
            for i, card in enumerate(cards):
                offset = int((i - (len(cards) - 1) / 2) * 28)
                self._queue_draw_animation(
                    card, (dest[0] + offset, dest[1]),
                    face_up=False, start=anim_start,
                )
        else:
            for i, card in enumerate(cards):
                idx = old_len + i
                dest = (HAND_LEFT_X + idx*HAND_SPACING + CARD_W//2, HAND_Y + CARD_H//2)
                self._queue_draw_animation(
                    card, dest, hide_until_done=True,
                    start=anim_start,
                )
        self.draw_animating = True
        self.draw_finish_at = anim_start + DRAW_CARD_MOVE_MS
        return True

    def _complete_draw_phase(self):
        if not self.engine or not self.draw_animating:
            return
        if self._has_draw_animation():
            return
        p = self.engine.get_current_player()
        self.draw_animating = False
        self.draw_finish_at = 0
        if not p or not p.alive or self.engine.state.phase != Phase.DRAW:
            return
        self._enter_play_after_draw(p)

    def _hs(self):
        p=self.engine.get_current_player()
        if not p or not p.alive: return
        if self.engine.state.phase==Phase.DRAW and self.draw_phase_pending_seat == p.seat:
            if self.draw_animating:
                return
            self._draw_phase_ui(p)
            self.player_draw_at = 0

    def _discard_need(self, p):
        return max(0, len(p.hand) - self.engine.hand_limit(p))

    def _enter_discard_phase(self, p):
        if (
            self.engine.state.phase == Phase.PLAY
            and self.engine.get_current_player().seat == p.seat
        ):
            event = self.engine.end_play_phase(p)
            self._begin_triggered_skill_sequence(
                p,
                SkillTiming.PLAY_PHASE_END,
                event,
                lambda p=p: self._complete_enter_discard_phase(p),
            )
            return
        self._complete_enter_discard_phase(p)

    def _complete_enter_discard_phase(self, p):
        self.clear_selection()
        need = self._discard_need(p)
        if need <= 0:
            self.msg(f"{p.general.name} 手牌未超过上限，跳过弃牌阶段")
            self._enter_end_phase(p)
            return
        self.engine.state.phase = Phase.DISCARD
        self._reset_play_timer()
        self.msg(f"{p.general.name} 进入弃牌阶段")
        if p.is_ai:
            self.hint(f"{p.general.name} 正在选择要弃置的牌")
            self._schedule_phase_transition(
                lambda p=p, need=need: self._perform_ai_discard(p, need),
                delay=AI_DISCARD_THINK_MS
            )
        else:
            self.hint(f"请选择{need}张牌弃置", 5000)

    def _perform_ai_discard(self, p, need):
        cards = choose_low_value_cards(
            self.engine, p, p.hand, need
        )
        for card in cards:
            self._queue_card_animation(card, self._player_center(p))
        self.engine.discard_cards(p, cards)
        self.msg(f"{p.general.name} 弃置{len(cards)}张牌")
        self._schedule_phase_transition(lambda p=p: self._enter_end_phase(p), delay=CARD_MOVE_MS + 160)

    def _auto_discard_timeout(self, p):
        need = self._discard_need(p)
        if need > 0:
            cards = p.hand[-need:]
            for card in cards:
                self._queue_card_animation(card, self._player_center(p))
            self.engine.discard_cards(p, cards)
            self.msg(f"{p.general.name} 自动弃置{len(cards)}张牌")
        self.clear_selection()
        self._enter_end_phase(p)

    def _confirm_discard(self, p):
        need = self._discard_need(p)
        if need <= 0:
            self._enter_end_phase(p)
            return
        if len(self.discard_selected) < need:
            self.hint(f"还需要选择{need-len(self.discard_selected)}张牌")
            return
        indexes = sorted(self.discard_selected, reverse=True)[:need]
        cards = [p.hand[i] for i in indexes if i < len(p.hand)]
        for i, card in zip(indexes, cards):
            self._queue_card_animation(card, self._hand_card_center(p, i))
        self.engine.discard_cards(p, cards)
        self.msg(f"{p.general.name} 弃置{len(cards)}张牌")
        self.clear_selection()
        self._enter_end_phase(p)

    def _enter_end_phase(self, p):
        """进入结束阶段；结束阶段事件完成后才真正切换回合。"""
        self.clear_hint()
        self.engine.state.phase = Phase.END
        self.msg(f"{p.general.name} 进入结束阶段")
        self._schedule_phase_transition(
            lambda p=p: self._finish_turn_ui(p), delay=360
        )

    def _finish_turn_ui(self, p):
        self.clear_hint()
        self.phase_transition_callback = None
        self.phase_transition_at = 0
        self._request_waiting_cards_fade()
        self.engine.finish_turn()
        # UI 已在事件发生时逐条记录；此处只清空引擎缓存，避免回合结束重复显示。
        self.engine.log.clear()
        self.ai_busy=False
        self.msg(f"{p.general.name} 回合结束")
        self._cg()
        if not self.go:
            self._nx()


    def _eh(self):
        p=self.engine.get_current_player(); self.clear_selection()
        self._enter_discard_phase(p)

    def _ck(self, pos):
        p=self.engine.get_current_player()
        if not p or not p.alive or self.go: return
        if self.initial_deal_animating or not self.first_turn_started:
            return
        if self._has_blocking_animation():
            return
        if self.judgment_display_in_progress and not self.active_prompt:
            return
        if self.borrowed_sword_choice and not self.wd:
            context = self.borrowed_sword_choice
            self._layout_pair_buttons()
            self.b_confirm.enabled = self._can_confirm_borrowed_sword()
            self.b_cancel.enabled = True
            if self.b_cancel.click(pos):
                self._cancel_borrowed_sword_target_choice()
                return
            if (
                self.b_confirm.enabled
                and self.b_confirm.click(pos)
            ):
                self._resolve_borrowed_sword_target(
                    context.get("victim")
                )
                return
            victim = self.gpl(pos)
            if victim:
                self._select_borrowed_sword_victim(victim)
            return
        if self.fire_attack_context and not self.wd:
            context = self.fire_attack_context
            chooser = context.get("chooser")
            if chooser and not chooser.is_ai:
                stage = context.get("stage")
                self._layout_pair_buttons()
                selected = context.get("selected")
                self.b_confirm.enabled = (
                    selected in context.get("choices", [])
                )
                self.b_cancel.enabled = (
                    True if stage == "discard" else selected is not None
                )
                if self.b_cancel.click(pos):
                    if stage == "reveal":
                        self._clear_fire_attack_reveal_selection()
                    else:
                        self._cancel_fire_attack_discard()
                    return
                if self.b_confirm.enabled and self.b_confirm.click(pos):
                    self._resolve_fire_attack_choice(selected)
                    return
                hand_index = self.gci(pos, chooser)
                if hand_index is not None and hand_index < len(chooser.hand):
                    chosen = chooser.hand[hand_index]
                    if chosen in context.get("choices", []):
                        context["selected"] = chosen
                        self.idx = hand_index
                        if stage == "discard":
                            self.hint(
                                f"已选择【{chosen.name}】，点击【确定】弃置，"
                                "或点击【取消】放弃",
                                5000,
                            )
                        else:
                            self.hint(
                                f"已选择【{chosen.name}】，点击【确定】展示，"
                                "或点击【取消】重新选择",
                                5000,
                            )
                    else:
                        self.hint("请选择高亮显示的同花色手牌")
                    return
            for rect, card in self.fire_attack_choice_rects:
                if rect.collidepoint(pos):
                    self._resolve_fire_attack_choice(card)
                    break
            return
        if self.target_card_choice and not self.wd:
            for rect, choice in self.target_card_choice_rects:
                if rect.collidepoint(pos):
                    self._resolve_target_card_choice(choice, rect)
                    break
            return
        if self.five_grains_choice and not self.wd:
            chooser = self.five_grains_choice.get("chooser")
            if chooser and not chooser.is_ai:
                for rect, card in self.five_grains_choice_rects:
                    if rect.collidepoint(pos):
                        self._resolve_five_grains_choice(card, rect)
                        break
            return
        if self.wd:
            if not self.dt or self.dt.is_ai:
                return
            if self._try_replace_play_skill_prompt(self.dt, pos):
                return
            if (
                self.active_prompt
                and self.active_prompt.prompt_type == PromptType.CHOOSE_TARGET
            ):
                target = self.gpl(pos)
                if target in self.skill_prompt_targets:
                    self.skill_prompt_selected_target = target
                    self.hint(
                        f"已选择目标：{target.general.name}，请点击【确定】"
                    )
                    return
            if not self.active_prompt:
                options = self.engine.skills.response_conversion_options(
                    self.dt, self.response_card_name
                )
                selected_option = next(
                    (
                        option for option in options
                        if self._response_conversion_entry_hit(
                            self.dt, option, pos
                        )
                    ),
                    None,
                )
                if selected_option:
                    player = self.dt
                    actor = self.da
                    source_name = self.response_source_name
                    source_card = self.response_source_card
                    candidates = (
                        self.engine.skills.conversion_candidates(
                            player, selected_option
                        )
                    )
                    self._open_skill_prompt(
                        player,
                        selected_option.skill.skill_id,
                        selected_option.skill.name,
                        f"请选择{selected_option.required_cards}张牌当"
                        f"【{selected_option.effective_card_name}】"
                        f"{self.response_action}",
                        lambda cards, option=selected_option:
                            self._use_response_conversion(
                                player, actor, source_name, source_card,
                                option, cards
                            ),
                        self._show_regular_response_prompt,
                        selectable_cards=candidates,
                        required_cards=selected_option.required_cards,
                    )
                    return
            response_selected = self._has_selected_response_card()
            self._layout_pair_buttons()
            self.b_confirm.enabled = (
                self._skill_prompt_selection_ready()
                if self.active_prompt else response_selected
            )
            self.b_cancel.enabled = True
            if self.dt and not self.dt.is_ai and self.b_cancel.click(pos):
                if self.active_prompt:
                    self._submit_skill_prompt(
                        self.active_prompt.prompt_id, False
                    )
                    return
                if self.dying_target:
                    self._skip_dying_peach(self.dt)
                    return
                if self.nullification_context and self.response_source_name == "无懈可击":
                    self._pass_nullification()
                    return
                if self.response_source_name == "借刀杀人":
                    self._refuse_borrowed_sword()
                    return
                if self.response_source_name == "青龙偃月刀":
                    self.weapon_followup_context = None
                    self._xd()
                    return
                allowed = self._allowed_response_names(self.dt)
                reason = f"放弃出【{self.response_card_name}】" if any(c.name in allowed for c in self.dt.hand) else f"无【{self.response_card_name}】"
                self._resolve_human_no_dodge(reason)
                return
            if self.dt and not self.dt.is_ai and self.b_confirm.click(pos):
                if self.active_prompt:
                    self._submit_skill_prompt(
                        self.active_prompt.prompt_id, True
                    )
                elif response_selected:
                    self._confirm_human_response()
                return
            if self.active_prompt:
                if self.skill_prompt_cards:
                    self.hd(pos)
                return
            self.hd(pos)
            return
        if self.engine.state.phase==Phase.DISCARD and not p.is_ai:
            need = self._discard_need(p)
            enough_selected = len(self.discard_selected) >= need
            self._layout_pair_buttons()
            self.b_confirm.enabled = enough_selected
            self.b_cancel.enabled = bool(self.discard_selected)
            if self.b_cancel.click(pos):
                self.discard_selected.clear()
                self.hint("已取消弃牌选择")
                return
            if enough_selected and self.b_confirm.click(pos):
                self._confirm_discard(p)
                return
            ci=self.gci(pos, p)
            if ci is not None:
                self.clear_hint()
                if ci in self.discard_selected:
                    self.discard_selected.remove(ci)
                else:
                    if len(self.discard_selected) >= need:
                        self.discard_selected.pop(0)
                    self.discard_selected.append(ci)
                return
        if self.engine.state.phase==Phase.PLAY and not p.is_ai:
            self._layout_end_button()
            if self.b_end.click(pos):
                self._eh()
                return
            self._layout_pair_buttons()
            self.b_confirm.enabled = self._can_confirm_play(p)
            self.b_cancel.enabled = self.idx is not None or bool(self.pending_skill_action)
            if self.b_cancel.click(pos):
                self.clear_selection()
                self.hint("已取消出牌")
                return
            if self.b_confirm.click(pos):
                self._confirm_play(p)
                return
            conversion_action = (
                self.pending_skill_action
                if self.pending_skill_action
                and self.pending_skill_action.get("option") is not None
                else None
            )
            active_skill_action = (
                self.pending_skill_action
                if self.pending_skill_action
                and self.pending_skill_action.get("action_type")
                == "active_skill"
                else None
            )
            if active_skill_action:
                action = active_skill_action["active_action"]
                ci = self.gci(pos)
                equipment = self._equipment_at_position(p, pos)
                candidate = (
                    p.hand[ci] if ci is not None else equipment
                )
                if candidate is not None:
                    if candidate not in action.legal_cards:
                        self.hint(
                            f"此牌不能作为【{action.skill.name}】的代价"
                        )
                        return
                    selected_cards = active_skill_action["cards"]
                    if candidate in selected_cards:
                        selected_cards.remove(candidate)
                    elif len(selected_cards) < action.required_cards:
                        selected_cards.append(candidate)
                    else:
                        selected_cards.pop(0)
                        selected_cards.append(candidate)
                    self.idx = None
                    self.hint(
                        f"【{action.skill.name}】：已选择"
                        f"{len(selected_cards)}/{action.required_cards}张牌，"
                        "请选择目标",
                        5000,
                    )
                    return
            if conversion_action:
                option = conversion_action["option"]
                ci = self.gci(pos)
                equipment = self._equipment_at_position(p, pos)
                candidate = (
                    p.hand[ci] if ci is not None
                    else equipment
                )
                if conversion_action.get("fixed_materials"):
                    if candidate is not None:
                        self.hint(
                            "该技能必须使用全部同色手牌；材料已经固定，"
                            "请点击【确定】或【取消】"
                        )
                        return
                elif candidate is not None:
                    if not self.engine.skills.validate_conversion(
                        p, option, [candidate]
                    ):
                        self.hint(
                            f"此牌不能用于【{option.skill.name}】"
                        )
                        return
                    conversion_action["cards"] = [candidate]
                    self.idx = ci
                    self.pending_target = None
                    effective = self.engine.skills.build_conversion_card(
                        option, [candidate]
                    )
                    self.hint(
                        f"已将此牌视为【{option.effective_card_name}】，"
                        + (
                            "请选择目标"
                            if self.engine.card_requires_manual_target(
                                effective
                            )
                            else "请点击【确定】"
                        ),
                        5000,
                    )
                    return
                if (
                    not conversion_action.get("fixed_materials")
                    and not conversion_action.get("cards")
                ):
                    self.hint(
                        f"请先选择【{option.skill.name}】需要的牌"
                    )
                    return
            selected_active_action = self._active_skill_action_at(p, pos)
            if selected_active_action:
                self.clear_selection()
                self._begin_active_skill_selection(
                    p, selected_active_action
                )
                return
            selected_option = self._play_conversion_option_at(p, pos)
            if selected_option:
                self._begin_play_conversion_selection(
                    p, selected_option
                )
                return
            weapon_slot = pygame.Rect(8, EQUIP_Y + 8, 194, 39)
            if weapon_slot.collidepoint(pos):
                weapon = next(
                    (card for card in p.equipment if card.equipment_type == "weapon"),
                    None,
                )
                if (
                    weapon and weapon.name == "丈八蛇矛"
                    and len(p.hand) >= 2 and self.engine.can_use_slash(p)
                ):
                    self._open_skill_prompt(
                        p, "weapon.zhangba", "丈八蛇矛",
                        "请选择两张手牌，确定后再选择【杀】的目标",
                        lambda cards: self._prepare_zhangba_play(p, cards),
                        self._cancel_zhangba_play_prompt,
                        selectable_cards=p.hand,
                        required_cards=2,
                        window="play",
                    )
                return
            ci=self.gci(pos)
            if ci is not None:
                self.clear_hint()
                candidate = p.hand[ci]
                if not self._can_select_play_card(p, candidate):
                    self.hint(f"【{candidate.name}】当前不能主动使用")
                    return
                if self.idx == ci:
                    self.clear_selection()
                else:
                    self.idx = ci
                    self.pending_target = None
                    self.pending_targets = []
                return
            if self.idx is not None or self.pending_skill_action:
                t=self.gpl(pos)
                if t and t.alive:
                    selected = (
                        p.hand[self.idx]
                        if self.idx is not None and self.idx < len(p.hand)
                        else None
                    )
                    if self.pending_skill_action:
                        if (
                            self.pending_skill_action.get("action_type")
                            == "active_skill"
                        ):
                            action = self.pending_skill_action[
                                "active_action"
                            ]
                            if t not in action.legal_targets:
                                self.hint(
                                    "当前角色不能成为此技能的目标"
                                )
                                return
                            self.pending_target = t
                            self.hint(
                                f"已选择目标：{t.general.name}，"
                                "请点击【确定】"
                            )
                            return
                        prompt = self.pending_skill_action.get(
                            "choice_prompt"
                        )
                        if (
                            self.pending_skill_action.get(
                                "fixed_materials"
                            )
                            and prompt is not None
                            and prompt.required_targets == 0
                        ):
                            self.hint(
                                "此技能无需选择目标，请点击【确定】或【取消】"
                            )
                            return
                        converted_cards = tuple(
                            self.pending_skill_action.get("cards", [])
                        )
                        if not self._current_play_target_legality(p, t):
                            self.hint("当前角色不能成为这张牌的目标")
                            return
                        self.pending_target = t
                        self.hint(f"已选择目标：{t.general.name}，请点击【确定】")
                        return
                    if (
                        selected
                        and not self.engine.card_requires_manual_target(
                            selected
                        )
                    ):
                        self.hint(f"【{selected.name}】无需选择目标，点击【确定】即可")
                        return
                    if (
                        selected
                        and not self._current_play_target_legality(p, t)
                    ):
                        self.hint(
                            f"{t.general.name} 不能成为【{selected.name}】的目标"
                        )
                        return
                    if selected and selected.name == "借刀杀人":
                        self._begin_borrowed_sword_target_choice(
                            p, selected, t
                        )
                        return
                    maximum = self._current_multi_target_limit(
                        p, selected
                    )
                    if maximum:
                        if t in self.pending_targets:
                            self.pending_targets.remove(t)
                            self.hint(f"已取消目标：{t.general.name}")
                        elif len(self.pending_targets) < maximum:
                            self.pending_targets.append(t)
                            self.hint(
                                self._selected_targets_hint(
                                    self.pending_targets
                                )
                            )
                        else:
                            self.hint(f"最多选择{maximum}名角色")
                    else:
                        self.pending_target = t
                        self.hint(f"已选择目标：{t.general.name}，请点击【确定】")
                    return

    def _can_select_play_card(self, p, card):
        """出牌阶段手牌是否允许主动选中；目标合法性由目标层单独判断。"""
        return self.engine.can_select_play_card(p, card)

    def _current_multi_target_limit(self, player, card):
        """返回当前牌的多目标选择上限；0表示使用普通单目标选择。"""
        if card is None:
            return 0
        if card.name == "铁索连环":
            return 2
        if (
            card.name in ("杀", "火杀", "雷杀")
            and len(player.hand) == 1
            and self.engine.weapon_skill_available(
                player, "weapon.fangtian"
            )
        ):
            return 3
        return 0

    @staticmethod
    def _selected_targets_hint(targets):
        """多目标牌共用中性提示，不把共享选择状态误写成某张牌。"""
        names = "、".join(
            target.general.name for target in targets
        )
        return f"已选目标：{names}"

    def _current_play_target_legality(self, player, target):
        """返回当前是否处于选目标状态，以及目标是否合法。"""
        if self.borrowed_sword_choice:
            context = self.borrowed_sword_choice
            return target in self.engine.borrowed_sword_victims(
                context["wielder"]
            )
        if self.pending_skill_action:
            cards = tuple(self.pending_skill_action.get("cards", []))
            if (
                self.pending_skill_action.get("action_type")
                == "active_skill"
            ):
                action = self.pending_skill_action["active_action"]
                return target in action.legal_targets
            if not cards:
                prompt = self.pending_skill_action.get("choice_prompt")
                if prompt is not None and prompt.required_targets:
                    return target.seat in prompt.legal_target_seats
                return None
            option = self.pending_skill_action.get("option")
            virtual_slash = (
                self.engine.skills.build_conversion_card(
                    option, list(cards)
                )
                if option is not None
                else self.engine.skills.build_effective_card(
                    "杀", list(cards)
                )
            )
            return self.engine.is_legal_play_target(
                player, virtual_slash, target, cards
            )
        if self.idx is None or self.idx >= len(player.hand):
            return None
        card = player.hand[self.idx]
        if not self.engine.card_requires_manual_target(card):
            return None
        return self.engine.is_legal_play_target(player, card, target)

    def _selected_slash(self, player):
        if self.idx is None or self.idx >= len(player.hand):
            return None
        card = player.hand[self.idx]
        return card if card.name in ("杀", "火杀", "雷杀") else None

    def _can_confirm_play(self, p):
        if self.pending_skill_action:
            cards = list(self.pending_skill_action.get("cards", []))
            if (
                self.pending_skill_action.get("action_type")
                == "active_skill"
            ):
                action = self.pending_skill_action["active_action"]
                targets = tuple(
                    [self.pending_target] if self.pending_target else []
                )
                return self.engine.can_submit_active_skill(
                    action, tuple(cards), targets
                )
            option = self.pending_skill_action.get("option")
            if option is not None:
                if option.timing == SkillTiming.PLAY_CONVERSION:
                    targets = tuple(
                        [self.pending_target]
                        if self.pending_target else []
                    )
                    return self.engine.can_submit_active_conversion(
                        p, option, cards, targets
                    )
                targets = tuple(
                    [self.pending_target] if self.pending_target else []
                )
                return self.engine.can_submit_conversion(
                    p, option, cards, targets
                )
            return bool(
                cards
                and self.pending_target and self.pending_target.alive
                and self.engine.can_use_slash(p, tuple(cards))
                and self.engine.in_attack_range(
                    p, self.pending_target, tuple(cards)
                )
            )
        if self.idx is None or self.idx >= len(p.hand):
            return False
        c = p.hand[self.idx]
        t = self.pending_target
        targets = tuple(
            self.pending_targets or ([t] if t else [])
        )
        return self.engine.can_submit_play_card(p, c, targets)

    def _confirm_play(self, p):
        if self.pending_skill_action:
            action = self.pending_skill_action
            target = self.pending_target
            if action.get("action_type") == "active_skill":
                prompt = action.get("choice_prompt")
                if prompt is None:
                    self.hint("当前主动技能提示已经失效")
                    return
                self._submit_active_skill_choice(PlayerChoice(
                    prompt_id=prompt.prompt_id,
                    player_seat=p.seat,
                    confirmed=True,
                    card_ids=tuple(
                        card.id for card in action["cards"]
                    ),
                    target_seats=tuple(
                        [target.seat] if target else []
                    ),
                    option_id=action[
                        "active_action"
                    ].skill.skill_id,
                ))
                return
            option = action.get("option")
            if (
                option is not None
                and option.timing == SkillTiming.PLAY_CONVERSION
            ):
                prompt = action.get("choice_prompt")
                if prompt is None:
                    self.hint("当前技能提示已经失效")
                    return
                self._submit_play_conversion_choice(PlayerChoice(
                    prompt_id=prompt.prompt_id,
                    player_seat=p.seat,
                    confirmed=True,
                    card_ids=tuple(
                        card.id for card in action["cards"]
                    ),
                    target_seats=tuple(
                        [target.seat] if target else []
                    ),
                    option_id=option.skill.skill_id,
                ))
            elif option is not None and target:
                prompt = action.get("choice_prompt")
                if prompt is None:
                    self.hint("当前牌转化提示已经失效")
                    return
                self._submit_play_conversion_choice(PlayerChoice(
                    prompt_id=prompt.prompt_id,
                    player_seat=p.seat,
                    confirmed=True,
                    card_ids=tuple(
                        card.id for card in action["cards"]
                    ),
                    target_seats=(target.seat,),
                    option_id=option.skill.skill_id,
                ))
            elif action.get("skill_id") == "weapon.zhangba" and target:
                self._play_zhangba_slash(p, action["cards"], target)
            return
        if self.idx is None or self.idx >= len(p.hand):
            self.clear_selection()
            return
        c = p.hand[self.idx]
        t = self.pending_target
        if c.name == "铁索连环":
            if self.pending_targets:
                self._play_iron_chain(p, c, self.pending_targets[:])
            else:
                self._recast_iron_chain(p, c)
            return
        no_target_tricks = {"无中生有", "桃园结义", "五谷丰登", "南蛮入侵", "万箭齐发", "万剑齐发", "闪电"}
        if c.kind == CardKind.TRICK and c.name in no_target_tricks:
            t = None
        if c.name in ("杀", "火杀", "雷杀"):
            slash_targets = self.pending_targets or ([t] if t else [])
            if not slash_targets or not all(target.alive for target in slash_targets):
                self.hint("请先点击敌方武将作为目标")
                return
            if any(target == p for target in slash_targets):
                self.hint("不能对自己使用【杀】")
                return
            self.ps(p,c,slash_targets)
        elif c.name=="桃":
            self.pp(p,c,p)
        elif c.name=="酒":
            self.pw(p,c)
        elif c.kind == CardKind.EQUIPMENT:
            self.pe(p,c)
        elif c.kind==CardKind.TRICK:
            if c.name not in no_target_tricks and (not t or not t.alive):
                self.hint("请先点击目标")
                return
            if c.name == "火攻" and not t.hand:
                self.hint("【火攻】只能指定一名有手牌的角色")
                return
            if c.name == "借刀杀人":
                self._begin_borrowed_sword_target_choice(
                    p, c, t
                )
                return
            self.pt(p,c,t)
        else:
            self.hint(f"【{c.name}】暂不能主动使用")

    def _prepare_zhangba_play(self, player, cards):
        self.wd = False
        self.dt = None
        self.da = None
        self.pending_skill_action = {
            "skill_id": "weapon.zhangba", "cards": cards[:]
        }
        self.idx = None
        self.pending_target = None
        self.hint("请选择【丈八蛇矛】转化【杀】的目标", 5000)

    def _cancel_skill_play_prompt(self, skill_name):
        """取消出牌阶段的非锁定技能，不消耗牌也不推进阶段。"""
        self.wd = False
        self.dt = None
        self.da = None
        self.active_prompt = None
        self._clear_skill_prompt_callbacks()
        self.response_time_remaining = 0
        self.ai_response_at = 0
        self.idx = None
        self.pending_target = None
        self.pending_skill_action = None
        self.hint(f"已取消发动【{skill_name}】", 3000)

    def _cancel_zhangba_play_prompt(self):
        """取消出牌阶段的丈八选牌，不进入任何响应失败或伤害分支。"""
        self.wd = False
        self.dt = None
        self.da = None
        self.active_prompt = None
        self.response_time_remaining = 0
        self.ai_response_at = 0
        self.idx = None
        self.pending_target = None
        self.pending_skill_action = None
        self.hint("已取消发动【丈八蛇矛】", 3000)

    def _play_zhangba_slash(self, player, cards, target):
        if not self.engine.skills.can_convert_zhangba(player, cards):
            self.pending_skill_action = None
            self.hint("用于【丈八蛇矛】的牌已失效")
            return
        card_sources = [
            self._hand_card_center(player, player.hand.index(card))
            for card in cards
        ]
        zhuge_was_required = (
            not self.engine.has_remaining_limited_slash_uses(player)
        )
        try:
            slash_event = self.engine.create_slash_event(
                player, cards, [target], "杀"
            )
        except ValueError as exc:
            self.pending_skill_action = None
            self.hint(str(exc))
            return
        self.active_slash_event = slash_event
        player.pending_slash_damage = slash_event.damage
        player.pending_slash_nature = slash_event.nature
        player.drunk = False
        virtual_slash = slash_event.effective_card
        self.pending_skill_action = None
        self.pending_target = None
        self._reset_play_timer()
        self._queue_discard_display(
            cards, card_sources,
            on_complete=lambda: self._after_slash_targeted(
                target, player, virtual_slash
            ),
        )
        self.msg(f"{player.general.name} 发动【丈八蛇矛】，将两张手牌当【杀】使用")
        self.play_equipment_sound("丈八蛇矛", player)
        self._play_zhuge_for_extra_slash(player, zhuge_was_required)

    def _play_conversion_slash(self, player, option, cards, target):
        card_sources = [
            self._owned_card_center(player, card) for card in cards
        ]
        # 实体牌离手后下标会复用给下一张牌，必须先清除界面选中状态。
        self.idx = None
        zhuge_was_required = (
            not self.engine.has_remaining_limited_slash_uses(player)
        )
        try:
            slash_event = self.engine.submit_play_conversion(
                player, option, cards, (target,)
            )
        except ValueError as exc:
            self.pending_skill_action = None
            self.hint(str(exc))
            return
        self.active_slash_event = slash_event
        effective_card = slash_event.effective_card
        player.pending_slash_damage = slash_event.damage
        player.pending_slash_nature = slash_event.nature
        self.pending_skill_action = None
        self.pending_target = None
        self._reset_play_timer()
        self._queue_discard_display(
            cards, card_sources,
            on_complete=lambda: self._after_slash_targeted(
                target, player, effective_card
            ),
        )
        self.msg(
            f"{player.general.name} 发动【{option.skill.name}】，"
            f"将{len(cards)}张牌当【{effective_card.name}】使用"
        )
        if option.entry_type == "equipment":
            self.play_equipment_sound(option.skill.source_name, player)
        else:
            self.play_skill_sound(player, option.skill.skill_id)
        self.play_card_sound(player, effective_card.name, effective_card)
        self._play_zhuge_for_extra_slash(player, zhuge_was_required)

    def _play_active_conversion(
        self, player, option, cards=None, target=None
    ):
        """执行模块化主动转化；后续只按有效牌规则选择通用结算。"""
        cards = list(
            cards
            if cards is not None
            else self.engine.skills.conversion_candidates(player, option)
        )
        if not cards:
            self.hint(f"当前没有可用于【{option.skill.name}】的手牌")
            return False
        card_sources = [
            self._owned_card_center(player, card) for card in cards
        ]
        try:
            use_event = self.engine.submit_active_conversion(
                player,
                option,
                cards,
                ((target,) if target is not None else ()),
            )
        except ValueError as exc:
            self.hint(str(exc))
            return False
        effective_card = use_event.effective_card
        self.clear_selection()
        self._reset_play_timer()
        self.msg(
            f"{player.general.name} 发动【{option.skill.name}】，"
            f"将{len(cards)}张牌当【{effective_card.name}】使用"
        )
        self.play_skill_sound(player, option.skill.skill_id)
        self.play_card_sound(player, effective_card.name, effective_card)

        if self.engine.card_requires_manual_target(effective_card):
            if target is None:
                for card in use_event.physical_cards:
                    self.engine.finish_processing_card(card)
                return False
            for card in use_event.physical_cards:
                if card not in self.active_trick_cards:
                    self.active_trick_cards.append(card)
            self.active_conversion_resolution_events.append(use_event)
            first = use_event.physical_cards[0]
            self._queue_card_animation(
                first,
                card_sources[0],
                self._arrow_target_center(target),
                blocking=True,
                arrow_source=self._play_arrow_source(player),
                visual_reason="converted_card_use",
                on_complete=lambda: self._begin_card_use_trigger_window(
                    lambda: self._resolve_converted_trick_after_card_use(
                        use_event, target
                    )
                ),
            )
            for card, source in zip(
                use_event.physical_cards[1:], card_sources[1:]
            ):
                self._queue_card_animation(
                    card,
                    source,
                    face_up=True,
                    blocking=False,
                    visual_reason="converted_card_use",
                )
            return True

        if effective_card.name == "桃":
            self.msg(
                f"{player.general.name} 回复1点体力"
                f"（{player.hp}/{player.max_hp}）"
            )

            def finish_peach():
                for card in use_event.physical_cards:
                    self.engine.finish_processing_card(card)
                if player.is_ai and self.ai_busy:
                    self._schedule_ai_action()

            self._queue_discard_display(
                list(use_event.physical_cards),
                card_sources,
                on_complete=finish_peach,
                visual_reason="converted_card_use",
            )
            return True

        if effective_card.name in ("万箭齐发", "万剑齐发"):
            targets = [
                target for target in self.engine.get_alive_players()
                if target.seat != player.seat
            ]
            for card in use_event.physical_cards:
                if card not in self.active_trick_cards:
                    self.active_trick_cards.append(card)
            # 中央区只展示真实组成牌：第一张实体牌承担群体箭头表现，
            # 其余实体牌同时正面飞入等待区；虚拟牌只保存在规则上下文。
            first = use_event.physical_cards[0]
            self._queue_area_card_animation(
                first,
                card_sources[0],
                targets,
                blocking=False,
                arrow_source=self._play_arrow_source(player),
            )
            for card, source in zip(
                use_event.physical_cards[1:], card_sources[1:]
            ):
                self._queue_card_animation(
                    card,
                    source,
                    face_up=True,
                    blocking=False,
                    visual_reason="converted_card_use",
                )
            # 先处理这张虚拟牌的“使用牌时”窗口，再建立群体响应。
            # 动画只消费事件，不承担规则推进条件。
            self._begin_card_use_trigger_window(
                lambda: self._queue_trick_effect_animations(
                    player, effective_card, None, set(), [],
                    source_physical_cards=use_event.physical_cards,
                )
            )
            return True

        # 引擎已拒绝未开放的有效牌；此分支仅作防御性收尾。
        for card in use_event.physical_cards:
            self.engine.finish_processing_card(card)
        return False

    def _resolve_converted_trick_after_card_use(
        self, use_event, target
    ):
        """主动转化出的普通锦囊进入与实体锦囊相同的无懈和效果窗口。"""
        callback = lambda: self._queue_trick_effect_animations(
            use_event.player,
            use_event.effective_card,
            target,
            set(),
            target.hand[:],
            source_physical_cards=use_event.physical_cards,
        )
        self._begin_nullification(
            use_event.player,
            use_event.effective_card,
            target,
            callback,
            on_cancel=lambda: self._cancel_converted_trick(
                use_event, target
            ),
        )

    def _cancel_converted_trick(self, use_event, target):
        """抵消转化牌时只结算其实体组成牌，不制造虚拟弃牌。"""
        self.msg(
            f"对 {target.general.name} 的"
            f"【{use_event.effective_card.name}】被【无懈可击】抵消"
        )
        self._xd()

    def _submit_play_conversion_choice(self, choice):
        """提交出牌阶段转化选择；本地、AI和网络入口共用此纯数据命令。"""
        action = self.pending_skill_action
        if not action or action.get("option") is None:
            return False
        prompt = action.get("choice_prompt")
        option = action["option"]
        if (
            prompt is None
            or choice.option_id != option.skill.skill_id
            or not self.engine.validate_player_choice(prompt, choice)
        ):
            return False
        players_by_seat = {
            player.seat: player for player in self.engine.state.players
        }
        try:
            player = players_by_seat[choice.player_seat]
            cards_by_id = {
                card.id: card
                for card in self.engine.skills.conversion_candidates(
                    player, option
                )
            }
            cards = [cards_by_id[card_id] for card_id in choice.card_ids]
            targets = [
                players_by_seat[seat] for seat in choice.target_seats
            ]
        except KeyError:
            return False
        if option.timing == SkillTiming.PLAY_CONVERSION:
            if (
                not self.engine.can_submit_active_conversion(
                    player, option, cards, tuple(targets)
                )
            ):
                return False
            if targets:
                return self._play_active_conversion(
                    player,
                    option,
                    cards=cards,
                    target=targets[0],
                )
            return self._play_active_conversion(
                player, option, cards=cards
            )
        if (
            len(targets) != 1
            or not self.engine.can_submit_conversion(
                player, option, cards, tuple(targets)
            )
        ):
            return False
        self._play_conversion_slash(player, option, cards, targets[0])
        return True

    def _submit_active_skill_choice(self, choice):
        """提交通用主动技能的牌与目标选择。"""
        pending = self.pending_skill_action
        if (
            not pending
            or pending.get("action_type") != "active_skill"
        ):
            return False
        action = pending.get("active_action")
        prompt = pending.get("choice_prompt")
        if (
            action is None
            or prompt is None
            or choice.option_id != action.skill.skill_id
            or not self.engine.validate_player_choice(prompt, choice)
        ):
            return False
        players_by_seat = {
            player.seat: player for player in self.engine.state.players
        }
        cards_by_id = {
            card.id: card
            for card in action.controller.hand
            + action.controller.equipment
        }
        try:
            cards = tuple(
                cards_by_id[card_id] for card_id in choice.card_ids
            )
            targets = tuple(
                players_by_seat[seat] for seat in choice.target_seats
            )
        except KeyError:
            return False
        if not self.engine.can_submit_active_skill(
            action, cards, targets
        ):
            return False
        try:
            result = self.engine.submit_active_skill(
                action, cards, targets
            )
        except ValueError as exc:
            self.hint(str(exc))
            return False
        self.clear_selection()
        self._reset_play_timer()

        def finish():
            if action.controller.is_ai and self.ai_busy:
                self._schedule_ai_action()

        self._present_skill_resolution(
            result, finish, action=action
        )
        return result.applied

    def _cg(self):
        winner = self.engine.check_winner()
        if not winner:
            return
        self.go = True
        self.wd = False
        self.dt = None
        self.da = None
        self.active_prompt = None
        self.response_queue = []
        self.slash_target_queue = []
        self.ai_busy = False
        self.ai_response_at = 0
        self.phase_transition_callback = None
        self.phase_transition_at = 0
        self._finalize_active_slash()
        if not getattr(self, "game_over_announced", False):
            self.msg(f"🏆 {winner.general.name} 胜利！")
            self.game_over_announced = True

    def _draw_decision_timer(self, player, remaining, label):
        """只在当前需要决策的角色一侧显示15秒读条。"""
        if player.is_ai:
            bar_x, bar_y, bar_w = (
                ENEMY_X, ENEMY_Y + ENEMY_H + 12, ENEMY_W
            )
            self.drw(label, "ts", bar_x, bar_y-18, C_GY)
        else:
            bar_x, bar_y, bar_w = TABLE_CX - 255, BOTTOM_BAR_Y - 72, 510
            self.drw(label, "ts", bar_x, bar_y-18, C_GY)
        bar_h = 12
        pct = min(1.0, max(0.0, remaining / PLAY_TIME_LIMIT_MS))
        pygame.draw.rect(self.screen, (24, 20, 17), (bar_x, bar_y, bar_w, bar_h), border_radius=6)
        pygame.draw.rect(self.screen, (214, 28, 26), (bar_x, bar_y, int(bar_w*pct), bar_h), border_radius=6)
        pygame.draw.rect(self.screen, (6, 5, 4), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=6)
        seconds_left = max(0, math.ceil(remaining / 1000))
        if player.is_ai:
            self.drw(f"{seconds_left}秒", "ts", bar_x+bar_w, bar_y-18, C_GY, right=True)
        else:
            self.drw(f"{seconds_left}秒", "ts", bar_x+bar_w, bar_y-18, C_GY, right=True)

    def _draw_nullification_timer(self):
        """无懈为全场同时响应，读条位置不透露具体持有者。"""
        bar_x, bar_y, bar_w, bar_h = TABLE_CX - 255, BOTTOM_BAR_Y - 72, 510, 12
        self.drw("全场无懈响应", "ts", bar_x, bar_y-18, C_GY)
        pct = min(1.0, max(0.0, self.response_time_remaining / PLAY_TIME_LIMIT_MS))
        pygame.draw.rect(self.screen, (24,20,17), (bar_x,bar_y,bar_w,bar_h), border_radius=6)
        pygame.draw.rect(self.screen, (214,28,26), (bar_x,bar_y,int(bar_w*pct),bar_h), border_radius=6)
        pygame.draw.rect(self.screen, (6,5,4), (bar_x,bar_y,bar_w,bar_h), 1, border_radius=6)
        seconds_left = max(0, math.ceil(self.response_time_remaining / 1000))
        self.drw(f"{seconds_left}秒", "ts", bar_x+bar_w, bar_y-18, C_GY, right=True)

    def _operation_controller(self, current):
        """返回当前操作提示真正对应的角色，避免把敌方询问画到我方区域。"""
        if self.wd and self.dt:
            return self.dt
        for context, key in (
            (self.fire_attack_context, "chooser"),
            (self.five_grains_choice, "chooser"),
            (self.target_card_choice, "actor"),
            (self.borrowed_sword_choice, "actor"),
        ):
            if context and context.get(key) is not None:
                return context[key]
        return current

    def _foreign_operation_in_progress(self, local_player, current):
        controller = self._operation_controller(current)
        return bool(
            local_player is not None
            and controller is not None
            and controller.seat != local_player.seat
        )

    # ===== 主绘制函数 =====
    def _draw(self, mp):
        # 背景
        self.draw_background()
        e=self.engine
        if not e: return
        hovered_general = self._update_general_hover(mp)

        # ========== 顶部栏 ==========
        draw_vertical_gradient(self.screen, (0, 0, W, TOP_BAR_H), (31, 29, 27), (10, 10, 10))
        pygame.draw.line(self.screen, (93, 72, 45), (0, TOP_BAR_H-1), (W, TOP_BAR_H-1), 2)
        self.drw(GAME_TITLE_DISPLAY, "b", 24, 7, C_GOLD)
        # 回合信息
        self.drw(f"第 {e.state.turn_count+1} 轮","b",TABLE_R-150,8,C_GOLD_LIGHT,center=True)
        self.drw(f"剩余牌 {len(e.draw_pile)}","s",TABLE_R-60,13,C_W_DARK,center=True)
        self.b_exit.draw(self.screen, self.f["btn"], mp)

        # ========== 侧边栏 - 牌局记录 ==========
        sidebar_rect = (SIDEBAR_L, TOP_BAR_H, W-SIDEBAR_L, H-TOP_BAR_H)
        draw_vertical_gradient(self.screen, sidebar_rect, (26, 23, 20), (8, 8, 7))
        pygame.draw.line(self.screen, (8, 7, 6), (SIDEBAR_L,TOP_BAR_H), (SIDEBAR_L,H), 4)
        pygame.draw.line(self.screen, (116, 91, 57), (SIDEBAR_L+3,TOP_BAR_H), (SIDEBAR_L+3,H), 1)

        info_rect = (SIDEBAR_L+18, TOP_BAR_H+28, W-SIDEBAR_L-36, 104)
        pygame.draw.rect(self.screen, (0, 0, 0, 70), info_rect, border_radius=6)
        pygame.draw.rect(self.screen, (69, 55, 37), info_rect, 1, border_radius=6)
        self.drw("战况提示","b",SIDEBAR_L+38,TOP_BAR_H+42,C_GOLD_LIGHT)
        self.drw("YY出品，必是精品","ts",SIDEBAR_L+38,TOP_BAR_H+78,C_W_DARK)

        log_top = TOP_BAR_H + 172
        log_bottom = BOTTOM_BAR_Y - 24
        log_rect = pygame.Rect(SIDEBAR_L+18, log_top, W-SIDEBAR_L-36, log_bottom-log_top)
        self.drw("牌 局 记 录","s",SIDEBAR_L+22,log_top-34,C_GOLD)
        pygame.draw.line(self.screen,C_GOLD_DARK,(SIDEBAR_L+18,log_top-10),(W-18,log_top-10),1)
        pygame.draw.rect(self.screen, (0, 0, 0, 68), log_rect, border_radius=5)
        pygame.draw.rect(self.screen, (73, 57, 36), log_rect, 1, border_radius=5)
        lh=log_rect.height-16
        vis=min(len(self.logs),max(0,lh//22))
        mx=max(0,len(self.logs)-vis)
        self.scroll=max(0,min(self.scroll,mx))
        si=max(0,len(self.logs)-vis-self.scroll)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(log_rect.inflate(-10, -8))
        for i in range(vis):
            idx=si+i
            if idx<len(self.logs):
                log_color = C_GOLD if "【杀】" in self.logs[idx] or "【闪】" in self.logs[idx] else C_GY
                if "获胜" in self.logs[idx] or "阵亡" in self.logs[idx]:
                    log_color = C_RED_LIGHT
                self.drw(self.logs[idx],"ts",SIDEBAR_L+28,log_top+8+i*22,log_color)
        self.screen.set_clip(old_clip)
        if mx>0: self.drw(f"↑↓({self.scroll+1}/{mx+1})","ts",W-22,log_bottom+8,C_GY,right=True)
        self.drw(f"共 {len(self.logs)} 条记录","ts",SIDEBAR_L+22,log_bottom+8,C_GY)

        # ========== 玩家信息 ==========
        enemy=next((p for p in e.state.players if p.is_ai),None)
        my=next((p for p in e.state.players if not p.is_ai),None)

        # 敌方武将
        if enemy:
            hit_x, hit_y = self._general_hit_offset(enemy)
            self.player_card_rects[enemy.seat] = pygame.Rect(
                ENEMY_X + hit_x,
                ENEMY_Y + hit_y,
                ENEMY_W,
                ENEMY_H,
            )
            self.draw_general_card(enemy, ENEMY_X + hit_x, ENEMY_Y + hit_y, ENEMY_W, ENEMY_H, is_enemy=True)
            self._draw_state_frame(
                enemy, ENEMY_X + hit_x, ENEMY_Y + hit_y,
                ENEMY_W, ENEMY_H, local_player=my
            )
            self._draw_enemy_equipment(
                enemy, ENEMY_X + hit_x, ENEMY_Y + hit_y,
                ENEMY_W, ENEMY_H,
            )
            if self.pending_target == enemy or enemy in self.pending_targets:
                self.draw_target_highlight(ENEMY_X, ENEMY_Y, ENEMY_W, ENEMY_H)
            self._draw_judgment_icons(
                enemy,
                ENEMY_X + hit_x,
                ENEMY_Y + hit_y,
                ENEMY_W,
                ENEMY_H,
            )
            target_legal = (
                self._current_play_target_legality(my, enemy)
                if my and e.get_current_player() == my
                and e.state.phase == Phase.PLAY else None
            )
            if target_legal is False:
                self._draw_disabled_player(
                    ENEMY_X + hit_x, ENEMY_Y + hit_y, ENEMY_W, ENEMY_H,
                    "当前不能成为目标",
                )

        # ========== 中央等待区 ==========
        self._draw_waiting_area()

        current = e.get_current_player()
        is_my_turn = bool(current and my and current.seat == my.seat)
        self._draw_phase_indicator(current, my)
        blocking_animation = self._has_blocking_animation()
        choice_in_progress = bool(self.target_card_choice or self.five_grains_choice or self.borrowed_sword_choice or self.fire_attack_context)
        own_phase_controls_available = bool(
            is_my_turn and not blocking_animation and not self.wd and not choice_in_progress
        )

        # ========== 当前决策角色读条 ==========
        if self.wd and self.dt:
            if self.nullification_context:
                self._draw_nullification_timer()
            elif self.dt != my or not blocking_animation:
                self._draw_decision_timer(self.dt, self.response_time_remaining, "响应限时")
        elif e.state.phase in (Phase.PLAY, Phase.DISCARD):
            if current != my or own_phase_controls_available:
                label = self._phase_label(current)
                self._draw_decision_timer(current, self.play_time_remaining, label)

        # ========== 按钮 ==========
        if my and my.alive and not self.go and not my.is_ai:
            local_fire_choice = bool(
                self.fire_attack_context
                and self.fire_attack_context.get("chooser") is my
                and self.fire_attack_context.get("stage")
                in ("reveal", "discard")
                and not self.wd
            )
            if local_fire_choice:
                self.b_cancel.text = "取消"
                self.b_confirm.text = "确定"
                self._layout_pair_buttons()
                selected = self.fire_attack_context.get("selected")
                self.b_confirm.enabled = (
                    selected in self.fire_attack_context.get("choices", [])
                )
                self.b_cancel.enabled = (
                    self.fire_attack_context.get("stage") == "discard"
                    or selected is not None
                )
                self.b_confirm.draw(self.screen, self.f["btn"], mp)
                self.b_cancel.draw(self.screen, self.f["btn"], mp)
            elif self.borrowed_sword_choice and not self.wd:
                self.b_cancel.text = "取消"
                self.b_confirm.text = "确定"
                self._layout_pair_buttons()
                self.b_confirm.enabled = (
                    self._can_confirm_borrowed_sword()
                )
                self.b_cancel.enabled = True
                self.b_confirm.draw(
                    self.screen, self.f["btn"], mp
                )
                self.b_cancel.draw(
                    self.screen, self.f["btn"], mp
                )
            elif (
                self.target_card_choice
                or self.five_grains_choice
                or self.fire_attack_context
            ) and not self.wd:
                pass
            elif self.wd:
                if self._should_draw_response_buttons(
                    my, self._has_blocking_animation()
                ):
                    self.b_cancel.text = "取消"
                    self.b_confirm.text = "确定"
                    self._layout_pair_buttons()
                    self.b_confirm.enabled = (
                        self._skill_prompt_selection_ready()
                        if self.active_prompt
                        else self._has_selected_response_card()
                    )
                    self.b_cancel.enabled = True
                    self.b_confirm.draw(self.screen,self.f["btn"],mp)
                    self.b_cancel.draw(self.screen,self.f["btn"],mp)
            elif own_phase_controls_available and e.state.phase==Phase.PLAY:
                self.b_cancel.text = "取消"
                self.b_confirm.text = "确定"
                self.b_end.text = "结束"
                self._layout_end_button()
                self.b_end.draw(self.screen,self.f["btn"],mp)
                self._layout_pair_buttons()
                self.b_confirm.enabled = self._can_confirm_play(my)
                self.b_cancel.enabled = (
                    self.idx is not None or bool(self.pending_skill_action)
                )
                self.b_cancel.draw(self.screen,self.f["btn"],mp)
                self.b_confirm.draw(self.screen,self.f["btn"],mp)
            elif own_phase_controls_available and e.state.phase==Phase.DISCARD:
                self.b_cancel.text = "取消"
                self.b_confirm.text = "确定"
                need = self._discard_need(my)
                self._layout_pair_buttons()
                self.b_confirm.enabled = len(self.discard_selected) >= need
                self.b_cancel.enabled = bool(self.discard_selected)
                self.b_confirm.draw(self.screen,self.f["btn"],mp)
                self.b_cancel.draw(self.screen,self.f["btn"],mp)

        # ========== 装备区 ==========
        if my:
            eq_x, eq_y = 0, EQUIP_Y
            eq_w, eq_h = 210, 196
            draw_vertical_gradient(self.screen,(eq_x,eq_y,eq_w,eq_h),(36,32,29),(16,14,13))
            pygame.draw.rect(self.screen,(115, 98, 70),(eq_x,eq_y,eq_w,eq_h),1)
            slot_names = ["武器", "防具", "进攻马", "防御马"]
            slot_types = ["weapon", "armor", "offensive_mount", "defensive_mount"]
            slot_gap = 8
            slot_h = (eq_h - slot_gap * 5) // 4
            for i, name in enumerate(slot_names):
                sy = eq_y + slot_gap + i * (slot_h + slot_gap)
                slot_rect = pygame.Rect(eq_x+8, sy, eq_w-16, slot_h)
                pygame.draw.rect(self.screen,(22,20,19),slot_rect,border_radius=4)
                pygame.draw.rect(self.screen,(88,72,50),slot_rect,1,border_radius=4)
                self.drw(name,"ts",slot_rect.x+10,slot_rect.y+8,C_GY)
                equipped = next((card for card in my.equipment if card.equipment_type == slot_types[i] and self._card_token(card) not in self.hidden_equipment_cards), None)
                if equipped:
                    conversion_action = (
                        self.pending_skill_action
                        if self.pending_skill_action
                        and (
                            self.pending_skill_action.get("option")
                            is not None
                            or self.pending_skill_action.get("action_type")
                            == "active_skill"
                        )
                        else None
                    )
                    conversion_candidates = (
                        self.engine.skills.conversion_candidates(
                            my, conversion_action["option"]
                        )
                        if (
                            conversion_action
                            and conversion_action.get("option") is not None
                        )
                        else (
                            list(
                                conversion_action[
                                    "active_action"
                                ].legal_cards
                            )
                            if conversion_action else []
                        )
                    )
                    equipment_prompt_active = (
                        self._equipment_skill_prompt_active(
                            my, equipped
                        )
                    )
                    choosing_own_cards = bool(
                        self.wd and self.dt is my and self.active_prompt
                        and self.skill_prompt_cards
                    ) or bool(
                        conversion_action or equipment_prompt_active
                    )
                    equipment_selected = bool(
                        equipment_prompt_active
                        or (
                            choosing_own_cards
                            and (
                                equipped.id in self.skill_prompt_selected
                                or equipped in (
                                    conversion_action or {}
                                ).get(
                                    "cards", []
                                )
                            )
                        )
                    )
                    selected_shift = 18 if equipment_selected else 0
                    art = self.equipment_images.get(equipped.name)
                    if art:
                        icon_w = min(180, slot_rect.w-14)
                        icon_h = min(
                            slot_rect.h-4,
                            max(16, round(icon_w * art.get_height() / art.get_width()))
                        )
                        icon = self._scaled(
                            f"equip-local:{equipped.name}", art, icon_w, icon_h
                        )
                        self.screen.blit(
                            icon,
                            (
                                slot_rect.centerx-icon_w//2 + selected_shift,
                                slot_rect.centery-icon_h//2,
                            )
                        )
                    else:
                        self.drw(
                            equipped.name, "s",
                            slot_rect.centerx + selected_shift,
                            slot_rect.centery-1,
                            C_GOLD_LIGHT, center=True
                        )
                    if choosing_own_cards:
                        if equipment_selected:
                            selected_rect = slot_rect.copy()
                            selected_rect.x += selected_shift
                            selected_rect.w -= selected_shift
                            glow = pygame.Surface(
                                (selected_rect.w, selected_rect.h),
                                pygame.SRCALPHA
                            )
                            pygame.draw.rect(
                                glow, (72, 220, 105, 72), glow.get_rect(),
                                border_radius=4
                            )
                            self.screen.blit(glow, selected_rect.topleft)
                            pygame.draw.rect(
                                self.screen, C_GREEN_LIGHT, selected_rect, 3,
                                border_radius=4
                            )
                        elif (
                            not equipment_prompt_active
                            and equipped not in (
                                conversion_candidates
                                if conversion_action
                                else self.skill_prompt_cards
                            )
                        ):
                            shade = pygame.Surface(
                                (slot_rect.w, slot_rect.h), pygame.SRCALPHA
                            )
                            shade.fill((24, 24, 24, 145))
                            self.screen.blit(shade, slot_rect.topleft)

        # ========== 我方武将 ==========
        if my:
            hit_x, hit_y = self._general_hit_offset(my)
            self.player_card_rects[my.seat] = pygame.Rect(
                ME_X + hit_x,
                ME_Y + hit_y,
                ME_W,
                ME_H,
            )
            self.draw_general_card(my, ME_X + hit_x, ME_Y + hit_y, ME_W, ME_H, is_enemy=False)
            self._draw_state_frame(
                my, ME_X + hit_x, ME_Y + hit_y,
                ME_W, ME_H, local_player=my
            )
            if self._should_draw_persistent_skills(my, my):
                self.draw_skills(
                    my, ME_X, ME_Y, is_left=False
                )
            if self.pending_target == my or my in self.pending_targets:
                self.draw_target_highlight(ME_X, ME_Y, ME_W, ME_H)
            target_legal = (
                self._current_play_target_legality(my, my)
                if e.get_current_player() == my
                and e.state.phase == Phase.PLAY else None
            )
            if target_legal is False:
                self._draw_disabled_player(
                    ME_X + hit_x, ME_Y + hit_y, ME_W, ME_H,
                    "当前不能成为目标",
                )
            self._draw_judgment_icons(
                my,
                ME_X + hit_x,
                ME_Y + hit_y,
                ME_W,
                ME_H,
            )

            # 我方手牌 - 从装备区右侧开始排列
            n=len(my.hand)
            if n>0:
                rects = self.hrects(my)
                for i,c in enumerate(my.hand):
                    if self._card_token(c) in self.hidden_draw_cards:
                        continue
                    sel=(i==self.idx) or (e.state.phase==Phase.DISCARD and i in self.discard_selected)
                    allowed = self._allowed_response_names(my)
                    fire_choices = (
                        self.fire_attack_context.get("choices", [])
                        if self.fire_attack_context
                        and self.fire_attack_context.get("chooser") == my
                        else []
                    )
                    hl = c in fire_choices
                    disabled = False
                    if self.wd and my == self.dt:
                        if self.active_prompt and self.skill_prompt_cards:
                            disabled = c not in self.skill_prompt_cards
                            sel = sel or c.id in self.skill_prompt_selected
                        else:
                            disabled = bool(self.active_prompt) or c.name not in allowed
                    elif (
                        self.pending_skill_action
                        and (
                            self.pending_skill_action.get("option")
                            is not None
                            or self.pending_skill_action.get("action_type")
                            == "active_skill"
                        )
                    ):
                        disabled = self._play_conversion_card_disabled(
                            my, c
                        )
                        sel = sel or c in self.pending_skill_action.get(
                            "cards", []
                        )
                    elif self.fire_attack_context and self.fire_attack_context.get("chooser") == my:
                        disabled = c not in self.fire_attack_context.get("choices", [])
                    elif is_my_turn and e.state.phase == Phase.PLAY and not choice_in_progress:
                        disabled = not self._can_select_play_card(my, c)
                    if i < len(rects):
                        self.dc(c,rects[i].x,rects[i].y,CARD_W,CARD_H,sel=sel,hl=hl)
                        if disabled:
                            self._draw_disabled_card(rects[i])

        self._draw_animations()
        self._draw_visual_effects()
        self._draw_skill_notice()
        self._draw_target_card_choice()
        self._draw_skill_reveal_panel()
        self._draw_five_grains_choice()
        self._draw_fire_attack_choice()

        # ========== 操作提示 ==========
        if my and my.alive and not self.go:
            tip_y = BOTTOM_BAR_Y - 112
            if self._foreign_operation_in_progress(my, current):
                pass
            elif self.hint_text and pygame.time.get_ticks() < self.hint_until:
                self.drw(self.hint_text, "s", TABLE_CX, tip_y, C_GOLD_LIGHT, center=True)
            elif (
                self.fire_attack_context
                and self.fire_attack_context.get("chooser") is my
            ):
                self.drw(
                    self.fire_attack_context.get(
                        "title", "请直接在手牌区选择一张牌"
                    ),
                    "s", TABLE_CX, tip_y, C_GOLD_LIGHT, center=True
                )
            elif self.borrowed_sword_choice:
                wielder = self.borrowed_sword_choice["wielder"]
                victim = self.borrowed_sword_choice.get("victim")
                text = (
                    f"借刀杀人：已选择 {wielder.general.name} 对 "
                    f"{victim.general.name} 使用【杀】，点击【确定】执行"
                    if victim else
                    f"借刀杀人：请选择 {wielder.general.name} "
                    "攻击范围内的被【杀】角色"
                )
                self.drw(
                    text, "s", TABLE_CX, tip_y,
                    C_GOLD_LIGHT, center=True
                )
            elif self.wd and self.dt==my and not self._has_blocking_animation():
                if self.active_prompt:
                    text = self.active_prompt.message
                    if self.active_prompt.prompt_type != PromptType.CHOOSE_OPTION:
                        text += " 点击【确定】发动，点击【取消】跳过"
                    self.drw(
                        text, "s", TABLE_CX, tip_y,
                        C_GOLD_LIGHT, center=True
                    )
                elif self.dying_target:
                    allowed = self._dying_response_names(my)
                    names = "】或【".join(allowed)
                    self.drw(f"濒死求救：选择绿色高亮的【{names}】后点击【确定】，或点击【取消】","s",TABLE_CX,tip_y,C_RED_LIGHT,center=True)
                else:
                    self.drw(f"选择绿色高亮的【{self.response_card_name}】后点击【确定】，或点击【取消】","s",TABLE_CX,tip_y,C_RED_LIGHT,center=True)
            elif is_my_turn and e.state.phase==Phase.PLAY and not my.is_ai:
                if self.idx is not None and self.idx<len(my.hand):
                    cn=my.hand[self.idx].name
                    if cn == "铁索连环":
                        chosen = "、".join(target.general.name for target in self.pending_targets)
                        h = (f"已选目标：{chosen}；点击确定使用" if chosen
                             else "点击一至两名角色后确定；不选目标直接确定可重铸")
                    elif self.pending_targets:
                        h = (
                            f"{self._selected_targets_hint(self.pending_targets)}；"
                            "点击【确定】"
                        )
                    elif self.pending_target:
                        h=f"已选择 {self.pending_target.general.name}，点击【确定】"
                    else:
                        h={
                            "杀":"已选【杀】：点击敌方武将，再点击【确定】",
                            "桃":"已选【桃】：点击【确定】即可",
                            "闪":"【闪】需响应时使用",
                            "酒":"已选【酒】：点击【确定】即可",
                            "南蛮入侵":"已选【南蛮入侵】：点击【确定】即可",
                            "万箭齐发":"已选【万箭齐发】：点击【确定】即可",
                            "万剑齐发":"已选【万箭齐发】：点击【确定】即可"
                        }.get(cn,f"已选【{cn}】：点击目标，再点击【确定】")
                    self.drw(h,"s",TABLE_CX,tip_y,C_GOLD_LIGHT,center=True)
                else:
                    self.drw("点击手牌并选择所需目标，再点击【确定】","s",TABLE_CX,tip_y,C_GY,center=True)
            elif is_my_turn and e.state.phase==Phase.DISCARD and not my.is_ai:
                need = self._discard_need(my)
                picked = len(self.discard_selected)
                if picked >= need:
                    text = f"弃牌阶段：需要弃置{need}张，已选{picked}张，请点击【确定】"
                else:
                    text = f"弃牌阶段：需要弃置{need}张，已选{picked}张，还需选择{need-picked}张"
                self.drw(text,"s",TABLE_CX,tip_y,C_GOLD_LIGHT,center=True)
            elif is_my_turn and e.state.phase==Phase.DRAW and not my.is_ai:
                self.drw("摸牌阶段：正在摸牌","s",TABLE_CX,tip_y,C_GY,center=True)

        self._draw_general_tooltip(hovered_general)

        # ========== 游戏结束遮罩 ==========
        if self.go:
            s=pygame.Surface((W,H),pygame.SRCALPHA)
            s.fill((0,0,0,180))
            self.screen.blit(s,(0,0))
            # 根据本地玩家所属一方显示胜利或失败，但始终明确获胜武将。
            vic_rect = (W//2-200, H//2-80, 400, 160)
            draw_rounded_rect(self.screen, (50, 35, 25), vic_rect, radius=16)
            draw_gold_border(self.screen, vic_rect, 3)
            winner = next(
                (
                    player for player in e.state.players
                    if player.seat == e.state.winner_seat
                ),
                None,
            )
            local_player = next((player for player in e.state.players if not player.is_ai), None)
            local_won = bool(
                winner and local_player
                and not e.are_enemies(winner, local_player)
            )
            title = "胜 利" if local_won else "失 败"
            title_color = C_GOLD_LIGHT if local_won else C_RED_LIGHT
            self.drw(title, "t", W//2, H//2-42, title_color, center=True)
            self.drw(
                f"{e.state.winner} 胜利",
                "b", W//2, H//2+8, C_W, center=True
            )
            self.drw(
                "按 ESC 或点击右上角【退出】",
                "b", W//2, H//2+35, C_W_DARK, center=True
            )

    def run(self, engine):
        self.engine=engine
        self.engine.skill_application_listener = (
            self._on_engine_skill_application
        )
        self.engine.card_use_listener = self._on_engine_card_use
        self.msg("二中杀 1v1 开始！")
        self._start_initial_deal(4)
        run=True
        while run:
            mp=pygame.mouse.get_pos()
            if self.initial_deal_animating:
                self._complete_initial_deal()
            self._update_phase_transition()
            self._update_five_grains_reveal()
            self._update_play_timer()
            self._update_card_use_trigger_queue()
            if self.nullification_context and self.nullification_ai_player and self.ai_response_at and pygame.time.get_ticks() >= self.ai_response_at:
                self._resolve_ai_nullification_window()
            elif self.wd and self.dt and self.dt.is_ai and self.ai_response_at and pygame.time.get_ticks() >= self.ai_response_at:
                self._ad()
            if self.draw_animating and self.draw_finish_at and pygame.time.get_ticks() >= self.draw_finish_at:
                self._complete_draw_phase()
            c=self.engine.get_current_player()
            if self.first_turn_started and c and not c.is_ai and not self.go and self.engine.state.phase==Phase.DRAW and self.player_draw_at and pygame.time.get_ticks() >= self.player_draw_at:
                self._hs()
            if self.first_turn_started and self.ai_busy and not self.wd and not self.go: self._pa()
            for ev in pygame.event.get():
                if self._event_requests_exit(ev):
                    run=False
                elif ev.type==pygame.KEYDOWN:
                    if ev.key==pygame.K_SPACE:
                        pass
                    elif ev.key==pygame.K_UP: self.scroll+=3
                    elif ev.key==pygame.K_DOWN: self.scroll=max(0,self.scroll-3)
                elif ev.type==pygame.MOUSEBUTTONDOWN:
                    if ev.button==4: self.scroll+=3
                    elif ev.button==5: self.scroll=max(0,self.scroll-3)
                    else: self._ck(ev.pos)
            self._draw(mp); pygame.display.flip(); self.clock.tick(FPS)
        pygame.quit()

def main():
    gs=load_generals(ROOT/"data"/"generals.yml")
    cs=load_cards(ROOT/"data"/"cards.yml")
    playable_generals = [general for general in gs if general.playable]
    if len(playable_generals)<2:
        print("至少需要2个技能已经实现的可用武将")
        sys.exit(1)
    ui=GameUI()
    sel=ui.choose_generals(
        playable_generals,
        seat_is_ai=GENERAL_SELECTION_SEAT_IS_AI,
    )
    if sel is None:
        pygame.quit()
        return
    ps=[
        Player(
            seat=i,
            general=g,
            skin_id=g.default_skin_id,
            hp=g.hp,
            max_hp=g.hp,
            hand=[],
            is_ai=GAMEPLAY_SEAT_IS_AI[i],
        )
        for i, g in enumerate(sel)
    ]
    eng=GameEngine(ps,cs)
    ui.msg(f"{ps[0].general.name} VS {ps[1].general.name}")
    ui.run(eng)

if __name__=="__main__": main()
