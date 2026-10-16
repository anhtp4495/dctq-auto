"""Application entry point."""

import logging

from dctq_auto.gui.app import run_gui


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    raise SystemExit(run_gui())


if __name__ == "__main__":
    main()
