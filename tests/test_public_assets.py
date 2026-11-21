"""Prevent private media and derived previews from reentering public builds."""

from pathlib import Path


def test_public_tree_excludes_personal_media_directories():
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "images/generals/dingyichen",
        "images/generals/zhangyiyan",
        "sound/general/dingyichen",
        "images/general_frames/previews",
    ):
        directory = root / relative
        assert not any(path.is_file() for path in directory.rglob("*")), relative
