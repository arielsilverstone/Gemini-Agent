import os
import json
import ast
import re
import argparse
from pathlib import Path

def find_files(root_dir, extensions, exclude_dirs):
    """Find all files with given extensions, excluding specified directories."""
    found_files = []
    for root, dirs, files in os.walk(root_dir):
        # Exclude specified directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                found_files.append(Path(root) / file)
    return found_files

def get_python_imports(file_path):
    """Extract import statements from a Python file."""
    imports = set()
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read(), filename=str(file_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
    return list(imports)

def get_string_references(file_path):
    """Extract path-like string references from a file."""
    references = set()
    path_regex = re.compile(r'(["\'])([./\w\\-]+)\1')
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            content = f.read()
            for match in path_regex.finditer(content):
                references.add(match.group(2))
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    return list(references)

def analyze_dependencies(files, base_path):
    """Analyze dependencies for a list of files."""
    dependencies = {}
    for file in files:
        rel_path = str(file.relative_to(base_path))
        if file.suffix == '.py':
            dependencies[rel_path] = get_python_imports(file)
        elif file.suffix in ['.json', '.html']:
            dependencies[rel_path] = get_string_references(file)
    return dependencies

def write_json_report(data, output_path):
    """Write dependencies to a JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def write_graphviz_report(data, output_path):
    """Write dependencies to a Graphviz DOT file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('digraph Dependencies {\n')
        f.write('  rankdir=LR;\n')
        f.write('  node [shape=box];\n')
        for node, deps in data.items():
            f.write(f'  "{node}";\n')
            for dep in deps:
                f.write(f'  "{node}" -> "{dep}";\n')
        f.write('}\n')

def main():
    parser = argparse.ArgumentParser(description='Generate dependency reports.')
    parser.add_argument('--root', default='.', help='Project root directory.')
    parser.add_argument('--outdir', default='.', help='Output directory for reports.')
    args = parser.parse_args()

    project_root = Path(args.root).resolve()
    output_dir = Path(args.outdir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    extensions_to_scan = ['.py', '.json', '.html']
    dirs_to_exclude = ['testing', 'documents', 'docs', '.git', '.vscode', '.backups', '__pycache__']

    print(f"Scanning for files in: {project_root}")
    files = find_files(project_root, extensions_to_scan, dirs_to_exclude)
    print(f"Found {len(files)} files to analyze.")

    dependencies = analyze_dependencies(files, project_root)

    json_report_path = output_dir / 'dependency_report.json'
    graphviz_report_path = output_dir / 'dependency_report.dot'

    print(f"Writing JSON report to: {json_report_path}")
    write_json_report(dependencies, json_report_path)

    print(f"Writing Graphviz report to: {graphviz_report_path}")
    write_graphviz_report(dependencies, graphviz_report_path)

    print("Dependency analysis complete.")

if __name__ == '__main__':
    main()
