"""音声処理・文字起こしモジュール."""

import asyncio
import platform
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

from src.models import (
    TranscriptionResult,
    TranscriptionSegment,
    WordInfo,
)


class AudioProcessError(Exception):
    """音声処理エラー."""

    pass


class TranscriptionError(Exception):
    """文字起こしエラー."""

    pass


class AudioProcessor:
    """音声処理クラス."""

    def __init__(self, temp_dir: Optional[Path] = None) -> None:
        """初期化.

        Args:
            temp_dir: 一時ファイルディレクトリ
        """
        self.temp_dir = temp_dir or Path("./temp")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def extract_audio(
        self,
        video_path: Path,
        output_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Path:
        """動画から音声を抽出.

        Args:
            video_path: 動画ファイルパス
            output_path: 出力パス（省略時は自動生成）
            progress_callback: 進捗コールバック

        Returns:
            音声ファイルパス

        Raises:
            AudioProcessError: 抽出失敗時
        """
        if not video_path.exists():
            raise AudioProcessError(f"Video file not found: {video_path}")

        if output_path is None:
            output_path = self.temp_dir / f"{video_path.stem}.wav"

        if progress_callback:
            progress_callback(0, "音声抽出中...")

        # FFmpegで音声抽出
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vn",  # 映像なし
            "-acodec", "pcm_s16le",  # WAV形式
            "-ar", "16000",  # 16kHz（Whisper推奨）
            "-ac", "1",  # モノラル
            str(output_path),
        ]

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, lambda: self._run_ffmpeg(cmd)
            )

            if progress_callback:
                progress_callback(100, "音声抽出完了")

            return output_path

        except subprocess.CalledProcessError as e:
            raise AudioProcessError(f"FFmpeg failed: {e}") from e

    def _run_ffmpeg(self, cmd: list[str]) -> None:
        """FFmpegを実行（同期）."""
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                cmd,
                result.stdout,
                result.stderr,
            )


def _is_apple_silicon() -> bool:
    """Apple Silicon (M1/M2/M3/M4) かどうかを判定."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


class Transcriber:
    """音声文字起こしクラス.

    Apple Silicon: lightning-whisper-mlx を使用（高速・最適化）
    その他: faster-whisper を使用
    """

    # 利用可能なモデル
    AVAILABLE_MODELS = [
        "tiny",
        "base",
        "small",
        "medium",
        "large",
        "large-v2",
        "large-v3",
        "distil-small.en",
        "distil-medium.en",
        "distil-large-v2",
        "distil-large-v3",
    ]

    def __init__(
        self,
        model: str = "distil-large-v3",
        language: Optional[str] = None,
        batch_size: int = 12,
    ) -> None:
        """初期化.

        Args:
            model: Whisperモデル名
            language: 言語コード（None=自動検出）
            batch_size: バッチサイズ
        """
        self.model_name = model
        self.language = language
        self.batch_size = batch_size
        self._model = None
        self._cancelled = False
        self._use_mlx = _is_apple_silicon()

    def _load_model(self) -> None:
        """モデルをロード."""
        if self._model is not None:
            return

        if self._use_mlx:
            from lightning_whisper_mlx import LightningWhisperMLX

            self._model = LightningWhisperMLX(
                model=self.model_name,
                batch_size=self.batch_size,
                quant=None,  # 量子化なし（精度優先）
            )
        else:
            # 非Apple Silicon環境ではfaster-whisperを使用
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_name,
                device="cpu",
                compute_type="int8",
            )

    async def transcribe(
        self,
        audio_path: Path,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> TranscriptionResult:
        """音声を文字起こし.

        Args:
            audio_path: 音声ファイルパス
            progress_callback: 進捗コールバック

        Returns:
            TranscriptionResult

        Raises:
            TranscriptionError: 文字起こし失敗時
        """
        self._cancelled = False
        start_time = time.time()

        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        try:
            if progress_callback:
                progress_callback(0, "モデル読み込み中...")

            # モデルロード
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._load_model)

            if self._cancelled:
                raise TranscriptionError("Transcription cancelled")

            if progress_callback:
                progress_callback(20, "文字起こし中...")

            # 文字起こし実行
            if self._use_mlx:
                result = await self._transcribe_mlx(audio_path, loop)
            else:
                result = await self._transcribe_faster_whisper(audio_path, loop)

            if self._cancelled:
                raise TranscriptionError("Transcription cancelled")

            if progress_callback:
                progress_callback(90, "結果を整形中...")

            # 結果を整形
            transcription_segments = []
            total_duration = 0

            for i, seg in enumerate(result["segments"]):
                # lightning-whisper-mlx: [start, end, text] 形式（centiseconds）
                # faster-whisper: {"start": ..., "end": ..., "text": ...} 形式（seconds）
                if isinstance(seg, (list, tuple)):
                    # lightning-whisper-mlx returns centiseconds (1/100 sec)
                    # Convert to seconds
                    seg_start = seg[0] / 100.0
                    seg_end = seg[1] / 100.0
                    seg_text = seg[2] if len(seg) > 2 else ""
                else:
                    seg_start = seg.get("start", 0)
                    seg_end = seg.get("end", 0)
                    seg_text = seg.get("text", "")

                segment = TranscriptionSegment(
                    id=i,
                    start=seg_start,
                    end=seg_end,
                    text=seg_text.strip() if seg_text else "",
                    words=[],
                    confidence=1.0,
                )
                transcription_segments.append(segment)
                total_duration = max(total_duration, seg_end)

            processing_time = time.time() - start_time

            if progress_callback:
                progress_callback(100, "文字起こし完了")

            return TranscriptionResult(
                segments=transcription_segments,
                language=result.get("language", self.language or "unknown"),
                model=self.model_name,
                processing_time=processing_time,
                total_duration=total_duration,
            )

        except Exception as e:
            if "cancelled" in str(e).lower():
                raise TranscriptionError("Transcription cancelled") from e
            raise TranscriptionError(f"Transcription failed: {e}") from e

    async def _transcribe_mlx(self, audio_path: Path, loop) -> dict:
        """lightning-whisper-mlxで文字起こし."""

        def _do_transcribe():
            result = self._model.transcribe(
                audio_path=str(audio_path),
                language=self.language,
            )
            return result

        return await loop.run_in_executor(None, _do_transcribe)

    async def _transcribe_faster_whisper(self, audio_path: Path, loop) -> dict:
        """faster-whisperで文字起こし."""

        def _do_transcribe():
            segments_gen, info = self._model.transcribe(
                str(audio_path),
                language=self.language,
                beam_size=5,
                vad_filter=True,
            )

            # generatorをlistに変換
            segments = []
            for seg in segments_gen:
                segments.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                })

            return {
                "segments": segments,
                "language": info.language,
            }

        return await loop.run_in_executor(None, _do_transcribe)

    def cancel(self) -> None:
        """文字起こしをキャンセル."""
        self._cancelled = True

    def unload_model(self) -> None:
        """モデルをアンロード."""
        self._model = None
