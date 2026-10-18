import argparse
import json
import sys
import time
from urllib.parse import urlsplit

import duckdb

from s3_client import BASE, CONFIG, credentials


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def connect():
    extensions = BASE / '.extensions'
    extensions.mkdir(exist_ok=True)
    db = duckdb.connect(config={'extension_directory': str(extensions)})
    db.execute('set threads=2')
    db.execute("set memory_limit='1GB'")
    db.execute('install httpfs')
    db.execute('load httpfs')
    access, secret = credentials()
    endpoint = urlsplit(CONFIG['endpoint'])
    db.execute(f"""
        create secret rustfs (
            type s3,
            key_id {quote(access)},
            secret {quote(secret)},
            region 'us-east-1',
            endpoint {quote(endpoint.netloc)},
            url_style 'path',
            use_ssl {'true' if endpoint.scheme == 'https' else 'false'}
        )
    """)
    return db


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='duckdb')
    parser.add_argument('--setup', action='store_true')
    args = parser.parse_args()
    started = time.perf_counter()
    with connect() as db:
        if args.setup:
            print('duckdb: httpfs готов')
            return
        output = BASE / 'results' / args.output
        output.mkdir(parents=True, exist_ok=True)
        print(f'duckdb: s3://{CONFIG["bucket"]}/{CONFIG["object_key"]}', flush=True)
        db.execute((BASE / 'sql/prepare.sql').read_text())
        db.execute((BASE / 'sql/frequencies.sql').read_text())
        ids = [row[0] for row in db.execute('select vacancy_id from selected order by vacancy_id').fetchall()]
        (output / 'selected_ids.json').write_text(json.dumps(ids))
        unique, occurrences = {}, {}
        for k in (1, 2, 3):
            cursor = db.execute(f'select skills, frequency from counts_{k} order by skills')
            unique[k] = occurrences[k] = 0
            with (output / f'skills_{k}.jsonl').open('w') as stream:
                while batch := cursor.fetchmany(2000):
                    for skills, frequency in batch:
                        stream.write(json.dumps({'skills': skills, 'frequency': frequency}, ensure_ascii=False) + '\n')
                        unique[k] += 1
                        occurrences[k] += frequency
            print(f'k={k}: сочетаний {unique[k]}, вхождений {occurrences[k]}', flush=True)
        db.execute(f'copy selected to {quote(output / "selected.csv")} (header, delimiter \',\')')
    summary = {
        'variant': 2, 'source': f's3://{CONFIG["bucket"]}/{CONFIG["object_key"]}',
        'duckdb_version': duckdb.__version__, 'selected_rows': len(ids),
        'unique_combinations': unique, 'combination_occurrences': occurrences,
        'elapsed_s': round(time.perf_counter() - started, 3)
    }
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print('вакансий:', len(ids))
    print(f'время: {summary["elapsed_s"]} с')
    print('результаты:', output.relative_to(BASE))


if __name__ == '__main__':
    main()
