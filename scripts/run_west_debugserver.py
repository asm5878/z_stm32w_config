import argparse
import os
import sys
from pathlib import Path

from openocd_server_process import run_server


def main():
    parser = argparse.ArgumentParser(description="Run west debugserver for the selected build.")
    parser.add_argument("--build-dir-file", type=Path, required=True)
    parser.add_argument("--west", type=Path)
    parser.add_argument("--pid-file", type=Path, required=True)
    parser.add_argument("west_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    west_args = args.west_args
    if west_args[:1] == ["--"]:
        west_args = west_args[1:]
    if not west_args or west_args[0] != "debugserver":
        parser.error("west arguments must start with 'debugserver'")

    try:
        if not args.build_dir_file.is_file():
            raise ValueError(
                f"Selected build directory not found: {args.build_dir_file}. "
                "Launch a Cortex-Debug profile to select it first."
            )
        build_dir = Path(args.build_dir_file.read_text(encoding="utf-8").strip()).expanduser()
        if not build_dir.is_dir():
            raise ValueError(f"Selected build directory does not exist: {build_dir}")

        west_path = args.west or (
            Path(sys.prefix)
            / ("Scripts" if os.name == "nt" else "bin")
            / ("west.exe" if os.name == "nt" else "west")
        )
        west = west_path.expanduser()
        if os.name == "nt" and not west.suffix and not west.is_file():
            west = west.with_suffix(".exe")
        west = west.resolve()
        if not west.is_file():
            raise ValueError(f"west executable not found: {west}")

        command = [str(west), west_args[0], "-d", str(build_dir.resolve()), *west_args[1:]]
        return run_server(command, args.pid_file)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"west debugserver launch failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())