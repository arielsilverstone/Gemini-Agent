# ============================================================================
#  Dependency Graph Analyzer Script
#  Version: 01.00
#  Purpose: Cross-language static dependency DAG builder for source codebases
#  Generated: 01AUG25
#  Path: d:/temp/dependency_graph.py
# ============================================================================

import os
import re
import sys
import ast
import json
import yaml
import argparse
from collections import defaultdict, deque

# ============================================================================
#  Section 1: Global Variables and Settings
# ============================================================================
SUPPORTED_EXTS = {'.py', '.js', '.json', '.yaml', '.yml', '.html', '.env'}
INCLUDE_DIRS = {'include', 'assets', 'templates'}
GRAPHVIZ_BIN = r'd:\program files\dev\tools\graphviz\bin\dot.exe'

# ============================================================================
#  Section 2: Utility Functions
# ============================================================================
def relpath(path, root):
     """Return path relative to root, with forward slashes."""
     return os.path.relpath(path, root).replace('\\', '/')

def ensure_dir(path):
     if not os.path.exists(path):
          os.makedirs(path)

def scan_files(root):
     """Yield (absolute_path, rel_path) for all supported files under root."""
     for dirpath, dirs, files in os.walk(root):
          # Skip excluded dirs
          dirs[:] = [d for d in dirs if d not in {'node_modules', '__pycache__'}]
          for fname in files:
               ext = os.path.splitext(fname)[1].lower()
               if ext in SUPPORTED_EXTS:
                    abspath = os.path.join(dirpath, fname)
                    yield abspath, relpath(abspath, root)

# ============================================================================
#  Section 3: Dependency Extraction Functions
# ============================================================================
def extract_py_deps(filepath, content):
     """Extract Python import dependencies using ast."""
     deps = set()
     try:
          tree = ast.parse(content, filename=filepath)
          for node in ast.walk(tree):
               if isinstance(node, ast.Import):
                    for n in node.names:
                         deps.add(n.name.split('.')[0])
               elif isinstance(node, ast.ImportFrom):
                    if node.module:
                         deps.add(node.module.split('.')[0])
     except Exception:
          pass
     return deps

def extract_js_deps(content):
     """Extract JS import/require dependencies via regex."""
     deps = set()
     # ES6 import ... from '...'
     for match in re.findall(r"import\\s+.*?from\\s+['\"](.*?)['\"]", content):
          deps.add(match)
     # CommonJS require('...')
     for match in re.findall(r"require\\(['\"](.*?)['\"]\\)", content):
          deps.add(match)
     return deps

def extract_json_yaml_deps(content):
     """Extract keys like import/include/module/path from JSON/YAML."""
     deps = set()
     try:
          data = yaml.safe_load(content)
          if isinstance(data, dict):
               stack = [data]
               while stack:
                    d = stack.pop()
                    for k, v in d.items():
                         if k.lower() in {'import', 'include', 'module', 'path'}:
                              if isinstance(v, str):
                                   deps.add(v)
                              elif isinstance(v, list):
                                   for i in v:
                                        if isinstance(i, str):
                                             deps.add(i)
                              elif isinstance(v, dict):
                                   stack.append(v)
                              elif isinstance(v, list):
                                   for i in v:
                                        if isinstance(i, dict):
                                             stack.append(i)
     except Exception:
          pass
     return deps

def extract_html_deps(content):
     """Extract <script src=...> and <link href=...> paths from HTML."""
     deps = set()
     for match in re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', content, re.I):
          deps.add(match)
     for match in re.findall(r'<link[^>]*href=["\']([^"\']+)["\']', content, re.I):
          deps.add(match)
     return deps

def extract_env_deps(content):
     """Extract file path values from key=value pairs."""
     deps = set()
     for line in content.splitlines():
          if '=' in line and not line.strip().startswith('#'):
               k, v = line.split('=', 1)
               v = v.strip().strip('"\'')
               if '/' in v or '\\' in v or v.startswith('.'):
                    deps.add(v)
     return deps

def extract_include_dir_refs(content):
     """Detect references to include/assets/templates folders."""
     deps = set()
     for d in INCLUDE_DIRS:
          for match in re.findall(rf'{d}/[\w\-./]+', content, re.I):
               deps.add(match)
     return deps

# ============================================================================
#  Section 4: Dependency Graph Construction
# ============================================================================
def build_dependency_graph(root):
     """Scan the codebase and build a dependency DAG."""
     file_map = {}  # rel_path -> abs_path
     dep_graph = defaultdict(set)
     for abspath, rel in scan_files(root):
          file_map[rel] = abspath
     for rel, abspath in file_map.items():
          ext = os.path.splitext(rel)[1].lower()
          try:
               with open(abspath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
          except Exception:
               continue
          deps = set()
          if ext == '.py':
               deps |= extract_py_deps(abspath, content)
          elif ext == '.js':
               deps |= extract_js_deps(content)
          elif ext in {'.json', '.yaml', '.yml'}:
               deps |= extract_json_yaml_deps(content)
          elif ext == '.html':
               deps |= extract_html_deps(content)
          elif ext == '.env':
               deps |= extract_env_deps(content)
          deps |= extract_include_dir_refs(content)
          # Normalize: only keep deps that are files in file_map or look like relative paths
          norm_deps = set()
          for d in deps:
               d = d.replace('\\', '/')
               if d in file_map:
                    norm_deps.add(d)
               else:
                    # Try relative to root
                    d_path = os.path.normpath(os.path.join(os.path.dirname(rel), d)).replace('\\', '/')
                    if d_path in file_map:
                         norm_deps.add(d_path)
          dep_graph[rel] = norm_deps
     return dep_graph, file_map

# ============================================================================
#  Section 5: Graph Algorithms (Cycle Detection, Toposort)
# ============================================================================
def detect_cycles(graph):
     """Return True if cycles are detected, else False."""
     visited = set()
     stack = set()
     def visit(node):
          if node in stack:
               return True
          if node in visited:
               return False
          visited.add(node)
          stack.add(node)
          for nbr in graph.get(node, []):
               if visit(nbr):
                    return True
          stack.remove(node)
          return False
     for n in graph:
          if visit(n):
               return True
     return False

def topological_sort(graph):
     """Return a topological ordering or None if cycles exist."""
     indeg = {n: 0 for n in graph}
     for nbrs in graph.values():
          for nbr in nbrs:
               if nbr in indeg:
                    indeg[nbr] += 1
     q = deque([n for n, d in indeg.items() if d == 0])
     order = []
     while q:
          n = q.popleft()
          order.append(n)
          for nbr in graph[n]:
               indeg[nbr] -= 1
               if indeg[nbr] == 0:
                    q.append(nbr)
     if len(order) == len(graph):
          return order
     return None

# ============================================================================
# Section 6: Detect Cycles and Toposort
# ============================================================================
def find_cycles(graph):
     visited = set()
     stack = set()
     cycles = []

     def visit(node, path):
          if node in stack:
               cycle_start = path.index(node)
               cycles.append(path[cycle_start:])
               return
          if node in visited:
               return
          visited.add(node)
          stack.add(node)
          for nbr in graph.get(node, []):
               visit(nbr, path + [nbr])
          stack.remove(node)

     for n in graph:
          visit(n, [n])
     return cycles


# ============================================================================
# Section 6: Output Functions
# ============================================================================
def save_json(graph, out_path):
     with open(out_path, 'w', encoding='utf-8') as f:
          json.dump({k: sorted(list(v)) for k, v in graph.items()}, f, indent=2)

def save_dot(graph, out_path):
     with open(out_path, 'w', encoding='utf-8') as f:
          f.write('digraph dependencies {\n')
          for src, tgts in graph.items():
               for tgt in tgts:
                    f.write(f'  "{src}" -> "{tgt}";\n')
          f.write('}\n')

def save_mermaid(graph, out_path):
     with open(out_path, 'w', encoding='utf-8') as f:
          f.write('graph TD\n')
          for src, tgts in graph.items():
               for tgt in tgts:
                    f.write(f'  {src.replace("/", "_")} --> {tgt.replace("/", "_")}\n')

def render_png(dot_path, png_path):
     import subprocess
     try:
          subprocess.run([GRAPHVIZ_BIN, '-Tpng', dot_path, '-o', png_path], check=True)
          return True
     except Exception:
          return False

def print_adjacency(graph):
     print('\nDependency Adjacency List:')
     for src, tgts in sorted(graph.items()):
          print(f'  {src}:')
          for tgt in sorted(tgts):
               print(f'    -> {tgt}')

# ============================================================================
# Section 7: Main Logic
# ============================================================================
def main():
     parser = argparse.ArgumentParser(description='Multi-language Dependency DAG Analyzer')
     parser.add_argument('-r', '--root', help='Root codebase folder to scan', required=False)
     parser.add_argument('-o', '--output', help='Output folder for reports/graphs', required=False)
     args = parser.parse_args()

     # Prompt if not provided
     root = args.root or input('Enter root codebase folder to scan: ').strip()
     output = args.output or input('Enter output folder for reports/graphs: ').strip()

     # Validate paths
     if not os.path.isdir(root):
          print(f'Error: Root folder not found: {root}')
          sys.exit(1)
     ensure_dir(output)

     # Build dependency graph
     dep_graph, file_map = build_dependency_graph(root)

     # Output files
     json_path = os.path.join(output, 'dependencies.json')
     dot_path = os.path.join(output, 'dependencies.dot')
     mmd_path = os.path.join(output, 'dependencies.mmd')
     png_path = os.path.join(output, 'dependencies.png')

     save_json(dep_graph, json_path)
     save_dot(dep_graph, dot_path)
     # save_mermaid(dep_graph, mmd_path)  <-- commented out making a mermaid diagram
     print_adjacency(dep_graph)

     # Graph features
     cycles = find_cycles(dep_graph)
     if cycles:
          print("\nWARNING: Cycles detected in dependency graph!")
          for i, cycle in enumerate(cycles, 1):
               print(f'Cycle {i}: {" -> ".join(cycle)} -> {cycle[0]}')
     else:
          order = topological_sort(dep_graph)
          if order is None:
               print("Topological sort failed: graph may have cycles or inconsistencies.")
          else:
               print("\nTopological Sort:")
               for n in order:
                    print(f"  {n}")

     # Optional: Render PNG if graphviz is installed
     if shutil.which(GRAPHVIZ_BIN):
          if render_png(dot_path, png_path):
               print(f'\nGraph image saved to: {png_path}')
     else:
          print('\n(Graphviz not found; PNG not generated)')

if __name__ == '__main__':
     import shutil
     main()
