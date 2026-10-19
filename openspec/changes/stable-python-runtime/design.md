## Decisions

1. Prefer `/usr/bin/python3`, resolve symlinks before creating the environment, require Python 3.11+ and venv, and use `venv --copies`. A Python-named base executable is a fallback if distribution Python is unavailable. This removes dependence on mise's mutable `latest` symlink.
2. Clear PYTHONHOME, PYTHONPATH, PYTHONEXECUTABLE and __PYVENV_LAUNCHER__ for child Python processes. CLI launchers use isolated mode and explicitly add the trusted application source directory. AppImage-provided Python settings must not redirect imports.
3. Both checkout and installed launchers probe private Python startup and fall back to distribution Python for stdlib diagnostics and explicit Setup. A working interpreter with missing SDK is diagnosed normally; it does not silently install packages.
4. Explicit runtime setup stops only the Zorya daemon, renames the old environment, creates the replacement at its final path (venv scripts contain absolute paths), installs the pinned hardware dependency and verifies imports. It never invokes venv creation over old interpreter symlinks. Keep the previous environment and failed replacement for diagnosis/rollback.
5. Restart an existing daemon immediately after the replacement passes verification, before later installer steps can fail. On replacement failure restore the old environment and attempt to restart it. Initial installations start after writing the unit. Hardware services, pairing and cooling configuration are outside this operation.

## Limits
Copied executables still depend on the distribution's matching standard library and shared libraries. A future distribution Python ABI removal can require explicit Setup again; fallback keeps diagnosis/bootstrap available while system Python remains installed. This is not a self-contained Python distribution.

## Verification
Regression fixtures cover mutable aliases, external interpreter symlink preservation, failed dependency installation, restart before returning, installed fallback and hostile parent Python settings. Local operational repair rebuilt only the private runtime and restored SDK access; the independently unbound wireless fan group is not a Python installation issue.
