"""Task planner for JARVIS."""

from ollama import chat


class Planner:
    """Creates a simple execution plan using the local LLM."""

    def __init__(self, model: str = "qwen3:8b"):
        self.model = model

    def create_plan(self, task: str) -> list[str]:
        """
        Create a short plan for the requested task.

        The planner only creates a plan.
        It does NOT execute tools.
        """

        prompt = f"""
Create a concise execution plan for this task:

{task}

Rules:
1. Produce at most 6 steps.
2. Start with inspection when the task involves a project,
   directory, repository, or existing code.
3. If files need to be changed, inspect/read them before changing them.
4. Include verification/testing when appropriate.
5. Do not perform the task.
6. Do not invent project files or results.
7. Return ONLY numbered steps.
"""

        response = chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the planning component of a local "
                        "coding agent. Create plans only. Do not claim "
                        "that you inspected files or executed commands."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            think=False,
        )

        text = response.message.content.strip()

        return self._parse_steps(text)

    def _parse_steps(self, text: str) -> list[str]:
        """Convert numbered model output into a list of steps."""

        steps = []

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            # Accept:
            # 1. Inspect the project
            # 2) Read the files
            if len(line) >= 3 and line[0].isdigit():
                if line[1] in ".):":
                    step = line[2:].strip()

                    if step:
                        steps.append(step)

        if not steps:
            return [
                "Inspect the relevant project files.",
                "Perform the requested task.",
                "Verify the result.",
            ]

        return steps[:6]