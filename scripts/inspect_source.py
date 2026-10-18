import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from s3_client import BASE, CONFIG


def main():
    config = CONFIG
    source = Path(config['source'])
    if not source.is_absolute():
        source = BASE / source
    digest = hashlib.sha256()
    with source.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    pattern = re.compile(config['title_regex'])
    counts, regions, currencies, gross = Counter(), Counter(), Counter(), Counter()
    identifiers = set()
    examples = []
    with source.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        for row in reader:
            counts['source_rows'] += 1
            if row['role'].strip() != config['role'] or not pattern.search(row['name']):
                continue
            counts['selected_rows'] += 1
            if row['vacancy_id'] in identifiers:
                counts['duplicate_vacancy_ids'] += 1
            identifiers.add(row['vacancy_id'])
            skills = {s.strip().lower() for s in row['key_skills'].split(';') if s.strip()}
            if skills:
                counts['with_skills'] += 1
            if row['salary_from'] or row['salary_to']:
                counts['with_salary'] += 1
                currencies[row['currency'] or '(не указана)'] += 1
                gross[row['gross'] or '(не указан)'] += 1
            regions[row['area']] += 1
            if len(examples) < 10:
                examples.append({k: row[k] for k in ('vacancy_id', 'name', 'role', 'area')})
    counts.setdefault('duplicate_vacancy_ids', 0)
    report = {
        'student': config['student'], 'variant': config['variant'],
        'source': str(source), 'source_bytes': source.stat().st_size,
        'source_sha256': digest.hexdigest(), 'columns': columns,
        'counts': counts,
        'top_regions': regions.most_common(10), 'salary_currencies': currencies,
        'salary_gross': gross, 'examples': examples,
    }
    target = BASE / 'evidence' / 'source_profile.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('студент: Бондаренко Анна Андреевна, вариант 2')
    print('размер csv:', report['source_bytes'], 'байт')
    print('sha256:', report['source_sha256'])
    for key, value in counts.items():
        print(key + ':', value)
    print('регионы:', regions.most_common(3))
    print('профиль:', target)


if __name__ == '__main__':
    main()
