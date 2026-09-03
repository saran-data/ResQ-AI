"""
ResQAI - Unified LLM Client
Single interface for calling any AI model regardless of provider.
Handles prompt construction, token counting, cost estimation, and response parsing.
"""

import time
from typing import Any, Optional, Union

from loguru import logger

from app.config import settings
from app.orchestrator.model_registry import ModelID, ModelProvider, get_model_registry


# -------------------------------------------------------
# Cost per 1K tokens (approximate, as of 2026)
# -------------------------------------------------------
MODEL_COSTS_PER_1K: dict[str, dict] = {
    ModelID.GPT4O.value:           {"input": 0.005, "output": 0.015},
    ModelID.GPT4O_MINI.value:      {"input": 0.00015, "output": 0.0006},
    ModelID.CLAUDE_35_SONNET.value: {"input": 0.003, "output": 0.015},
    ModelID.GEMINI_15_PRO.value:   {"input": 0.00125, "output": 0.005},
    ModelID.DEEPSEEK_CHAT.value:   {"input": 0.0002, "output": 0.0002},
    ModelID.MISTRAL_SMALL.value:   {"input": 0.001, "output": 0.003},
    ModelID.LLAMA3.value:          {"input": 0.0, "output": 0.0},  # Local = free
    ModelID.MISTRAL_LOCAL.value:   {"input": 0.0, "output": 0.0},
}


class LLMResponse:
    """Normalized response from any LLM provider."""

    def __init__(
        self,
        content: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int = 0,
    ) -> None:
        self.content = content
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens
        self.latency_ms = latency_ms
        self.cost_usd = self._calculate_cost(model, prompt_tokens, completion_tokens)

    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        costs = MODEL_COSTS_PER_1K.get(model, {"input": 0.001, "output": 0.003})
        return (prompt_tokens * costs["input"] + completion_tokens * costs["output"]) / 1000


class LLMClient:
    """
    Unified client that abstracts all LLM providers behind a single API.
    
    Usage:
        client = LLMClient()
        response = await client.complete(
            model=ModelID.GPT4O,
            system_prompt="You are a food safety expert...",
            user_prompt="Analyze this food: ...",
        )
    """

    def __init__(self) -> None:
        self._registry = get_model_registry()

    async def complete(
        self,
        model: ModelID,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        json_mode: bool = False,
        images: Optional[list[str]] = None,
    ) -> LLMResponse:
        """
        Send a completion request to any supported model.

        Args:
            model: Target model identifier
            user_prompt: Main query/task description
            system_prompt: Optional system instruction
            temperature: Sampling temperature (0=deterministic)
            max_tokens: Maximum output tokens
            json_mode: Request structured JSON output
            images: Base64 image strings or URLs (for vision models)

        Returns:
            Normalized LLMResponse

        Raises:
            RuntimeError: If the model provider is unavailable
        """
        start = time.monotonic()

        if model in (ModelID.GPT4O, ModelID.GPT4O_MINI):
            response = await self._call_openai(
                model, user_prompt, system_prompt, temperature, max_tokens, json_mode, images
            )
        elif model == ModelID.CLAUDE_35_SONNET:
            response = await self._call_anthropic(
                model, user_prompt, system_prompt, temperature, max_tokens
            )
        elif model == ModelID.GEMINI_15_PRO:
            response = await self._call_gemini(
                model, user_prompt, system_prompt, temperature, max_tokens, images
            )
        elif model == ModelID.DEEPSEEK_CHAT:
            response = await self._call_deepseek(
                model, user_prompt, system_prompt, temperature, max_tokens, json_mode
            )
        elif model == ModelID.MISTRAL_SMALL:
            response = await self._call_mistral(
                model, user_prompt, system_prompt, temperature, max_tokens
            )
        elif model in (ModelID.LLAMA3, ModelID.MISTRAL_LOCAL):
            response = await self._call_ollama(
                model, user_prompt, system_prompt, temperature, max_tokens
            )
        else:
            raise RuntimeError(f"Unsupported model: {model}")

        response.latency_ms = int((time.monotonic() - start) * 1000)
        self._registry.record_call(model, response.latency_ms)
        return response

    # -------------------------------------------------------
    # Provider Implementations
    # -------------------------------------------------------
    async def _call_openai(
        self, model: ModelID, user_prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int, json_mode: bool, images: Optional[list]
    ) -> LLMResponse:
        client = self._registry.get_openai_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if images:
            # Vision: multi-modal message
            content = [{"type": "text", "text": user_prompt}]
            for img in images:
                if img.startswith("http"):
                    content.append({"type": "image_url", "image_url": {"url": img}})
                else:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img}"}
                    })
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user_prompt})

        kwargs: dict = {
            "model": model.value,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content or "",
            model=model.value,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )

    async def _call_anthropic(
        self, model: ModelID, user_prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int
    ) -> LLMResponse:
        client = self._registry.get_anthropic_client()

        kwargs: dict = {
            "model": model.value,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await client.messages.create(**kwargs)
        content = response.content[0].text if response.content else ""
        usage = response.usage

        return LLMResponse(
            content=content,
            model=model.value,
            prompt_tokens=usage.input_tokens,
            completion_tokens=usage.output_tokens,
        )

    async def _call_gemini(
        self, model: ModelID, user_prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int, images: Optional[list]
    ) -> LLMResponse:
        import google.generativeai as genai

        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        gemini_model = genai.GenerativeModel(
            model_name=model.value,
            generation_config=generation_config,
            system_instruction=system_prompt,
        )

        parts = [user_prompt]
        if images:
            for img in images:
                if img.startswith("http"):
                    import httpx
                    async with httpx.AsyncClient() as http:
                        r = await http.get(img)
                        from PIL import Image
                        import io
                        image = Image.open(io.BytesIO(r.content))
                        parts.append(image)
                else:
                    import base64
                    from PIL import Image
                    import io
                    img_bytes = base64.b64decode(img)
                    image = Image.open(io.BytesIO(img_bytes))
                    parts.append(image)

        response = await gemini_model.generate_content_async(parts)
        content = response.text if hasattr(response, "text") else str(response)

        # Gemini doesn't always expose token counts in the same way
        return LLMResponse(
            content=content,
            model=model.value,
            prompt_tokens=getattr(response, "prompt_token_count", 0),
            completion_tokens=getattr(response, "candidates_token_count", 0),
        )

    async def _call_deepseek(
        self, model: ModelID, user_prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int, json_mode: bool
    ) -> LLMResponse:
        client = self._registry.get_deepseek_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        kwargs: dict = {
            "model": model.value,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(**kwargs)
        usage = response.usage

        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=model.value,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )

    async def _call_mistral(
        self, model: ModelID, user_prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int
    ) -> LLMResponse:
        client = self._registry.get_mistral_client()
        from mistralai.models import UserMessage, SystemMessage

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(UserMessage(content=user_prompt))

        response = await client.chat.complete_async(
            model=model.value,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        usage = response.usage

        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=model.value,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )

    async def _call_ollama(
        self, model: ModelID, user_prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int
    ) -> LLMResponse:
        import httpx
        ollama_url = self._registry.get_client(ModelProvider.OLLAMA)

        payload = {
            "model": model.value,
            "prompt": f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120) as http:
            response = await http.post(f"{ollama_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()

        return LLMResponse(
            content=data.get("response", ""),
            model=model.value,
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
        )

    async def complete_with_task(
        self,
        task_name: str,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Convenience method: auto-selects the best model for a task.
        
        Args:
            task_name: Task identifier (used for model routing)
            user_prompt: Query
            system_prompt: System instruction
            **kwargs: Forwarded to complete()

        Returns:
            LLMResponse from the selected model
        """
        model = self._registry.get_model_for_task(task_name)
        logger.debug(f"Task '{task_name}' → model '{model.value}'")
        return await self.complete(
            model=model,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            **kwargs,
        )
