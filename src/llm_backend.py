"""OpenAI-compatible HTTP and optional offline Hugging Face inference backends."""
import json
from datetime import datetime, timezone
from pathlib import Path
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def split_thinking(text, *, starts_in_thinking=False):
    """Split a leading think block, including a block opened by the chat template."""
    stripped = text.lstrip()
    if stripped.startswith("<think>"):
        stripped = stripped[len("<think>"):]
        starts_in_thinking = True
    if starts_in_thinking:
        reasoning, separator, answer = stripped.partition("</think>")
        if not separator:
            raise ValueError("Thinking did not finish: missing </think>; increase max_new_tokens")
        return reasoning.strip(), answer.strip()
    # Some HTTP servers omit the opening tag when it was part of the prompt.
    if "</think>" in stripped and not stripped.startswith(("{", "[", "```")):
        reasoning, _, answer = stripped.partition("</think>")
        return reasoning.strip(), answer.strip()
    return None, text.strip()


class LLMBackend:
    def __init__(self, model_name, *, base_url="http://localhost:11434/v1",
                 api_key="ollama", backend="ollama", max_tokens=400, top_p=0.9,
                 log_path=None, structured_output=True, reasoning_effort=None, enable_thinking=None):
        parsed = urlsplit(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base_url must be an HTTP(S) endpoint without credentials or query parameters")
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.backend = backend
        self.max_tokens, self.top_p = max_tokens, top_p
        self.log_path = Path(log_path) if log_path else None
        self.structured_output = structured_output
        self.reasoning_effort = reasoning_effort
        self.enable_thinking = enable_thinking

    def _request(self, url, payload=None, timeout=900):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Backend HTTP {exc.code}: {detail}. Check model support for the recorded request parameters.") from exc

    def generate(self, messages, *, seed, temperature, turn_number, stage, attempt, schema=None):
        payload = {"model": self.model_name, "messages": messages, "stream": False,
                   "seed": seed, "temperature": temperature,
                   "max_tokens": self.max_tokens, "top_p": self.top_p}
        if self.reasoning_effort is not None:
            payload["reasoning_effort"] = self.reasoning_effort
        if self.enable_thinking is not None and self.backend != "ollama":
            payload["chat_template_kwargs"] = {"enable_thinking": self.enable_thinking}
        if schema is not None and self.structured_output:
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "structured_result", "strict": True, "schema": schema}}
        entry = {"timestamp": utc_now(), "turn": turn_number, "stage": stage,
                 "attempt": attempt, "base_url": self.base_url, "request": payload}
        start = time.monotonic()
        try:
            response = self._request(self.base_url + "/chat/completions", payload)
            entry["response"] = response
            choice = response["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ValueError("Generation reached its token limit; increase max_tokens")
            content = choice["message"].get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Backend returned no text content")
            if self.enable_thinking:
                message = choice["message"]
                reasoning = message.get("reasoning_content") or message.get("reasoning")
                if reasoning is None:
                    reasoning, content = split_thinking(content)
                entry["parsed_response"] = {"reasoning_content": reasoning, "text": content.strip()}
                if not content.strip():
                    raise ValueError("Backend returned reasoning without a final answer")
            return content.strip()
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            entry["elapsed_seconds"] = round(time.monotonic() - start, 3)
            if self.log_path:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", encoding="utf-8") as output:
                    # Redact the API key in case the server echoes it back.
                    text = json.dumps(entry, ensure_ascii=False)
                    if self.api_key and self.api_key != "ollama":
                        text = text.replace(self.api_key, "[REDACTED]")
                    output.write(text + "\n")

    def metadata(self):
        info = {"backend": self.backend, "base_url": self.base_url, "model_name": self.model_name,
                "model_revision": None, "max_tokens": self.max_tokens, "top_p": self.top_p,
                "structured_output": self.structured_output, "reasoning_effort": self.reasoning_effort,
                "enable_thinking": self.enable_thinking,
                "seed_support": "Sent explicitly; provider determinism is not guaranteed.",
                "context_configuration": "Provider/model configuration; not set by the chat API."}
        if self.backend == "ollama":
            root = self.base_url.removesuffix("/v1")
            try:
                info["server_version"] = self._request(root + "/api/version", timeout=5)
                models = self._request(root + "/api/tags", timeout=5)["models"]
                model = next((m for m in models if m["name"] in (self.model_name, self.model_name + ":latest")), None)
                if model:
                    info["model_revision"] = model.get("digest")
                    info["model_details"] = model
                info["model_configuration"] = self._request(root + "/api/show", {"model": self.model_name}, timeout=5)
            except Exception as exc:
                info["metadata_note"] = f"Optional model metadata unavailable ({type(exc).__name__})."
        else:
            info["metadata_note"] = "Immutable revision not discovered; response model/fingerprint are retained in model_calls.jsonl."
        return info

    @staticmethod
    def canonical_model_name(name):
        return name if ":" in name.rsplit("/", 1)[-1] else name + ":latest"

    def check_available(self):
        """Read-only preflight for local models; hosted models validate at inference."""
        if self.backend != "ollama":
            return
        root = self.base_url.removesuffix("/v1")
        models = self._request(root + "/api/tags", timeout=10)["models"]
        wanted = self.canonical_model_name(self.model_name)
        if not any(self.canonical_model_name(m["name"]) == wanted for m in models):
            raise ValueError(f"Ollama model {self.model_name!r} is not installed at {root}")

    def unload(self, model_name=None, timeout=30):
        """Unload an Ollama model and verify it leaves the resident-model list."""
        if self.backend != "ollama":
            return
        root = self.base_url.removesuffix("/v1")
        name = model_name or self.model_name
        wanted = self.canonical_model_name(name)
        self._request(root + "/api/generate", {"model": name, "keep_alive": 0, "stream": False}, timeout=timeout)
        deadline = time.monotonic() + timeout
        while True:
            models = self._request(root + "/api/ps", timeout=5)["models"]
            if not any(self.canonical_model_name(m["name"]) == wanted for m in models):
                return
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Ollama did not unload {name}; stopping before loading another model")
            time.sleep(0.25)

    def prepare_local_model(self):
        """Reserve the local server for this model; do not preload or generate text."""
        if self.backend != "ollama":
            return
        root = self.base_url.removesuffix("/v1")
        wanted = self.canonical_model_name(self.model_name)
        for model in self._request(root + "/api/ps", timeout=10)["models"]:
            if self.canonical_model_name(model["name"]) != wanted:
                self.unload(model["name"])


class HFBackend:
    """In-process inference on the devices made visible by a Slurm allocation."""

    def __init__(self, model_name, *, max_tokens=400, top_p=0.9, log_path=None,
                 enable_thinking=False, reasoning_effort=None):
        self.model_name = model_name
        self.max_tokens, self.top_p = max_tokens, top_p
        self.log_path = Path(log_path) if log_path else None
        self.backend, self.api_key = "hf", None
        self.model = self.tokenizer = None
        self.enable_thinking = enable_thinking
        self.reasoning_effort = reasoning_effort

    def check_available(self):
        # Keep imports optional: HTTP runs do not need the GPU environment.
        try:
            import torch
            import transformers
            import accelerate
        except ImportError as exc:
            raise RuntimeError("HF backend needs torch, transformers and accelerate; "
                               "install requirements-hf.txt in the server environment") from exc

    def prepare_local_model(self):
        if self.model is not None:
            return
        self.check_available()
        import torch
        from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

        loading = dict(local_files_only=True, trust_remote_code=False)
        config = AutoConfig.from_pretrained(self.model_name, **loading)
        model_loader = AutoModelForCausalLM
        if config.model_type in {"mistral3", "qwen3_5", "gemma4"}:
            # These checkpoints use a multimodal class even for text-only input.
            from transformers import AutoModelForImageTextToText
            model_loader = AutoModelForImageTextToText
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, **loading)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.padding_side = "left"
        self.model = model_loader.from_pretrained(
            self.model_name, config=config, device_map="auto", dtype=torch.bfloat16, **loading)
        self.model.eval()

    def generate(self, messages, *, seed, temperature, turn_number, stage, attempt, schema=None):
        import torch

        if schema is not None:
            # Prompt for JSON; decoding is unconstrained and the evaluator validates it.
            messages = [dict(message) for message in messages]
            instruction = ("\n\nReturn only a JSON object matching this JSON Schema. "
                           "Do not include Markdown fences or commentary.\n"
                           + json.dumps(schema, ensure_ascii=False))
            if messages and messages[0]["role"] == "system":
                messages[0]["content"] += instruction
            else:
                messages.insert(0, {"role": "system", "content": instruction.strip()})
        parameters = {"max_new_tokens": self.max_tokens, "do_sample": temperature > 0,
                      "num_beams": 1, "num_return_sequences": 1}
        if temperature > 0:
            parameters.update(temperature=temperature, top_p=self.top_p, top_k=0)
        template_kwargs = {"enable_thinking": self.enable_thinking}
        if self.reasoning_effort is not None:
            template_kwargs["reasoning_effort"] = self.reasoning_effort
        entry = {"timestamp": utc_now(), "turn": turn_number, "stage": stage,
                 "attempt": attempt, "backend": "hf", "request": {
                     "model": self.model_name, "messages": messages, "seed": seed,
                     "generation_kwargs": parameters, **template_kwargs}}
        start = time.monotonic()
        try:
            self.prepare_local_model()
            parameters["pad_token_id"] = self.tokenizer.pad_token_id
            inputs = self.tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True, return_tensors="pt",
                return_dict=True, **template_kwargs)
            device = self.model.get_input_embeddings().weight.device
            inputs = {key: value.to(device) for key, value in inputs.items()}
            prompt_length = inputs["input_ids"].shape[-1]
            # manual_seed touches every visible CUDA device; restore all their RNG states.
            devices = list(range(torch.cuda.device_count())) if torch.cuda.is_available() else []
            with torch.random.fork_rng(devices=devices), torch.inference_mode():
                torch.manual_seed(seed)
                output = self.model.generate(**inputs, **parameters)
            completion = output[0][prompt_length:]
            text = self.tokenizer.decode(completion, skip_special_tokens=True).strip()
            eos = self.model.generation_config.eos_token_id
            eos_ids = eos if isinstance(eos, (list, tuple)) else [eos]
            ended = len(completion) > 0 and completion[-1].item() in eos_ids
            limited = len(completion) >= self.max_tokens and not ended
            entry["response"] = {"text": text, "completion_tokens": len(completion),
                                 "finish_reason": "length" if limited else "stop"}
            if self.enable_thinking:
                # Keep the exact decoded output, even if the thought block is incomplete.
                entry["response"]["raw_text"] = self.tokenizer.decode(completion, skip_special_tokens=False)
            if limited:
                raise ValueError("Generation reached its token limit; increase max_new_tokens")
            if self.enable_thinking:
                prompt = self.tokenizer.decode(inputs["input_ids"][0], skip_special_tokens=False)
                starts_in_thinking = prompt.rstrip().endswith("<think>")
                end_id = self.tokenizer.get_vocab().get("</think>")
                ids = completion.tolist()
                raw = entry["response"]["raw_text"]
                if end_id is not None and end_id in ids and (starts_in_thinking or raw.lstrip().startswith("<think>")):
                    boundary = ids.index(end_id)
                    reasoning = self.tokenizer.decode(completion[:boundary], skip_special_tokens=True).strip()
                    reasoning = reasoning.removeprefix("<think>").strip()
                    text = self.tokenizer.decode(completion[boundary + 1:], skip_special_tokens=True).strip()
                else:
                    reasoning, text = split_thinking(text, starts_in_thinking=starts_in_thinking)
                entry["response"].update(text=text, reasoning_content=reasoning)
            if not text:
                raise ValueError("Backend returned no text content")
            return text
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            entry["elapsed_seconds"] = round(time.monotonic() - start, 3)
            if self.log_path:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", encoding="utf-8") as output_file:
                    output_file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def metadata(self):
        import torch
        import transformers
        from huggingface_hub.constants import HF_HUB_CACHE

        self.prepare_local_model()
        return {"backend": "hf", "model_name": self.model_name,
                "model_revision": getattr(self.model.config, "_commit_hash", None),
                "cache_dir": HF_HUB_CACHE, "local_files_only": True,
                "trust_remote_code": False, "dtype": str(self.model.dtype),
                "device_map": {str(k): str(v) for k, v in
                               getattr(self.model, "hf_device_map", {}).items()},
                "max_tokens": self.max_tokens, "top_p": self.top_p, "top_k": 0,
                "structured_output": False, "enable_thinking": self.enable_thinking,
                "reasoning_effort": self.reasoning_effort,
                "schema_handling": "JSON schema included in system prompt when supplied; unconstrained decoding.",
                "thinking_note": "Only effective for chat templates supporting enable_thinking.",
                "torch_version": torch.__version__, "transformers_version": transformers.__version__,
                "generation_config": self.model.generation_config.to_dict(),
                "chat_template": self.tokenizer.chat_template,
                "seed_support": "Explicit per-call seed with restored CPU/CUDA RNG states; "
                                "determinism across hardware/software is not guaranteed."}

    def unload(self):
        import gc
        import torch

        self.model = self.tokenizer = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
