import os
import tree_sitter_python
from tree_sitter import Language
from repo_parser import RepoParser
from dependency_graph import DependencyGraph, DependencyExtractor

def main():
    # Example usage
    repo_path = "sample_repo/sample1"  # Current directory
    # repo_path = "sample_repo/pytorch"  # Current directory

    try:
        PY_LANGUAGE = Language(tree_sitter_python.language())
    except Exception as e:
        print(f"Error loading python language: {e}")
        return

    languages = {
        '.py': PY_LANGUAGE
    }
    
    parser = RepoParser(repo_path, languages)
    graph = DependencyGraph()
    extractor = DependencyExtractor(languages)
    
    print(f"Parsing repository at: {os.path.abspath(repo_path)}")
    
    # Pass 1: Extract Definitions
    print("Pass 1: Extracting definitions...")
    for file_path, tree in parser.parse_repo():
        extractor.extract_definitions(file_path, tree, graph)
        
    # Pass 2: Resolve Dependencies
    print("Pass 2: Resolving dependencies...")
    for file_path, tree in parser.parse_repo():
        extractor.resolve_dependencies(file_path, tree, graph)
        
    # print("\nDependency Graph (DOT format):")
    # print(graph.to_dot())
    
    # Save to file
    print("Generating DOT file...")
    dot_content = graph.to_dot()
    with open("graph.dot", "w") as f:
        f.write(dot_content)
    print(f"\nGraph saved to graph.dot ({len(dot_content)} bytes)")

if __name__ == "__main__":
    main()
