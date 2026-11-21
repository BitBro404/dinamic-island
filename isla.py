#!/usr/bin/env python3
"""Isla dinámica: lanzador. El código está en el paquete isla_dinamica/."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from isla_dinamica.main import main  # noqa: E402

if __name__ == "__main__":
    main()
