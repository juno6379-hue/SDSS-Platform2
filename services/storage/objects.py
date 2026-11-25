"""Private S3 objects addressed by institution and verified SHA-256."""

from __future__ import annotations

import base64
import os
import tempfile
from contextlib import closing
from hashlib import file_digest, sha256
from pathlib import Path
from urllib.parse import urlsplit

from .store import DIGEST, INSTITUTION, StorageError, checked

CHUNK_SIZE = 1024**2
MAX_LINK_SECONDS = 900


def object_key(institution, digest):
    checked(INSTITUTION, institution)
    checked(DIGEST, digest)
    return f"{institution}/sha256/{digest[:2]}/{digest}"


def checked_endpoint(value, *, internal=False):
    if value is None:
        return None
    url = urlsplit(value)
    if (
        not url.hostname
        or url.netloc != url.netloc.lower()
        or url.username is not None
        or url.password is not None
        or url.path not in ("", "/")
        or url.query
        or url.fragment
        or (
            url.scheme != "https"
            and not (
                url.scheme == "http"
                and url.hostname
                in (
                    {"127.0.0.1", "::1", "localhost", "objects"}
                    if internal
                    else {"127.0.0.1", "::1", "localhost"}
                )
            )
        )
    ):
        raise StorageError("STORAGE_ENDPOINT_INVALID")
    return value


class ObjectStore:
    def __init__(self, client, bucket, *, signer=None):
        if not bucket:
            raise StorageError("STORAGE_BUCKET_REQUIRED")
        self.client = client
        self.signer = signer or client
        self.bucket = bucket

    @classmethod
    def from_env(cls):
        import boto3
        from botocore.config import Config

        endpoint = checked_endpoint(os.getenv("SDSS_STORAGE_S3_ENDPOINT"), internal=True)
        sign_value = os.getenv("SDSS_STORAGE_S3_SIGN_ENDPOINT")
        sign_endpoint = checked_endpoint(sign_value) if sign_value else checked_endpoint(endpoint)
        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"} if endpoint else None,
            connect_timeout=5,
            read_timeout=30,
            retries={"mode": "standard", "max_attempts": 3},
        )
        client = boto3.client("s3", endpoint_url=endpoint, config=config)
        signer = (
            client
            if endpoint == sign_endpoint
            else boto3.client("s3", endpoint_url=sign_endpoint, config=config)
        )
        return cls(client, os.getenv("SDSS_STORAGE_BUCKET"), signer=signer)

    def put(self, institution, path, digest, byte_count):
        from botocore.exceptions import ClientError

        key = object_key(institution, digest)
        with Path(path).open("rb") as handle:
            if (
                file_digest(handle, "sha256").hexdigest() != digest
                or os.fstat(handle.fileno()).st_size != byte_count
            ):
                raise StorageError("STORAGE_LOCAL_PIN_MISMATCH")
            handle.seek(0)
            encoded_digest = base64.b64encode(bytes.fromhex(digest)).decode("ascii")
            try:
                self.client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=handle,
                    ContentLength=byte_count,
                    ChecksumSHA256=encoded_digest,
                    IfNoneMatch="*",
                    Metadata={"sha256": digest},
                )
            except ClientError as error:
                status = error.response["ResponseMetadata"]["HTTPStatusCode"]
                if status not in {409, 412}:
                    raise
        self.verify(institution, digest, byte_count)
        return key

    def verify(self, institution, digest, byte_count, output=None):
        """Check content rather than a backend-specific ETag, streaming optionally to output."""
        reply = self.client.get_object(Bucket=self.bucket, Key=object_key(institution, digest))
        with closing(reply["Body"]) as stream:
            if reply["ContentLength"] != byte_count:
                raise StorageError("STORAGE_REMOTE_CONTENT_MISMATCH")
            hashed = sha256()
            transferred = 0
            while chunk := stream.read(CHUNK_SIZE):
                transferred += len(chunk)
                if transferred > byte_count:
                    raise StorageError("STORAGE_REMOTE_CONTENT_MISMATCH")
                hashed.update(chunk)
                if output is not None:
                    output.write(chunk)
        if transferred != byte_count or hashed.hexdigest() != digest:
            raise StorageError("STORAGE_REMOTE_CONTENT_MISMATCH")

    def export_asset(self, institution, digest, byte_count, directory):
        key = object_key(institution, digest)
        target = Path(directory) / key.rsplit("/", 1)[-1]
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as output:
            temporary = Path(output.name)
            try:
                self.verify(institution, digest, byte_count, output)
            except Exception:
                output.close()
                temporary.unlink()
                raise
        try:
            os.link(temporary, target)
        finally:
            temporary.unlink()

    def download_link(self, transaction, kind, key, purpose, *, expires_in=300):
        """Resolve the object only through an authorized institution's recorded asset."""
        if type(expires_in) is not int or not 1 <= expires_in <= MAX_LINK_SECONDS:
            raise StorageError("STORAGE_LINK_TTL_INVALID")
        asset = transaction.get_asset(kind, key, purpose)
        if asset is None:
            raise StorageError("STORAGE_ASSET_NOT_FOUND")
        object_name = object_key(transaction.institution, asset["sha256"])
        head = self.client.head_object(Bucket=self.bucket, Key=object_name)
        if (
            head["ContentLength"] != asset["byte_count"]
            or head["Metadata"].get("sha256") != asset["sha256"]
        ):
            raise StorageError("STORAGE_REMOTE_CONTENT_MISMATCH")
        params = {"Bucket": self.bucket, "Key": object_name}
        if version := head.get("VersionId"):
            if version != "null":
                params["VersionId"] = version
        url = self.signer.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in)
        return {"url": url, "expires_in_seconds": expires_in, **asset}
