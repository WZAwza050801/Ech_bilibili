"""Render structured content; never compile a model-authored document or preamble."""
import os
import re
import subprocess

# A deliberately bounded math vocabulary. Unsupported commands become visible review notes.
MATH_COMMANDS = set("""
frac dfrac tfrac sqrt root over binom dbinom tbinom
alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu
xi pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega
Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega
sum prod coprod int iint iiint oint lim limsup liminf sup inf max min
sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh log ln exp det dim ker gcd
mod bmod pmod operatorname mathrm mathbf mathit mathsf mathtt mathcal mathbb boldsymbol
text textrm textnormal mathnormal overline underline widehat widetilde hat bar vec dot ddot
left right big Big bigg Bigg bigl bigr Bigl Bigr
cdot cdots ldots vdots ddots times div pm mp circ bullet ast star
le leq ge geq neq ne approx sim simeq equiv cong propto
in notin ni subset subseteq supset supseteq cup cap setminus emptyset varnothing
forall exists nexists neg land lor wedge vee implies iff
to mapsto rightarrow leftarrow leftrightarrow Rightarrow Leftarrow Leftrightarrow
longrightarrow longleftarrow Longrightarrow Longleftrightarrow
infty partial nabla ell hbar Re Im top bot perp parallel angle triangle
langle rangle lvert rvert lVert rVert vert Vert lfloor rfloor lceil rceil
quad qquad space hspace phantom vphantom hphantom
underbrace overbrace underset overset substack
begin end cases aligned gathered matrix pmatrix bmatrix vmatrix Vmatrix smallmatrix
nonumber notag
""".split())
MATH_ENVS = {"aligned", "gathered", "cases", "matrix", "pmatrix", "bmatrix", "vmatrix", "Vmatrix", "smallmatrix"}


def math_tex(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Empty math")
    if re.search(r"[%#$~\x00-\x08\x0b-\x1f]", value) or "^^" in value:
        raise ValueError("Unsupported math characters")
    commands = re.findall(r"\\([A-Za-z]+|.)", value, flags=re.S)
    if any(c not in MATH_COMMANDS and c not in {",", ";", ":", "!", " ", "\\", "{", "}", "|", "_", "&"} for c in commands):
        raise ValueError("Unsupported LaTeX command")
    environments = []
    for action, env in re.findall(r"\\(begin|end)\s*\{([^{}]+)\}", value):
        if env not in MATH_ENVS:
            raise ValueError("Unsupported math environment")
        if action == "begin":
            environments.append(env)
        elif not environments or environments.pop() != env:
            raise ValueError("Mismatched math environment")
    if environments:
        raise ValueError("Unclosed math environment")
    depth = 0
    for token in re.findall(r"\\.|[{}]", value):
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
        if depth < 0:
            raise ValueError("Unbalanced math braces")
    if depth:
        raise ValueError("Unbalanced math braces")
    return value.strip()


ESCAPES = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$",
           "&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "~": r"\textasciitilde{}",
           "^": r"\textasciicircum{}"}


def escape(value):
    return "".join(ESCAPES.get(c, c) for c in str(value))


def prose_tex(value):
    parts = re.split(r"(\\\(.*?\\\)|(?<!\\)\$[^$\n]+(?<!\\)\$)", value, flags=re.S)
    output = []
    for part in parts:
        if part.startswith(r"\(") and part.endswith(r"\)"):
            content = part[2:-2]
        elif part.startswith("$") and part.endswith("$"):
            content = part[1:-1]
        else:
            output.append(escape(part))
            continue
        try:
            output.append(r"\(" + math_tex(content) + r"\)")
        except ValueError:
            output.append(escape(part) + r"\textbf{（行内公式待核验）}")
    return "".join(output).replace("\n\n", "\n\n\\noindent ")


def timestamp(value):
    seconds = int(value)
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


PREAMBLE = r"""\documentclass[UTF8,a4paper,11pt,fontset=fandol]{ctexart}
\usepackage[margin=24mm]{geometry}
\usepackage{amsmath,amssymb,amsthm,graphicx,xcolor,longtable,booktabs}
\usepackage[unicode,colorlinks=true,linkcolor=blue,urlcolor=blue]{hyperref}
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{EchoNotes · 课程讲义}
\fancyhead[R]{证据可回查 · 初稿}
\fancyfoot[C]{\thepage}
\setlength{\headheight}{15pt}
\setlength{\emergencystretch}{3em}
\setlength{\parskip}{0.45em}
\newtheorem{definition}{定义}[section]
\newtheorem{theorem}[definition]{定理}
\newtheorem{example}[definition]{例题}
\renewcommand{\proofname}{证明}
\allowdisplaybreaks
"""


def render(lecture, run):
    meta, blocks, report = lecture["meta"], lecture["blocks"], lecture["quality"]
    frame_map = {f["id"]: f for f in lecture["frames"]}
    segment_map = {s["id"]: s for s in lecture["segments"]}
    check_map = {c["id"]: c for c in report["formula_checks"]}
    lines = [PREAMBLE, r"\title{" + escape(meta["title"]) + "}",
             r"\author{EchoNotes 课程整理}", r"\date{" + escape(meta["date"]) + "}",
             r"\begin{document}", r"\maketitle",
             r"\noindent\textbf{来源：}" + escape(meta.get("owner", "本地课程"))]
    if meta.get("url"):
        lines.append(r"\par\url{" + meta["url"] + "}")
    lines.extend([r"\par\textbf{阅读说明：}本讲义为机器整理初稿。公式视觉复查仅表示与原帧一致，"
                  "不代表数学正确；缺失条件、模糊板书和符号冲突均需回看原视频。",
                  r"\tableofcontents", r"\newpage"])
    by_id = {b["id"]: b for b in blocks}
    for section in lecture["outline"]["sections"]:
        lines.append(r"\section{" + escape(section["title"]) + "}")
        for block_id in section["block_ids"]:
            block = by_id[block_id]
            lines.append(r"\subsection{" + escape(block["title"]) + "}")
            evidence = [timestamp(segment_map[s]["start"]) for s in block["segment_ids"]]
            evidence += [timestamp(frame_map[f]["actual_t"]) for f in block["frame_ids"]]
            lines.append(r"{\small\color{gray}证据时间：" + escape("、".join(dict.fromkeys(evidence))) + r"}\par")
            env = block["kind"] if block["kind"] in {"definition", "theorem", "example", "proof"} else None
            if env:
                lines.append(r"\begin{" + env + "}")
            lines.append(prose_tex(block["text"]))
            for formula in block["formulas"]:
                try:
                    lines.append("\\[\n" + math_tex(formula["latex"]) + "\n\\]")
                except ValueError:
                    lines.append(r"\textbf{公式待人工排版：}" + escape(formula["latex"]))
                check = check_map.get(formula["id"], {})
                if formula["uncertain"] or check.get("status") != "match":
                    lines.append(r"\par{\small\color{red}公式待核验：" +
                                 escape(check.get("note", "原始识别不确定")) + "}")
            if env:
                lines.append(r"\end{" + env + "}")
            for note in block["uncertainties"]:
                lines.append(r"\par\textbf{待核验：}" + prose_tex(note))
            if block["frame_ids"]:
                refs = [r"\hyperref[frame:" + f + "]{" + escape(f) + "}" for f in block["frame_ids"]]
                lines.append(r"\par{\small 板书索引：" + "，".join(refs) + "}")
    lines.extend([r"\appendix", r"\section{符号表与核验记录}"])
    for symbol, meanings in report["symbols"].items():
        try:
            shown = r"\(" + math_tex(symbol) + r"\)"
        except ValueError:
            shown = escape(symbol)
        lines.append(r"\noindent " + shown + "：" + prose_tex("；".join(meanings)) + r"\par")
    if report["symbol_conflicts"]:
        lines.append(r"\textbf{符号含义存在多种记录，需结合上下文检查：}" +
                     escape("，".join(report["symbol_conflicts"])))
    lines.append(prose_tex(report["disclaimer"]))
    lines.append(f"未被知识块显式引用的转写段：{len(report['unreferenced_segments'])}；"
                 f"未被显式引用的抽帧：{len(report['unreferenced_frames'])}。完整清单见 quality.json。")
    lines.extend([r"\section{板书证据索引}",
                  "图片采用实际解码时间。同一图片多次出现会分别标记时间，不等于视频全部画面已覆盖。"])
    # One page per unique frame, with all occurrence anchors retained.
    groups = {}
    for frame in lecture["frames"]:
        groups.setdefault(frame["path"], []).append(frame)
    for path, occurrences in groups.items():
        if not re.fullmatch(r"frames/f\d+\.jpg", path):
            raise ValueError("Unsafe frame path")
        lines.append(r"\clearpage")
        for frame in occurrences:
            lines.append(r"\phantomsection\label{frame:" + frame["id"] + "}")
        labels = "；".join(f"{f['id']} / {timestamp(f['actual_t'])}" for f in occurrences)
        lines.append(r"\noindent\textbf{" + escape(labels) + r"}\par")
        lines.append(r"\begin{center}\includegraphics[width=\linewidth,height=.70\textheight,keepaspectratio]{" +
                     path + r"}\end{center}")
    lines.append(r"\end{document}")
    path = run / "lecture.tex"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def compile_pdf(run):
    args = ["xelatex", "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "lecture.tex"]
    for pass_number in (1, 2):
        process = subprocess.run(args, cwd=run, capture_output=True, encoding="utf-8",
                                 errors="replace", timeout=180,
                                 env=os.environ | {"openin_any": "p", "openout_any": "p"})
        (run / f"compile-{pass_number}.txt").write_text(process.stdout + process.stderr, encoding="utf-8")
        if process.returncode:
            raise RuntimeError(f"XeLaTeX failed; inspect {run / f'compile-{pass_number}.txt'}")
    if not (run / "lecture.pdf").exists():
        raise RuntimeError("XeLaTeX did not produce lecture.pdf")
    log = (run / "lecture.log").read_text(encoding="utf-8", errors="replace")
    return {"engine": "xelatex", "passes": 2, "pdf": "lecture.pdf",
            "layout_warnings": [line for line in log.splitlines()
                                if "Overfull" in line or "Missing character" in line]}
