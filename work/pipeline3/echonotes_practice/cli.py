import argparse
import json
from pathlib import Path
from .common import read_json, run, save_json
from .contracts import PROGRAMMABLE, classify, normalize_timestamps, validate_argv, validate_plan
from .executor import execute
from .frames import evidence_frames, extract, merged_times
from .gemini import Gemini, analysis_prompt, api_key_from, extract_json, interaction_text
from .report import render
from .siliconflow import SiliconFlow, encode_chunk, frame_content
from .siliconflow import api_key_from as sf_key_from
from .source import Bilibili, parse_bvid, polish, transcribe


def repair_steps(analysis):
    """Make provider output pass validate_plan: auto-repair what is recoverable
    (missing expected, res:// paths, trivial verifies) and downgrade steps that
    cannot be made contract-compliant to ui_operation instead of losing the page."""
    for step in analysis.get("steps", []):
        path = step.get("path")
        if isinstance(path, str) and path.startswith("res://"):
            # Godot project-relative protocol; strip to a plain relative path.
            step["path"] = path[len("res://"):].lstrip("/")
        if not step.get("expected"):
            step["expected"] = (step.get("details")
                                or "对照视频对应时间戳的画面核对")
        if not isinstance(step.get("depends_on"), list):
            step["depends_on"] = []
        verify = step.get("verify")
        if isinstance(verify, dict):
            files = verify.get("files_exist")
            if isinstance(files, list):
                # res:// prefix leaks into file-existence checks too.
                verify["files_exist"] = [
                    f[len("res://"):].lstrip("/") if isinstance(f, str) and f.startswith("res://") else f
                    for f in files]
        action = step.get("action")
        def downgrade(reason):
            step["action"] = "ui_operation"
            step["downgraded"] = reason
            step.pop("verify", None)
        if action in {"write_file", "set_param"}:
            if not step.get("path") or not isinstance(step.get("content"), str):
                downgrade("missing path/content for a file step")
        elif action == "run_command":
            try:
                validate_argv(step.get("argv"))
            except ValueError as exc:
                downgrade(f"invalid argv: {exc}")
        elif action == "install_pkg":
            import re as _re
            packages = step.get("packages") or []
            if not packages or any(
                    not _re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", str(p))
                    for p in packages):
                downgrade("packages missing or not name==version")
        if step.get("action") in PROGRAMMABLE:
            verify = step.get("verify") or {}
            ok = False
            try:
                validate_argv(verify.get("argv"))
                ok = bool(verify.get("stdout_contains") or verify.get("files_exist")
                          or verify.get("assertions"))
            except ValueError:
                ok = False
            if not ok:
                if step.get("action") == "write_file" and step.get("path"):
                    step["verify"] = {"files_exist": [step["path"]]}
                else:
                    downgrade("verify not automatable")
    return analysis


def chunk_bounds(duration, chunk_seconds):
    bounds = []
    start = 0.0
    while start < duration - 1:
        end = min(duration, start + chunk_seconds)
        bounds.append((round(start, 2), round(end, 2)))
        start = end
    return bounds


def split_video(source, target, start, end):
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-to", f"{end:.2f}",
         "-i", source, "-c", "copy", target])


def chunked_analysis(client, meta, segments, run_dir, chunk_seconds, provider="gemini",
                     mode="video"):
    """Analyze pages longer than the model's video window by splitting into
    time-ordered chunks; merge step/section lists with global timestamps."""
    source = run_dir / "source" / "source.mp4"
    chunks_dir = run_dir / "source" / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    duration = float(meta["duration"])
    if provider == "siliconflow":
        prefix = "sff" if mode == "frames" else "sf"
    else:
        prefix = "gemini"
    merged = {"summary_parts": [], "prerequisites": [], "concepts": [], "sections": [],
              "steps": [], "gaps": [], "tutorial_issues": [], "chunk_classifications": []}
    seen_concepts = set()
    for index, (start, end) in enumerate(chunk_bounds(duration, chunk_seconds), 1):
        chunk_path = chunks_dir / f"chunk-{index:02d}.mp4"
        frames_mode = provider == "siliconflow" and mode == "frames"
        if not frames_mode and not chunk_path.exists():
            if provider == "siliconflow":
                # Native 1080p detail, audio stripped (ASR transcript rides in prompt).
                encode_chunk(source, chunk_path, start, end)
            else:
                split_video(source, chunk_path, start, end)
        transcript = "\n".join(
            f"[{max(0.0, x['start'] - start):.2f}-{min(end, x['end']) - start:.2f}] {x['text']}"
            for x in segments if float(x["end"]) > start and float(x["start"]) < end)
        chunk_meta = dict(meta, duration=round(end - start, 2))
        response_path = run_dir / f"{prefix}-response-chunk-{index:02d}.json"
        if response_path.exists():
            raw = read_json(response_path)
            text = raw["text"] if provider == "siliconflow" else interaction_text(raw)
        else:
            prompt = analysis_prompt(chunk_meta, transcript)
            if frames_mode:
                content, _ = frame_content(
                    source, start, end,
                    work_dir=run_dir / "source" / "frames" / f"{index:02d}")
                content.append({"type": "text", "text": prompt})
                text, raw = client.analyze_framelist(content)
            elif provider == "siliconflow":
                text, raw = client.analyze_video(chunk_path, prompt)
            else:
                uploaded = client.upload_or_reuse(chunk_path)
                text, raw = client.interaction(prompt, uploaded)
            save_json(response_path, raw)
        part = extract_json(text)
        minutes = lambda t: f"{int(t)//60:02d}:{int(t)%60:02d}"
        merged["summary_parts"].append(
            f"**片段 {index}（{minutes(start)}-{minutes(end)}）**：{part.get('summary', '')}")
        merged["chunk_classifications"].append(part.get("classification", {}))
        for value in part.get("prerequisites", []):
            if value not in merged["prerequisites"]:
                merged["prerequisites"].append(value)
        for concept in part.get("concepts", []):
            name = concept.get("name", "")
            if name and name not in seen_concepts:
                seen_concepts.add(name)
                concept["evidence_t"] = float(concept.get("evidence_t", 0)) + start
                merged["concepts"].append(concept)
        for section in part.get("sections", []):
            merged["sections"].append({
                "start": float(section.get("start", 0)) + start,
                "end": float(section.get("end", end - start)) + start,
                "title": section.get("title", ""),
                "notes": section.get("notes", "")})
        id_map = {}
        new_steps = []
        for step in part.get("steps", []):
            # Key by source id, but tolerate duplicate/missing ids inside one
            # chunk (weaker models do this): each step still gets a fresh id.
            source_id = step.get("id", "") or f"__anon{len(new_steps)}"
            new_id = f"s{len(merged['steps']) + len(new_steps) + 1:02d}"
            if source_id not in id_map:
                id_map[source_id] = new_id
            step["id"] = new_id
            step["evidence_t"] = float(step.get("evidence_t", 0)) + start
            step["chunk_offset"] = round(start, 2)
            new_steps.append(step)
        earlier = []
        for step in new_steps:
            step["depends_on"] = [id_map[d] for d in step.get("depends_on", [])
                                  if id_map.get(d) in earlier]
            earlier.append(step["id"])
            merged["steps"].append(step)
        for gap in part.get("gaps", []):
            gap["evidence_t"] = float(gap.get("evidence_t", 0)) + start
            merged["gaps"].append(gap)
        merged["tutorial_issues"].extend(part.get("tutorial_issues", []))
    merged["summary"] = "\n\n".join(merged.pop("summary_parts"))
    return merged


def main():
    parser = argparse.ArgumentParser(description="EchoNotes pipeline 3")
    parser.add_argument("video")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--secrets", type=Path)
    parser.add_argument("--asr-model", type=Path)
    parser.add_argument("--model", default="gemini-3.8-flash")
    parser.add_argument("--fallback-model", default="gemini-3.7-flash")
    parser.add_argument("--page", type=int, default=1,
                        help="Bilibili video page (P number), 1-based")
    parser.add_argument("--provider", default="siliconflow", choices=["siliconflow", "gemini"],
                        help="Video-understanding provider (default: siliconflow Qwen3-VL)")
    parser.add_argument("--sf-model", default="Qwen/Qwen3-VL-30B-A3B-Instruct",
                        help="SiliconFlow vision model when --provider siliconflow")
    parser.add_argument("--mode", default="video", choices=["video", "frames"],
                        help="siliconflow input style: video_url (cheap, capped) or "
                             "labeled frame list (~20x visual tokens, hifi)")
    parser.add_argument("--chunk-seconds", type=int, default=0,
                        help="Split pages longer than this into chunks; 0 = auto "
                             "(300 for siliconflow, 2400 for gemini)")
    parser.add_argument("--proxy", default=None,
                        help="Explicit HTTP(S) proxy for model API calls")
    parser.add_argument("--prepare-only", action="store_true",
                        help="Stop after download and ASR; no model calls")
    parser.add_argument("--polish", action="store_true",
                        help="Spend extra model calls on ASR punctuation cleanup")
    args = parser.parse_args()
    source_dir = args.run_dir / "source"
    meta = Bilibili().acquire(parse_bvid(args.video), source_dir, page=args.page)
    if not (source_dir / "transcript.json").exists():
        if not args.asr_model:
            raise RuntimeError("--asr-model is required when no cached transcript exists")
        transcribe(source_dir, args.asr_model)
    if args.chunk_seconds <= 0:
        args.chunk_seconds = 300 if args.provider == "siliconflow" else 2400
    if args.prepare_only:
        print(json.dumps({"output": str(source_dir), "prepared": True},
                         ensure_ascii=False))
        return
    if args.provider == "siliconflow":
        client = SiliconFlow(sf_key_from(args.secrets), args.sf_model)
    else:
        client = Gemini(api_key_from(args.secrets), args.model, proxy=args.proxy)
    if args.polish and args.provider != "gemini":
        raise SystemExit("--polish currently requires --provider gemini")
    if args.polish and not (source_dir / "polished.json").exists():
        polish(source_dir, client)
    source_segments = (read_json(source_dir / "polished.json")
                       if (source_dir / "polished.json").exists()
                       else read_json(source_dir / "transcript.json")["segments"])
    if not (args.run_dir / "analysis.json").exists():
        duration = float(meta["duration"])
        if duration > args.chunk_seconds:
            analysis = chunked_analysis(client, meta, source_segments,
                                        args.run_dir, args.chunk_seconds,
                                        provider=args.provider, mode=args.mode)
            actual_model = (args.sf_model + "+framelist"
                            if (args.provider == "siliconflow" and args.mode == "frames")
                            else args.sf_model if args.provider == "siliconflow"
                            else args.model)
            save_json(args.run_dir / "analysis-chunks.json", analysis)
        else:
            transcript = "\n".join(
                f"[{item['start']:.2f}-{item['end']:.2f}] {item['text']}"
                for item in source_segments)
            prefix = ("sff" if args.mode == "frames" else "sf") \
                if args.provider == "siliconflow" else "gemini"
            response_path = args.run_dir / f"{prefix}-response.json"
            if response_path.exists():
                raw = read_json(response_path)
                if args.provider == "siliconflow":
                    text = raw["text"]
                else:
                    text = interaction_text(raw)
                actual_model = raw.get("model", "cached-response")
            elif args.provider == "siliconflow" and args.mode == "frames":
                content, _ = frame_content(source_dir / "source.mp4", 0.0, float(meta["duration"]),
                                           work_dir=args.run_dir / "source" / "frames" / "single")
                content.append({"type": "text", "text": analysis_prompt(meta, transcript)})
                text, raw = client.analyze_framelist(content)
                actual_model = raw["model"]
                save_json(response_path, raw)
            elif args.provider == "siliconflow":
                text, raw = client.analyze_video(source_dir / "source.mp4",
                                                 analysis_prompt(meta, transcript))
                actual_model = raw["model"]
                save_json(response_path, raw)
            else:
                uploaded = client.upload_or_reuse(source_dir / "source.mp4")
                save_json(args.run_dir / "gemini-file.json", uploaded)
                try:
                    text, raw = client.interaction(analysis_prompt(meta, transcript), uploaded)
                    actual_model = args.model
                except RuntimeError as exc:
                    throttled = ("Gemini HTTP 429" in str(exc)
                                 or "Gemini HTTP 503" in str(exc))
                    if not throttled or not args.fallback_model:
                        raise
                    client = Gemini(api_key_from(args.secrets), args.fallback_model,
                                    proxy=args.proxy)
                    text, raw = client.interaction(analysis_prompt(meta, transcript), uploaded)
                    actual_model = args.fallback_model
                save_json(response_path, raw)
            analysis = extract_json(text)
        # Providers differ in discipline; repair/downgrade before validation.
        repair_steps(analysis)
        analysis["analysis_model"] = actual_model
        analysis["model_classification"] = analysis.get("classification")
        analysis["classification"] = classify(analysis.get("steps", []))
        normalize_timestamps(analysis, meta["duration"])
        validate_plan(analysis, meta["duration"])
        save_json(args.run_dir / "analysis.json", analysis)
    else:
        analysis = read_json(args.run_dir / "analysis.json")
    overview = args.run_dir / "overview-frames"
    if not (overview / "manifest.json").exists():
        extract(source_dir / "source.mp4", overview, merged_times(source_dir / "source.mp4"))
    evidence_frames(source_dir / "source.mp4", args.run_dir / "evidence-frames", analysis["steps"])
    records = execute(analysis, args.run_dir / "artifact", args.run_dir / "execution.json",
                      grade=analysis["classification"]["grade"])
    output = render(meta, analysis, records, args.run_dir)
    print(json.dumps({"output": str(output), "classification": analysis["classification"]},
                     ensure_ascii=False))
