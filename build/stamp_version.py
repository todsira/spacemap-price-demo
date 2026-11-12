"""Stamp web/index.html with a content hash (?v=...) on its local CSS/JS/data links, so
browsers fetch fresh files after every change instead of reusing a cached older copy."""
import hashlib
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
ASSETS = ["css/style.css", "data/layers.js", "js/app.js"]


def main():
    h = hashlib.sha256()
    for a in ASSETS:
        h.update((WEB / a).read_bytes())
    version = h.hexdigest()[:10]
    index = WEB / "index.html"
    html = index.read_text()
    for a in ASSETS:
        html = re.sub(rf'({re.escape(a)})(\?v=[0-9a-z]+)?"', rf'\1?v={version}"', html)
    index.write_text(html)
    print(f"stamped index.html with v={version}")


if __name__ == "__main__":
    main()
