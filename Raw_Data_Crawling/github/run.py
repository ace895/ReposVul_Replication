from pathlib import Path
from urllib.parse import unquote
from bs4 import BeautifulSoup
import re
import os
import json
import time
import random
from urllib.request import Request, urlopen
import requests
import subprocess
from tqdm import tqdm
from dotenv import load_dotenv
from .merge import main as merge

load_dotenv()
GITHUB_TOKEN = os.environ['GITHUB_TOKEN']

#Make required directories
BASE_DIR = Path(__file__).resolve().parent
for folder in [
    "crawl_result",
    "crawl_result_new",
    "files",
    "files_before",
    "logs",
    "merge_result_new",
    os.path.join("merge_result_new", "language"),
    os.path.join("merge_result_new", "project"),
    os.path.join("merge_result_new", "project_big"),
    os.path.join("merge_result_new", "time"),
    "rawcode_result",
    "repos",
    "repos_before",
    "results"
]:
    os.makedirs(os.path.join(BASE_DIR, folder), exist_ok=True)

def step_one(Year, Month, limit=None):
    """
    Scrapes Mend.io for CVE data for a given Year and Month.
    Extracts vulnerability details, saves them in logs and results JSONL files.
    Will extract the first 'limit' entries, if provided (used for testing).
    
    Input files:
        logs/<Year>_<Month>.log (if it exists) - stores previously scraped CVE URLs
        results/<Year>_<Month>.jsonl (if it exists) - used to track already processed CVEs

    Output files:
        logs/<Year>_<Month>.log - stores scraped CVE URLs
        results/<Year>_<Month>.jsonl - appends JSON objects for each CVE with metadata
    """
    #Setup filenames and URLs
    YM = Year + '_' + Month
    filename = BASE_DIR / 'logs' / f"{YM}.log"
    res_filename = BASE_DIR / 'results' / f"{YM}.jsonl"

    #Check if log file exists, else scrape the data
    if not os.path.exists(filename):

        #Request page for vulnerabilities
        url = f"https://www.mend.io/vulnerability-database/full-listing/{Year}/{Month}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.mend.io/vulnerability-database/",
        }

        #Fetch and parse HTML
        req = Request(url, headers=headers)
        html = urlopen(req).read()
        soup = BeautifulSoup(html, "html.parser")

        #Extract links to CVE pages
        links = []
        try:
            max_pagenumber = int(soup.find_all("li", class_="vuln-pagination-item")[-2].text.strip())
        except Exception:
            max_pagenumber = 1

        #Limit the number of links collected (for testing)
        def collect_links(soup, links, limit):
            for link in soup.find_all("a", href=re.compile("^/vulnerability-database/CVE")):
                if limit is not None and len(links) >= limit:
                    break
                name = link.text
                href = link.get("href")
                links.append((name, href))
            return links

        #Collect from first page
        links = collect_links(soup, links, limit)

        #Scrape subsequent pages if needed
        if max_pagenumber > 1 and (limit is None or len(links) < limit):
            for i in range(2, max_pagenumber + 1):
                if limit is not None and len(links) >= limit:
                    break
                url = f"https://www.mend.io/vulnerability-database/full-listing/{Year}/{Month}/{i}"
                soup = BeautifulSoup(urlopen(Request(url, headers=headers)).read(), 'html.parser')
                links = collect_links(soup, links, limit)

        #Save extracted links to log file
        with open(filename,'w') as f:
            for name, href in links:
                f.write(href+'\n')

    #Read all CVE links
    with open(filename,'r') as f:
        content = f.readlines()
    prefix = 'https://www.mend.io'

    #Track progress from last query
    already_query_qid = 0
    if os.path.exists(res_filename):
        with open(res_filename, 'r', encoding='utf-8') as f2:
            queried = f2.readlines()
            already_query_qid = json.loads(queried[-1])["q_id"] if len(queried) != 0 else 0
            print('already query {}'.format(already_query_qid))

    #Iterate through each CVE entry and extract detailed info
    for i in range(len(content)):
        try:
            random_time = random.uniform(0.1, 1)
            one_res = {"q_id":i ,"cve_id": content[i].strip().split('/')[-1], "language":None, "date":None, "resources": [], "CWEs": [] ,"cvss": None, "description":None, "AV":None, "AC":None, "PR":None, "UI":None, "S":None, "C":None, "I":None, "A":None}
            if i <= already_query_qid:
                continue

            #Fetch and parse each CVE page
            fullweb_url = prefix + content[i].strip()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.mend.io/vulnerability-database/",
            }
            req = Request(fullweb_url, headers=headers)
            html = urlopen(req).read()
            soup = BeautifulSoup(html, "html.parser")

            #Extract metadata
            date = None
            language = None
            description = None

            for tag in soup.find_all(["h4"]):
                if tag.name == "h4":
                    if "Date:" in tag.text:
                        date = tag.text.strip().replace("Date:", "").strip()
                    elif "Language:" in tag.text:
                        language = tag.text.strip().replace("Language:", "").strip()
            
            #Extract description
            div = soup.find("div", class_="single-vuln-desc no-good-to-know")
            if div:
                desc = div.find("p")
                description = desc.text.strip()
                one_res["description"] = description
            
            div = soup.find("div", class_="single-vuln-desc")
            if div:
                desc = div.find("p")
                description = desc.text.strip()
                one_res["description"] = description

            one_res["date"] =  date
            one_res["language"] =  language

            #Extract reference URLs
            reference_links = []
            for div in soup.find_all("div", class_="reference-row"):
                for link in div.find_all("a", href=True):
                    reference_links.append(link["href"])
            one_res["resources"] =  reference_links

            #Extract severity and vector metrics
            severity_score = ""
            div = soup.find("div", class_="ranger-value")
            if div:
                label = div.find("label")
                if label:
                    severity_score = label.text.strip()
            one_res["cvss"] =  severity_score

            #Parse CVSS metrics
            table = soup.find("table", class_="table table-report")
            if table:
                for tr in table.find_all("tr"):
                    th = tr.find('th').text.strip()
                    td = tr.find('td').text.strip()
                    if "Attack Vector" in th:
                        one_res["AV"] = td
                    elif "Attack Complexity" in th:
                        one_res["AC"] = td
                    elif "Privileges Required" in th:
                        one_res["PR"] = td
                    elif "User Interaction" in th:
                        one_res["UI"] = td
                    elif "Scope" in th:
                        one_res["S"] = td
                    elif "Confidentiality" in th:
                        one_res["C"] = td
                    elif "Integrity" in th:
                        one_res["I"] = td
                    elif "Availability" in th:
                        one_res["A"] = td

            #Extract CWE identifiers
            cwe_numbers = []
            for div in soup.find_all("div", class_="light-box"):
                for link in div.find_all("a", href=True):
                    if "CWE" in link.text:
                        cwe_numbers.append( link.text)
            one_res["CWEs"] =  cwe_numbers

            #Write valid results to file
            if (one_res["cve_id"] is not None) and (one_res["language"] is not None) and (one_res["date"] is not None) and ( \
                    one_res["resources"] != []) and (one_res["CWEs"] != []) and (one_res["cvss"] is not None):
                print("correct! all info is done for case", content[i])
                with open(res_filename, 'a', encoding='utf-8') as f2:
                    jsonobj = json.dumps(one_res)
                    f2.write(jsonobj + '\n')
            else:
                #Log missing data cases
                if one_res["resources"] == []:
                    print('no source ,therefore give it up ',content[i])
                else:
                    missing = []
                    if one_res["cve_id"] is None: missing.append("cve_id")
                    if one_res["language"] is None: missing.append("language")
                    if one_res["date"] is None: missing.append("date")
                    if one_res["resources"] == []: missing.append("resources")
                    if one_res["CWEs"] == []: missing.append("CWEs")
                    if one_res["cvss"] is None: missing.append("cvss")
                    print(f"Wrong! Missing fields: {missing}, see case {content[i]}")
        except Exception as e:
            print("line 169")
            print(e)


def step_two(Year, Month):
    """
    Fetches GitHub commit patch details from URLs collected in step_one.
    Stores commit metadata and associated changed files.

    Input files:
        results/<Year>_<Month>.jsonl - CVE JSON entries from step_one

    Output files:
        crawl_result/<Year>_<Month>_patch.jsonl - structured JSON containing commit info and modified files
        crawl_result/<Year>_<Month>_patch_error.txt - list of URLs that failed to fetch
    """
    #Setup paths
    YM = Year+'_'+Month
    res_filename = BASE_DIR / 'results' / f"{YM}.jsonl"
    patch_name = BASE_DIR / 'crawl_result' / f"{YM}_patch.jsonl"
    error_file = BASE_DIR / 'crawl_result' / f"{YM}_patch_error.txt"

    #Exit if no results found
    if not os.path.exists(res_filename):
        return

    #Load all CVE entries
    CVES = [json.loads(line) for line in open(res_filename, "r",encoding = "utf-8")]
    querys = []
    fetchs = []

    #Collect commit URLs
    for CVE in CVES:
        for res in CVE['resources']:
            if "commit" in res and "github" in res:
                querys.append(res.replace('/commit/', '/commits/').replace('https://github.com/', 'https://api.github.com/repos/'))

    #Fetch data from GitHub API
    try:
        total = len(querys)
        i = 0
        errors = []
        for query in querys:
            i += 1
            data = {}
            try:
                output = bytes.decode(subprocess.check_output(["curl", "--request", "GET" ,"-H", f"Authorization: Bearer {GITHUB_TOKEN}", "-H", "X-GitHub-Api-Version: 2022-11-28", query]))
                data = json.loads(output)
            except Exception as e:
                print("line 200")
                print(e)
                continue
            #Store valid results
            if 'url' in data and 'html_url' in data and 'commit' in data and 'files' in data:    
                for file in data['files']:
                    if 'raw_url' in file:
                        file['raw_url'] = unquote(file['raw_url'])
                fetchs.append({
                    'url': data['url'],
                    'html_url': data['html_url'],
                    'message': data['commit']['message'], 
                    'files': data['files'],
                    'commit_id': data['sha'],
                    'commit_date': data['commit']['committer']['date']
                })
            else:
                #Record failed cases
                print("Wrong! Data is NULL, see case ", query)
                print(data)
                errors.append(query)    
            time.sleep(1)
    except Exception:
        with open(patch_name, "w", encoding = "utf-8") as rf:
            rf.write(json.dumps(fetchs, sort_keys=True, indent=4, separators=(',', ': ')))
    except KeyboardInterrupt:
        with open(patch_name, "w", encoding = "utf-8") as rf:
            rf.write(json.dumps(fetchs, sort_keys=True, indent=4, separators=(',', ': ')))
    
    #Write fetched results and errors
    with open(patch_name, "w", encoding = "utf-8") as rf:
        rf.write(json.dumps(fetchs, indent=4, separators=(',', ': ')))
    with open(error_file, "w", encoding = "utf-8") as rf:
        for err in errors:
            rf.write(err+'\n')


def raw_code_before(raw_url, file_id, YM):
    """
    Fetches the previous version of a file (before the latest commit)
    from a GitHub repository using the GitHub API and saves it locally.

    Output files:
        files_before/<YM>/<file_id> - stores previous version of the file

    Args:
        raw_url (str): Raw URL of the current version of the file on GitHub.
        file_id (int): Unique identifier for the file.
        YM (str): Year-Month string used for directory organization.
    """
    try:
        #Create directory for storing "before" files based on year-month
        dir_path = BASE_DIR / f"files_before/{YM}"
        os.makedirs(dir_path, exist_ok=True)
        file_path = dir_path / str(file_id)

        #Skip downloading if the file already exists
        if os.path.exists(file_path):
            print("[DEBUG] File already exists, skipping")
            return

        #Parse owner, repo name, commit ID, and file path from raw URL
        #Example: https://github.com/<owner>/<repo>/raw/<commit>/<path>
        parts = raw_url.split('/')
        owner = parts[3]
        repo = parts[4]
        commit_id = parts[6]
        file_path_in_repo = '/'.join(parts[7:])

        #Use GitHub API to list recent commits affecting this file
        api_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        params = {"path": file_path_in_repo}

        response = requests.get(api_url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"[ERROR] GitHub API request failed: {response.status_code}, {response.text}")
            return

        commits = response.json()

        #Ensure at least two commits exist (current and previous)
        if len(commits) < 2:
            print("[WARNING] No previous commit found for this file, skipping")
            return

        #Extract the commit ID of the previous version
        commit_id_before = commits[1]['sha']

        #Construct the raw URL for the previous version of the file
        raw_url_before = f"https://raw.githubusercontent.com/{owner}/{repo}/{commit_id_before}/{file_path_in_repo}"

        #Fetch the raw file content from GitHub
        resp = requests.get(raw_url_before, headers=headers)
        if resp.status_code != 200:
            print(f"[ERROR] Failed to fetch raw file: {resp.status_code}")
            return

        content = resp.text

        #Save the previous version of the file locally
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    except Exception as e:
        print("Error in raw_code_before_api:", e)

def add_message(file_id, YM):
    """
    Reads and returns the content of a previously saved file from the
    'files_before' directory.

    Input files
        files_before/<YM>/<file_id> - previous version of the file

    Args:
        file_id (int): Unique identifier for the file.
        YM (str): Year-Month string used for locating the directory.

    Returns:
        str: The content of the file if found, otherwise an empty string.
    """
    dir_path = BASE_DIR / f"files_before/{YM}"
    file_path = dir_path / str(file_id)
    
    #Verify that the file exists before attempting to read it
    if not os.path.exists(file_path):
        print(f"Path does not exist: {file_path}")
        return ''

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except:
        return ''

def step_three(Year, Month):
    """
    Processes patch data, downloads raw source code files for each patch,
    retrieves the previous version of each file, and saves both to disk.
    
    Input files:
        crawl_result/<Year>_<Month>_patch.jsonl - patch information including raw_url and patch content
        files_before/ - stores previous version of files

    Output files:
        rawcode_result/<Year>_<Month>_rawcode.jsonl - JSON objects with patch info, raw code, original code
        rawcode_result/<Year>_<Month>_rawcode_error.txt - records failed file downloads
    """
    patches_id = 0
    files_id = 0
    YM = Year + '_' + Month
    patch_name = BASE_DIR / 'crawl_result' / f"{YM}_patch.jsonl"
    rawcode_name = BASE_DIR / 'rawcode_result' / f"{YM}_rawcode.jsonl"
    error_file = BASE_DIR / 'rawcode_result' / f"{YM}_rawcode_error.txt"

    #Skip if no patch file exists
    if not os.path.exists(patch_name):
        return

    #Continue from the last processed patch if the output file already exists
    already_patch = 0
    if os.path.exists(rawcode_name):
        with open(rawcode_name, "r", encoding="utf-8") as rf:
            alcon = rf.readlines()
            if len(alcon) > 0:
                last = alcon[-1]
                already_patch = int(json.loads(last)['patches_id'])
    print("already_patch: ", already_patch)

    patches = []
    with open(patch_name, "r", encoding="utf-8") as f:
        patches = json.load(f)

    errors = []

    #Iterate through each patch entry
    for patch in tqdm(patches):
        patches_id += 1
        if patches_id <= already_patch:
            continue

        for eachfile in patch['files']:
            try:
                #Process only entries with a raw_url key
                if "raw_url" in eachfile:
                    files_id += 1
                    one_res = {}
                    raw_url = eachfile['raw_url']

                    #Skip files with no patch content
                    if 'patch' not in eachfile:
                        continue

                    #Download the raw source file and save it locally
                    dir_path = BASE_DIR / f"files/{YM}"
                    os.makedirs(dir_path, exist_ok=True)
                    file_path = str(dir_path / str(files_id))
                    wget_command = f'wget -O "{file_path}" "{raw_url}"'
                    subprocess.run(wget_command, shell=True)

                    #Read file content from disk
                    with open(file_path, 'r', encoding='utf-8') as file:
                        print("getting content")
                        content = file.read()

                    #Construct the JSON object for this file entry
                    if content is not None:
                        one_res['patches_id'] = patches_id
                        one_res['files_id'] = files_id
                        one_res['language'] = eachfile['filename'].split('.')[-1]
                        one_res['raw_url'] = raw_url
                        one_res['raw_code'] = content
                        one_res['file_path'] = file_path

                        #Ensure correct encoding for text content
                        if isinstance(content, bytes):
                            one_res['raw_code'] = content.decode('utf-8', errors='ignore')
                        else:
                            one_res['raw_code'] = content

                        #Fetch and attach the previous version of the file
                        raw_code_before(raw_url, files_id, YM)
                        one_res['raw_code_before'] = add_message(files_id, YM)

                        #Include the patch data itself
                        one_res['patch'] = eachfile['patch']

                    #Append result to output file incrementally
                    with open(rawcode_name, 'a', encoding='utf-8') as f2:
                        jsonobj = json.dumps(one_res)
                        f2.write(jsonobj + '\n')
                else:
                    print("Wrong! raw_url not exist, see case ", patches_id)
                    errors.append(patches_id)
            except Exception as e:
                print(e)
                print("case is wrong ", patches_id)
                continue

    #Record any patch IDs that caused errors
    with open(error_file, "w", encoding="utf-8") as rf:
        for err in errors:
            rf.write(err + '\n')

    print('in total we have got {}'.format(patches_id))


def get_repos(Year, Month):
    """
    Downloads archived repositories corresponding to commits listed in the
    'merge_result_new' directory. Each commit is saved as a ZIP file.
    
    Input files:
        merge_result_new/time/merge_<Year>_<Month>.jsonl - contains commit URLs and IDs

    Output files:
        repos/<Year>_<Month>/<commit_id>.zip - repository archives for the listed commits
    """
    YM = Year + '_' + Month
    merge_name = BASE_DIR / 'merge_result_new/time' / f"merge_{YM}.jsonl"

    #Skip if no merge file exists
    if not os.path.exists(merge_name):
        return

    #Prepare destination directory for repository archives
    dir_path = BASE_DIR / f'repos/{YM}'
    os.makedirs(dir_path, exist_ok=True)

    #Read merge file entries and process each
    with open(merge_name, encoding='utf-8') as f:
        content = f.readlines()

        for i in range(len(content)):
            js = json.loads(content[i])
            raw_url = js['html_url']
            commit_id = js['commit_id']
            
            repos_name = str(commit_id) + ".zip"
            repos_file = dir_path / repos_name
            repos_url = raw_url.replace("commit/" + str(commit_id), "archive/" + str(commit_id)) + ".zip"

            #Use subprocess to run wget for downloading repository archives
            try:
                subprocess.run(["wget", "-O", repos_file, repos_url], check=True)
                print("Download old repos successful!")
            except subprocess.CalledProcessError as e:
                print(f"Error downloading file: {e}")


def add_message_before(Year, Month):
    """
    Extends patch data by adding parent commit information fetched from
    GitHub API for each patch, then saves the enriched result as a new file.
    
    Input files:
        crawl_result/<Year>_<Month>_patch.jsonl - patch data

    Output files:
        crawl_result_new/<Year>_<Month>_patch.jsonl - JSON with added parent commit info
    """
    YM = Year + '_' + Month
    crawl_name = BASE_DIR / 'crawl_result' / f"{YM}_patch.jsonl"
    crawl_name_new = BASE_DIR / 'crawl_result_new' / f"{YM}_patch.jsonl"

    fetchs = []

    #Skip if original crawl result does not exist
    if not os.path.exists(crawl_name):
        return

    #Read original patch data
    with open(crawl_name, "r", encoding="utf-8") as f:
        content = json.load(f)

        for i in range(len(content)):
            url = content[i]['url']

            try:
                #Fetch commit data via GitHub API to obtain parent commits
                output = bytes.decode(subprocess.check_output([
                    "curl", "--request", "GET",
                    "-H", f"Authorization: Bearer {GITHUB_TOKEN}",
                    "-H", "X-GitHub-Api-Version: 2022-11-28", url
                ]))

                data = json.loads(output)
                parents = data['parents']
                content[i]['parents'] = []

                #Add parent commit metadata
                for item in parents:
                    parent = {}
                    parent['commit_id_before'] = item['sha']
                    parent['url_before'] = item['url']
                    parent['html_url_before'] = item['html_url']
                    content[i]['parents'].append(parent)

                fetchs.append(content[i])

            except Exception as e:
                print("line 416")
                print(e)
                fetchs.append(content[i])
                continue

    #Write updated data with parent commit info to new output file
    with open(crawl_name_new, "w", encoding="utf-8") as rf:
        rf.write(json.dumps(fetchs, indent=4, separators=(',', ': ')))

def get_repos_before(Year, Month):
    """
    Downloads the repository archives corresponding to the commits
    that immediately precede the main commits listed in the merge file.

    For each parent commit associated with the merge, it reconstructs
    the GitHub archive URL for that commit and downloads the repository
    as a ZIP file into the appropriate 'repos_before' directory.
    
    Input files:
        merge_result_new/time/merge_<Year>_<Month>.jsonl - contains patch info with parents

    Output files:
        repos_before/<Year>_<Month>/<commit_id>.zip - ZIP archive of parent commit repositories
    """
    YM = Year + '_' + Month
    mergefile_time = BASE_DIR / 'merge_result_new/time/merge_'
    merge_name = str(mergefile_time) + YM + '.jsonl'

    #Exit if the merge file does not exist for this year-month
    if not os.path.exists(merge_name):
        return

    #Ensure directory for old repositories exists
    dir_path = BASE_DIR / f'repos_before/{YM}'
    os.makedirs(dir_path, exist_ok=True)

    #Read each line of the merge file (each line contains one commit entry)
    with open(merge_name, encoding='utf-8') as f:
        content = f.readlines()

        for i in range(len(content)):
            js = json.loads(content[i])

            #Skip entries without parent commit information
            try:
                parents = js['parents']
            except:
                continue

            #For each parent commit, reconstruct the download URL and fetch it
            for parent in parents:
                raw_url = parent['html_url_before']
                commit_id = parent['commit_id_before']

                repos_name = str(commit_id) + ".zip"
                repos_file = dir_path / repos_name
                repos_url = raw_url.replace("commit/" + str(commit_id),
                                            "archive/" + str(commit_id)) + ".zip"

                #Download the repository archive using wget
                try:
                    subprocess.run(["wget", "-O", repos_file, repos_url], check=True)
                    print("Download old repos successful!")
                except subprocess.CalledProcessError as e:
                    print(f"Error downloading file: {e}")


def run_steps(Years, Months, limit=None):
    #Run the first step for each year-month combination
    for Year in Years:
        for Month in Months:
            step_one(Year, Month, limit)

    #Run the second step for each year-month combination
    for Year in Years:
        for Month in Months:
            step_two(Year, Month)

    #Run the third step and extract additional message data
    for Year in Years:
        for Month in Months:
            step_three(Year, Month)
    
    for Year in Years:
        for Month in Months:
            add_message_before(Year, Month)

def get_all_repos(Years, Months):
    #Download repository archives for the processed commits
    for Year in Years:
        for Month in Months:
            get_repos(Year, Month)

    #Fetch metadata and download parent commit repositories
    for Year in Years:
        for Month in Months:
            get_repos_before(Year, Month)

#Called by main script
def main(Years=['2016'], Months=['8'], limit=None):
    run_steps(Years, Months, limit)
    print("Scraped CVE data and patch data")

    merge(Years, Months)
    print("Merged data")
    
    get_all_repos(Years, Months)
    print("Extracted repos")

if __name__ == '__main__':
    main()