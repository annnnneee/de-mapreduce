import argparse
import csv
import itertools
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from compare_results import read_counts

BASE = Path(__file__).resolve().parents[1]
OUTPUT = BASE / 'results/analysis'


def salary(row):
    if row['currency'] not in ('RUR', 'RUB') or row['gross'] != 'false':
        return None
    low = float(row['salary_from']) if row['salary_from'] else None
    high = float(row['salary_to']) if row['salary_to'] else None
    values = [value for value in (low, high) if value is not None and value > 0]
    if not values or (low is not None and high is not None and low > high):
        return None
    return statistics.mean(values)


def read_jobs():
    with (BASE / 'results/duckdb/selected.csv').open(newline='') as stream:
        return [
            (row['area'], sorted({s.strip().lower() for s in row['key_skills'].split(';') if s.strip()}), salary(row))
            for row in csv.DictReader(stream)
        ]


def save(name, rows):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def salary_analysis(jobs, size, minimum):
    frequencies = {}
    for k in (1, 2, 3):
        frequencies.update(read_counts(BASE / 'results/mapreduce' / f'skills_{k}.jsonl'))
    salaries = defaultdict(list)
    for _, skills, value in jobs:
        if value is not None:
            for k in (1, 2, 3):
                for combination in itertools.combinations(skills, k):
                    salaries[combination].append(value)
    rows = []
    for skills, values in salaries.items():
        if len(skills) != size or len(values) < minimum:
            continue
        base = max(itertools.combinations(skills, size - 1), key=lambda key: frequencies[key])
        median = statistics.median(values)
        baseline = statistics.median(salaries[base])
        rows.append({
            'skills': ' + '.join(skills), 'base': ' + '.join(base),
            'added_skill': next(skill for skill in skills if skill not in base),
            'vacancies': frequencies[skills], 'salary_count': len(values),
            'base_vacancies': frequencies[base], 'base_salary_count': len(salaries[base]),
            'base_median': round(baseline, 2), 'median': round(median, 2),
            'difference': round(median - baseline, 2),
            'difference_pct': round(100 * (median / baseline - 1), 2)
        })
    rows.sort(key=lambda row: (-row['difference_pct'], row['skills']))
    print(f'зарплаты: вакансий {len(jobs)}, рублёвых зарплат на руки {sum(value is not None for _, _, value in jobs)}')
    print(f'размер сочетания: {size}, минимум зарплат: {minimum}')
    if not rows:
        print('нет сочетаний с нужным числом зарплат')
        return
    name = 'salary_pairs.csv' if size == 2 else 'salary_triples.csv'
    save(name, rows)
    for title, sign in [('рост медианы', 1), ('снижение медианы', -1)]:
        selected = [row for row in rows if row['difference_pct'] * sign > 0]
        selected.sort(key=lambda row: -row['difference_pct'] * sign)
        print(title)
        for row in selected[:3]:
            print('  ' + row['skills'])
            print(f'  база {row["base"]}: {row["base_median"]:.0f} → {row["median"]:.0f} руб, '
                  f'{row["difference_pct"]:+.1f}%, n={row["salary_count"]}')
    print('результаты:', (OUTPUT / name).relative_to(BASE))


def region_analysis(jobs):
    regions = [region for region, _ in Counter(region for region, _, _ in jobs).most_common(3)]
    overview, top = [], []
    for region in regions:
        subset = [(skills, value) for area, skills, value in jobs if area == region]
        values = [value for _, value in subset if value is not None]
        frequencies = {k: Counter() for k in (1, 2, 3)}
        salaries = defaultdict(list)
        for skills, value in subset:
            for k in frequencies:
                combinations = list(itertools.combinations(skills, k))
                frequencies[k].update(combinations)
                if value is not None:
                    for combination in combinations:
                        salaries[combination].append(value)
        overview.append({
            'region': region, 'vacancies': len(subset),
            'with_skills': sum(bool(skills) for skills, _ in subset),
            'salary_count': len(values), 'salary_share_pct': round(100 * len(values) / len(subset), 2),
            'median_salary': statistics.median(values) if values else '',
            'skill_occurrences': sum(frequencies[1].values()),
            'pair_occurrences': sum(frequencies[2].values()),
            'triple_occurrences': sum(frequencies[3].values())
        })
        for k, counter in frequencies.items():
            for skills, frequency in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:5]:
                values = salaries[skills]
                top.append({
                    'region': region, 'size': k, 'skills': ' + '.join(skills),
                    'frequency': frequency, 'share_pct': round(100 * frequency / len(subset), 2),
                    'salary_count': len(values),
                    'median_salary': statistics.median(values) if values else ''
                })
    save('regions.csv', overview)
    save('region_skills.csv', top)
    print('регион                  вакансий  зарплат  медиана, руб')
    for row in overview:
        median = f'{row["median_salary"]:.0f}' if row['median_salary'] != '' else 'нет данных'
        print(f'{row["region"]:24} {row["vacancies"]:7} {row["salary_count"]:8} {median:>12}')
    print('самые частые сочетания')
    for region in regions:
        print(region)
        for k in (1, 2, 3):
            row = next(item for item in top if item['region'] == region and item['size'] == k)
            median = f'{row["median_salary"]:.0f}' if row['median_salary'] != '' else 'нет данных'
            print(f'  k={k}: {row["skills"]}, частота {row["frequency"]}, зарплат {row["salary_count"]}, медиана {median} руб')
    print('результаты: results/analysis/regions.csv, results/analysis/region_skills.csv')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['salary', 'regions'])
    parser.add_argument('--size', type=int, choices=[2, 3], default=2)
    parser.add_argument('--min-count', type=int, default=10)
    args = parser.parse_args()
    jobs = read_jobs()
    if args.mode == 'salary':
        salary_analysis(jobs, args.size, args.min_count)
    else:
        region_analysis(jobs)


if __name__ == '__main__':
    main()
