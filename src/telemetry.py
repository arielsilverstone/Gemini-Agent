# ============================================================================
#  File: telemetry.py
#  Version: 1.0 (Fixed & Complete)
#  Purpose: Internal telemetry for Gemini-Agent (timing, usage, resource)
#  Created: 29JUL25 | Fixed: 31JUL25
# ============================================================================
# SECTION 1: Global Variables
# ============================================================================
#
import time
import csv
import json
import os
import psutil
from datetime import datetime

TELEMETRY_CSV = os.path.join('logs', 'telemetry.csv')
if not os.path.exists('logs'):
    os.makedirs('logs')
#
# ============================================================================
# SECTION 2: Timing Decorator
# ============================================================================
# Function 2.1: record_telemetry
# Purpose: Decorator to record timing, memory, and CPU usage for agent
#          actions.
# ============================================================================
#
def record_telemetry(agent, action):

    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.time()
            process = psutil.Process(os.getpid())
            mem_before = process.memory_info().rss
            cpu_before = process.cpu_percent(interval=None)
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            mem_after = process.memory_info().rss
            cpu_after = process.cpu_percent(interval=None)
            row = {
                'datetime': datetime.now().isoformat(),
                'agent': agent,
                'action': action,
                'elapsed_sec': round(elapsed, 3),
                'mem_mb': round((mem_after - mem_before) / 1048576, 3),
                'cpu_pct': cpu_after - cpu_before
            }
            with open(TELEMETRY_CSV, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                if f.tell() == 0:
                    writer.writeheader()
                writer.writerow(row)
            return result
        return wrapper
    return decorator
#
# ============================================================================
# SECTION 3: Usage Counter
# ============================================================================
# Function 3.1: increment_usage
# Purpose: Increment usage count for a specific agent-action pair.
# ============================================================================
#
USAGE_FILE = os.path.join('logs', 'usage.json')
def increment_usage(agent, action):

    if os.path.exists(USAGE_FILE):
        with open(USAGE_FILE, 'r') as f:
            usage = json.load(f)
    else:
        usage = {}
    key = f'{agent}:{action}'
    usage[key] = usage.get(key, 0) + 1
    with open(USAGE_FILE, 'w') as f:
        json.dump(usage, f, indent=2)
    return usage[key]
#
#
## End of Script
