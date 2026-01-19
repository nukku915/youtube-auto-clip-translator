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

---

## 15. 追加仕様

### 15.1 多言語混在の処理

1動画内で複数言語が話される場合の対処：

```python
@dataclass
class MultiLanguageConfig:
    # 主要言語を自動検出
    detect_primary: bool = True

    # 言語切り替えポイントを検出
    detect_language_switches: bool = False  # MVP: オフ

    # 言語ごとの閾値
    min_segment_duration: float = 3.0  # 言語判定に必要な最小セグメント長

async def process_multilingual(
    audio_path: Path,
    config: MultiLanguageConfig
) -> TranscriptionResult:
    """
    多言語混在動画の処理

    1. 音声の最初30秒で主要言語を検出
    2. 主要言語で全体を文字起こし
    3. 他言語部分は「ベストエフォート」で認識

    注意: 頻繁に言語が切り替わる場合、精度低下の可能性あり
    """
    # 主要言語を検出
    primary_language = await detect_language(audio_path)

    # 主要言語で文字起こし
    result = await transcribe(audio_path, language=primary_language)

    # 低信頼度セグメントに警告フラグを付与
    for segment in result.segments:
        if segment.confidence < 0.5:
            segment.flags.append("low_confidence_may_be_different_language")

    return result
```

**ユーザー向けガイダンス**:
```
多言語が混在する動画の場合：
- 主要な言語が自動検出されます
- 他の言語部分は認識精度が低下する可能性があります
- 字幕編集画面で手動修正を推奨します
```

### 15.2 ノイズ対策詳細

#### ノイズ種別と対策

| ノイズ種別 | 影響 | 対策 |
|-----------|------|------|
| BGM | 中〜高 | 音声分離フィルター（オプション） |
| 環境音（街、風） | 低〜中 | ノイズゲート適用 |
| 反響（エコー） | 中 | エコーキャンセル（限定的） |
| 複数人同時発話 | 高 | 話者分離（diarization）推奨 |

#### 音声前処理オプション

```python
@dataclass
class AudioPreprocessConfig:
    # 音量正規化
    normalize: bool = True
    target_dbfs: float = -20.0

    # ノイズゲート（小さい音をカット）
    noise_gate: bool = False
    noise_gate_threshold: float = -50.0  # dB

    # ハイパスフィルター（低周波ノイズ除去）
    highpass_filter: bool = True
    highpass_freq: int = 80  # Hz

    # BGM分離（実験的機能）
    separate_vocals: bool = False  # demucs使用、処理時間増大

def preprocess_audio(
    audio_path: Path,
    config: AudioPreprocessConfig
) -> Path:
    """音声の前処理を適用"""
    # FFmpegフィルターを構築
    filters = []

    if config.highpass_filter:
        filters.append(f"highpass=f={config.highpass_freq}")

    if config.normalize:
        filters.append(f"loudnorm=I=-16:TP=-1.5:LRA=11")

    if config.noise_gate:
        filters.append(f"agate=threshold={config.noise_gate_threshold}dB")

    # FFmpeg実行
    ...
```

### 15.3 HuggingFace トークン取得手順

話者分離（pyannote.audio）を使用するにはHuggingFaceトークンが必要：

#### 取得手順

1. **HuggingFaceアカウント作成**
   - https://huggingface.co/join にアクセス
   - アカウントを作成

2. **モデル利用規約に同意**
   - https://huggingface.co/pyannote/speaker-diarization-3.1 にアクセス
   - 「Agree and access repository」をクリック

3. **アクセストークン取得**
   - https://huggingface.co/settings/tokens にアクセス
   - 「New token」をクリック
   - 名前を入力、タイプは「Read」を選択
   - トークンをコピー

4. **設定**
   ```yaml
   # config.yaml
   whisper:
     hf_token: "hf_xxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```
   または環境変数:
   ```bash
   export HF_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```

### 15.4 モデルキャッシュ場所

WhisperXおよび関連モデルの保存場所：

```python
MODEL_CACHE_PATHS = {
    # WhisperXモデル（faster-whisper形式）
    "whisper": Path.home() / ".cache" / "huggingface" / "hub",

    # wav2vec2アライメントモデル
    "alignment": Path.home() / ".cache" / "huggingface" / "hub",

    # pyannote話者分離モデル
    "diarization": Path.home() / ".cache" / "huggingface" / "hub",

    # アプリ固有キャッシュ
    "app_cache": Path.home() / ".youtube-auto-clip-translator" / "cache" / "models",
}

def get_model_cache_size() -> int:
    """キャッシュサイズを取得（bytes）"""
    total = 0
    for name, path in MODEL_CACHE_PATHS.items():
        if path.exists():
            total += sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total

def clear_model_cache(keep_recent: bool = True) -> int:
    """キャッシュをクリア（解放容量を返す）"""
    ...
```

**モデルサイズ目安**:
| モデル | サイズ |
|--------|--------|
| distil-large-v3 | ~1.5GB |
| large-v3 | ~3GB |
| wav2vec2 (ja) | ~1GB |
| pyannote | ~500MB |

### 15.5 ストリーミング処理（長時間動画）

長時間動画のメモリ効率的な処理：

```python
@dataclass
class StreamingConfig:
    # チャンクサイズ（秒）
    chunk_duration: int = 300  # 5分

    # チャンク間のオーバーラップ（秒）
    overlap: int = 5

    # メモリ制限（GB）
    max_memory_gb: float = 8.0

async def transcribe_streaming(
    audio_path: Path,
    config: StreamingConfig,
    progress_callback: Callable[[float, str], None] = None
) -> TranscriptionResult:
    """
    ストリーミング方式で文字起こし

    - 音声を小さなチャンクに分割
    - 各チャンクを順次処理
    - 結果を結合してタイムスタンプを補正
    """
    audio_duration = get_audio_duration(audio_path)
    all_segments = []

    for start in range(0, int(audio_duration), config.chunk_duration - config.overlap):
        end = min(start + config.chunk_duration, audio_duration)

        # チャンクを抽出
        chunk_path = extract_audio_chunk(audio_path, start, end)

        # 文字起こし
        result = await transcribe(chunk_path)

        # タイムスタンプを補正してマージ
        for segment in result.segments:
            segment.start += start
            segment.end += start
            all_segments.append(segment)

        # 進捗更新
        if progress_callback:
            progress = (end / audio_duration) * 100
            progress_callback(progress, f"文字起こし中... {int(end)}秒 / {int(audio_duration)}秒")

        # チャンクファイル削除
        chunk_path.unlink()

    # オーバーラップ部分の重複を解消
    all_segments = merge_overlapping_segments(all_segments)

    return TranscriptionResult(segments=all_segments, ...)
```

### 15.6 GPU VRAM不足時の動作

```python
class VRAMManager:
    """VRAMの監視と自動調整"""

    def __init__(self):
        self.min_free_vram = 1.0  # 最低1GB空けておく

    def get_available_vram(self) -> float:
        """利用可能なVRAM（GB）"""
        if not torch.cuda.is_available():
            return 0.0
        return (torch.cuda.get_device_properties(0).total_memory -
                torch.cuda.memory_allocated(0)) / 1e9

    def select_optimal_config(self) -> tuple[str, str, int]:
        """
        VRAMに基づいて最適な設定を選択

        Returns:
            (model_name, compute_type, batch_size)
        """
        available = self.get_available_vram()

        if available >= 10:
            return ("large-v3", "float16", 16)
        elif available >= 6:
            return ("distil-large-v3", "float16", 16)
        elif available >= 4:
            return ("distil-large-v3", "int8", 8)
        elif available >= 2:
            return ("medium", "int8", 4)
        else:
            # CPU fallback
            return ("small", "int8", 1)

    async def transcribe_with_vram_management(
        self,
        audio_path: Path
    ) -> TranscriptionResult:
        """VRAM不足時に自動調整して文字起こし"""
        max_retries = 3

        for attempt in range(max_retries):
            model, compute_type, batch_size = self.select_optimal_config()

            try:
                return await transcribe(
                    audio_path,
                    model=model,
                    compute_type=compute_type,
                    batch_size=batch_size
                )
            except torch.cuda.OutOfMemoryError:
                # VRAM解放
                torch.cuda.empty_cache()
                gc.collect()

                # 次の試行では小さい設定を使用
                self.min_free_vram += 1.0

                if attempt == max_retries - 1:
                    # 最終手段: CPUで実行
                    return await transcribe(
                        audio_path,
                        model="small",
                        device="cpu",
                        compute_type="int8"
                    )
```

**ユーザー通知**:
```
⚠️ GPUメモリが不足しています
- モデルを small に変更しました
- 処理時間が長くなります
- 設定画面でモデルサイズを調整できます
```

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-01-19 | 初版作成 |
| 2026-01-19 | 追加仕様（多言語、ノイズ対策、VRAM管理等）を追記 |
