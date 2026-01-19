# 字幕生成モジュール詳細計画書

## 1. 概要

### 目的
翻訳済みテキストと音声タイムスタンプから、動画に適した字幕ファイルを生成する

### 責務
- 字幕ファイルの生成（SRT/ASS/VTT）
- 音声波形に同期したタイミング調整
- 字幕スタイリング（フォント、色、位置）
- 通常動画/Shorts用のレイアウト最適化
- 二言語字幕の対応

---

## 2. 入出力仕様

### 入力
| 項目 | 型 | 必須 | 説明 |
|------|-----|------|------|
| segments | List[TranslatedSegment] | Yes | 翻訳済みセグメント |
| original_segments | List[TranscriptionSegment] | No | 原文セグメント（二言語用） |
| output_format | str | Yes | 出力形式（srt, ass, vtt） |
| style_config | SubtitleStyleConfig | No | スタイル設定 |
| video_format | str | No | 動画形式（normal, shorts） |

### 出力
```python
@dataclass
class SubtitleResult:
    file_path: Path                    # 生成された字幕ファイル
    format: str                        # フォーマット（srt, ass, vtt）
    subtitle_count: int                # 字幕数
    total_duration: float              # 総時間
    style_applied: SubtitleStyleConfig # 適用されたスタイル
```

---

## 3. 字幕データモデル

```python
@dataclass
class SubtitleEntry:
    id: int                    # 字幕ID
    start: float               # 開始時間（秒）
    end: float                 # 終了時間（秒）
    text: str                  # 表示テキスト
    original_text: Optional[str]  # 原文（二言語表示用）
    style: Optional[str]       # スタイル名（ASS用）
    position: Optional[tuple]  # 位置（x, y）

@dataclass
class SubtitleStyleConfig:
    # フォント設定
    font_family: str = "Noto Sans JP"
    font_size: int = 24
    font_weight: str = "bold"

    # 色設定
    primary_color: str = "#FFFFFF"      # メイン文字色
    outline_color: str = "#000000"      # 縁取り色
    shadow_color: str = "#00000080"     # 影色

    # 縁取り・影
    outline_width: int = 2
    shadow_depth: int = 1

    # 位置設定
    position: str = "bottom"  # top, middle, bottom
    margin_v: int = 20        # 垂直マージン
    margin_h: int = 20        # 水平マージン

    # アニメーション（ASS用）
    fade_in: int = 0          # フェードイン（ms）
    fade_out: int = 0         # フェードアウト（ms）

    # 二言語設定
    bilingual: bool = False
    original_font_size: int = 18
    original_color: str = "#CCCCCC"
```

---

## 4. 処理フロー

```
┌─────────────────────────────────────────────────────────┐
│              翻訳済みセグメント入力                       │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 1. タイミング最適化                                      │
│    ├─ 最小表示時間の確保（1.5秒以上）                    │
│    ├─ 重複解消                                          │
│    ├─ 読みやすい表示時間への調整                         │
│    └─ Word-level タイムスタンプからの補正               │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 2. テキスト整形                                          │
│    ├─ 1行あたりの最大文字数制限                          │
│    ├─ 適切な位置での改行                                 │
│    ├─ 句読点での分割                                     │
│    └─ 表示時間に基づく分割                               │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 3. スタイル適用                                          │
│    ├─ フォント設定                                       │
│    ├─ 色・縁取り設定                                     │
│    ├─ 位置設定                                          │
│    └─ Shorts用レイアウト調整                            │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 4. 字幕ファイル生成                                      │
│    ├─ pysubs2 でファイル生成                            │
│    └─ フォーマット変換（SRT/ASS/VTT）                   │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 SubtitleResult 返却                      │
└─────────────────────────────────────────────────────────┘
```

---

## 5. タイミング最適化アルゴリズム

### 5.1 読みやすさの基準

```python
TIMING_CONFIG = {
    "min_duration": 1.0,        # 最小表示時間（秒）
    "max_duration": 7.0,        # 最大表示時間（秒）
    "chars_per_second": 15,     # 1秒あたりの文字数（日本語）
    "chars_per_second_en": 25,  # 1秒あたりの文字数（英語）
    "gap_threshold": 0.1,       # 字幕間の最小ギャップ（秒）
}
```

### 5.2 表示時間計算

```python
def calculate_optimal_duration(text: str, language: str) -> float:
    """
    テキスト量に基づいて最適な表示時間を計算
    """
    cps = TIMING_CONFIG["chars_per_second"]
    if language == "en":
        cps = TIMING_CONFIG["chars_per_second_en"]

    char_count = len(text)
    optimal = char_count / cps

    # 最小・最大でクリップ
    return max(
        TIMING_CONFIG["min_duration"],
        min(TIMING_CONFIG["max_duration"], optimal)
    )
```

### 5.3 重複解消

```python
def resolve_overlaps(entries: List[SubtitleEntry]) -> List[SubtitleEntry]:
    """
    重複する字幕のタイミングを調整
    """
    result = []
    for i, entry in enumerate(entries):
        if i > 0 and entry.start < result[-1].end:
            # 重複あり：前の字幕を短縮
            gap = TIMING_CONFIG["gap_threshold"]
            result[-1].end = entry.start - gap
        result.append(entry)
    return result
```

---

## 6. テキスト整形ルール

### 6.1 改行ルール

```python
TEXT_FORMAT_CONFIG = {
    "max_chars_per_line": 40,      # 1行の最大文字数（日本語）
    "max_chars_per_line_en": 60,   # 1行の最大文字数（英語）
    "max_lines": 2,                # 最大行数
    "prefer_break_at": [           # 優先改行位置
        "。", "、", "！", "？",    # 日本語句読点
        ". ", ", ", "! ", "? ",   # 英語句読点
        " ",                       # スペース
    ],
}
```

### 6.2 Shorts用の調整

```python
SHORTS_FORMAT_CONFIG = {
    "max_chars_per_line": 20,      # 縦型なので短く
    "max_lines": 3,                # 行数は増やせる
    "font_size_multiplier": 1.3,   # フォントを大きく
    "position": "bottom",          # セーフエリア内
    "margin_v": 150,               # 下部にマージン（UIを避ける）
}
```

---

## 7. 出力フォーマット仕様

### 7.1 SRT形式

```
1
00:00:01,000 --> 00:00:04,000
こんにちは、皆さん

2
00:00:04,500 --> 00:00:07,000
今日は特別な動画です
```

### 7.2 ASS形式（スタイル付き）

```
[Script Info]
Title: Generated Subtitle
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, Bold, Alignment, MarginV
Style: Default,Noto Sans JP,48,&H00FFFFFF,&H00000000,1,2,50
Style: Original,Noto Sans JP,36,&H00CCCCCC,&H00000000,0,2,100

[Events]
Format: Layer, Start, End, Style, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,こんにちは、皆さん
Dialogue: 0,0:00:01.00,0:00:04.00,Original,Hello everyone
```

### 7.3 VTT形式

```
WEBVTT

00:00:01.000 --> 00:00:04.000
こんにちは、皆さん

00:00:04.500 --> 00:00:07.000
今日は特別な動画です
```

---

## 8. 二言語字幕

### 8.1 レイアウト

```
┌────────────────────────────────────────┐
│                                        │
│              動画画面                   │
│                                        │
│                                        │
├────────────────────────────────────────┤
│     Hello everyone          ← 原文     │
│     こんにちは、皆さん       ← 訳文     │
└────────────────────────────────────────┘
```

### 8.2 実装

```python
def create_bilingual_entry(
    translated: TranslatedSegment,
    config: SubtitleStyleConfig
) -> List[SubtitleEntry]:
    """
    二言語字幕エントリを生成
    """
    entries = []

    # 原文（上段）
    entries.append(SubtitleEntry(
        id=translated.id * 2,
        start=translated.start,
        end=translated.end,
        text=translated.original_text,
        style="Original",
        position=(0, config.margin_v + 50)
    ))

    # 訳文（下段）
    entries.append(SubtitleEntry(
        id=translated.id * 2 + 1,
        start=translated.start,
        end=translated.end,
        text=translated.translated_text,
        style="Default",
        position=(0, config.margin_v)
    ))

    return entries
```

---

## 9. 設定オプション

```python
@dataclass
class SubtitleGeneratorConfig:
    # 出力設定
    default_format: str = "ass"  # srt, ass, vtt
    encoding: str = "utf-8"

    # タイミング設定
    timing_config: dict = field(default_factory=lambda: TIMING_CONFIG)

    # テキスト整形
    text_format_config: dict = field(default_factory=lambda: TEXT_FORMAT_CONFIG)

    # スタイル
    style_config: SubtitleStyleConfig = field(default_factory=SubtitleStyleConfig)

    # 動画形式
    video_format: str = "normal"  # normal, shorts

    # 二言語
    bilingual: bool = False
```

---

## 10. 依存関係

### Python パッケージ
```
pysubs2>=1.8.0
```

---

## 11. ファイル構成

```
src/core/subtitle_generator/
├── __init__.py
├── generator.py        # メインクラス: SubtitleGenerator
├── timing.py           # タイミング調整
├── formatter.py        # テキスト整形
├── styler.py           # スタイル適用
├── models.py           # データモデル
├── config.py           # 設定
└── presets/
    ├── default.py      # デフォルトスタイル
    ├── shorts.py       # Shorts用スタイル
    └── bilingual.py    # 二言語用スタイル
```

---

## 12. インターフェース定義

### SubtitleGenerator クラス

```python
class SubtitleGenerator:
    def __init__(self, config: SubtitleGeneratorConfig = None):
        """初期化"""

    def generate(
        self,
        segments: List[TranslatedSegment],
        output_path: Path,
        original_segments: List[TranscriptionSegment] = None
    ) -> SubtitleResult:
        """
        字幕ファイルを生成

        Args:
            segments: 翻訳済みセグメント
            output_path: 出力パス
            original_segments: 原文セグメント（二言語用）

        Returns:
            SubtitleResult
        """

    def optimize_timing(
        self,
        entries: List[SubtitleEntry]
    ) -> List[SubtitleEntry]:
        """タイミングを最適化"""

    def format_text(
        self,
        text: str,
        language: str
    ) -> str:
        """テキストを整形（改行挿入など）"""

    def apply_style(
        self,
        entries: List[SubtitleEntry],
        style_config: SubtitleStyleConfig
    ) -> List[SubtitleEntry]:
        """スタイルを適用"""

    def convert_format(
        self,
        input_path: Path,
        output_format: str
    ) -> Path:
        """フォーマット変換"""

    def preview(
        self,
        entries: List[SubtitleEntry],
        video_resolution: tuple
    ) -> Image:
        """プレビュー画像を生成（GUI用）"""
```

---

## 13. 使用例

```python
from core.subtitle_generator import (
    SubtitleGenerator,
    SubtitleGeneratorConfig,
    SubtitleStyleConfig
)

# スタイル設定
style = SubtitleStyleConfig(
    font_family="Noto Sans JP",
    font_size=48,
    primary_color="#FFFFFF",
    outline_color="#000000",
    outline_width=3,
    bilingual=True
)

# ジェネレーター設定
config = SubtitleGeneratorConfig(
    default_format="ass",
    video_format="normal",
    style_config=style,
    bilingual=True
)

generator = SubtitleGenerator(config)

# 字幕生成
result = generator.generate(
    segments=translated_segments,
    output_path=Path("./output/subtitles.ass"),
    original_segments=original_segments
)

print(f"Generated: {result.file_path}")
print(f"Subtitle count: {result.subtitle_count}")
```

---

## 14. フォントの埋め込み

### 推奨フォント
| 言語 | フォント | ライセンス |
|------|---------|-----------|
| 日本語 | Noto Sans JP | OFL |
| 英語 | Noto Sans | OFL |
| 汎用 | M PLUS 1p | OFL |

### フォント埋め込み（ASS）
ASS形式ではフォントを埋め込むことはできないが、FFmpegでの焼き付け時にフォントを指定できる。

---

## 15. テスト項目

### ユニットテスト
- [ ] タイミング最適化
- [ ] テキスト改行処理
- [ ] 各フォーマットの出力
- [ ] 二言語字幕生成
- [ ] スタイル適用

### 統合テスト
- [ ] 長時間動画（1時間以上）
- [ ] 多数の字幕（1000件以上）
- [ ] 特殊文字を含むテキスト
- [ ] Shorts用レイアウト
- [ ] FFmpegでの焼き付け動作確認
