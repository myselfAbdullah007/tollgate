"""Create a source-free deployment archive; never read the user's .env."""

import argparse
import io
import re
import tarfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", default="myselfabii")
    tags = parser.add_mutually_exclusive_group()
    tags.add_argument("--version", help="Stable release version, optionally prefixed with v")
    tags.add_argument("--image-tag", help="latest or an exact sha-<40 hex digits> image tag")
    args = parser.parse_args()
    version = args.version.removeprefix("v") if args.version is not None else None
    image_tag = version if version is not None else args.image_tag
    if image_tag is None:
        image_tag = "latest"
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]+", args.namespace):
        parser.error("Use a lowercase Docker Hub namespace")
    if version is not None and not re.fullmatch(r"\d+\.\d+\.\d+", version):
        parser.error("Use a stable MAJOR.MINOR.PATCH version")
    if version is None and not re.fullmatch(r"latest|sha-[0-9a-f]{40}", image_tag):
        parser.error("Use latest or sha- followed by an exact 40-character commit hash")
    root = Path(__file__).resolve().parents[1]
    example = (root / "deploy/.env.images.example").read_text()
    for variable, image in [
        ("TOLLGATE_IMAGE", "tollgate"),
        ("TOLLGATE_DASHBOARD_IMAGE", "tollgate-dashboard"),
    ]:
        example = re.sub(
            rf"(?m)^{variable}=.*$",
            f"{variable}={args.namespace}/{image}:{image_tag}",
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
