from pathlib import Path
import subprocess
import os
import json
import git
import time
from itertools import groupby
import re
from datetime import datetime

#Make required folders if missing
for folder in [
    "windows",
    "repos_now",
    "crawl_result_new2",
    "crawl_result_new3",
    "crawl_result_new4",
    "crawl_result_last"
]:
    os.makedirs(folder, exist_ok=True)

def clone_github_repo(repo_url, local_path):
    # print(local_path)
    git.Repo.clone_from(repo_url, local_path)
    time.sleep(5)

def git_log(local_path, date, commit_id):
    after_cmd = [
        "git", "log",
        f"--since={date}", "--reverse",
        "--pretty=format:%H - %ad : %s",
        "--name-only"
    ]
    before_cmd = [
        "git", "log",
        f"--before={date}",
        "--pretty=format:%H - %ad : %s",
        "--name-only"
    ]

    after_output = subprocess.run(after_cmd, cwd=local_path, capture_output=True, text=True, encoding="utf-8", errors="replace")
    with open(os.path.join("windows", f"{commit_id}_after.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(after_output.stdout.splitlines()[:200]))

    before_output = subprocess.run(before_cmd, cwd=local_path, capture_output=True, text=True, encoding="utf-8", errors="replace")
    with open(os.path.join("windows", f"{commit_id}_before.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(before_output.stdout.splitlines()[:200]))
    
def add_message(Year, Month):

    YM = Year+'_'+Month
    print(YM)
    current_dir = Path(__file__).resolve().parent.parent.parent
    crawl_name = current_dir / 'Raw_Data_Crawling//github//crawl_result' / f"{YM}_patch.jsonl"

    dir_path_new = './/crawl_result_new2//'
    crawl_name_new = dir_path_new + YM + '_patch.jsonl'

    fetchs = []
    if not os.path.exists(crawl_name):
        return

    with open(crawl_name, "r", encoding="utf-8") as f:
        content = json.load(f)

        for i in range(len(content)):
            url = content[i]['url']
            date = content[i]['commit_date']
            commit_id = content[i]['commit_id']

            record = content[i]
            record['commit_id'] = commit_id
            path_before = os.path.join("windows", f"{commit_id}_before.txt")
            path_after = os.path.join("windows", f"{commit_id}_after.txt")

            if os.path.exists(path_before) and os.path.exists(path_after):
                with open(path_before, 'r', encoding='utf-8') as file:
                    content_before = file.read()
                    record['windows_before'] = content_before
                with open(path_after, 'r', encoding='utf-8') as file:
                    content_after = file.read() 
                    record['windows_after'] = content_after
                fetchs.append(record)
                continue

            local_path = './repos_now/' + url.partition('/repos/')[2].partition('/commits/')[0].replace('/','_')
            download_url = 'https://github.com/' + url.partition('/repos/')[2].partition('/commits/')[0] + '.git'

            if not os.path.exists(local_path):
                try:
                    clone_github_repo(download_url, local_path)
                except Exception as e:
                    print(e)
                    continue

            git_log(local_path, date, commit_id)

            with open(path_before, 'r', encoding='utf-8') as file:
                content_before = file.read()
                record['windows_before'] = content_before
            with open(path_after, 'r', encoding='utf-8') as file:
                content_after = file.read() 
                record['windows_after'] = content_after
            fetchs.append(record)

    with open(crawl_name_new, "w", encoding = "utf-8") as rf:
        rf.write(json.dumps(fetchs, indent=4, separators=(',', ': ')))

def add_message_1(Year, Month):

    YM = Year+'_'+Month
    print(YM)
    dir_path = './crawl_result_new2/'
    crawl_name = dir_path + YM + '_patch.jsonl'

    dir_path_new = './crawl_result_new3/'
    crawl_name_new = dir_path_new + YM + '_patch.jsonl'

    fetchs = []
    if not os.path.exists(crawl_name):
        return

    with open(crawl_name, "r", encoding="utf-8") as f:
        content = json.load(f)
        for i in range(len(content)):
            commit_id_now = content[i]['commit_id']
            windows_before = content[i]['windows_before']
            windows_after = content[i]['windows_after']

            windows_before_split = windows_before.replace('\r\n', '\n').split('\n')
            windows_after_split = windows_after.replace('\r\n', '\n').split('\n')
            
            windows = []
            groups = [list(group) for key, group in groupby(windows_before_split, key=lambda x: x == '') if not key]
            for group in groups:
                window = {}
                commit_detail = group[0]
                pattern = re.compile(r'(?P<id>[a-f0-9]+) - (?P<date>.*?) : (?P<message>.*)')
                match = pattern.match(commit_detail)
                commit_id = match.group('id')
                if str(commit_id.strip()) == str(commit_id_now.strip()):
                    continue
                commit_date = match.group('date')
                commit_message = match.group('message')
                group.pop(0)
                window['commit_id'] = commit_id
                window['commit_date'] = commit_date
                window['commit_message'] = commit_message
                window['files_name'] = group
                windows.append(window)
            content[i]['windows_before'] = windows

            windows = []    
            groups = [list(group) for key, group in groupby(windows_after_split, key=lambda x: x == '') if not key]
            for group in groups:
                window = {}
                commit_detail = group[0]
                pattern = re.compile(r'(?P<id>[a-f0-9]+) - (?P<date>.*?) : (?P<message>.*)')
                match = pattern.match(commit_detail)
                commit_id = match.group('id')
                if str(commit_id.strip()) == str(commit_id_now.strip()):
                    continue
                commit_date = match.group('date')
                commit_message = match.group('message')
                group.pop(0)
                window['commit_id'] = commit_id
                window['commit_date'] = commit_date
                window['commit_message'] = commit_message
                window['files_name'] = group
                windows.append(window)
            content[i]['windows_after'] = windows
            fetchs.append(content[i])

    with open(crawl_name_new, "w", encoding = "utf-8") as rf:
        rf.write(json.dumps(fetchs, indent=4, separators=(',', ': ')))

def find(filename, windows, num):
    for i in range(num):
        if i >= len(windows):
            return 0
        filenames = windows[i]['files_name']
        for each in filenames:
            if filename == each:
                return 1
    return 0

def add_message_2(Year, Month):

    YM = Year+'_'+Month
    print(YM)
    dir_path = './crawl_result_new2/'
    crawl_name = dir_path + YM + '_patch.jsonl'

    dir_path_new = './crawl_result_new3/'
    crawl_name_new = dir_path_new + YM + '_patch.jsonl'

    dir_path_new1 = './crawl_result_new4/'
    crawl_name_new1 = dir_path_new1 + YM + '_patch.jsonl'
    fetchs = []
    if not os.path.exists(crawl_name_new):
        return

    with open(crawl_name_new, "r", encoding="utf-8") as f:
        content = json.load(f)
        for i in range(len(content)):
            record = content[i]
            windows_before = record['windows_before']
            windows_after = record['windows_after']

            for j in range(len(record['files'])):
                filename = record['files'][j]['filename']
                record['files'][j]['outdated_file_before'] = find(filename, windows_before, 3)
                record['files'][j]['outdated_file_after'] = find(filename, windows_after, 3)
            fetchs.append(record)


    with open(crawl_name_new1, "w", encoding = "utf-8") as rf:
        rf.write(json.dumps(fetchs, indent=4, separators=(',', ': ')))

def get_alldate():
    Years = [str(year) for year in range(2001, 2024)]
    Months = [str(i) for i in range(1, 13)]
    dict_date = {}
    for Year in Years:
        for Month in Months:
            YM = Year+'_'+Month
            print(YM)
            dir_path = './crawl_result_new4/'
            crawl_name = dir_path + YM + '_patch.jsonl'
            if not os.path.exists(crawl_name):
                continue
            with open(crawl_name, "r", encoding="utf-8") as f:
                content = json.load(f)
                for i in range(len(content)):
                    record = content[i]
                    date = record['commit_date']
                    date = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    for j in range(len(record['files'])):
                        filename = record['files'][j]['filename']
                        if filename in dict_date:
                            dict_date[filename] = max(dict_date[filename], date)
                        else:
                            dict_date[filename] = date
    return dict_date

def add_message_3(Year, Month, dict_date):

    YM = Year+'_'+Month
    print(YM)

    dir_path = './crawl_result_new4/'
    crawl_name = dir_path + YM + '_patch.jsonl'

    if not os.path.exists(crawl_name):
        print(crawl_name)
        return

    fetchs = []

    with open(crawl_name, "r", encoding="utf-8") as f:
        content = json.load(f)
        for i in range(len(content)):
            record = content[i]
            date = record['commit_date']
            date = datetime.fromisoformat(date.replace('Z', '+00:00'))
            for j in range(len(record['files'])):
                filename = record['files'][j]['filename']
                if filename not in dict_date:
                    record['files'][j]['outdated_file_modify'] = 0
                elif date < dict_date[filename]:
                    record['files'][j]['outdated_file_modify'] = 1
                else:
                    record['files'][j]['outdated_file_modify'] = 0
            fetchs.append(record)

    dir_path_new = './crawl_result_last/'
    crawl_name_new = dir_path_new + YM + '_patch.jsonl'
    with open(crawl_name_new, "w", encoding = "utf-8") as rf:
        rf.write(json.dumps(fetchs, indent=4, separators=(',', ': ')))

def outdated_window(CVEs):
    
    file_suffix = [ 
                    'po',
                    # 'pm',
                    'toml',
                    'lock',
                    'tests/TESTLIST',
                    # 'erb',
                    'inc',
                    'svg',
                    'rst',
                    'out',
                    'ChangeLog',
                    # 'tpl',
                    'txt',
                    'json',
                    'md',
                    'CHANGELOG',
                    'CHANGES',
                    'CHANGELOG',
                    'misc/CHANGELOG',

                    'yml',
                    'yaml',
                    'css',
                    'sh',
                    'vim',
                   ]

    for CVE in CVEs:
        for i,detail in enumerate(CVE['details']):
            windows_before = CVE['windows_before']
            windows_after = CVE['windows_after']
            filename = detail['file_name']
            CVE['details'][i]['outdated_file_before'] = find(filename, windows_before, 1)
            CVE['details'][i]['outdated_file_after'] = find(filename, windows_after, 1)

    for CVE in CVEs:
        CVE['outdated_precise'] = 0
        for i,detail in enumerate(CVE['details']):
            if 'file_language' in detail:
                if detail['file_language'] not in file_suffix:
                    if detail['outdated_file_modify'] == 1 and (detail['outdated_file_before'] == 1 or detail['outdated_file_after'] == 1):
                        CVE['outdated_precise'] = 1
                        break
    
    return CVEs

def integrate_module4_results(Year, Month):
    """
    Integrate Module 4's crawl_result_4 output with Module 3's enriched dataset.

    Expected paths:
      - Module 3 output:   Multi-granularity_Dependency_Extraction_Module/output/output_c_final.jsonl
      - Module 4 output:   Trace-based_Filtering_Module/github/crawl_result_4.jsonl
      - Repos folder:      Raw_Data_Crawling/github/repos
    Output:
      - merged_module3_module4.jsonl in the same directory as crawl_result_4
    """

    base_path = Path(__file__).resolve().parent.parent.parent
    YM = Year+'_'+Month

    module3_path = base_path / "Multi-granularity_Dependency_Extraction_Module" / "output" / "output_c_final.jsonl"
    module4_path = base_path / "Trace-based_Filtering_Module" / "github" / "crawl_result_new4" / f"{YM}_patch.jsonl"
    output_path  = base_path / "Trace-based_Filtering_Module" / "github" / "module4_output_final.jsonl"

    # --- Load Module 3 dataset ---
    with open(module3_path, "r", encoding="utf-8") as f3:
        module3_data = [json.loads(line) for line in f3 if line.strip()]

    # --- Load Module 4 dataset ---
    with open(module4_path, "r", encoding="utf-8") as f4:
        first_char = f4.read(1)
        f4.seek(0)
        if first_char == "[":
            module4_data = json.load(f4)  # full JSON array
        else:
            module4_data = [json.loads(line) for line in f4 if line.strip()]

    # --- Build a map from commit_id -> Module 4 entry ---
    module4_map = {entry.get("commit_id"): entry for entry in module4_data}

    print(f"Loaded {len(module3_data)} Module 3 entries")
    print(f"Loaded {len(module4_data)} Module 4 entries")

    merged_data = []
    missing_count = 0

    for entry in module3_data:
        commit_id = entry.get("commit_id")

        if commit_id in module4_map:
            module4_entry = module4_map[commit_id]

            # Merge only window-related fields
            entry["windows_before"] = module4_entry.get("windows_before", "")
            entry["windows_after"]  = module4_entry.get("windows_after", "")

            # Optionally merge any additional stats (if present)
            for key in ["func_before", "func_after", "lines_changed"]:
                if key in module4_entry:
                    entry[key] = module4_entry[key]
        else:
            missing_count += 1

        merged_data.append(entry)

    # --- Save final merged output ---
    with open(output_path, "w", encoding="utf-8") as fout:
        for record in merged_data:
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Dataset saved to: {output_path}")
    
def main():

    Years = [str(year) for year in range(2001, 2024)]
    Years = ["2016"]
    Months = [str(i) for i in range(1, 13)]
    Months = ["8"]
    
    for Year in Years:
        for Month in Months:
            integrate_module4_results(Year, Month)

    return
    for Year in Years:
        for Month in Months:
            add_message(Year, Month)

    for Year in Years:
        for Month in Months:
            add_message_1(Year, Month)
    
    for Year in Years:
        for Month in Months:
            add_message_2(Year, Month)
    
    dict_date = get_alldate()
    
    for Year in Years:
        for Month in Months:
            add_message_3(Year, Month, dict_date)


if __name__ == "__main__":
    main()
    