"""Allow ``python -m winclip``."""

import sys

from winclip.adapters.driving.cli import main

if __name__ == "__main__":
    sys.exit(main())
