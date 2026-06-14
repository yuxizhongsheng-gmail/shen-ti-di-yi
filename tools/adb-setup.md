# Windows 安装 Android Platform Tools（adb）最短步骤

## 检测结果

当前云端容器（Linux）未安装 adb。Windows 本机请按下方步骤检测和安装。

## 本项目（wechat_capture_bot）的推荐放置位置

`src/wechat_capture_bot.py` 默认从项目内的 `tools/platform-tools/adb.exe` 读取 adb。
解压后把整个 `platform-tools` 文件夹的内容放进项目的 `tools/platform-tools/` 目录
（即让 `tools/platform-tools/adb.exe` 存在），不需要额外配置 PATH，Bot 会自动找到它。

如果你已经在系统 PATH 里装过 adb，也可以不放进项目目录——Bot 会按
`config/wechat_groups.json` 里的 `device.adb_path` -> `tools/platform-tools/` -> 系统 PATH 的顺序查找。

## 安装步骤（最短路径）

1. **下载官方压缩包**
   访问 https://developer.android.com/tools/releases/platform-tools ，下载 "SDK Platform-Tools for Windows"
   （直链：`https://dl.google.com/android/repo/platform-tools-latest-windows.zip`）

2. **解压**
   - 给本项目用：解压后把里面的文件（含 `adb.exe`）复制到本项目的 `tools/platform-tools/` 目录
   - 或给全局用：解压到例如 `C:\platform-tools`

3. **（全局安装时）加入 PATH**
   - 按 `Win` 键搜索「编辑系统环境变量」→「环境变量」
   - 在「用户变量」的 `Path` 中新增一行：`C:\platform-tools`
   - 重新打开命令行使其生效

4. **验证安装**
   打开 PowerShell 或 CMD，运行：
   ```
   adb version
   ```
   显示版本号即安装成功。

   如果是放进项目目录、未加入 PATH，需先 `cd tools\platform-tools` 再运行 `.\adb version`。

5. **连接手机验证**
   - 手机：设置 → 关于手机 → 连续点击「版本号」7 次开启开发者模式 → 开发者选项中打开「USB 调试」
   - 用数据线连接电脑，手机上确认「允许 USB 调试」
   - 运行：
     ```
     adb devices
     ```
     列表中出现设备序列号即连接成功。
