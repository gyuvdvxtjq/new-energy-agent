#!/usr/bin/env python3
"""Fetch a selected public Zenodo record file and write provenance metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "new-energy-research-agent/0.1"})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("record_id")
    parser.add_argument("filename")
    parser.add_argument("--out-dir", type=Path, default=Path("datasets/raw"))
    args = parser.parse_args()

    metadata_url = f"https://zenodo.org/api/records/{args.record_id}"
    record = get_json(metadata_url)
    file_record = next((item for item in record.get("files", []) if item.get("key") == args.filename), None)
    if file_record is None:
        available = ", ".join(item.get("key", "") for item in record.get("files", []))
        raise SystemExit(f"file not found: {args.filename}; available: {available}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.out_dir / args.filename
    download_url = file_record["links"]["self"]
    request = Request(download_url, headers={"User-Agent": "new-energy-research-agent/0.1"})
    digest = hashlib.sha256()
    with urlopen(request, timeout=120) as response, output_path.open("wb") as handle:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            handle.write(chunk)

    manifest = {
        "source_id": f"zenodo:{args.record_id}",
        "record_title": record.get("metadata", {}).get("title"),
        "record_id": args.record_id,
        "filename": args.filename,
        "source_url": f"https://doi.org/10.5281/zenodo.{args.record_id}",
        "download_url": download_url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "size_bytes": output_path.stat().st_size,
        "sha256": digest.hexdigest(),
        "license": record.get("metadata", {}).get("license"),
        "evidence_status": "database_native" if "DFT" in (record.get("metadata", {}).get("title") or "") else "user_provided_public",
    }
    manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
