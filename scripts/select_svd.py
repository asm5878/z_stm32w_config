import argparse
import os
import shutil
import sys
from pathlib import Path

from board_config import BOARD_CONFIG, read_board


def copy_atomic(source, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_name(output.name + ".tmp")
    try:
        shutil.copyfile(source, temporary_output)
        os.replace(temporary_output, output)
    finally:
        if temporary_output.exists():
            temporary_output.unlink()


def select_svd(build_dir, output, selected_build_dir_file, elf_output):
    board = read_board(build_dir)
    board_config = BOARD_CONFIG.get(board)
    if board_config is None:
        supported = ", ".join(sorted(BOARD_CONFIG))
        raise ValueError(f"Unsupported board '{board}'. Supported boards: {supported}")

    elf_source = build_dir / "zephyr" / "zephyr.elf"
    if not elf_source.is_file():
        raise ValueError(f"Zephyr ELF not found for {board}: {elf_source}")

    svd_dir = Path(__file__).resolve().parents[1] / "svd"
    source = svd_dir / board_config["svd"]
    if not source.is_file():
        raise ValueError(f"SVD file for {board} was not found: {source}")

    copy_atomic(source, output)
    copy_atomic(elf_source, elf_output)
    selected_build_dir_file.parent.mkdir(parents=True, exist_ok=True)
    selected_build_dir_file.write_text(f"{build_dir.resolve()}\n", encoding="utf-8")

    return board, source


def main():
    parser = argparse.ArgumentParser(description="Select the SVD matching a Zephyr build board.")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selected-build-dir-file", type=Path, required=True)
    parser.add_argument("--elf-output", type=Path, required=True)
    args = parser.parse_args()

    try:
        board, source = select_svd(
            args.build_dir.resolve(),
            args.output.resolve(),
            args.selected_build_dir_file.resolve(),
            args.elf_output.resolve(),
        )
    except (OSError, ValueError) as error:
        print(f"SVD selection failed: {error}", file=sys.stderr)
        return 1

    print(f"Selected {source.name} for {board}: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())