"""Entry point for launching the refactored master control UI."""

from . import MasterControlApp


def main() -> None:
    app = MasterControlApp()
    app.run()


if __name__ == "__main__":
    main()
