from unittest.mock import patch

import pygame

from main import _resolve_ui_font


def test_missing_windows_font_uses_an_available_system_font():
    with (
        patch("main.Path.is_file", return_value=False),
        patch.object(pygame.font, "match_font", return_value="available.ttf"),
    ):
        assert _resolve_ui_font() == "available.ttf"


def test_no_system_font_still_provides_a_loadable_default():
    with (
        patch("main.Path.is_file", return_value=False),
        patch.object(pygame.font, "match_font", return_value=None),
    ):
        selected = _resolve_ui_font()
    pygame.font.init()
    assert pygame.font.Font(selected, 22).render("Erzhongsha", True, "white").get_width() > 0
