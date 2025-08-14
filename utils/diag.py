# diag.py - Diagnostic script to find Python path customization files
import site
import sys

print("--- Python Path (sys.path) ---")
for p in sys.path:
    print(p)
print("-" * 20)

print(f"\nUSER_SITE directory: {site.USER_SITE}")
print(f"USER_BASE directory: {site.USER_BASE}")
print("-" * 20)

try:
    import sitecustomize
    print(f"\nSUCCESS: Found sitecustomize.py at:")
    print(sitecustomize.__file__)
except ImportError:
    print(f"\nINFO: No sitecustomize.py found.")

try:
    import usercustomize
    print(f"\nSUCCESS: Found usercustomize.py at:")
    print(usercustomize.__file__)
except ImportError:
    print(f"\nINFO: No usercustomize.py found.")
