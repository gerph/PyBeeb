# PyBeeb - A simple BBC Micro emulator in Python

## Summary

This is a (partial) emulation of a BBC Micro in Python - it includes emulation
of a 6502 CPU and enough supporting hardware to boot MOS 1.2 and get to the
BASIC prompt.

The emulator is intended for experimentation and learning about the operation
of a simple CPU, within a wimpler Python environment. The emulator has the
ability to 'hook' addresses within the 6502 code and either trace their
use, or modify the behaviour, in Python.

## Usage

The emulator can be run with `python PyBeeb.py`. This will start the emulator
running, booting the BBC MOS and entering BBC BASIC. The emulator provides
default hooks to allow the terminal input to be passed to the keyboard reading
code, VDU output will be written to the terminal output.

Simple hooks are provided for the filesystem interfaces, allowing access
to files within the current working directory in the host system.

Within the emulator, running BASIC, you can write programs and load and save
files. There is no video or sound system attached in this emulation, so any
graphics will not be displayed, and sound (other than the terminal beeb) will
not be heard.


### Example usage

The emulator runs at a BASIC prompt by default, and you can run commands, such
as printing messages:

    PRINT "Hello world"

The current directory can be listed with `*CAT` or `*.`:

    *cat

Programs can be loaded and saved with `LOAD` and `SAVE`. On the BBC file paths
are separated by a `.` character (not the `/` that you might be used to on
unix-like systems, or the `\\` used by Windows and DOS systems). An example
program can be found in the `tests` directory, which you can run:

    LOAD "Tests.helloworld"
    RUN

To quit the emulator, use `*QUIT`:

    *quit

## Host hooks

Extensions to the BBC system are provided through hooks which can be registered
with the emulator. The emulation system, and its hooks, are based around the
spirit of the Unicorn engine emulator. Hooks can be registered for code
execution, and memory accesses.

The `PyBeeb.py` tool contains commented out code which can be enabled to use
these hooks directly. The example hooks allow code to be traced - each instruction
executed will be disassembled and displayed - and to report on memory accesses
in different areas of memory.

The `pybeeb.Host` package contains a number of implementations of hooked routines
which can be used to replace or augment the standard MOS routines. This package
contains base classess which interpret the interfaces in the `base` module, and
concrete classes within the `hostfs` and `hosttty` modules. These latter modules
provide the file system and terminal I/O.

The `PyBeeb.py` tool includes two simple examples of these extensions, to provide
more information in `*FX0` (the system version), and to allow the emulator to be
quit with `*Quit`.
