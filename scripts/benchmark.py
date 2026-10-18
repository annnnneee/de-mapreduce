import argparse
import csv
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import psutil

from compare_results import read_counts, read_ids

BASE = Path(__file__).resolve().parents[1]


def measure(command, log):
    started = time.perf_counter()
    peak = samples = 0
    with log.open('w') as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
        root = psutil.Process(process.pid)
        while process.poll() is None:
            rss = 0
            try:
                for item in [root] + root.children(recursive=True):
                    try:
                        rss += item.memory_info().rss
                    except psutil.NoSuchProcess:
                        pass
            except psutil.NoSuchProcess:
                pass
            peak = max(peak, rss)
            samples += 1
            time.sleep(0.05)
        if process.wait():
            raise RuntimeError(f'ошибка запуска, лог: {log.relative_to(BASE)}')
    return round(time.perf_counter() - started, 3), round(peak / 1024 ** 2, 2), samples


def verify(output):
    reference = BASE / 'results/mapreduce'
    for k in (1, 2, 3):
        if read_counts(output / f'skills_{k}.jsonl') != read_counts(reference / f'skills_{k}.jsonl'):
            raise ValueError(f'частоты не совпали: k={k}')
    if read_ids(output) != read_ids(reference):
        raise ValueError('выборки вакансий не совпали')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--label', default='main')
    parser.add_argument('--mr-workers', type=int, default=2)
    parser.add_argument('--chunk-rows', type=int, default=1000)
    args = parser.parse_args()
    if args.runs < 3:
        parser.error('нужно минимум три запуска')
    target = BASE / 'evidence' / f'benchmark_{args.label}'
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for attempt in range(1, args.runs + 1):
        for method in ('mapreduce', 'duckdb'):
            output = f'benchmark_{args.label}/{method}_{attempt}'
            command = [sys.executable, str(BASE / 'scripts' / f'run_{method}.py'), '--output', output]
            if method == 'mapreduce':
                command += ['--workers', str(args.mr_workers), '--chunk-rows', str(args.chunk_rows)]
            print(f'{method}: запуск {attempt}/{args.runs}', flush=True)
            elapsed, peak, samples = measure(command, target / f'{method}_{attempt}.log')
            verify(BASE / 'results' / output)
            rows.append({
                'method': method, 'attempt': attempt, 'elapsed_s': elapsed,
                'peak_tree_rss_mib': peak, 'rss_samples': samples, 'exit_code': 0,
                'results_verified': True, 'workers': args.mr_workers if method == 'mapreduce' else 2,
                'chunk_rows': args.chunk_rows if method == 'mapreduce' else None
            })
            print(f'время: {elapsed:.3f} с, память: {peak:.2f} mib, сверка: совпало', flush=True)
            (target / 'attempts.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    with (target / 'attempts.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    summary = {}
    print('метод       медиана, с    максимум rss, mib')
    for method in ('mapreduce', 'duckdb'):
        group = [row for row in rows if row['method'] == method]
        median = statistics.median(row['elapsed_s'] for row in group)
        peak = max(row['peak_tree_rss_mib'] for row in group)
        summary[method] = {
            'attempts': len(group), 'median_elapsed_s': median, 'max_peak_tree_rss_mib': peak
        }
        print(f'{method:10} {median:10.3f} {peak:20.2f}')
    (target / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print('логи:', target.relative_to(BASE))


if __name__ == '__main__':
    main()
