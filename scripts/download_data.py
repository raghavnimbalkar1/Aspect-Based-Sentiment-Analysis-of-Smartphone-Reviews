"""Download the fixed public source version; never extract untrusted ZIP paths."""

import hashlib
import io
import sys
import urllib.request
from pathlib import Path
from zipfile import ZipFile

from smartphone_absa.data import FILES, audit_source

URL = (
    "https://www.kaggle.com/api/v1/datasets/download/grikomsn/"
    "amazon-cell-phones-reviews?dataset_version_number=2"
)


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw/grikomsn-v2")
    target.mkdir(parents=True, exist_ok=True)
    if all((target / name).is_file() for name in FILES):
        audit_source(target)
        print(f"Verified existing files in {target}")
        return
    request = urllib.request.Request(URL, headers={"User-Agent": "smartphone-absa/0.1"})
    with urllib.request.urlopen(request, timeout=90) as response:
        archive = response.read(64 * 1024 * 1024 + 1)
    if len(archive) > 64 * 1024 * 1024:
        raise ValueError("Download exceeded the expected size limit")
    with ZipFile(io.BytesIO(archive)) as zipped:
        for name, expected in FILES.items():
            content = zipped.read(name)
            if hashlib.sha256(content).hexdigest() != expected:
                raise ValueError(f"Source checksum mismatch: {name}")
            (target / name).write_bytes(content)
    audit_source(target)
    print(f"Downloaded and verified {len(FILES)} files in {target}")


if __name__ == "__main__":
    main()
