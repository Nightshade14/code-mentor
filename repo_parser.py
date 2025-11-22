import os
from typing import Dict, Generator, Tuple, Optional
import tree_sitter
# Assuming tree_sitter version >= 0.22.0 where Language is directly available or via bindings
# and Parser is the main entry point.
from tree_sitter import Language, Parser

class RepoParser:
    """
    A class to traverse a repository and generate Tree-sitter syntax trees
    for supported file types.
    """

    def __init__(self, repo_path: str, languages: Dict[str, Language]):
        """
        Initialize the RepoParser.

        Args:
            repo_path: Path to the root of the repository.
            languages: A dictionary mapping file extensions (e.g., '.py') to
                       Tree-sitter Language objects.
        """
        self.repo_path = repo_path
        self.languages = languages
        self.parsers = {}
        self._initialize_parsers()

    def _initialize_parsers(self):
        """Initialize Tree-sitter parsers for each supported language."""
        for ext, lang in self.languages.items():
            parser = Parser()
            parser.language = lang
            self.parsers[ext] = parser

    def parse_repo(self) -> Generator[Tuple[str, tree_sitter.Tree], None, None]:
        """
        Traverse the repository and yield (file_path, tree) tuples for
        supported files.
        """
        for root, dirs, files in os.walk(self.repo_path):
            # Skip hidden directories like .git
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                _, ext = os.path.splitext(file)
                if ext in self.languages:
                    file_path = os.path.join(root, file)
                    tree = self._parse_file(file_path, ext)
                    if tree:
                        yield file_path, tree

    def _parse_file(self, file_path: str, ext: str) -> Optional[tree_sitter.Tree]:
        """Parse a single file using the appropriate parser."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            parser = self.parsers.get(ext)
            if parser:
                return parser.parse(content)
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
        return None
