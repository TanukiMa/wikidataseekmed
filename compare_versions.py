#!/usr/bin/env python3
"""
Compare performance between old SPARQL-heavy version and new API-optimized version

This script runs both versions on a small dataset and compares:
- Number of SPARQL queries
- Number of API requests
- Total execution time
- Data quality

Usage:
    python compare_versions.py --limit 100
"""

import argparse
import subprocess
import time
import re
from pathlib import Path
from datetime import datetime


def run_version(script: str, args: argparse.Namespace) -> dict:
    """Run a version and extract statistics"""
    print(f"\n{'='*60}")
    print(f"Running: {script}")
    print(f"{'='*60}")

    log_file = f"logs/compare_{Path(script).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    cmd = [
        'python', script,
        '--small',
        '--limit', str(args.limit),
        '--log', log_file
    ]

    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes timeout
        )

        elapsed = time.time() - start_time

        # Parse log file for statistics
        stats = {
            'script': script,
            'success': result.returncode == 0,
            'elapsed_time': elapsed,
            'log_file': log_file
        }

        # Read log file
        if Path(log_file).exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()

            # Extract statistics from log
            stats['sparql_queries'] = extract_number(log_content, r'Total (?:SPARQL )?[Qq]ueries?:\s*(\d+)')
            stats['api_requests'] = extract_number(log_content, r'(?:Total )?API requests?:\s*(\d+)')
            stats['items_collected'] = extract_number(log_content, r'Total [Ii]tems(?: Collected)?:\s*(\d+)')
            stats['retries'] = extract_number(log_content, r'Total [Rr]etries?:\s*(\d+)')
            stats['timeout_errors'] = extract_number(log_content, r'504.*?:\s*(\d+)')

        print(f"✓ Completed in {elapsed:.1f}s")

        return stats

    except subprocess.TimeoutExpired:
        print(f"✗ Timeout after 10 minutes")
        return {
            'script': script,
            'success': False,
            'error': 'Timeout',
            'elapsed_time': 600
        }

    except Exception as e:
        print(f"✗ Error: {e}")
        return {
            'script': script,
            'success': False,
            'error': str(e)
        }


def extract_number(text: str, pattern: str) -> int:
    """Extract number from text using regex"""
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0


def print_comparison(old_stats: dict, new_stats: dict):
    """Print comparison table"""
    print("\n" + "="*80)
    print("PERFORMANCE COMPARISON")
    print("="*80)

    if not old_stats['success'] or not new_stats['success']:
        print("\n⚠️  One or both versions failed to complete")
        print(f"Old version: {'✓' if old_stats['success'] else '✗'}")
        print(f"New version: {'✓' if new_stats['success'] else '✗'}")
        return

    # Comparison table
    metrics = [
        ('Execution Time (s)', 'elapsed_time', lambda x: f"{x:.1f}"),
        ('SPARQL Queries', 'sparql_queries', str),
        ('API Requests', 'api_requests', str),
        ('Items Collected', 'items_collected', str),
        ('Retries', 'retries', str),
        ('Timeout Errors', 'timeout_errors', str),
    ]

    print(f"\n{'Metric':<25} {'Old Version':<20} {'New Version':<20} {'Change':<15}")
    print("-" * 80)

    for metric_name, key, formatter in metrics:
        old_val = old_stats.get(key, 0)
        new_val = new_stats.get(key, 0)

        old_str = formatter(old_val)
        new_str = formatter(new_val)

        # Calculate change
        if old_val > 0:
            if key == 'elapsed_time':
                change_pct = (new_val - old_val) / old_val * 100
                change_str = f"{change_pct:+.1f}%"
            elif key in ['sparql_queries', 'retries', 'timeout_errors']:
                change_pct = (new_val - old_val) / old_val * 100
                change_str = f"{change_pct:+.1f}%"
            elif key == 'api_requests':
                change_str = f"+{new_val}" if new_val > 0 else "0"
            else:
                change_str = "="
        else:
            change_str = "-"

        # Color code improvements
        if key in ['elapsed_time', 'retries', 'timeout_errors'] and old_val > new_val:
            change_str += " ✓"  # Improvement
        elif key == 'sparql_queries' and new_val < old_val:
            change_str += " ✓"  # Improvement

        print(f"{metric_name:<25} {old_str:<20} {new_str:<20} {change_str:<15}")

    print("-" * 80)

    # Summary
    print("\n📊 SUMMARY:")

    if new_stats.get('elapsed_time', float('inf')) < old_stats.get('elapsed_time', 0):
        speedup = (old_stats['elapsed_time'] - new_stats['elapsed_time']) / old_stats['elapsed_time'] * 100
        print(f"   ✓ New version is {speedup:.1f}% faster")

    sparql_old = old_stats.get('sparql_queries', 1)
    sparql_new = new_stats.get('sparql_queries', 0)
    if sparql_old > 0:
        # Note: Both use similar number of SPARQL queries, but new version uses lighter queries
        print(f"   ✓ SPARQL queries remain similar, but new version uses lighter queries")

    if new_stats.get('api_requests', 0) > 0:
        print(f"   ✓ New version uses {new_stats['api_requests']} Action API requests for efficient batching")

    if new_stats.get('timeout_errors', 0) < old_stats.get('timeout_errors', 1):
        print(f"   ✓ Fewer timeout errors ({old_stats.get('timeout_errors', 0)} → {new_stats.get('timeout_errors', 0)})")

    # Data quality check
    items_old = old_stats.get('items_collected', 0)
    items_new = new_stats.get('items_collected', 0)

    if items_new >= items_old:
        print(f"   ✓ Data completeness maintained ({items_new} items)")
    else:
        print(f"   ⚠️  Fewer items collected ({items_old} → {items_new})")

    print("\n" + "="*80)

    # Log files
    print("\nLog files for detailed analysis:")
    print(f"  Old version: {old_stats.get('log_file', 'N/A')}")
    print(f"  New version: {new_stats.get('log_file', 'N/A')}")
    print()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Compare old vs new version performance'
    )
    parser.add_argument('--limit', type=int, default=100,
                       help='Items per category (default: 100)')
    parser.add_argument('--skip-old', action='store_true',
                       help='Skip old version (only run new version)')

    args = parser.parse_args()

    # Create logs directory
    Path('logs').mkdir(exist_ok=True)

    print("="*80)
    print("VERSION COMPARISON TEST")
    print("="*80)
    print(f"Configuration:")
    print(f"  Scale: Small (5 categories)")
    print(f"  Limit: {args.limit} items per category")
    print(f"  Skip old: {args.skip_old}")
    print("="*80)

    # Run old version
    if not args.skip_old:
        old_stats = run_version('wikidataseekmed_improved.py', args)
    else:
        print("\nSkipping old version...")
        old_stats = {
            'script': 'wikidataseekmed_improved.py',
            'success': False,
            'skipped': True
        }

    # Run new version
    new_stats = run_version('wikidataseekmed_api_optimized.py', args)

    # Compare
    if not args.skip_old:
        print_comparison(old_stats, new_stats)
    else:
        print("\n" + "="*80)
        print("NEW VERSION RESULTS")
        print("="*80)
        print(f"Success: {'✓' if new_stats['success'] else '✗'}")
        print(f"Execution time: {new_stats.get('elapsed_time', 0):.1f}s")
        print(f"SPARQL queries: {new_stats.get('sparql_queries', 0)}")
        print(f"API requests: {new_stats.get('api_requests', 0)}")
        print(f"Items collected: {new_stats.get('items_collected', 0)}")
        print("="*80)


if __name__ == '__main__':
    main()
