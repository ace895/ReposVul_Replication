import os
import urllib.request
import json
from tqdm import tqdm
import jsonlines

#Global counter for tracking outdated files
outdated = 0

def merge_alldata(Year='2023', Month='1', index=0, total=0):
    """
    Merges CVE data, patch information, and raw code into structured JSON files.
    For each CVE, it matches GitHub commits and aggregates details about files and patches.

    Output files produced:
        merge_result_new/language/<language>.jsonl
        merge_result_new/project/<project>.jsonl
        merge_result_new/project_big/<project_big>.jsonl
        merge_result_new/time/<Year>_<Month>.jsonl
    
    Parameters:
        Year (str): Year of the CVE data
        Month (str): Month of the CVE data
        index (int): Running index for merged entries
        total (int): Running total of raw code entries merged
    
    Returns:
        index (int): Updated index after merging
        total (int): Updated total raw code count after merging
    
    """
    
    global outdated
    YM = Year+'_'+Month
    #File paths for inputs
    CVEinfo_name = 'results/' + YM + '.jsonl'
    patch_name = 'crawl_result_new/' + YM + '_patch.jsonl'
    patcherr_name = 'crawl_result/' + YM + '_patch_error.txt'
    rawcode_name = 'rawcode_result/' + YM + '_rawcode.jsonl'

    #Directories for output
    mergefile_language = 'merge_result_new/language/merge_'
    mergefile_project = 'merge_result_new/project/merge_'
    mergefile_project_big = 'merge_result_new/project_big/merge_'
    mergefile_time = 'merge_result_new/time/merge_'

    #Ensure output directories exist
    os.makedirs('merge_result_new/language', exist_ok=True)
    os.makedirs('merge_result_new/project', exist_ok=True)
    os.makedirs('merge_result_new/project_big', exist_ok=True)
    os.makedirs('merge_result_new/time', exist_ok=True)

    #Skip if required input files do not exist
    if not os.path.exists(CVEinfo_name) or patch_name is None or rawcode_name is None:
        return index, total

    #Load CVE information
    CVEinfo = []
    with open(CVEinfo_name, "r", encoding="utf-8") as rf:
        for line in rf:
            CVEinfo.append(json.loads(line))
    
    #Load patch information
    patches = []
    with open(patch_name, "r", encoding="utf-8") as f:
        patches = json.load(f)
    
    #Load raw code information
    rawcode = []
    with open(rawcode_name, "r", encoding="utf-8") as rfc:
        for line in rfc:
            rawcode.append(json.loads(line))

    #Load list of patch errors
    patch_err = []
    with open(patcherr_name, "r", encoding="utf-8") as rfc:
        for line in rfc:
            patch_err.append(line.replace('\n', ''))

    patch_id = 0
    CVEinfo_id = 0

    #Iterate over CVEs and match them with patches
    while CVEinfo_id < len(CVEinfo) and patch_id < len(patches):
        for resource in CVEinfo[CVEinfo_id]['resources']:
            repo1 = (patches[patch_id]['html_url'].partition('github.com/')[2].partition('/commit'))[0]
            repo2 = (resource.partition('github.com/')[2].partition('/commit'))[0]

            #Construct GitHub API URL for commit
            url = resource.replace('/commit/', '/commits/').replace('https://github.com/', 'https://api.github.com/repos/')
            
            #Merge only if resource matches a patch and not in patch errors
            if 'commit' in resource and url not in patch_err and repo1.lower() == repo2.lower():
                merge_data = {} 
                #CVE metadata
                merge_data['index'] = index
                merge_data['cve_id'] = CVEinfo[CVEinfo_id]['cve_id']
                merge_data['cwe_id'] = CVEinfo[CVEinfo_id]['CWEs']
                merge_data['cve_language'] = CVEinfo[CVEinfo_id]['language']
                merge_data['cve_description'] = CVEinfo[CVEinfo_id]['description']
                merge_data['cvss'] = CVEinfo[CVEinfo_id]['cvss']
                merge_data['publish_date'] = CVEinfo[CVEinfo_id]['date']
                merge_data['AV'] = CVEinfo[CVEinfo_id]['AV']
                merge_data['AC'] = CVEinfo[CVEinfo_id]['AC']
                merge_data['PR'] = CVEinfo[CVEinfo_id]['PR']
                merge_data['UI'] = CVEinfo[CVEinfo_id]['UI']
                merge_data['S'] = CVEinfo[CVEinfo_id]['S']
                merge_data['C'] = CVEinfo[CVEinfo_id]['C']
                merge_data['I'] = CVEinfo[CVEinfo_id]['I']
                merge_data['A'] = CVEinfo[CVEinfo_id]['A']

                #Commit metadata
                merge_data['commit_id'] = patches[patch_id]['commit_id']
                merge_data['commit_message'] = patches[patch_id]['message']
                merge_data['commit_date'] = patches[patch_id]['commit_date']
                merge_data['project'] = repo1.lower()
                merge_data['url'] = patches[patch_id]['url']
                merge_data['html_url'] = patches[patch_id]['html_url']
                merge_data['windows_before'] = patches[patch_id].get('windows_before', "")
                merge_data['windows_after'] = patches[patch_id].get('windows_after', "")
                merge_data['parents'] = patches[patch_id]['parents']

                #Initialize details list for files
                merge_data['details'] = []

                #Iterate over files in the patch
                for eachfile in patches[patch_id]['files']:
                    #Find corresponding raw code entries
                    for rawcode_id in range(len(rawcode)):
                        if rawcode[rawcode_id]['patches_id'] == patch_id+1 and rawcode[rawcode_id]['raw_url'] == eachfile['raw_url']:
                            detail = {}
                            detail['raw_url'] = eachfile['raw_url']
                            detail['code'] = rawcode[rawcode_id]['raw_code']
                            detail['code_before'] = rawcode[rawcode_id]['raw_code_before']
                            detail['patch'] = eachfile['patch']
                            detail['file_path'] = rawcode[rawcode_id]['file_path']
                            detail['file_language'] = rawcode[rawcode_id]['language']
                            detail['file_name'] = eachfile['filename']
                            detail['outdated_file_modify'] = eachfile.get('outdated_file_modify', None)
                            detail['outdated_file_before'] = eachfile.get('outdated_file_before', None)
                            detail['outdated_file_after'] = eachfile.get('outdated_file_after', None)

                            merge_data['details'].append(detail)
                            total += 1

                #Mark outdated CVEs if any file is outdated
                if merge_data['details']:
                    merge_data['outdated'] = 0
                    for j in range(len(merge_data['details'])):
                        if merge_data['details'][j]['outdated_file_modify'] == 1 and (merge_data['details'][j]['outdated_file_before'] == 1 or merge_data['details'][j]['outdated_file_after'] == 1):
                            outdated += 1
                            merge_data['outdated'] = 1
                            break

                    #Save merged data by language
                    merge_name = mergefile_language + merge_data['cve_language'] + '.jsonl'
                    with open(merge_name, 'a', encoding='utf-8') as f2:
                        jsonobj = json.dumps(merge_data)
                        f2.write(jsonobj+'\n')

                    #Save merged data by project
                    merge_name = mergefile_project + merge_data['project'].replace('/','_') + '.jsonl'
                    with open(merge_name, 'a', encoding='utf-8') as f2:
                        jsonobj = json.dumps(merge_data)
                        f2.write(jsonobj + '\n')

                    #Save merged data by time (year_month)
                    merge_name = mergefile_time + YM + '.jsonl'
                    with open(merge_name, 'a', encoding='utf-8') as f2:
                        jsonobj = json.dumps(merge_data)
                        f2.write(jsonobj + '\n')

                    #Save merged data by project_big (repo name only)
                    merge_name = mergefile_project_big + merge_data['project'].split('/')[1] + '.jsonl'
                    with open(merge_name, 'a', encoding='utf-8') as f2:
                        jsonobj = json.dumps(merge_data)
                        f2.write(jsonobj + '\n')
                    index += 1  #Increment index after writing
                patch_id += 1
                if patch_id >= len(patches):
                    break
        CVEinfo_id += 1

    return index, total

def merge_data(Years, Months):
    index = 0
    total = 0
    for Year in Years:
        for Month in Months:
            index, total = merge_alldata(Year, Month, index, total)
            print(str(Year) + ' ' + str(Month) + ' ' + str(index) + ' ' + str(total))
    print('in total we merge '+str(index)+' commits')
    print('in total we merge '+str(total)+' rawcodes')
    print(outdated)

def main(Years=['2016'], Months=['8']):
    """
    Main entry point to merge data for specified years and months.
    Called by run.py
    """
    merge_data(Years, Months)
