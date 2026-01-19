# 音声処理・文字起こしモジュール詳細計画書

## 1. 概要

### 目的
動画ファイルから音声を抽出し、WhisperXを使用して高精度な文字起こしを行う

### 責務
- 動画から音声トラックの抽出
- 音声の前処理（正規化・ノイズ除去）
- WhisperXによる文字起こし
- Word-level タイムスタンプの取得
- 話者分離（オプション）
- 言語自動検出

---

## 2. 入出力仕様

### 入力
| 項目 | 型 | 必須 | 説明 |
|------|-----|------|------|
| video_path | Path | Yes | 動画ファイルパス |
| language | string | No | 言語コード（自動検出時はNone） |
| enable_diarization | bool | No | 話者分離を有効化 |

### 出力
```python
@dataclass
class TranscriptionResult:
    segments: List[TranscriptionSegment]  # 文字起こしセグメント
    language: str                          # 検出/指定された言語
    audio_path: Path                       # 抽出した音声ファイル
    duration: float                        # 音声長（秒）
    word_count: int                        # 総単語数

@dataclass
class TranscriptionSegment:
    id: int                    # セグメントID
    start: float               # 開始時間（秒）
    end: float                 # 終了時間（秒）
    text: str                  # テキスト
    words: List[WordTiming]    # 単語レベルタイミング
    speaker: Optional[str]     # 話者ID（diarization有効時）
    confidence: float          # 信頼度スコア

@dataclass
class WordTiming:
    word: str                  # 単語
    start: float               # 開始時間（秒）
    end: float                 # 終了時間（秒）
    confidence: float          # 信頼度
```

---

## 3. 処理フロー

```
┌─────────────────────────────────────────────────────────┐
│                   動画ファイル入力                        │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 1. 音声抽出 (FFmpeg)                                     │
│    ├─ 音声トラック分離                                   │
│    ├─ WAV形式に変換（16kHz, mono）                       │
│    └─ 一時ファイルとして保存                             │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 2. 音声前処理                                            │
│    ├─ 音量正規化                                         │
│    ├─ ノイズゲート（オプション）                          │
│    └─ 無音区間のトリミング（先頭・末尾）                  │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 3. 言語検出（指定なしの場合）                             │
│    ├─ 音声の最初30秒をサンプリング                       │
│    └─ WhisperX で言語推定                                │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 4. WhisperX 文字起こし                                   │
│    ├─ VAD (Voice Activity Detection)                    │
│    ├─ バッチ処理による高速化                             │
│    └─ セグメント生成                                     │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 5. Forced Alignment                                     │
│    ├─ wav2vec2 によるアライメント                        │
│    └─ Word-level タイムスタンプ生成                      │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 6. 話者分離（オプション）                                 │
│    ├─ pyannote.audio による話者検出                      │
│    └─ 各セグメントに話者IDを付与                         │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 7. 後処理                                                │
│    ├─ セグメントのマージ/分割調整                        │
│    ├─ 信頼度スコアの計算                                 │
│    └─ 結果オブジェクト生成                               │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              TranscriptionResult 返却                    │
└─────────────────────────────────────────────────────────┘
```

---

## 4. WhisperX モデル選択

### モデル一覧
| モデル | パラメータ数 | VRAM使用量 | 用途 |
|--------|------------|-----------|------|
| tiny | 39M | ~1GB | テスト用 |
| base | 74M | ~1GB | 軽量処理 |
| small | 244M | ~2GB | バランス型 |
| medium | 769M | ~5GB | 高精度 |
| large-v3 | 1.5B | ~10GB | 最高精度 |
| distil-large-v3 | 756M | ~6GB | 高速+高精度（推奨） |

### デバイス自動選択
```python
def select_device() -> tuple[str, str]:
    """
    Returns: (device, compute_type)
    """
    if torch.cuda.is_available():
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        if vram >= 10:
            return "cuda", "float16"
        elif vram >= 6:
            return "cuda", "int8"
        else:
            return "cuda", "int8"  # 小さいモデルを使用
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps", "float16"  # Apple Silicon
    else:
        return "cpu", "int8"
```

---

## 5. 音声抽出仕様

### FFmpeg コマンド
```bash
ffmpeg -i input.mp4 \
  -vn \                      # 映像なし
  -acodec pcm_s16le \        # 16-bit PCM
  -ar 16000 \                # 16kHz
  -ac 1 \                    # モノラル
  output.wav
```

### 音声フォーマット要件
| 項目 | 値 | 理由 |
|------|-----|------|
| サンプリングレート | 16000 Hz | Whisperの入力要件 |
| チャンネル数 | 1 (mono) | 処理効率化 |
| ビット深度 | 16-bit | 十分な品質 |
| フォーマット | WAV | 無損失 |

---

## 6. 設定オプション

```python
@dataclass
class AudioProcessorConfig:
    # WhisperX設定
    model_name: str = "distil-large-v3"  # モデル選択
    device: str = "auto"                  # cuda, mps, cpu, auto
    compute_type: str = "auto"            # float16, int8, auto
    batch_size: int = 16                  # バッチサイズ

    # 言語設定
    language: Optional[str] = None        # None=自動検出

    # VAD設定
    vad_onset: float = 0.500              # 発話開始閾値
    vad_offset: float = 0.363             # 発話終了閾値
    chunk_size: int = 30                  # チャンクサイズ（秒）

    # 話者分離設定
    enable_diarization: bool = False      # 話者分離を有効化
    min_speakers: int = 1                 # 最小話者数
    max_speakers: int = 10                # 最大話者数
    hf_token: Optional[str] = None        # HuggingFace token (pyannote用)

    # 前処理設定
    normalize_audio: bool = True          # 音量正規化
    noise_gate: bool = False              # ノイズゲート
```

---

## 7. 言語対応

### 自動検出対応言語（主要）
| 言語コード | 言語名 |
|-----------|-------|
| ja | 日本語 |
| en | 英語 |
| zh | 中国語 |
| ko | 韓国語 |
| es | スペイン語 |
| fr | フランス語 |
| de | ドイツ語 |

### 言語検出ロジック
```python
async def detect_language(audio_path: Path) -> str:
    """
    音声の最初30秒から言語を検出
    """
    # 最初30秒をロード
    audio = whisperx.load_audio(audio_path)
    audio_sample = audio[:30 * 16000]  # 30秒分

    # 言語検出
    model = whisperx.load_model("small", device)
    result = model.detect_language(audio_sample)

    return result["language"]
```

---

## 8. エラーハンドリング

### エラー種別
| エラー | 原因 | 対処 |
|--------|------|------|
| `AudioExtractionError` | FFmpegエラー | FFmpegインストール確認 |
| `ModelLoadError` | モデルロード失敗 | VRAM確認、小モデルにフォールバック |
| `TranscriptionError` | 文字起こし失敗 | 音声品質確認 |
| `OutOfMemoryError` | VRAM/RAM不足 | バッチサイズ縮小、CPUにフォールバック |
| `LanguageDetectionError` | 言語検出失敗 | 手動で言語指定を促す |

### フォールバック戦略
```python
MODEL_FALLBACK_ORDER = [
    "distil-large-v3",
    "medium",
    "small",
    "base",
    "tiny"
]

async def transcribe_with_fallback(audio_path: Path) -> TranscriptionResult:
    for model_name in MODEL_FALLBACK_ORDER:
        try:
            return await transcribe(audio_path, model_name)
        except OutOfMemoryError:
            logger.warning(f"OOM with {model_name}, trying smaller model")
            continue
    raise TranscriptionError("All models failed")
```

---

## 9. 依存関係

### Python パッケージ
```
whisperx>=3.1.0
torch>=2.0.0
torchaudio>=2.0.0
ffmpeg-python>=0.2.0
librosa>=0.10.0  # 波形処理
pyannote.audio>=3.0.0  # 話者分離（オプション）
```

### 外部ツール
| ツール | バージョン | 用途 |
|--------|-----------|------|
| FFmpeg | 5.0+ | 音声抽出 |
| CUDA | 12.x | GPU処理（オプション） |

---

## 10. ファイル構成

```
src/core/audio_processor/
├── __init__.py
├── processor.py        # メインクラス: AudioProcessor
├── extractor.py        # 音声抽出: AudioExtractor
├── transcriber.py      # 文字起こし: Transcriber
├── diarizer.py         # 話者分離: Diarizer
├── models.py           # データモデル
├── config.py           # 設定クラス
└── exceptions.py       # カスタム例外
```

---

## 11. インターフェース定義

### AudioProcessor クラス
```python
class AudioProcessor:
    def __init__(self, config: AudioProcessorConfig = None):
        """初期化（モデルはlazyロード）"""

    async def process(
        self,
        video_path: Path,
        progress_callback: Callable[[float, str], None] = None
    ) -> TranscriptionResult:
        """
        動画から音声を抽出し、文字起こしを実行

        Args:
            video_path: 動画ファイルパス
            progress_callback: 進捗通知コールバック

        Returns:
            TranscriptionResult
        """

    async def extract_audio(self, video_path: Path) -> Path:
        """音声のみ抽出"""

    async def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """音声ファイルから文字起こし"""

    def get_waveform(
        self,
        audio_path: Path,
        start: float = 0,
        end: float = None
    ) -> np.ndarray:
        """波形データを取得（GUI表示用）"""

    def unload_model(self) -> None:
        """モデルをメモリから解放"""
```

---

## 12. 使用例

```python
from core.audio_processor import AudioProcessor, AudioProcessorConfig

# 設定
config = AudioProcessorConfig(
    model_name="distil-large-v3",
    device="auto",
    enable_diarization=False
)

processor = AudioProcessor(config)

# 進捗コールバック
def on_progress(progress: float, status: str):
    print(f"[{progress:.1f}%] {status}")

# 処理実行
result = await processor.process(
    video_path=Path("./video.mp4"),
    progress_callback=on_progress
)

# 結果確認
print(f"Language: {result.language}")
print(f"Segments: {len(result.segments)}")

for seg in result.segments:
    print(f"[{seg.start:.2f} - {seg.end:.2f}] {seg.text}")
    for word in seg.words:
        print(f"  {word.word}: {word.start:.2f} - {word.end:.2f}")
```

---

## 13. パフォーマンス目安

### 処理時間（10分の動画）
| 環境 | モデル | 処理時間 |
|------|--------|----------|
| RTX 4090 | distil-large-v3 | ~30秒 |
| RTX 3080 | distil-large-v3 | ~1分 |
| M2 Pro | distil-large-v3 | ~2分 |
| CPU (8コア) | small | ~5分 |

### メモリ使用量
| モデル | VRAM | RAM (CPU時) |
|--------|------|-------------|
| distil-large-v3 | 6GB | 8GB |
| medium | 5GB | 6GB |
| small | 2GB | 4GB |

---

## 14. テスト項目

### ユニットテスト
- [ ] 音声抽出（各フォーマット）
- [ ] 言語検出
- [ ] タイムスタンプ精度
- [ ] 話者分離

### 統合テスト
- [ ] 日本語動画の文字起こし
- [ ] 英語動画の文字起こし
- [ ] 多言語混在動画
- [ ] ノイズが多い動画
- [ ] 長時間動画（1時間以上）
- [ ] GPU/CPU切り替え
