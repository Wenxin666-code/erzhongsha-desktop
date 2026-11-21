"""统一技能定义、有效性检查与已实现装备技能的规则分派。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.models import (
    Card, DamageEvent, DamageNature, Player, SkillDefinition, SkillKind,
    SkillSourceType, SkillTiming,
)
from src.skill_modules.base import (
    ActiveSkillAIDecision, ActiveSkillAction, JudgmentReplacementAction,
    JudgmentReplacementResult, SkillAIContext, SkillAIConversionDecision,
    SkillResolutionRequest, SkillResolutionResult, TriggeredSkillAction,
    build_converted_card,
)
from src.skill_modules.registry import (
    ACTIVE_SKILL_HANDLERS, CONVERSION_SKILL_HANDLERS,
    GENERAL_SKILL_DEFINITIONS,
    JUDGMENT_REPLACEMENT_SKILL_HANDLERS,
    TARGET_PROHIBITION_SKILL_HANDLERS, TRIGGERED_SKILL_HANDLERS,
)


@dataclass(frozen=True)
class SkillApplication:
    """一次技能实际影响结算的记录，供引擎日志和界面展示使用。"""
    skill: SkillDefinition
    message: str


@dataclass(frozen=True)
class ResponseConversionOption:
    """由技能运行时提供给统一响应窗口的牌转化动作。"""
    skill: SkillDefinition
    effective_card_name: str
    required_cards: int
    entry_type: str
    timing: SkillTiming
    fixed_materials: bool = False


def _equipment_skill(
    skill_id: str,
    name: str,
    source_name: str,
    source_type: SkillSourceType,
    kind: SkillKind,
    *timings: SkillTiming,
) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        name=name,
        source_type=source_type,
        source_name=source_name,
        kind=kind,
        timings=timings,
        mandatory=kind == SkillKind.LOCKED,
    )


EQUIPMENT_SKILLS: tuple[SkillDefinition, ...] = (
    _equipment_skill(
        "armor.bagua", "八卦阵", "八卦阵", SkillSourceType.ARMOR,
        SkillKind.TRIGGERED, SkillTiming.RESPONSE_REQUIRED,
    ),
    _equipment_skill(
        "armor.renwang", "仁王盾", "仁王盾", SkillSourceType.ARMOR,
        SkillKind.LOCKED, SkillTiming.EFFECT_VALIDITY,
    ),
    _equipment_skill(
        "armor.vine", "藤甲", "藤甲", SkillSourceType.ARMOR,
        SkillKind.LOCKED, SkillTiming.EFFECT_VALIDITY, SkillTiming.WHEN_DAMAGED,
    ),
    _equipment_skill(
        "armor.silver_lion", "白银狮子", "白银狮子", SkillSourceType.ARMOR,
        SkillKind.LOCKED, SkillTiming.WHEN_DAMAGED, SkillTiming.EQUIPMENT_LOST,
    ),
)


WEAPON_ATTACK_RANGES = {
    "诸葛连弩": 1, "青釭剑": 2, "寒冰剑": 2, "雌雄双股剑": 2,
    "古锭刀": 2, "青龙偃月刀": 3, "丈八蛇矛": 3, "贯石斧": 3,
    "朱雀羽扇": 4, "方天画戟": 4, "麒麟弓": 5,
}

WEAPON_RANGE_SKILLS: tuple[SkillDefinition, ...] = tuple(
    _equipment_skill(
        f"weapon.range.{name}", f"{name}攻击范围", name,
        SkillSourceType.WEAPON, SkillKind.STATE, SkillTiming.ATTACK_RANGE,
    )
    for name in WEAPON_ATTACK_RANGES
)

WEAPON_EFFECT_SKILLS: tuple[SkillDefinition, ...] = (
    _equipment_skill(
        "weapon.zhuge", "诸葛连弩", "诸葛连弩", SkillSourceType.WEAPON,
        SkillKind.STATE, SkillTiming.SLASH_LEGALITY,
    ),
    _equipment_skill(
        "weapon.cixiong", "雌雄双股剑", "雌雄双股剑", SkillSourceType.WEAPON,
        SkillKind.TRIGGERED, SkillTiming.SLASH_TARGETED,
    ),
    _equipment_skill(
        "weapon.qinggang", "青釭剑", "青釭剑", SkillSourceType.WEAPON,
        SkillKind.LOCKED, SkillTiming.SLASH_TARGETED,
    ),
    _equipment_skill(
        "weapon.hanbing", "寒冰剑", "寒冰剑", SkillSourceType.WEAPON,
        SkillKind.TRIGGERED, SkillTiming.BEFORE_SLASH_DAMAGE,
    ),
    _equipment_skill(
        "weapon.guding", "古锭刀", "古锭刀", SkillSourceType.WEAPON,
        SkillKind.LOCKED, SkillTiming.BEFORE_SLASH_DAMAGE,
    ),
    _equipment_skill(
        "weapon.qinglong", "青龙偃月刀", "青龙偃月刀", SkillSourceType.WEAPON,
        SkillKind.TRIGGERED, SkillTiming.SLASH_DODGED,
    ),
    _equipment_skill(
        "weapon.zhangba", "丈八蛇矛", "丈八蛇矛", SkillSourceType.WEAPON,
        SkillKind.CONVERSION, SkillTiming.SLASH_CONVERSION,
        SkillTiming.RESPONSE_CONVERSION,
    ),
    _equipment_skill(
        "weapon.guanshi", "贯石斧", "贯石斧", SkillSourceType.WEAPON,
        SkillKind.TRIGGERED, SkillTiming.SLASH_DODGED,
    ),
    _equipment_skill(
        "weapon.fangtian", "方天画戟", "方天画戟", SkillSourceType.WEAPON,
        SkillKind.STATE, SkillTiming.SLASH_TARGETED,
    ),
    _equipment_skill(
        "weapon.zhuque", "朱雀羽扇", "朱雀羽扇", SkillSourceType.WEAPON,
        SkillKind.CONVERSION, SkillTiming.SLASH_CONVERSION,
    ),
    _equipment_skill(
        "weapon.qilin", "麒麟弓", "麒麟弓", SkillSourceType.WEAPON,
        SkillKind.TRIGGERED, SkillTiming.CAUSING_DAMAGE,
    ),
)

GENERAL_SKILLS: tuple[SkillDefinition, ...] = GENERAL_SKILL_DEFINITIONS

SKILL_DEFINITIONS = {
    skill.skill_id: skill
    for skill in (
        *EQUIPMENT_SKILLS, *WEAPON_RANGE_SKILLS, *WEAPON_EFFECT_SKILLS,
        *GENERAL_SKILLS,
    )
}


class SkillManager:
    """按照来源、有效性和时机查询技能，并执行已实现的规则效果。"""

    @staticmethod
    def skill_definition(skill_id: str) -> Optional[SkillDefinition]:
        """按稳定ID返回统一技能定义，供规则与只读界面共同使用。"""
        return SKILL_DEFINITIONS.get(skill_id)

    @staticmethod
    def _source_equipment(player: Player, skill: SkillDefinition) -> Optional[Card]:
        expected_type = {
            SkillSourceType.WEAPON: "weapon",
            SkillSourceType.ARMOR: "armor",
            SkillSourceType.MOUNT: ("offensive_mount", "defensive_mount"),
            SkillSourceType.TREASURE: "treasure",
        }.get(skill.source_type)
        if expected_type is None:
            return None
        expected_types = (
            expected_type if isinstance(expected_type, tuple) else (expected_type,)
        )
        return next(
            (
                card for card in player.equipment
                if card.equipment_type in expected_types
                and card.name == skill.source_name
            ),
            None,
        )

    def is_effective(self, player: Player, skill: SkillDefinition) -> bool:
        if not player.alive:
            return False
        if skill.source_type == SkillSourceType.GENERAL:
            return any(
                reference.skill_id == skill.skill_id
                for reference in player.general.skills
            )
        if skill.source_type in {
            SkillSourceType.WEAPON, SkillSourceType.ARMOR,
            SkillSourceType.MOUNT, SkillSourceType.TREASURE,
        }:
            return self._source_equipment(player, skill) is not None
        return False

    @staticmethod
    def general_skill_ids(player: Player) -> tuple[str, ...]:
        """返回所选武将赋予角色的技能 ID，不把显示名称当作程序主键。"""
        return tuple(reference.skill_id for reference in player.general.skills)

    def skills_at(
        self, player: Player, timing: SkillTiming
    ) -> list[SkillDefinition]:
        return [
            skill for skill in SKILL_DEFINITIONS.values()
            if timing in skill.timings and self.is_effective(player, skill)
        ]

    def triggered_actions(
        self, engine, player: Player, timing: SkillTiming, event: object
    ) -> list[TriggeredSkillAction]:
        """在统一时机查询模块化触发技，不按显示名称分派。"""
        actions: list[TriggeredSkillAction] = []
        for skill in self.skills_at(player, timing):
            handler = TRIGGERED_SKILL_HANDLERS.get(skill.skill_id)
            if handler and handler.can_trigger(engine, player, event):
                actions.append(handler.create_action(engine, player, event))
        return actions

    def prepare_draw_phase(self, engine, player: Player, event) -> None:
        """让摸牌阶段技能声明默认状态，不按技能名称写阶段特例。"""
        for skill in self.skills_at(player, SkillTiming.DRAW_PHASE):
            handler = TRIGGERED_SKILL_HANDLERS.get(skill.skill_id)
            prepare = getattr(handler, "prepare_draw_phase", None)
            if prepare is not None:
                prepare(engine, player, event)

    def prohibits_card_target(
        self, engine, source: Player, target: Player, card: Card
    ) -> bool:
        """查询目标角色的通用“不能成为此牌目标”锁定效果。"""
        for skill in self.skills_at(target, SkillTiming.EFFECT_VALIDITY):
            handler = TARGET_PROHIBITION_SKILL_HANDLERS.get(
                skill.skill_id
            )
            prohibits = getattr(handler, "prohibits_target", None)
            if prohibits is not None and prohibits(
                engine, target, source, card
            ):
                return True
        return False

    def global_triggered_actions(
        self, engine, timing: SkillTiming, event: object
    ) -> list[TriggeredSkillAction]:
        """从当前回合角色开始按座次收集全场同一时机的触发动作。"""
        players = engine.state.players
        if not players:
            return []
        start = engine.state.current_turn
        ordered = [
            players[(start + offset) % len(players)]
            for offset in range(len(players))
        ]
        actions: list[TriggeredSkillAction] = []
        for player in ordered:
            actions.extend(
                self.triggered_actions(engine, player, timing, event)
            )
        return actions

    def active_skill_actions(
        self, engine, player: Player
    ) -> list[ActiveSkillAction]:
        """返回当前出牌阶段可提交的通用主动技能动作。"""
        actions: list[ActiveSkillAction] = []
        for skill in self.skills_at(player, SkillTiming.ACTIVE_PLAY):
            handler = ACTIVE_SKILL_HANDLERS.get(skill.skill_id)
            if handler is None:
                continue
            action = handler.create_action(engine, player)
            if action is not None:
                actions.append(action)
        return actions

    @staticmethod
    def validate_active_skill(
        engine, action: ActiveSkillAction,
        cards: tuple[Card, ...], targets: tuple[Player, ...],
    ) -> bool:
        handler = ACTIVE_SKILL_HANDLERS.get(action.skill.skill_id)
        return bool(
            handler
            and handler.validate(engine, action, cards, targets)
        )

    @staticmethod
    def resolve_active_skill(
        engine, action: ActiveSkillAction,
        cards: tuple[Card, ...], targets: tuple[Player, ...],
    ) -> SkillResolutionResult:
        handler = ACTIVE_SKILL_HANDLERS.get(action.skill.skill_id)
        if handler is None:
            return SkillResolutionResult(
                action.skill, action.controller, applied=False
            )
        return handler.resolve(engine, action, cards, targets)

    @staticmethod
    def ai_decide_active_skill(
        engine, action: ActiveSkillAction
    ) -> Optional[ActiveSkillAIDecision]:
        handler = ACTIVE_SKILL_HANDLERS.get(action.skill.skill_id)
        chooser = getattr(handler, "ai_decide", None)
        return chooser(engine, action) if chooser else None

    @staticmethod
    def resolve_triggered_action(
        engine, action: TriggeredSkillAction
    ) -> SkillResolutionResult:
        handler = TRIGGERED_SKILL_HANDLERS.get(action.skill.skill_id)
        if handler is None:
            return SkillResolutionResult(
                action.skill, action.controller, applied=False
            )
        return handler.resolve(engine, action)

    @staticmethod
    def continue_triggered_action(
        engine, action: TriggeredSkillAction,
        request: SkillResolutionRequest, choice,
    ) -> SkillResolutionResult:
        handler = TRIGGERED_SKILL_HANDLERS.get(action.skill.skill_id)
        continuation = getattr(handler, "continue_resolution", None)
        if continuation is None:
            return SkillResolutionResult(
                action.skill, action.controller, applied=False, announce=False
            )
        return continuation(engine, action, request, choice)

    @staticmethod
    def ai_choose_triggered_target(
        engine, action: TriggeredSkillAction,
        request: SkillResolutionRequest,
    ) -> Optional[Player]:
        handler = TRIGGERED_SKILL_HANDLERS.get(action.skill.skill_id)
        chooser = getattr(handler, "ai_choose_target", None)
        return chooser(engine, action, request) if chooser else None

    def judgment_replacement_actions(
        self, engine, event
    ) -> list[JudgmentReplacementAction]:
        """从当前回合角色开始按座次收集判定牌生效前的合法替换机会。"""
        players = engine.state.players
        start = engine.state.current_turn
        ordered = [
            players[(start + offset) % len(players)]
            for offset in range(len(players))
        ]
        actions: list[JudgmentReplacementAction] = []
        for player in ordered:
            for skill in self.skills_at(
                player, SkillTiming.JUDGMENT_BEFORE_EFFECT
            ):
                handler = JUDGMENT_REPLACEMENT_SKILL_HANDLERS.get(
                    skill.skill_id
                )
                if handler is None:
                    continue
                action = handler.create_action(engine, player, event)
                if action.candidates:
                    actions.append(action)
        return actions

    @staticmethod
    def resolve_judgment_replacement(
        engine, action: JudgmentReplacementAction, replacement: Card,
    ) -> JudgmentReplacementResult:
        handler = JUDGMENT_REPLACEMENT_SKILL_HANDLERS.get(
            action.skill.skill_id
        )
        if handler is None:
            return JudgmentReplacementResult(
                action=action, event=action.event, applied=False
            )
        return handler.resolve(engine, action, replacement)

    @staticmethod
    def ai_choose_judgment_replacement(
        engine, action: JudgmentReplacementAction
    ) -> Optional[Card]:
        handler = JUDGMENT_REPLACEMENT_SKILL_HANDLERS.get(
            action.skill.skill_id
        )
        chooser = getattr(handler, "ai_choose_card", None)
        return chooser(engine, action) if chooser else None

    @staticmethod
    def ai_should_activate_triggered(
        engine, action: TriggeredSkillAction
    ) -> bool:
        """把触发技是否发动交给技能模块；无策略的可选技默认不发动。"""
        handler = TRIGGERED_SKILL_HANDLERS.get(action.skill.skill_id)
        if handler is None:
            return False
        evaluator = getattr(handler, "ai_should_activate", None)
        if evaluator is None:
            return action.skill.mandatory
        return bool(evaluator(
            engine,
            action,
            SkillAIContext(window="trigger", event=action.event),
        ))

    def optional_response_skill(
        self, player: Player, required_card: str
    ) -> Optional[SkillDefinition]:
        # 牌的转化不是一个需要抢在响应窗口前询问的触发事件。
        # 这里只返回八卦阵等真正需要单独确认发动的响应时机技能。
        if required_card != "闪":
            return None
        return next(
            (
                skill for skill in self.skills_at(
                    player, SkillTiming.RESPONSE_REQUIRED
                )
                if not skill.mandatory
            ),
            None,
        )

    def response_conversion_options(
        self, player: Player, required_card: str
    ) -> list[ResponseConversionOption]:
        """返回当前“需要牌”窗口可操作的转化动作，不检查材料是否充足。"""
        options = self.conversion_options(
            player, required_card, SkillTiming.RESPONSE_CONVERSION
        )
        if required_card == "杀":
            if self.has_skill(player, "weapon.zhangba"):
                options.append(ResponseConversionOption(
                    SKILL_DEFINITIONS["weapon.zhangba"],
                    "杀", 2, "equipment", SkillTiming.RESPONSE_CONVERSION,
                ))
        return options

    def play_conversion_options(
        self, player: Player, effective_card_name: str
    ) -> list[ResponseConversionOption]:
        """返回出牌阶段可自主操作的武将牌转化动作。"""
        return self.conversion_options(
            player, effective_card_name, SkillTiming.SLASH_CONVERSION
        )

    def active_play_conversion_options(
        self, engine, player: Player
    ) -> list[ResponseConversionOption]:
        """返回当前可进入选牌态的主动转化；不得检查是否存在合法目标。"""
        options = self.conversion_options(
            player, None, SkillTiming.PLAY_CONVERSION
        )
        return [
            option for option in options
            if self.can_activate_play_conversion(engine, player, option)
        ]

    def conversion_options(
        self, player: Player, effective_card_name: Optional[str],
        timing: SkillTiming,
    ) -> list[ResponseConversionOption]:
        options: list[ResponseConversionOption] = []
        for skill in self.skills_at(player, timing):
            handler = CONVERSION_SKILL_HANDLERS.get(skill.skill_id)
            if (
                handler
                and (
                    effective_card_name is None
                    or handler.effective_card_name == effective_card_name
                )
            ):
                candidates = handler.candidates(
                    player, self.is_effective(player, skill)
                )
                required_cards = getattr(
                    handler, "required_count", lambda _player, _cards:
                    handler.required_cards
                )(player, candidates)
                options.append(ResponseConversionOption(
                    skill,
                    handler.effective_card_name,
                    required_cards,
                    handler.entry_type,
                    timing,
                    getattr(handler, "fixed_materials", False),
                ))
        return options

    def can_activate_play_conversion(
        self, engine, player: Player, option: ResponseConversionOption
    ) -> bool:
        handler = CONVERSION_SKILL_HANDLERS.get(option.skill.skill_id)
        checker = getattr(handler, "can_activate", None) if handler else None
        if checker is None:
            return False
        return bool(
            self.is_effective(player, option.skill)
            and checker(engine, player)
        )

    @staticmethod
    def record_play_conversion(
        engine, player: Player, option: ResponseConversionOption
    ) -> None:
        handler = CONVERSION_SKILL_HANDLERS.get(option.skill.skill_id)
        recorder = getattr(handler, "record_use", None) if handler else None
        if recorder is not None:
            recorder(engine, player)

    def conversion_candidates(
        self, player: Player, option: ResponseConversionOption
    ) -> list[Card]:
        handler = CONVERSION_SKILL_HANDLERS.get(option.skill.skill_id)
        if handler:
            return handler.candidates(
                player, self.is_effective(player, option.skill)
            )
        if option.skill.skill_id == "weapon.zhangba":
            return list(player.hand)
        return []

    def validate_conversion(
        self, player: Player, option: ResponseConversionOption,
        cards: list[Card],
    ) -> bool:
        handler = CONVERSION_SKILL_HANDLERS.get(option.skill.skill_id)
        if handler:
            return handler.validate(
                player, cards, self.is_effective(player, option.skill)
            )
        if option.skill.skill_id == "weapon.zhangba":
            return self.can_convert_zhangba(player, cards)
        return False

    def build_conversion_card(
        self, option: ResponseConversionOption, cards: list[Card]
    ) -> Card:
        handler = CONVERSION_SKILL_HANDLERS.get(option.skill.skill_id)
        if handler:
            return handler.build_effective_card(cards)
        return build_converted_card(
            option.effective_card_name, cards
        )

    @staticmethod
    def build_effective_card(
        effective_card_name: str, cards: list[Card]
    ) -> Card:
        """不依赖具体技能名构造转化后的有效牌面。"""
        return build_converted_card(effective_card_name, cards)

    def can_convert_to(
        self, player: Player, cards: list[Card],
        effective_card_name: str, timing: SkillTiming,
    ) -> bool:
        return any(
            self.validate_conversion(player, option, cards)
            for option in self.conversion_options(
                player, effective_card_name, timing
            )
        )

    def ai_choose_conversion(
        self, engine, player: Player, effective_card_name: str,
        timing: SkillTiming, context: SkillAIContext,
    ) -> Optional[SkillAIConversionDecision]:
        """由各技能模块选择材料和目标，管理器只负责统一校验。"""
        options = (
            self.response_conversion_options(
                player, effective_card_name
            )
            if timing == SkillTiming.RESPONSE_CONVERSION
            else self.conversion_options(
                player, effective_card_name, timing
            )
        )
        for option in options:
            handler = CONVERSION_SKILL_HANDLERS.get(
                option.skill.skill_id
            )
            candidates = self.conversion_candidates(player, option)
            choose_cards = getattr(
                handler, "ai_choose_cards", None
            ) if handler else None
            cards = (
                choose_cards(engine, player, candidates, context)
                if choose_cards
                else candidates[:option.required_cards]
            )
            if not self.validate_conversion(player, option, cards):
                continue
            target = None
            if context.legal_targets:
                effective_card = self.build_conversion_card(option, cards)
                legal_targets = list(context.legal_targets)
                if timing == SkillTiming.SLASH_CONVERSION:
                    legal_targets = [
                        candidate for candidate in legal_targets
                        if engine.is_legal_play_target(
                            player,
                            effective_card,
                            candidate,
                            tuple(cards),
                        )
                    ]
                    # 规则合法不等于策略上值得提交：过滤会被当前防具
                    # 直接无效的【杀】，但不改变牌和目标的规则合法集。
                    from src.ai import viable_slash_targets
                    legal_targets = viable_slash_targets(
                        engine,
                        player,
                        effective_card,
                        legal_targets,
                        excluded_cards=tuple(cards),
                    )
                if not legal_targets:
                    continue
                choose_target = getattr(
                    handler, "ai_choose_target", None
                ) if handler else None
                target = (
                    choose_target(
                        engine, player,
                        legal_targets, context,
                    )
                    if choose_target
                    else legal_targets[0]
                )
                if target not in legal_targets:
                    continue
                if (
                    timing == SkillTiming.SLASH_CONVERSION
                    and not engine.can_submit_conversion(
                        player, option, cards, (target,)
                    )
                ):
                    continue
            return SkillAIConversionDecision(
                option=option, cards=tuple(cards), target=target
            )
        return None

    def ai_choose_active_play_conversion(
        self, engine, player: Player, option: ResponseConversionOption,
    ) -> Optional[SkillAIConversionDecision]:
        """为一项主动转化选择材料与目标，并用真人入口重新校验。"""
        handler = CONVERSION_SKILL_HANDLERS.get(
            option.skill.skill_id
        )
        if handler is None:
            return None
        candidates = self.conversion_candidates(player, option)
        if not candidates:
            return None

        # 先按所有候选材料的并集提供公开合法目标；技能AI不得借此读取手牌牌面。
        target_candidates: list[Player] = []
        for target in engine.state.players:
            if any(
                engine.can_submit_active_conversion(
                    player, option, [candidate], (target,)
                )
                for candidate in candidates
            ):
                target_candidates.append(target)
        context = SkillAIContext(
            window="play_conversion",
            legal_targets=tuple(target_candidates),
        )
        chooser = getattr(handler, "ai_choose_cards", None)
        cards = (
            chooser(engine, player, candidates, context)
            if chooser is not None
            else (
                candidates
                if option.fixed_materials
                else candidates[:option.required_cards]
            )
        )
        if not self.validate_conversion(player, option, cards):
            return None
        effective = self.build_conversion_card(option, cards)
        legal_targets = engine.get_legal_play_targets(
            player, effective, tuple(cards)
        ) if engine.card_requires_manual_target(effective) else []
        target = None
        if legal_targets:
            choose_target = getattr(
                handler, "ai_choose_target", None
            )
            target = (
                choose_target(engine, player, legal_targets, context)
                if choose_target is not None else legal_targets[0]
            )
            if (
                target not in legal_targets
                or not engine.can_submit_active_conversion(
                    player, option, cards, (target,)
                )
            ):
                return None
        elif not engine.can_submit_active_conversion(
            player, option, cards, ()
        ):
            return None
        return SkillAIConversionDecision(
            option=option,
            cards=tuple(cards),
            target=target,
        )

    def nullifying_skill(
        self, target: Player, source_name: str, source_card: Optional[Card]
    ) -> Optional[SkillDefinition]:
        for skill in self.skills_at(target, SkillTiming.EFFECT_VALIDITY):
            if skill.skill_id == "armor.vine":
                if source_name in ("南蛮入侵", "万箭齐发", "万剑齐发"):
                    return skill
                if (
                    source_name == "杀" and source_card is not None
                    and source_card.name == "杀"
                ):
                    return skill
            if (
                skill.skill_id == "armor.renwang"
                and source_name == "杀"
                and source_card is not None
                and source_card.name in ("杀", "火杀", "雷杀")
                and source_card.color == "black"
            ):
                return skill
        return None

    def modify_damage(
        self, target: Player, event: DamageEvent
    ) -> tuple[DamageEvent, list[SkillApplication]]:
        amount = max(0, event.amount)
        applications: list[SkillApplication] = []
        # 此入口只处理“受到伤害时”的装备技能。调用方须先结算同一角色
        # 的武将技能，并在每项效果后重新检查伤害事件是否仍继续。
        skills = self.skills_at(target, SkillTiming.WHEN_DAMAGED)
        seen: set[str] = set()
        for skill in skills:
            if skill.skill_id in seen:
                continue
            seen.add(skill.skill_id)
            if skill.skill_id == "armor.vine" and event.nature == DamageNature.FIRE:
                amount += 1
                applications.append(SkillApplication(
                    skill, f"{target.general.name} 的【藤甲】令火焰伤害+1"
                ))
            elif skill.skill_id == "armor.silver_lion" and amount > 1:
                amount = 1
                applications.append(SkillApplication(
                    skill, f"{target.general.name} 的【白银狮子】将伤害减至1点"
                ))
        return event.model_copy(update={"amount": amount}), applications

    def equipment_lost(
        self, player: Player, card: Card
    ) -> list[SkillApplication]:
        skill = SKILL_DEFINITIONS.get("armor.silver_lion")
        if (
            skill and card.name == skill.source_name
            and player.alive and player.hp < player.max_hp
        ):
            player.hp += 1
            return [SkillApplication(
                skill,
                f"{player.general.name} 失去【白银狮子】，回复1点体力"
                f"（{player.hp}/{player.max_hp}）",
            )]
        return []

    def attack_range(
        self, player: Player, excluded_cards: tuple[Card, ...] = ()
    ) -> int:
        weapon = next(
            (
                card for card in player.equipment
                if card not in excluded_cards
                and card.equipment_type == "weapon"
            ),
            None,
        )
        return WEAPON_ATTACK_RANGES.get(weapon.name, 1) if weapon else 1

    @staticmethod
    def attack_range_for_weapon(weapon: Optional[Card]) -> int:
        """供AI轻量推演使用；不改变角色当前装备区。"""
        return WEAPON_ATTACK_RANGES.get(weapon.name, 1) if weapon else 1

    def has_skill(self, player: Player, skill_id: str) -> bool:
        skill = SKILL_DEFINITIONS.get(skill_id)
        return bool(skill and self.is_effective(player, skill))

    def slash_unlimited(
        self, player: Player, excluded_cards: tuple[Card, ...] = ()
    ) -> bool:
        source = self._source_equipment(
            player, SKILL_DEFINITIONS["weapon.zhuge"]
        )
        return bool(source and source not in excluded_cards)

    def slash_ignores_armor(
        self, player: Player, excluded_cards: tuple[Card, ...] = ()
    ) -> bool:
        source = self._source_equipment(
            player, SKILL_DEFINITIONS["weapon.qinggang"]
        )
        return bool(source and source not in excluded_cards)

    def slash_target_limit(
        self, player: Player, was_last_hand_card: bool,
        excluded_cards: tuple[Card, ...] = (),
    ) -> int:
        source = self._source_equipment(
            player, SKILL_DEFINITIONS["weapon.fangtian"]
        )
        if (
            was_last_hand_card and source
            and source not in excluded_cards
        ):
            return 3
        return 1

    def can_convert_zhuque(self, player: Player, card: Card) -> bool:
        return card.name == "杀" and self.has_skill(player, "weapon.zhuque")

    def can_convert_zhangba(self, player: Player, cards: list[Card]) -> bool:
        return (
            len(cards) == 2
            and len({card.id for card in cards}) == 2
            and all(card in player.hand for card in cards)
            and self.has_skill(player, "weapon.zhangba")
        )

    def before_slash_damage(
        self, source: Player, target: Player, event: DamageEvent
    ) -> tuple[DamageEvent, list[SkillApplication]]:
        applications: list[SkillApplication] = []
        if (
            self.has_skill(source, "weapon.guding")
            and not target.hand and event.amount > 0
        ):
            skill = SKILL_DEFINITIONS["weapon.guding"]
            event = event.model_copy(update={"amount": event.amount + 1})
            applications.append(SkillApplication(
                skill, f"{source.general.name} 的【古锭刀】令伤害+1"
            ))
        return event, applications
