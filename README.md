# IP 群高光

把微信群里最能激活大家的内容，转化为作品样本、行动清单、社群记忆和长期知识资产。

> 这不是「AI 总结群聊」。我们不总结全部聊天，而是抓**反应峰值**——一个观点让所有人愣了一下、一个作品被刷屏、一场讨论吵出了新角度——把这些瞬间剪辑成型，沉淀成长期资产。详细产品定位见 [`product-brief.md`](./product-brief.md)。

核心工作流是**纯 Markdown 文件 + prompt 的本地流程**：没有数据库、不接飞书 API、不破解微信数据库。所有「编辑判断」都由你把 prompt 和素材一起发给 AI（Claude / ChatGPT 等）来完成。

素材采集这一端新增了一个**本地 Bot**（`src/wechat_capture_bot.py` 等）：通过 ADB 操作手机当前可见的微信界面，自动截图、滚动、OCR、规则初筛，产出「候选高光」交给 AI 做后续判断。采集 / OCR / 初筛这三步**不调用任何大模型**，详见下方「素材采集自动化」一节。

## 目录结构

```
inbox/            每周的原始聊天素材（输入，可手动粘贴，也可由采集 Bot 辅助）
prompts/          6 个 prompt，对应工作流的加工步骤
runs/             中间产物（采集 manifest、OCR 文本、候选事件、筛选结果、下周计划），按周存放
outputs/          三个最终发布版本（周刊 / 微信短版 / 飞书版）
knowledge/        长期知识资产，6 个库按周累积
portfolio/        作品集材料：demo.html 展示页 + case-study.md
product-brief.md  产品定位说明
references.md     设计参考的 9 个世界级案例
quality-bar.md    四档质量标准 + 终极标准

config/           采集 Bot 配置：群列表、采集参数、事件规则
src/              采集 Bot 源码（capture / OCR / 事件检测 / pipeline）
scripts/          Windows PowerShell 一键运行脚本
tools/            adb 等本地工具（adb.exe 放在 tools/platform-tools/ 下）
requirements.txt  OCR 步骤的 Python 依赖
```

## 每周工作流（7 步）

约定：`Wxx` 是 ISO 周数，比如 6 月中旬是 `2026-W24`。

### 第一步：填 inbox 素材

复制 `inbox/2026-Wxx-raw.md` 模板为本周文件（如 `inbox/2026-W24-raw.md`），把一周里看到的有价值群聊内容随手粘贴进去。每条素材记录：时间、发言人、原文、你觉得有价值的原因（可空）、是否匿名（可选）。

平时随手存，周末统一加工。重点留意三类内容：**群主观点**（引发认同或追问的判断）、**群友作品**（被分享并获得关注的产出）、**话题讨论**（引发多人接力的问题）。

> 可选自动化：如果跑过下方「素材采集自动化」的本地 Bot，会额外生成 `runs/2026-Wxx/candidate_events.md`——把这个文件和本周 inbox 一起交给 AI，作为第二步筛选的补充输入（Bot 已经按这三类做了初步标记，AI 不用从零开始翻聊天记录）。

### 第二步：用 prompts 筛选高光

把 `prompts/01-extract.md` + 本周 raw 文件一起发给 AI。
得到按 **A（必须进周刊）/ B（补充）/ C（只归档）** 分级的筛选结果。
保存到 `runs/2026-Wxx-01-extract.md`。

A 级每周 3-6 条足够，宁缺毋滥——这是整个工作流里最重要的一步。

### 第三步：生成完整周刊

把 `prompts/02-weekly-digest.md` + 筛选结果 + raw 原文一起发给 AI。
得到完整的《IP群精华周刊》，保存到 `outputs/2026-Wxx-weekly-digest.md`。

**人工通读一遍**：核对引用是否忠于原话、匿名是否处理对、Vol 编号填上。这一步是唯一不能省的人工把关。

### 第四步：生成微信群短版

把 `prompts/03-wechat-short.md` + 正式周刊发给 AI。
得到 600-900 字、可直接发群的版本，保存到 `outputs/2026-Wxx-wechat-short.md`，复制发到群里。

（如果还需要长期归档版，用 `prompts/04-feishu-version.md` 生成 `outputs/2026-Wxx-feishu.md`，整篇复制进飞书 / Typeless。）

### 第五步：沉淀 knowledge

把 `prompts/05-archive-knowledge.md` + 筛选结果（含 C 级）+ 正式周刊发给 AI。
得到 6 段可追加内容，分别粘贴到 `knowledge/` 下 6 个库文件的末尾：

| 库 | 收什么 |
|---|---|
| topics.md | 本周出现的讨论话题 |
| methods.md | 有步骤、可复用的方法 |
| member-questions.md | 成员的真实问题（含未解决的） |
| cases.md | 成员的实践案例与数据 |
| quotes.md | 值得引用的原话金句 |
| next-week-ideas.md | 没聊透的问题、潜在选题 |

单期周刊是事件，`knowledge/` 按周累积下来才是这个群真正的资产。

### 第六步：记录反馈

发完微信短版后，**观察而不是猜测**：

- 被 @ 的群友有没有回复？
- 「下周值得继续聊什么」里的问题有没有人接？
- 有没有人主动转发飞书版、或提到「这个能不能写进周刊」？

把这些观察简单记一笔（哪怕只是几行字），按 [`quality-bar.md`](./quality-bar.md) 的四档标准给本期打个分——这是下一期筛选口味的校准依据。

### 第七步：迭代下一期

把 `prompts/06-next-week-plan.md` + 本周周刊 + `knowledge/next-week-ideas.md` 发给 AI，得到下周运营计划（重点话题、3 个问题、1 个小作业、1 个讨论、观察重点），保存到 `runs/2026-Wxx-06-next-week-plan.md`。

结合第六步的反馈，调整下一期的筛选标准和栏目侧重——比如这期「成员高光」反响好，下期就多挖一些群友作品。

## 几个原则

- **筛选要狠**：A 级每周 3-6 条足够，周刊宁短勿水。
- **引用要真**：周刊里的关键观点必须能回到原始聊天记录，不许 AI 编。
- **匿名要严**：素材里标了匿名的，所有产出（周刊/短版/飞书/知识库）一律隐去真名。
- **沉淀比发布重要**：单周周刊是事件，knowledge/ 按周累积下来才是这个群真正的资产。

## 第一周怎么开始

1. 现在就建好本周文件：复制 `inbox/2026-Wxx-raw.md` 为 `inbox/2026-W24-raw.md`（按实际周数）。
2. 这周开始，看到群里有价值的讨论就随手粘进去，不用整理，先求有。
3. 周末花 1-2 小时跑完第二步到第七步。第一期 Vol.001 不用追求完美，发出去比完美重要。
4. 发完微信短版后观察群友反应，记录下来，作为下一期的校准依据。

## 素材采集自动化（wechat_capture_bot）

### 最快路径：手动截图 → 一键生成候选事件

不需要 ADB、不需要接手机，只要你能把截图文件复制到这里：

```
inbox/adb_captures/2026-W24/main/     ← 主群截图（按时间顺序，0001.png 0002.png …）
inbox/adb_captures/2026-W24/trigger/  ← 触发源群截图（可选）
```

然后运行：

```powershell
.\scripts\build_candidate_events.ps1 -Week 2026-W24
```

输出：`runs/2026-W24/candidate_events.md`（候选高光，交给 Claude/GPT 做精筛）。

> 如果没有安装 Tesseract OCR，第一次运行会生成 `runs/2026-W24/manual_ocr_template.md`，
> 在里面手动填写截图里的聊天文字，然后重新运行脚本即可。

---

第一版工作流里，「填 inbox」完全靠手动复制粘贴——这一步最累，也最容易让人放弃。`src/` 下的本地 Bot 把这一步自动化到「截图 + OCR + 规则初筛」，产出候选高光，但**判断哪些真正值得写进周刊，仍然交给人和 AI**。

### 为什么不用电脑微信记录

电脑版微信的聊天记录存在本地数据库文件里，格式是私有的、不公开的，而且随版本更新经常变化——基于它写的解析代码，下次微信升级很可能就失效，维护成本持续不断。更现实的问题是：很多人主力聊天设备是手机，电脑微信消息本来就不全。

### 为什么不破解微信数据库

直接读取（甚至解密）微信的本地数据库，意味着绕过应用本身的访问控制去拿数据——这和「我自己截图保存自己看到的内容」是两件性质不同的事。而且加密方式、密钥派生方式同样随版本变化，破解脚本极其脆弱，一次更新就可能全部报废，完全不符合「第一版 Workflow Bot」的定位。

### 为什么用手机可见界面采集

ADB 的 `screencap` 截取的是「手机屏幕上正在显示的画面」——本质上和你自己手动截图发给自己没有区别，只是把「截图 → 上滑 → 再截图」这个体力活交给程序循环执行。它不解析微信的内部数据结构，只要界面还是「聊天列表 + 上下滚动」，这套方法基本不受微信版本更新影响。

这也是为什么 Bot 设计成**人机配合**而不是全自动：打开手机、进入哪个群、滚动到哪个时间点开始采集，这些都需要人工操作一次；Bot 接手之后才开始自动截图、滚动、保存、断点续采。这不是能力不够，是有意为之——避免做成一个在你手机里"自己乱点"的全自主 Agent。

### 如何运行 Bot

前置准备（一次性）：

1. 按 [`tools/adb-setup.md`](./tools/adb-setup.md) 下载 Android Platform Tools，把 `adb.exe` 放进 `tools/platform-tools/`
2. 手机开启「开发者选项 -> USB 调试」，USB 连接电脑，授权调试
3. （OCR 需要）`pip install -r requirements.txt`，再安装 Tesseract-OCR 本体并勾选中文语言包，详见 `src/ocr_extract.py` 顶部说明
4. 按需调整 `config/wechat_groups.json`（群名、采集周数、日期范围）和 `config/event_rules.json`（关键词规则）

每周运行（任选其一）：

```powershell
# 一次性跑完 采集 -> OCR -> 规则检测
.\scripts\run_week_pipeline.ps1 -Week 2026-W24

# 或者分步跑
.\scripts\run_capture_week.ps1 -Week 2026-W24    # 采集截图（需要在手机上操作）
.\scripts\run_ocr_week.ps1 -Week 2026-W24        # 本地 OCR
.\scripts\run_detect_week.ps1 -Week 2026-W24     # 规则筛选候选事件

# 补采某一天
.\scripts\run_capture_week.ps1 -Week 2026-W24 -Backfill 2026-06-07
```

采集过程中，Bot 会在终端提示「请在手机上打开微信，进入「群名」，滚动到采集窗口最早的消息处，按 Enter 继续」——这是唯一需要你操作手机的步骤，之后 Bot 自动截图+滚动直到检测到底部（连续多张截图内容相同）或达到上限。中断后重新运行同一命令即可断点续采。

### 哪些步骤不消耗模型额度

采集、OCR、规则检测这三步**全部在本地完成，不调用任何大模型 API，0 模型额度**：

| 步骤 | 产出 | 说明 |
|---|---|---|
| `wechat_capture_bot.py` | `runs/2026-Wxx/capture_manifest.json`<br>`runs/2026-Wxx/capture_log.md` | 纯 ADB 截图+滑动 |
| `ocr_extract.py` | `runs/2026-Wxx/ocr_text.md` | 本地 Tesseract OCR |
| `event_detector.py` | `runs/2026-Wxx/candidate_events.md`<br>`runs/2026-Wxx/event_scores.json` | 纯关键词/规则匹配 |

### 哪一步才需要 GPT/Claude

从 `candidate_events.md` 产出之后——也就是上面 7 步工作流的**第二步及之后**——才需要 GPT/Claude：判断候选事件是否真的有价值、怎么拆解、怎么改写成周刊/短版/知识库、文字是否有编辑感和审美。

这就是核心原则：**模型额度花在「判断、拆解、成稿、审美」上，不花在「翻聊天记录、滚动截图、识别文字、初筛」这些体力活上**——这些体力活交给本地 Bot。

## 作品集材料

- [`portfolio/demo.html`](./portfolio/demo.html)：产品展示页，浏览器直接打开即可查看，支持打印导出 PDF。
- [`portfolio/case-study.md`](./portfolio/case-study.md)：完整的产品实践案例，包含问题发现、产品决策、AI 协作分工与验证方式。
- [`references.md`](./references.md)：这个项目向 9 个世界级内容产品学了什么。
- [`quality-bar.md`](./quality-bar.md)：四档质量标准与终极标准。

## 其他

- [`tools/adb-setup.md`](./tools/adb-setup.md)：Windows 安装 Android Platform Tools（adb）的最短步骤（与本项目工作流无关，仅作本地工具参考）。
