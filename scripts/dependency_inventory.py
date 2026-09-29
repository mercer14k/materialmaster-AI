"""Capture installed package version/license metadata; no network required."""

import importlib.metadata
import json
from pathlib import Path

python = []
for distribution in importlib.metadata.distributions():
    meta = distribution.metadata
    license_value = (
        meta.get("License-Expression")
        or meta.get("License")
        or "; ".join(value for value in meta.get_all("Classifier", []) if value.startswith("License ::"))
        or "Review upstream LICENSE"
    )
    python.append(
        {
            "name": meta["Name"],
            "version": distribution.version,
            "license_metadata": license_value[:500],
            "homepage": meta.get("Home-page", ""),
        }
    )
frontend = {}
base = Path("apps/web/node_modules/.pnpm")
paths = list(base.glob("*/node_modules/*/package.json")) + list(base.glob("*/node_modules/@*/*/package.json"))
for path in paths:
    try:
        package = json.loads(path.read_text())
    except (ValueError, OSError):
        continue
    if "name" in package and "version" in package:
        key = package["name"] + "@" + package["version"]
        frontend[key] = {
            "name": package["name"],
            "version": package["version"],
            "license_metadata": package.get("license", "Review upstream LICENSE"),
        }
Path("docs/dependency-inventory.json").write_text(
    json.dumps(
        {
            "notice": "Installed metadata, not legal advice or an assertion that metadata is complete. Review license files when distributing binaries.",
            "python": sorted(python, key=lambda item: item["name"].lower()),
            "frontend": sorted(frontend.values(), key=lambda item: item["name"]),
        },
        indent=2,
    )
    + "\n"
)
print(f"Captured {len(python)} Python packages and {len(frontend)} frontend packages")
