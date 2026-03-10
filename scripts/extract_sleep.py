import csv
import xml.etree.ElementTree as ET
import os
from pathlib import Path

# Multi-user: API injects USER_DATA_DIR per user. Falls back to "data/" for manual runs.
DATA_DIR = Path(os.environ.get("USER_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

INPUT_XML = str(DATA_DIR / "export.xml")
OUT_CSV   = str(DATA_DIR / "sleep_records.csv")

SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"


def main():
    print(f"DEBUG: Reading from {INPUT_XML}")
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["sourceName", "creationDate", "startDate", "endDate", "value"]
        )
        writer.writeheader()
        for _, elem in ET.iterparse(INPUT_XML, events=("end",)):
            if elem.tag == "Record" and elem.attrib.get("type") == SLEEP_TYPE:
                writer.writerow({
                    "sourceName":   elem.attrib.get("sourceName", ""),
                    "creationDate": elem.attrib.get("creationDate", ""),
                    "startDate":    elem.attrib.get("startDate", ""),
                    "endDate":      elem.attrib.get("endDate", ""),
                    "value":        elem.attrib.get("value", ""),
                })
                elem.clear()
    print(f"Wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
