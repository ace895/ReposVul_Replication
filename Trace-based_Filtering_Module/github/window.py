from pathlib import Path
import subprocess
import os
import json
import git
import time
from itertools import groupby
import re
from datetime import datetime

#Create required folders if they do not exist
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
    """
    Clone a GitHub repository to a local path.

    Parameters:
        repo_url: URL of the GitHub repository
        local_path: Local folder path to clone the repository into
    """
    git.Repo.clone_from(repo_url, local_path)
    time.sleep(5)  #Wait 5 seconds to avoid rate-limits

def git_log(local_path, date, commit_id):
    """
    Extract Git commit logs before and after a given date and save them to files.

    Parameters:
        local_path: Local path to the Git repository
        date: Date to filter commits
        commit_id: Commit identifier used for naming output files

    Output files:
        windows/<commit_id>_before.txt
        windows/<commit_id>_after.txt
    """
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

    #Save recent commits after the date
    after_output = subprocess.run(after_cmd, cwd=local_path, capture_output=True, text=True, encoding="utf-8", errors="replace")
    with open(os.path.join("windows", f"{commit_id}_after.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(after_output.stdout.splitlines()[:200]))

    #Save older commits before the date
    before_output = subprocess.run(before_cmd, cwd=local_path, capture_output=True, text=True, encoding="utf-8", errors="replace")
    with open(os.path.join("windows", f"{commit_id}_before.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(before_output.stdout.splitlines()[:200]))
    
def add_message(Year, Month):
    """
    Enrich patch data with the corresponding Git logs (before/after) for each commit.

    Input files:
        Raw_Data_Crawling/github/crawl_result/<Year>_<Month>_patch.jsonl

    Output files:
        crawl_result_new2/<Year>_<Month>_patch.jsonl
    """
    YM = Year+'_'+Month
    print(YM)
    current_dir = Path(__file__).resolve().parent.parent.parent
    crawl_name = current_dir / 'Raw_Data_Crawling//github//crawl_result' / f"{YM}_patch.jsonl"

    dir_path_new = './/crawl_result_new2//'
    crawl_name_new = dir_path_new + YM + '_patch.jsonl'

    fetchs = []
    if not os.path.exists(crawl_name):
        return

    #Process each patch and retrieve associated Git logs
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

            #If logs already exist, read them
            if os.path.exists(path_before) and os.path.exists(path_after):
                with open(path_before, 'r', encoding='utf-8') as file:
                    content_before = file.read()
                    record['windows_before'] = content_before
                with open(path_after, 'r', encoding='utf-8') as file:
                    content_after = file.read() 
                    record['windows_after'] = content_after
                fetchs.append(record)
                continue

            #Clone repo if missing and extract logs
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

    #Save new patch data
    with open(crawl_name_new, "w", encoding = "utf-8") as rf:
        rf.write(json.dumps(fetchs, indent=4, separators=(',', ': ')))

def add_message_1(Year, Month):
    """
    Convert raw Git log text into structured window objects for before/after commits.

    Input files:
        crawl_result_new2/<Year>_<Month>_patch.jsonl

    Output files:
        crawl_result_new3/<Year>_<Month>_patch.jsonl
    """
    YM = Year+'_'+Month
    print(YM)
    dir_path = './crawl_result_new2/'
    crawl_name = dir_path + YM + '_patch.jsonl'

    dir_path_new = './crawl_result_new3/'
    crawl_name_new = dir_path_new + YM + '_patch.jsonl'

    fetchs = []
    if not os.path.exists(crawl_name):
        return

    #Process each patch and convert Git log text into structured commit windows
    with open(crawl_name, "r", encoding="utf-8") as f:
        content = json.load(f)
        for i in range(len(content)):
            commit_id_now = content[i]['commit_id']
            windows_before = content[i]['windows_before']
            windows_after = content[i]['windows_after']

            #Process windows_before text into structured list
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

            #Process windows_after text into structured list
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

    #Save structured windows
    with open(crawl_name_new, "w", encoding = "utf-8") as rf:
        rf.write(json.dumps(fetchs, indent=4, separators=(',', ': ')))

def find(filename, windows, num):
    """
    Check whether a filename exists in the first num windows.

    Returns:
        1 if found, 0 otherwise.
    """
    for i in range(num):
        if i >= len(windows):
            return 0
        filenames = windows[i]['files_name']
        for each in filenames:
            if filename == each:
                return 1
    return 0

def add_message_2(Year, Month):
    """
    Mark each file in the patch as outdated in previous/future windows based on filename occurrence.

    Input files:
        crawl_result_new3/<Year>_<Month>_patch.jsonl

    Output files:
        crawl_result_new4/<Year>_<Month>_patch.jsonl
    """
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
    """
    Compute the latest commit date for each file across all patches.

    Returns:
        dict_date: {filename: latest datetime of modification}
    """
    Years = [str(year) for year in range(2001, 2024)]
    Months = [str(i) for i in range(1, 13)]
    dict_date = {}

    for Year in Years:
        for Month in Months:
            YM = Year+'_'+Month
            print(YM)
            dir_path = './crawl_result_new4/'
            crawl_name = dir_path + YM + '_patch.jsonl'

            #Skip if the patch file does not exist
            if not os.path.exists(crawl_name):
                continue

            #Load patch data for the month
            with open(crawl_name, "r", encoding="utf-8") as f:
                content = json.load(f)

                #Iterate through each patch entry
                for i in range(len(content)):
                    record = content[i]
                    date = record['commit_date']
                    date = datetime.fromisoformat(date.replace('Z', '+00:00'))

                    #Update latest modification date for each file
                    for j in range(len(record['files'])):
                        filename = record['files'][j]['filename']
                        if filename in dict_date:
                            #Keep the latest date if already recorded
                            dict_date[filename] = max(dict_date[filename], date)
                        else:
                            #Initialize date if first occurrence of the file
                            dict_date[filename] = date
    return dict_date

def add_message_3(Year, Month, dict_date):
    """
    Mark files as outdated based on whether they were modified after the last known commit date.

    Parameters:
        Year, Month: patch identifiers
        dict_date: dictionary of latest file modification dates

    Output files:
        crawl_result_last/<Year>_<Month>_patch.jsonl
    """
    YM = Year+'_'+Month
    print(YM)

    dir_path = './crawl_result_new4/'
    crawl_name = dir_path + YM + '_patch.jsonl'

    #Skip if patch file does not exist
    if not os.path.exists(crawl_name):
        print(crawl_name)
        return

    fetchs = []

    #Load patch data for the month
    with open(crawl_name, "r", encoding="utf-8") as f:
        content = json.load(f)

        #Iterate through each patch entry
        for i in range(len(content)):
            record = content[i]
            date = record['commit_date']
            date = datetime.fromisoformat(date.replace('Z', '+00:00'))

            #Mark each file as outdated if its last modification is after the commit date
            for j in range(len(record['files'])):
                filename = record['files'][j]['filename']
                if filename not in dict_date:
                    #File not found in overall latest dates, mark as not outdated
                    record['files'][j]['outdated_file_modify'] = 0
                elif date < dict_date[filename]:
                    #Current patch is older than the latest modification, mark as outdated
                    record['files'][j]['outdated_file_modify'] = 1
                else:
                    #Current patch is up-to-date
                    record['files'][j]['outdated_file_modify'] = 0

            #Add enriched record to fetch list
            fetchs.append(record)

    #Save the updated patch data with outdated flags
    dir_path_new = './crawl_result_last/'
    crawl_name_new = dir_path_new + YM + '_patch.jsonl'
    with open(crawl_name_new, "w", encoding="utf-8") as rf:
        rf.write(json.dumps(fetchs, indent=4, separators=(',', ': ')))

def outdated_window(CVEs):
    """
    Evaluate CVE details to mark files as outdated based on commit windows.

    Parameters:
        CVEs: List of CVE dictionaries containing windows_before and windows_after

    Returns:
        CVEs: Updated CVEs with outdated_file_before, outdated_file_after, and outdated_precise flags
    """
    file_suffix = [ 
                    'po', 'toml', 'lock', 'tests/TESTLIST', 'inc', 'svg', 'rst',
                    'out', 'ChangeLog', 'txt', 'json', 'md', 'CHANGELOG', 'CHANGES',
                    'CHANGELOG', 'misc/CHANGELOG', 'yml', 'yaml', 'css', 'sh', 'vim',
                   ]

    #Mark each file as outdated based on 1-window check
    for CVE in CVEs:
        for i,detail in enumerate(CVE['details']):
            windows_before = CVE['windows_before']
            windows_after = CVE['windows_after']
            filename = detail['file_name']
            CVE['details'][i]['outdated_file_before'] = find(filename, windows_before, 1)
            CVE['details'][i]['outdated_file_after'] = find(filename, windows_after, 1)

    #Mark CVEs as precisely outdated based on file type and modification
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
    Integrates Module 4's crawl_result output with Module 3's enriched dataset.

    Input files:
        Multi-granularity_Dependency_Extraction_Module/output/output_c_final.jsonl - Module 3 dataset
        Trace-based_Filtering_Module/github/crawl_result_4.jsonl - Module 4 dataset
        Raw_Data_Crawling/github/repos/ - local cloned repositories

    Output files:
        Trace-based_Filtering_Module/github/module4_output.jsonl - merged dataset with window info and additional stats
    """

    base_path = Path(__file__).resolve().parent.parent.parent
    YM = Year+'_'+Month

    module3_path = base_path / "Multi-granularity_Dependency_Extraction_Module" / "output" / "output_c_final.jsonl"
    module4_path = base_path / "Trace-based_Filtering_Module" / "github" / "crawl_result_new4" / f"{YM}_patch.jsonl"
    output_path  = base_path / "Trace-based_Filtering_Module" / "github" / "module4_output.jsonl"

    #Load Module 3 dataset
    with open(module3_path, "r", encoding="utf-8") as f3:
        module3_data = [json.loads(line) for line in f3 if line.strip()]

    #Load Module 4 dataset
    with open(module4_path, "r", encoding="utf-8") as f4:
        first_char = f4.read(1)
        f4.seek(0)
        if first_char == "[":
            module4_data = json.load(f4)
        else:
            module4_data = [json.loads(line) for line in f4 if line.strip()]

    #Build a map from commit_id to Module 4 entry
    module4_map = {entry.get("commit_id"): entry for entry in module4_data}

    print(f"Loaded {len(module3_data)} Module 3 entries")
    print(f"Loaded {len(module4_data)} Module 4 entries")

    merged_data = []
    missing_count = 0

    for entry in module3_data:
        commit_id = entry.get("commit_id")

        if commit_id in module4_map:
            module4_entry = module4_map[commit_id]

            #Merge only window-related fields
            entry["windows_before"] = module4_entry.get("windows_before", "")
            entry["windows_after"]  = module4_entry.get("windows_after", "")

            #Merge any additional stats (if present)
            for key in ["func_before", "func_after", "lines_changed"]:
                if key in module4_entry:
                    entry[key] = module4_entry[key]
        else:
            missing_count += 1

        merged_data.append(entry)

    #Save final merged output
    with open(output_path, "w", encoding="utf-8") as fout:
        for record in merged_data:
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Dataset saved to: {output_path}")
    
def main(Years=['2016'], Months=['8']):
    
    #Add raw Git logs to patch data
    for Year in Years:
        for Month in Months:
            add_message(Year, Month)

    #Structure Git log windows
    for Year in Years:
        for Month in Months:
            add_message_1(Year, Month)
    
    #Mark files as outdated in windows
    for Year in Years:
        for Month in Months:
            add_message_2(Year, Month)
    
    #Collect latest commit dates
    dict_date = get_alldate()
    
    #Mark outdated files based on latest commits
    for Year in Years:
        for Month in Months:
            add_message_3(Year, Month, dict_date)

    #Merge Module 4 results into Module 3 data
    for Year in Years:
        for Month in Months:
            integrate_module4_results(Year, Month)

if __name__ == "__main__":
    main()
