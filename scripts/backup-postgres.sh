#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required"
  exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-./backups}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

DUMP_FILE="$BACKUP_DIR/temu-platform-$STAMP.sql.gz"
pg_dump "$DATABASE_URL" --no-owner --no-privileges | gzip > "$DUMP_FILE"
echo "Backup written to $DUMP_FILE"
export DUMP_FILE

if [[ -n "${BACKUP_S3_BUCKET:-}" ]]; then
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "$PYTHON_BIN is required for optional S3 upload"
    exit 1
  fi
  "$PYTHON_BIN" - <<'PY'
import os
from pathlib import Path
import boto3

dump_file = Path(os.environ["DUMP_FILE"])
bucket = os.environ["BACKUP_S3_BUCKET"]
prefix = os.environ.get("BACKUP_S3_PREFIX", "temu-backups/")
endpoint = os.environ.get("S3_ENDPOINT") or None
region = os.environ.get("S3_REGION") or None
aws_access_key_id = os.environ.get("S3_ACCESS_KEY") or None
aws_secret_access_key = os.environ.get("S3_SECRET_KEY") or None

client = boto3.client(
    "s3",
    endpoint_url=endpoint,
    region_name=region,
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
)
key = f"{prefix.rstrip('/')}/{dump_file.name}"
client.upload_file(str(dump_file), bucket, key)
print(f"Uploaded backup to s3://{bucket}/{key}")
PY
fi
