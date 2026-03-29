#!/usr/bin/env python
"""Slideshow Generator - Run from project root"""

import sys
import os
from pathlib import Path


def main():
    project_root = Path(__file__).parent
    script_dir = project_root / "slideshow-generator"
    sys.path.insert(0, str(script_dir))

    from generate_slideshow import main as slideshow_main

    slideshow_main()


if __name__ == "__main__":
    main()
