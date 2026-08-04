#!/bin/bash
# TuLite 数据备份脚本
# 用法：./backup.sh [备份目录]
# 默认备份到 ./backups，保留最近 10 份。
set -euo pipefail

cd "$(dirname "$0")"

DATA_DIR="${TULITE_DATA_DIR:-data}"
BACKUP_DIR="${1:-backups}"
KEEP=10

if [ ! -d "$DATA_DIR" ]; then
  echo "错误：找不到数据目录 $DATA_DIR" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="$BACKUP_DIR/tulite-data-$STAMP.tar.gz"

# SQLite 需要一致性快照：直接打包正在写入的库可能存到半个事务。
# 有 sqlite3 命令时用官方 .backup 生成快照，替换进归档；否则直接打包并提示。
SNAP_DIR=""
cleanup() { [ -n "$SNAP_DIR" ] && rm -rf "$SNAP_DIR"; }
trap cleanup EXIT

TAR_ARGS=(--exclude="$DATA_DIR/logs")

snapshot_sqlite() {
  # $1=源库 $2=目标。优先 sqlite3 CLI，否则用 python3 的 sqlite3 模块（同一套 backup API）。
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$1" ".backup '$2'"
  elif command -v python3 >/dev/null 2>&1; then
    python3 - "$1" "$2" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
# 必须以读写方式打开：WAL 模式下只读连接无法建立 WAL 索引，
# 会静默备份出一个空库。
s = sqlite3.connect(src)
d = sqlite3.connect(dst)
try:
    s.backup(d)
    n = d.execute(
        "select count(*) from sqlite_master where type='table'"
    ).fetchone()[0]
    src_n = s.execute(
        "select count(*) from sqlite_master where type='table'"
    ).fetchone()[0]
    if src_n and not n:
        sys.exit("快照为空库，备份中止")
finally:
    d.close()
    s.close()
PY
  else
    return 1
  fi
}

if [ -f "$DATA_DIR/tasks.sqlite3" ]; then
  SNAP_DIR="$(mktemp -d -t tulite-snap-XXXXXX)"
  mkdir -p "$SNAP_DIR/$DATA_DIR"
  if snapshot_sqlite "$DATA_DIR/tasks.sqlite3" "$SNAP_DIR/$DATA_DIR/tasks.sqlite3"; then
    # 排除活动库与 WAL/SHM，改用一致性快照
    TAR_ARGS+=(
      --exclude="$DATA_DIR/tasks.sqlite3"
      --exclude="$DATA_DIR/tasks.sqlite3-wal"
      --exclude="$DATA_DIR/tasks.sqlite3-shm"
    )
    # 分两步：--exclude 会作用于所有成员，若同一条 tar 命令里追加快照，
    # 快照也会被同名 exclude 规则吃掉。先打包再追加，最后压缩。
    RAW_TAR="$SNAP_DIR/archive.tar"
    tar -cf "$RAW_TAR" "${TAR_ARGS[@]}" "$DATA_DIR"
    tar -rf "$RAW_TAR" -C "$SNAP_DIR" "$DATA_DIR/tasks.sqlite3"
    gzip -c "$RAW_TAR" > "$ARCHIVE"
  else
    echo "提示：无 sqlite3 / python3，任务库为直接打包；建议在服务空闲时备份。" >&2
    tar -czf "$ARCHIVE" "${TAR_ARGS[@]}" "$DATA_DIR"
  fi
else
  tar -czf "$ARCHIVE" "${TAR_ARGS[@]}" "$DATA_DIR"
fi

chmod 600 "$ARCHIVE"
echo "已备份到 $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

# 清理旧备份，仅保留最近 $KEEP 份
COUNT=$(ls -1t "$BACKUP_DIR"/tulite-data-*.tar.gz 2>/dev/null | wc -l | tr -d ' ')
if [ "$COUNT" -gt "$KEEP" ]; then
  ls -1t "$BACKUP_DIR"/tulite-data-*.tar.gz | tail -n +$((KEEP + 1)) | while read -r old; do
    rm -f "$old"
    echo "已清理旧备份 $(basename "$old")"
  done
fi
