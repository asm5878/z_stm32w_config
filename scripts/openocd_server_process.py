import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def _read_record(pid_file):
    try:
        return json.loads(pid_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as error:
        raise ValueError(f"Cannot read OpenOCD process record {pid_file}: {error}") from error


def _windows_process_identity(pid):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.QueryFullProcessImageNameW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    kernel32.QueryFullProcessImageNameW.restype = ctypes.c_int
    kernel32.GetProcessTimes.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    kernel32.GetProcessTimes.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int

    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return None

    try:
        image_path = ctypes.create_unicode_buffer(32768)
        image_path_size = ctypes.c_ulong(len(image_path))
        if not kernel32.QueryFullProcessImageNameW(
            handle, 0, image_path, ctypes.byref(image_path_size)
        ):
            return None

        class FileTime(ctypes.Structure):
            _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]

        creation_time = FileTime()
        exit_time = FileTime()
        kernel_time = FileTime()
        user_time = FileTime()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation_time),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        ):
            return None

        started = (creation_time.high << 32) | creation_time.low
        return str(Path(image_path.value).resolve()), started
    finally:
        kernel32.CloseHandle(handle)


def _posix_process_identity(pid):
    if sys.platform.startswith("linux"):
        process_dir = Path(f"/proc/{pid}")
        command_line = process_dir.joinpath("cmdline").read_bytes().split(b"\0")
        command = [item.decode(errors="replace") for item in command_line if item]
        stat = process_dir.joinpath("stat").read_text(encoding="utf-8")
        started = stat.rsplit(")", 1)[1].split()[19]
        return command, started

    command = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        check=False,
        capture_output=True,
        text=True,
    )
    started = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="],
        check=False,
        capture_output=True,
        text=True,
    )
    if command.returncode != 0 or started.returncode != 0:
        return None
    return command.stdout.strip(), started.stdout.strip()


def _process_matches(record):
    pid = record.get("pid")
    executable = record.get("executable")
    started = record.get("started")
    if not isinstance(pid, int) or pid <= 0 or not isinstance(executable, str) or started is None:
        raise ValueError("Invalid OpenOCD process record")

    expected = str(Path(executable).resolve())
    try:
        if os.name == "nt":
            identity = _windows_process_identity(pid)
            return (
                identity is not None
                and identity[0].casefold() == expected.casefold()
                and identity[1] == started
            )

        identity = _posix_process_identity(pid)
        if identity is None or os.getsid(pid) != pid or identity[1] != started:
            return False
        if isinstance(identity[0], list):
            return expected in identity[0]
        return expected in identity[0]
    except (OSError, ProcessLookupError, PermissionError):
        return False


def _remove_record(pid_file, expected_pid):
    record = _read_record(pid_file)
    if record and record.get("pid") == expected_pid:
        pid_file.unlink(missing_ok=True)


def _write_record(pid_file, record):
    temporary_file = pid_file.with_name(pid_file.name + ".tmp")
    try:
        temporary_file.write_text(json.dumps(record), encoding="utf-8")
        os.replace(temporary_file, pid_file)
    finally:
        temporary_file.unlink(missing_ok=True)


def run_server(command, pid_file):
    pid_file = Path(pid_file)
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    old_record = _read_record(pid_file)
    if old_record:
        if _process_matches(old_record):
            raise RuntimeError(f"Managed OpenOCD server already runs with PID {old_record['pid']}")
        pid_file.unlink(missing_ok=True)

    process = subprocess.Popen(command, start_new_session=os.name != "nt")
    identity = (
        _windows_process_identity(process.pid)
        if os.name == "nt"
        else _posix_process_identity(process.pid)
    )
    if identity is None:
        process.terminate()
        process.wait()
        raise RuntimeError(f"Could not inspect West process {process.pid}")

    record = {
        "pid": process.pid,
        "executable": str(Path(command[0]).resolve()),
        "started": identity[1],
        "stop_requested": False,
    }
    temporary_file = pid_file.with_name(pid_file.name + ".tmp")
    try:
        temporary_file.write_text(json.dumps(record), encoding="utf-8")
        os.replace(temporary_file, pid_file)
    except OSError:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise

    try:
        exit_code = process.wait()
        current_record = _read_record(pid_file)
        if (
            current_record
            and current_record.get("pid") == process.pid
            and current_record.get("stop_requested")
        ):
            return 0
        return exit_code
    finally:
        temporary_file.unlink(missing_ok=True)
        _remove_record(pid_file, process.pid)


def stop_server(pid_file, timeout=5):
    pid_file = Path(pid_file)
    record = _read_record(pid_file)
    if not record:
        print("No managed OpenOCD server is running.")
        return

    pid = record.get("pid")
    if not _process_matches(record):
        _remove_record(pid_file, pid)
        print("Removed stale OpenOCD process record.")
        return

    record["stop_requested"] = True
    _write_record(pid_file, record)

    if os.name == "nt":
        taskkill = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "taskkill.exe"
        result = subprocess.run(
            [str(taskkill), "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and _process_matches(record):
            record["stop_requested"] = False
            _write_record(pid_file, record)
            raise RuntimeError(result.stderr.strip() or "Could not stop the West/OpenOCD process tree")
    else:
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    deadline = time.monotonic() + timeout
    while _process_matches(record) and time.monotonic() < deadline:
        time.sleep(0.1)
    if _process_matches(record):
        record["stop_requested"] = False
        _write_record(pid_file, record)
        raise RuntimeError(f"West process {pid} is still running after cleanup")

    deadline = time.monotonic() + timeout
    while pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    if pid_file.exists():
        _remove_record(pid_file, pid)
    print(f"Stopped West/OpenOCD process tree (PID {pid}).")