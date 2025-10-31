import json
from pathlib import Path

def trim_jsonl_files(jsonl_files, limit=50):
    """
    Trim JSON files by keeping only 'limit' entries and removing the 'code' key
    """
    for file_path in jsonl_files:
        file_path = Path(file_path)
        if not file_path.exists():
            print(f"{file_path} does not exist")
            continue

        #Read JSON file
        trimmed_entries = []
        with open(file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break
                try:
                    obj = json.loads(line)

                    #Remove code
                    obj.pop("code", None)

                    if isinstance(obj.get("details"), dict):
                        obj["details"].pop("code", None)

                    details = obj.get("details")
                    if isinstance(details, list):
                        for item in details:
                            if isinstance(item, dict):
                                item.pop("code", None)

                    obj.pop("code_before", None)
                    
                    if isinstance(obj.get("details"), dict):
                        obj["details"].pop("code_before", None)

                    details = obj.get("details")
                    if isinstance(details, list):
                        for item in details:
                            if isinstance(item, dict):
                                item.pop("code_before", None)

                    trimmed_entries.append(obj)
                except json.JSONDecodeError:
                    continue

        #Write to new file
        output_file = file_path.with_name(f"{file_path.stem}_trimmed.jsonl")
        with open(output_file, "w", encoding="utf-8") as f_out:
            for obj in trimmed_entries:
                json.dump(obj, f_out, ensure_ascii=False)
                f_out.write("\n")

jsonl_files = [
    
]

trim_jsonl_files(jsonl_files, limit=50)