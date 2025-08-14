#!/usr/bin/env python3
# =============================================================================
# CODEBASE INDEXER
# =============================================================================
"""
This script analyzes a codebase and generates a comprehensive index of its structure, including functions, classes, imports, and call graphs.
"""

import ast
import json
import os
import time
import logging
from pathlib import Path
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta

# =============================================================================
# GLOBAL VARIABLES
# =============================================================================

# File extensions to process
SUPPORTED_EXTENSIONS = {
    '.bat': 'batch',
    '.cfg': 'cfg',
    '.cmd': 'command',
    '.config': 'config',
    '.csv': 'csv',
    '.env': 'env',
    '.html': 'html',
    '.in': 'txt',  # Input/template files
    '.ini': 'ini',
    '.js': 'javascript',
    '.json': 'json',
    '.json5': 'json5',
    '.jsonc': 'jsonc',
    '.jsonl': 'jsonl',
    '.md': 'markdown',
    '.ndjson': 'ndjson',
    '.ps1': 'powershell',
    '.psd1': 'powershell_data',
    '.psm1': 'powershell_module',
    '.py': 'python',
    '.ts': 'typescript',
    '.tsx': 'tsx',
    '.txt': 'text',
    '.xml': 'xml',
    '.yaml': 'yaml',
    '.yml': 'yml'
}

RARE_EXTENSIONS = {
    '.cpp': 'cpp',
    '.cs': 'csharp',
    '.fish': 'fish',
    '.go': 'go',
    '.h': 'c_header',
    '.hpp': 'cpp_header',
    '.java': 'java',
    '.kt': 'kotlin',
    '.lock': 'lock',
    '.mdx': 'mdx',
    '.mmd': 'mmd',
    '.pbtxt': 'pbtxt',
    '.php': 'php',
    '.proj': 'project',
    '.rb': 'ruby',
    '.rs': 'rust',
    '.rst': 'rst',
    '.sh': 'sh',
    '.swift': 'swift',
    '.vba': 'vba',
    '.vbscript': 'vbscript',
    '.vc': 'vc',
    '.zsh': 'zsh'
}

NEVER_EXTENSIONS = {
    '.*env*/**': 'venv',
    '.DS_Store': 'ds_store',
    '.~*': 'temp',
    '.7z': '7z',
    '.bin': 'bin',
    '.bz2': 'bz2',
    '.d': 'c',
    '.dockerfile': 'dockerfile',
    '.dockerignore': 'dockerignore',
    '.git/**': 'git',
    '.gradle': 'gradle',
    '.gradlew': 'gradlew',
    '.gz': 'gz',
    '.idea/**': 'idea',
    '.ipynb': 'jupyter',
    '.iso': 'iso',
    '.lock': 'lock',
    '.log': 'log',
    '.npp': 'notepad++',
    '.pb': 'pb',
    '.pdb': 'pdb',
    '.pyd': 'python_bytecode',
    '.pyc': 'python_bytecode',
    '.pyo': 'python_bytecode',
    '.pyw': 'python_bytecode',
    '.rar': 'rar',
    '.tar': 'tar',
    '.temp': 'temp',
    '.tmp': 'tmp',
    '.trace': 'trace',
    '.vscode/**': 'vscode',
    '.whl': 'wheel',
    '.zip': 'zip',
    'node_modules/**': 'node_modules',
    'site-packages/**': 'site-packages',
    'version': 'version'  # No dot, sorts to the end
}


# =============================================================================
# DATA MODELS
# =============================================================================

class CodebaseIndex:
    def __init__(self):
        self.files = {}
        self.classes = {}
        self.functions = {}
        self.imports = {}
        self.call_graph = defaultdict(set)
        self.file_structure = {}

    def to_dict(self) -> Dict:
        """Convert the index to a dictionary for JSON serialization."""
        return {
            'files': self.files,
            'classes': self.classes,
            'functions': self.functions,
            'imports': self.imports,
            'call_graph': {k: list(v) for k, v in self.call_graph.items()},
            'file_structure': self.file_structure
        }

# =============================================================================
# PARSER FUNCTIONS
# =============================================================================

def parse_python_file(file_path: str, content: str, index: CodebaseIndex) -> None:
    """Parse a Python file and update the index."""
    try:
        tree = ast.parse(content)
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return

    file_id = str(Path(file_path).relative_to(Path.cwd()))
    index.files[file_id] = {
        'path': file_id,
        'language': 'python',
        'classes': [],
        'functions': [],
        'imports': []
    }

    # Track imports
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_name = []
            if isinstance(node, ast.Import):
                for name in node.names:
                    import_name.append(name.name)
            else:
                module = node.module or ''
                for name in node.names:
                    import_name.append(f"{module}.{name.name}")
            index.files[file_id]['imports'].extend(import_name)
            if file_id not in index.imports:
                index.imports[file_id] = []
            index.imports[file_id].extend(import_name)

    # Track classes and functions
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_info = {
                'name': node.name,
                'bases': [ast.unparse(base) for base in node.bases],
                'methods': [],
                'line_start': node.lineno,
                'line_end': getattr(node, 'end_lineno', node.lineno)
            }
            index.files[file_id]['classes'].append(node.name)
            index.classes[f"{file_id}::{node.name}"] = class_info

            # Track methods
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    method_info = {
                        'name': item.name,
                        'parameters': [arg.arg for arg in item.args.args],
                        'line_start': item.lineno,
                        'line_end': getattr(item, 'end_lineno', item.lineno)
                    }
                    class_info['methods'].append(method_info)
                    func_id = f"{file_id}::{node.name}.{item.name}"
                    index.functions[func_id] = method_info
                    index.files[file_id]['functions'].append(func_id)

        elif isinstance(node, ast.FunctionDef):
            func_info = {
                'name': node.name,
                'parameters': [arg.arg for arg in node.args.args],
                'line_start': node.lineno,
                'line_end': getattr(node, 'end_lineno', node.lineno)
            }
            func_id = f"{file_id}::{node.name}"
            index.functions[func_id] = func_info
            index.files[file_id]['functions'].append(func_id)

    # Track function calls (simplified)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                caller = get_enclosing_function(node, tree)
                if caller:
                    index.call_graph[caller].add(node.func.id)


def get_enclosing_function(node: ast.AST, tree: ast.AST) -> Optional[str]:
    """Get the name of the function that encloses the given node."""
    for ancestor in ast.walk(tree):
        if isinstance(ancestor, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            if (hasattr(ancestor, 'lineno') and hasattr(ancestor, 'end_lineno') and
                    ancestor.lineno <= node.lineno <= ancestor.end_lineno):
                if isinstance(ancestor, ast.FunctionDef) or isinstance(ancestor, ast.AsyncFunctionDef):
                    return ancestor.name
                elif isinstance(ancestor, ast.ClassDef):
                    for item in ancestor.body:
                        if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and
                                item.lineno <= node.lineno <= getattr(item, 'end_lineno', node.lineno)):
                            return f"{ancestor.name}.{item.name}"
    return None

# =============================================================================
# FILE SYSTEM FUNCTIONS
# =============================================================================

def build_file_structure(root_dir: str) -> Dict:
    """Build a dictionary representing the file system structure."""
    root_path = Path(root_dir)
    structure = {
        'name': root_path.name,
        'type': 'directory',
        'path': str(root_path.relative_to(Path.cwd())),
        'children': []
    }

    for item in root_path.iterdir():
        rel_path = str(item.relative_to(Path.cwd()))
        if item.is_dir():
            if item.name not in ['__pycache__', '.git', '.idea', 'venv', 'node_modules']:
                structure['children'].append(build_file_structure(item))
        else:
            if item.suffix.lower() in SUPPORTED_EXTENSIONS:
                structure['children'].append({
                    'name': item.name,
                    'type': 'file',
                    'path': rel_path,
                    'language': SUPPORTED_EXTENSIONS[item.suffix.lower()]
                })

    return structure

def process_file(file_path: str, index: CodebaseIndex) -> None:
    """Process a single file and update the index."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return

    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.py':
        parse_python_file(file_path, content, index)
    # Add parsers for other languages here

# =============================================================================
# MAIN FUNCTION
# =============================================================================

def generate_codebase_index(root_dir: str, output_file: str = 'gemini-codebase-index.json') -> None:
    """Generate a comprehensive index of the codebase."""
    root_path = Path(root_dir).resolve()
    index = CodebaseIndex()

    # Build file structure
    index.file_structure = build_file_structure(root_dir)

    # Process all supported files
    for ext in SUPPORTED_EXTENSIONS:
        for file_path in root_path.rglob(f'*{ext}'):
            if any(part.startswith('.') or part in ['__pycache__', 'venv', 'node_modules']
                  for part in file_path.parts):
                continue
            process_file(str(file_path), index)

    # Save the index to a file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(index.to_dict(), f, indent=2)

    print(f"Codebase index generated: {output_file}")

class AutoRefreshingIndexer:
    def __init__(self, root_dir: str, output_file: str = 'gemini-codebase-index.json',
                 refresh_interval: int = 600, log_file: str = None):
        self.root_dir = Path(root_dir).resolve()
        self.output_file = Path(output_file).resolve()
        self.refresh_interval = refresh_interval
        self.running = False
        self.last_modified_times = {}

        # Set up logging
        import logging
        log_handlers = [logging.StreamHandler()]
        
        # Add file handler if log file is specified
        if log_file:
            log_file_path = Path(log_file).resolve()
            log_handlers.append(logging.FileHandler(log_file_path))
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=log_handlers
        )
        self.logger = logging.getLogger(__name__)
        
        # Create parent directories if they don't exist
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        if log_file:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_file_modification_times(self) -> Dict[str, float]:
        """Get the last modified time for all files in the codebase."""
        mod_times = {}
        for root, _, files in os.walk(self.root_dir):
            for file in files:
                file_path = Path(root) / file
                try:
                    mod_times[str(file_path)] = file_path.stat().st_mtime
                except OSError as e:
                    self.logger.warning(f"Could not read {file_path}: {e}")
        return mod_times

    def _has_changes(self) -> bool:
        """Check if any files have been modified since the last check."""
        current_times = self._get_file_modification_times()

        if not self.last_modified_times:
            self.last_modified_times = current_times
            return True

        # Check for new, modified, or deleted files
        all_files = set(self.last_modified_times.keys()) | set(current_times.keys())
        for file in all_files:
            if file not in self.last_modified_times or \
               file not in current_times or \
               self.last_modified_times[file] != current_times[file]:
                return True

        return False

    def _run_indexer(self):
        """Run the indexer and update the output file if changes are detected."""
        try:
            if self._has_changes():
                self.logger.info("Detected changes in codebase. Updating index...")
                generate_codebase_index(str(self.root_dir), str(self.output_file))
                self.last_modified_times = self._get_file_modification_times()
                self.logger.info(f"Successfully updated index at {self.output_file}")
            else:
                self.logger.debug("No changes detected in codebase.")
        except Exception as e:
            self.logger.error(f"Error updating index: {e}", exc_info=True)

    def _is_within_hours(self, start_hour=8, end_hour=22):
        """Check if current time is within the specified hours."""
        current_hour = datetime.now().hour
        return start_hour <= current_hour < end_hour

    def start(self, start_hour=8, end_hour=22):
        """Start the auto-refreshing indexer.

        Args:
            start_hour: Hour to start indexing (inclusive, 24-hour format)
            end_hour: Hour to stop indexing (exclusive, 24-hour format)
        """
        self.running = True
        self.logger.info(f"Starting auto-refreshing indexer for {self.root_dir}")
        self.logger.info(f"Index will be saved to {self.output_file}")
        self.logger.info(f"Refresh interval: {self.refresh_interval} seconds")
        self.logger.info(f"Active hours: {start_hour}:00 - {end_hour}:00")

        try:
            while self.running:
                current_time = datetime.now()

                if self._is_within_hours(start_hour, end_hour):
                    self.logger.debug(f"Within active hours ({start_hour}-{end_hour}), running indexer...")
                    start_time = time.time()
                    self._run_indexer()

                    # Calculate sleep time, but don't sleep past the end hour
                    elapsed = time.time() - start_time
                    sleep_time = max(0, self.refresh_interval - elapsed)

                    # If we're close to the end hour, reduce sleep time
                    time_until_end = (datetime.now().replace(
                        hour=end_hour, minute=0, second=0, microsecond=0
                    ) - datetime.now()).total_seconds()

                    if time_until_end > 0:
                        sleep_time = min(sleep_time, time_until_end)
                else:
                    # Outside active hours, calculate time until next start hour
                    next_start = datetime.now().replace(
                        hour=start_hour, minute=0, second=0, microsecond=0
                    )
                    if datetime.now().hour >= end_hour:
                        next_start += timedelta(days=1)

                    sleep_time = (next_start - datetime.now()).total_seconds()
                    self.logger.info(f"Outside active hours. Next run at {next_start}")

                # Sleep in small increments to allow for graceful shutdown
                sleep_until = time.time() + sleep_time
                while time.time() < sleep_until and self.running:
                    time.sleep(min(1, sleep_until - time.time()))

        except KeyboardInterrupt:
            self.logger.info("Shutting down indexer...")
        finally:
            self.running = False

    def stop(self):
        """Stop the auto-refreshing indexer."""
        self.logger.info("Stopping indexer...")
        self.running = False

def main():
    import argparse
    import time

    parser = argparse.ArgumentParser(description='Codebase Indexer')
    parser.add_argument('root_dir', nargs='?', default=os.getcwd(),
                       help='Root directory to index (default: current directory)')
    parser.add_argument('-o', '--output', default='codebase_index.json',
                       help='Output file path (default: codebase_index.json)')
    parser.add_argument('-i', '--interval', type=int, default=600,
                       help='Refresh interval in seconds (default: 600)')
    parser.add_argument('--once', action='store_true',
                       help='Run once and exit without auto-refreshing')
    parser.add_argument('--log', help='Log file path (default: no file logging)')

    args = parser.parse_args()

    # Resolve paths relative to the script's directory
    script_dir = Path(__file__).parent.resolve()
    output_path = Path(args.output) if os.path.isabs(args.output) else script_dir / args.output
    log_path = Path(args.log) if args.log and os.path.isabs(args.log) else (script_dir / args.log if args.log else None)

    indexer = AutoRefreshingIndexer(
        root_dir=args.root_dir,
        output_file=output_path,
        refresh_interval=args.interval,
        log_file=log_path
    )

    if args.once:
        indexer._run_indexer()
    else:
        try:
            # Run between 8 AM (8) and 10 PM (22)
            indexer.start(start_hour=8, end_hour=22)
        except KeyboardInterrupt:
            indexer.stop()

if __name__ == "__main__":
    main()
