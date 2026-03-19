import csv
import xml.etree.ElementTree as ET
import os
from pathlib import Path
from datetime import datetime, timedelta

# Multi-user: API injects USER_DATA_DIR per user. Falls back to "data/" for manual runs.
DATA_DIR = Path(os.environ.get("USER_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

INPUT_XML = str(DATA_DIR / "export.xml")
OUT_CSV   = str(DATA_DIR / "sleep_records.csv")

SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"

def main():
    print(f"DEBUG: Reading from {INPUT_XML}")
    
    # Define the cutoff date (30 days ago from today)
    cutoff_date = datetime.now() - timedelta(days=365)
    print(f"DEBUG: Filtering records newer than {cutoff_date.strftime('%Y-%m-%d')}")

    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["sourceName", "creationDate", "startDate", "endDate", "value"]
        )
        writer.writeheader()
        
        count = 0
        skipped = 0
        
        try:
            # We use iterparse for memory efficiency
            context = ET.iterparse(INPUT_XML, events=("end",))
            
            for _, elem in context:
                if elem.tag == "Record" and elem.attrib.get("type") == SLEEP_TYPE:
                    start_date_str = elem.attrib.get("startDate", "")
                    
                    # FILTER LOGIC
                    try:
                        # Apple dates: '2024-03-10 22:30:00 -0700'
                        # We extract the YYYY-MM-DD part
                        record_date = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
                        
                        if record_date < cutoff_date:
                            skipped += 1
                            elem.clear()
                            continue
                    except Exception:
                        # If date parsing fails, we skip just in case
                        elem.clear()
                        continue

                    # If it passes the filter, write it
                    writer.writerow({
                        "sourceName":   elem.attrib.get("sourceName", ""),
                        "creationDate": elem.attrib.get("creationDate", ""),
                        "startDate":    elem.attrib.get("startDate", ""),
                        "endDate":      elem.attrib.get("endDate", ""),
                        "value":        elem.attrib.get("value", ""),
                    })
                    count += 1
                
                # Clear element from memory
                elem.clear()
                
        except ET.ParseError as e:
            print(f"⚠️ Warning: XML was truncated, but we saved what we could. Error: {e}")

    print(f"✅ Wrote {count} recent records to {OUT_CSV} (Skipped {skipped} old records)")

if __name__ == "__main__":
    main()
