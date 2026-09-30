import boto3
import pytest
from moto import mock_aws

from pgbackup.config import S3Config
from pgbackup.storage.local import LocalStorage
from pgbackup.storage.s3 import S3Storage


def test_local_roundtrip(tmp_path):
    src = tmp_path / "src.dump"
    src.write_bytes(b"payload")
    storage = LocalStorage(tmp_path / "store")

    storage.put(str(src), "a.dump")
    assert "a.dump" in storage.list_keys()

    out = tmp_path / "out.dump"
    storage.get("a.dump", str(out))
    assert out.read_bytes() == b"payload"

    storage.delete("a.dump")
    assert storage.list_keys() == []


def test_local_missing_get_raises(tmp_path):
    storage = LocalStorage(tmp_path / "store")
    with pytest.raises(FileNotFoundError):
        storage.get("nope", str(tmp_path / "x"))


def test_local_list_filters_by_suffix(tmp_path):
    storage = LocalStorage(tmp_path / "store")
    (storage.base / "a.json").write_text("{}")
    (storage.base / "a.dump").write_bytes(b"x")
    assert storage.list_keys(suffix=".json") == ["a.json"]


@mock_aws
def test_s3_roundtrip(tmp_path):
    bucket = "pgbackup-test-bucket"
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=bucket)
    storage = S3Storage(S3Config(bucket=bucket, prefix="pgbackup", region="us-east-1"))

    src = tmp_path / "f.dump"
    src.write_bytes(b"data")
    storage.put(str(src), "x.dump")

    assert storage.list_keys(suffix=".dump") == ["x.dump"]
    assert storage.location("x.dump") == f"s3://{bucket}/pgbackup/x.dump"

    out = tmp_path / "out.dump"
    storage.get("x.dump", str(out))
    assert out.read_bytes() == b"data"

    storage.delete("x.dump")
    assert storage.list_keys() == []


@mock_aws
def test_s3_list_ignores_sibling_prefixes(tmp_path):
    bucket = "pgbackup-test-bucket"
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket=bucket)
    storage = S3Storage(S3Config(bucket=bucket, prefix="pgbackup", region="us-east-1"))

    src = tmp_path / "f.json"
    src.write_text("{}")
    storage.put(str(src), "real.json")
    client.put_object(Bucket=bucket, Key="pgbackup-archive/foreign.json", Body=b"{}")
    client.put_object(Bucket=bucket, Key="pgbackupNOTES.json", Body=b"{}")

    assert storage.list_keys(suffix=".json") == ["real.json"]
