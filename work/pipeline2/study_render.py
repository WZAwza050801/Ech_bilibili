"""Restrained colour notebook, one reading stream and no screenshot appendix."""
from .concept_map import MAP_CAPTION, render_concept_map
from .render import escape, math_tex, prose_tex, timestamp

PREAMBLE = r"""\documentclass[UTF8,a4paper,11pt,fontset=fandol]{ctexart}
\usepackage[margin=22mm,headheight=16pt]{geometry}
\usepackage{amsmath,amssymb,graphicx,xcolor,fancyhdr,needspace}
\usepackage[most]{tcolorbox}
\usepackage{tikz}
\usetikzlibrary{arrows.meta}
\definecolor{Ink}{HTML}{26344A}
\definecolor{Blue}{HTML}{345D90}
\definecolor{Teal}{HTML}{26736B}
\definecolor{Gold}{HTML}{926323}
\definecolor{Plum}{HTML}{745283}
\definecolor{Alert}{HTML}{A54A40}
\usepackage[unicode,colorlinks,linkcolor=Blue,urlcolor=Teal]{hyperref}
\ctexset{section={format=\Large\bfseries\color{Ink}},subsection={format=\large\bfseries\color{Blue}}}
\pagestyle{fancy}\fancyhf{}
\fancyhead[L]{\small\color{Ink}EchoNotes / 学习笔记}
\fancyhead[R]{\small\color{Teal}讲解 · 推导 · 理解}
\fancyfoot[C]{\small\color{Ink}\thepage}
\setlength{\parskip}{0.45em}
\setlength{\emergencystretch}{3em}
\setcounter{tocdepth}{1}
\allowdisplaybreaks
\newtcolorbox{studybox}[2]{enhanced,breakable,colback=#1!4!white,
 colframe=#1!40!white,colbacktitle=#1!12!white,coltitle=Ink,
 fonttitle=\bfseries,title={#2},boxrule=0.4pt,arc=2mm,
 left=3mm,right=3mm,top=2mm,bottom=2mm,
 before skip=9pt,after skip=9pt}
"""


def box(color, title, body):
    return (r"\begin{studybox}{" + color + "}{" + escape(title) + "}\n" +
            body + "\n" + r"\end{studybox}")


def render_study(study):
    meta, plan = study["meta"], study["plan"]
    lines = [PREAMBLE, r"\begin{document}",
             r"{\small\color{Teal}课程视频 / 理解与批注版}\par\vspace{8mm}",
             r"{\huge\bfseries\color{Ink}" + escape(meta["title"]) + r"}\par\vspace{5mm}",
             r"{\color{Blue}" + escape(meta["owner"]) + " · " + escape(meta["date"]) + r"}\par",
             box("Teal", "贯穿本课的问题", prose_tex(plan["course_question"])),
             prose_tex(plan["perspective"]),
             r"\par\textbf{建议先具备：}" + prose_tex("；".join(plan["prerequisites"])),
             box("Gold", "如何读这份笔记",
                 "蓝色区块记录讲解与来源笔记；绿色为补充推导与理解批注；紫色为自测。"
                 "补充内容是编辑解释，不是老师原话。图片按学习单元选取，重复画面只引用索引。"
                 r"\par " + escape("音频定位精度：" + study["timestamp_precision"]) +
                 "。公式若有疑点会在单元末保留，补充推导不等同于独立验证。")]
    levels = {"basic": "基础理解", "deep": "深入理解", "transfer": "迁移应用"}
    for goal in plan["goals"]:
        lines.append(box("Plum", levels[goal["level"]],
                         prose_tex(goal["outcome"]) + r"\par\textbf{检查：}" + prose_tex(goal["check"])))
    cmap = study.get("concept_map")
    if cmap:
        lines += [r"\clearpage\section*{课程概念地图}",
                  r"{\small\color{Ink}" + escape(MAP_CAPTION) + r"}\par\vspace{3mm}",
                  render_concept_map(cmap, len(study["units"])),
                  r"\clearpage"]
    lines += [r"\tableofcontents\clearpage"]
    displayed = {}
    for i, unit in enumerate(study["units"], 1):
        content = unit["content"]
        lines += [r"\section{" + escape(unit["title"]) + "}",
                  r"{\small\color{Blue}" + escape(timestamp(unit["start"]) + "–" +
                                                     timestamp(unit["end"])) + r"}\par",
                  box("Teal", "这一段要想明白", prose_tex(unit["focus"]))]
        frame = unit["frame"]
        if frame:
            sha = frame["sha256"]
            if sha in displayed:
                lines.append(r"\noindent\textbf{画面沿用：}\hyperref[pic:" +
                             str(displayed[sha]) + "]{学习单元 " + str(displayed[sha]) + " 的图}。")
            else:
                displayed[sha] = i
                lines += [r"\begin{center}",
                          r"\includegraphics[width=.88\linewidth,height=.30\textheight,keepaspectratio]{" +
                          frame["path"] + "}",
                          r"\phantomsection\label{pic:" + str(i) + "}",
                          r"\par{\small\color{Blue}" +
                          escape("画面索引 " + frame["id"] + " / " + timestamp(frame["actual_t"])) + "}",
                          r"\end{center}"]
        else:
            lines.append(r"{\small\color{Alert}本段没有合适的代表画面，以音频证据为主。}")
        lines.append(box("Blue", "老师讲了什么 · 音频整理", prose_tex(content["audio_summary"])))
        for note in content["notes"]:
            supplement = note["provenance"] == "supplement"
            body = prose_tex(note["text"])
            for equation in note["equations"]:
                body += "\n\\[\n" + math_tex(equation) + "\n\\]\n"
            if note["evidence_ids"]:
                body += r"\par{\scriptsize\color{Blue}来源索引：" + escape("、".join(note["evidence_ids"])) + "}"
            lines.append(box("Teal" if supplement else "Blue",
                             ("补充推导 / " if supplement else "课堂笔记 / ") + note["title"], body))
        for annotation in content["annotations"]:
            lines.append(box("Teal", "理解批注 / " + annotation["title"], prose_tex(annotation["text"])))
        symbols = content.get("symbol_summary")
        if symbols:
            rows = []
            for entry in symbols:
                try:
                    shown = r"\(" + math_tex(entry["symbol"]) + r"\)"
                except ValueError:
                    shown = escape(entry["symbol"])
                rows.append(prose_tex(shown + "：" + entry["meaning"]))
            lines.append(box("Blue", "本单元符号", r"\par ".join(rows)))
        check = content["self_check"]
        lines.append(box("Plum", "停一下，检查理解",
                         prose_tex(check["question"]) + r"\par\textbf{提示：}" + prose_tex(check["hint"])))
        issues = list(content["uncertainties"])
        issues += [c["id"] + "：" + c["note"] for c in unit["original_formula_issues"]]
        if issues:
            lines.append(box("Alert", "证据疑点 · 保留供复查",
                             r"\par ".join(prose_tex(s) for s in dict.fromkeys(issues))))
        lines += [r"{\scriptsize\color{Blue}音频索引：" + escape("、".join(unit["segment_ids"])) + "}",
                  r"\clearpage"]
    lines += [r"\section*{来源与阅读边界}",
              prose_tex("原视频：" + meta.get("url", "本地文件")),
              "本版复用已有转写和采样帧生成学习目标与理解笔记，未重新执行整段视频理解。"
              "视觉识别可能遗漏短暂板书，整理后的音频不是逐字引语；解释与补充推导已单独标色。"
              "学习目标是依据课程内容给出的建议，不代表已测量你的知识水平。",
              r"\end{document}"]
    return "\n".join(lines) + "\n"
