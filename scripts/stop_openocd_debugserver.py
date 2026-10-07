import argparse
import sys
from pathlib import Path

from openocd_server_process import stop_server


def main():
    parser = argparse.ArgumentParser(description="Stop the managed West/OpenOCD process tree.")
    parser.add_argument("--pid-file", type=Path, required=True)
    args = parser.parse_args()

    try:
        stop_server(args.pid_file)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"OpenOCD cleanup failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())