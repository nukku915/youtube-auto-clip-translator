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

---

## 16. 追加仕様

### 16.1 特殊文字エスケープ

ASS形式での特殊文字の扱い：

```python
def escape_ass_text(text: str) -> str:
    """ASS形式のテキストをエスケープ"""
    # ASSの特殊文字
    replacements = {
        "\\": "\\\\",     # バックスラッシュ
        "{": "\\{",       # 波括弧開始（スタイル制御に使用）
        "}": "\\}",       # 波括弧終了
        "\n": "\\N",      # 改行
    }

    for char, escaped in replacements.items():
        text = text.replace(char, escaped)

    return text

def escape_srt_text(text: str) -> str:
    """SRT形式のテキストをエスケープ"""
    # SRTでは特殊なエスケープは不要だが、HTMLタグに注意
    # 一部のプレーヤーは <i> <b> 等を解釈する
    replacements = {
        "<": "&lt;",
        ">": "&gt;",
    }

    for char, escaped in replacements.items():
        text = text.replace(char, escaped)

    return text

# 使用例
"""
入力: "Hello {world}"
ASS出力: "Hello \\{world\\}"

入力: "Line1\nLine2"
ASS出力: "Line1\\NLine2"
"""
```

### 16.2 RTL言語対応

**MVP では非対応**。アラビア語、ヘブライ語等の右から左に書く言語。

```python
# 将来対応時の設計
RTL_LANGUAGES = ["ar", "he", "fa", "ur"]

def is_rtl_language(lang_code: str) -> bool:
    """RTL言語かどうか判定"""
    return lang_code in RTL_LANGUAGES

def format_rtl_text(text: str, lang: str) -> str:
    """RTLテキストのフォーマット"""
    if is_rtl_language(lang):
        # Unicode制御文字を使用
        # RLM (Right-to-Left Mark): U+200F
        # RLE (Right-to-Left Embedding): U+202B
        return f"\u202B{text}\u202C"
    return text

# ASS形式でのRTL対応
"""
Style: Arabic,Arabic Typesetting,48,&HFFFFFF,&H000000,1,2,50
Dialogue: 0,0:00:01.00,0:00:04.00,Arabic,{\an7}مرحبا بالجميع
"""
# \an7 = 右上揃え（RTL用）
```

**MVPでの対応方針**:
- RTL言語が検出された場合、警告を表示
- 「この言語は現在サポートされていません」

### 16.3 絵文字対応

```python
import emoji
import unicodedata

def contains_emoji(text: str) -> bool:
    """テキストに絵文字が含まれるか"""
    return emoji.emoji_count(text) > 0

def get_emoji_aware_length(text: str) -> int:
    """絵文字を考慮した文字数カウント"""
    # 絵文字は1文字としてカウント（表示幅は2文字分の場合あり）
    return len(text) - emoji.emoji_count(text) + emoji.emoji_count(text) * 2

def check_font_emoji_support(font_path: Path) -> bool:
    """フォントが絵文字をサポートしているか確認"""
    # Noto Color Emoji等が必要
    ...

# フォントフォールバック設定
EMOJI_FONT_FALLBACK = {
    "windows": "Segoe UI Emoji",
    "macos": "Apple Color Emoji",
    "linux": "Noto Color Emoji",
}

# ASS形式での絵文字フォント指定
def create_ass_with_emoji_support(style_config: SubtitleStyleConfig) -> str:
    """絵文字対応ASSスタイルを生成"""
    import sys

    emoji_font = EMOJI_FONT_FALLBACK.get(sys.platform, "Noto Color Emoji")

    return f"""
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, Bold, Alignment, MarginV
Style: Default,{style_config.font_family},48,&HFFFFFF,&H000000,1,2,50
Style: Emoji,{emoji_font},48,&HFFFFFF,&H000000,0,2,50
"""
```

### 16.4 フォントフォールバック

```python
@dataclass
class FontConfig:
    primary: str = "Noto Sans JP"
    fallback_chain: List[str] = field(default_factory=lambda: [
        "Noto Sans CJK JP",
        "Hiragino Sans",
        "Yu Gothic",
        "MS Gothic",
        "sans-serif"
    ])

def find_available_font(config: FontConfig) -> str:
    """利用可能なフォントを検索"""
    from matplotlib import font_manager

    all_fonts = [f.name for f in font_manager.fontManager.ttflist]

    # プライマリフォントをチェック
    if config.primary in all_fonts:
        return config.primary

    # フォールバックチェーン
    for font in config.fallback_chain:
        if font in all_fonts:
            logger.warning(f"Font '{config.primary}' not found, using '{font}'")
            return font

    # 最終手段
    logger.warning("No preferred fonts found, using system default")
    return "sans-serif"

def get_font_path(font_name: str) -> Optional[Path]:
    """フォント名からパスを取得（FFmpeg用）"""
    from matplotlib import font_manager

    matches = font_manager.findSystemFonts(fontpaths=None, fontext='ttf')
    for path in matches:
        try:
            font = font_manager.FontProperties(fname=path)
            if font.get_name() == font_name:
                return Path(path)
        except:
            continue
    return None
```

### 16.5 行数が多い時の分割

```python
@dataclass
class LineSplitConfig:
    max_lines: int = 2
    max_chars_per_line: int = 40
    min_segment_duration: float = 1.5  # 分割後の最小表示時間

def split_long_subtitle(
    entry: SubtitleEntry,
    config: LineSplitConfig
) -> List[SubtitleEntry]:
    """長い字幕を複数に分割"""
    text = entry.text
    lines = text.split("\\N")  # ASS形式の改行

    # 行数がmax_lines以下ならそのまま
    if len(lines) <= config.max_lines:
        return [entry]

    # 分割が必要
    duration = entry.end - entry.start
    split_entries = []

    # 2行ずつのグループに分割
    for i in range(0, len(lines), config.max_lines):
        group_lines = lines[i:i + config.max_lines]
        group_text = "\\N".join(group_lines)

        # 時間を比例配分
        char_ratio = len(group_text) / len(text.replace("\\N", ""))
        group_duration = max(duration * char_ratio, config.min_segment_duration)

        split_entries.append(SubtitleEntry(
            id=entry.id * 100 + len(split_entries),
            start=entry.start + sum(e.end - e.start for e in split_entries),
            end=entry.start + sum(e.end - e.start for e in split_entries) + group_duration,
            text=group_text,
            style=entry.style
        ))

    return split_entries

def format_long_text(text: str, config: LineSplitConfig) -> List[str]:
    """長いテキストを適切な行に分割"""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        word_length = len(word)
        if current_length + word_length + 1 > config.max_chars_per_line:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_length = word_length
        else:
            current_line.append(word)
            current_length += word_length + 1

    if current_line:
        lines.append(" ".join(current_line))

    return lines
```

### 16.6 読み速度の自動調整

```python
@dataclass
class ReadingSpeedConfig:
    # 言語別の読み速度（文字/秒）
    chars_per_second: Dict[str, float] = field(default_factory=lambda: {
        "ja": 8.0,    # 日本語: 1秒に8文字
        "en": 15.0,   # 英語: 1秒に15文字（約3語）
        "zh": 6.0,    # 中国語: 1秒に6文字
        "ko": 10.0,   # 韓国語: 1秒に10文字
        "es": 15.0,   # スペイン語
        "fr": 14.0,   # フランス語
        "de": 14.0,   # ドイツ語
    })

    min_duration: float = 1.0     # 最小表示時間（秒）
    max_duration: float = 8.0     # 最大表示時間（秒）
    buffer_ratio: float = 1.2     # 余裕を持たせる係数

def calculate_optimal_duration(
    text: str,
    language: str,
    config: ReadingSpeedConfig = None
) -> float:
    """テキストの最適な表示時間を計算"""
    if config is None:
        config = ReadingSpeedConfig()

    cps = config.chars_per_second.get(language, 12.0)  # デフォルト: 12文字/秒

    # 文字数（改行等を除く）
    char_count = len(text.replace("\\N", "").replace(" ", ""))

    # 必要な読み取り時間
    required_time = char_count / cps * config.buffer_ratio

    # min/maxでクリップ
    return max(config.min_duration, min(config.max_duration, required_time))

def adjust_subtitle_timing(
    entries: List[SubtitleEntry],
    language: str,
    config: ReadingSpeedConfig = None
) -> List[SubtitleEntry]:
    """字幕のタイミングを読み速度に基づいて調整"""
    adjusted = []

    for entry in entries:
        optimal_duration = calculate_optimal_duration(entry.text, language, config)
        current_duration = entry.end - entry.start

        if current_duration < optimal_duration * 0.8:
            # 表示時間が短すぎる
            entry.flags.append("display_time_short")
            # 可能であれば延長（次の字幕とのギャップを確認）
            ...

        if current_duration > optimal_duration * 2.0:
            # 表示時間が長すぎる（分割を検討）
            entry.flags.append("display_time_long")

        adjusted.append(entry)

    return adjusted
```

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-01-19 | 初版作成 |
| 2026-01-19 | 追加仕様（特殊文字、絵文字、読み速度等）を追記 |
