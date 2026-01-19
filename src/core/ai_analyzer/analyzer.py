"""動画分析モジュール（見どころ・チャプター検出）."""
import json
import time
from typing import Callable, Optional

from src.models import (
    AnalysisResult,
    Chapter,
    Highlight,
    HighlightType,
    TranscriptionResult,
)

from .llm_client import BaseLLMClient, LLMError


class AnalysisError(Exception):
    """分析エラー."""

    pass


class VideoAnalyzer:
    """動画分析クラス."""

    # 見どころ検出プロンプト
    HIGHLIGHT_PROMPT = """Analyze the following transcript and identify key highlights (interesting moments, important information, funny parts, etc.).

Transcript:
{transcript}

Return a JSON array of highlights with this exact format:
[
  {{
    "start": <start_time_in_seconds>,
    "end": <end_time_in_seconds>,
    "title": "<short title for the highlight>",
    "description": "<brief description>",
    "type": "<type: important|funny|emotional|climax|quote|tutorial|news|other>",
    "score": <importance score 0.0-1.0>
  }}
]

Requirements:
- Identify 3-10 highlights
- Each highlight should be 15-60 seconds long
- Focus on the most engaging moments
- Return ONLY valid JSON, no other text"""

    # チャプター検出プロンプト
    CHAPTER_PROMPT = """Analyze the following transcript and divide it into logical chapters/sections.

Transcript:
{transcript}

Return a JSON array of chapters with this exact format:
[
  {{
    "start": <start_time_in_seconds>,
    "end": <end_time_in_seconds>,
    "title": "<chapter title>"
  }}
]

Requirements:
- Create 3-8 chapters that cover the entire video
- Each chapter should have a clear theme or topic
- Chapters should be sequential and non-overlapping
- Return ONLY valid JSON, no other text"""

    # 要約プロンプト
    SUMMARY_PROMPT = """Summarize the following transcript in 2-3 sentences.

Transcript:
{transcript}

Return only the summary, no other text."""

    def __init__(self, llm_client: BaseLLMClient) -> None:
        """初期化.

        Args:
            llm_client: LLMクライアント
        """
        self.llm_client = llm_client
        self._cancelled = False

    async def analyze(
        self,
        transcription: TranscriptionResult,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> AnalysisResult:
        """動画を分析.

        Args:
            transcription: 文字起こし結果
            progress_callback: 進捗コールバック

        Returns:
            分析結果
        """
        self._cancelled = False
        start_time = time.time()

        # 文字起こしテキストを準備
        transcript_text = self._prepare_transcript(transcription)

        if progress_callback:
            progress_callback(0, "分析開始...")

        # 見どころ検出
        if progress_callback:
            progress_callback(10, "見どころを検出中...")

        highlights = await self._detect_highlights(transcript_text)

        if self._cancelled:
            raise AnalysisError("Analysis cancelled")

        # チャプター検出
        if progress_callback:
            progress_callback(40, "チャプターを検出中...")

        chapters = await self._detect_chapters(transcript_text, transcription.total_duration)

        if self._cancelled:
            raise AnalysisError("Analysis cancelled")

        # 要約生成
        if progress_callback:
            progress_callback(70, "要約を生成中...")

        summary = await self._generate_summary(transcript_text)

        if progress_callback:
            progress_callback(100, "分析完了")

        processing_time = time.time() - start_time

        # Shorts向きのハイライトを特定
        shorts_candidates = [
            h.id for h in highlights if h.duration <= 60
        ]

        return AnalysisResult(
            highlights=highlights,
            chapters=chapters,
            summary=summary,
            shorts_candidates=shorts_candidates,
            processing_time=processing_time,
        )

    def _prepare_transcript(self, transcription: TranscriptionResult) -> str:
        """文字起こしテキストを準備（時間情報付き）."""
        lines = []
        for seg in transcription.segments:
            timestamp = self._format_timestamp(seg.start)
            lines.append(f"[{timestamp}] {seg.text}")
        return "\n".join(lines)

    def _format_timestamp(self, seconds: float) -> str:
        """秒をタイムスタンプに変換."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    async def _detect_highlights(self, transcript: str) -> list[Highlight]:
        """見どころを検出."""
        # トランスクリプトが長すぎる場合は分割
        max_length = 8000
        if len(transcript) > max_length:
            transcript = transcript[:max_length] + "\n...(truncated)"

        prompt = self.HIGHLIGHT_PROMPT.format(transcript=transcript)

        try:
            result = await self.llm_client.generate(
                prompt,
                temperature=0.5,
                max_tokens=2048,
            )

            # JSONをパース
            highlights_data = self._parse_json(result)
            if not isinstance(highlights_data, list):
                return []

            highlights = []
            for i, h in enumerate(highlights_data):
                try:
                    highlight_type = HighlightType.OTHER
                    type_str = h.get("type", "other").lower()
                    for ht in HighlightType:
                        if ht.value == type_str:
                            highlight_type = ht
                            break

                    highlights.append(
                        Highlight(
                            id=i,
                            start=float(h.get("start", 0)),
                            end=float(h.get("end", 0)),
                            title=h.get("title", f"Highlight {i + 1}"),
                            description=h.get("description", ""),
                            highlight_type=highlight_type,
                            score=float(h.get("score", 0.5)),
                        )
                    )
                except (ValueError, KeyError):
                    continue

            return highlights

        except LLMError:
            return []

    async def _detect_chapters(
        self, transcript: str, total_duration: float
    ) -> list[Chapter]:
        """チャプターを検出."""
        max_length = 8000
        if len(transcript) > max_length:
            transcript = transcript[:max_length] + "\n...(truncated)"

        prompt = self.CHAPTER_PROMPT.format(transcript=transcript)

        try:
            result = await self.llm_client.generate(
                prompt,
                temperature=0.5,
                max_tokens=2048,
            )

            # JSONをパース
            chapters_data = self._parse_json(result)
            if not isinstance(chapters_data, list):
                return self._create_default_chapters(total_duration)

            chapters = []
            for i, c in enumerate(chapters_data):
                try:
                    chapters.append(
                        Chapter(
                            id=i,
                            start=float(c.get("start", 0)),
                            end=float(c.get("end", total_duration)),
                            title=c.get("title", f"Chapter {i + 1}"),
                        )
                    )
                except (ValueError, KeyError):
                    continue

            if not chapters:
                return self._create_default_chapters(total_duration)

            return chapters

        except LLMError:
            return self._create_default_chapters(total_duration)

    def _create_default_chapters(self, total_duration: float) -> list[Chapter]:
        """デフォルトチャプターを作成."""
        # 3分割
        duration = total_duration / 3
        return [
            Chapter(id=0, start=0, end=duration, title="Introduction"),
            Chapter(id=1, start=duration, end=duration * 2, title="Main Content"),
            Chapter(id=2, start=duration * 2, end=total_duration, title="Conclusion"),
        ]

    async def _generate_summary(self, transcript: str) -> str:
        """要約を生成."""
        max_length = 4000
        if len(transcript) > max_length:
            transcript = transcript[:max_length] + "\n...(truncated)"

        prompt = self.SUMMARY_PROMPT.format(transcript=transcript)

        try:
            result = await self.llm_client.generate(
                prompt,
                temperature=0.5,
                max_tokens=256,
            )
            return result.strip()
        except LLMError:
            return ""

    def _parse_json(self, text: str) -> list | dict:
        """JSONをパース（エラー耐性あり）."""
        # JSON部分を抽出
        text = text.strip()

        # コードブロック内のJSONを抽出
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()

        # 配列を探す
        if "[" in text and "]" in text:
            start = text.index("[")
            end = text.rindex("]") + 1
            text = text[start:end]

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return []

    def cancel(self) -> None:
        """分析をキャンセル."""
        self._cancelled = True
