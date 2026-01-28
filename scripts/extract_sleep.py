import csv
import xml.etree.ElementTree as ET

INPUT_XML = "export.xml"
OUT_CSV = "sleep_records.csv"
SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"

def main():
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["sourceName", "creationDate", "startDate", "endDate", "value"]
        )
        writer.writeheader()

        for _, elem in ET.iterparse(INPUT_XML, events=("end",)):
            if elem.tag == "Record" and elem.attrib.get("type") == SLEEP_TYPE:
                writer.writerow({
                    "sourceName": elem.attrib.get("sourceName", ""),
                    "creationDate": elem.attrib.get("creationDate", ""),
                    "startDate": elem.attrib.get("startDate", ""),
                    "endDate": elem.attrib.get("endDate", ""),
                    "value": elem.attrib.get("value", ""),
                })
                elem.clear()

if __name__ == "__main__":
    main()
