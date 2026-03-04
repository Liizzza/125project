import json
import subprocess
from pathlib import Path
from datetime import datetime
import os

# Multi-user: API injects USER_DATA_DIR per user. Falls back to "data/" for manual runs.
DATA_DIR = Path(os.environ.get("USER_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

MAKE_SLEEP_PLAN_SCRIPT   = "scripts/make_sleep_plan.py"
RECOMMEND_CONTENT_SCRIPT = "scripts/recommend_content.py"

PLAN_JSON    = DATA_DIR / "tonight_plan.json"
CONTENT_JSON = DATA_DIR / "tonight_content.json"
BUNDLE_OUT   = DATA_DIR / "tonight_bundle.json"

STAGE_B_MIN          = 45
STAGE_B_MAX_DURATION = 12
STAGE_B_MAX_INTENSITY = 0.18


def fmt_time(mins: int) -> str:
    mins = int(mins) % 1440
    h = mins // 60
    m = mins % 60
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ampm}"


def minutes_from_midnight(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def minutes_until(now_min: int, t_min: int) -> int:
    return int((t_min - now_min) % 1440)


def build_stages(plan: dict, content: dict) -> dict:
    now     = datetime.now()
    now_min = minutes_from_midnight(now)

    bed   = int(plan["bedtime_min"])
    wake  = int(plan["wake_min"])
    until_bed = minutes_until(now_min, bed)

    stage_b_start_min = (bed - STAGE_B_MIN) % 1440
    recs = content.get("recommendations", []) or []

    strict_b = []
    soft_b   = []
    for r in recs:
        try:
            dur   = float(r.get("durationMin", 10))
            inten = float(r.get("intensity", 1))
        except Exception:
            continue
        if dur <= STAGE_B_MAX_DURATION and inten <= STAGE_B_MAX_INTENSITY:
            strict_b.append(r)
        if dur <= 15 and inten <= 0.25:
            soft_b.append(r)

    stage_b = strict_b[:5]
    if len(stage_b) < 3:
        used = {x.get("url") for x in stage_b if x.get("url")}
        for r in soft_b:
            if r.get("url") not in used:
                stage_b.append(r)
                used.add(r.get("url"))
            if len(stage_b) >= 5:
                break

    stage_b_urls = {r.get("url") for r in stage_b if r.get("url")}
    stage_a = [r for r in recs if r.get("url") not in stage_b_urls][:7]

    return {
        "now_iso":            now.isoformat(),
        "now_min":            now_min,
        "bedtime_min":        bed,
        "wake_min":           wake,
        "mins_until_bedtime": until_bed,
        "stage_a": {
            "label":           "Stage A (now → 45 min before bed)",
            "window":          {"start_min": now_min, "end_min": stage_b_start_min},
            "recommendations": stage_a,
        },
        "stage_b": {
            "label":   f"Stage B (last {STAGE_B_MIN} min before bed)",
            "window":  {"start_min": stage_b_start_min, "end_min": bed},
            "filters": {
                "strict":   {"max_duration_min": STAGE_B_MAX_DURATION, "max_intensity": STAGE_B_MAX_INTENSITY},
                "fallback": {"max_duration_min": 15, "max_intensity": 0.25},
            },
            "recommendations": stage_b,
        },
    }


def main():
    # Forward USER_DATA_DIR to child scripts
    env = os.environ.copy()
    env["USER_DATA_DIR"] = str(DATA_DIR)

    print(f"Running {MAKE_SLEEP_PLAN_SCRIPT} ...")
    subprocess.run(["python3", MAKE_SLEEP_PLAN_SCRIPT], check=True, env=env)

    print(f"\nRunning {RECOMMEND_CONTENT_SCRIPT} ...")
    subprocess.run(["python3", RECOMMEND_CONTENT_SCRIPT], check=True, env=env)

    if not PLAN_JSON.exists():
        raise FileNotFoundError(f"Missing plan file: {PLAN_JSON}")
    if not CONTENT_JSON.exists():
        raise FileNotFoundError(f"Missing content file: {CONTENT_JSON}")

    plan    = json.loads(PLAN_JSON.read_text())
    content = json.loads(CONTENT_JSON.read_text())
    stages  = build_stages(plan, content)

    bundle = {
        "generated_at": datetime.now().isoformat(),
        "plan":         plan,
        "content":      content,
        "stages":       stages,
    }

    BUNDLE_OUT.write_text(json.dumps(bundle, indent=2))
    print(f"\nWrote bundle → {BUNDLE_OUT}")

    bed  = int(plan["bedtime_min"])
    wake = int(plan["wake_min"])
    print("\n=== Tonight (Bundle Summary) ===")
    print(f"Bed:  {fmt_time(bed)}")
    print(f"Wake: {fmt_time(wake)}")

    print("\nStage A picks:")
    for rec in stages["stage_a"]["recommendations"][:5]:
        print(f"  - {rec['title']} ({rec['durationMin']} min) → {rec['url']}")

    print("\nStage B picks (short + very gentle):")
    for rec in stages["stage_b"]["recommendations"][:5]:
        print(f"  - {rec['title']} ({rec['durationMin']} min) → {rec['url']}")


if __name__ == "__main__":
    main()