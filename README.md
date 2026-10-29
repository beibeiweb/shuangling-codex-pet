# 霜铃 · Codex 宠物套装

白发紫瞳的小龙娘霜铃：桌面宠物、四句随机完成语音，以及打开 Codex 前播放的龙娘启动动画。

![霜铃](launcher/media/shuangling-icon.png)

本项目是社区定制工具，与 OpenAI 无官方关联。仅支持 **Windows x64**，需要已经安装支持自定义宠物的 Codex 桌面版、Windows 媒体组件以及 **Python 3.11 或更新版本**。安装和播放不需要 API 密钥、不调用生图或语音服务。

## 下载与安装

1. 在 [Releases](https://github.com/beibeiweb/shuangling-codex-pet/releases/latest) 下载 `shuangling-codex-pet-windows-v1.0.0.zip`，或点击仓库的 **Code → Download ZIP**。
2. 将 ZIP **完整解压**到普通文件夹。不要直接在压缩包里运行。
3. 如果没有 Python，先从 [Python 官网](https://www.python.org/downloads/windows/) 安装 Python 3.11+，勾选加入 PATH，保留 Python Launcher 和 pythonw。
4. 双击 `Install.cmd`。以当前用户安装，无需管理员权限。终端显示 `Installed` 才表示安装成功。
5. 完全退出并重新打开 Codex，在宠物选择界面选择 **霜铃**。安装程序不会自动关闭正在工作的 Codex。
6. 使用桌面或开始菜单中的 **Shuangling - Codex** 快捷方式播放启动动画。要放到任务栏，请手动将该快捷方式固定到任务栏。

安装程序不会替换原有 Codex 快捷方式。点击原始 Codex 图标或已运行窗口的任务栏图标时，不会经过启动动画。不同 Codex 版本的宠物入口和通知行为可能变化。

## 包含的效果

- 8 × 9 透明宠物图集，单格 192 × 208，支持待机、跑动、等待、失败、审阅等动作。
- 完成动作使用抱臂姿势，沿用客户端原有动作时长，**不是持续 20 秒**。
- 每次收到 `agent-turn-complete` 通知随机播放一句，避免连续重复；相同线程/轮次通知去重，多条通知依次排队。
- 启动器播放约 14 秒视频，然后尝试激活 Codex。随附窗口检测、激活重试和超时处理。

四句语音：

1. 主人，工作已经完成啦！快来看看吧！
2. 完成啦～霜铃是不是很能干？
3. 叮！任务搞定，主人请验收！
4. 主人，成果准备好啦，等你来看看哦！

## 安装位置与恢复

| 内容 | 位置 |
| --- | --- |
| 播放器、启动动画、语音 | `%LOCALAPPDATA%\ShuanglingCodexPet` |
| 宠物文件 | `%CODEX_HOME%\pets\shuangling-white-dragon`，未设置时使用 `%USERPROFILE%\.codex` |
| 通知钩子 | 同一 Codex 目录的 `config.toml` 顶层 `notify` |
| 本地备份记录 | `%LOCALAPPDATA%\ShuanglingCodexPet\installation.json` |

安装时保留已有通知命令，并在通知到达时转发；原有同名宠物和快捷方式文件也会备份。配置中的其他字段保持不变。重复安装会停止，请先卸载旧套装。若此前手动配置过另一套霜铃播音，请先解除旧播音钩子，以免转发时重复播放。

双击解压目录中的 `Uninstall.cmd` 可恢复安装前的通知命令、同名宠物及快捷方式。安装后如果手工修改过受管理文件或 `notify`，卸载会停止并提示，避免覆盖你的修改。运行日志与新增文件保留。不要将本地安装目录或备份记录重新上传到 GitHub。

## 试听与排查

安装后可在命令提示符中运行：

```bat
py -3 "%LOCALAPPDATA%\ShuanglingCodexPet\voice\notify.py" --preview
```

语音日志位于 `%LOCALAPPDATA%\ShuanglingCodexPet\voice\playback.log`，只记录事件与音频文件名，不记录聊天内容。若试听有声音但任务完成没有声音，先重启 Codex，再检查日志是否有 `completion-played`；客户端必须实际支持并调用 `notify`。原生通知提示音不由本套装关闭。

启动日志位于安装目录的 `launcher\logs\launcher.log`。启动器默认激活应用标识 `OpenAI.Codex_2p2nqsd0c76g0!App`；不同安装渠道如不使用该标识，需要修改 `launcher\launcher.json`。无法播放视频时，请检查 Windows 媒体组件。软件未签名，Windows 可能显示来源提示；可查看源码后自行构建。

## 源码、构建和验证

- `pet/`：已安装版本的宠物图集和描述。
- `voice/`：Python 标准库语音通知器和四段 WAV；未包含参考音频。
- `launcher/`：预编译 Windows 启动器、配置、视频和图标。
- `upstream/dragon-codex-boot/`：基于原项目修改的 Windows 启动器源码、构建脚本和测试。
- `scripts/install.py`：按用户安装、备份、配置校验及卸载逻辑。

在仓库根目录运行：

```powershell
py -3 -m unittest discover -s tests -v
py -3 voice/notify.py --self-test
powershell -NoProfile -ExecutionPolicy Bypass -File upstream/dragon-codex-boot/scripts/build.ps1 -IconPath launcher/media/shuangling.ico
powershell -NoProfile -ExecutionPolicy Bypass -File upstream/dragon-codex-boot/scripts/test.ps1
```

构建需要 Windows 的 .NET Framework x64 编译器；输出位于 `upstream/dragon-codex-boot/build/DragonCodexBoot`。替换 `launcher/DragonCodexBoot.exe` 即可使用重新编译的程序。

本发布已验证隔离安装/卸载、配置保留、随机语音与音频格式，以及启动器测试。维护者电脑已记录实际任务完成播音。尚未在全新电脑完整验证冷启动和全部 Codex 版本。

## 来源与许可

启动器基于 [dragon-codex-boot](https://github.com/yushua0808-cpu/dragon-codex-boot)，保留上游 MIT 许可及媒体说明。软件源码采用 MIT；视频、角色图、宠物图集及语音不自动适用源码许可，详见 [素材与第三方说明](THIRD_PARTY_NOTICES.md)。
