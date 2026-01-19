# 動画編集モジュール詳細計画書

## 1. 概要

### 目的
FFmpegを使用して動画の切り抜き、字幕焼き付け、タイトルカットイン挿入などの編集を行う

### 責務
- 動画の切り抜き（トリミング）
- 複数セグメントの結合
- 字幕の焼き付け（ハードサブ）
- タイトルカットインの挿入
- アスペクト比変換（16:9 ⇔ 9:16）
- エンコード・圧縮

---

## 2. 入出力仕様

### 入力
| 項目 | 型 | 必須 | 説明 |
|------|-----|------|------|
| video_path | Path | Yes | 元動画ファイル |
| segments | List[EditSegment] | Yes | 編集セグメント情報 |
| subtitle_path | Path | No | 字幕ファイル |
| output_config | OutputConfig | Yes | 出力設定 |

### EditSegment
```python
@dataclass
class EditSegment:
    id: int                        # セグメントID
    start: float                   # 開始時間（秒）
    end: float                     # 終了時間（秒）
    title: Optional[str]           # タイトルカットイン
    title_duration: float = 2.0    # タイトル表示時間
    transition: str = "none"       # トランジション（none, fade, dissolve）
    speed: float = 1.0             # 再生速度（1.0 = 通常）
```

### 出力
```python
@dataclass
class EditResult:
    output_path: Path              # 出力動画パス
    duration: float                # 出力動画の長さ
    resolution: tuple              # 解像度 (width, height)
    file_size: int                 # ファイルサイズ（bytes）
    encoding_time: float           # エンコード時間（秒）
```

---

## 3. 処理フロー

```
┌─────────────────────────────────────────────────────────┐
│                    編集指示入力                          │
│  (セグメント情報、字幕、タイトル、出力設定)               │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 1. セグメント切り出し                                    │
│    ├─ 各セグメントを個別ファイルとして抽出               │
│    └─ 無劣化切り出し（-c copy）可能な場合は使用          │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 2. タイトルカットイン生成                                │
│    ├─ 各セグメント用のタイトル動画を生成                 │
│    ├─ テキスト + 背景 + アニメーション                   │
│    └─ セグメント動画と同じ解像度・フレームレート          │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 3. セグメント結合                                        │
│    ├─ タイトル + セグメント動画を順番に結合              │
│    ├─ トランジション効果の適用                           │
│    └─ concat demuxer または filter_complex 使用          │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 4. 字幕焼き付け（オプション）                            │
│    ├─ ASS字幕のスタイルを保持して焼き付け                │
│    └─ subtitles フィルター使用                           │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 5. アスペクト比変換（Shorts用）                          │
│    ├─ 16:9 → 9:16 変換                                  │
│    ├─ クロップ or パディング                             │
│    └─ 顔検出による追従クロップ（オプション）             │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 6. 最終エンコード                                        │
│    ├─ コーデック設定（H.264/H.265）                     │
│    ├─ ビットレート調整                                   │
│    └─ 品質設定                                          │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   EditResult 返却                        │
└─────────────────────────────────────────────────────────┘
```

---

## 4. タイトルカットイン

### 4.1 デザイン仕様

#### 通常動画用（16:9）
```
┌────────────────────────────────────────────────────────┐
│                                                        │
│                                                        │
│                   ┌──────────────┐                     │
│                   │  Chapter 1   │  ← タイトル        │
│                   │  オープニング │  ← サブタイトル    │
│                   └──────────────┘                     │
│                                                        │
│                                                        │
└────────────────────────────────────────────────────────┘
```

#### Shorts用（9:16）
```
┌──────────────────────┐
│                      │
│                      │
│   ┌──────────────┐   │
│   │  Chapter 1   │   │
│   │  オープニング │   │
│   └──────────────┘   │
│                      │
│                      │
│                      │
│                      │
│                      │
└──────────────────────┘
```

### 4.2 タイトルカットイン設定

```python
@dataclass
class TitleCardConfig:
    # テキスト設定
    font_family: str = "Noto Sans JP"
    title_font_size: int = 72
    subtitle_font_size: int = 36
    text_color: str = "#FFFFFF"

    # 背景設定
    background_type: str = "solid"  # solid, gradient, blur
    background_color: str = "#000000"
    background_opacity: float = 0.8

    # アニメーション
    animation: str = "fade"  # none, fade, slide, zoom
    duration: float = 2.0    # 表示時間（秒）
    fade_in: float = 0.3     # フェードイン時間
    fade_out: float = 0.3    # フェードアウト時間

    # 位置
    position: str = "center"  # center, top, bottom
```

### 4.3 FFmpeg コマンド例（タイトル生成）

```bash
ffmpeg -f lavfi -i color=c=black:s=1920x1080:d=2 \
  -vf "drawtext=fontfile='NotoSansJP-Bold.ttf':
       text='Chapter 1':
       fontsize=72:
       fontcolor=white:
       x=(w-text_w)/2:
       y=(h-text_h)/2-50,
       drawtext=fontfile='NotoSansJP-Regular.ttf':
       text='オープニング':
       fontsize=36:
       fontcolor=white:
       x=(w-text_w)/2:
       y=(h-text_h)/2+50,
       fade=t=in:st=0:d=0.3,
       fade=t=out:st=1.7:d=0.3" \
  -c:v libx264 -t 2 title_card.mp4
```

---

## 5. アスペクト比変換（Shorts用）

### 5.1 変換方式: パディング + グラスモーフィズム背景

**決定事項**: 元動画のアスペクト比を維持し、余白にデザイン背景を配置

```
┌─────────────────────┐
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │ ← グラスモーフィズム背景
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │   （元動画をぼかし + 暗く）
├─────────────────────┤
│ ┌─────────────────┐ │
│ │                 │ │
│ │   元動画 16:9   │ │ ← アスペクト比維持
│ │   最大サイズ    │ │
│ │                 │ │
│ └─────────────────┘ │
├─────────────────────┤
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
│                     │
│   こんにちは        │ ← 字幕（下部余白に配置）
│                     │
└─────────────────────┘
```

### 5.2 背景スタイル設定

```python
@dataclass
class ShortsBackgroundConfig:
    # 背景スタイル
    style: str = "glassmorphism"  # glassmorphism, solid, gradient

    # グラスモーフィズム設定
    blur_radius: int = 30         # ぼかし半径
    brightness: float = -0.3      # 明度調整（暗くする）
    saturation: float = 0.8       # 彩度

    # ソリッドカラー（style="solid"の場合）
    solid_color: str = "#000000"

    # グラデーション（style="gradient"の場合）
    gradient_start: str = "#1a1a2e"
    gradient_end: str = "#16213e"
```

### 5.3 FFmpeg コマンド（グラスモーフィズム）

```bash
ffmpeg -i input.mp4 -filter_complex "
  # 背景: 拡大してクロップ + ぼかし + 暗く
  [0:v]scale=1080:1920:force_original_aspect_ratio=increase,
       crop=1080:1920,
       boxblur=30:30,
       eq=brightness=-0.3:saturation=0.8[bg];

  # 前景: アスペクト比維持でスケール
  [0:v]scale=1080:-1:force_original_aspect_ratio=decrease[fg];

  # 合成: 中央配置
  [bg][fg]overlay=(W-w)/2:(H-h)/2[out]
" -map "[out]" -map 0:a -c:v libx264 -c:a aac output_shorts.mp4
```

### 5.4 変換関数

```python
def convert_to_shorts(
    input_path: Path,
    output_path: Path,
    config: ShortsBackgroundConfig = None
) -> Path:
    """
    16:9 動画を 9:16 Shorts形式に変換

    - 元動画のアスペクト比を維持
    - グラスモーフィズム背景を適用
    - 字幕は下部余白に配置
    """
    if config is None:
        config = ShortsBackgroundConfig()

    if config.style == "glassmorphism":
        filter_complex = build_glassmorphism_filter(config)
    elif config.style == "solid":
        filter_complex = build_solid_filter(config)
    else:
        filter_complex = build_gradient_filter(config)

    # FFmpeg実行
    ...
```

### 5.5 字幕位置の自動調整

Shorts変換時は字幕位置を下部余白に移動:

```python
SHORTS_SUBTITLE_CONFIG = {
    "position": "bottom",
    "margin_v": 150,        # 下部マージン（UIを避ける）
    "font_size": 36,        # やや大きめ
    "max_chars_per_line": 20,  # 短く
}
```

---

## 6. 字幕焼き付け

### 6.1 FFmpeg コマンド

```bash
# ASS字幕の焼き付け
ffmpeg -i input.mp4 \
  -vf "ass=subtitles.ass:fontsdir=/path/to/fonts" \
  -c:v libx264 -c:a copy output.mp4
```

### 6.2 フォント埋め込み

```python
def get_subtitle_filter(
    subtitle_path: Path,
    fonts_dir: Path = None
) -> str:
    """
    字幕焼き付けフィルターを生成
    """
    filter_str = f"ass={subtitle_path}"
    if fonts_dir:
        filter_str += f":fontsdir={fonts_dir}"
    return filter_str
```

---

## 7. エンコード設定

### 7.1 プリセット

```python
@dataclass
class EncodingPreset:
    name: str
    video_codec: str
    audio_codec: str
    video_bitrate: str
    audio_bitrate: str
    crf: int
    preset: str

# プリセット定義
PRESETS = {
    "high_quality": EncodingPreset(
        name="High Quality",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="8M",
        audio_bitrate="192k",
        crf=18,
        preset="slow"
    ),
    "balanced": EncodingPreset(
        name="Balanced",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="5M",
        audio_bitrate="128k",
        crf=23,
        preset="medium"
    ),
    "fast": EncodingPreset(
        name="Fast",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="3M",
        audio_bitrate="128k",
        crf=28,
        preset="fast"
    ),
    "shorts": EncodingPreset(
        name="YouTube Shorts",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="4M",
        audio_bitrate="128k",
        crf=23,
        preset="medium"
    ),
}
```

### 7.2 ハードウェアアクセラレーション

```python
@dataclass
class HWAccelConfig:
    enabled: bool = True
    encoder: str = "auto"  # auto, nvenc, videotoolbox, vaapi, qsv

def detect_hw_encoder() -> str:
    """
    利用可能なハードウェアエンコーダーを検出
    """
    # NVIDIA GPU
    if check_nvenc_available():
        return "h264_nvenc"
    # Apple Silicon
    if check_videotoolbox_available():
        return "h264_videotoolbox"
    # Intel QSV
    if check_qsv_available():
        return "h264_qsv"
    # ソフトウェアエンコード
    return "libx264"
```

---

## 8. 出力設定

```python
@dataclass
class OutputConfig:
    # 出力形式
    format: str = "mp4"              # mp4, webm, mov
    video_format: str = "normal"     # normal, shorts

    # 解像度
    resolution: Optional[tuple] = None  # None = 元動画と同じ
    max_resolution: tuple = (1920, 1080)

    # エンコード
    preset: str = "balanced"         # プリセット名
    hw_accel: bool = True            # ハードウェアアクセラレーション

    # 字幕
    burn_subtitles: bool = True      # 字幕焼き付け
    subtitle_path: Optional[Path] = None

    # タイトルカード
    include_title_cards: bool = True
    title_card_config: TitleCardConfig = field(default_factory=TitleCardConfig)

    # 出力パス
    output_dir: Path = Path("./output")
    filename_template: str = "{title}_{index}"
```

---

## 9. 依存関係

### 外部ツール
| ツール | バージョン | 用途 |
|--------|-----------|------|
| FFmpeg | 5.0+ | 動画編集・エンコード |
| FFprobe | 5.0+ | 動画情報取得 |

### Python パッケージ
```
ffmpeg-python>=0.2.0
```

---

## 10. ファイル構成

```
src/core/video_editor/
├── __init__.py
├── editor.py           # メインクラス: VideoEditor
├── segment.py          # セグメント処理
├── title_card.py       # タイトルカード生成
├── aspect_ratio.py     # アスペクト比変換
├── subtitle_burner.py  # 字幕焼き付け
├── encoder.py          # エンコード処理
├── ffmpeg_wrapper.py   # FFmpegラッパー
├── models.py           # データモデル
├── config.py           # 設定
├── presets/
│   ├── encoding.py     # エンコードプリセット
│   └── title_card.py   # タイトルカードプリセット
└── exceptions.py       # カスタム例外
```

---

## 11. インターフェース定義

### VideoEditor クラス

```python
class VideoEditor:
    def __init__(self, config: OutputConfig = None):
        """初期化"""

    async def edit(
        self,
        video_path: Path,
        segments: List[EditSegment],
        subtitle_path: Path = None,
        progress_callback: Callable[[float, str], None] = None
    ) -> EditResult:
        """
        動画を編集

        Args:
            video_path: 元動画パス
            segments: 編集セグメント
            subtitle_path: 字幕ファイルパス
            progress_callback: 進捗コールバック

        Returns:
            EditResult
        """

    async def cut_segment(
        self,
        video_path: Path,
        start: float,
        end: float,
        output_path: Path
    ) -> Path:
        """単一セグメントの切り出し"""

    async def concat_videos(
        self,
        video_paths: List[Path],
        output_path: Path
    ) -> Path:
        """動画の結合"""

    async def create_title_card(
        self,
        title: str,
        subtitle: str,
        output_path: Path,
        config: TitleCardConfig = None
    ) -> Path:
        """タイトルカード生成"""

    async def burn_subtitles(
        self,
        video_path: Path,
        subtitle_path: Path,
        output_path: Path
    ) -> Path:
        """字幕焼き付け"""

    async def convert_to_shorts(
        self,
        video_path: Path,
        output_path: Path,
        mode: str = "crop_center"
    ) -> Path:
        """Shorts形式に変換"""

    def get_video_info(self, video_path: Path) -> dict:
        """動画情報を取得"""

    def cancel(self) -> None:
        """処理をキャンセル"""
```

---

## 12. 使用例

```python
from core.video_editor import (
    VideoEditor,
    OutputConfig,
    EditSegment,
    TitleCardConfig
)

# 編集セグメント定義
segments = [
    EditSegment(
        id=1,
        start=10.0,
        end=60.0,
        title="Chapter 1: オープニング",
        title_duration=2.0
    ),
    EditSegment(
        id=2,
        start=120.0,
        end=180.0,
        title="Chapter 2: メイン解説",
        title_duration=2.0
    ),
]

# 出力設定
config = OutputConfig(
    video_format="normal",
    preset="balanced",
    burn_subtitles=True,
    subtitle_path=Path("./subtitles.ass"),
    include_title_cards=True
)

editor = VideoEditor(config)

# 編集実行
result = await editor.edit(
    video_path=Path("./original.mp4"),
    segments=segments,
    progress_callback=lambda p, s: print(f"[{p:.1f}%] {s}")
)

print(f"Output: {result.output_path}")
print(f"Duration: {result.duration}s")
print(f"File size: {result.file_size / 1024 / 1024:.1f}MB")

# Shorts版も生成
shorts_result = await editor.convert_to_shorts(
    video_path=result.output_path,
    output_path=Path("./output_shorts.mp4"),
    mode="crop_center"
)
```

---

## 13. パフォーマンス目安

### エンコード時間（10分の動画）
| 環境 | プリセット | 時間 |
|------|-----------|------|
| RTX 4090 (NVENC) | balanced | ~30秒 |
| M2 Pro (VideoToolbox) | balanced | ~1分 |
| CPU 8コア (libx264) | balanced | ~5分 |
| CPU 8コア (libx264) | slow | ~15分 |

### 出力ファイルサイズ目安
| プリセット | 10分動画 (1080p) |
|-----------|-----------------|
| high_quality | ~600MB |
| balanced | ~400MB |
| fast | ~250MB |

---

## 14. テスト項目

### ユニットテスト
- [ ] セグメント切り出し精度
- [ ] タイトルカード生成
- [ ] 動画結合
- [ ] 字幕焼き付け
- [ ] アスペクト比変換

### 統合テスト
- [ ] 複数セグメントの編集
- [ ] 長時間動画（1時間以上）
- [ ] 各種コーデック対応
- [ ] ハードウェアエンコーダー
- [ ] エラーリカバリ
