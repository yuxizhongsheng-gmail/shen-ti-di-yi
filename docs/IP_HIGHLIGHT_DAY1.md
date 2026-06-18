# IP 群高光 · Day 1 Bot 使用说明

## 这个 Bot 能做什么

它能自动帮你从手机微信群截图中，找出本周最值得写进周刊的高光事件。

具体来说，它会：
1. 自动控制手机截图（你只需要先打开微信群）
2. 自动滚动，连续截 80 张左右
3. 用 OCR 识别截图中的文字
4. 给每张截图打「热度分」
5. 找出高热度的截图区间
6. 生成候选事件初稿

整个过程不联网、不调用 AI、不破解微信，纯本地完成。

## 运行前：手机准备

1. **USB 连接**：用数据线把手机连到电脑
2. **开启 USB 调试**：
   - 手机「设置」→「关于手机」→ 连点版本号 7 次 → 开启开发者模式
   - 「设置」→「开发者选项」→ 打开「USB 调试」
   - 手机弹出「允许此电脑调试」→ 点允许
3. **打开微信群**：
   - 打开微信 → 进入「25IP训练营交流群」
   - 滚动到本周聊天记录的**起始位置**（比如周一早上的消息附近）
   - 停在这里，不要动

## 怎么运行

打开 Windows 命令行（cmd 或 PowerShell），进入项目目录：

```
cd C:\Users\mings\Documents\ip群周精华总结
```

然后运行：

```
run_ip_highlight_day1.cmd 2026-W25
```

把 `2026-W25` 换成你要采集的周次。

Bot 会提示你按 Enter 开始，然后自动截图。期间不要碰手机。

## 运行过程中你会看到什么

```
步骤 1/5: 检查 ADB 连接
  ✅ 设备已连接: xxxxx
  ✅ 屏幕分辨率: 1080x2340

步骤 2/5: 截图采集
  📷 001.png  (1/80)
  📷 002.png  (2/80)
  ...
  ✅ 截图采集完成: 80 张

步骤 3/5: OCR 文字识别
  ✅ 001.png: 342 字符
  ✅ 002.png: 287 字符
  ...

步骤 4/5: 截图热度评分
  ✅ screenshot_heat_scores.json

步骤 5/5: 构建候选事件
  ✅ candidate_events.md
```

## 输出文件在哪里

全部在 `runs/2026-W25/` 目录下（W25 换成你的周次）：

| 文件 | 是什么 | 你需要看吗 |
|------|--------|-----------|
| `screenshots/` | 手机截图原图 | 需要，对照确认 |
| `capture_manifest.json` | 截图清单 | 一般不用看 |
| `ocr_text.md` | OCR 识别出的文字 | 建议看，确认识别质量 |
| `ocr_health_report.md` | OCR 质量报告 | 如果候选事件少，看这个排查 |
| `screenshot_heat_scores.json` | 每张截图的热度分 | 一般不用看 |
| `review_queue.md` | **高热截图排行榜** | **必看**，告诉你哪些截图最值得关注 |
| `candidate_events.md` | **候选事件初稿** | **必看**，这是主要产出 |
| `manual_candidate_events.md` | 人工补充模板 | 如果自动检测不够，在这里手工补 |

## 什么算成功

- `screenshots/` 里有 40 张以上截图
- `ocr_text.md` 里大部分截图都识别出了中文
- `review_queue.md` 列出了至少 2-3 个热点区间
- `candidate_events.md` 有至少 1 条候选事件

即使 candidate_events.md 只有少量候选，也算成功——你可以：
1. 对照 `review_queue.md` 手工挑选
2. 编辑 `manual_candidate_events.md` 补充
3. 然后把候选事件交给 Claude/DeepSeek 写周刊

## 如果失败怎么排查

### 「ADB 未找到」

- 下载 Android Platform Tools
- 把 `adb.exe` 放到项目的 `tools/platform-tools/` 目录下
- 或者把 adb 加入系统 PATH

### 「没有检测到设备」

- 检查 USB 线是否连好（试换一根）
- 检查手机是否弹出了「允许调试」→ 要点允许
- 在命令行跑 `adb devices` 看是否有设备

### 「OCR 识别出的字很少或全是乱码」

- 需要安装 Tesseract OCR：https://github.com/UB-Mannheim/tesseract/wiki
- 安装时勾选 `Chinese Simplified`（chi_sim）语言包
- 安装完后在命令行跑 `tesseract --version` 确认
- 还需要：`pip install pytesseract Pillow`

### 「候选事件为 0」

- 打开 `ocr_health_report.md`，看看 OCR 质量
- 打开 `review_queue.md`，看看有没有高热截图
- 可能是截图没截到有价值的讨论——试着从群聊中间重新截
- 编辑 `manual_candidate_events.md` 手工补充

### 「截图全是重复的」

- 可能微信已经到底了，或者滑动参数不对
- 试试手动在手机上滚动确认还有更多内容
- 可以调整 `config/ip_highlight.yaml` 里的 swipe 参数

## 哪一步需要人工介入

| 步骤 | 自动/手动 | 说明 |
|------|-----------|------|
| 打开微信群并定位 | 手动 | Bot 不会自动点日期或找群 |
| 截图和滚动 | 自动 | 按 Enter 后不用管 |
| OCR | 自动 | 需要 Tesseract 已安装 |
| 热度评分 | 自动 | |
| 候选事件初稿 | 自动 | |
| **审阅候选事件** | **手动** | 看 review_queue.md 和 candidate_events.md |
| **补充遗漏事件** | **手动** | 编辑 manual_candidate_events.md |
| 生成最终周刊 | 手动调用 | 把候选事件交给 Claude/DeepSeek |

## 进阶：单步运行

如果只想跑某一步（比如重新跑 OCR 或评分）：

```
python -m src.ip_highlight_cli doctor  --week 2026-W25
python -m src.ip_highlight_cli capture --week 2026-W25
python -m src.ip_highlight_cli ocr     --week 2026-W25
python -m src.ip_highlight_cli score   --week 2026-W25
python -m src.ip_highlight_cli build-events --week 2026-W25
```

## 进阶：自定义配置

复制 `config/ip_highlight.yaml.example` 为 `config/ip_highlight.yaml`，可以调整：
- 截图数量（默认 80）
- 滑动速度和间隔
- 高光关键词（可以加你群里常出现的词）
- 评分阈值
