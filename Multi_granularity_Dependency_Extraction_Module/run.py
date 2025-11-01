import os
import json
import zipfile
from pathlib import Path
from mprocess_utils import extract_functions_with_spans_tree_sitter, get_changed_functions_from_files_tree_sitter, build_dependency_trees

current_dir = Path(__file__).resolve().parent.parent

#Path to repos
REPOS_AFTER_ROOT = current_dir / "Raw_Data_Crawling" / "github" / "repos" 

#Path to repos_before
REPOS_BEFORE_ROOT = current_dir / "Raw_Data_Crawling" / "github" / "repos_before"

#Path to function output is stored
OUTPUT_PATH = current_dir / "Multi_granularity_Dependency_Extraction_Module" / "output" / "m_output.jsonl"

def build_function_level_info(year, month):
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        pass
    current_dir = Path(__file__).resolve().parent
    YM = f"{year}_{month}"

    #Construct paths
    before_root = Path(REPOS_BEFORE_ROOT) / YM
    after_root = Path(REPOS_AFTER_ROOT) / YM

    all_patches_json_path = current_dir / "prepared_input" / "module2_output.jsonl"
    all_patches = []

    #Load output of module 2
    all_patches_json = []
    with open(all_patches_json_path, 'r', encoding='utf-8') as f:
        for line in f:
            all_patches_json.append(json.loads(line))

    for patch in all_patches_json:
        commit_id_after = patch['commit_id']
        commit_id_before = patch['parents'][0]['commit_id_before']

        repo_after_path = Path(after_root) / f"{commit_id_after}.zip"
        repo_before_path = Path(before_root) / f"{commit_id_before}.zip"

        after_extract_dir = Path(after_root) / f"{commit_id_after}_after"
        before_extract_dir = Path(before_root) / f"{commit_id_before}_before"

        #Skip unzipping if already extracted, otherwise unzip the repo folders
        if not after_extract_dir.exists():
            after_extract_dir.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(repo_after_path, "r") as zip_ref:
                    zip_ref.extractall(after_extract_dir)
            except Exception as e:
                continue

        if not before_extract_dir.exists():
            before_extract_dir.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(repo_before_path, "r") as zip_ref:
                    zip_ref.extractall(before_extract_dir)
            except Exception as e:
                continue

        print(f"After: {commit_id_after}")
        print(f"Before: {commit_id_before}")
        #Store repo information, including the information of all functions changed between the before and after
        repo_info = {
            "repo_after": commit_id_after,
            "repo_before": commit_id_before,
            "functions_before": [],
            "functions_after": []
        }
        for root, _, files in os.walk(after_extract_dir):
            for file in files:
                #Get file path
                after_file = Path(root) / file
                rel_path = after_file.relative_to(after_extract_dir)
                parts = list(rel_path.parts)
                if len(parts) < 2:
                    continue

                #Get the repo path of the corresponding 'before' repo
                parts[0] = parts[0].replace(commit_id_after, commit_id_before)
                parts[1] = parts[1].replace(commit_id_after, commit_id_before)
                before_rel_path = Path(*parts)
                before_file = before_extract_dir / before_rel_path

                if not before_file.exists():
                    #Skip files introduced in fix
                    continue

                #Determine changed functions between the two files
                changed_funcs = get_changed_functions_from_files_tree_sitter(before_file, after_file, language='c')
                if not changed_funcs:
                    continue

                #Extract functions using tree-sitter
                before_all = extract_functions_with_spans_tree_sitter(before_file, language='c')
                after_all  = extract_functions_with_spans_tree_sitter(after_file, language='c')

                before_funcs = [f for f in before_all if f["name"] in changed_funcs]
                after_funcs  = [f for f in after_all  if f["name"] in changed_funcs]

                for f in before_funcs:
                    repo_info["functions_before"].append({
                        "name": f["name"],
                        "content": f["content"],
                        "file": str(before_file)
                    })

                for f in after_funcs:
                    repo_info["functions_after"].append({
                        "name": f["name"],
                        "content": f["content"],
                        "file": str(after_file)
                    })

                #Add dependency information (caller and callee) using cflow
                caller_tree_before, callee_tree_before = build_dependency_trees(before_extract_dir, repo_info["functions_before"], language='c')
                caller_tree_after, callee_tree_after = build_dependency_trees(after_extract_dir, repo_info["functions_after"], language='c')

                for f in repo_info["functions_before"]:
                    fname = f["name"]
                    f["callees"] = caller_tree_before.get(fname, [])
                    f["callers"] = callee_tree_before.get(fname, [])

                for f in repo_info["functions_after"]:
                    fname = f["name"]
                    f["callees"] = caller_tree_after.get(fname, [])
                    f["callers"] = callee_tree_after.get(fname, [])

                #Store overall tree (can be removed)
                repo_info["callerTree_before"] = caller_tree_before
                repo_info["calleeTree_before"] = callee_tree_before
                repo_info["callerTree_after"] = caller_tree_after
                repo_info["calleeTree_after"] = callee_tree_after

        #Write all information to final output file
        if repo_info["functions_before"] or repo_info["functions_after"]:
            with open(OUTPUT_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(repo_info) + "\n")
            all_patches.append(repo_info)

    return all_patches

def add_to_dataset():
    #Load original dataset
    original_path = current_dir / "Multi_granularity_Dependency_Extraction_Module" / "prepared_input" / "module2_output.jsonl"
    with open(original_path, "r", encoding="utf-8") as f:
        original_entries = [json.loads(line) for line in f]

    #Load out extracted functions
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        new_entries = [json.loads(line) for line in f]

    #Merge information based on commit id
    commit_to_functions = {e["repo_before"]: e for e in new_entries}

    for entry in original_entries:
        cid = entry.get("commit_id")
        if cid in commit_to_functions:
            funcs_entry = commit_to_functions[cid]
            entry["functions_before"] = funcs_entry.get("functions_before", [])
            entry["functions_after"] = funcs_entry.get("functions_after", [])

    with open("output/module3_output.jsonl", "w", encoding="utf-8") as f:
        for e in original_entries:
            f.write(json.dumps(e) + "\n")

def main(Years=['2016'], Months=['8']):
    for year in Years:
        for month in Months:
            build_function_level_info(year, month)
            add_to_dataset()
