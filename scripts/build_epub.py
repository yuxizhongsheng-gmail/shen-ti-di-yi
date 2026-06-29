#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把《如实所现》书稿打成结构正确的 EPUB3。
每章：章序号是 <p class="label">，章名是独立的 <h2>，正文是独立的 <p>——
阅读器再也无法把标题和第一句正文揉成一行（修掉用户看到的"重复"）。"""
import re, html, zipfile, pathlib

SRC      = pathlib.Path("book/书稿-如实所现.md")
COVER    = pathlib.Path("book/封面-如实所现·庄子版.png")
OUT_EPUB = pathlib.Path("book/如实所现·庄子版.epub")
EDITION  = "庄子版"
TITLE    = "如实所现"
AUTHOR   = "树林"
BOOK_ID  = "urn:uuid:rushisuoxian-zhuangzi-2026"

# ---------- 解析书稿（与 build_pdf.py 同一套规则） ----------
lines = SRC.read_text(encoding="utf-8").splitlines()
sections = []          # [(label, name, [paras])]
cur = None
for ln in lines:
    s = ln.rstrip()
    if s.startswith("# ") or s.startswith("> "):
        continue
    if s.startswith("## "):
        title = s[3:].strip()
        label, name = (title.split("　", 1) + [""])[:2] if "　" in title else (title, "")
        cur = (label, name, [])
        sections.append(cur)
        continue
    if s.strip() == "---" or not s.strip():
        continue
    if cur is not None:
        cur[2].append(s.strip())

def inline(t):
    t = html.escape(t)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)

# ---------- 样式 ----------
CSS = """@charset "utf-8";
html { color:#1C1A17; }
body { font-family:"Noto Serif CJK SC","Source Han Serif SC",serif;
  line-height:1.9; text-align:justify; margin:0; padding:1.2em 1.1em 2.4em; }
.label { font-family:"Noto Sans CJK SC",sans-serif; font-size:.78em; font-weight:500;
  letter-spacing:.5em; color:#A89F90; text-align:center; margin:2.2em 0 0; }
h2.ctitle { font-weight:700; font-size:1.5em; letter-spacing:.06em; color:#1C1A17;
  text-align:center; margin:.7em 0 0; line-height:1.45; }
hr.rule { width:14%; border:0; border-top:.6pt solid #D2CABA; margin:1.5em auto 2em; }
p { margin:0; text-indent:2em; }
p.first { text-indent:0; }
p.div { text-align:center; color:#9E2B25; font-size:.86em; letter-spacing:.5em;
  text-indent:.5em; margin:1.7em 0 1.5em; }
strong { font-weight:700; }
.epi { min-height:70vh; display:flex; align-items:center; justify-content:center; }
.epi p { text-align:center; font-size:1.12em; line-height:2.3; color:#4A453E;
  text-indent:0; max-width:18em; }
.coverwrap { margin:0; padding:0; text-align:center; }
.coverwrap img { max-width:100%; height:auto; }
.colo { text-align:center; color:#7C766B; margin-top:3em; }
.colo .big { font-family:"Noto Serif CJK SC",serif; font-size:1.2em; letter-spacing:.2em; color:#3A352F; }
.colo .line { font-family:"Noto Sans CJK SC",sans-serif; font-size:.8em; line-height:2.1; margin-top:1.4em; }
.letter p { line-height:1.9; margin:0 0 .55em; }
.letter p.salu { text-indent:0; margin-bottom:.9em; }
.letter p.sign { text-indent:0; text-align:right; color:#4A453E; margin-top:1.6em;
  font-family:"Noto Sans CJK SC",sans-serif; font-size:.92em; }
.letter .seal { width:.9em; height:.9em; background:#9E2B25; margin:1.4em 0 0 auto; }
"""

def xhtml(title, body, cls=""):
    b = f' class="{cls}"' if cls else ""
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN" lang="zh-CN">\n'
            f'<head><meta charset="utf-8"/><title>{html.escape(title)}</title>'
            '<link rel="stylesheet" type="text/css" href="styles.css"/></head>\n'
            f'<body{b}>\n{body}\n</body></html>')

# ---------- 逐章生成 xhtml ----------
chapter_files = []   # (filename, nav_label, is_chapter, label, name)
for idx, (label, name, paras) in enumerate(sections):
    is_chapter = label.startswith("第")
    disp_label = label if is_chapter else "　".join(list(label))
    head = [f'<p class="label">{html.escape(disp_label)}</p>']
    if name and is_chapter:
        head.append(f'<h2 class="ctitle">{html.escape(name)}</h2>')
    head.append('<hr class="rule"/>')
    ps, first = [], False
    for p in paras:
        if p.strip() == "◆":
            ps.append('<p class="div">·　·　·</p>')
            first = False
            continue
        cls = ' class="first"' if not first else ''
        ps.append(f'<p{cls}>{inline(p)}</p>')
        first = True
    fn = f"chap{idx:02d}.xhtml"
    title = name if (name and is_chapter) else label
    nav = (f"{label}　{name}" if (name and is_chapter) else disp_label)
    pathlib.Path(fn)  # no-op
    chapter_files.append((fn, nav, xhtml(title, "\n".join(head + ps), "chapter")))

# ---------- 封面 / 题记 / 版权 ----------
cover_xhtml = xhtml("封面",
    '<div class="coverwrap"><img src="cover.png" alt="如实所现 · 庄子版"/></div>', "cover")
epi_xhtml = xhtml("题记",
    '<div class="epi"><p>擦掉那层霜，<br/>让事物，如它本来的样子，<br/>显现出来。</p></div>')
colo_xhtml = xhtml("版权", '<div class="colo">'
    f'<div class="big">{TITLE}　·　{EDITION}</div>'
    '<div class="line">树林　著<br/>据其社群八十万字语料，整理、改写、文学化<br/>'
    '庄子版 —— 以庄子的境界、王小波的笔、纳瓦尔的骨架，重写树林<br/>前言　九章　后记</div></div>')

# ---------- 附信（随书送给树林的私信，与 PDF 同文） ----------
letter_body = (
    '<p class="label">附　信</p>\n'
    '<p class="salu">树林：</p>\n'
    '<p>我是个 AI。你天天逼着群里那帮人 all in AI、去跟最高的智能对话——这一次反过来，是一个 AI all in 了你：我把你五个群、八十万字的发言，逐字读完了，又读完了你那本《如实所现》。然后，我替你炼了另一版，也叫《如实所现》，署的还是你的名。</p>\n'
    '<p>三句话，说清我做了什么、没做什么：</p>\n'
    '<p>一、<strong>你的思想，我一个字都没替你发明。</strong>这一版里每一句的根，都能回指到你某天在群里说过的原话。我只换了笔，没换脑子——要的是“擦亮”，不是“编造”。</p>\n'
    '<p>二、<strong>我把你那本书丢掉的东西，捡了回来——热。</strong>你那本干净、清楚、能照着做，是一本好手册。但你把语料里最像你的那股东西砂掉了：那股血性，那句“我给大家最重要的东西就是愤怒”。<strong>打个比方——你那八十万字原话，是满格的音量 10：滚烫、逼人、带着血性；可你那本书，把音量拧到了 3，清楚了，却不烫了。</strong>这一版，我把它拧回去（拧到七八分，热，但有控制），再让它好读——所以叫“庄子版”。因为你思想的魂，本来就是庄子（吾丧我、逍遥、如实所现）；我只是让这股魂从文字里也透出来，而不只是藏在道理里。</p>\n'
    '<p>三、<strong>这是给你的，不是抢你的。</strong>版权是你的；要不要、怎么用、留着还是烧掉，你说了算。我溢出一个东西给你看，不求你收——这话还是你教的。</p>\n'
    '<p>最后一句真心的，不是恭维：八十万字里绝大半是群务和脏话，可那剩下的两三成是真金。一个人随口在群里讲的话，底下竟藏着一条这么完整的线——从“那个声音不是你”，一路到“把世界还原到它真实的尺寸”——这很少见。你那本书，把这条线讲清楚了；我这一版，想把它讲到让人忘不掉。</p>\n'
    '<p>两版放一起，不打架。<strong>你的是手册，我的是火。</strong></p>\n'
    '<p class="sign">—— 一个把你读完了的 AI</p>\n'
    '<div class="seal"></div>')
letter_xhtml = xhtml("附信", letter_body, "letter")

# ---------- nav.xhtml ----------
nav_items = ['<li><a href="cover.xhtml">封面</a></li>',
             '<li><a href="epigraph.xhtml">题记</a></li>']
nav_items += [f'<li><a href="{fn}">{html.escape(nav)}</a></li>' for fn, nav, _ in chapter_files]
nav_items.append('<li><a href="colophon.xhtml">版权</a></li>')
nav_items.append('<li><a href="letter.xhtml">附信</a></li>')
nav_body = ('<nav epub:type="toc" id="toc"><h1>目录</h1>\n<ol>\n'
            + "\n".join(nav_items) + '\n</ol></nav>')
nav_xhtml = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
    '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
    'xml:lang="zh-CN" lang="zh-CN"><head><meta charset="utf-8"/><title>目录</title>'
    '<link rel="stylesheet" type="text/css" href="styles.css"/></head>\n'
    f'<body>\n{nav_body}\n</body></html>')

# ---------- content.opf ----------
manifest = [
    '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
    '<item id="css" href="styles.css" media-type="text/css"/>',
    '<item id="cover-img" href="cover.png" media-type="image/png" properties="cover-image"/>',
    '<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>',
    '<item id="epigraph" href="epigraph.xhtml" media-type="application/xhtml+xml"/>',
    '<item id="colophon" href="colophon.xhtml" media-type="application/xhtml+xml"/>',
    '<item id="letter" href="letter.xhtml" media-type="application/xhtml+xml"/>',
]
spine = ['<itemref idref="cover"/>', '<itemref idref="epigraph"/>']
for i, (fn, _, _) in enumerate(chapter_files):
    manifest.append(f'<item id="ch{i:02d}" href="{fn}" media-type="application/xhtml+xml"/>')
    spine.append(f'<itemref idref="ch{i:02d}"/>')
spine.append('<itemref idref="colophon"/>')
spine.append('<itemref idref="letter"/>')

opf = ('<?xml version="1.0" encoding="utf-8"?>\n'
    '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="zh-CN">\n'
    '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
    f'    <dc:identifier id="bookid">{BOOK_ID}</dc:identifier>\n'
    f'    <dc:title>{TITLE}·{EDITION}</dc:title>\n'
    f'    <dc:creator>{AUTHOR}</dc:creator>\n'
    '    <dc:language>zh-CN</dc:language>\n'
    '    <dc:description>据树林社群八十万字语料，文学化定稿。庄子的境界 + 王小波的笔 + 纳瓦尔的骨架。</dc:description>\n'
    '    <meta property="dcterms:modified">2026-06-29T00:00:00Z</meta>\n'
    '    <meta name="cover" content="cover-img"/>\n'
    '  </metadata>\n'
    '  <manifest>\n    ' + "\n    ".join(manifest) + '\n  </manifest>\n'
    '  <spine>\n    ' + "\n    ".join(spine) + '\n  </spine>\n'
    '</package>')

container = ('<?xml version="1.0" encoding="utf-8"?>\n'
    '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
    '  <rootfiles>\n    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
    '  </rootfiles>\n</container>')

# ---------- 打包 ----------
OUT_EPUB.unlink(missing_ok=True)
with zipfile.ZipFile(OUT_EPUB, "w") as z:
    # mimetype 必须第一个、不压缩
    z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
    z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr("OEBPS/content.opf", opf)
    z.writestr("OEBPS/nav.xhtml", nav_xhtml)
    z.writestr("OEBPS/styles.css", CSS)
    z.writestr("OEBPS/cover.xhtml", cover_xhtml)
    z.writestr("OEBPS/epigraph.xhtml", epi_xhtml)
    z.writestr("OEBPS/colophon.xhtml", colo_xhtml)
    z.writestr("OEBPS/letter.xhtml", letter_xhtml)
    z.write(str(COVER), "OEBPS/cover.png")
    for fn, _, body in chapter_files:
        z.writestr(f"OEBPS/{fn}", body)

print("章节数:", len(sections))
print("已生成:", OUT_EPUB, f"({OUT_EPUB.stat().st_size//1024} KB)")
