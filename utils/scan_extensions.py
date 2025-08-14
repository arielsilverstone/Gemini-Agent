#!/usr/bin/env python3
"""
Scans a directory and lists all file extensions with their counts.
"""
import os
from pathlib import Path
from collections import defaultdict

def scan_directory(directory: str) -> dict:
    """Scan a directory and count file extensions."""
    ext_counts = defaultdict(int)
    
    try:
        for root, _, files in os.walk(directory):
            for file in files:
                ext = Path(file).suffix.lower()
                ext_counts[ext] += 1
    except Exception as e:
        print(f"Error scanning directory: {e}")
    
    return ext_counts

def main():
    import sys
    
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = os.getcwd()
    
    print(f"Scanning {directory} for file extensions...")
    ext_counts = scan_directory(directory)
    
    # Sort by count (descending)
    sorted_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)
    
    print("\nFile extensions found (most common first):")
    print("-" * 40)
    print(f"{'Extension':<10} {'Count':<10}")
    print("-" * 40)
    
    for ext, count in sorted_exts:
        print(f"{ext:<10} {count:<10}")
    
    print("\nScan complete.")

if __name__ == "__main__":
    main()
