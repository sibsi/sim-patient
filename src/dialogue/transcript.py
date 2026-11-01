
import json
from pathlib import Path
from typing import Literal


Role = Literal ["doctor", "patient"]
Message = dict[str, str]


def write_outputs(dialogue, directory):
    """Write conversation.json and transcript.txt, overwriting the previous turn's version."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    contents = {
        "conversation.json": json.dumps(dialogue, ensure_ascii=False, indent=2) + "\n",
        "transcript.txt": "\n\n".join(
            f"Doctor: {turn['doctor_question']}\n\nPatient: {turn['patient_reply']}"
            for turn in dialogue["turns"]),
    }
    for name, content in contents.items():
        temporary = directory / (name + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(directory / name)

class Transcript:
    def __init__(self):
        self.messages: list[Message] = []

    def append(self, role: Role, content: str):
        self.messages.append({"role": role, "content": content})

    def render_messages(self, own_role: Role) -> list[Message]:
        return [
            {"role": "assistant" if m["role"] == own_role else "user",
             "content": m["content"]}
            for m in self.messages
        ]

    def get_last_message(self) -> Message | None:
                return self.messages[-1] if self.messages else None

    def save(self, file_path: str):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=4)
