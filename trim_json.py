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

if __name__ == "__main__":
    jsonl_files = [
        "Vulnerability_Untangling_Module//static//new_output//semgrep_3//merge_C_new.jsonl",
        "Vulnerability_Untangling_Module//static//new_output//llm//merge_C.jsonl",
        "Vulnerability_Untangling_Module//static//new_output//flawfinder_1//merge_C_new.jsonl",
        "Vulnerability_Untangling_Module//static//new_output//cppcheck_4//merge_C_new.jsonl",
        "Raw_Data_Crawling//github//results//2016_8.jsonl",
        "Raw_Data_Crawling//github//rawcode_result//2016_8_rawcode.jsonl",
        "Raw_Data_Crawling//github//merge_result_new//time//merge_2016_8.jsonl",
        "Raw_Data_Crawling//github//merge_result_new//language//merge_C.jsonl",
        "Raw_Data_Crawling//github//crawl_result_new//2016_8_patch.jsonl",
        "Multi-granularity_Dependency_Extraction_Module//prepared_input//output_c.jsonl",
        "Multi-granularity_Dependency_Extraction_Module//output//output_c.jsonl"
    ]

    trim_jsonl_files(jsonl_files, limit=50)
