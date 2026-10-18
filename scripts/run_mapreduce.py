import argparse
import csv
import gzip
import hashlib
import io
import itertools
import json
import re
import sys
import time
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor

from s3_client import BASE, CONFIG, Body, open_object, upload


def map_chunk(rows, fail=False):
    if fail:
        raise RuntimeError('ошибка маппера')
    counts = {k: Counter() for k in (1, 2, 3)}
    ids = []
    pattern = re.compile(CONFIG['title_regex'])
    for row in rows:
        if row['role'].strip() != CONFIG['role'] or not pattern.search(row['name']):
            continue
        skills = sorted({s.strip().lower() for s in row['key_skills'].split(';') if s.strip()})
        ids.append(row['vacancy_id'])
        for k in counts:
            counts[k].update(itertools.combinations(skills, k))
    return counts, ids


def gzip_parts(lines):
    data = gzip.compress(b''.join(lines), mtime=0)
    if len(data) <= 60 * 1024:
        yield data
    elif len(lines) == 1:
        raise ValueError('строка не помещается в порцию')
    else:
        middle = len(lines) // 2
        yield from gzip_parts(lines[:middle])
        yield from gzip_parts(lines[middle:])


def save_to_s3(output):
    folder = output / 's3_parts'
    folder.mkdir(exist_ok=True)
    manifest = {'format': 'jsonl, независимые gzip-порции в указанном порядке', 'files': []}
    for k in (1, 2, 3):
        source = output / f'skills_{k}.jsonl'
        item = {'k': k, 'original_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'parts': []}
        with source.open('rb') as stream:
            while lines := list(itertools.islice(stream, 8000)):
                for data in gzip_parts(lines):
                    number = len(item['parts']) + 1
                    path = folder / f'skills_{k}_part_{number:03}.jsonl.gz'
                    path.write_bytes(data)
                    key = f'results/{output.name}/skills_{k}/{path.name}'
                    item['parts'].append(upload(path, key))
        manifest['files'].append(item)
        print(f's3: k={k}, порций: {len(item["parts"])}', flush=True)
    path = output / 's3_manifest.json'
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return [upload(path, f'results/{output.name}/manifest.json')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chunk-rows', type=int, default=1000)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--output', default='mapreduce')
    parser.add_argument('--inject-failure', action='store_true')
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    if args.chunk_rows < 1 or args.workers < 1:
        parser.error('размер чанка и число процессов должны быть положительными')
    output = BASE / 'results' / args.output
    output.mkdir(parents=True, exist_ok=True)
    counts = {k: Counter() for k in (1, 2, 3)}
    ids, retries = [], []
    rows_read = chunks = 0
    started = time.perf_counter()
    source = f's3://{CONFIG["bucket"]}/{CONFIG["object_key"]}'
    print('mapreduce:', source, flush=True)
    print(f'строк в чанке: {args.chunk_rows}, процессов: {args.workers}', flush=True)
    response = open_object(CONFIG['object_key'])
    body = Body(response)
    stream = io.TextIOWrapper(io.BufferedReader(body), encoding='utf-8-sig', newline='')

    def reduce_job(job, pool):
        number, future, rows, fail = job
        try:
            local, selected = future.result()
        except RuntimeError:
            if not fail:
                raise
            print(f'ошибка маппера: чанк {number}, повтор 1', flush=True)
            retries.append({'chunk': number, 'retry': 1})
            local, selected = pool.submit(map_chunk, rows).result()
        for k in counts:
            counts[k].update(local[k])
        ids.extend(selected)

    try:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            pending = deque()
            reader = csv.DictReader(stream)
            while rows := list(itertools.islice(reader, args.chunk_rows)):
                fail = args.inject_failure and chunks == 0
                pending.append((chunks, pool.submit(map_chunk, rows, fail), rows, fail))
                rows_read += len(rows)
                chunks += 1
                if len(pending) >= 2 * args.workers:
                    reduce_job(pending.popleft(), pool)
            for job in pending:
                reduce_job(job, pool)
    finally:
        response.close()
    expected = json.loads((BASE / 'evidence/source_profile.json').read_text())
    if body.sha256.hexdigest() != expected['source_sha256'] or body.bytes_read != expected['source_bytes']:
        raise ValueError('исходный объект изменился или прочитан не полностью')
    for k, counter in counts.items():
        with (output / f'skills_{k}.jsonl').open('w') as stream:
            for skills, frequency in sorted(counter.items()):
                stream.write(json.dumps({'skills': skills, 'frequency': frequency}, ensure_ascii=False) + '\n')
        print(f'k={k}: сочетаний {len(counter)}, вхождений {sum(counter.values())}', flush=True)
    (output / 'selected_ids.json').write_text(json.dumps(sorted(ids)))
    uploaded = save_to_s3(output) if args.upload else []
    summary = {
        'variant': 2, 'source': source, 'source_sha256': body.sha256.hexdigest(),
        'source_bytes': body.bytes_read, 'source_rows': rows_read, 'selected_rows': len(ids),
        'chunks': chunks, 'chunk_rows': args.chunk_rows, 'workers': args.workers,
        'retries': retries, 'unique_combinations': {k: len(c) for k, c in counts.items()},
        'combination_occurrences': {k: sum(c.values()) for k, c in counts.items()},
        'uploaded': uploaded, 'upload_complete': args.upload,
        'elapsed_s': round(time.perf_counter() - started, 3)
    }
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(f'строк: {rows_read}, вакансий: {len(ids)}, чанков: {chunks}')
    print(f'время: {summary["elapsed_s"]} с')
    print('результаты:', output.relative_to(BASE))
    if args.upload:
        print(f's3: результаты и манифест сохранены в {CONFIG["bucket"]}/results/{output.name}')


if __name__ == '__main__':
    main()
