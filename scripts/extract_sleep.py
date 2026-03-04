import csv
import xml.etree.ElementTree as ET
import os 
import sys 


SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"

def main(user_folder):
    INPUT_XML = os.path.join(user_folder, "export2.xml")
    OUT_CSV = os.path.join(user_folder, "sleep_records2.csv")
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

    print(f"Wrote {OUT_CSV}")

if __name__ == "__main__":
    user_folder = sys.argv[1]
    main(user_folder)

