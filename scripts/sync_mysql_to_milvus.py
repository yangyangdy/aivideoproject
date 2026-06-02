from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import get_settings
from app.db.mysql_client import MySQLClient
from app.services.milvus_service import MilvusService
from app.services.sync_service import SyncService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync vectors from MySQL to Milvus")
    parser.add_argument("--mode", choices=["full", "incremental"], required=True, help="sync mode")
    parser.add_argument("--batch-size", type=int, default=None, help="batch size")
    parser.add_argument("--max-records", type=int, default=None, help="max records to sync for test")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    mysql_client = MySQLClient(settings)
    milvus_service = MilvusService(settings)
    sync_service = SyncService(settings=settings, mysql_client=mysql_client, milvus_service=milvus_service)

    start = datetime.now()
    if args.mode == "full":
        stats = sync_service.run_full_sync(batch_size=args.batch_size, max_records=args.max_records)
    else:
        stats = sync_service.run_incremental_sync(batch_size=args.batch_size, max_records=args.max_records)
    elapsed = (datetime.now() - start).total_seconds()

    print(
        json.dumps(
            {
                "mode": args.mode,
                "total": stats.total,
                "success": stats.success,
                "failed": stats.failed,
                "elapsed_seconds": elapsed,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
