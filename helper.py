import os
import argparse
import json
import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Query, QueryCursor

# Initialize the Tree-sitter parser for Python once at import time
PY_LANGUAGE = Language(tspython.language())
parser = Parser(PY_LANGUAGE)

# Built-in Python functions to exclude from call tracking
PYTHON_BUILTINS = {
    'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'breakpoint', 'bytearray',
    'bytes', 'callable', 'chr', 'classmethod', 'compile', 'complex',
    'delattr', 'dict', 'dir', 'divmod', 'enumerate', 'eval', 'exec',
    'filter', 'float', 'format', 'frozenset', 'getattr', 'globals',
    'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int', 'isinstance',
    'issubclass', 'iter', 'len', 'list', 'locals', 'map', 'max',
    'memoryview', 'min', 'next', 'object', 'oct', 'open', 'ord', 'pow',
    'print', 'property', 'range', 'repr', 'reversed', 'round', 'set',
    'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super',
    'tuple', 'type', 'vars', 'zip', '__import__'
}

def get_node_text(node, source_bytes):
    """Helper to extract string from node range."""
    if not node:
        return ""
    return source_bytes[node.start_byte:node.end_byte].decode('utf8')

def extract_calls(block_node, source_bytes):
    """Extract function call strings from a block node."""
    calls = []
    call_scm = """
    (call
      function: (_) @called_func)
    """
    call_query = Query(PY_LANGUAGE, call_scm)
    cursor = QueryCursor(call_query)
    captures = cursor.captures(block_node)
    for name, nodes in captures.items():
        for node in nodes:
            call_text = get_node_text(node, source_bytes)
            func_name = call_text.split('.')[0].split('(')[0]
            if func_name not in PYTHON_BUILTINS:
                calls.append(call_text)
    return list(set(calls))

def parse_architecture(source_code, filename="unknown"):
    global parser, PY_LANGUAGE
    tree = parser.parse(bytes(source_code, "utf8"))
    source_bytes = bytes(source_code, "utf8")

    # ---------------------------------------------------------
    # QUERY 1: IMPORTS
    # ---------------------------------------------------------
    import_scm = """
    (import_statement
      name: (dotted_name) @import_name)
    (import_from_statement
      module_name: (dotted_name) @from_import)
    """
    import_query = Query(PY_LANGUAGE, import_scm)
    imports = []
    cursor = QueryCursor(import_query)
    for name, nodes in cursor.captures(tree.root_node).items():
        for node in nodes:
            imports.append(get_node_text(node, source_bytes))

    # ---------------------------------------------------------
    # QUERY 2: CLASSES & FUNCTIONS
    # ---------------------------------------------------------
    structures = []
    for child in tree.root_node.children:
        if child.type == 'class_definition':
            class_name = get_node_text(child.child_by_field_name('name'), source_bytes)
            methods = []
            body = child.child_by_field_name('body')
            if body:
                for item in body.children:
                    if item.type == 'function_definition':
                        method_name = get_node_text(item.child_by_field_name('name'), source_bytes)
                        func_body = item.child_by_field_name('body')
                        calls = extract_calls(func_body, source_bytes) if func_body else []
                        methods.append({"name": method_name, "calls": calls})
            structures.append({"type": "class", "name": class_name, "methods": methods})
        elif child.type == 'function_definition':
            func_name = get_node_text(child.child_by_field_name('name'), source_bytes)
            func_body = child.child_by_field_name('body')
            calls = extract_calls(func_body, source_bytes) if func_body else []
            structures.append({"type": "function", "name": func_name, "calls": calls})
    return {"filename": filename, "imports": list(set(imports)), "structures": structures}

def process_file(file_info):
    """Process a single file and return its architecture analysis."""
    full_path, rel_path = file_info
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            source_code = f.read()
        return parse_architecture(source_code, rel_path)
    except Exception as e:
        return {"filename": rel_path, "error": str(e)}

def scan_repository(repo_path):
    """Scan a repository sequentially and return analysis for all .py files."""
    file_list = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith('.py'):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_path)
                file_list.append((full_path, rel_path))
    results = []
    for file_info in file_list:
        result = process_file(file_info)
        if "error" in result:
            print(f"Error processing {result['filename']}: {result['error']}")
        else:
            results.append(result)
    return results

def extract_repo_knowledge(repo_path):
    """Entry point to extract knowledge from a repository path."""
    if not os.path.exists(repo_path):
        print(f"Error: Path '{repo_path}' does not exist.")

    analysis_results = scan_repository(repo_path)
    with open('output.json', 'w', encoding='utf-8') as f:
        json.dump(analysis_results, f, indent=2)
    return analysis_results