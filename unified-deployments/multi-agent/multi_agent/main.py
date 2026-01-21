"""
Main entry point for the DGX Spark Multi-Agent system.
"""

import os
import sys


def main():
    """Main entry point."""
    from .server import main as run_server
    run_server()


if __name__ == "__main__":
    main()
