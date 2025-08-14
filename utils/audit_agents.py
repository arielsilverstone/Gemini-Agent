import subprocess
import re
from pathlib import Path
from collections import defaultdict

def get_code_line(file_path, line_number):
    """Extracts a single line of code from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        # Vulture lines are 1-indexed
        return lines[line_number - 1].strip()
    except FileNotFoundError:
        return f"# ERROR: Could not find file {file_path}"
    except IndexError:
        return f"# ERROR: Line {line_number} not found in {file_path}"
    except Exception as e:
        return f"# ERROR: Could not read file {file_path}: {e}"

def main():
    """Runs vulture to find dead code and creates a markdown report with code snippets."""
    project_root = Path(__file__).parent.parent
    agents_dir = project_root / 'agents'
    report_path = agents_dir / 'unused-code.md'
    python_executable = r'd:\Program Files\Dev\tools\Python313\Python\python.exe'

    command = [
        str(python_executable),
        '-m',
        'vulture',
        str(agents_dir),
        '--min-confidence',
        '80' # Standard confidence level
    ]

    print(f"Running command: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True, check=False)

    if not result.stdout.strip():
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('# Unused Code Report for Agents\n\n')
            f.write('**No unused code found.**\n')
        print(f"Report generated at: {report_path}")
        return

    # Group findings by file
    findings_by_file = defaultdict(list)
    # Regex to parse vulture's output, e.g., "path/to/file.py:123: unused variable 'x' (90% confidence)"
    line_regex = re.compile(r"^(.*?):(\d+): (.*)$")
    
    for line in result.stdout.strip().split('\n'):
        match = line_regex.match(line)
        if match:
            file_path, line_num, message = match.groups()
            findings_by_file[file_path].append({'line': int(line_num), 'message': message})

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('# Unused Code Report for Agents\n\n')
        f.write('This report lists potentially unused code found by `vulture`.\n\n')

        for file_path_str, items in sorted(findings_by_file.items()):
            # Vulture might return relative paths, resolve them against the project root
            file_path = Path(file_path_str)
            if not file_path.is_absolute():
                file_path = project_root / file_path
            
            f.write(f'## File: `{file_path_str}`\n\n')
            for item in sorted(items, key=lambda x: x['line']):
                code_line = get_code_line(file_path, item['line'])
                f.write(f"### Finding: {item['message']}\n")
                f.write(f"Line: {item['line']}\n")
                f.write('```python\n')
                f.write(code_line + '\n')
                f.write('```\n\n')

    print(f"Report generated at: {report_path}")

if __name__ == '__main__':
    main()
