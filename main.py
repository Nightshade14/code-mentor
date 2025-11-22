import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Query, QueryCursor
import json

# 1. SETUP (Modern 0.22+ API)
PY_LANGUAGE = Language(tspython.language())
parser = Parser(PY_LANGUAGE)

def get_node_text(node, source_bytes):
    """Helper to extract string from source based on node range."""
    if not node: return ""
    return source_bytes[node.start_byte:node.end_byte].decode('utf8')

def parse_architecture(source_code, filename="unknown"):
    tree = parser.parse(bytes(source_code, "utf8"))
    source_bytes = bytes(source_code, "utf8")
    
    # ---------------------------------------------------------
    # QUERY 1: IMPORTS
    # ---------------------------------------------------------
    # Note: In S-expressions, standard naming is usually snake_case or simple names
    import_scm = """
    (import_statement
      name: (dotted_name) @import_name)
    (import_from_statement
      module_name: (dotted_name) @from_import)
    """
    
    import_query = Query(PY_LANGUAGE, import_scm)
    
    imports = []
    # MODERN API: captures() returns a list of (Node, str) tuples
    # arguments: query.captures(node)
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
                calls.append(get_node_text(node, source_bytes))
        return list(set(calls)) # Dedupe

    # Manual Walk to preserve hierarchy (Class -> Method -> Call)
    # This is safer than regex or complex queries for nested logic
    cursor = tree.walk()
    
    # We iterate over the children of the root node
    for child in tree.root_node.children:
        if child.type == 'class_definition':
            class_name = get_node_text(child.child_by_field_name('name'), source_bytes)
            methods = []
            
            body = child.child_by_field_name('body')
            # Safety check: body might be None if class is empty
            if body:
                for item in body.children:
                    if item.type == 'function_definition':
                        method_name = get_node_text(item.child_by_field_name('name'), source_bytes)
                        # EXTRACT CALLS INSIDE THIS METHOD
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
            # Standalone functions
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

import os
import argparse

# ... (keep existing imports and setup) ...

def scan_repository(repo_path):
    results = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        source_code = f.read()
                    
                    # Use relative path for cleaner output
                    rel_path = os.path.relpath(full_path, repo_path)
                    analysis = parse_architecture(source_code, rel_path)
                    results.append(analysis)
                except Exception as e:
                    print(f"Error processing {full_path}: {e}")
    return results

if __name__ == "__main__":
    cli_parser = argparse.ArgumentParser(description="Analyze Python repository architecture.")
    cli_parser.add_argument("repo_path", help="Path to the repository to analyze")
    args = cli_parser.parse_args()

    if not os.path.exists(args.repo_path):
        print(f"Error: Path '{args.repo_path}' does not exist.")
        exit(1)

    analysis_results = scan_repository(args.repo_path)
    print(json.dumps(analysis_results, indent=2))