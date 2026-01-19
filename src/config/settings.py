"""アプリケーション設定."""
import os
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


def get_app_dir() -> Path:
    """アプリケーションディレクトリを取得."""
    app_dir = Path.home() / ".youtube-auto-clip-translator"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_config_path() -> Path:
    """設定ファイルパスを取得."""
    return get_app_dir() / "config.yaml"


def is_macos() -> bool:
    """macOSかどうか判定."""
    return platform.system() == "Darwin"


def is_windows() -> bool:
    """Windowsかどうか判定."""
    return platform.system() == "Windows"


def is_apple_silicon() -> bool:
    """Apple Siliconかどうか判定."""
    return is_macos() and platform.machine() == "arm64"


@dataclass
class LLMConfig:
    """LLM設定."""

    # プロバイダ設定
    provider: str = "hybrid"  # "local", "gemini", "hybrid"

    # ローカルLLMバックエンド設定
    local_backend: str = "ollama"  # "ollama" or "mlx" (macOS only)

    # Ollama設定
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    # MLX LM設定（macOSのみ）
    mlx_model: str = "mlx-community/Qwen2.5-7B-Instruct-4bit"

    # Gemini設定
    gemini_enabled: bool = True
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # タスク振り分け
    use_local_for: list[str] = field(
        default_factory=lambda: [
            "highlight_detection",
            "chapter_detection",
            "translation",
        ]
    )
    use_gemini_for: list[str] = field(
        default_factory=lambda: [
            "title_generation",
            "high_quality_translation",
        ]
    )

    # フォールバック
    fallback_to_gemini: bool = True

    def __post_init__(self) -> None:
        """初期化後の処理."""
        # 環境変数からAPIキーを読み込み
        if not self.gemini_api_key:
            self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

        # macOS以外ではMLXは使えない
        if not is_apple_silicon() and self.local_backend == "mlx":
            self.local_backend = "ollama"


@dataclass
class TranscriptionConfig:
    """文字起こし設定."""

    model: str = "large-v3"  # WhisperXモデル
    device: str = "auto"  # auto, cpu, cuda, mps
    compute_type: str = "float16"  # float16, int8
    language: Optional[str] = None  # None = 自動検出
    batch_size: int = 16

    def __post_init__(self) -> None:
        """初期化後の処理."""
        if self.device == "auto":
            if is_apple_silicon():
                self.device = "mps"
                self.compute_type = "float32"  # MPSはfloat16非対応の場合あり
            elif sys.platform == "win32":
                # CUDAが利用可能かチェック
                try:
                    import torch

                    self.device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    self.device = "cpu"
            else:
                self.device = "cpu"


@dataclass
class VideoConfig:
    """動画関連設定."""

    # ダウンロード設定
    download_quality: str = "1080p"  # 720p, 1080p, 1440p, 2160p
    download_format: str = "mp4"
    download_dir: Path = field(default_factory=lambda: get_app_dir() / "downloads")

    # 一時ファイル
    temp_dir: Path = field(default_factory=lambda: get_app_dir() / "temp")

    # 出力設定
    output_dir: Path = field(default_factory=lambda: Path.home() / "Videos" / "YACT")

    def __post_init__(self) -> None:
        """ディレクトリを作成."""
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class UIConfig:
    """UI設定."""

    theme: str = "dark"  # dark, light
    language: str = "ja"  # UI言語
    window_width: int = 1280
    window_height: int = 720
    auto_save_interval: int = 30  # 秒


@dataclass
class AppSettings:
    """アプリケーション設定."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    # 最近のプロジェクト
    recent_projects: list[str] = field(default_factory=list)
    max_recent_projects: int = 10

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AppSettings":
        """設定をファイルから読み込み."""
        if path is None:
            path = get_config_path()

        if not path.exists():
            # デフォルト設定を返す
            settings = cls()
            settings.save(path)
            return settings

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> "AppSettings":
        """辞書から設定を作成."""
        settings = cls()

        # LLM設定
        if "llm" in data:
            llm_data = data["llm"]
            for key, value in llm_data.items():
                if hasattr(settings.llm, key):
                    setattr(settings.llm, key, value)

        # 文字起こし設定
        if "transcription" in data:
            trans_data = data["transcription"]
            for key, value in trans_data.items():
                if hasattr(settings.transcription, key):
                    setattr(settings.transcription, key, value)

        # 動画設定
        if "video" in data:
            video_data = data["video"]
            for key, value in video_data.items():
                if hasattr(settings.video, key):
                    if key.endswith("_dir"):
                        value = Path(value)
                    setattr(settings.video, key, value)

        # UI設定
        if "ui" in data:
            ui_data = data["ui"]
            for key, value in ui_data.items():
                if hasattr(settings.ui, key):
                    setattr(settings.ui, key, value)

        # 最近のプロジェクト
        if "recent_projects" in data:
            settings.recent_projects = data["recent_projects"]

        return settings

    def save(self, path: Optional[Path] = None) -> None:
        """設定をファイルに保存."""
        if path is None:
            path = get_config_path()

        data = self._to_dict()

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

        # Unixではパーミッションを設定
        if not is_windows():
            os.chmod(path, 0o600)

    def _to_dict(self) -> dict:
        """設定を辞書に変換."""
        return {
            "llm": {
                "provider": self.llm.provider,
                "local_backend": self.llm.local_backend,
                "ollama_host": self.llm.ollama_host,
                "ollama_model": self.llm.ollama_model,
                "mlx_model": self.llm.mlx_model,
                "gemini_enabled": self.llm.gemini_enabled,
                "gemini_api_key": self.llm.gemini_api_key,
                "gemini_model": self.llm.gemini_model,
                "use_local_for": self.llm.use_local_for,
                "use_gemini_for": self.llm.use_gemini_for,
                "fallback_to_gemini": self.llm.fallback_to_gemini,
            },
            "transcription": {
                "model": self.transcription.model,
                "device": self.transcription.device,
                "compute_type": self.transcription.compute_type,
                "language": self.transcription.language,
                "batch_size": self.transcription.batch_size,
            },
            "video": {
                "download_quality": self.video.download_quality,
                "download_format": self.video.download_format,
                "download_dir": str(self.video.download_dir),
                "temp_dir": str(self.video.temp_dir),
                "output_dir": str(self.video.output_dir),
            },
            "ui": {
                "theme": self.ui.theme,
                "language": self.ui.language,
                "window_width": self.ui.window_width,
                "window_height": self.ui.window_height,
                "auto_save_interval": self.ui.auto_save_interval,
            },
            "recent_projects": self.recent_projects,
        }

    def add_recent_project(self, project_path: str) -> None:
        """最近のプロジェクトに追加."""
        if project_path in self.recent_projects:
            self.recent_projects.remove(project_path)
        self.recent_projects.insert(0, project_path)
        self.recent_projects = self.recent_projects[: self.max_recent_projects]


# グローバル設定インスタンス
_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """設定を取得（シングルトン）."""
    global _settings
    if _settings is None:
        _settings = AppSettings.load()
    return _settings


def reload_settings() -> AppSettings:
    """設定を再読み込み."""
    global _settings
    _settings = AppSettings.load()
    return _settings
