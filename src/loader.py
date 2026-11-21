from pathlib import Path

import yaml

from src.models import Card, General
from src.skills import SKILL_DEFINITIONS


def load_generals(path: Path) -> list[General]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    generals = [General(**item) for item in raw["generals"]]
    general_ids = [general.id for general in generals]
    if len(general_ids) != len(set(general_ids)):
        raise ValueError("武将数据中存在重复的 general.id")
    for general in generals:
        if general.gender not in ("male", "female"):
            raise ValueError(f"武将【{general.name}】的 gender 必须为 male 或 female")
        skill_ids = [skill.skill_id for skill in general.skills]
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError(f"武将【{general.name}】重复绑定了同一技能")
        for skill in general.skills:
            if not skill.skill_id.startswith("general.") or not skill.name.strip():
                raise ValueError(
                    f"武将【{general.name}】的技能引用不完整：{skill.skill_id}"
                )
            if general.playable and skill.skill_id not in SKILL_DEFINITIONS:
                raise ValueError(
                    f"可用武将【{general.name}】引用了尚未实现的技能："
                    f"{skill.skill_id}"
                )
    return generals


def load_cards(path: Path) -> list[Card]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [Card(**item) for item in raw["cards"]]
