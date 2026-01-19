# 設定ファイルスキーマ

## 1. 概要

### 保存場所

```
~/.youtube-auto-clip-translator/
├── config.yaml          # メイン設定ファイル
├── projects/            # プロジェクト保存先
├── autosave/            # 自動保存データ
├── cache/               # キャッシュ
├── logs/                # ログファイル
└── bin/                 # 外部ツール（FFmpeg等）
```

### 読み込み優先順位

1. 環境変数（最優先）
2. config.yaml
3. デフォルト値

---

## 2. 完全なconfig.yaml

```yaml
# ~/.youtube-auto-clip-translator/config.yaml
# YouTube Auto Clip Translator 設定ファイル

# =============================================================================
# アプリケーション設定
# =============================================================================
app:
  # UIテーマ: dark, light
  theme: dark

  # UI言語: ja, en
  language: ja

  # 作業ディレクトリ（プロジェクト保存先）
  projects_dir: ~/.youtube-auto-clip-translator/projects

  # 自動保存間隔（秒）
  auto_save_interval: 30

  # 最近のプロジェクト表示数
  recent_projects_limit: 10

# =============================================================================
# LLM設定（翻訳・AI分析）
# =============================================================================
llm:
  # プロバイダ: hybrid, gemini, local
  # hybrid: Gemini + Ollama併用（推奨）
  # gemini: Geminiのみ
  # local: Ollamaのみ
  provider: hybrid

  # Gemini設定
  gemini:
    # APIキー（環境変数 GEMINI_API_KEY でも設定可能）
    api_key: ""

    # モデル名
    model: gemini-2.0-flash

    # タイムアウト（秒）
    timeout: 60

    # 生成温度（0.0〜1.0）
    temperature: 0.3

  # Ollama設定（ローカルLLM）
  ollama:
    # ホストURL
    host: http://localhost:11434

    # モデル名
    model: gemma-2-jpn:2b

    # タイムアウト（秒）
    timeout: 120

    # 生成温度
    temperature: 0.3

  # タスク振り分け
  # local: Ollamaを使用
  # gemini: Gemini APIを使用
  task_routing:
    highlight_detection: local
    chapter_detection: local
    translation: gemini
    title_generation: gemini

  # Geminiへのフォールバック（ローカル失敗時）
  fallback_to_gemini: true

# =============================================================================
# 文字起こし設定（WhisperX）
# =============================================================================
whisper:
  # モデルサイズ: tiny, base, small, medium, large-v3, distil-large-v3
  model: distil-large-v3

  # デバイス: auto, cuda, mps, cpu
  device: auto

  # 計算精度: auto, float16, int8
  compute_type: auto

  # バッチサイズ（GPU メモリに応じて調整）
  batch_size: 16

  # 言語: auto（自動検出）または言語コード
  language: auto

  # 話者分離を有効化
  enable_diarization: false

  # HuggingFace トークン（話者分離に必要）
  hf_token: ""

# =============================================================================
# 動画取得設定（yt-dlp）
# =============================================================================
fetcher:
  # 画質: best, 1080p, 720p, 480p, 360p
  quality: best

  # 優先フォーマット: mp4, webm
  prefer_format: mp4

  # タイムアウト（秒）
  timeout: 30

  # リトライ回数
  retries: 3

  # Cookieファイルパス（年齢制限動画用）
  cookies_file: ""

  # プロキシ設定
  proxy: ""

# =============================================================================
# 字幕設定
# =============================================================================
subtitle:
  # デフォルト出力形式: srt, ass, vtt
  default_format: ass

  # 二言語表示
  bilingual: false

  # フォント設定
  font:
    family: Noto Sans JP
    size: 48
    weight: bold

  # 色設定（RRGGBB形式）
  colors:
    primary: "#FFFFFF"
    outline: "#000000"
    shadow: "#00000080"

  # 縁取り幅
  outline_width: 2

  # 位置: top, middle, bottom
  position: bottom

  # 垂直マージン
  margin_v: 20

# =============================================================================
# 動画編集設定
# =============================================================================
editor:
  # エンコードプリセット: high_quality, balanced, fast
  encoding_preset: balanced

  # ハードウェアアクセラレーション
  hw_accel: true

  # タイトルカード設定
  title_card:
    enabled: true
    duration: 2.0
    animation: fade
    font_size: 72
    background_opacity: 0.8

  # Shorts背景スタイル: glassmorphism, solid, gradient
  shorts_background: glassmorphism

# =============================================================================
# 出力設定
# =============================================================================
export:
  # デフォルト出力先
  output_dir: ~/Videos/youtube-clips

  # ファイル名テンプレート
  # 変数: {title}, {format}, {date}, {datetime}, {index}, {chapter}, {lang}
  filename_template: "{title}_{format}"

  # 字幕を動画に焼き付け
  burn_subtitles: true

  # 字幕ファイルも出力
  export_subtitle_files: true

# =============================================================================
# 外部ツール設定
# =============================================================================
tools:
  # FFmpegパス（空欄の場合は自動検出）
  ffmpeg_path: ""

  # Denoパス（空欄の場合は自動検出）
  deno_path: ""

  # mpvパス（空欄の場合は自動検出）
  mpv_path: ""

# =============================================================================
# ログ設定
# =============================================================================
logging:
  # ログレベル: DEBUG, INFO, WARNING, ERROR
  level: INFO

  # ログファイル保存
  save_to_file: true

  # ログファイル保存先
  log_dir: ~/.youtube-auto-clip-translator/logs

  # ログローテーション（日数）
  retention_days: 7
```

---

## 3. Pydanticモデル定義

```python
# config/settings.py
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Optional, Literal

class GeminiConfig(BaseModel):
    api_key: str = ""
    model: str = "gemini-2.0-flash"
    timeout: int = 60
    temperature: float = 0.3

class OllamaConfig(BaseModel):
    host: str = "http://localhost:11434"
    model: str = "gemma-2-jpn:2b"
    timeout: int = 120
    temperature: float = 0.3

class TaskRouting(BaseModel):
    highlight_detection: Literal["local", "gemini"] = "local"
    chapter_detection: Literal["local", "gemini"] = "local"
    translation: Literal["local", "gemini"] = "gemini"
    title_generation: Literal["local", "gemini"] = "gemini"

class LLMConfig(BaseModel):
    provider: Literal["hybrid", "gemini", "local"] = "hybrid"
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    task_routing: TaskRouting = Field(default_factory=TaskRouting)
    fallback_to_gemini: bool = True

class WhisperConfig(BaseModel):
    model: str = "distil-large-v3"
    device: Literal["auto", "cuda", "mps", "cpu"] = "auto"
    compute_type: Literal["auto", "float16", "int8"] = "auto"
    batch_size: int = 16
    language: str = "auto"
    enable_diarization: bool = False
    hf_token: str = ""

class FetcherConfig(BaseModel):
    quality: str = "best"
    prefer_format: str = "mp4"
    timeout: int = 30
    retries: int = 3
    cookies_file: str = ""
    proxy: str = ""

class FontConfig(BaseModel):
    family: str = "Noto Sans JP"
    size: int = 48
    weight: str = "bold"

class ColorConfig(BaseModel):
    primary: str = "#FFFFFF"
    outline: str = "#000000"
    shadow: str = "#00000080"

class SubtitleConfig(BaseModel):
    default_format: Literal["srt", "ass", "vtt"] = "ass"
    bilingual: bool = False
    font: FontConfig = Field(default_factory=FontConfig)
    colors: ColorConfig = Field(default_factory=ColorConfig)
    outline_width: int = 2
    position: Literal["top", "middle", "bottom"] = "bottom"
    margin_v: int = 20

class TitleCardConfig(BaseModel):
    enabled: bool = True
    duration: float = 2.0
    animation: str = "fade"
    font_size: int = 72
    background_opacity: float = 0.8

class EditorConfig(BaseModel):
    encoding_preset: Literal["high_quality", "balanced", "fast"] = "balanced"
    hw_accel: bool = True
    title_card: TitleCardConfig = Field(default_factory=TitleCardConfig)
    shorts_background: Literal["glassmorphism", "solid", "gradient"] = "glassmorphism"

class ExportConfig(BaseModel):
    output_dir: Path = Path.home() / "Videos" / "youtube-clips"
    filename_template: str = "{title}_{format}"
    burn_subtitles: bool = True
    export_subtitle_files: bool = True

class ToolsConfig(BaseModel):
    ffmpeg_path: str = ""
    deno_path: str = ""
    mpv_path: str = ""

class LoggingConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    save_to_file: bool = True
    log_dir: Path = Path.home() / ".youtube-auto-clip-translator" / "logs"
    retention_days: int = 7

class AppConfig(BaseModel):
    theme: Literal["dark", "light"] = "dark"
    language: Literal["ja", "en"] = "ja"
    projects_dir: Path = Path.home() / ".youtube-auto-clip-translator" / "projects"
    auto_save_interval: int = 30
    recent_projects_limit: int = 10

class Settings(BaseModel):
    """アプリケーション全体の設定"""
    app: AppConfig = Field(default_factory=AppConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    whisper: WhisperConfig = Field(default_factory=WhisperConfig)
    fetcher: FetcherConfig = Field(default_factory=FetcherConfig)
    subtitle: SubtitleConfig = Field(default_factory=SubtitleConfig)
    editor: EditorConfig = Field(default_factory=EditorConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
```

---

## 4. 環境変数マッピング

| 環境変数 | 設定項目 | 説明 |
|----------|---------|------|
| GEMINI_API_KEY | llm.gemini.api_key | Gemini APIキー |
| YACT_PROJECTS_DIR | app.projects_dir | プロジェクト保存先 |
| YACT_LOG_LEVEL | logging.level | ログレベル |
| HF_TOKEN | whisper.hf_token | HuggingFaceトークン |

---

## 5. 設定読み込みフロー

```python
class ConfigManager:
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or self._default_config_path()

    def _default_config_path(self) -> Path:
        return Path.home() / ".youtube-auto-clip-translator" / "config.yaml"

    def load(self) -> Settings:
        """
        設定を読み込み

        1. デフォルト値でSettingsを作成
        2. config.yamlがあれば上書き
        3. 環境変数があればさらに上書き
        """
        settings = Settings()

        if self.config_path.exists():
            with open(self.config_path) as f:
                yaml_data = yaml.safe_load(f)
                settings = Settings(**yaml_data)

        # 環境変数で上書き
        if api_key := os.environ.get("GEMINI_API_KEY"):
            settings.llm.gemini.api_key = api_key

        if hf_token := os.environ.get("HF_TOKEN"):
            settings.whisper.hf_token = hf_token

        return settings

    def save(self, settings: Settings) -> None:
        """設定を保存"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump(settings.model_dump(), f, default_flow_style=False)

    def reset(self) -> Settings:
        """デフォルト設定にリセット"""
        settings = Settings()
        self.save(settings)
        return settings
```

---

## 6. GUI設定画面との対応

| 設定画面セクション | config.yamlセクション |
|-------------------|---------------------|
| 一般設定 | app |
| API設定 | llm.gemini, llm.ollama |
| 処理設定 | whisper |
| 字幕設定 | subtitle |
| 出力設定 | export, editor |

---

## 7. バリデーションルール

```python
from pydantic import validator

class WhisperConfig(BaseModel):
    # ...

    @validator("batch_size")
    def batch_size_positive(cls, v):
        if v < 1 or v > 64:
            raise ValueError("batch_size must be between 1 and 64")
        return v

class SubtitleConfig(BaseModel):
    # ...

    @validator("margin_v")
    def margin_v_range(cls, v):
        if v < 0 or v > 200:
            raise ValueError("margin_v must be between 0 and 200")
        return v
```

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-01-19 | 初版作成 |

