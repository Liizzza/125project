import json
import subprocess
from pathlib import Path
from datetime import datetime
import os 
import sys 
# ---- Choose user by changing these two ----
MAKE_SLEEP_PLAN_SCRIPT = "scripts/make_sleep_plan.py"
PLAN_JSON = os.path.join(sys.argv[1], "tonight_plan.json")
# ------------------------------------------

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
    # Step 1: regenerate plan artifact (tonight_plan2.json)
    print(f"Running {MAKE_SLEEP_PLAN_SCRIPT} ...")
    subprocess.run(["python", MAKE_SLEEP_PLAN_SCRIPT], check=True)

    # Step 2: load plan artifact
    if not PLAN_JSON.exists():
        raise FileNotFoundError(f"Expected plan file not found: {PLAN_JSON}")

    plan = json.loads(PLAN_JSON.read_text())

    now = datetime.now()
    now_min = minutes_from_midnight(now)

    bed = int(plan["bedtime_min"])
    wake = int(plan["wake_min"])
    mins_until_bed = (bed - now_min) % 1440
    mins_until_wake = (wake - now_min) % 1440

    print("\n=== Tonight’s Best Plan (from plan artifact) ===")
    print("Generated at:", plan.get("generated_at"))
    print("Now:", now)
    print(f"Bedtime: {fmt_time(bed)}  (in {mins_until_bed} min)")
    print(f"Wake:    {fmt_time(wake)}  (in {mins_until_wake} min)")
    print("Sleep opportunity:", plan.get("sleep_opportunity_min"), "min")
    print("Desired sleep:", plan.get("desired_sleep_min"), "min")
    print("Debt:", plan.get("debt_min"), "min")

    # Optional: show stage timing for content
    stage_b = 45  # last 45 minutes before bed
    stage_a_start = mins_until_bed
    stage_b_start = max(0, mins_until_bed - stage_b)

    print("\n=== Content Timing Windows ===")
    print(f"Stage A: now → {stage_b_start} min before bed (longer wind-down content ok)")
    print(f"Stage B: last {stage_b} min before bed (short content only)")

    # Optional: print the “why”
    why = plan.get("why")
    if why:
        print("\n=== Why this plan won ===")
        print(why)

    # Optional next step: run recommend_content.py (uncomment if you want)
    # subprocess.run(["python", "scripts/recommend_content.py"], check=True)

if __name__ == "__main__":
    main()
