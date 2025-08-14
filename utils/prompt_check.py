"""
Agent Prompt Construction Logic Verification Script
Version: 1.00
Purpose: Scan agent files to verify prompt construction logic.
"""
import os
import ast

def get_python_files(root_dir):
    """Get all Python files in the directory, excluding base classes."""
    python_files = []
    for item in os.listdir(root_dir):
        if item.endswith('.py') and 'base' not in item and '__init__' not in item:
            python_files.append(os.path.join(root_dir, item))
    return python_files

def analyze_agent_file(filepath):
    """Analyzes a single agent file for prompt construction logic."""
    report = {
        'uses_get_template_content': ('Fail', '`_construct_prompt` method not found.'),
        'has_template_override_logic': ('Fail', '`_construct_prompt` method not found.'),
        'formats_template': ('Fail', '`_construct_prompt` method not found.')
    }

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
    except Exception as e:
        return {
            'uses_get_template_content': ('Fail', f'Error parsing file: {e}'),
            'has_template_override_logic': ('Fail', f'Error parsing file: {e}'),
            'formats_template': ('Fail', f'Error parsing file: {e}')
        }

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_construct_prompt':
            # Reset reports since method is found
            report['uses_get_template_content'] = ('Fail', '`config_manager.get_template_content()` not called.')
            report['has_template_override_logic'] = ('Fail', 'No logic for `template_override` found.')
            report['formats_template'] = ('Fail', 'Template formatting not found.')

            body_content = ast.dump(node)

            if 'config_manager.get_template_content' in body_content:
                report['uses_get_template_content'] = ('Pass', '')
            
            if 'template_override' in body_content:
                report['has_template_override_logic'] = ('Pass', '')
            
            # Check for string formatting calls like .format() or f-strings
            is_formatted = False
            for sub_node in ast.walk(node):
                if isinstance(sub_node, ast.Call) and isinstance(sub_node.func, ast.Attribute) and sub_node.func.attr == 'format':
                    is_formatted = True
                    break
                if isinstance(sub_node, ast.JoinedStr): # f-string
                    is_formatted = True
                    break
            
            if is_formatted:
                report['formats_template'] = ('Pass', '')
            break # Stop after finding the method
    
    return report

def main():
    agents_dir = r"d:\Program Files\Dev\projects\Gemini-Agent\agents"
    agent_files = get_python_files(agents_dir)
    
    final_report = ""

    for agent_file in agent_files:
        final_report += f"--- Agent: {os.path.basename(agent_file)} ---\n"
        results = analyze_agent_file(agent_file)
        final_report += f"1. Uses config_manager.get_template_content(): {results['uses_get_template_content'][0]}"
        if results['uses_get_template_content'][1]:
             final_report += f" - {results['uses_get_template_content'][1]}"
        final_report += "\n"

        final_report += f"2. Has template_override logic: {results['has_template_override_logic'][0]}"
        if results['has_template_override_logic'][1]:
             final_report += f" - {results['has_template_override_logic'][1]}"
        final_report += "\n"

        final_report += f"3. Formats template with variables: {results['formats_template'][0]}"
        if results['formats_template'][1]:
             final_report += f" - {results['formats_template'][1]}"
        final_report += "\n\n"

    print(final_report)

if __name__ == "__main__":
    main()
