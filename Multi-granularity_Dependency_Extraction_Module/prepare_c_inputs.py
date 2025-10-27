import os
import json
import zipfile
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def get_files_before_path(publish_date: str):
    """Convert publish_date like 'August 7, 2016' to '2016_8'"""
    try:
        dt = datetime.strptime(publish_date, "%B %d, %Y")
        return f"{dt.year}_{dt.month}"
    except Exception:
        return None

project_root = Path(__file__).resolve().parents[1]

module2_files = [
    project_root / "Vulnerability_Untangling_Module" / "static" / "new_output" / "cppcheck_4" / "merge_C_new.jsonl",
    project_root / "Vulnerability_Untangling_Module" / "static" / "new_output" / "flawfinder_1" / "merge_C_new.jsonl",
    project_root / "Vulnerability_Untangling_Module" / "static" / "new_output" / "semgrep_3" / "merge_C_new.jsonl",
    project_root / "Vulnerability_Untangling_Module" / "static" / "new_output" / "llm" / "merge_C.jsonl"
]

base_dir = project_root / "Multi-granularity_Dependency_Extraction_Module"
prepared_dir = base_dir / "prepared_input"
repos_before_dir = prepared_dir / "repos_before"
output_jsonl = prepared_dir / "output_c.jsonl"

files_before_root = project_root / "Raw_Data_Crawling" / "github" / "files_before"
rawcode_root = project_root / "Raw_Data_Crawling" / "github" / "rawcode_result"

os.makedirs(repos_before_dir, exist_ok=True)

#Merge module 2 outputs
import os
import json

merged_entries = []

for file_path in module2_files:
    if not os.path.exists(file_path):
        continue

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            #Fix details
            if "details" in data and isinstance(data["details"], list):
                for detail in data["details"]:
                    if not isinstance(detail, dict):
                        continue

                    #Fix name
                    if "llm_check_new1" in detail:
                        llm_value = detail.pop("llm_check_new1")

                        #Convert string to boolean
                        if isinstance(llm_value, str):
                            llm_value_upper = llm_value.strip().upper()
                            if llm_value_upper == "YES":
                                llm_value = True
                            elif llm_value_upper in ("NO", "UNCERTAIN"):
                                llm_value = False
                        detail["llm_check"] = llm_value

                    #Merge static results
                    if "static" in detail and isinstance(detail["static"], dict):
                        static = detail["static"]
                        static_check = 1 if any(
                            isinstance(v, list) and len(v) > 0 and v[0] is True
                            for v in static.values()
                        ) else 0
                        detail["static_check"] = static_check

            merged_entries.append(json.dumps(data, ensure_ascii=False))

#Write merged output
with open(output_jsonl, 'w', encoding='utf-8') as out:
    for line in merged_entries:
        out.write(line + '\n')


#Zip files by commit ID
missing_files = []
created_zips = 0

for line in merged_entries:
    try:
        data = json.loads(line)
        publish_date = data.get("publish_date", "")
        subdir = get_files_before_path(publish_date)
        if not subdir:
            continue

        commit_id_before = data.get("parents", [{}])[0].get("commit_id_before")
        if not commit_id_before:
            continue

        zip_dir = repos_before_dir / subdir
        os.makedirs(zip_dir, exist_ok=True)
        zip_path = zip_dir / f"{commit_id_before}.zip"

        files_to_zip = []
        for detail in data.get("details", []):
            file_path_str = detail.get("file_path")
            if not file_path_str:
                continue

            file_id = Path(file_path_str).name
            candidate_file = files_before_root / subdir / file_id
            if candidate_file.exists():
                files_to_zip.append(candidate_file)
            else:
                missing_files.append(str(candidate_file))
        if files_to_zip:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                folder_name = commit_id_before
                for file in files_to_zip:
                    zipf.write(file, arcname=os.path.join(folder_name, f"{file.name}.c"))
            created_zips += 1

    except Exception:
        continue

if missing_files:
    with open(prepared_dir / "missing_files.txt", "w", encoding='utf-8') as mf:
        mf.write("\n".join(missing_files))

print(f"Output JSONL: {output_jsonl}")
print(f"repos_before directory: {repos_before_dir}")

#Create empty file
function_db_path = prepared_dir / "ReposVul_function_c.jsonl"
if not function_db_path.exists():
    with open(function_db_path, 'w', encoding='utf-8') as fdb:
        pass