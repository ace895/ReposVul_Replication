import os
import subprocess
import difflib
from tree_sitter_language_pack import get_parser
from parse_getout_nearfunc_c import traverse_outfunc, get_func_name
from pathlib import Path
import difflib
import re

#Build caller-callee trees
def build_dependency_trees(repo_path, funcs_info, language='c'):
    """
    Builds caller-callee dependency trees for all functions in the given repository using cflow.

    Parameters:
        repo_path (str | Path): Path to the repository containing source code files.
        funcs_info (list[dict]): List of dictionaries with function information, each containing:
                                 - "file": relative path to the source file
                                 - "name": function name
        language (str, optional): Programming language of the source files (default is 'c').

    Returns:
        tuple[dict, dict]:
            - caller_tree: Dictionary mapping each caller function to a list of callee functions.
            - callee_tree: Dictionary mapping each callee function to a list of caller functions.
    """
    caller_tree = {}
    callee_tree = {}

    #Group functions by file
    funcs_by_file = {}
    for f in funcs_info:
        file_path = f["file"].split("/", 1)[-1] if "/" in f["file"] else f["file"]
        funcs_by_file.setdefault(file_path, []).append(f["name"])

    for file_path, func_names in funcs_by_file.items():
        abs_path = os.path.join(repo_path, file_path)

        for func_name in func_names:  
            try:
                #Run cflow to extract dependency information
                result = subprocess.run(
                    ["cflow", "-T", "-m", func_name, "-d", "2", "--omit-symbol-names", abs_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10
                )
                cflow_output = result.stdout
            except Exception as e:
                print(f"cflow failed for {func_name}: {e}")
                continue

            if not cflow_output.strip():
                continue

            #Parse cflow output
            stack = []
            for line in cflow_output.splitlines():
                #Skip non function lines
                if not line.strip().startswith(('+', '\\')):
                    continue

                #Handle indentations
                indent = len(line) - len(line.lstrip(' '))
                depth = indent // 2

                #Extract function name
                match = re.search(r'([A-Za-z_]\w*)\s*\(', line)
                if not match:
                    continue
                name = match.group(1)

                #Maintain call stack based on indentation depth
                while len(stack) > depth:
                    stack.pop()

                if stack:
                    caller = stack[-1]
                    callee = name
                    caller_tree.setdefault(caller, set()).add(callee)
                    callee_tree.setdefault(callee, set()).add(caller)

                stack.append(name)

    #Convert to lists
    caller_tree = {k: list(v) for k, v in caller_tree.items()}
    callee_tree = {k: list(v) for k, v in callee_tree.items()}

    return caller_tree, callee_tree

def extract_functions_with_spans_tree_sitter(file_path, language='c'):
    """
    Extracts top-level function definitions from a source file using Tree-sitter and returns their spans.

    Parameters:
        file_path (str | Path): Path to the source file to be parsed.
        language (str, optional): Programming language of the source file (default is 'c').

    Returns:
        list[dict]: A list of dictionaries, each representing a function with:
            - "name" (str): Function name.
            - "start_line" (int): Starting line number of the function.
            - "end_line" (int): Ending line number of the function.
            - "content" (str): Full text content of the function body.
    """
    #Skip files that aren't in the given language
    if language == 'c' and not str(file_path).endswith(".c"):
        return []
    elif language == 'cpp' and not str(file_path).endswith((".cpp", ".cxx", ".cc", ".hpp", ".h")):
        return []

    #Get parser for given language
    parser = get_parser(language)
    try:
        data = Path(file_path).read_bytes()
    except FileNotFoundError:
        return []

    #Parse the file
    tree = parser.parse(data)
    root = tree.root_node

    results = []
    #Extract function information
    for node in traverse_outfunc(root):
        name = get_func_name(node)
        if not name:
            continue
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        func_bytes = data[node.start_byte: node.end_byte]
        try:
            func_text = func_bytes.decode('utf-8', errors='ignore')
        except Exception:
            func_text = func_bytes.decode('latin-1', errors='ignore')
        results.append({
            'name': name,
            'start_line': start_line,
            'end_line': end_line,
            'content': func_text
        })
    return results

def get_changed_functions_from_files_tree_sitter(before_file, after_file, language='c'):
    """
    Identifies which functions have changed between two versions of a source file using Tree-sitter and difflib.

    Parameters:
        before_file (str | Path): Path to the 'before' version of the source file.
        after_file (str | Path): Path to the 'after' version of the source file.
        language (str, optional): Programming language of the source files (default is 'c').

    Returns:
        set[str]: A set of function names that were modified, added, or removed between the two files.
    """
    #Extract functions from both versions
    before_funcs = extract_functions_with_spans_tree_sitter(before_file, language)
    after_funcs = extract_functions_with_spans_tree_sitter(after_file, language)

    if before_funcs == [] or after_funcs == []:
        return []

    #Map names to list of functions
    before_by_name = {f["name"]: f for f in before_funcs}
    after_by_name  = {f["name"]: f for f in after_funcs}

    #Load lines
    try:
        before_lines = Path(before_file).read_text(encoding="utf-8", errors="ignore").splitlines()
    except FileNotFoundError:
        before_lines = []
    try:
        after_lines = Path(after_file).read_text(encoding="utf-8", errors="ignore").splitlines()
    except FileNotFoundError:
        after_lines = []

    #Compute changed line numbers
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
    changed_lines_after = set()
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            changed_lines_after.update(range(j1 + 1, j2 + 1))

    changed_funcs = set()

    #Map changed lines to after functions
    for f in after_funcs:
        for ln in changed_lines_after:
            if f["start_line"] <= ln <= f["end_line"]:
                changed_funcs.add(f["name"])
                break

    #Detect removed or renamed functions
    for name in before_by_name:
        if name not in after_by_name:
            changed_funcs.add(name)

    return changed_funcs
