# IP 群高光

把微信群里最能激活大家的内容，转化为作品样本、行动清单、社群记忆和长期知识资产。

> 这不是「AI 总结群聊」。我们不总结全部聊天，而是抓**反应峰值**——一个观点让所有人愣了一下、一个作品被刷屏、一场讨论吵出了新角度——把这些瞬间剪辑成型，沉淀成长期资产。详细产品定位见 [`product-brief.md`](./product-brief.md)。

第一版是最小可运行版本：**纯 Markdown 文件 + prompt 的本地工作流**。没有前端、没有数据库、不爬微信、不接 OCR、不接飞书 API。所有「自动化」都由你把 prompt 和素材一起发给 AI（Claude / ChatGPT 等）来完成。

## 目录结构

```
inbox/            每周的原始聊天素材（输入）
prompts/          6 个 prompt，对应工作流的加工步骤
runs/             中间产物（筛选结果、下周计划），按周存放
outputs/          三个最终发布版本（周刊 / 微信短版 / 飞书版）
knowledge/        长期知识资产，6 个库按周累积
portfolio/        作品集材料：demo.html 展示页 + case-study.md
product-brief.md  产品定位说明
references.md     设计参考的 9 个世界级案例
quality-bar.md    四档质量标准 + 终极标准
```

## 每周工作流（7 步）

约定：`Wxx` 是 ISO 周数，比如 6 月中旬是 `2026-W24`。

### 第一步：填 inbox 素材

复制 `inbox/2026-Wxx-raw.md` 模板为本周文件（如 `inbox/2026-W24-raw.md`），把一周里看到的有价值群聊内容随手粘贴进去。每条素材记录：时间、发言人、原文、你觉得有价值的原因（可空）、是否匿名（可选）。

平时随手存，周末统一加工。重点留意三类内容：**群主观点**（引发认同或追问的判断）、**群友作品**（被分享并获得关注的产出）、**话题讨论**（引发多人接力的问题）。

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

## 作品集材料

- [`portfolio/demo.html`](./portfolio/demo.html)：产品展示页，浏览器直接打开即可查看，支持打印导出 PDF。
- [`portfolio/case-study.md`](./portfolio/case-study.md)：完整的产品实践案例，包含问题发现、产品决策、AI 协作分工与验证方式。
- [`references.md`](./references.md)：这个项目向 9 个世界级内容产品学了什么。
- [`quality-bar.md`](./quality-bar.md)：四档质量标准与终极标准。

## 其他

- [`tools/adb-setup.md`](./tools/adb-setup.md)：Windows 安装 Android Platform Tools（adb）的最短步骤（与本项目工作流无关，仅作本地工具参考）。
