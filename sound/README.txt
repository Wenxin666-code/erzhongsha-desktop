二中杀音效整理说明
==================

来源：
assets 下的原始完整素材包

本目录只保存游戏实际使用的副本。程序通过稳定英文键读取，不依赖来源目录中的
机翻文件名。

背景音乐：

music/main_theme.ogg
    来源素材“三国杀开局音乐_爱给网_aigei_com.mp3”。源文件实际为 AAC 编码，
    统一转换为 48 kHz 立体声 OGG，并清除设备元数据。游戏启动后通过独立音乐
    通道无限循环播放，默认音量为30%，不会占用或打断卡牌、装备和技能语音通道。

重要机翻对应：

飞机.ogg          -> jink.ogg             -> 【闪】
注销.ogg          -> nullification.ogg    -> 【无懈可击】
斜杠.ogg          -> slash.ogg            -> 【杀】
火烧迹地.ogg      -> fire_slash.ogg       -> 【火杀】
雷斜杠.ogg        -> thunder_slash.ogg    -> 【雷杀】
兴奋剂.ogg        -> analeptic.ogg        -> 【酒】
抓举.ogg          -> snatch.ogg           -> 【顺手牵羊】
奇异恩典.ogg      -> amazing_grace.ogg    -> 【五谷丰登】
神的救恩.ogg      -> god_salvation.ogg    -> 【桃园结义】
抵押品.ogg        -> collateral.ogg        -> 【借刀杀人】

装备目录中的英文/机翻对应：

Axe               -> 贯石斧
Fan               -> 朱雀羽扇
halberg            -> 方天画戟
八图              -> 八卦阵
双剑              -> 雌雄双股剑
叶片              -> 青龙偃月刀
寒冰之剑          -> 寒冰剑
弩                -> 诸葛连弩
矛                -> 丈八蛇矛
葡萄树            -> 藤甲
银狮              -> 白银狮子
青钢剑            -> 青釭剑

若以后替换素材，只需保持 sound 下的目标文件名不变，无需修改游戏规则代码。

武将语音按“general.id / skin_id / 类型”整理：

general/guanyu/default/skill/general.wusheng/1.ogg、2.ogg
    来源素材“武胜1.ogg、武胜2.ogg”，对应关羽默认皮肤的【武圣】。

general/guanyu/default/death.ogg
    来源素材“死亡/关羽.ogg”，对应关羽默认皮肤的阵亡语音。

general/caocao/default/skill/general.jianxiong/1.ogg、2.ogg
    来源素材“吴健雄1.ogg、吴健雄2.ogg”（素材包对 jianxiong 的机翻文件名），
    对应曹操默认皮肤的【奸雄】。

general/caocao/default/death.ogg
    来源素材“死亡/曹操.ogg”，对应曹操默认皮肤的阵亡语音。

公开版不包含私人录制的DIY武将技能和阵亡语音；缺失时静默跳过，不影响规则结算。

现有武将牌图片、技能语音和阵亡语音全部视为 default 皮肤。选将界面在没有
独立皮肤选择步骤时始终展示 default 皮肤。以后增加皮肤时使用稳定英文 skin_id，
例如 skin_001；不得把可修改的中文皮肤名称作为文件夹名或存档标识。

播放技能语音时使用 general_id、skin_id、skill_id 三个稳定标识；播放阵亡语音
时使用 general_id、skin_id。当前皮肤缺少某类语音时，只回退到同一武将的
default 皮肤，不得回退到其他武将。

阵亡语音只在统一濒死求救全部结束、引擎正式产生 player_died 事件后播放；
进入濒死、等待求桃、成功获救或重复执行死亡清理时均不得播放。
