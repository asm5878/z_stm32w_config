import argparse
import subprocess
import sys
from pathlib import Path

from board_config import BOARD_CONFIG, read_board


def main():
    parser = argparse.ArgumentParser(description="Run PyOCD for the board in a Zephyr build.")
    parser.add_argument("--build-dir-file", type=Path, required=True)
    parser.add_argument("--pyocd", type=Path)
    parser.add_argument("pyocd_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    pyocd_args = args.pyocd_args
    if pyocd_args[:1] == ["--"]:
        pyocd_args = pyocd_args[1:]
    if not pyocd_args or pyocd_args[0] != "gdbserver":
        parser.error("PyOCD arguments must start with 'gdbserver'")

    try:
        if not args.build_dir_file.is_file():
            raise ValueError(
                f"Selected build directory not found: {args.build_dir_file}. "
                "Launch a Cortex-Debug profile to select it first."
            )
        build_dir = Path(args.build_dir_file.read_text(encoding="utf-8").strip()).expanduser()
        if not build_dir.is_dir():
            raise ValueError(f"Selected build directory does not exist: {build_dir}")

        board = read_board(build_dir.resolve())
        board_config = BOARD_CONFIG.get(board)
        if board_config is None:
            supported = ", ".join(sorted(BOARD_CONFIG))
            raise ValueError(f"Unsupported board '{board}'. Supported boards: {supported}")

        pyocd_path = args.pyocd or (
            Path(sys.prefix)
            / ("Scripts" if sys.platform == "win32" else "bin")
            / ("pyocd.exe" if sys.platform == "win32" else "pyocd")
        )
        pyocd = pyocd_path.expanduser().resolve()
        if not pyocd.is_file():
            raise ValueError(f"PyOCD executable not found: {pyocd}")

        command = [str(pyocd), *pyocd_args, "--target", board_config["pyocd_target"]]
        print(f"Using PyOCD target {board_config['pyocd_target']} for {board}", flush=True)
        return subprocess.call(command)
    except (OSError, ValueError) as error:
        print(f"PyOCD target selection failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())