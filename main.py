import os
import argparse
import concurrent.futures
import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Query, QueryCursor
import json

# Global variables for worker processes
PY_LANGUAGE = None
parser = None

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

def init_worker():
    """Initialize parser in each worker process."""
    global PY_LANGUAGE, parser
    PY_LANGUAGE = Language(tspython.language())
    parser = Parser(PY_LANGUAGE)

def get_node_text(node, source_bytes):
    """Helper to extract string from source based on node range."""
    if not node: return ""
    return source_bytes[node.start_byte:node.end_byte].decode('utf8')

def parse_architecture(source_code, filename="unknown"):
    # Ensure parser is initialized (should be done by init_worker)
    global parser, PY_LANGUAGE
    if parser is None:
        init_worker()
        
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
    captures = cursor.captures(tree.root_node)
    for name, nodes in captures.items():
        for node in nodes:
            imports.append(get_node_text(node, source_bytes))

    # ---------------------------------------------------------
    # QUERY 2: CLASS & FUNCTION DEFINITIONS (The "Boxes")
    # ---------------------------------------------------------
    structures = []
    
    # Helper function to find calls inside a block
    def extract_calls(block_node):
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
                # Extract just the function name (before any dot or parenthesis)
                func_name = call_text.split('.')[0].split('(')[0]
                # Filter out built-in functions
                if func_name not in PYTHON_BUILTINS:
                    calls.append(call_text)
        return list(set(calls)) # Dedupe

    # Manual Walk to preserve hierarchy
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
                        calls = extract_calls(func_body) if func_body else []
                        methods.append({
                            "name": method_name,
                            "calls": calls
                        })
            
            structures.append({
                "type": "class",
                "name": class_name,
                "methods": methods
            })

        elif child.type == 'function_definition':
            func_name = get_node_text(child.child_by_field_name('name'), source_bytes)
            func_body = child.child_by_field_name('body')
            calls = extract_calls(func_body) if func_body else []
            structures.append({
                "type": "function",
                "name": func_name,
                "calls": calls
            })

    return {
        "filename": filename,
        "imports": list(set(imports)),
        "structures": structures
    }

def process_file(file_info):
    """Worker function to process a single file."""
    full_path, rel_path = file_info
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            source_code = f.read()
        return parse_architecture(source_code, rel_path)
    except Exception as e:
        # Return error info instead of printing directly from worker
        return {"filename": rel_path, "error": str(e)}

def scan_repository(repo_path):
    file_list = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_path)
                file_list.append((full_path, rel_path))
    
    results = []
    # Use ProcessPoolExecutor for parallel processing
    # max_workers=None defaults to number of processors
    with concurrent.futures.ProcessPoolExecutor(initializer=init_worker) as executor:
        # Map returns results in order
        for result in executor.map(process_file, file_list):
            if "error" in result:
                print(f"Error processing {result['filename']}: {result['error']}")
            else:
                results.append(result)
                
    return results

if __name__ == "__main__":
    cli_parser = argparse.ArgumentParser(description="Analyze Python repository architecture.")
    cli_parser.add_argument("repo_path", help="Path to the repository to analyze")
    args = cli_parser.parse_args()

    if not os.path.exists(args.repo_path):
        print(f"Error: Path '{args.repo_path}' does not exist.")
        exit(1)

    analysis_results = scan_repository(args.repo_path)
    with open('output.json', 'w', encoding='utf-8') as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=2)

    