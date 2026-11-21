# 二中杀 · 桌面单机版

这是从 2026-07-27 历史提交恢复的 **Pygame 桌面单机版**，不是网页联机版。
公开版保留游戏规则、DIY技能、AI和桌面界面，移除了私人肖像、包含肖像的预览图和个人录音。
DIY武将使用文字牌面，缺少的专属语音静默跳过；无需额外下载私人素材。
项目元数据版本 `0.1.0` 表示本次独立维护起点，不代表曾发布的安装包版本。

## 运行（Windows）

已安装 uv 后，在 PowerShell 执行：

```powershell
git clone https://github.com/Wenxin666-code/erzhongsha-desktop.git
cd erzhongsha-desktop
uv sync --locked --managed-python
uv run --locked python main.py
```

首次同步会下载 Python 和依赖，需要联网；之后游戏运行不需要 Docker、服务器或 GitHub 登录。
游戏会打开桌面窗口，**没有网页入口**。不需要先 `conda activate`，也不需要手动激活 `.venv`。
如果刚安装 uv 后命令找不到，重开终端；安装方式见 [uv 官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)。

请用 VS Code 打开整个项目目录，并选择 `.venv\Scripts\python.exe`。共享编辑器配置面向 Windows。
Python 版本固定为 3.11.15，与迁移前环境一致；本地环境位于 `.venv`，不提交到 Git。
`uv.lock` 则必须提交，其他机器据此安装相同版本的依赖。

## 目录职责

```text
main.py                  原桌面入口和 UI，暂不做大规模拆分
src/                     引擎、模型、技能与 AI
data/                    牌堆和武将数据（必须保留）
images/、sound/           公开版使用的运行素材；不含私人照片和录音
tests/                   原有回归测试
docs/                    编程规范、技能需求、AI 策略及迁移记录
docs/history/            原 Conda 配置、导出说明，仅供追溯
scripts/                 无窗口检查脚本、打包配置
.github/workflows/       提交/合并请求的自动检查配置
pyproject.toml           运行依赖、开发依赖和工具配置
uv.lock                  完整依赖锁定结果，由 uv 生成
```

原始 `assets/` 素材库、旧安装包、示例文件和 Python 缓存没有复制进来，但仍在历史归档中保留。
不要把 `data/` 当成训练数据排除：这里装的是游戏必需规则。

## 检查和开发

```powershell
uv run --locked python scripts/check.py
# 只验证一个子系统：
uv run --locked python scripts/check.py tests/test_weapon_effects.py
```

检查脚本先运行 Ruff，再用无窗口、无声音模式运行 pytest。退出码非零表示失败。
当前 Ruff 仅启用基础致命错误检查，不代表全部代码已符合现代风格；暂不批量格式化历史代码。
测试结果不能代替真实对局的视频、动画和操作验收。

添加新依赖使用 `uv add 包名`，开发工具使用 `uv add --dev 包名`；提交时同时带上配置与锁文件。
不要在 Conda 中装一遍、在项目 `.venv` 中再手动维护另一套。旧配置只作历史记录。
Python 或依赖升级应单独提交并跑完整回归，不和技能改动混在一起。

## 打包（可选）

从项目根目录运行：

```powershell
uv run --locked --group build pyinstaller scripts/erzhongsha.spec
```

输出位于 `dist/二中杀/`，需要分发整个目录，不能只拷贝其中的 exe。
打包工具不属于游戏运行所需依赖，按需安装；每次发布前还需实际启动和对局验收。
不要把 dist/build 提交进代码仓库；确认授权后可把发布包作为 GitHub Release 附件。

## GitHub 与素材边界

公开版本从清理后的快照建立独立历史，不包含原私有仓库的旧提交、旧包或个人素材。
请勿重新提交个人肖像、录音或含这些内容的截图；相关目录已加入忽略规则。
代码和其余第三方素材未统一授予开源许可；公开可见不代表可任意再分发。
详情见 [素材与发布检查](docs/素材与发布检查.md)。

开发前阅读 [编程逻辑规范](docs/二中杀编程逻辑规范.txt)。
来源和验证范围见 [迁移记录](docs/迁移记录.md)。
