import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from src.audio import (
    CARD_SOUND_KEYS, EQUIPMENT_SOUND_KEYS, SoundManager,
)
from main import GameUI


class AudioAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.root = Path(__file__).parents[1] / "sound"
        cls.sound = SoundManager(cls.root)

    def test_all_mapped_card_voices_exist_for_both_genders(self):
        for key in set(CARD_SOUND_KEYS.values()):
            for gender in ("male", "female"):
                self.assertTrue(
                    (self.root / "card" / gender / f"{key}.ogg").is_file()
                )

    def test_all_mapped_equipment_sounds_exist(self):
        for key in set(EQUIPMENT_SOUND_KEYS.values()):
            self.assertTrue(
                (self.root / "equipment" / f"{key}.ogg").is_file()
            )

    def test_all_mapped_skill_sounds_exist(self):
        expected = {
            ("guanyu", "default", "general.wusheng"): 2,
            ("caocao", "default", "general.jianxiong"): 2,
        }
        for voice_key, count in expected.items():
            with self.subTest(voice_key=voice_key):
                self.assertEqual(
                    len(self.sound.skill_voice_paths(*voice_key)), count
                )

    def test_every_ogg_file_can_be_loaded(self):
        self.assertTrue(self.sound.enabled)
        files = list(self.root.rglob("*.ogg"))
        self.assertTrue(files)
        for path in files:
            with self.subTest(path=path.relative_to(self.root)):
                sound = pygame.mixer.Sound(path)
                self.assertGreater(sound.get_length(), 0)

    def test_bgm_is_loaded_on_dedicated_channel_and_loops(self):
        path = self.sound.bgm_path("main_theme")
        self.assertIsNotNone(path)
        self.assertEqual(path.name, "main_theme.ogg")
        with (
            patch.object(pygame.mixer.music, "load") as load,
            patch.object(
                pygame.mixer.music, "set_volume"
            ) as set_volume,
            patch.object(pygame.mixer.music, "play") as play,
        ):
            self.sound._active_bgm = None
            self.assertTrue(self.sound.play_bgm("main_theme"))
        load.assert_called_once_with(path)
        set_volume.assert_called_once_with(self.sound.bgm_volume)
        play.assert_called_once_with(-1)

    def test_representative_playback_routes(self):
        self.assertTrue(self.sound.play_card("杀", "male"))
        self.assertTrue(self.sound.play_equipment("八卦阵"))
        self.assertTrue(self.sound.play_equipment("藤甲燃烧"))
        self.assertTrue(self.sound.play_skill(
            "guanyu", "default", "general.wusheng"
        ))
        self.assertTrue(self.sound.play_death("guanyu", "default"))
        self.assertTrue(self.sound.play_death("caocao", "default"))
        self.assertTrue(self.sound.play_system("damage1"))

    def test_skill_voice_variants_rotate(self):
        sound = SoundManager(self.root)

        self.assertTrue(sound.play_skill(
            "guanyu", "default", "general.wusheng"
        ))
        self.assertTrue(sound.play_skill(
            "guanyu", "default", "general.wusheng"
        ))
        self.assertEqual(
            sound._skill_variant_index[
                "guanyu:default:general.wusheng"
            ],
            2,
        )

    def test_missing_skin_voice_falls_back_to_default(self):
        skill_paths = self.sound.skill_voice_paths(
            "guanyu", "skin_001", "general.wusheng"
        )
        death_path = self.sound.death_voice_path(
            "guanyu", "skin_001"
        )

        self.assertTrue(skill_paths)
        self.assertTrue(all(
            "default" in path.parts for path in skill_paths
        ))
        self.assertIsNotNone(death_path)
        self.assertIn("default", death_path.parts)

    def test_death_voice_uses_stable_general_id(self):
        played = []
        ui = GameUI.__new__(GameUI)
        ui.sound = SimpleNamespace(
            play_death=lambda general_id, skin_id:
                played.append((general_id, skin_id))
        )
        player = SimpleNamespace(
            general=SimpleNamespace(id="guanyu"),
            skin_id="skin_001",
        )

        ui.play_general_death_sound(player)

        self.assertEqual(played, [("guanyu", "skin_001")])

    def test_skill_voice_uses_general_skin_and_skill_ids(self):
        played = []
        ui = GameUI.__new__(GameUI)
        ui.sound = SimpleNamespace(
            play_skill=lambda general_id, skin_id, skill_id:
                played.append((general_id, skin_id, skill_id))
        )
        ui.engine = None
        player = SimpleNamespace(
            general=SimpleNamespace(id="dingyichen"),
            skin_id="default",
        )

        ui.play_skill_sound(player, "general.kiss")

        self.assertEqual(
            played,
            [("dingyichen", "default", "general.kiss")],
        )


if __name__ == "__main__":
    unittest.main()
