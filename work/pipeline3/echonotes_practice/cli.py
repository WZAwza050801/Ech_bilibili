import argparse
import json
from pathlib import Path
from .common import read_json, save_json
from .contracts import classify, normalize_timestamps, validate_plan
from .executor import execute
from .frames import evidence_frames, extract, merged_times
from .gemini import Gemini, analysis_prompt, api_key_from, extract_json
from .report import render
from .source import Bilibili, parse_bvid, polish, transcribe


def main():
    parser = argparse.ArgumentParser(description="EchoNotes pipeline 3")
    parser.add_argument("video")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--secrets", type=Path)
    parser.add_argument("--asr-model", type=Path)
    parser.add_argument("--model", default="gemini-3.8-flash")
    parser.add_argument("--fallback-model", default="gemini-3.7-flash")
    parser.add_argument("--polish", action="store_true",
                        help="Spend extra model calls on ASR punctuation cleanup")
    args = parser.parse_args()
    source_dir = args.run_dir / "source"
    meta = Bilibili().acquire(parse_bvid(args.video), source_dir)
    if not (source_dir / "transcript.json").exists():
        if not args.asr_model:
            raise RuntimeError("--asr-model is required when no cached transcript exists")
        transcribe(source_dir, args.asr_model)
    client = Gemini(api_key_from(args.secrets), args.model)
    if args.polish and not (source_dir / "polished.json").exists():
        polish(source_dir, client)
    source_segments = (read_json(source_dir / "polished.json")
                       if (source_dir / "polished.json").exists()
                       else read_json(source_dir / "transcript.json")["segments"])
    transcript = "\n".join(
        f"[{item['start']:.2f}-{item['end']:.2f}] {item['text']}"
        for item in source_segments)
    if not (args.run_dir / "analysis.json").exists():
        response_path = args.run_dir / "gemini-response.json"
        if response_path.exists():
            raw = read_json(response_path)
            from .gemini import interaction_text
            text = interaction_text(raw)
            actual_model = raw.get("model", "cached-response")
        else:
            uploaded = client.upload_or_reuse(source_dir / "source.mp4")
            save_json(args.run_dir / "gemini-file.json", uploaded)
            try:
                text, raw = client.interaction(analysis_prompt(meta, transcript), uploaded)
                actual_model = args.model
            except RuntimeError as exc:
                if "Gemini HTTP 429" not in str(exc) or not args.fallback_model:
                    raise
                client = Gemini(api_key_from(args.secrets), args.fallback_model)
                text, raw = client.interaction(analysis_prompt(meta, transcript), uploaded)
                actual_model = args.fallback_model
            save_json(response_path, raw)
        analysis = extract_json(text)
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
