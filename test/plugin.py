# ============================================================================
# File: plugin.py
# Purpose: Pytest plugin for comprehensive test tracking and reporting.
# Created: 28JUL25 | Refactored: 02AUG25
# ============================================================================
# Section 1: Imports and configurations
# ============================================================================
#
import pytest
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, cast
from pathlib import Path
from .test_logging import test_stats, TestEvent, TEST_RUN_ID, LOG_DIR, RESULTS_FILE

# Configure logging for the plugin
import logging
logger = logging.getLogger('pytest_plugin')
#
# ============================================================================
# Section 2: Plugin hooks
# ============================================================================
# Method 2.1: pytest_configure
# ============================================================================
#
def pytest_configure(config):
    """Configure pytest plugin and test statistics tracking."""
    # Add custom markers
    config.addinivalue_line(
        "markers",
        "webtest: mark test as webtest to run with web service"
    )

    # Store test stats on the config object
    config.test_stats = test_stats
    config.test_run_id = TEST_RUN_ID

    # Create a run-specific log file for pytest output
    run_log = LOG_DIR / f'pytest_{TEST_RUN_ID}.log'
    handler = logging.FileHandler(run_log, mode='w', encoding='utf-8')
    handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(handler)
    logger.info(f"Starting test run {TEST_RUN_ID}")

    # Set up terminal reporting
    config.option.tbstyle = "auto"
    config.option.verbose = 2
#
# ============================================================================
# Method 2.2: pytest_runtest_protocol
# Purpose: Handle test execution protocol with timing and logging.
# ============================================================================
#
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_protocol(item, nextitem):

    test_name = item.nodeid
    start_time = time.time()

    # Log test start
    test_stats.start_test(test_name)
    logger.info(f"Starting test: {test_name}")

    # Run the test
    outcome = yield

    # Log test completion
    duration = time.time() - start_time
    logger.info(f"Completed test: {test_name} in {duration:.3f}s")
#
# ============================================================================
# Method 2.3: pytest_runtest_makereport
# Purpose: Process test results and log detailed information.
# ============================================================================
#
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):

    outcome = yield
    result = outcome.get_result()

    test_name = item.nodeid
    when = result.when
    duration = result.duration

    # Prepare event details
    details = {
        'when': when,
        'outcome': result.outcome,
        'nodeid': result.nodeid,
        'keywords': dict(item.keywords),
        'user_properties': dict(item.user_properties),
        'location': f"{item.fspath}:{item.location[1]}",
        'test_doc': item.obj.__doc__ or '',
        'test_module': item.module.__name__ if hasattr(item, 'module') else '',
        'test_class': item.cls.__name__ if hasattr(item, 'cls') and item.cls else ''
    }

    # Handle different test phases
    if when == "setup":
        if result.failed:
            message = f"Setup failed: {str(result.longrepr)}"
            test_stats.end_test(test_name, 'error', message, details)
        return

    elif when == "call":
        if result.passed:
            message = "Test passed"
            outcome = 'pass'
        elif result.failed:
            message = str(result.longrepr)
            outcome = 'fail'

            # Add failure details
            if hasattr(result, 'longrepr') and hasattr(result.longrepr, 'reprcrash'):
                details['failure'] = {
                    'message': str(result.longrepr.reprcrash),
                    'traceback': str(result.longrepr.reprtraceback)
                }
        else:
            message = result.wasxfail or "Test skipped"
            outcome = 'skip'

    elif when == "teardown":
        if result.failed:
            message = f"Teardown failed: {str(result.longrepr)}"
            test_stats.end_test(test_name, 'error', message, details)
        return

    # Record the test result
    test_stats.end_test(test_name, outcome, message, details)

    # Log detailed failure information
    if outcome in ('fail', 'error'):
        logger.error(f"Test {outcome.upper()}: {test_name}\n{message}",
                   extra={'test_name': test_name, 'outcome': outcome})
    elif outcome == 'skip':
        logger.warning(f"Test SKIPPED: {test_name} - {message}",
                     extra={'test_name': test_name, 'outcome': 'skip'})
#
# ============================================================================
# Method 2.4: pytest_sessionfinish
# Purpose: Save test results and generate reports when session finishes.
# ============================================================================
#
@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):



    # Save detailed test results
    results_file = RESULTS_FILE.with_name(f'test_results_{TEST_RUN_ID}.json')
    test_stats.save_results(results_file)

    # Generate summary report
    stats = test_stats.get_stats()

    # Print summary to console
    print("\n" + "="*80)
    print(f"TEST SESSION COMPLETED - Run ID: {TEST_RUN_ID}")
    print(f"Started:  {stats['start_time']}")
    print(f"Finished: {stats['end_time']}")
    print("="*80)
    print(f"Total tests:    {stats['total_tests']:4d}")
    print(f"Passed:         {stats['passed']:4d} ({stats['success_rate']:.1f}%)")
    print(f"Failed:         {stats['failed']:4d}")
    print(f"Skipped:        {stats['skipped']:4d}")
    print(f"Errors:         {stats['errors']:4d}")
    print("-"*80)
    print(f"Duration:       {stats['duration_seconds']:8.2f} seconds")
    print(f"Tests/second:   {stats['tests_per_second']:8.2f}")
    print("="*80)
    print(f"Detailed logs:  {results_file}")
    print("="*80)

    # Log completion
    logger.info(f"Test session completed with status: {exitstatus}")
    logger.info(f"Results saved to: {results_file}")

    # Generate HTML report if we have failures
    if stats['failed'] > 0 or stats['errors'] > 0:
        generate_html_report(stats, results_file)
#
# ============================================================================
# Method 2.5: generate_html_report
# Purpose: Generate an HTML report of test results.
# ============================================================================
#
def generate_html_report(stats: Dict[str, Any], results_file: Path) -> None:

    try:
        report_file = results_file.with_suffix('.html')
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Test Results - {TEST_RUN_ID}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }}
                    .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
                    .pass {{ color: green; }}
                    .fail {{ color: red; }}
                    .error {{ color: orange; }}
                    .skip {{ color: blue; }}
                    table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                    th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                    th {{ background-color: #f2f2f2; }}
                    tr:hover {{ background-color: #f5f5f5; }}
                </style>
            </head>
            <body>
                <h1>Test Results - {TEST_RUN_ID}</h1>
                <div class="summary">
                    <h2>Summary</h2>
                    <p><strong>Started:</strong> {stats['start_time']}</p>
                    <p><strong>Finished:</strong> {stats['end_time']}</p>
                    <p><strong>Duration:</strong> {stats['duration_seconds']:.2f} seconds</p>
                    <p>
                        <span class="pass">Passed: {stats['passed']}</span> |
                        <span class="fail">Failed: {stats['failed']}</span> |
                        <span class="error">Errors: {stats['errors']}</span> |
                        <span class="skip">Skipped: {stats['skipped']}</span>
                    </p>
                    <p><strong>Success Rate:</strong> {stats['success_rate']:.1f}%</p>
                </div>

                <h2>Performance Metrics</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Average Duration</td><td>{stats['avg_duration']:.3f}s</td></tr>
                    <tr><td>Min Duration</td><td>{stats['min_duration']:.3f}s</td></tr>
                    <tr><td>Max Duration</td><td>{stats['max_duration']:.3f}s</td></tr>
                    <tr><td>Median Duration</td><td>{stats['median_duration']:.3f}s</td></tr>
                    <tr><td>Tests per Second</td><td>{stats['tests_per_second']:.2f}</td></tr>
                </table>

                <p>Detailed results available in: <code>{results_file}</code></p>
            </body>
            </html>
            """)

        logger.info(f"HTML report generated: {report_file}")
        print(f"\nHTML report: file://{report_file.resolve()}")

    except Exception as e:
        logger.error(f"Failed to generate HTML report: {str(e)}")
#
#
## End of Script
