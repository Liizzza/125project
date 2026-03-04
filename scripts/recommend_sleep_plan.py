import json
import subprocess
from pathlib import Path
from datetime import datetime
import os

# Multi-user: API injects USER_DATA_DIR per user. Falls back to "data/" for manual runs.
DATA_DIR = Path(os.environ.get("USER_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

MAKE_SLEEP_PLAN_SCRIPT = "scripts/make_sleep_plan.py"
PLAN_JSON = DATA_DIR / "tonight_plan.json"


def fmt_time(mins: int) -> str:
    mins = int(mins) % 1440
    h = mins // 60
    m = mins % 60
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{m:02d} {ampm}"


def minutes_from_midnight(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def main():
    # Step 1: regenerate plan (passes USER_DATA_DIR through to make_sleep_plan.py)
    print(f"Running {MAKE_SLEEP_PLAN_SCRIPT} ...")
    env = os.environ.copy()
    env["USER_DATA_DIR"] = str(DATA_DIR)
    subprocess.run(["python3", MAKE_SLEEP_PLAN_SCRIPT], check=True, env=env)

    # Step 2: load plan
    if not PLAN_JSON.exists():
        raise FileNotFoundError(f"Expected plan file not found: {PLAN_JSON}")

    plan = json.loads(PLAN_JSON.read_text())

    now     = datetime.now()
    now_min = minutes_from_midnight(now)

    bed             = int(plan["bedtime_min"])
    wake            = int(plan["wake_min"])
    mins_until_bed  = (bed - now_min) % 1440
    mins_until_wake = (wake - now_min) % 1440

    print("\n=== Tonight's Best Plan ===")
    print("Generated at:", plan.get("generated_at"))
    print("Now:", now)
    print(f"Bedtime: {fmt_time(bed)}  (in {mins_until_bed} min)")
    print(f"Wake:    {fmt_time(wake)}  (in {mins_until_wake} min)")
    print("Sleep opportunity:", plan.get("sleep_opportunity_min"), "min")
    print("Desired sleep:",     plan.get("desired_sleep_min"), "min")
    print("Debt:",              plan.get("debt_min"), "min")

    stage_b       = 45
    stage_b_start = max(0, mins_until_bed - stage_b)

    print("\n=== Content Timing Windows ===")
    print(f"Stage A: now → {stage_b_start} min before bed (longer wind-down content ok)")
    print(f"Stage B: last {stage_b} min before bed (short content only)")

    why = plan.get("why")
    if why:
        print("\n=== Why this plan won ===")
        print(why)

    # Uncomment to also run content recommendations:
    # subprocess.run(["python3", "scripts/recommend_content.py"], check=True, env=env)


if __name__ == "__main__":
    main()