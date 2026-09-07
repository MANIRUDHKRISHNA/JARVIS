"""Main desktop interface for JARVIS."""

from app.agent.brain import Brain


class MainWindow:
    """Simple command-line interface for JARVIS."""

    def __init__(self) -> None:
        self.brain = Brain()

    def run(self) -> None:
        """Start the JARVIS interaction loop."""

        print("JARVIS started.")
        print("Type 'exit' to close JARVIS.")
        print()

        while True:
            user_input = input("You: ").strip()

            if user_input.lower() == "exit":
                print("JARVIS shutting down.")
                break

            if not user_input:
                continue

            response = self.brain.think(user_input)

            print(f"JARVIS: {response}")
            print()