import json
import argparse
from collections import defaultdict
from pathlib import Path

def find_cycles_util(graph, node, visited, recursion_stack, path, cycles):
    """Utility function for finding cycles using DFS."""
    visited[node] = True
    recursion_stack[node] = True
    path.append(node)

    for neighbor in graph.get(node, []):
        if not visited.get(neighbor, False):
            find_cycles_util(graph, neighbor, visited, recursion_stack, path, cycles)
        elif recursion_stack.get(neighbor, False):
            try:
                cycle_start_index = path.index(neighbor)
                cycle = path[cycle_start_index:] + [neighbor]
                # Normalize the cycle to avoid duplicates
                sorted_cycle = tuple(sorted(cycle))
                if sorted_cycle not in cycles:
                    cycles[sorted_cycle] = cycle
            except ValueError:
                # This can happen if the neighbor is not in the current path, which is unexpected
                # but we'll handle it gracefully.
                pass

    path.pop()
    recursion_stack[node] = False

def find_all_cycles(graph):
    """Finds all elementary cycles in a directed graph."""
    visited = {}
    recursion_stack = {}
    cycles = {}
    
    for node in list(graph.keys()):
        if not visited.get(node, False):
            find_cycles_util(graph, node, visited, recursion_stack, [], cycles)
            
    return list(cycles.values())

def main():
    parser = argparse.ArgumentParser(description='Find circular dependencies from a JSON report.')
    parser.add_argument('report_file', help='Path to the dependency_report.json file.')
    args = parser.parse_args()

    try:
        with open(args.report_file, 'r', encoding='utf-8') as f:
            dependencies = json.load(f)
    except FileNotFoundError:
        print(f"Error: Report file not found at {args.report_file}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {args.report_file}")
        return

    # Create a map from a module-like name (e.g., 'src.orchestrator') to a file path
    module_to_file_map = {
        str(Path(f).with_suffix('')).replace('\\', '.'): f for f in dependencies.keys() if f.endswith('.py')
    }
    
    graph = defaultdict(list)
    for file_path, deps in dependencies.items():
        for dep_module in deps:
            # Check if the dependency module maps to a known file
            if dep_module in module_to_file_map:
                graph[file_path].append(module_to_file_map[dep_module])
            # Also check for direct file path references
            elif dep_module in dependencies:
                graph[file_path].append(dep_module)

    cycles = find_all_cycles(graph)

    if cycles:
        print(f"Found {len(cycles)} circular dependenc(y/ies):")
        for i, cycle in enumerate(cycles, 1):
            print(f"\n--- Cycle {i} ---")
            print(" -> ".join(cycle))
            print("-" * (len(str(i)) + 12))
    else:
        print("No circular dependencies found.")

if __name__ == '__main__':
    main()
