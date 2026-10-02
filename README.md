# STM32 Wireless Debugging

## 1. GDB, OpenOCD, and PyOCD

### 1.1 Roles in a Zephyr debug session

GDB is the debugger: it reads symbols and source information from the Zephyr
ELF, controls execution, sets breakpoints, and inspects threads, variables,
and registers. GDB does not speak directly to the board's debug probe. It
connects to a GDB server, which translates GDB remote-protocol requests into
probe and target operations over SWD.

OpenOCD and PyOCD are alternative GDB server programs; Zephyr provides runner
plugins that invoke them. West selects the runner recorded for the build or
the runner specified with `-r`; the runner starts the server, handles
target-specific operations, and connects GDB. OpenOCD is used when its
host-side support is available for the board and probe. PyOCD provides a
Python-based server for supported debug probes and target devices. They
provide the hardware-facing layer; GDB provides the interactive source-level
debugging experience.

### 1.2 Where the tools come from

- **GDB and OpenOCD:** supplied as native host tools by the Zephyr SDK. OpenOCD
  is under the SDK's `hosttools/openocd` directory; its executable and scripts
  are recorded in the build's `zephyr/runners.yaml`. Inspect that file or run
  `west debug --context -d <build-dir> -r openocd` to view runner settings.
- **PyOCD:** a Python dependency installed in the Zephyr workspace virtual
  environment. In this Windows workspace the executable is
  `.venv/Scripts/pyocd.exe`. Activate that environment before invoking PyOCD
  directly. West's `pyocd` runner uses the Python package from its environment.

If PyOCD does not recognize an MCU, update/search the pack index and install
the matching CMSIS Device Family Pack (DFP) from that environment:

```powershell
.\.venv\Scripts\pyocd.exe pack find --update "STM32WB09KE*"
.\.venv\Scripts\pyocd.exe pack install --update "STM32WB09KE*"
.\.venv\Scripts\pyocd.exe list --targets
```

For example, PyOCD maps `STM32WB09KEVx` to target `stm32wb09kevx`; the
`Keil.STM32WB0x_DFP` pack is needed if that target is not available locally.
Use the MCU-specific pack pattern appropriate for other target devices.

### 1.3 West debug, attach, and GDB commands

#### 1.3.1 GDB environment and initialization

Run these commands from the Zephyr workspace root in PowerShell. Set `HOME` so
Windows GDB can find the user's `.gdbinit` file:

```powershell
$env:HOME = $env:USERPROFILE
```

Use `$HOME/.gdbinit` for GDB commands that should apply to every debug session,
whether GDB is started by West or Cortex-Debug. For example:

```gdb
# $HOME/.gdbinit
set pagination off
```

For both GUI and command-line sessions, make sure `HOME` is set in the Windows
user environment before starting VS Code, and in any PowerShell session used
for West.

West `debug` uses the selected runner to load the image onto the target, reset
the SoC, and start an interactive GDB session. West `attach` connects GDB to
the image already running on the target without resetting the SoC or
reflashing. The default debug runner is recorded in the build's
`zephyr/runners.yaml`; pass `-r openocd` or `-r pyocd` to select one explicitly.
`--no-rebuild` prevents West from rebuilding/reconfiguring before starting the
runner; it does not change whether the runner loads or resets the target.

```powershell
# Launch/debug with either runner
west debug -d build_dbg_tester -r openocd --no-rebuild
west debug -d build_dbg_tester -r pyocd --no-rebuild

# Attach without reflashing
west attach -d build_dbg_tester -r openocd --no-rebuild --cmd-pre-init "set NO_RESET_ATTACH 1"
west attach -d build_dbg_tester -r pyocd --no-rebuild
```

The current build's runner settings are authoritative. For example, the
OpenOCD runner is configured to load the ELF for debug, while the recorded
PyOCD options include `--no-load` and attach mode. OpenOCD's non-reset attach
command is board/patch dependent; the documented STM32WBA path has been used
for WBA55CG and WBA65RI. The PyOCD target is currently configured in
`runners.yaml`; the GUI prompts for it separately.

West starts GDB for the selected runner. At the GDB prompt, the most useful
commands are:

| Command | Purpose |
| --- | --- |
| `break main` or `break function_name` | Set a breakpoint. |
| `continue` (`c`) | Resume execution until the next breakpoint or stop. |
| `next` (`n`) / `step` (`s`) | Execute one source line, stepping over/into calls. |
| `finish` | Run until the current function returns. |
| `bt` | Show the current call stack. |
| `info threads` / `thread <n>` | List Zephyr threads / select one. |
| `info locals` / `print expression` | Inspect local variables / evaluate an expression. |
| `info registers` | Inspect CPU registers. |
| `monitor reset halt` | Reset and halt the target; use for launch, not when preserving an attached target's state. |
| `detach` / `quit` | Detach from the target / exit GDB. |

## 2. Zephyr GUI debugging setup

### 2.1 Clone the GUI workspace

Clone this repository inside the Zephyr west workspace so it is a sibling of
`zephyr`, `.venv`, and the build directory. Open the workspace file, not just
the repository folder:

```powershell
Set-Location 'C:\path\to\zephyrproject' # Replace with your actual west workspace root.
git clone https://github.com/asm5878/z_stm32w_config.git
code .\z_stm32w_config\z_stm32w_config.code-workspace
```

The workspace refers to its Zephyr parent root by the name `zephyrproject`.
Keep that root name or update the `${workspaceFolder:zephyrproject}` references
if changing the workspace configuration.

### 2.2 VSCode extension and application configurations

Install the VS Code **Cortex-Debug** extension (`marus25.cortex-debug`),
available from Extensions. The workspace also recommends the C/C++ extension
pack and Embedded Tools. Keep a matching Zephyr ELF available at the selected
build directory's `zephyr/zephyr.elf`; the GUI uses it for symbols and source
mapping.

For a debug-capable Zephyr application, use at least:

```ini
CONFIG_DEBUG=y
CONFIG_DEBUG_OPTIMIZATIONS=y
CONFIG_THREAD_NAME=y
CONFIG_DEBUG_THREAD_INFO=y
```

The PyOCD target names currently verified by the installed PyOCD target index
are:

| Zephyr board | PyOCD target |
| --- | --- |
| `nucleo_wba65ri` | `stm32wba65rivx` |
| `nucleo_wba55cg` | `stm32wba55cgux` |
| `nucleo_wb09ke` | `stm32wb09kevx` |

The WBA65 board has received the most extensive debug testing. Target names
identify MCU parts, not Zephyr board names. WB09 may require installing the
DFP described in section 1.2.

### 2.3 VS Code GUI: Cortex-Debug

The GUI uses the same GDB and hardware-facing OpenOCD/PyOCD mechanisms as the
command line. Cortex-Debug is the graphical front end: it starts the configured
prelaunch task, connects GDB to `localhost:3333`, and presents source stepping,
breakpoints, variables, registers, and threads in VS Code. It is not a
different debug protocol or a replacement for the runner/server.

Open **Run and Debug** (`Ctrl+Shift+D`), choose a profile, and press **F5**.
The current profiles are:

| Profile | Behavior |
| --- | --- |
| `Debug (PyOCD)` | Starts PyOCD in `under-reset` mode at 1 MHz, runs the WBA65RI PyOCD hook, connects GDB, then sends `monitor reset halt`. It does not load the ELF; the target must already run the desired firmware. |
| `Debug (OpenOCD)` | Starts West's OpenOCD debug server and sends GDB `load` to program the selected ELF. |
| `Attach (PyOCD)` | Starts PyOCD in `attach` mode and connects GDB without loading the ELF. The current WBA65RI hook calls `board.target.halt()` on connection, so the target is halted. |
| `Attach (OpenOCD)` | Starts West's OpenOCD debug server with `NO_RESET_ATTACH` and halt commands; GDB attaches without loading the ELF. |

PyOCD profiles prompt for `device`; enter the target from the table in section
2.2. Both server types use GDB port `3333`; PyOCD also uses telnet port `4444`.
Run only one server at a time. Its background task remains active until stopped.

The current profiles use GDB at
`%USERPROFILE%/zephyr-sdk-1.0.1/gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-gdb-py.exe`
and all use the fixed SVD path
`C:/MyTools/STM32CubeCLT_1.22.0/STMicroelectronics_CMSIS_SVD/STM32WBA65.svd`.
The SVD is WBA65-specific; verify both paths exist on the host. The automatic
board-to-SVD selection is not implemented yet.

### 2.4 Sample application to test stdby debugging

Standby behavior is covered by the `dbg_tester` application. It alternates a
30-second busy phase and a 30-second sleep/standby phase; while both threads
are blocked, Zephyr power management can enter standby. See
[`dbg_tester/README.rst`](https://github.com/asm5878/z_applications/blob/main/dbg_tester/README.rst),
[`prj.conf`](https://github.com/asm5878/z_applications/blob/main/dbg_tester/prj.conf),
and
[`stm32wba_pwr_optim.overlay`](https://github.com/asm5878/z_applications/blob/main/dbg_tester/boards/stm32wba_pwr_optim.overlay).
Set breakpoints in `busy_thread()` or `stdby_thread()` and continue through the
alternating phases. Function breakpoints can also be set on
`set_mode_suspend_to_ram_enter()` and `set_mode_suspend_to_ram_exit()` in the
STM32WBA power-management code. If the debugger reaches both functions, it is
properly tracking standby entry and resume.

### 2.5 External Zephyr changes

The West runner workflows depend on external STM32 Wireless changes to Zephyr
for reliable `west debug` and `west attach`, particularly the OpenOCD
non-reset attach path. These changes are not supplied by cloning
`z_stm32w_config`; they are proposed in the currently unmerged
[Zephyr pull request #121062](https://github.com/zephyrproject-rtos/zephyr/pull/121062).
Until it is merged, retrieve the PR branch from its author's fork and apply its
five commits to your Zephyr checkout:

```sh
git remote add stm32wbax-pr https://github.com/asm5878/zephyr.git
git fetch stm32wbax-pr stm32wbax_stdby_debug
git cherry-pick fa9cd4be40e5e0951a85da2df497e7fd428c7d58
git cherry-pick 9136126531311f1ab97592ce4af2d7d4a3f77971
git cherry-pick e4a2710964f08d4a95cfec186c958bdad0d788b4
git cherry-pick 4c0aea4e67039260b672dee350b61552c0605e38
git cherry-pick d2842f2817ab2a308bf34b83bf1d5bd92357099d
```

Run the cherry-pick commands in order. If you already added the remote, skip
the `remote add` command. Without these changes, the commands or board-specific
reset/attach behavior may not work as documented.

## 3. Official documentation

- [Zephyr `west build`](https://docs.zephyrproject.org/latest/develop/west/build-flash-debug.html#building-west-build)
- [Zephyr `west flash`](https://docs.zephyrproject.org/latest/develop/west/build-flash-debug.html#flashing-west-flash)
- [Zephyr `west debug` and `west attach`](https://docs.zephyrproject.org/latest/develop/west/build-flash-debug.html#debugging-west-debug-west-debugserver)
- [GNU GDB manual](https://sourceware.org/gdb/current/onlinedocs/gdb.html/)
- [PyOCD documentation](https://pyocd.io/docs/)
- [OpenOCD User's Guide](https://openocd.org/doc/html/)

## 4. TODO

1. Extend and validate support across all STM32 Wireless boards; WBA65RI is the
  board tested most intensively so far.
2. Remove machine-specific paths, especially GDB, OpenOCD, PyOCD hook, and SVD
  paths, from the workspace configuration.
3. Select the SVD file automatically from the selected board/MCU.
4. Select the correct PyOCD target automatically from the Zephyr board instead
  of prompting the user for `device`.
5. Identify, track, and upstream the external Zephyr patches needed for
  reliable West `debug` and `attach` support across the STM32 Wireless boards.
6. Test the debug workflows in Git Bash and Linux Bash shells.