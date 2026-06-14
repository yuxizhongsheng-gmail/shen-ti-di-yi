# Windows 安装 Android Platform Tools（adb）最短步骤

> 与「IP 群高光」项目本身无关，仅作为本地工具链参考记录在这里。

## 检测结果

当前云端容器（Linux）未安装 adb。Windows 本机请按下方步骤检测和安装。

## 安装步骤（最短路径）

1. **下载官方压缩包**
   访问 https://developer.android.com/tools/releases/platform-tools ，下载 "SDK Platform-Tools for Windows"
   （直链：`https://dl.google.com/android/repo/platform-tools-latest-windows.zip`）

2. **解压到固定目录**
   解压到例如 `C:\platform-tools`（解压后该目录下应能看到 `adb.exe`）

3. **加入 PATH（可选但推荐）**
   - 按 `Win` 键搜索「编辑系统环境变量」→「环境变量」
   - 在「用户变量」的 `Path` 中新增一行：`C:\platform-tools`
   - 重新打开命令行使其生效

4. **验证安装**
   打开 PowerShell 或 CMD，运行：
   ```
   adb version
   ```
   显示版本号即安装成功。

   如果跳过第 3 步，需先 `cd C:\platform-tools` 再运行 `.\adb version`。

5. **连接手机验证**
   - 手机：设置 → 关于手机 → 连续点击「版本号」7 次开启开发者模式 → 开发者选项中打开「USB 调试」
   - 用数据线连接电脑，手机上确认「允许 USB 调试」
   - 运行：
     ```
     adb devices
     ```
     列表中出现设备序列号即连接成功。
