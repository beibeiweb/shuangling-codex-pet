# 霜铃 · 纯宠物增强版

完整解压后双击 Install.cmd，即可安装或更新。无需 Python、管理员权限或 API 密钥。
安装后在 Codex 中刷新宠物列表并重新选择霜铃；必要时重启 Codex。
包含 16 方向注视、抱臂眨眼，以及待机/工作/等待/成果待查看四组状态。
单格仍为 192×208，spriteVersionNumber 为 2；需要支持 v2 自定义宠物的客户端。

更新会校验包内文件哈希，保留首次安装前的备份；失败时恢复原文件。
双击 Uninstall.cmd 恢复首次安装前的宠物。用户额外添加的文件和备份历史保留。
安装记录：%LOCALAPPDATA%\ShuanglingCodexPet\PetOnly\pet-installation.json。
宠物目录：%CODEX_HOME%\pets\shuangling-white-dragon，未设置时用 %USERPROFILE%\.codex。
已有旧完整套装管理的宠物须先用旧套装的卸载程序解除管理。

本包仅安装宠物，不包含启动动画、语音或其他可选组件。
图像和角色素材不自动适用源码 MIT 许可，见 THIRD_PARTY_NOTICES.md。
源码：https://github.com/beibeiweb/shuangling-codex-pet
