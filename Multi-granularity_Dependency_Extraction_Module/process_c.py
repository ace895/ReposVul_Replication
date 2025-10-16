import os
import json
import subprocess
import zipfile
import sys
import re
import glob
import concurrent.futures
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import parse_getout_nearfunc_c
import traceback

def process_content(lock, line, new_list):
    json_file = json.loads(line)

    #Extract function_id safely
    function_id = json_file.get('function_id')
    if function_id and function_id in new_list:
        return
    
    #Extract file_path safely
    if 'file_path' in json_file:
        path = json_file['file_path']
    elif 'details' in json_file and len(json_file['details']) > 0 and 'file_path' in json_file['details'][0]:
        path = json_file['details'][0]['file_path']
    else:
        path = None

    #Extract date safely
    if path:
        publish_date = path.replace('\\', '/').split('/')[1]
    else:
        #print("Could not find file path")
        return
    
    final_output_json = dict()
    final_output_json['function_id'] = function_id
    final_output_json['caller'] = dict()
    final_output_json['callee'] = dict()
    final_output_json['function_name'] = ''
    try:
        commit_id = json_file['parents'][0]['commit_id_before']
            
        path_before = 'prepared_input/repos_before/{}/{}.zip'.format(publish_date, commit_id)
        #if json_file['file_target'] == '-1':
        #    return
        path_after = 'tmp/unzip_tmp'
        os.makedirs(path_after, exist_ok=True)
        with zipfile.ZipFile(path_before, 'r') as zip_ref:
            zip_ref.extractall(path_after)
            contents = zip_ref.namelist()

        folder_name = contents[0].split('/')[0]
        dir_path = os.path.join(path_after, folder_name).replace("\\", "/")
        c_files = glob.glob(os.path.join(dir_path, "**", "*.c"), recursive=True)
        if not c_files:
            print(f"No .c files found in {dir_path}")
            result1 = None

        else:
            #Provide absolute path since cflow is not compatible with Windows paths
            for i in range(len(c_files)):
                c_files[i] = os.path.abspath(c_files[i]).replace("\\", "/")
            cmd = ["cflow", "-T", "-d", "2", "--omit-symbol-names", "-r"] + c_files

            try:
                result1 = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            except Exception as e:
                print(f"Error with cflow: {e}")
                result1 = None
                
        #print(result1)
        if result1.returncode == 0:
            result_arr = result1.stdout.splitlines()
            unzip_code_path = c_files[0]
            json_file['function_numbers'] = parse_getout_nearfunc_c.extract_function_numbers(unzip_code_path)
            for fn in json_file['function_numbers']:
                start_line = fn['function_start']
                end_line = fn['function_end']
                
                tmp = parse_getout_nearfunc_c.get_outfunc_and_nearfunc(unzip_code_path, 'c', start_line, end_line)
                for t in tmp:
                    func_name = t.split('.')[-1]
                    final_output_json['function_name'] = func_name
                    for i in range(len(result_arr)):
                        if result_arr[i].startswith('+-{}'.format(func_name)) and unzip_code_path in result_arr[i]:
                            callee_raw = list()
                            cnt = i
                            while True:
                                cnt += 1
                                if cnt == len(result_arr):
                                    break
                                if result_arr[cnt].startswith('  '):
                                    callee_raw.append(result_arr[cnt])
                                else:
                                    break
                            for cr in callee_raw:
                                if_exists, func_abs_name, raw_code = parse_getout_nearfunc_c.get_code(cr)
                                if if_exists:
                                    final_output_json['callee'][func_abs_name] = raw_code

                cmd2 = ["cflow", "-T", "-m", func_name, "-d", "2", "--omit-symbol-names"] + c_files


                try:
                    result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=300)
                except Exception as e:
                    print(f"Error with cflow second run: {e}")
                    result2 = None

                if result2 and result2.returncode == 0:
                    result_arr1 = result2.stdout.splitlines()
                    for i in range(len(result_arr1)):
                        if result_arr1[i].startswith('+-{}'.format(func_name)) and unzip_code_path in result_arr1[i]:
                            caller_raw = list()
                            cnt = i
                            while True:
                                cnt += 1
                                if cnt == len(result_arr1):
                                    break
                                if result_arr1[cnt].startswith('  '):
                                    caller_raw.append(result_arr1[cnt])
                                else:
                                    break
                            for cr in caller_raw:
                                if_exists, func_abs_name, raw_code = parse_getout_nearfunc_c.get_code(cr)
                                if if_exists:
                                    final_output_json['caller'][func_abs_name] = raw_code

    except Exception as e:
        print('Error reason: {}'.format(e))
        traceback.print_exc()
    with lock:
        with open('output/output_c.jsonl', 'a') as w1:
            w1.write(json.dumps(final_output_json) + '\n')

with open('prepared_input/output_c.jsonl', 'r', encoding = "utf-8") as r:
    content = r.readlines()
with open('prepared_input/ReposVul_function_c.jsonl', 'r', encoding = 'utf-8') as r1:
    new_content = r1.readlines()
new_list = list()
for new_line in new_content:
    json_file_new = json.loads(new_line)
    if 'function_id' in json_file_new:
        new_list.append(json_file_new['function_id'])

if __name__ == "__main__":
    multiprocessing.freeze_support()
    with multiprocessing.Manager() as manager:
        lock = manager.Lock()
        with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()//2) as executor:
            futures = [
                executor.submit(process_content, lock, line, new_list)
                for line in content
            ]
            for future in concurrent.futures.as_completed(futures):
                processed_line = future.result()