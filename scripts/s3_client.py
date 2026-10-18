import hashlib
import io
import json
import os
from functools import cache
from pathlib import Path

import boto3
from botocore.config import Config

BASE = Path(__file__).resolve().parents[1]
CONFIG = json.loads((BASE / 'config.json').read_text())
if (BASE / 'config.local.json').exists():
    CONFIG.update(json.loads((BASE / 'config.local.json').read_text()))


def credentials():
    access = os.getenv('RUSTFS_ACCESS_KEY')
    secret = os.getenv('RUSTFS_SECRET_KEY')
    if access and secret:
        return access, secret
    path = Path(os.getenv('RUSTFS_ENV_FILE', BASE / '.env'))
    values = dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line)
    return values['RUSTFS_ACCESS_KEY'], values['RUSTFS_SECRET_KEY']


@cache
def storage():
    access, secret = credentials()
    return boto3.client(
        's3', endpoint_url=CONFIG['endpoint'], region_name='us-east-1',
        aws_access_key_id=access, aws_secret_access_key=secret,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'})
    )


class Body(io.RawIOBase):
    def __init__(self, stream):
        super().__init__()
        self.stream = stream
        self.sha256 = hashlib.sha256()
        self.bytes_read = 0

    def readable(self):
        return True

    def readinto(self, buffer):
        data = self.stream.read(min(len(buffer), 65536))
        self.sha256.update(data)
        self.bytes_read += len(data)
        buffer[:len(data)] = data
        return len(data)


def open_object(key):
    return storage().get_object(Bucket=CONFIG['bucket'], Key=key)['Body']


def upload(path, key):
    data = path.read_bytes()
    storage().put_object(Bucket=CONFIG['bucket'], Key=key, Body=data)
    return {'key': key, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
