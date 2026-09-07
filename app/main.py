"""Entry point for the JARVIS application."""

from app.ui.main_window import MainWindow


def main() -> None:
    """Launch the user interface."""
    window = MainWindow()
    window.run()


if __name__ == "__main__":
    main()
