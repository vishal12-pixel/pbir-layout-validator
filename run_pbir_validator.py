"""Top-level entry script used by PyInstaller to build the standalone .exe.

PyInstaller treats this file as a script (no package context), so it uses
absolute imports. ``python -m pbir_validator`` still works via
``pbir_validator/__main__.py`` which uses relative imports.
"""

from pbir_validator.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
