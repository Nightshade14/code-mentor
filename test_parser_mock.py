import sys
from unittest.mock import MagicMock

# Mock tree_sitter and tree_sitter_python
sys.modules["tree_sitter"] = MagicMock()
sys.modules["tree_sitter_python"] = MagicMock()

from tree_sitter import Language, Parser
import tree_sitter_python

# Setup mocks
mock_language = MagicMock()
Language.return_value = mock_language
tree_sitter_python.language.return_value = "python_lang_ptr"

mock_parser_instance = MagicMock()
Parser.return_value = mock_parser_instance
mock_tree = MagicMock()
mock_tree.root_node.type = "module"
mock_parser_instance.parse.return_value = mock_tree

# Now import the actual code
from repo_parser import RepoParser
import os

def test_repo_parser():
    # Create a dummy file to parse
    with open("dummy.py", "w") as f:
        f.write("print('hello')")
    
    try:
        languages = {'.py': mock_language}
        parser = RepoParser(".", languages)
        
        found = False
        for file_path, tree in parser.parse_repo():
            if file_path.endswith("dummy.py"):
                print(f"Successfully parsed {file_path}")
                print(f"Root node type: {tree.root_node.type}")
                found = True
                break
        
        if not found:
            print("Failed to find dummy.py")
            
    finally:
        if os.path.exists("dummy.py"):
            os.remove("dummy.py")

if __name__ == "__main__":
    test_repo_parser()
