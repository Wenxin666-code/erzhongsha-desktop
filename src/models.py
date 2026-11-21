from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class GeneralSkillRef(BaseModel):
    """武将牌与技能定义之间的稳定引用。"""
    skill_id: str
    name: str


class General(BaseModel):
    id: str
    name: str
    kingdom: str
    hp: int
    # 现有武将牌图片与选将界面均使用 default；未来皮肤系统通过 skin_id 覆盖。
    default_skin_id: str = "default"
    # 新接入武将默认使用独立透明边框；旧武将可在数据中显式关闭。
    use_portrait_frame: bool = True
    gender: str = "male"
    skills: list[GeneralSkillRef] = []
    # 只有技能代码已经完整注册并通过测试的武将才能进入开局选择池。
    playable: bool = False


class CardKind(str, Enum):
    BASIC = "basic"
    TRICK = "trick"
    EQUIPMENT = "equipment"


class DamageNature(str, Enum):
    """伤害属性；普通伤害不会触发铁索连环传导。"""
    NORMAL = "normal"
    FIRE = "fire"
    THUNDER = "thunder"


class JudgmentStep(str, Enum):
    """通用判定事件所处的结算步骤。"""
    CREATED = "created"
    REVEALED = "revealed"
    MODIFYING = "modifying"
    FINALIZED = "finalized"
    COMPLETED = "completed"


class PromptType(str, Enum):
    """需要由真人或 AI 作出选择的统一提示类型。"""
    ACTIVATE_SKILL = "activate_skill"
    RESPONSE_CARD = "response_card"
    CHOOSE_TARGET = "choose_target"
    CHOOSE_CARDS = "choose_cards"
    CHOOSE_OPTION = "choose_option"
    CONFIRM_ACTION = "confirm_action"


class SkillSourceType(str, Enum):
    """技能来源；来源决定技能何时随区域变化而获得或失去。"""
    GENERAL = "general"
    WEAPON = "weapon"
    ARMOR = "armor"
    MOUNT = "mount"
    TREASURE = "treasure"
    TEMPORARY = "temporary"


class SkillKind(str, Enum):
    """技能操作类型；锁定技的 mandatory 必须为 True。"""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    LOCKED = "locked"
    CONVERSION = "conversion"
    STATE = "state"
    LIMITED = "limited"


class SkillTiming(str, Enum):
    """当前引擎已经开放的技能检查时机。"""
    DRAW_PHASE = "draw_phase"
    AFTER_DRAW_CARDS = "after_draw_cards"
    DAMAGE_START = "damage_start"
    CAUSING_DAMAGE = "causing_damage"
    RESPONSE_REQUIRED = "response_required"
    EFFECT_VALIDITY = "effect_validity"
    DAMAGE_MODIFY = "damage_modify"
    EQUIPMENT_LOST = "equipment_lost"
    ATTACK_RANGE = "attack_range"
    SLASH_LEGALITY = "slash_legality"
    SLASH_CONVERSION = "slash_conversion"
    SLASH_TARGETED = "slash_targeted"
    SLASH_DODGED = "slash_dodged"
    BEFORE_SLASH_DAMAGE = "before_slash_damage"
    AFTER_SLASH_DAMAGE = "after_slash_damage"
    # “受到伤害时”属于伤害事件内部、扣减体力之前的独立窗口。
    # 它不得与扣减体力并处理濒死后的 AFTER_DAMAGE 混用。
    WHEN_DAMAGED = "when_damaged"
    AFTER_CAUSING_DAMAGE = "after_causing_damage"
    AFTER_DAMAGE = "after_damage"
    # 供“任意角色受到伤害后”类技能使用；由全场触发队列按座次收集。
    AFTER_ANY_DAMAGE = "after_any_damage"
    DAMAGE_END = "damage_end"
    ENTER_DYING = "enter_dying"
    AFTER_CARD_RESPONSE = "after_card_response"
    # 牌完成合法使用声明并离开原区域后、开始处理目标响应和牌效果前。
    CARD_USE = "card_use"
    AFTER_CARD_USE = "after_card_use"
    # 一张牌的全部目标与效果已经结算完毕；用于“此牌结算后”类技能。
    AFTER_CARD_RESOLUTION = "after_card_resolution"
    # 牌因锦囊效果被弃置后，保留锦囊、操作者、目标和移动记录的因果窗口。
    CARD_DISCARDED_BY_TRICK = "card_discarded_by_trick"
    # 真实出牌阶段结束、进入弃牌阶段之前。
    PLAY_PHASE_END = "play_phase_end"
    JUDGMENT_BEFORE_EFFECT = "judgment_before_effect"
    RESPONSE_CONVERSION = "response_conversion"
    PLAY_CONVERSION = "play_conversion"
    ACTIVE_PLAY = "active_play"


class SkillDefinition(BaseModel):
    """静态技能定义；效果代码由 skill_id 在统一技能管理器中分派。"""
    skill_id: str
    name: str
    source_type: SkillSourceType
    source_name: str
    kind: SkillKind
    timings: tuple[SkillTiming, ...]
    mandatory: bool = False
    description: str = ""


class Card(BaseModel):
    id: str
    name: str
    suit: str
    rank: str
    kind: CardKind
    # 装备牌所属槽位；普通牌为 None。效果以后可继续挂在这个分类上实现。
    equipment_type: Optional[str] = None
    # 转化牌可以没有花色但仍有颜色；None 表示由实体花色自然推导。
    # 允许值为 red、black、colorless。
    color_override: Optional[str] = None

    @property
    def color(self) -> Optional[str]:
        if self.color_override == "colorless":
            return None
        if self.color_override in ("red", "black"):
            return self.color_override
        if self.suit in ("heart", "diamond"):
            return "red"
        if self.suit in ("spade", "club"):
            return "black"
        return None


class Player(BaseModel):
    seat: int
    general: General
    # 当前选用的皮肤；属于本局角色状态，不改变武将牌的稳定 general.id。
    skin_id: str = "default"
    hp: int
    max_hp: int
    hand: list[Card] = []
    equipment: list[Card] = []
    judgment_area: list[Card] = []
    alive: bool = True
    is_ai: bool = False
    # 暂无身份模式时为空，默认其他座次均为敌对；以后组队模式写入相同 side。
    side: Optional[str] = None
    slash_used: bool = False  # 本回合是否已出过杀
    # 【杀】次数使用统一计数；slash_used 仅保留为旧入口兼容状态。
    slash_use_count: int = 0
    # 当前出牌阶段已经生效的额外次数，以及等待下个出牌阶段生效的次数。
    active_slash_use_bonus: int = 0
    pending_slash_use_bonus: int = 0
    wine_used: bool = False  # 本出牌阶段是否已使用过酒
    drunk: bool = False  # 使用【酒】后，下一张杀伤害+1
    pending_slash_damage: int = 1
    pending_slash_nature: DamageNature = DamageNature.NORMAL
    # 摸牌阶段实际摸牌数，以及当前回合每张【杀】的基础伤害。
    # 两者由阶段/技能规则修改，界面只读取，不自行推导。
    draw_phase_card_count: int = 2
    turn_slash_base_damage: int = 1
    # 记录该角色最近一次“使用”的有效牌面；打出、弃置和重铸不写入。
    last_used_card: Optional[Card] = None
    # 当前出牌阶段实际使用的有效牌名次数；转化牌按转化后的牌名统计。
    play_phase_card_use_counts: dict[str, int] = Field(default_factory=dict)
    # 等待该角色下次真实进入摸牌阶段时加入基础摸牌数；跳过摸牌阶段不消耗。
    pending_draw_phase_bonus: int = 0
    chained: bool = False  # 横置；属性伤害会在所有横置角色之间传导
    skip_draw: bool = False
    skip_play: bool = False
    # 以“当前回合”为作用域的技能发动次数；每名角色的回合开始时统一清空。
    # 因此既能表达“出牌阶段限X次”，也能表达“每回合限X次”。
    skill_usage_counts: dict[str, int] = Field(default_factory=dict)


class DamageEvent(BaseModel):
    """一次伤害的完整上下文，供装备、技能及连环传导共同使用。"""
    amount: int = 1
    nature: DamageNature = DamageNature.NORMAL
    source_player: Optional[Player] = None
    # source_card 表示结算时的有效牌面；转化牌可能是没有规则区域的虚拟副本。
    source_card: Optional[Card] = None
    # 实体组成牌才允许被获得、弃置或移动；普通实体牌通常只有一张。
    source_physical_cards: tuple[Card, ...] = ()
    chain_origin: Optional[Player] = None
    is_chain_transfer: bool = False
    parent_slash_id: Optional[int] = None


class DrawPhaseEvent(BaseModel):
    """一次真实进入摸牌阶段后的可修改规则上下文。"""

    player: Player
    base_draw_count: int = 2
    draw_count: int = 2


class DrawCardsEvent(BaseModel):
    """一次不可拆分的摸牌动作；多张牌共享同一个 draw_id。"""

    draw_id: int
    player: Player
    cards: tuple[Card, ...]
    count: int
    reason: str = "摸牌"
    source_event_id: Optional[int] = None
    move_ids: tuple[int, ...] = ()


class DyingEvent(BaseModel):
    """一名角色已经进入濒死时冻结的来源上下文。"""

    target: Player
    damage_event: Optional[DamageEvent] = None


class CardResponseEvent(BaseModel):
    """一次已经成功提交的使用/打出响应，供后续触发技读取。"""
    player: Player
    effective_card: Card
    physical_cards: tuple[Card, ...] = ()
    action: str = "打出"
    source_player: Optional[Player] = None
    source_name: str = ""
    source_card: Optional[Card] = None


class ActiveCardUseEvent(BaseModel):
    """主动技能把若干实体牌作为一张牌使用后冻结的规则上下文。"""
    player: Player
    skill_id: str
    skill_name: str
    effective_card: Card
    physical_cards: tuple[Card, ...]
    target_seats: tuple[int, ...] = ()


class CardUseEvent(BaseModel):
    """一张牌已经合法提交使用后的统一上下文。"""

    player: Player
    effective_card: Card
    physical_cards: tuple[Card, ...] = ()
    previous_card: Optional[Card] = None
    target_seats: tuple[int, ...] = ()


class TrickCardDiscardEvent(BaseModel):
    """一张牌因锦囊效果被弃置后的完整因果上下文。"""

    actor: Player
    target: Player
    trick_name: str
    source_card: Optional[Card] = None
    discarded_card: Card
    move_event: "CardMoveEvent"


class PlayPhaseEndEvent(BaseModel):
    """一名角色的真实出牌阶段即将结束。"""

    player: Player
    card_use_counts: dict[str, int] = Field(default_factory=dict)


class HpLossEvent(BaseModel):
    """失去体力不是伤害：没有伤害来源，也不进入伤害触发链。"""
    target: Player
    amount: int
    reason: str = ""
    source_skill_id: Optional[str] = None


class SlashEvent(BaseModel):
    """一张【杀】从提交使用到所有目标结算完成的独立上下文。"""
    slash_id: int
    source_player: Player
    physical_cards: list[Card]
    effective_name: str
    effective_card: Optional[Card] = None
    targets: list[Player]
    current_target_index: int = 0
    damage: int = 1
    nature: DamageNature = DamageNature.NORMAL
    ignores_armor_for: set[int] = set()
    was_last_hand_card: bool = False
    forced_hit_targets: set[int] = set()
    completed_targets: set[int] = set()


class JudgmentEvent(BaseModel):
    """一次独立判定；可由任意阶段或其他结算事件创建。"""
    judgment_id: int
    # 规则语义中的“进行判定的角色”。它不是判定牌、延时锦囊或
    # 判定技能的来源，因此必须与 source_player/source_card 分开。
    judging_player: Player
    reason: str
    result_rule: str
    source_player: Optional[Player] = None
    source_card: Optional[Card] = None
    parent_event_id: Optional[int] = None
    initial_card: Optional[Card] = None
    current_card: Optional[Card] = None
    replaced_cards: list[Card] = []
    result: Optional[bool] = None
    step: JudgmentStep = JudgmentStep.CREATED


class PromptContext(BaseModel):
    """可序列化的选择提示；不得保存函数、界面控件或完整角色对象。"""
    prompt_id: int
    prompt_type: PromptType
    player_seat: int
    message: str
    skill_id: Optional[str] = None
    skill_name: Optional[str] = None
    parent_event_id: Optional[int] = None
    legal_card_ids: tuple[str, ...] = ()
    legal_target_seats: tuple[int, ...] = ()
    required_cards: int = 0
    required_targets: int = 0
    window: str = "generic"


class PlayerChoice(BaseModel):
    """真人、AI与未来网络客户端共用的唯一玩家选择格式。"""
    prompt_id: int
    player_seat: int
    confirmed: bool
    card_ids: tuple[str, ...] = ()
    target_seats: tuple[int, ...] = ()
    option_id: Optional[str] = None


class RuleEvent(BaseModel):
    """规则层发布给客户端的可序列化事件信封。"""
    event_id: int
    event_type: str
    actor_seat: Optional[int] = None
    target_seats: tuple[int, ...] = ()
    card_ids: tuple[str, ...] = ()
    data: dict[str, Any] = Field(default_factory=dict)
    visibility: str = "public"
    recipient_seats: tuple[int, ...] = ()


class ResolutionFrame(BaseModel):
    """一个可暂停并恢复的结算帧；state 保存该父事件的冻结现场。"""
    event_id: int
    event_type: str
    parent_event_id: Optional[int] = None
    state: dict[str, Any] = {}


class CardMoveEvent(BaseModel):
    """一张实体牌的规则区域移动记录。"""
    move_id: int
    card: Card
    from_player_seat: Optional[int] = None
    to_player_seat: Optional[int] = None
    from_zone: str
    to_zone: str
    reason: str
    source_event_id: Optional[int] = None
    # 同一次移动若包含多张实体牌，各单牌移动共享批次号，并保存批内位置。
    batch_id: Optional[int] = None
    batch_index: int = 0
    batch_size: int = 1
    visibility: str = "private"


class CardRevealEvent(BaseModel):
    """公开一张实体牌的信息，但不改变该实体牌所在的规则区域。"""
    reveal_id: int
    card: Card
    owner_seat: Optional[int] = None
    from_zone: str
    visibility: str = "public"
    reason: str
    source_event_id: Optional[int] = None


class Phase(str, Enum):
    PREPARE = "prepare"
    JUDGE = "judge"
    DRAW = "draw"
    PLAY = "play"
    DISCARD = "discard"
    END = "end"


class GameState(BaseModel):
    players: list[Player]
    current_turn: int = 0
    phase: Phase = Phase.PREPARE
    turn_count: int = 0
    winner: Optional[str] = None
    winner_seat: Optional[int] = None

