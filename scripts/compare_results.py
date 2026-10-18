import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def read_counts(path):
    with path.open() as stream:
        return {tuple(row['skills']): row['frequency'] for row in map(json.loads, stream)}


def read_ids(path):
    return set(json.loads((path / 'selected_ids.json').read_text()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', default='mapreduce')
    parser.add_argument('--right', default='duckdb')
    args = parser.parse_args()
    left, right = [BASE / 'results' / name for name in (args.left, args.right)]
    a, b = read_ids(left), read_ids(right)
    report = {
        'left': args.left, 'right': args.right,
        'selected_ids_match': a == b, 'selected_ids_differences': sorted(a ^ b),
        'comparisons': []
    }
    print(f'сверка: {args.left} и {args.right}')
    for k in (1, 2, 3):
        ca, cb = [read_counts(path / f'skills_{k}.jsonl') for path in (left, right)]
        delta = sorted(key for key in ca.keys() | cb.keys() if ca.get(key) != cb.get(key))
        report['comparisons'].append({
            'k': k, 'keys_left': len(ca), 'keys_right': len(cb), 'differences': len(delta),
            'examples': [{'skills': key, 'left': ca.get(key), 'right': cb.get(key)} for key in delta[:10]]
        })
        print(f'k={k}: ключей {len(ca)}/{len(cb)}, расхождений {len(delta)}')
    report['all_equal'] = a == b and all(row['differences'] == 0 for row in report['comparisons'])
    name = f'comparison_{args.left}_{args.right}.json'.replace('/', '_')
    (BASE / 'evidence' / name).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('вакансии совпадают:', 'да' if a == b else 'нет')
    print('результаты совпадают:', 'да' if report['all_equal'] else 'нет')
    if not report['all_equal']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
