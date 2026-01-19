"""字幕生成モジュール."""
from pathlib import Path
from typing import Optional

import pysubs2

from src.models import (
    SubtitleEntry,
    SubtitleFormat,
    SubtitleResult,
    SubtitleStyleConfig,
    TranslatedSegment,
    TranslationResult,
)


class SubtitleGeneratorError(Exception):
    """字幕生成エラー."""

    pass


class SubtitleGenerator:
    """字幕生成クラス."""

    # タイミング設定
    MIN_DURATION = 1.0  # 最小表示時間（秒）
    MAX_DURATION = 5.0  # 最大表示時間（秒）- 短めに設定
    GAP_THRESHOLD = 0.1  # 字幕間の最小ギャップ（秒）

    # セグメント分割設定
    MAX_SEGMENT_DURATION = 4.0  # 1セグメントの最大表示時間（秒）
    MAX_CHARS_PER_SEGMENT_JA = 35  # 日本語の1セグメント最大文字数
    MAX_CHARS_PER_SEGMENT_EN = 80  # 英語の1セグメント最大文字数

    # テキスト整形設定
    MAX_CHARS_PER_LINE_JA = 40  # 日本語
    MAX_CHARS_PER_LINE_EN = 60  # 英語
    MAX_LINES = 2

    def __init__(self, style_config: Optional[SubtitleStyleConfig] = None) -> None:
        """初期化.

        Args:
            style_config: 字幕スタイル設定
        """
        self.style_config = style_config or SubtitleStyleConfig()

    def generate(
        self,
        translation: TranslationResult,
        output_path: Path,
        output_format: SubtitleFormat = SubtitleFormat.ASS,
        bilingual: bool = False,
    ) -> SubtitleResult:
        """字幕ファイルを生成.

        Args:
            translation: 翻訳結果
            output_path: 出力パス
            output_format: 出力フォーマット
            bilingual: 二言語表示

        Returns:
            SubtitleResult
        """
        # 字幕エントリを作成
        entries = self._create_entries(translation.segments, bilingual)

        # タイミングを最適化
        entries = self._optimize_timing(entries)

        # pysubs2で字幕ファイルを作成
        subs = pysubs2.SSAFile()

        # スタイルを設定（ASS形式の場合）
        if output_format == SubtitleFormat.ASS:
            self._setup_styles(subs)

        # イベントを追加
        for entry in entries:
            event = pysubs2.SSAEvent(
                start=int(entry.start * 1000),  # ミリ秒
                end=int(entry.end * 1000),
                text=self._format_text(entry.text, entry.original_text, bilingual),
                style=entry.style or "Default",
            )
            subs.append(event)

        # ファイル拡張子を確認・修正
        output_path = self._ensure_extension(output_path, output_format)

        # 保存
        subs.save(str(output_path), format_=output_format.value)

        return SubtitleResult(
            file_path=output_path,
            format=output_format,
            subtitle_count=len(entries),
            total_duration=entries[-1].end if entries else 0,
            style_applied=self.style_config,
        )

    def _create_entries(
        self,
        segments: list[TranslatedSegment],
        bilingual: bool,
    ) -> list[SubtitleEntry]:
        """字幕エントリを作成（長いセグメントは分割）."""
        entries = []
        entry_id = 0

        for seg in segments:
            # セグメントを分割
            split_entries = self._split_segment(
                seg,
                bilingual,
                start_id=entry_id,
            )
            entries.extend(split_entries)
            entry_id += len(split_entries)

        return entries

    def _split_segment(
        self,
        seg: TranslatedSegment,
        bilingual: bool,
        start_id: int,
    ) -> list[SubtitleEntry]:
        """長いセグメントを適切な長さに分割."""
        text = seg.translated_text
        original_text = seg.original_text if bilingual else None
        duration = seg.end - seg.start

        # 日本語かどうかを判定
        has_japanese = self._has_japanese(text)
        max_chars = (
            self.MAX_CHARS_PER_SEGMENT_JA if has_japanese else self.MAX_CHARS_PER_SEGMENT_EN
        )

        # 分割が不要な場合
        if len(text) <= max_chars and duration <= self.MAX_SEGMENT_DURATION:
            return [
                SubtitleEntry(
                    id=start_id,
                    start=seg.start,
                    end=seg.end,
                    text=text,
                    original_text=original_text,
                )
            ]

        # テキストを文節で分割
        chunks = self._split_text_into_chunks(text, max_chars, has_japanese)

        if not chunks:
            return [
                SubtitleEntry(
                    id=start_id,
                    start=seg.start,
                    end=seg.end,
                    text=text,
                    original_text=original_text,
                )
            ]

        # 時間を均等に分配
        entries = []
        chunk_duration = duration / len(chunks)
        # 最小表示時間を確保
        chunk_duration = max(chunk_duration, self.MIN_DURATION)

        for i, chunk in enumerate(chunks):
            chunk_start = seg.start + (i * chunk_duration)
            chunk_end = min(chunk_start + chunk_duration, seg.end)

            # 最後のチャンクは残り時間を使う
            if i == len(chunks) - 1:
                chunk_end = seg.end

            entries.append(
                SubtitleEntry(
                    id=start_id + i,
                    start=chunk_start,
                    end=chunk_end,
                    text=chunk.strip(),
                    original_text=None,  # 分割時は原文は省略
                )
            )

        return entries

    def _split_text_into_chunks(
        self,
        text: str,
        max_chars: int,
        is_japanese: bool,
    ) -> list[str]:
        """テキストを自然な区切りで分割."""
        if len(text) <= max_chars:
            return [text]

        chunks = []

        if is_japanese:
            # 日本語: 句読点で分割
            delimiters = ["。", "！", "？", "、", "」", "』", "．", "，"]
            current_chunk = ""

            i = 0
            while i < len(text):
                char = text[i]
                current_chunk += char

                # 区切り文字に到達 or 最大文字数に到達
                is_delimiter = char in delimiters
                is_max_length = len(current_chunk) >= max_chars

                if is_delimiter or is_max_length:
                    # 最大文字数を超えている場合、適切な位置で切る
                    if is_max_length and not is_delimiter:
                        # 近くの区切り文字を探す
                        best_split = -1
                        for d in delimiters:
                            pos = current_chunk.rfind(d)
                            if pos > best_split and pos > max_chars // 2:
                                best_split = pos

                        if best_split > 0:
                            # 区切り文字の位置で分割
                            chunks.append(current_chunk[: best_split + 1].strip())
                            current_chunk = current_chunk[best_split + 1 :]
                        else:
                            # 区切り文字がなければそのまま追加
                            chunks.append(current_chunk.strip())
                            current_chunk = ""
                    elif is_delimiter and len(current_chunk) >= max_chars * 0.5:
                        # 区切り文字で、十分な長さがあれば分割
                        chunks.append(current_chunk.strip())
                        current_chunk = ""

                i += 1

            if current_chunk.strip():
                chunks.append(current_chunk.strip())
        else:
            # 英語: 文末で分割
            import re
            sentences = re.split(r'(?<=[.!?])\s+', text)

            current_chunk = ""
            for sentence in sentences:
                if len(current_chunk) + len(sentence) + 1 <= max_chars:
                    current_chunk += (" " if current_chunk else "") + sentence
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    # 文自体が長すぎる場合はさらに分割
                    if len(sentence) > max_chars:
                        words = sentence.split()
                        current_chunk = ""
                        for word in words:
                            if len(current_chunk) + len(word) + 1 <= max_chars:
                                current_chunk += (" " if current_chunk else "") + word
                            else:
                                if current_chunk:
                                    chunks.append(current_chunk.strip())
                                current_chunk = word
                    else:
                        current_chunk = sentence

            if current_chunk.strip():
                chunks.append(current_chunk.strip())

        # 空のチャンクを除去
        return [c for c in chunks if c.strip()]

    def _has_japanese(self, text: str) -> bool:
        """日本語が含まれているか判定."""
        return any(
            "\u3040" <= c <= "\u309f" or  # ひらがな
            "\u30a0" <= c <= "\u30ff" or  # カタカナ
            "\u4e00" <= c <= "\u9fff"  # 漢字
            for c in text
        )

    def _optimize_timing(self, entries: list[SubtitleEntry]) -> list[SubtitleEntry]:
        """タイミングを最適化."""
        if not entries:
            return entries

        optimized = []

        for i, entry in enumerate(entries):
            # 最小表示時間を確保
            duration = entry.end - entry.start
            if duration < self.MIN_DURATION:
                entry.end = entry.start + self.MIN_DURATION

            # 最大表示時間を制限
            if duration > self.MAX_DURATION:
                entry.end = entry.start + self.MAX_DURATION

            # 重複を解消
            if optimized and entry.start < optimized[-1].end:
                gap = self.GAP_THRESHOLD
                optimized[-1].end = entry.start - gap

            optimized.append(entry)

        return optimized

    def _setup_styles(self, subs: pysubs2.SSAFile) -> None:
        """ASSスタイルを設定."""
        # デフォルトスタイル
        default_style = subs.styles["Default"]
        default_style.fontname = self.style_config.font_family
        default_style.fontsize = self.style_config.font_size
        default_style.bold = self.style_config.font_weight == "bold"
        default_style.primarycolor = self._parse_color(self.style_config.primary_color)
        default_style.outlinecolor = self._parse_color(self.style_config.outline_color)
        default_style.outline = self.style_config.outline_width
        default_style.shadow = self.style_config.shadow_depth
        default_style.marginv = self.style_config.margin_v

        # アライメント設定
        position_map = {
            "top": 8,  # 上部中央
            "middle": 5,  # 中央
            "bottom": 2,  # 下部中央
        }
        default_style.alignment = position_map.get(
            self.style_config.position.value, 2
        )

        # 二言語用スタイル（原文用）
        if self.style_config.bilingual:
            original_style = default_style.copy()
            original_style.fontsize = self.style_config.original_font_size
            original_style.primarycolor = self._parse_color(
                self.style_config.original_color
            )
            subs.styles["Original"] = original_style

    def _parse_color(self, color: str) -> pysubs2.Color:
        """カラーコードをpysubs2.Colorに変換."""
        # #RRGGBB -> pysubs2.Color
        color = color.lstrip("#")

        if len(color) == 6:
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            a = 0
        elif len(color) == 8:
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            a = int(color[6:8], 16)
        else:
            r, g, b, a = 255, 255, 255, 0

        return pysubs2.Color(r, g, b, a)

    def _format_text(
        self,
        text: str,
        original_text: Optional[str],
        bilingual: bool,
    ) -> str:
        """テキストを整形."""
        # テキストを適切な長さで改行
        formatted = self._wrap_text(text)

        # 二言語表示
        if bilingual and original_text:
            formatted_original = self._wrap_text(original_text)
            # ASS形式の改行: \N
            formatted = f"{formatted_original}\\N{formatted}"

        return formatted

    def _wrap_text(self, text: str, max_chars: Optional[int] = None) -> str:
        """テキストを適切な長さで改行."""
        if max_chars is None:
            has_japanese = self._has_japanese(text)
            max_chars = (
                self.MAX_CHARS_PER_LINE_JA if has_japanese else self.MAX_CHARS_PER_LINE_EN
            )

        if len(text) <= max_chars:
            return text

        # 適切な位置で改行
        lines = []
        current_line = ""

        for word in text.split():
            if len(current_line) + len(word) + 1 <= max_chars:
                current_line += (" " if current_line else "") + word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        # 最大行数を制限
        if len(lines) > self.MAX_LINES:
            lines = lines[: self.MAX_LINES]
            lines[-1] += "..."

        return "\\N".join(lines)

    def _ensure_extension(self, path: Path, format: SubtitleFormat) -> Path:
        """拡張子を確認・修正."""
        ext_map = {
            SubtitleFormat.SRT: ".srt",
            SubtitleFormat.ASS: ".ass",
            SubtitleFormat.VTT: ".vtt",
        }
        expected_ext = ext_map.get(format, ".srt")

        if path.suffix.lower() != expected_ext:
            path = path.with_suffix(expected_ext)

        return path

    def convert_format(
        self,
        input_path: Path,
        output_format: SubtitleFormat,
        output_path: Optional[Path] = None,
    ) -> Path:
        """字幕フォーマットを変換.

        Args:
            input_path: 入力ファイルパス
            output_format: 出力フォーマット
            output_path: 出力パス（省略時は自動生成）

        Returns:
            出力ファイルパス
        """
        if not input_path.exists():
            raise SubtitleGeneratorError(f"Input file not found: {input_path}")

        # 読み込み
        subs = pysubs2.load(str(input_path))

        # 出力パス
        if output_path is None:
            output_path = input_path.with_suffix(f".{output_format.value}")

        # 保存
        subs.save(str(output_path), format_=output_format.value)

        return output_path
