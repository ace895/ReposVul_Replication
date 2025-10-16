# ReposVul Replication Project Overview

**Note:** All tests were run on CVEs found in August 2016

---

## Module 1: Raw Data Crawling

Collects the related code of vulnerable patches by scraping their GitHub repositories.

**Run order:** run.py -> merge.py -> run.py

Some files generated in `merge.py` are required by `get_repos()` and `get_repos_before()`.

**Outputs:**

* `results/`
* `logs/`
* `crawl_result/`
* `crawl_result_new/`
* `rawcode_result/`
* `files/`
* `files_before/`
* `repos/`
* `repos_before/`
* `merge_result_new/`

**Current Problems:**

* Some keys are never populated: `window_before`, `window_after`, `outdated_file_modify`, `outdated_file_after`, `outdated_file_before`. These will likely be needed for module 4

---

## Module 2: Vulnerability Untangling

Labels patches using static analysis tools and LLMs.

**Run static tools (any order):** run_cppcheck.py, run_flawfinder.py, run_semgrep.py

**Run LLM:** llm_evaluate.py

**Inputs:**

* `Raw_Data_Crawling/github/merge_result_new/language`
* `Raw_Data_Crawling/github/files_before`

**Outputs:**

* `new_output/cppcheck_4`
* `new_output/flawfinder_1`
* `new_output/llm`
* `new_output/semgrep_3`

**Current Problems:**

* Static analysis tools label very few entires as "true"
* Cannot test with the LLM from the paper (Tongyi Qwen) since there's no free version
* Currently using a free Hugging Face model, but I hit the token limit quickly, so the results aren't accurate right now
* Could not run RATS (another static analysis tool) since it's native to Linux; will likely have to run using WSL

---

## Module 3: Multi-granularity Dependency Extraction

**Purpose:** Identifies function dependencies.

**Run order:** prepare_c_inputs.py -> process_c.py

`prepare_c_inputs.py` merges outputs of Module 2 (`output_c.jsonl`) and creates a zip file of all files related to a single commit (`repos_before`) as required by `process_c.py`.

**Inputs:**

* `prepared_input/*`

**Outputs:**

* `output/output_c.jsonl`

**Current Problems:**

* Uses `ReposVul_function_c.jsonl` to avoid reprocessing entries it has already processed, but I'm not sure (I created an empty file for now) 
* `function_id` is null
* Does not correlate the functions to anything from previous module (i.e. the CVEs)
* I have not combined the labels of the static analysis tools and LLM yet (this will need to be done in `prepare_c_inputs.py`)
* No code to extract the start and end of functions (i.e. `function_start` and `function_end`) so I made a method myself in `parse_getout_nearfunc_c.py`, but I'm not sure if this is the intended way of doing this


---

## Module 4: Trace-based Filtering Module
Not started yet

---
