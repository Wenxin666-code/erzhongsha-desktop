# 二中杀 · 桌面单机版

基于 Pygame 的双座位单机卡牌对战游戏，包含 DIY 武将、技能结算和 AI 对手。依次为两个座位选将，进入对局后二号位由 AI 控制。

当前公开发布版为 **v0.1.0**，提供 Windows x64 免安装包。公开版以文字牌面替代个人肖像，缺少的专属语音静默跳过。

## 下载与游玩

[下载 Windows x64 免安装版](https://github.com/Wenxin666-code/erzhongsha-desktop/releases/latest/download/Erzhongsha-windows-x64.zip) · [版本与更新记录](https://github.com/Wenxin666-code/erzhongsha-desktop/releases)

1. 下载 ZIP 成品包并完整解压。
2. 进入“二中杀”文件夹，双击 `二中杀.exe`。
3. 保留同目录下的 `_internal` 文件夹，无需安装 Python。

仓库与发布页公开可访问，无需登录 GitHub。发布页的 `Source code` 是源码压缩包。当前不提供网页入口或联机功能，也未提供 Linux、macOS 成品包。

## 从源码运行

需要 Git 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)。在 Windows PowerShell 中执行：

```powershell
git clone https://github.com/Wenxin666-code/erzhongsha-desktop.git
cd erzhongsha-desktop
uv sync --locked --managed-python
uv run --locked python main.py
```

项目通过 `.python-version` 固定 Python 3.11.15，依赖版本以 `uv.lock` 为准。首次同步需要联网下载解释器和依赖；游戏本身离线运行。源码运行以 Windows 为主要维护环境，其他系统兼容性未在本说明中保证。

## 项目结构

| 路径 | 内容 |
| --- | --- |
| `main.py` | 桌面入口与界面 |
| `src/` | 引擎、数据模型、技能与 AI |
| `data/` | 游戏运行必需的牌堆和武将规则 |
| `images/`、`sound/` | 公开版运行素材 |
| `tests/` | 回归测试 |
| `scripts/` | 检查与打包配置 |
| `docs/` | 规则、设计、素材说明及历史记录 |

运行时保持上述相对目录完整。历史环境与迁移记录见 [docs/迁移记录.md](docs/迁移记录.md)，不作为第二套安装步骤。

## 开发检查

在项目根目录执行：

```powershell
uv run --locked python scripts/check.py
# 仅运行指定测试文件
uv run --locked python scripts/check.py tests/test_weapon_effects.py
```

脚本先执行 Ruff 基础错误检查，再以无窗口、无声音模式运行 pytest。自动检查不能替代对局与界面验收。规则或技能修改前阅读[编程逻辑规范](docs/二中杀编程逻辑规范.txt)。

## 打包 Windows 版本

```powershell
uv run --locked --group build pyinstaller scripts/erzhongsha.spec
```

输出为 `dist/二中杀/`，应分发整个目录。构建产物不提交到源码仓库，成品包通过 Releases 分发。发布前需核对素材范围并完成启动与对局检查。

## 素材与使用说明

公开仓库不包含个人照片、含照片的预览图和个人录音；缺失素材不应从私人版本补回。具体范围见[公开版素材说明](docs/素材与发布检查.md)。

项目尚未指定统一代码许可证，其余第三方卡图、界面与声音资源也未统一授予使用许可。公开访问不等于可以任意再分发。
