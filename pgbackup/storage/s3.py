from __future__ import annotations

from pgbackup.config import S3Config


class S3Storage:
    def __init__(self, cfg: S3Config) -> None:
        import boto3

        self.cfg = cfg
        self.client = boto3.client("s3", region_name=cfg.region, endpoint_url=cfg.endpoint_url)

    def _key(self, key: str) -> str:
        prefix = self.cfg.prefix.strip("/")
        return f"{prefix}/{key}" if prefix else key

    def put(self, local_path: str, key: str) -> None:
        self.client.upload_file(local_path, self.cfg.bucket, self._key(key))

    def get(self, key: str, local_path: str) -> None:
        self.client.download_file(self.cfg.bucket, self._key(key), local_path)

    def list_keys(self, suffix: str = "") -> list[str]:
        prefix = self.cfg.prefix.strip("/")
        token = None
        keys: list[str] = []
        while True:
            kwargs = {"Bucket": self.cfg.bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            resp = self.client.list_objects_v2(**kwargs)
            for obj in resp.get("Contents", []):
                name = obj["Key"].split("/")[-1]
                if name.endswith(suffix):
                    keys.append(name)
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return sorted(keys)

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.cfg.bucket, Key=self._key(key))

    def location(self, key: str) -> str:
        return f"s3://{self.cfg.bucket}/{self._key(key)}"
