from pathlib import Path


BOARD_CONFIG = {
    "nucleo_wba65ri": {
        "svd": "STM32WBA65.svd",
        "pyocd_target": "stm32wba65rivx",
    },
    "nucleo_wba55cg": {
        "svd": "STM32WBA55.svd",
        "pyocd_target": "stm32wba55cgux",
    },
    "nucleo_wba25ce1": {
        "svd": "STM32WBA25.svd",
        "pyocd_target": "stm32wba25ceux",
    },
    "nucleo_wb09ke": {
        "svd": "STM32WB09.svd",
        "pyocd_target": "stm32wb09kevx",
    },
}


def read_board(build_dir):
    cache_file = Path(build_dir) / "CMakeCache.txt"
    if not cache_file.is_file():
        raise ValueError(f"No CMakeCache.txt found in build directory: {build_dir}")

    cache_values = {}
    for line in cache_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(("BOARD:STRING=", "CACHED_BOARD:STRING=")):
            key, value = line.split("=", 1)
            cache_values[key.split(":", 1)[0]] = value.strip()

    board = cache_values.get("BOARD") or cache_values.get("CACHED_BOARD")
    if not board:
        raise ValueError(f"No BOARD entry found in {cache_file}")

    return board.split("/", 1)[0]