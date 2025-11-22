import os
from typing import Dict, List, Set, Tuple, Optional
import tree_sitter
from tree_sitter import Language, Parser, Query, QueryCursor, Node
import tree_sitter_python

class DependencyGraph:
    def __init__(self):
        self.files: Set[str] = set()
        self.functions: Dict[str, str] = {}  # func_name -> file_path
        self.file_dependencies: Dict[str, Set[str]] = {}  # file -> set(files)
        self.function_dependencies: Dict[str, Set[str]] = {}  # func -> set(funcs)
        self.function_definitions: Dict[str, List[Tuple[str, str]]] = {} # file -> [(func_name, full_name)]
        self.function_name_index: Dict[str, List[str]] = {} # func_name -> [unique_name]

    def add_file(self, file_path: str):
        self.files.add(file_path)
        if file_path not in self.file_dependencies:
            self.file_dependencies[file_path] = set()

    def add_function(self, func_name: str, file_path: str):
        # We store a unique name for the function to handle duplicates across files roughly
        # For now, we'll just use the simple name, but in a real system we'd want FQDNs.
        # To support the graph, let's store "file:func" as the unique key if needed, 
        # but the user asked for "what functions depend on what other functions".
        # Let's use a composite key "file_path::func_name" for the graph nodes.
        unique_name = f"{file_path}::{func_name}"
        self.functions[unique_name] = file_path
        if unique_name not in self.function_dependencies:
            self.function_dependencies[unique_name] = set()
        
        if file_path not in self.function_definitions:
            self.function_definitions[file_path] = []
        self.function_definitions[file_path].append((func_name, unique_name))
        
        # Update index
        if func_name not in self.function_name_index:
            self.function_name_index[func_name] = []
        self.function_name_index[func_name].append(unique_name)
        
        return unique_name

    def add_file_dependency(self, source_file: str, target_file: str):
        if source_file in self.files and target_file in self.files:
            self.file_dependencies[source_file].add(target_file)

    def add_function_dependency(self, source_func_unique: str, target_func_name: str):
        # Optimized lookup using index
        if target_func_name in self.function_name_index:
            for match in self.function_name_index[target_func_name]:
                self.function_dependencies[source_func_unique].add(match)

    def to_dot(self) -> str:
        lines = ["digraph CodeGraph {", "  rankdir=LR;", "  node [shape=box];"]
        
        lines.append("  subgraph cluster_files {")
        lines.append("    label = \"File Dependencies\";")
        for file in self.files:
            lines.append(f"    \"{os.path.basename(file)}\";")
        for src, targets in self.file_dependencies.items():
            src_name = os.path.basename(src)
            for tgt in targets:
                tgt_name = os.path.basename(tgt)
                lines.append(f"    \"{src_name}\" -> \"{tgt_name}\";")
        lines.append("  }")

        lines.append("  subgraph cluster_functions {")
        lines.append("    label = \"Function Dependencies\";")
        for unique_name in self.functions:
            label = unique_name.split("::")[-1]
            lines.append(f"    \"{label}\" [label=\"{label}\"];")
            
        for src, targets in self.function_dependencies.items():
            src_label = src.split("::")[-1]
            for tgt in targets:
                tgt_label = tgt.split("::")[-1]
                lines.append(f"    \"{src_label}\" -> \"{tgt_label}\";")
        lines.append("  }")
        
        lines.append("}")
        return "\n".join(lines)

class DependencyExtractor:
    def __init__(self, languages: Dict[str, Language]):
        self.languages = languages
        self.parser = Parser()

    def extract(self, file_path: str, tree: tree_sitter.Tree, graph: DependencyGraph):
        _, ext = os.path.splitext(file_path)
        lang = self.languages.get(ext)
        if not lang:
            return

        graph.add_file(file_path)
        
        # 1. Extract Imports (File Dependencies)
        # Naive: map import name to file name. 
        # e.g. "from utils import helper" -> look for "utils.py" or "utils/__init__.py"
        # This requires knowledge of the repo root, which we might not have easily here 
        # unless passed down. Let's assume relative imports or simple matching for now.
        
        import_query = Query(lang, """
        (import_statement) @import
        (import_from_statement) @from_import
        """)
        
        cursor = QueryCursor(import_query)
        captures = cursor.captures(tree.root_node)
        
        # We need to parse the import text to get the module name.
        # This is a bit rough with just regex or string parsing on the node text, 
        # but tree-sitter gives us structure.
        # Let's just grab the text and try to map it to files in the graph.
        # Note: The graph might not be fully populated with all files yet if we process one by one.
        # So we might need a two-pass approach: 
        # Pass 1: Collect all files and functions.
        # Pass 2: Resolve dependencies.
        
        # Let's implement the collection first in `extract_definitions` and resolution in `resolve_dependencies`.
        pass

    def extract_definitions(self, file_path: str, tree: tree_sitter.Tree, graph: DependencyGraph):
        _, ext = os.path.splitext(file_path)
        lang = self.languages.get(ext)
        if not lang:
            return

        graph.add_file(file_path)

        func_query = Query(lang, """
        (function_definition name: (identifier) @func_name)
        """)
        
        cursor = QueryCursor(func_query)
        captures = cursor.captures(tree.root_node)
        
        if 'func_name' in captures:
            for node in captures['func_name']:
                func_name = node.text.decode('utf8')
                graph.add_function(func_name, file_path)

    def resolve_dependencies(self, file_path: str, tree: tree_sitter.Tree, graph: DependencyGraph):
        _, ext = os.path.splitext(file_path)
        lang = self.languages.get(ext)
        if not lang:
            return

        # Resolve File Dependencies (Imports)
        import_query = Query(lang, """
        (dotted_name) @module_name
        """)
        # This is too broad, we need specific fields in import statements.
        # Better:
        import_query = Query(lang, """
        (import_statement name: (dotted_name) @mod)
        (import_from_statement module_name: (dotted_name) @mod)
        (import_from_statement name: (dotted_name) @mod)
        """)
        
        cursor = QueryCursor(import_query)
        captures = cursor.captures(tree.root_node)
        
        if 'mod' in captures:
            for node in captures['mod']:
                mod_name = node.text.decode('utf8')
                # Try to find a file that matches this module name
                # e.g. "utils.helper" -> "utils/helper.py" or "utils/helper/__init__.py"
                # e.g. "os" -> likely system, ignore?
                # Simple heuristic: check if any known file ends with "{mod_name}.py"
                # or "{mod_name}/__init__.py"
                
                # We need to be careful about partial matches.
                # Let's look for exact suffix matches on the path.
                expected_suffix = mod_name.replace('.', '/') + '.py'
                expected_init = mod_name.replace('.', '/') + '/__init__.py'
                
                for other_file in graph.files:
                    if other_file.endswith(expected_suffix) or other_file.endswith(expected_init):
                        if other_file != file_path:
                            graph.add_file_dependency(file_path, other_file)

        # Resolve Function Dependencies (Calls)
        call_query = Query(lang, """
        (call function: (identifier) @call_name)
        (call function: (attribute attribute: (identifier) @attr_call))
        """)
        
        cursor = QueryCursor(call_query)
        captures = cursor.captures(tree.root_node)
        
        calls = []
        if 'call_name' in captures:
            calls.extend([n.text.decode('utf8') for n in captures['call_name']])
        if 'attr_call' in captures:
            calls.extend([n.text.decode('utf8') for n in captures['attr_call']])
            
        # Find current function context?
        # For now, let's just link "functions in this file" to "called functions".
        # To be more precise, we should know WHICH function is making the call.
        # We can traverse the tree or check node ranges.
        
        # Let's iterate over defined functions in this file and find calls within them.
        if file_path in graph.function_definitions:
            for func_name, unique_name in graph.function_definitions[file_path]:
                # Find the node for this function again? 
                # Or we could have stored it. 
                # Let's re-query or just do a range check if we had the nodes.
                # Re-querying is easier for now but inefficient.
                # Optimization: Store nodes in extract_definitions? 
                # `graph` shouldn't store nodes (memory).
                
                # Let's refine: `resolve_dependencies` iterates functions in the tree.
                pass

        # Better approach for function calls:
        # Iterate function definitions in the tree.
        # For each definition, query for calls inside its body.
        
        func_def_query = Query(lang, """
        (function_definition name: (identifier) @func_name body: (block) @body)
        """)
        cursor = QueryCursor(func_def_query)
        func_captures = cursor.captures(tree.root_node)
        
        # The captures dict gives lists of nodes. We need to group them by match to know which body belongs to which name.
        # `captures()` returns a dict, so we lose the relationship if we just iterate lists.
        # We should use `matches()` to keep them grouped!
        
        cursor = QueryCursor(func_def_query)
        matches = cursor.matches(tree.root_node)
        
        for match in matches:
            # match is (pattern_index, capture_dict)
            capture_dict = match[1]
            func_node = capture_dict.get('func_name')
            body_node = capture_dict.get('body')
            
            if func_node and body_node:
                # func_node and body_node are lists (or single items depending on API, usually list in bindings if multiple?)
                # In python bindings, capture_dict values are usually single nodes if the capture name is unique in pattern?
                # Wait, `matches` returns `dict[str, Node | list[Node]]`?
                # Let's assume it's a single node for now based on the pattern.
                
                # Actually, let's check the `matches` API return type in my experiment if needed, 
                # but standard tree-sitter python bindings usually return a list of nodes for a capture name 
                # if it appears multiple times, or just the node.
                # But in `matches`, it's usually one match instance.
                
                f_name = func_node.text.decode('utf8') if isinstance(func_node, Node) else func_node[0].text.decode('utf8')
                b_node = body_node if isinstance(body_node, Node) else body_node[0]
                
                unique_name = f"{file_path}::{f_name}"
                
                # Now find calls inside b_node
                call_cursor = QueryCursor(call_query)
                call_captures = call_cursor.captures(b_node)
                
                calls_found = []
                if 'call_name' in call_captures:
                    calls_found.extend([n.text.decode('utf8') for n in call_captures['call_name']])
                if 'attr_call' in call_captures:
                    calls_found.extend([n.text.decode('utf8') for n in call_captures['attr_call']])
                
                for target_call in calls_found:
                    graph.add_function_dependency(unique_name, target_call)
