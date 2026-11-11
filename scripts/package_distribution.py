"""Create a source-free deployment archive; never read the user's .env."""

import argparse
import io
import re
import tarfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", default="myselfabii")
    parser.add_argument("--version", default="0.2.0")
    args = parser.parse_args()
    version = args.version.removeprefix("v")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]+", args.namespace):
        parser.error("Use a lowercase Docker Hub namespace")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        parser.error("Use a stable MAJOR.MINOR.PATCH version")
    root = Path(__file__).resolve().parents[1]
    example = (root / "deploy/.env.images.example").read_text()
    for variable, image in [
        ("TOLLGATE_IMAGE", "tollgate"),
        ("TOLLGATE_DASHBOARD_IMAGE", "tollgate-dashboard"),
    ]:
        example = re.sub(
            rf"(?m)^{variable}=.*$",
            f"{variable}={args.namespace}/{image}:{version}",
            example,
        )
    example = example.replace("namespace: myselfabii", "namespace: " + args.namespace)
    files = {
        "compose.yml": (root / "deploy/compose.images.yml").read_bytes(),
        ".env.example": example.encode(),
        "README.md": (root / "docs/image-distribution.md").read_bytes(),
        "LICENSE": (root / "LICENSE").read_bytes(),
    }
    target = root / "dist/tollgate-deployment.tar.gz"
    target.parent.mkdir(exist_ok=True)
    with tarfile.open(target, "w:gz") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo("tollgate-deployment/" + name)
            info.size, info.mode = len(data), 0o644
            archive.addfile(info, io.BytesIO(data))
    print(f"Created {target}; configuration/docs only, no credentials or source code")


if __name__ == "__main__":
    main()
