# ReposVul Replication Project Overview

---

## Module 1: Raw Data Crawling

Collects the related code of vulnerable patches by scraping their GitHub repositories.

**Run:** github/run.py

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

---

## Module 2: Vulnerability Untangling

Labels patches using static analysis tools and LLMs.

**Run static tools:** static/run_cppcheck.py, static/run_flawfinder.py, static/run_semgrep.py

**Run LLM:** llm/llm_evaluate.py

**Run all:** run.py

**Inputs:**

* `Raw_Data_Crawling/github/merge_result_new/language`
* `Raw_Data_Crawling/github/files_before`

**Outputs:**

* `output/cppcheck`
* `output/flawfinder`
* `output/llm`
* `output/semgrep`

**Current Problems:**

* Cannot test with the LLM from the paper (Tongyi Qwen) since there's no free version
* LLM results are not accurate since token limits are reached during testing
* Could not run RATS, a static analysis tool, since it's native to Linux; will likely have to run using WSL

---

## Module 3: Multi-granularity Dependency Extraction

Identifies function dependencies by building caller-callee function trees.

**Run:** prepare_inputs.py -> run.py

`prepare_c_inputs.py` merges outputs of Module 2 (`module2_output_[language].jsonl`) and creates a zip file of all files related to a single commit (`repos_before`)

**Inputs:**

* `prepared_input/*`

**Outputs:**

* `output/m_output.jsonl` (intermediary)
* `output/module3_output.jsonl` (final)

---

## Module 4: Trace-based Filtering Module

Identifies outdated patches by extracting commits before and after the patch.

**Run:** github/window.py

**Inputs**:

* `Raw_Data_Crawling/github/crawl_result/<Year>_<Month>_patch.jsonl`
* `Raw_Data_Crawling/github/repos/`
* `Multi_granularity_Dependency_Extraction_Module/output/module3_output.jsonl`

**Outputs**:

* `crawl_result_new2/`
* `crawl_result_new3/`
* `crawl_result_new4/`
* `crawl_result_last/`
* `github/module4_output.jsonl` (final)

---

## Running All Modules

* To run all modules for all years and months, run main.py
* To run all modules for a custom set of years and months, change the Years and Months parameters and run main.py
