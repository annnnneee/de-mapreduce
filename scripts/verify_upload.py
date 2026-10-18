import hashlib
import json
import time

from s3_client import BASE, CONFIG, open_object


def main():
    expected = json.loads((BASE / 'evidence/source_profile.json').read_text())
    started = time.perf_counter()
    digest = hashlib.sha256()
    size = 0
    print(f's3: {CONFIG["bucket"]}/{CONFIG["object_key"]}', flush=True)
    with open_object(CONFIG['object_key']) as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(data)
            size += len(data)
    valid = size == expected['source_bytes'] and digest.hexdigest() == expected['source_sha256']
    report = {
        'object': f's3://{CONFIG["bucket"]}/{CONFIG["object_key"]}',
        'bytes_read': size, 'sha256': digest.hexdigest(), 'integrity_ok': valid,
        'elapsed_s': round(time.perf_counter() - started, 3)
    }
    (BASE / 'evidence/upload_verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('байт:', size)
    print('sha256:', digest.hexdigest())
    print('файл совпадает:', 'да' if valid else 'нет')
    if not valid:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
