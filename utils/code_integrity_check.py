# ============================================================================
#  File: code_integrity_check.py
#  Version: 1.10
#  Purpose: Scan Python files for duplicate code and unreachable code
#  Updated: 01AUG25
# ============================================================================
# SECTION 1: Imports and Global Variables
# ============================================================================

# Standard library imports
import ast
import hashlib
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Third-party imports
from loguru import logger

# Configure logging
LOG_FILE = "logs/code_integrity_check.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
logger.add(LOG_FILE, rotation="10 MB", level="DEBUG")

# ============================================================================
# SECTION 2: File Operations
# ============================================================================

def get_python_files(root_dir: str) -> List[str]:
    """
    Recursively find all Python files in the specified directory.

    Args:
        root_dir: Directory to search for Python files

    Returns:
        List of absolute paths to Python files
    """
    try:
        root_path = Path(root_dir).resolve()
        if not root_path.exists():
            logger.error(f"Directory does not exist: {root_dir}")
            return []

        python_files = [
            str(file_path)
            for file_path in root_path.rglob("*.py")
            if file_path.is_file()
        ]

        logger.debug(f"Found {len(python_files)} Python files in {root_dir}")
        return python_files

    except Exception as e:
        logger.error(f"Error finding Python files in {root_dir}: {str(e)}", exc_info=True)
        return []

def read_file_lines(filepath: str) -> List[str]:
    """
    Read all lines from a file with error handling.

    Args:
        filepath: Path to the file to read

    Returns:
        List of file lines, or empty list on error
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            logger.trace(f"Read {len(lines)} lines from {filepath}")
            return lines
    except Exception as e:
        logger.error(f"Error reading {filepath}: {str(e)}", exc_info=True)
        return []

# ============================================================================
# SECTION 3: Code Analysis
# ============================================================================

def find_duplicate_code_blocks(filepath: str, min_lines: int = 5) -> List[Dict[str, Any]]:
    """
    Find duplicate code blocks within a single file.

    Args:
        filepath: Path to the Python file to analyze
        min_lines: Minimum number of consecutive lines to consider as a block

    Returns:
        List of dictionaries containing duplicate code block information
    """
    logger.debug(f"Searching for duplicate code blocks in {filepath}")
    lines = read_file_lines(filepath)
    if not lines:
        return []

    duplicates = []
    blocks_seen = {}

    try:
        # First pass: find all blocks and their hashes
        for i in range(len(lines) - min_lines + 1):
            # Skip empty or whitespace-only blocks
            block_lines = lines[i:i + min_lines]
            if not any(line.strip() for line in block_lines):
                continue

            block = ''.join(block_lines)
            # Using SHA-256 for cryptographic strength instead of MD5
            block_hash = hashlib.sha256(block.encode()).hexdigest()

            if block_hash in blocks_seen:
                blocks_seen[block_hash].append(i + 1)  # +1 for 1-based line numbers
            else:
                blocks_seen[block_hash] = [i + 1]

        # Second pass: report duplicates
        for block_hash, line_numbers in blocks_seen.items():
            if len(line_numbers) > 1:
                # Create pairs of duplicate line ranges
                for i in range(len(line_numbers)):
                    for j in range(i + 1, len(line_numbers)):
                        start1 = line_numbers[i]
                        start2 = line_numbers[j]
                        duplicates.append({
                            'type': 'Duplicate Code',
                            'file': filepath,
                            'lines': (start1, start1 + min_lines - 1, start2, start2 + min_lines - 1),
                            'description': (
                                f"Duplicate block of {min_lines} lines found at lines "
                                f"{start1}-{start1 + min_lines - 1} and {start2}-{start2 + min_lines - 1}"
                            ),
                            'severity': 'medium',
                            'code': '\n'.join(f"{start1 + k}: {line.rstrip()}" for k, line in enumerate(block_lines))
                        })

        if duplicates:
            logger.info(f"Found {len(duplicates)} duplicate code blocks in {filepath}")

    except Exception as e:
        logger.error(f"Error finding duplicate code blocks in {filepath}: {str(e)}", exc_info=True)

    return duplicates

def find_unreachable_code(filepath: str) -> List[Dict[str, Any]]:
    """
    Find unreachable code in a Python file using AST analysis.

    Args:
        filepath: Path to the Python file to analyze

    Returns:
        List of dictionaries containing unreachable code information
    """
    logger.debug(f"Searching for unreachable code in {filepath}")

    class UnreachableCodeVisitor(ast.NodeVisitor):
        """AST visitor that identifies unreachable code after return/raise statements."""
        def __init__(self):
            self.issues: List[Dict[str, Any]] = []
            self.current_function = None

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            """Check for unreachable code in function bodies."""
            prev_function = self.current_function
            self.current_function = node.name
            self.check_unreachable_in_body(node.body)
            self.generic_visit(node)
            self.current_function = prev_function

        def visit_If(self, node: ast.If) -> None:
            """Check for unreachable code in if/else blocks."""
            self.check_unreachable_in_body(node.body)
            if node.orelse:
                self.check_unreachable_in_body(node.orelse)
            self.generic_visit(node)

        def visit_Try(self, node: ast.Try) -> None:
            """Check for unreachable code in try/except blocks."""
            self.check_unreachable_in_body(node.body)
            for handler in node.handlers:
                self.check_unreachable_in_body(handler.body)
            if node.orelse:
                self.check_unreachable_in_body(node.orelse)
            self.generic_visit(node)

        def check_unreachable_in_body(self, body: List[ast.AST]) -> None:
            """Check for unreachable code after return/raise statements."""
            return_found = False
            for stmt in body:
                if return_found:
                    # Found unreachable code after return/raise
                    self.issues.append({
                        'type': 'Unreachable Code',
                        'file': filepath,
                        'function': self.current_function or 'module',
                        'lines': (stmt.lineno, getattr(stmt, 'end_lineno', stmt.lineno)),
                        'description': (
                            f"Code at line {stmt.lineno} is unreachable due to "
                            "previous return/raise statement"
                        ),
                        'severity': 'high',
                        'context': self._get_context(stmt)
                    })

                if isinstance(stmt, (ast.Return, ast.Raise)):
                    return_found = True

        def _get_context(self, node: ast.AST) -> str:
            """Extract context around the node for better error reporting."""
            if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                start_line = max(1, node.lineno - 2)
                end_line = node.end_lineno + 2
                return f"Lines {start_line}-{end_line}"
            return f"Line {getattr(node, 'lineno', 'unknown')}"

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content, filename=filepath)
        visitor = UnreachableCodeVisitor()
        visitor.visit(tree)

        if visitor.issues:
            logger.info(f"Found {len(visitor.issues)} instances of unreachable code in {filepath}")

        return visitor.issues

    except SyntaxError as e:
        logger.error(f"Syntax error in {filepath}: {str(e)}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error analyzing {filepath}: {str(e)}", exc_info=True)
        return []

def check_all_files_for_duplicates(file_list: List[str]) -> List[Dict[str, Any]]:
    """
    Check all files for duplicate content, both entire files and code blocks.

    Args:
        file_list: List of file paths to check for duplicates

    Returns:
        List of dictionaries containing duplicate code information
    """
    logger.info(f"Checking {len(file_list)} files for duplicate content")
    file_hashes = {}
    duplicates = []

    try:
        # First pass: check for duplicate files
        for filepath in file_list:
            try:
                lines = read_file_lines(filepath)
                if not lines:
                    continue

                file_content = ''.join(lines)
                file_hash = hashlib.md5(file_content.encode()).hexdigest()

                if file_hash in file_hashes:
                    # Found duplicate file
                    duplicate_of = file_hashes[file_hash]
                    logger.warning(f"Duplicate file found: {filepath} is identical to {duplicate_of}")

                    duplicates.append({
                        'type': 'Duplicate File',
                        'file': filepath,
                        'lines': (1, len(lines)),
                        'description': f"Entire file is a duplicate of {duplicate_of}",
                        'severity': 'high',
                        'duplicate_of': duplicate_of
                    })
                else:
                    file_hashes[file_hash] = filepath
            except Exception as e:
                logger.error(f"Error checking file {filepath} for duplicates: {str(e)}", exc_info=True)

        # Second pass: check for duplicate blocks within files
        logger.debug("Checking for duplicate code blocks within files")
        for filepath in file_list:
            try:
                block_duplicates = find_duplicate_code_blocks(filepath)
                if block_duplicates:
                    duplicates.extend(block_duplicates)
            except Exception as e:
                logger.error(f"Error checking {filepath} for duplicate blocks: {str(e)}", exc_info=True)

        logger.info(f"Found {len(duplicates)} duplicate code issues across {len(file_list)} files")
        return duplicates

    except Exception as e:
        logger.critical(f"Fatal error in duplicate detection: {str(e)}", exc_info=True)
        return []

def scan_project() -> List[Dict[str, Any]]:
    """
    Main function to scan the project for code issues, including duplicates and unreachable code.

    Returns:
        List of all found issues across all scanned files
    """
    # Define directories to scan relative to script location
    script_dir = Path(__file__).parent.parent
    src_dir = script_dir / "src"
    agents_dir = script_dir / "agents"

    logger.info(f"Starting code integrity scan in {script_dir}")

    try:
        # Get all Python files
        logger.debug("Discovering Python files...")
        src_files = get_python_files(str(src_dir))
        agents_files = get_python_files(str(agents_dir))
        all_files = src_files + agents_files

        if not all_files:
            logger.warning("No Python files found to scan")
            return []

        logger.info(f"Found {len(all_files)} Python files to analyze")

        # Check for duplicate code
        logger.info("Checking for duplicate code...")
        duplicate_issues = check_all_files_for_duplicates(all_files)

        # Check for unreachable code
        logger.info("Checking for unreachable code...")
        unreachable_issues = []
        for filepath in all_files:
            try:
                issues = find_unreachable_code(filepath)
                if issues:
                    unreachable_issues.extend(issues)
            except Exception as e:
                logger.error(f"Error checking {filepath} for unreachable code: {str(e)}", exc_info=True)

        # Combine and report findings
        all_issues = duplicate_issues + unreachable_issues

        # Log summary
        if all_issues:
            issue_counts = {}
            for issue in all_issues:
                issue_type = issue.get('type', 'Unknown')
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

            logger.warning(f"\nFound {len(all_issues)} issues across {len(all_files)} files:")
            for issue_type, count in issue_counts.items():
                logger.warning(f"  - {issue_type}: {count}")

            # Log detailed report to file
            report_file = "code_quality_report.txt"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("Code Quality Analysis Report\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Scanned {len(all_files)} files at: {script_dir}\n")
                f.write(f"Found {len(all_issues)} total issues\n\n")

                for i, issue in enumerate(all_issues, 1):
                    f.write(f"{i}. {issue['type']} - {issue['file']}\n")
                    f.write(f"   Severity: {issue.get('severity', 'unknown')}\n")
                    f.write(f"   Lines: {issue.get('lines', 'N/A')}\n")
                    f.write(f"   Description: {issue.get('description', 'No description')}\n")
                    if 'code' in issue:
                        f.write("\n   Code Snippet:\n")
                        f.write("   " + "\n   ".join(issue['code'].split('\n')) + "\n")
                    f.write("\n" + "-" * 70 + "\n\n")

            logger.info(f"Detailed report written to: {report_file}")
        else:
            logger.success("No code quality issues found!")

        return all_issues

    except Exception as e:
        logger.critical(f"Fatal error during code scan: {str(e)}", exc_info=True)
        return []

if __name__ == "__main__":
    scan_project()
#
#
## End of Script
