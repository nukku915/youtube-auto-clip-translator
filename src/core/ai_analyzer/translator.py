"""翻訳モジュール."""
import asyncio
import time
from typing import Callable, Optional

from src.models import (
    TranscriptionResult,
    TranscriptionSegment,
    TranslatedSegment,
    TranslationResult,
)

from .llm_client import BaseLLMClient, LLMError


class TranslationError(Exception):
    """翻訳エラー."""

    pass


# 言語コード -> 言語名マッピング
LANGUAGE_NAMES = {
    "ja": "Japanese",
    "en": "English",
    "zh": "Chinese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
}


class Translator:
    """LLMを使用した翻訳クラス."""

    # バッチサイズ（一度に翻訳するセグメント数）
    BATCH_SIZE = 10

    # 翻訳プロンプトテンプレート
    TRANSLATION_PROMPT = """Translate the following text from {source_lang} to {target_lang}.

Rules:
- Maintain the original meaning and nuance
- Keep proper nouns as-is when appropriate
- Use natural {target_lang} expressions
- Return ONLY the translation, no explanations

Text to translate:
{text}"""

    BATCH_TRANSLATION_PROMPT = """Translate the following numbered segments from {source_lang} to {target_lang}.

Rules:
- Maintain the original meaning and nuance
- Keep proper nouns as-is when appropriate
- Use natural {target_lang} expressions
- Return translations in the same numbered format
- Do NOT add any explanations

Segments:
{segments}

Translations (same format, numbered):"""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        source_language: str = "en",
        target_language: str = "ja",
    ) -> None:
        """初期化.

        Args:
            llm_client: LLMクライアント
            source_language: 元の言語コード
            target_language: 翻訳先言語コード
        """
        self.llm_client = llm_client
        self.source_language = source_language
        self.target_language = target_language
        self._cancelled = False

    async def translate_text(self, text: str) -> str:
        """単一のテキストを翻訳.

        Args:
            text: 翻訳するテキスト

        Returns:
            翻訳されたテキスト
        """
        source_name = LANGUAGE_NAMES.get(self.source_language, self.source_language)
        target_name = LANGUAGE_NAMES.get(self.target_language, self.target_language)

        prompt = self.TRANSLATION_PROMPT.format(
            source_lang=source_name,
            target_lang=target_name,
            text=text,
        )

        try:
            result = await self.llm_client.generate(
                prompt,
                temperature=0.3,  # 翻訳は低めの温度で
                max_tokens=len(text) * 3,  # 翻訳は元のテキストの3倍程度
            )
            return result.strip()
        except LLMError as e:
            raise TranslationError(f"Translation failed: {e}") from e

    async def translate_segments(
        self,
        segments: list[TranscriptionSegment],
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> list[TranslatedSegment]:
        """セグメントリストを翻訳.

        Args:
            segments: 翻訳するセグメントリスト
            progress_callback: 進捗コールバック

        Returns:
            翻訳されたセグメントリスト
        """
        self._cancelled = False
        translated_segments = []
        total = len(segments)

        # バッチ処理
        for i in range(0, total, self.BATCH_SIZE):
            if self._cancelled:
                raise TranslationError("Translation cancelled")

            batch = segments[i : i + self.BATCH_SIZE]
            batch_translated = await self._translate_batch(batch)
            translated_segments.extend(batch_translated)

            if progress_callback:
                progress = min(100, (i + len(batch)) / total * 100)
                progress_callback(progress, f"翻訳中... {i + len(batch)}/{total}")

        return translated_segments

    async def _translate_batch(
        self, segments: list[TranscriptionSegment]
    ) -> list[TranslatedSegment]:
        """バッチで翻訳."""
        source_name = LANGUAGE_NAMES.get(self.source_language, self.source_language)
        target_name = LANGUAGE_NAMES.get(self.target_language, self.target_language)

        # セグメントを番号付きテキストに変換
        segments_text = "\n".join(
            f"{i + 1}. {seg.text}" for i, seg in enumerate(segments)
        )

        prompt = self.BATCH_TRANSLATION_PROMPT.format(
            source_lang=source_name,
            target_lang=target_name,
            segments=segments_text,
        )

        try:
            result = await self.llm_client.generate(
                prompt,
                temperature=0.3,
                max_tokens=len(segments_text) * 3,
            )

            # 結果をパース
            return self._parse_batch_result(segments, result)

        except LLMError as e:
            # バッチ失敗時は個別に翻訳
            return await self._translate_individually(segments)

    async def _translate_individually(
        self, segments: list[TranscriptionSegment]
    ) -> list[TranslatedSegment]:
        """個別に翻訳（フォールバック）."""
        translated = []

        for seg in segments:
            if self._cancelled:
                raise TranslationError("Translation cancelled")

            try:
                translated_text = await self.translate_text(seg.text)
            except TranslationError:
                # 翻訳失敗時は元のテキストを使用
                translated_text = seg.text

            translated.append(
                TranslatedSegment(
                    id=seg.id,
                    start=seg.start,
                    end=seg.end,
                    original_text=seg.text,
                    translated_text=translated_text,
                    source_language=self.source_language,
                    target_language=self.target_language,
                )
            )

        return translated

    def _parse_batch_result(
        self,
        segments: list[TranscriptionSegment],
        result: str,
    ) -> list[TranslatedSegment]:
        """バッチ翻訳結果をパース."""
        translated = []
        lines = result.strip().split("\n")

        # 番号付き行を抽出
        translations = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # "1. テキスト" または "1) テキスト" 形式をパース
            for sep in [". ", ") ", "。", "："]:
                if sep in line:
                    parts = line.split(sep, 1)
                    try:
                        num = int(parts[0].strip())
                        text = parts[1].strip() if len(parts) > 1 else ""
                        translations[num] = text
                        break
                    except ValueError:
                        continue

        # セグメントと照合
        for i, seg in enumerate(segments):
            idx = i + 1
            translated_text = translations.get(idx, seg.text)

            translated.append(
                TranslatedSegment(
                    id=seg.id,
                    start=seg.start,
                    end=seg.end,
                    original_text=seg.text,
                    translated_text=translated_text,
                    source_language=self.source_language,
                    target_language=self.target_language,
                )
            )

        return translated

    async def translate_transcription(
        self,
        transcription: TranscriptionResult,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> TranslationResult:
        """文字起こし結果を翻訳.

        Args:
            transcription: 文字起こし結果
            progress_callback: 進捗コールバック

        Returns:
            翻訳結果
        """
        start_time = time.time()

        if progress_callback:
            progress_callback(0, "翻訳開始...")

        # 言語を設定
        self.source_language = transcription.language

        # セグメントを翻訳
        translated_segments = await self.translate_segments(
            transcription.segments,
            progress_callback,
        )

        processing_time = time.time() - start_time

        return TranslationResult(
            segments=translated_segments,
            source_language=self.source_language,
            target_language=self.target_language,
            processing_time=processing_time,
        )

    def cancel(self) -> None:
        """翻訳をキャンセル."""
        self._cancelled = True
