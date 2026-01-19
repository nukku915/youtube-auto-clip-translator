"""LLMクライアント（Ollama / Gemini）."""
import asyncio
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

import ollama


class LLMError(Exception):
    """LLMエラー."""

    pass


class BaseLLMClient(ABC):
    """LLMクライアント基底クラス."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """テキストを生成.

        Args:
            prompt: ユーザープロンプト
            system_prompt: システムプロンプト
            temperature: 温度（0.0-1.0）
            max_tokens: 最大トークン数

        Returns:
            生成されたテキスト
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """テキストをストリーム生成.

        Yields:
            生成されたテキストチャンク
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """サービスが利用可能かどうか."""
        pass


class OllamaClient(BaseLLMClient):
    """Ollamaクライアント."""

    def __init__(
        self,
        model: str = "qwen3:8b",
        host: str = "http://localhost:11434",
    ) -> None:
        """初期化.

        Args:
            model: モデル名
            host: OllamaホストURL
        """
        self.model = model
        self.host = host
        self._client = ollama.AsyncClient(host=host)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """テキストを生成."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            )
            return response["message"]["content"]

        except ollama.ResponseError as e:
            raise LLMError(f"Ollama error: {e}") from e
        except Exception as e:
            raise LLMError(f"Ollama connection failed: {e}") from e

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """テキストをストリーム生成."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            async for chunk in await self._client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
                stream=True,
            ):
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]

        except ollama.ResponseError as e:
            raise LLMError(f"Ollama error: {e}") from e
        except Exception as e:
            raise LLMError(f"Ollama connection failed: {e}") from e

    async def is_available(self) -> bool:
        """Ollamaが利用可能かどうか."""
        try:
            await self._client.list()
            return True
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """利用可能なモデル一覧を取得."""
        try:
            response = await self._client.list()
            return [m["name"] for m in response.get("models", [])]
        except Exception:
            return []

    async def pull_model(self, model: str) -> bool:
        """モデルをダウンロード."""
        try:
            await self._client.pull(model)
            return True
        except Exception:
            return False


class GeminiClient(BaseLLMClient):
    """Geminiクライアント."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
    ) -> None:
        """初期化.

        Args:
            api_key: Gemini API キー
            model: モデル名
        """
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        """クライアントを取得（遅延初期化）."""
        if self._client is None:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model)
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """テキストを生成."""
        try:
            client = self._get_client()

            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.generate_content(
                    full_prompt,
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                    },
                ),
            )

            return response.text

        except Exception as e:
            raise LLMError(f"Gemini error: {e}") from e

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """テキストをストリーム生成."""
        try:
            client = self._get_client()

            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            response = client.generate_content(
                full_prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
                stream=True,
            )

            for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            raise LLMError(f"Gemini error: {e}") from e

    async def is_available(self) -> bool:
        """Geminiが利用可能かどうか."""
        if not self.api_key:
            return False

        try:
            client = self._get_client()
            # 簡単なテストを実行
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: client.generate_content("Hello"),
            )
            return True
        except Exception:
            return False


class HybridLLMClient(BaseLLMClient):
    """ハイブリッドLLMクライアント（ローカル + クラウド）."""

    def __init__(
        self,
        local_client: Optional[BaseLLMClient] = None,
        cloud_client: Optional[BaseLLMClient] = None,
        fallback_to_cloud: bool = True,
    ) -> None:
        """初期化.

        Args:
            local_client: ローカルLLMクライアント（Ollama）
            cloud_client: クラウドLLMクライアント（Gemini）
            fallback_to_cloud: ローカル失敗時にクラウドへフォールバック
        """
        self.local_client = local_client
        self.cloud_client = cloud_client
        self.fallback_to_cloud = fallback_to_cloud

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        prefer_local: bool = True,
    ) -> str:
        """テキストを生成."""
        primary = self.local_client if prefer_local else self.cloud_client
        fallback = self.cloud_client if prefer_local else self.local_client

        # プライマリを試行
        if primary and await primary.is_available():
            try:
                return await primary.generate(
                    prompt, system_prompt, temperature, max_tokens
                )
            except LLMError:
                if not self.fallback_to_cloud:
                    raise

        # フォールバック
        if fallback and self.fallback_to_cloud and await fallback.is_available():
            return await fallback.generate(
                prompt, system_prompt, temperature, max_tokens
            )

        raise LLMError("No LLM available")

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        prefer_local: bool = True,
    ) -> AsyncIterator[str]:
        """テキストをストリーム生成."""
        primary = self.local_client if prefer_local else self.cloud_client
        fallback = self.cloud_client if prefer_local else self.local_client

        # プライマリを試行
        if primary and await primary.is_available():
            try:
                async for chunk in primary.generate_stream(
                    prompt, system_prompt, temperature, max_tokens
                ):
                    yield chunk
                return
            except LLMError:
                if not self.fallback_to_cloud:
                    raise

        # フォールバック
        if fallback and self.fallback_to_cloud and await fallback.is_available():
            async for chunk in fallback.generate_stream(
                prompt, system_prompt, temperature, max_tokens
            ):
                yield chunk
            return

        raise LLMError("No LLM available")

    async def is_available(self) -> bool:
        """いずれかのLLMが利用可能かどうか."""
        if self.local_client and await self.local_client.is_available():
            return True
        if self.cloud_client and await self.cloud_client.is_available():
            return True
        return False
