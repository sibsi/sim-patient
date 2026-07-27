from llm_backend import LLMBackendPicker

class BaseAgent:
    """
    Each agent has a role, private memory (system prompt), and access to the shared conversation transcript.
    """
    def __init__(self, role: str, system_prompt: str, llm: LLMBackendPicker):
        self.role = role
        self.system_prompt = system_prompt

        # shared LLM instance for all agents
        self.llm = llm

    def generate_response(self, shared_transcript: list) -> str:
        # first, agent's system prompt (private memory)
        messages = [{"role": "system", "content": self.system_prompt}]

        # then, the shared transcript (public conversation)
        # maybe make self.messages later for efficiency, or keep this for evaluation of shared transcript
        for turn in shared_transcript:
                        speaker = "assistant" if turn["role"] == self.role else "user"
                        messages.append({"role": speaker, "content": turn["text"]})
                        
        return self.llm.chat(messages=messages)