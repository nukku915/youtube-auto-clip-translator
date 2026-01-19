"""動画取得モジュール."""
import asyncio
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from src.models import DownloadResult, VideoInfo, VideoMetadata


class VideoFetchError(Exception):
    """動画取得エラー."""

    pass


class VideoFetcher:
    """YouTube動画取得クラス."""

    # YouTubeのURL正規表現パターン
    YOUTUBE_PATTERNS = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]

    def __init__(
        self,
        download_dir: Optional[Path] = None,
        quality: str = "1080p",
    ) -> None:
        """初期化.

        Args:
            download_dir: ダウンロード先ディレクトリ
            quality: ダウンロード品質 (360p, 480p, 720p, 1080p, 1440p, 2160p)
        """
        self.download_dir = download_dir or Path("./downloads")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.quality = quality
        self._cancelled = False

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """URLから動画IDを抽出.

        Args:
            url: YouTube URL

        Returns:
            動画ID または None
        """
        for pattern in VideoFetcher.YOUTUBE_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def is_valid_youtube_url(url: str) -> bool:
        """有効なYouTube URLかどうか判定."""
        return VideoFetcher.extract_video_id(url) is not None

    async def get_video_info(self, url: str) -> VideoInfo:
        """動画情報を取得（ダウンロードせず）.

        Args:
            url: YouTube URL

        Returns:
            VideoInfo

        Raises:
            VideoFetchError: 情報取得失敗時
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            raise VideoFetchError(f"Invalid YouTube URL: {url}")

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, lambda: self._extract_info(url, ydl_opts)
            )

            return VideoInfo(
                video_id=video_id,
                title=info.get("title", ""),
                duration=info.get("duration", 0),
                url=url,
                thumbnail_url=info.get("thumbnail", ""),
                is_available=not info.get("is_unavailable", False),
                is_live=info.get("is_live", False),
                formats=info.get("formats", []),
            )
        except Exception as e:
            raise VideoFetchError(f"Failed to get video info: {e}") from e

    def _extract_info(self, url: str, ydl_opts: dict) -> dict:
        """yt-dlpで情報を抽出（同期）."""
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    async def download(
        self,
        url: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        download_audio_only: bool = False,
    ) -> DownloadResult:
        """動画をダウンロード.

        Args:
            url: YouTube URL
            progress_callback: 進捗コールバック (progress: 0-100, status: str)
            download_audio_only: 音声のみダウンロード

        Returns:
            DownloadResult
        """
        self._cancelled = False
        start_time = time.time()

        video_id = self.extract_video_id(url)
        if not video_id:
            return DownloadResult(
                success=False,
                error=f"Invalid YouTube URL: {url}",
            )

        # 出力パス
        video_path = self.download_dir / f"{video_id}.mp4"
        audio_path = self.download_dir / f"{video_id}.m4a"

        # 品質に応じたフォーマット指定
        quality_map = {
            "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
            "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
            "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
        }

        format_spec = quality_map.get(self.quality, quality_map["1080p"])

        if download_audio_only:
            format_spec = "bestaudio[ext=m4a]/bestaudio"

        # yt-dlp オプション
        ydl_opts = {
            "format": format_spec,
            "outtmpl": str(self.download_dir / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [
                lambda d: self._progress_hook(d, progress_callback)
            ],
            "merge_output_format": "mp4",
            "postprocessors": [],
        }

        if download_audio_only:
            ydl_opts["postprocessors"].append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
            })

        try:
            if progress_callback:
                progress_callback(0, "ダウンロード開始...")

            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, lambda: self._download(url, ydl_opts)
            )

            if self._cancelled:
                return DownloadResult(
                    success=False,
                    error="Download cancelled",
                )

            # メタデータを作成
            metadata = self._create_metadata(info, video_id, url)

            download_time = time.time() - start_time

            # ファイルパスを確認
            if download_audio_only:
                actual_audio_path = self.download_dir / f"{video_id}.m4a"
                if not actual_audio_path.exists():
                    # 拡張子が異なる場合を探す
                    for ext in ["m4a", "mp3", "opus", "webm"]:
                        check_path = self.download_dir / f"{video_id}.{ext}"
                        if check_path.exists():
                            actual_audio_path = check_path
                            break

                return DownloadResult(
                    success=True,
                    audio_path=actual_audio_path if actual_audio_path.exists() else None,
                    metadata=metadata,
                    download_time=download_time,
                )

            # 動画ファイルを探す
            actual_video_path = video_path
            if not actual_video_path.exists():
                for ext in ["mp4", "webm", "mkv"]:
                    check_path = self.download_dir / f"{video_id}.{ext}"
                    if check_path.exists():
                        actual_video_path = check_path
                        break

            return DownloadResult(
                success=True,
                video_path=actual_video_path if actual_video_path.exists() else None,
                metadata=metadata,
                download_time=download_time,
            )

        except Exception as e:
            return DownloadResult(
                success=False,
                error=str(e),
                download_time=time.time() - start_time,
            )

    def _download(self, url: str, ydl_opts: dict) -> dict:
        """yt-dlpでダウンロード（同期）."""
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)

    def _progress_hook(
        self,
        d: dict,
        callback: Optional[Callable[[float, str], None]],
    ) -> None:
        """yt-dlp進捗フック."""
        if self._cancelled:
            raise yt_dlp.utils.DownloadCancelled("Download cancelled by user")

        if callback is None:
            return

        status = d.get("status", "")

        if status == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            if total > 0:
                progress = (downloaded / total) * 100
                speed = d.get("speed", 0)
                if speed:
                    speed_str = f"{speed / 1024 / 1024:.1f} MB/s"
                else:
                    speed_str = "計算中..."
                callback(progress, f"ダウンロード中... {speed_str}")
            else:
                callback(0, "ダウンロード中...")

        elif status == "finished":
            callback(100, "ダウンロード完了、処理中...")

    def _create_metadata(
        self, info: dict, video_id: str, url: str
    ) -> VideoMetadata:
        """yt-dlp情報からメタデータを作成."""
        upload_date = None
        if info.get("upload_date"):
            try:
                upload_date = datetime.strptime(
                    info["upload_date"], "%Y%m%d"
                )
            except ValueError:
                pass

        return VideoMetadata(
            video_id=video_id,
            title=info.get("title", ""),
            duration=info.get("duration", 0),
            url=url,
            channel_name=info.get("channel", "") or info.get("uploader", ""),
            channel_id=info.get("channel_id", ""),
            upload_date=upload_date,
            description=info.get("description", ""),
            tags=info.get("tags", []) or [],
            view_count=info.get("view_count", 0) or 0,
            like_count=info.get("like_count", 0) or 0,
            width=info.get("width", 0) or 0,
            height=info.get("height", 0) or 0,
            fps=info.get("fps", 0) or 0,
            codec=info.get("vcodec", ""),
            file_size=info.get("filesize", 0) or 0,
            original_language=info.get("language", "") or "",
        )

    def cancel(self) -> None:
        """ダウンロードをキャンセル."""
        self._cancelled = True
