"""PyInstaller entry shim for the GUI launcher."""
from pbir_validator.gui.app import main

if __name__ == "__main__":
    raise SystemExit(main())
