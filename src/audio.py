"""游戏音效加载与播放；音频设备或单个资源失败时静默降级。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import re
import time

import pygame


CARD_SOUND_KEYS = {
    "杀": "slash",
    "火杀": "fire_slash",
    "雷杀": "thunder_slash",
    "闪": "jink",
    "桃": "peach",
    "酒": "analeptic",
    "决斗": "duel",
    "顺手牵羊": "snatch",
    "过河拆桥": "dismantlement",
    "乐不思蜀": "indulgence",
    "无中生有": "ex_nihilo",
    "南蛮入侵": "savage_assault",
    "万箭齐发": "archery_attack",
    "万剑齐发": "archery_attack",
    "五谷丰登": "amazing_grace",
    "桃园结义": "god_salvation",
    "借刀杀人": "collateral",
    "铁索连环": "iron_chain",
    "火攻": "fire_attack",
    "闪电": "lightning",
    "无懈可击": "nullification",
    "兵粮寸断": "supply_shortage",
}

EQUIPMENT_SOUND_KEYS = {
    "贯石斧": "guanshi",
    "朱雀羽扇": "zhuque",
    "方天画戟": "fangtian",
    "仁王盾": "renwang",
    "八卦阵": "bagua",
    "雌雄双股剑": "cixiong",
    "青龙偃月刀": "qinglong",
    "寒冰剑": "hanbing",
    "诸葛连弩": "zhuge",
    "丈八蛇矛": "zhangba",
    "藤甲": "vine",
    "藤甲燃烧": "vine_fire",
    "白银狮子": "silver_lion",
    "青釭剑": "qinggang",
    "麒麟弓": "qilin",
}

VOICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class SoundManager:
    def __init__(
        self, root: Path, volume: float = 0.72,
        bgm_volume: float = 0.30,
    ):
        self.root = root
        self.volume = max(0.0, min(1.0, volume))
        self.bgm_volume = max(0.0, min(1.0, bgm_volume))
        self.enabled = False
        self._cache: dict[str, pygame.mixer.Sound] = {}
        self._last_played: dict[str, float] = {}
        self._skill_variant_index: dict[str, int] = {}
        self._active_bgm: Optional[Path] = None
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            pygame.mixer.set_num_channels(max(12, pygame.mixer.get_num_channels()))
            self.enabled = True
        except (pygame.error, OSError):
            self.enabled = False

    def _play_path(self, path: Path, volume: Optional[float] = None) -> bool:
        if not self.enabled or not path.is_file():
            return False
        key = str(path)
        now = time.monotonic()
        if now - self._last_played.get(key, 0.0) < 0.12:
            return False
        try:
            sound = self._cache.get(key)
            if sound is None:
                sound = pygame.mixer.Sound(path)
                self._cache[key] = sound
            sound.set_volume(self.volume if volume is None else volume)
            sound.play()
            self._last_played[key] = now
            return True
        except (pygame.error, OSError):
            return False

    def play_card(self, card_name: str, gender: str = "male") -> bool:
        key = CARD_SOUND_KEYS.get(card_name)
        if key is None:
            return False
        voice = "female" if gender == "female" else "male"
        return self._play_path(self.root / "card" / voice / f"{key}.ogg")

    def play_recast(self, gender: str = "male") -> bool:
        voice = "female" if gender == "female" else "male"
        return self._play_path(self.root / "card" / voice / "recast.ogg")

    def play_equipment(self, equipment_name: str) -> bool:
        key = EQUIPMENT_SOUND_KEYS.get(equipment_name)
        if key is None:
            return False
        return self._play_path(self.root / "equipment" / f"{key}.ogg")

    def play_equip_action(self, equipment_type: Optional[str]) -> bool:
        key = {
            "weapon": "equip_weapon",
            "armor": "equip_armor",
            "offensive_mount": "equip_mount",
            "defensive_mount": "equip_mount",
        }.get(equipment_type or "")
        if key is None:
            return False
        return self._play_path(self.root / "equipment" / f"{key}.ogg")

    @staticmethod
    def _valid_voice_ids(*values: str) -> bool:
        return all(
            bool(value) and VOICE_ID_PATTERN.fullmatch(value) is not None
            for value in values
        )

    @staticmethod
    def _variant_sort_key(path: Path) -> tuple[int, int | str]:
        return (
            (0, int(path.stem))
            if path.stem.isdigit()
            else (1, path.name)
        )

    def skill_voice_paths(
        self, general_id: str, skin_id: str, skill_id: str
    ) -> tuple[Path, ...]:
        """返回当前皮肤技能语音；缺失时回退该武将的 default 皮肤。"""
        if not self._valid_voice_ids(general_id, skin_id, skill_id):
            return ()
        skin_candidates = (
            (skin_id, "default") if skin_id != "default"
            else ("default",)
        )
        for candidate_skin in skin_candidates:
            directory = (
                self.root / "general" / general_id / candidate_skin
                / "skill" / skill_id
            )
            paths = tuple(sorted(
                (
                    path for path in directory.glob("*.ogg")
                    if path.is_file()
                ),
                key=self._variant_sort_key,
            ))
            if paths:
                return paths
        return ()

    def play_skill(
        self, general_id: str, skin_id: str, skill_id: str
    ) -> bool:
        """按武将、皮肤与技能 ID 播放技能语音；同一组素材依次轮换。"""
        paths = self.skill_voice_paths(general_id, skin_id, skill_id)
        if not paths:
            return False
        voice_key = f"{general_id}:{skin_id}:{skill_id}"
        index = self._skill_variant_index.get(voice_key, 0) % len(paths)
        self._skill_variant_index[voice_key] = index + 1
        return self._play_path(paths[index])

    def death_voice_path(
        self, general_id: str, skin_id: str
    ) -> Optional[Path]:
        """返回当前皮肤阵亡语音；缺失时回退该武将的 default 皮肤。"""
        if not self._valid_voice_ids(general_id, skin_id):
            return None
        skin_candidates = (
            (skin_id, "default") if skin_id != "default"
            else ("default",)
        )
        for candidate_skin in skin_candidates:
            path = (
                self.root / "general" / general_id / candidate_skin
                / "death.ogg"
            )
            if path.is_file():
                return path
        return None

    def play_death(self, general_id: str, skin_id: str) -> bool:
        """按稳定武将与皮肤 ID 播放阵亡语音；没有素材时静默跳过。"""
        path = self.death_voice_path(general_id, skin_id)
        if path is None:
            return False
        return self._play_path(path)

    def play_system(self, event: str, volume: Optional[float] = None) -> bool:
        return self._play_path(
            self.root / "system" / f"{event}.ogg", volume=volume
        )

    def bgm_path(self, track_id: str = "main_theme") -> Optional[Path]:
        """按稳定英文ID读取背景音乐。"""
        if not self._valid_voice_ids(track_id):
            return None
        path = self.root / "music" / f"{track_id}.ogg"
        return path if path.is_file() else None

    def play_bgm(self, track_id: str = "main_theme") -> bool:
        """使用独立音乐通道无限循环BGM，不占用语音和音效通道。"""
        path = self.bgm_path(track_id)
        if not self.enabled or path is None:
            return False
        try:
            if (
                self._active_bgm == path
                and pygame.mixer.music.get_busy()
            ):
                return True
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.bgm_volume)
            pygame.mixer.music.play(-1)
            self._active_bgm = path
            return True
        except (pygame.error, OSError):
            self._active_bgm = None
            return False

    def stop_bgm(self) -> None:
        """停止当前背景音乐；不影响正在播放的规则音效。"""
        if self.enabled:
            pygame.mixer.music.stop()
        self._active_bgm = None
