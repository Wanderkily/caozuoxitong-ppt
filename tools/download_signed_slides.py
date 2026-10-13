"""Download ordered Rain Classroom slide images from browser-exported signed URLs.

Usage: python tools/download_signed_slides.py URLS_JSON OUTPUT_DIR
The URL list is temporary and is not copied into the output manifest.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from pathlib import Path
import json
import sys
import time
from urllib.request import Request, urlopen


def download_one(item):
    page, url, out_dir = item
    dest = out_dir / f"page_{page:03d}.jpg"
    error = None
    for attempt in range(3):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=30) as response:
                data = response.read()
                content_type = response.headers.get("Content-Type", "")
            if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
                raise ValueError(f"invalid JPEG ({content_type}, {len(data)} bytes)")
            dest.write_bytes(data)
            return {"page": page, "path": str(dest), "name": dest.name,
                    "size": len(data), "sha256": sha256(data).hexdigest()}
        except Exception as exc:
            error = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"page {page}: {error}")


def main():
    source = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    urls = json.loads(source.read_text(encoding="utf-8"))
    if not urls or not all(isinstance(url, str) and url.startswith("https://") for url in urls):
        raise ValueError("expected a nonempty list of HTTPS slide URLs")
    out_dir.mkdir(parents=True, exist_ok=True)
    items = [(i + 1, url, out_dir) for i, url in enumerate(urls)]
    assets = [None] * len(items)
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(download_one, item): item[0] for item in items}
        for future in as_completed(futures):
            assets[futures[future] - 1] = future.result()
    manifest = {"page_count": len(assets), "assets": assets}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"pages": len(assets), "bytes": sum(a["size"] for a in assets),
                      "manifest": str(out_dir / "manifest.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
