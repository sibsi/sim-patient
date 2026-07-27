
import json
import os
from typing import List, Dict, Any
import ollama

"""
LLM Backend Picker: "ollama" or "transformers" (huggingface)
HF imports loaded lazily
"""

class LLMBackendPicker:
    def __init__(self, backend: str = "ollama", model_name: str = "mistral-nemo:latest"):
        self.backend = backend.lower()
        self.model_name = model_name
        
        if self.backend == "huggingface":
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            
            # 4-bit quantization
            self.hf_model = AutoModelForCausalLM.from_pretrained(
                model_name,
                device_map="auto",
                quant_config=BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.bfloat16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
            )

    """universal chat interface for both backends"""
    def chat(self, messages: List[Dict[str, str]], force_json: bool = False) -> str:
            if self.backend == "ollama":
                # use ollama's native json mode
                options = {"format": "json"} if force_json else {}
                response = ollama.chat(
                    model=self.model_name,
                    messages=messages,
                    **options
                )
                return response['message']['content']
                
            elif self.backend == "huggingface":
                # apply_chat_template important here for model's native chat format
                prompt = self.tokenizer.apply_chat_template(
                    messages, 
                    tokenize=False, 
                    add_generation_prompt=True
                )
                
                inputs = self.tokenizer(prompt, return_tensors="pt").to(self.hf_model.device)
                
                outputs = self.hf_model.generate(**inputs, max_new_tokens=1024, pad_token_id=self.tokenizer.eos_token_id)
                
                generated_tokens = outputs[0][inputs['input_ids'].shape[-1]:]
                response_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
                
                return response_text
            
            else:
                raise ValueError(f"Unknown backend: {self.backend}, must be 'ollama' or 'huggingface'.")