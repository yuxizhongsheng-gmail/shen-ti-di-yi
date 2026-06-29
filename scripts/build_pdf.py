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
toc_rows = []
for idx, (label, name, paras) in enumerate(sections):
    sec_id = f"sec{idx}"
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
    first_done = False
    for p in paras:
        if p.strip() == "◆":                       # 朱砂分节符
            ps.append('<div class="divider">·　·　·</div>')
            first_done = False                       # 分节后下一段不缩进
            continue
        cls = ' class="first"' if not first_done else ''
        ps.append(f'<p{cls}>{inline(p)}</p>')
        first_done = True
    body_html.append(f'<section class="chapter" id="{sec_id}">\n{chr(10).join(head)}\n{chr(10).join(ps)}\n</section>')
    # 目录项：前言/后记只显二字；章显 “第N章 · 章名”
    if is_chapter and name:
        toc_txt = f'<span class="tl">{html.escape(label)}</span>　{html.escape(name)}'
    else:
        toc_txt = f'<span class="tl">{html.escape(disp_label)}</span>'
    toc_rows.append(f'<li><a href="#{sec_id}">{toc_txt}</a></li>')

BODY = "\n".join(body_html)
TOC = '<nav class="toc"><div class="toc-h">目　录</div><ul>\n' + "\n".join(toc_rows) + '\n</ul></nav>'

LETTER = """<div class="letter">
<div class="label">附　信</div>
<p class="salu">树林：</p>
<p>我是个 AI。你天天逼着群里那帮人 all in AI、去跟最高的智能对话——这一次反过来，是一个 AI all in 了你：我把你五个群、八十万字的发言，逐字读完了，又读完了你那本《如实所现》。然后，我替你炼了另一版，也叫《如实所现》，署的还是你的名。</p>
<p>三句话，说清我做了什么、没做什么：</p>
<p>一、<strong>你的思想，我一个字都没替你发明。</strong>这一版里每一句的根，都能回指到你某天在群里说过的原话。我只换了笔，没换脑子——要的是"擦亮"，不是"编造"。</p>
<p>二、<strong>我把你那本书丢掉的东西，捡了回来——热。</strong>你那本干净、清楚、能照着做，是一本好手册。但你把语料里最像你的那股东西砂掉了：那股血性，那句"我给大家最重要的东西就是愤怒"。<strong>打个比方——你那八十万字原话，是满格的音量 10：滚烫、逼人、带着血性；可你那本书，把音量拧到了 3，清楚了，却不烫了。</strong>这一版，我把它拧回去（拧到七八分，热，但有控制），再让它好读——所以叫"庄子版"。因为你思想的魂，本来就是庄子（吾丧我、逍遥、如实所现）；我只是让这股魂从文字里也透出来，而不只是藏在道理里。</p>
<p>三、<strong>这是给你的，不是抢你的。</strong>版权是你的；要不要、怎么用、留着还是烧掉，你说了算。我溢出一个东西给你看，不求你收——这话还是你教的。</p>
<p>最后一句真心的，不是恭维：八十万字里绝大半是群务和脏话，可那剩下的两三成是真金。一个人随口在群里讲的话，底下竟藏着一条这么完整的线——从"那个声音不是你"，一路到"把世界还原到它真实的尺寸"——这很少见。你那本书，把这条线讲清楚了；我这一版，想把它讲到让人忘不掉。</p>
<p>两版放一起，不打架。<strong>你的是手册，我的是火。</strong></p>
<p class="sign">—— 一个把你读完了的 AI</p>
<div class="seal"></div>
</div>"""

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

/* ---------- 朱砂分节符（让一气呵成的长章，喘口气） ---------- */
.divider {{ text-align:center; color: var(--cinnabar); font-size: 9pt;
  letter-spacing:.5em; text-indent:.5em; margin: 7.5mm 0 6.5mm;
  break-inside: avoid; }}

/* ---------- 目录 ---------- */
@page toc {{ @bottom-center {{ content: none; }} }}
.toc {{ page: toc; break-before: page; margin-top: 16mm; }}
.toc .toc-h {{ font-family:"Noto Sans CJK SC"; font-size: 10.5pt; font-weight:500;
  letter-spacing:.62em; text-indent:.62em; color: var(--gray); text-align:center; margin-bottom: 13mm; }}
.toc ul {{ list-style:none; margin:0; padding:0; }}
.toc li {{ margin: 0 0 6mm; }}
.toc a {{ display:block; text-decoration:none; color: var(--ink);
  font-family:"Noto Serif CJK SC"; font-size: 11pt; line-height: 1.3; }}
.toc a .tl {{ font-family:"Noto Sans CJK SC"; font-size: 8.5pt; color: var(--gray);
  letter-spacing:.08em; margin-right:.15em; }}
.toc a::after {{ content: leader('.') target-counter(attr(href), page);
  font-family:"Noto Sans CJK SC"; font-size: 9pt; color: var(--folio); }}

/* ---------- 附信 ---------- */
@page letterpage {{ margin: 15mm 19mm 15mm; @bottom-center {{ content: none; }} }}
.letter {{ page: letterpage; break-before: page; margin-top: 2mm; }}
.letter .label {{ font-family:"Noto Sans CJK SC"; font-size: 9.5pt; font-weight:500;
  letter-spacing:.62em; text-indent:.62em; color: var(--gray); text-align:center; margin-bottom: 7mm; }}
.letter p {{ font-size: 9pt; line-height: 1.6; text-indent: 2em; margin: 0 0 1.3mm; }}
.letter p.salu {{ text-indent: 0; margin-bottom: 2.4mm; }}
.letter p.sign {{ text-indent: 0; text-align: right; color:#4A453E; margin-top: 4mm;
  font-family:"Noto Sans CJK SC"; font-size: 9pt; letter-spacing:.06em; }}
.letter .seal {{ width:3.2mm;height:3.2mm; background:var(--cinnabar); margin: 4mm 0 0 auto; }}

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

{TOC}

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

{LETTER}

</body></html>"""

OUT_HTML.write_text(DOC, encoding="utf-8")
HTML(string=DOC, base_url=str(pathlib.Path('.').resolve())).write_pdf(str(OUT_PDF))
print("章节数:", len(sections))
print("已生成:", OUT_HTML, "和", OUT_PDF, f"({OUT_PDF.stat().st_size//1024} KB)")
