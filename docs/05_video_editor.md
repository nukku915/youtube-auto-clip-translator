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

---

## 15. 追加仕様

### 15.1 複数音声トラック

多言語音声トラックを持つ動画の扱い：

```python
@dataclass
class AudioTrackInfo:
    index: int
    language: str
    codec: str
    channels: int
    sample_rate: int
    is_default: bool

def get_audio_tracks(video_path: Path) -> List[AudioTrackInfo]:
    """動画の音声トラック一覧を取得"""
    result = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "a",
        str(video_path)
    ], capture_output=True, text=True)

    data = json.loads(result.stdout)
    tracks = []
    for stream in data.get("streams", []):
        tracks.append(AudioTrackInfo(
            index=stream["index"],
            language=stream.get("tags", {}).get("language", "und"),
            codec=stream["codec_name"],
            channels=stream["channels"],
            sample_rate=int(stream["sample_rate"]),
            is_default=stream.get("disposition", {}).get("default", 0) == 1
        ))
    return tracks

def select_audio_track(
    video_path: Path,
    preferred_language: str = None
) -> int:
    """使用する音声トラックを選択"""
    tracks = get_audio_tracks(video_path)

    if not tracks:
        raise NoAudioTrackError("音声トラックがありません")

    if preferred_language:
        for track in tracks:
            if track.language == preferred_language:
                return track.index

    # デフォルトトラックを返す
    for track in tracks:
        if track.is_default:
            return track.index

    return tracks[0].index

# FFmpegでの音声トラック選択
"""
ffmpeg -i input.mp4 -map 0:v:0 -map 0:a:{track_index} output.mp4
"""
```

### 15.2 キーフレーム問題

正確な切り出しのためのキーフレーム考慮：

```python
@dataclass
class KeyframeInfo:
    time: float
    pts: int

def get_keyframes(video_path: Path, start: float, end: float) -> List[KeyframeInfo]:
    """指定範囲のキーフレームを取得"""
    result = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-select_streams", "v:0",
        "-show_entries", "packet=pts_time,flags",
        "-of", "csv=p=0",
        "-read_intervals", f"{start}%{end}",
        str(video_path)
    ], capture_output=True, text=True)

    keyframes = []
    for line in result.stdout.strip().split("\n"):
        parts = line.split(",")
        if len(parts) >= 2 and "K" in parts[1]:  # K = keyframe
            keyframes.append(KeyframeInfo(
                time=float(parts[0]),
                pts=int(parts[0])
            ))
    return keyframes

def find_nearest_keyframe(
    keyframes: List[KeyframeInfo],
    target_time: float,
    prefer: str = "before"  # "before" or "after"
) -> float:
    """目標時間に最も近いキーフレームを見つける"""
    if not keyframes:
        return target_time

    if prefer == "before":
        candidates = [kf for kf in keyframes if kf.time <= target_time]
        return max(candidates, key=lambda kf: kf.time).time if candidates else keyframes[0].time
    else:
        candidates = [kf for kf in keyframes if kf.time >= target_time]
        return min(candidates, key=lambda kf: kf.time).time if candidates else keyframes[-1].time

def determine_cut_strategy(
    video_path: Path,
    start: float,
    end: float,
    precision: str = "frame"  # "keyframe" or "frame"
) -> dict:
    """
    切り出し戦略を決定

    Returns:
        {
            "use_copy": bool,       # 無劣化コピー可能か
            "adjusted_start": float, # 調整後の開始時間
            "adjusted_end": float,   # 調整後の終了時間
            "requires_reencode": bool
        }
    """
    keyframes = get_keyframes(video_path, start - 10, end + 10)

    if precision == "keyframe":
        # キーフレーム単位（高速、無劣化）
        adjusted_start = find_nearest_keyframe(keyframes, start, "before")
        adjusted_end = find_nearest_keyframe(keyframes, end, "after")
        return {
            "use_copy": True,
            "adjusted_start": adjusted_start,
            "adjusted_end": adjusted_end,
            "requires_reencode": False
        }
    else:
        # フレーム単位（正確、再エンコード必要）
        return {
            "use_copy": False,
            "adjusted_start": start,
            "adjusted_end": end,
            "requires_reencode": True
        }
```

### 15.3 フレーム単位精度

```python
@dataclass
class FramePrecisionConfig:
    # 精度モード
    mode: str = "frame"  # "keyframe", "frame", "millisecond"

    # フレームレート（自動検出も可能）
    fps: Optional[float] = None

def time_to_frame(time: float, fps: float) -> int:
    """時間をフレーム番号に変換"""
    return int(time * fps)

def frame_to_time(frame: int, fps: float) -> float:
    """フレーム番号を時間に変換"""
    return frame / fps

def snap_to_frame(time: float, fps: float) -> float:
    """時間を最も近いフレーム境界にスナップ"""
    frame = round(time * fps)
    return frame / fps

def create_precise_cut_command(
    video_path: Path,
    start: float,
    end: float,
    output_path: Path,
    config: FramePrecisionConfig
) -> List[str]:
    """精密な切り出しコマンドを生成"""
    # フレームレート取得
    if config.fps is None:
        config.fps = get_video_fps(video_path)

    if config.mode == "keyframe":
        # 無劣化切り出し（キーフレーム境界）
        return [
            "ffmpeg", "-i", str(video_path),
            "-ss", str(start),
            "-to", str(end),
            "-c", "copy",
            str(output_path)
        ]
    else:
        # 再エンコード（フレーム精度）
        snapped_start = snap_to_frame(start, config.fps)
        snapped_end = snap_to_frame(end, config.fps)

        return [
            "ffmpeg", "-i", str(video_path),
            "-ss", str(snapped_start),
            "-to", str(snapped_end),
            "-c:v", "libx264",
            "-c:a", "aac",
            str(output_path)
        ]
```

### 15.4 一時ファイルクリーンアップ

```python
@dataclass
class TempFileConfig:
    # 一時ファイルの保存先
    temp_dir: Path = Path.home() / ".youtube-auto-clip-translator" / "temp"

    # 自動削除設定
    cleanup_on_success: bool = True
    cleanup_on_error: bool = False
    retention_hours: int = 24

class TempFileManager:
    """一時ファイルの管理"""

    def __init__(self, config: TempFileConfig = None):
        self.config = config or TempFileConfig()
        self.config.temp_dir.mkdir(parents=True, exist_ok=True)
        self.created_files: List[Path] = []

    def create_temp_file(self, suffix: str = ".mp4") -> Path:
        """一時ファイルを作成"""
        temp_file = self.config.temp_dir / f"temp_{uuid.uuid4().hex}{suffix}"
        self.created_files.append(temp_file)
        return temp_file

    def cleanup(self, force: bool = False) -> int:
        """一時ファイルを削除"""
        deleted = 0
        for file in self.created_files:
            try:
                if file.exists():
                    file.unlink()
                    deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete temp file {file}: {e}")
        self.created_files.clear()
        return deleted

    def cleanup_old_files(self) -> int:
        """古い一時ファイルを削除"""
        threshold = datetime.now() - timedelta(hours=self.config.retention_hours)
        deleted = 0

        for file in self.config.temp_dir.glob("temp_*"):
            try:
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if mtime < threshold:
                    file.unlink()
                    deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete old temp file {file}: {e}")

        return deleted

    def get_total_size(self) -> int:
        """一時ファイルの合計サイズ"""
        return sum(f.stat().st_size for f in self.config.temp_dir.glob("*") if f.is_file())

# コンテキストマネージャーとして使用
class VideoEditSession:
    """動画編集セッション（自動クリーンアップ付き）"""

    def __init__(self):
        self.temp_manager = TempFileManager()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # 正常終了
            if self.temp_manager.config.cleanup_on_success:
                self.temp_manager.cleanup()
        else:
            # エラー発生
            if self.temp_manager.config.cleanup_on_error:
                self.temp_manager.cleanup()

# 使用例
with VideoEditSession() as session:
    temp_file = session.temp_manager.create_temp_file()
    # 処理...
# セッション終了時に自動クリーンアップ
```

### 15.5 プログレス計算方法

```python
@dataclass
class ProgressWeight:
    """各処理ステップの重み付け"""
    segment_cut: float = 0.2      # セグメント切り出し
    title_card: float = 0.1       # タイトルカード生成
    concat: float = 0.1           # 結合
    subtitle_burn: float = 0.2    # 字幕焼き付け
    encode: float = 0.4           # 最終エンコード

class ProgressTracker:
    """進捗追跡"""

    def __init__(self, weights: ProgressWeight = None):
        self.weights = weights or ProgressWeight()
        self.current_step: str = ""
        self.step_progress: float = 0.0
        self.completed_steps: Dict[str, float] = {}

    def get_total_progress(self) -> float:
        """全体進捗率を計算（0-100）"""
        total = 0.0

        # 完了したステップ
        for step, _ in self.completed_steps.items():
            total += getattr(self.weights, step, 0) * 100

        # 現在のステップ
        if self.current_step:
            step_weight = getattr(self.weights, self.current_step, 0)
            total += step_weight * self.step_progress

        return min(total, 100.0)

    def start_step(self, step_name: str) -> None:
        """ステップを開始"""
        self.current_step = step_name
        self.step_progress = 0.0

    def update_step_progress(self, progress: float) -> None:
        """ステップ内の進捗を更新（0-100）"""
        self.step_progress = progress

    def complete_step(self) -> None:
        """ステップを完了"""
        if self.current_step:
            self.completed_steps[self.current_step] = 100.0
            self.current_step = ""
            self.step_progress = 0.0

# FFmpegの進捗をパース
def parse_ffmpeg_progress(line: str, total_duration: float) -> Optional[float]:
    """FFmpeg出力から進捗を抽出"""
    # "time=00:01:30.50" のようなパターンを探す
    match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
    if match:
        hours, minutes, seconds, centiseconds = map(int, match.groups())
        current_time = hours * 3600 + minutes * 60 + seconds + centiseconds / 100
        return (current_time / total_duration) * 100
    return None
```

### 15.6 FFmpegエラー解析

```python
@dataclass
class FFmpegError:
    exit_code: int
    error_type: str
    message: str
    user_friendly_message: str
    is_retryable: bool

# エラーパターン
FFMPEG_ERROR_PATTERNS = {
    r"No such file or directory": FFmpegError(
        exit_code=1,
        error_type="file_not_found",
        message="Input file not found",
        user_friendly_message="入力ファイルが見つかりません",
        is_retryable=False
    ),
    r"Permission denied": FFmpegError(
        exit_code=1,
        error_type="permission_denied",
        message="Permission denied",
        user_friendly_message="ファイルへのアクセス権限がありません",
        is_retryable=False
    ),
    r"No space left on device": FFmpegError(
        exit_code=1,
        error_type="disk_full",
        message="Disk full",
        user_friendly_message="ディスク容量が不足しています",
        is_retryable=False
    ),
    r"Invalid data found": FFmpegError(
        exit_code=1,
        error_type="invalid_input",
        message="Invalid input data",
        user_friendly_message="入力ファイルが破損しているか、対応していない形式です",
        is_retryable=False
    ),
    r"Connection (refused|timed out)": FFmpegError(
        exit_code=1,
        error_type="network_error",
        message="Network error",
        user_friendly_message="ネットワーク接続に問題があります",
        is_retryable=True
    ),
    r"(CUDA|NVENC|encoder).*(failed|error)": FFmpegError(
        exit_code=1,
        error_type="hw_encoder_error",
        message="Hardware encoder failed",
        user_friendly_message="ハードウェアエンコーダーでエラーが発生しました。ソフトウェアエンコードに切り替えます",
        is_retryable=True
    ),
}

def analyze_ffmpeg_error(stderr: str, exit_code: int) -> FFmpegError:
    """FFmpegエラー出力を解析"""
    for pattern, error in FFMPEG_ERROR_PATTERNS.items():
        if re.search(pattern, stderr, re.IGNORECASE):
            return FFmpegError(
                exit_code=exit_code,
                error_type=error.error_type,
                message=error.message,
                user_friendly_message=error.user_friendly_message,
                is_retryable=error.is_retryable
            )

    # 未知のエラー
    return FFmpegError(
        exit_code=exit_code,
        error_type="unknown",
        message=stderr[:500],  # 最初の500文字
        user_friendly_message="動画処理中に予期しないエラーが発生しました",
        is_retryable=False
    )
```

### 15.7 音声・映像の同期ズレ対策

```python
@dataclass
class SyncConfig:
    # 許容される同期ズレ（秒）
    max_drift: float = 0.05  # 50ms

    # 同期方法
    sync_method: str = "audio"  # "audio" or "video"

def check_av_sync(video_path: Path) -> float:
    """音声と映像の同期ズレを検出（秒）"""
    result = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-show_entries", "stream=start_time",
        "-of", "json",
        str(video_path)
    ], capture_output=True, text=True)

    data = json.loads(result.stdout)
    streams = data.get("streams", [])

    video_start = None
    audio_start = None

    for stream in streams:
        start_time = float(stream.get("start_time", 0))
        if stream.get("codec_type") == "video":
            video_start = start_time
        elif stream.get("codec_type") == "audio":
            audio_start = start_time

    if video_start is not None and audio_start is not None:
        return audio_start - video_start

    return 0.0

def fix_av_sync(
    video_path: Path,
    output_path: Path,
    drift: float
) -> None:
    """音声と映像の同期を修正"""
    if abs(drift) < 0.001:
        # ズレなし
        shutil.copy(video_path, output_path)
        return

    if drift > 0:
        # 音声が遅れている → 音声を早める
        filter_str = f"adelay=0|0,aresample=async=1:first_pts=0"
    else:
        # 映像が遅れている → 映像を早める
        filter_str = f"setpts=PTS-{abs(drift)}/TB"

    subprocess.run([
        "ffmpeg", "-i", str(video_path),
        "-af" if drift > 0 else "-vf", filter_str,
        "-c:v", "copy" if drift > 0 else "libx264",
        "-c:a", "libx264" if drift > 0 else "copy",
        str(output_path)
    ], check=True)

def concat_with_sync_correction(
    video_paths: List[Path],
    output_path: Path
) -> None:
    """同期ズレを補正しながら動画を結合"""
    # 各動画の同期をチェック
    corrected_paths = []

    for i, path in enumerate(video_paths):
        drift = check_av_sync(path)
        if abs(drift) > 0.05:  # 50ms以上のズレ
            logger.warning(f"A/V sync drift detected in {path}: {drift*1000:.1f}ms")
            corrected_path = path.with_suffix(f".sync{path.suffix}")
            fix_av_sync(path, corrected_path, drift)
            corrected_paths.append(corrected_path)
        else:
            corrected_paths.append(path)

    # 結合
    concat_videos(corrected_paths, output_path)

    # 一時ファイル削除
    for path in corrected_paths:
        if path not in video_paths and path.exists():
            path.unlink()
```

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-01-19 | 初版作成 |
| 2026-01-19 | 追加仕様（キーフレーム、同期ズレ、プログレス等）を追記 |
