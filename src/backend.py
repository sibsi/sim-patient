import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

class ModelBackend:
    def __init__(self, model_name: str, device_map: str = "auto", **gen_kwargs):
        self.model_name = model_name
        self.device_map = device_map

        #default arguments for generation, can be overridden when calling generate()
        self.gen_kwargs = {"max_new_tokens": 256, "do_sample": True,
                           "temperature": 0.7, "top_p": 0.9, **gen_kwargs}
        
        # load the tokenizer and model
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            local_files_only=True,
            trust_remote_code=True
        )

        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.padding_side = "left" 

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            device_map=self.device_map,
            dtype=torch.bfloat16,
            local_files_only=True,
            trust_remote_code=True
        )

        self.model.eval()  # set for inference (HF sets automatically but still)

    def generate(self, messages: list, **overrides) -> str:

        # add reproducibility seed later (fork_rng so doc and patient resseeding don't interfere)
        
        inputs = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True
        )

        device = next(self.model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        prompt_length = inputs["input_ids"].shape[-1]

        with torch.inference_mode():
            generation_kwargs = {**self.gen_kwargs, **overrides}
            generation_kwargs.setdefault("pad_token_id", self.tokenizer.pad_token_id)
            output = self.model.generate(
                **inputs,
                **generation_kwargs,
            )

        completion = output[0][prompt_length:]
        return self.tokenizer.decode(completion, skip_special_tokens=True).strip()

# test to run with salloc on cluster
import os
import time 

MODEL = "Qwen/Qwen3.5-4B"

def main():
        print("gpu count      :", torch.cuda.device_count())
        print("gpu 0 name       :", torch.cuda.get_device_name(0))
        print("model name     :", MODEL)
        print("starting model...")

        t0 = time.time()
        backend = ModelBackend(MODEL, max_new_tokens=64)
        load_time = time.time() - t0
        device = next(backend.model.parameters()).device
        print(f"model loaded on {device} in {load_time:.2f} seconds")

        messages = [{"role": "user", "content": "Reply with one short sentence: are you working?"}]

        t0 = time.time()
        output = backend.generate(messages)
        gen_time = time.time() - t0

        print(f"generation time: {gen_time:.2f} seconds")
        print("output:", output)
        print(f"GPU memory peak: {torch.cuda.max_memory_allocated() / 1e9:.1f} GB")


if __name__ == "__main__":
    main()

