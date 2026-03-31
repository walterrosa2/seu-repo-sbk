from __future__ import annotations

import os
import site
import sys
from pathlib import Path


def configure_shared_site_packages() -> None:
    shared_paths = os.getenv("SBK_SHARED_SITE_PACKAGES", "")
    for raw_path in shared_paths.split(os.pathsep):
        candidate = raw_path.strip()
        if candidate and Path(candidate).exists():
            site.addsitedir(candidate)


def main() -> int:
    configure_shared_site_packages()

    from streamlit.web.cli import main as streamlit_main

    sys.argv[0] = "streamlit"
    return int(streamlit_main())


if __name__ == "__main__":
    raise SystemExit(main())
