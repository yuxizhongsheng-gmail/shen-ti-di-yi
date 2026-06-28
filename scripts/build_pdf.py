#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把《如实所现》书稿排成印刷级 PDF。设计取向：极简、留白、字体讲究——一页只为一件事。
正文 思源宋体；结构件 思源黑体；唯一的色，是一点朱砂。"""
import re, sys, html, pathlib
from weasyprint import HTML

SRC = pathlib.Path("book/书稿-如实所现.md")
EDITION  = "庄子版"
OUT_HTML = pathlib.Path("book/如实所现·庄子版.html")
OUT_PDF  = pathlib.Path("book/如实所现·庄子版.pdf")

# ---------- 解析书稿 ----------
raw = SRC.read_text(encoding="utf-8")
lines = raw.splitlines()
sections = []          # [(label, name, [paras])]
cur = None
for ln in lines:
    s = ln.rstrip()
    if s.startswith("# "):            # 书名行，跳过（封面另做）
        continue
    if s.startswith("> "):            # 副信息行，跳过
        continue
    if s.startswith("## "):
        title = s[3:].strip()
        if "　" in title:
            label, name = title.split("　", 1)
        else:
            label, name = title, ""
        cur = (label, name, [])
        sections.append(cur)
        continue
    if s.strip() == "---" or not s.strip():
        continue
    if cur is not None:
        cur[2].append(s.strip())

def inline(t):
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return t

# ---------- 组装正文 ----------
body_html = []
for label, name, paras in sections:
    is_chapter = label.startswith("第")
    # 章名打散加字距用 label 原样；前言/后记把两字拉开
    disp_label = label if is_chapter else "　".join(list(label))
    head = [f'<header class="opener">',
            f'  <div class="label">{html.escape(disp_label)}</div>']
    if name and is_chapter:        # 前言/后记只留二字标签，不重复书名
        head.append(f'  <h1 class="ctitle">{html.escape(name)}</h1>')
    head.append('  <div class="rule"></div>')
    head.append('</header>')
    ps = []
    for i, p in enumerate(paras):
        cls = ' class="first"' if i == 0 else ''
        ps.append(f'<p{cls}>{inline(p)}</p>')
    body_html.append(f'<section class="chapter">\n{chr(10).join(head)}\n{chr(10).join(ps)}\n</section>')

BODY = "\n".join(body_html)

# ---------- 模板 ----------
DOC = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
:root {{ --ink:#1C1A17; --paper:#FCFBF7; --gray:#A89F90; --rule:#D2CABA; --folio:#BFB7A8; --cinnabar:#9E2B25; }}

@page {{
  size: 140mm 210mm;
  margin: 22mm 19mm 20mm;
  background: var(--paper);
  @bottom-center {{
    content: counter(page);
    font-family: "Noto Sans CJK SC"; font-size: 8pt; color: var(--folio);
    letter-spacing: .12em; margin-top: 6mm;
  }}
}}
@page cover {{ margin: 0; background: var(--paper); @bottom-center {{ content: none; }} }}
@page plain {{ @bottom-center {{ content: none; }} }}

html {{ color: var(--ink); }}
body {{
  font-family: "Noto Serif CJK SC", serif;
  font-size: 10.5pt; line-height: 1.95; text-align: justify;
  text-justify: inter-ideograph; margin: 0;
}}

/* ---------- 封面 ---------- */
.cover {{ page: cover; height: 210mm; width:140mm; position: relative; }}
.cover .stack {{ position:absolute; left:0; right:0; top:64mm; text-align:center; }}
.cover .title {{
  font-family: "Noto Serif CJK SC"; font-weight: 700;
  font-size: 40pt; letter-spacing: .34em; text-indent:.34em; color: var(--ink);
}}
.cover .seal {{ width:4.2mm; height:4.2mm; background: var(--cinnabar); margin: 12mm auto 0; }}
.cover .hr {{ width: 17mm; border-top:.7pt solid var(--rule); margin: 11mm auto 0; }}
.cover .pinyin {{
  font-family:"Noto Sans CJK SC"; font-size: 8.5pt; letter-spacing:.42em; text-indent:.42em;
  color: var(--gray); margin-top: 8mm;
}}
.cover .edition {{
  font-family:"Noto Sans CJK SC"; font-weight:500; font-size: 9.5pt;
  letter-spacing:.5em; text-indent:.5em; color: var(--cinnabar); margin-top: 9mm;
}}
.cover .author {{
  position:absolute; left:0; right:0; bottom: 34mm; text-align:center;
  font-family:"Noto Sans CJK SC"; font-size: 11pt; letter-spacing:.45em; text-indent:.45em; color:#4A453E;
}}
.cover .imprint {{
  position:absolute; left:0; right:0; bottom: 20mm; text-align:center;
  font-family:"Noto Sans CJK SC"; font-size: 7.5pt; letter-spacing:.3em; text-indent:.3em; color:#C2BBAD;
}}

/* ---------- 题记 ---------- */
.epigraph {{ page: plain; break-before: page; height: 168mm; display:flex; align-items:center; justify-content:center; }}
.epigraph p {{ text-align:center; font-size: 12pt; line-height: 2.4; color:#4A453E; letter-spacing:.06em; max-width: 86mm; text-indent:0; }}

/* ---------- 章首 ---------- */
.chapter {{ break-before: page; }}
.opener {{ margin: 26mm 0 13mm; text-align:center; }}
.opener .label {{
  font-family:"Noto Sans CJK SC"; font-size: 9.5pt; font-weight:500;
  letter-spacing:.62em; text-indent:.62em; color: var(--gray);
}}
.opener .ctitle {{
  font-family:"Noto Serif CJK SC"; font-weight:700; font-size: 18.5pt;
  letter-spacing:.07em; color: var(--ink); margin: 7mm 0 0; line-height:1.45;
}}
.opener .rule {{ width: 15mm; border-top:.7pt solid var(--rule); margin: 8mm auto 0; }}

/* ---------- 正文 ---------- */
p {{ margin: 0; text-indent: 2em; orphans: 2; widows: 2; }}
p.first {{ text-indent: 0; }}
strong {{ font-weight: 700; }}

/* ---------- 版权尾页 ---------- */
.colophon {{ page: plain; break-before: page; height: 168mm; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; color:#7C766B; }}
.colophon .big {{ font-family:"Noto Serif CJK SC"; font-size: 13pt; letter-spacing:.34em; text-indent:.34em; color:#3A352F; }}
.colophon .line {{ font-family:"Noto Sans CJK SC"; font-size: 8pt; letter-spacing:.18em; line-height:2.2; margin-top:7mm; }}
.colophon .seal {{ width:3.4mm;height:3.4mm; background:var(--cinnabar); margin-top:11mm; }}
</style></head>
<body>

<div class="cover">
  <div class="stack">
    <div class="title">如实所现</div>
    <div class="seal"></div>
    <div class="hr"></div>
    <div class="pinyin">RÚ SHÍ SUǑ XIÀN</div>
    <div class="edition">{EDITION}</div>
  </div>
  <div class="author">树林　著</div>
  <div class="imprint">据树林社群语料 · 文学化定稿</div>
</div>

<div class="epigraph"><p>擦掉那层霜，<br>让事物，如它本来的样子，<br>显现出来。</p></div>

{BODY}

<div class="colophon">
  <div class="big">如实所现　·　庄子版</div>
  <div class="line">
    树林　著<br>
    据其社群八十万字语料，整理、改写、文学化<br>
    庄子版 —— 以庄子的境界、王小波的笔、纳瓦尔的骨架，重写树林<br>
    前言　九章　后记
  </div>
  <div class="seal"></div>
</div>

</body></html>"""

OUT_HTML.write_text(DOC, encoding="utf-8")
HTML(string=DOC, base_url=str(pathlib.Path('.').resolve())).write_pdf(str(OUT_PDF))
print("章节数:", len(sections))
print("已生成:", OUT_HTML, "和", OUT_PDF, f"({OUT_PDF.stat().st_size//1024} KB)")
