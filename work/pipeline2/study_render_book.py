"""Publication edition: continuous prose, restrained colour law, no card grid.

Same evidence contracts as the card edition (colours carry meaning; supplements
stay distinguishable from classroom content) but typeset like a book.
"""
from .concept_map import MAP_CAPTION, render_concept_map
from .render import escape, math_tex, prose_tex, timestamp

PREAMBLE = r"""\documentclass[UTF8,a4paper,11pt,fontset=fandol]{ctexart}
\usepackage[margin=26mm,headheight=16pt]{geometry}
\usepackage{amsmath,amssymb,graphicx,xcolor,fancyhdr,needspace}
\usepackage[most]{tcolorbox}
\usepackage{tikz}
\usetikzlibrary{arrows.meta}
\definecolor{Ink}{HTML}{1F2A3A}
\definecolor{Blue}{HTML}{345D90}
\definecolor{Teal}{HTML}{26736B}
\definecolor{Gold}{HTML}{926323}
\definecolor{Plum}{HTML}{745283}
\definecolor{Alert}{HTML}{A54A40}
\usepackage[unicode,colorlinks,linkcolor=Blue,urlcolor=Teal]{hyperref}
\ctexset{
 section={format=\LARGE\bfseries\color{Ink},beforeskip=1.2em,afterskip=0.6em},
 subsection={format=\large\bfseries\color{Ink}}}
\pagestyle{fancy}\fancyhf{}
\fancyhead[L]{\small\color{Ink}EchoNotes / 精读版}
\fancyfoot[C]{\small\color{Ink}\thepage}
\renewcommand{\headrulewidth}{0.3pt}
\setlength{\parskip}{0.5em}
\setlength{\parindent}{2em}
\setlength{\emergencystretch}{3em}
\setcounter{tocdepth}{1}
\allowdisplaybreaks
\newcommand{\runhead}[2]{\needspace{4\baselineskip}\par\medskip
 \noindent{\color{#1}\bfseries #2}\par\nopagebreak\smallskip}
\newtcolorbox{insightbox}{enhanced,breakable,colback=Teal!3!white,
 colframe=Teal!55!white,boxrule=0pt,leftrule=1.2pt,
 left=3mm,right=2mm,top=2mm,bottom=2mm,before skip=8pt,after skip=8pt}
\newtcolorbox{checkbox}{enhanced,breakable,colback=Plum!3!white,
 colframe=Plum!50!white,boxrule=0pt,leftrule=1.2pt,
 left=3mm,right=2mm,top=2mm,bottom=2mm,before skip=8pt,after skip=8pt}
\newtcolorbox{focusbox}[1]{enhanced,breakable,colback=Teal!4!white,
 colframe=Teal!35!white,boxrule=0.4pt,arc=1.5mm,
 left=3mm,right=3mm,top=2mm,bottom=2mm,before skip=8pt,after skip=8pt,
 coltitle=Ink,fonttitle=\bfseries,title={#1}}
"""


def symbol_tex(value):
    try:
        return r"\(" + math_tex(value) + r"\)"
    except ValueError:
        return escape(value)


def note_block(lines, note):
    supplement = note["provenance"] == "supplement"
    color = "Teal" if supplement else "Ink"
    heading = ("〔补充〕" if supplement else "") + note["title"]
    lines.append(r"\runhead{" + color + "}{" + escape(heading) + "}")
    lines.append(prose_tex(note["text"]))
    for equation in note["equations"]:
        lines.append("\\[\n" + math_tex(equation) + "\n\\]")
    if note["evidence_ids"]:
        lines.append(r"\par{\scriptsize\color{Blue}来源：" +
                     escape("、".join(note["evidence_ids"])) + "}")


def render_book(study):
    meta, plan = study["meta"], study["plan"]
    lines = [PREAMBLE, r"\begin{document}",
             r"\begin{center}",
             r"{\small\color{Teal}课程视频精读 · 出版编排}\par\vspace{10mm}",
             r"{\Huge\bfseries\color{Ink}" + escape(meta["title"]) + r"}\par\vspace{6mm}",
             r"{\color{Blue}" + escape(meta["owner"]) + " · " + escape(meta["date"]) + r"}\par",
             r"\end{center}\vspace{4mm}",
             r"\begin{focusbox}{贯穿全书的问题}" + prose_tex(plan["course_question"]) + r"\end{focusbox}",
             prose_tex(plan["perspective"]),
             r"\par\noindent{\bfseries 建议先具备：}" + prose_tex("；".join(plan["prerequisites"])),
             r"\begin{focusbox}{如何读这本书}",
             "课堂内容以常规正文呈现，标题前带〔补充〕的条目是编辑补全的推导、"
             "例子与条件澄清；绿色竖线段落是批注，给行家判断与适用边界；"
             "紫色段落是思考题；节末小字红色条目保留证据疑点，不做静默修正。"
             r"\par " + escape("音频定位精度：" + study["timestamp_precision"]) +
             "。补充推导不等同于独立验证，引用课程内容时以来源索引为准。",
             r"\end{focusbox}"]
    levels = {"basic": "基础理解", "deep": "深入理解", "transfer": "迁移应用"}
    for goal in plan["goals"]:
        lines.append(r"\noindent{\color{Plum}\bfseries " + escape(levels[goal["level"]]) +
                     "}　" + prose_tex(goal["outcome"]) +
                     r"\par\nopagebreak{\small\color{Ink}检验：" + prose_tex(goal["check"]) + r"}\par")
    cmap = study.get("concept_map")
    if cmap:
        lines += [r"\clearpage\section*{课程概念地图}",
                  r"{\small\color{Ink}" + escape(MAP_CAPTION) + r"}\par\vspace{4mm}",
                  render_concept_map(cmap, len(study["units"])),
                  r"\clearpage"]
    lines += [r"\tableofcontents\clearpage"]
    displayed = {}
    for i, unit in enumerate(study["units"], 1):
        content = unit["content"]
        lines += [r"\section{" + escape(unit["title"]) + "}",
                  r"{\small\color{Blue}" + escape(timestamp(unit["start"]) + "–" +
                                                     timestamp(unit["end"])) + r"}\par",
                  r"\begin{focusbox}{这一节要想明白}" + prose_tex(unit["focus"]) + r"\end{focusbox}"]
        frame = unit["frame"]
        if frame:
            sha = frame["sha256"]
            if sha in displayed:
                lines.append(r"\par{\small\color{Blue}画面沿用第 " + str(displayed[sha]) +
                             " 节的图（" + escape(frame["id"] + " / " +
                                                 timestamp(frame["actual_t"])) + "）。}")
            else:
                displayed[sha] = i
                lines += [r"\begin{center}",
                          r"\includegraphics[width=.8\linewidth,height=.32\textheight,keepaspectratio]{" +
                          frame["path"] + "}",
                          r"\par{\small\color{Blue}" +
                          escape("画面 " + frame["id"] + " · " + timestamp(frame["actual_t"])) + "}",
                          r"\end{center}"]
        else:
            lines.append(r"\par{\small\color{Alert}本节没有合适的代表画面，以音频证据为主。}")
        lines.append(r"\runhead{Ink}{课堂讲解}")
        lines.append(prose_tex(content["audio_summary"]))
        for note in content["notes"]:
            note_block(lines, note)
        for annotation in content["annotations"]:
            lines += [r"\begin{insightbox}",
                      r"{\color{Teal}\bfseries 批注 · " + escape(annotation["title"]) + r"}\par",
                      prose_tex(annotation["text"]),
                      r"\end{insightbox}"]
        symbols = content.get("symbol_summary")
        if symbols:
            rows = "；".join(symbol_tex(s["symbol"]) + "　" + prose_tex(s["meaning"])
                            for s in symbols)
            lines.append(r"\par{\small\color{Ink}\bfseries 本节符号　}" +
                         r"{\small " + rows + r"}\par")
        check = content["self_check"]
        lines += [r"\begin{checkbox}",
                  r"{\color{Plum}\bfseries 思考}\par",
                  prose_tex(check["question"]) + r"\par{\small\color{Ink}提示：}" +
                  prose_tex(check["hint"]),
                  r"\end{checkbox}"]
        issues = list(content["uncertainties"])
        issues += [c["id"] + "：" + c["note"] for c in unit["original_formula_issues"]]
        if issues:
            lines.append(r"\par{\footnotesize\color{Alert}疑点（保留供复查，未静默修正）：" +
                         r"\par ".join(prose_tex(s) for s in dict.fromkeys(issues)) + "}")
        lines += [r"{\scriptsize\color{Blue}本节音频索引：" +
                  escape("、".join(unit["segment_ids"])) + "}", r"\clearpage"]
    lines += [r"\section*{来源与阅读边界}",
              prose_tex("原视频：" + meta.get("url", "本地文件")),
              "本版复用已有转写和采样帧生成学习目标与理解笔记，未重新执行整段视频理解。"
              "视觉识别可能遗漏短暂板书，整理后的音频不是逐字引语；"
              "〔补充〕条目与批注是编辑内容，未经独立证明。"
              "学习目标是依据课程内容给出的建议，不代表已测量你的知识水平。",
              r"\end{document}"]
    return "\n".join(lines) + "\n"
