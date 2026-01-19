# AI分析モジュール詳細計画書

## 1. 概要

### 目的
ハイブリッドLLM構成（ローカル + クラウド）を使用して、文字起こしテキストの分析・翻訳を行う

### LLMプロバイダ
| プロバイダ | 用途 | モデル |
|-----------|------|--------|
| Ollama（ローカル） | 見どころ検出、チャプター検出 | gemma-2-jpn:2b |
| Gemini（クラウド） | 翻訳、タイトル生成 | gemini-3-flash |

### 責務
- テキストの翻訳（日本語⇔英語、自動検出）
- 見どころ検出・スコアリング
- チャプター区切り検出
- セクションタイトル生成
- LLMプロバイダの自動切り替え
- APIコスト最適化

---

## 2. サブモジュール構成

```
AI Analyzer
├── Translator          # 翻訳
├── HighlightDetector   # 見どころ検出
├── ChapterDetector     # チャプター検出
└── TitleGenerator      # タイトル生成
```

---

## 3. 共通仕様

### ハイブリッドLLM設定

```python
@dataclass
class LLMConfig:
    """ハイブリッドLLM設定"""
    # プロバイダ設定
    provider: str = "hybrid"  # "local", "gemini", "hybrid"

    # ローカルLLM（Ollama）設定
    local_enabled: bool = True
    local_model: str = "gemma-2-jpn:2b"
    ollama_host: str = "http://localhost:11434"
    ollama_timeout: int = 120  # ローカルは時間がかかる可能性

    # クラウドLLM（Gemini）設定
    gemini_enabled: bool = True
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash"
    gemini_timeout: int = 60

    # 共通設定
    temperature: float = 0.3
    max_output_tokens: int = 8192

    # タスク振り分け
    use_local_for: List[str] = field(default_factory=lambda: [
        "highlight_detection",
        "chapter_detection",
    ])
    use_gemini_for: List[str] = field(default_factory=lambda: [
        "translation",
        "title_generation",
    ])

    # フォールバック
    fallback_to_gemini: bool = True

    # レート制限対策（Gemini用）
    requests_per_minute: int = 60
    retry_count: int = 3
    retry_delay: float = 1.0
```

### Ollama設定

```python
@dataclass
class OllamaConfig:
    host: str = "http://localhost:11434"
    model: str = "gemma-2-jpn:2b"
    timeout: int = 120
    temperature: float = 0.3
    num_ctx: int = 8192  # コンテキストウィンドウサイズ
```

### Gemini設定

```python
@dataclass
class GeminiConfig:
    api_key: str                          # APIキー
    model: str = "gemini-3-flash"         # モデル名
    temperature: float = 0.3              # 生成温度
    max_output_tokens: int = 8192         # 最大出力トークン
    timeout: int = 60                     # タイムアウト（秒）

    # レート制限対策
    requests_per_minute: int = 60
    retry_count: int = 3
    retry_delay: float = 1.0
```

### 設定ファイル

```yaml
# ~/.youtube-auto-clip-translator/config.yaml
llm:
  provider: "hybrid"  # hybrid, local, gemini
  fallback_to_gemini: true

  ollama:
    host: "http://localhost:11434"
    model: "gemma-2-jpn:2b"
    timeout: 120

  gemini:
    api_key: "YOUR_API_KEY_HERE"
    model: "gemini-3-flash"
    timeout: 60

  task_routing:
    highlight_detection: "local"
    chapter_detection: "local"
    translation: "gemini"
    title_generation: "gemini"
```

**読み込み優先順位（Gemini API Key）**:
1. 環境変数 `GEMINI_API_KEY`（設定されている場合）
2. 設定ファイル `~/.youtube-auto-clip-translator/config.yaml`

### LLMルーター

```python
class LLMRouter:
    """タスクに応じてLLMプロバイダを選択"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.ollama_client = OllamaClient(config) if config.local_enabled else None
        self.gemini_client = GeminiClient(config) if config.gemini_enabled else None

    async def execute(
        self,
        task: str,
        prompt: str,
        **kwargs
    ) -> LLMResponse:
        """
        タスクに応じて適切なLLMで実行

        Args:
            task: タスク種別 (highlight_detection, translation, etc.)
            prompt: プロンプト

        Returns:
            LLMResponse: 応答
        """
        provider = self._get_provider_for_task(task)

        try:
            if provider == "local":
                return await self.ollama_client.generate(prompt, **kwargs)
            else:
                return await self.gemini_client.generate(prompt, **kwargs)
        except Exception as e:
            if self.config.fallback_to_gemini and provider == "local":
                # ローカル失敗時はGeminiにフォールバック
                return await self.gemini_client.generate(prompt, **kwargs)
            raise

    def _get_provider_for_task(self, task: str) -> str:
        if task in self.config.use_local_for and self.config.local_enabled:
            return "local"
        return "gemini"
```

### 接続テスト

保存時にAPIキーの有効性とOllamaの接続を確認

### 共通入力データ
```python
@dataclass
class AnalysisInput:
    segments: List[TranscriptionSegment]  # 文字起こし結果
    source_language: str                   # 元言語
    video_metadata: VideoMetadata          # 動画メタデータ
```

---

## 4. 翻訳モジュール (Translator)

### 4.1 入出力仕様

#### 入力
| 項目 | 型 | 必須 | 説明 |
|------|-----|------|------|
| segments | List[TranscriptionSegment] | Yes | 翻訳対象セグメント |
| source_lang | str | No | 元言語（自動検出可） |
| target_lang | str | Yes | 翻訳先言語 |

#### 出力
```python
@dataclass
class TranslationResult:
    translated_segments: List[TranslatedSegment]
    source_language: str
    target_language: str
    total_tokens_used: int

@dataclass
class TranslatedSegment:
    id: int                    # 元セグメントID
    original_text: str         # 原文
    translated_text: str       # 訳文
    start: float               # 開始時間
    end: float                 # 終了時間
    words: List[TranslatedWord]  # 単語レベル翻訳（オプション）
```

### 4.2 翻訳プロンプト設計

```python
TRANSLATION_SYSTEM_PROMPT = """
あなたは動画字幕の翻訳専門家です。以下のルールに従って翻訳してください：

## ルール
1. 自然で読みやすい訳文にする
2. 字幕として表示されるため、1セグメント40文字以内を目安にする
3. 話し言葉のニュアンスを維持する
4. 専門用語は文脈に応じて適切に訳す
5. 固有名詞（人名、地名、ブランド名）は原則そのまま
6. 相槌や感嘆詞も自然に訳す

## 出力形式
JSON形式で出力してください：
{
  "translations": [
    {"id": 1, "text": "訳文"},
    {"id": 2, "text": "訳文"}
  ]
}
"""

TRANSLATION_USER_PROMPT = """
以下のセグメントを{source_lang}から{target_lang}に翻訳してください。

セグメント一覧：
{segments_json}
"""
```

### 4.3 バッチ処理

コスト最適化のため、複数セグメントをまとめて翻訳：

```python
BATCH_CONFIG = {
    "max_segments_per_request": 50,   # 1リクエストあたりの最大セグメント数
    "max_tokens_per_request": 4000,   # 1リクエストあたりの最大トークン数
}
```

### 4.4 処理フロー

```
┌─────────────────────────────────────────────────────────┐
│ 1. セグメントのバッチ分割                                │
│    └─ トークン数を考慮して適切なサイズに分割             │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 2. 各バッチを並列でAPI呼び出し                           │
│    └─ レート制限を考慮した並列度制御                     │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 3. レスポンスのパース・検証                              │
│    └─ JSON形式の検証、欠損チェック                       │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 4. 元セグメントとのマッピング                            │
│    └─ タイムスタンプの引き継ぎ                           │
└─────────────────────────────────────────────────────────┘
```

---

## 5. 見どころ検出モジュール (HighlightDetector)

### 5.1 入出力仕様

#### 入力
| 項目 | 型 | 必須 | 説明 |
|------|-----|------|------|
| segments | List[TranscriptionSegment] | Yes | 分析対象 |
| video_type | str | No | 動画タイプ（gaming, talk, tutorial等） |

#### 出力
```python
@dataclass
class HighlightResult:
    highlights: List[Highlight]
    summary: str  # 動画全体の要約

@dataclass
class Highlight:
    start: float           # 開始時間
    end: float             # 終了時間
    score: float           # 見どころスコア（0-100）
    reason: str            # 選出理由
    category: str          # カテゴリ（funny, informative, dramatic等）
    suggested_title: str   # 切り抜きタイトル候補
```

### 5.2 見どころ検出プロンプト

```python
HIGHLIGHT_SYSTEM_PROMPT = """
あなたは動画コンテンツの分析専門家です。
文字起こしテキストから「見どころ」となる部分を検出してください。

## 見どころの判断基準
1. **面白い場面**: 笑いを誘う発言、ユーモア
2. **重要な情報**: 核心的な解説、結論
3. **感情的なピーク**: 驚き、感動、興奮
4. **印象的なフレーズ**: 名言、キャッチーな発言
5. **ストーリーのクライマックス**: 盛り上がり、転換点

## 出力形式
JSON形式で出力してください：
{
  "highlights": [
    {
      "start_segment_id": 10,
      "end_segment_id": 15,
      "score": 85,
      "reason": "選出理由",
      "category": "funny",
      "suggested_title": "【爆笑】..."
    }
  ],
  "summary": "動画全体の要約（100字程度）"
}
"""
```

### 5.3 スコアリング基準

| スコア | 判定 | 説明 |
|--------|------|------|
| 90-100 | 必見 | 動画のハイライト、必ず含めるべき |
| 70-89 | 重要 | 高い価値があり、含めることを推奨 |
| 50-69 | 普通 | 含めても良いが必須ではない |
| 0-49 | 低 | 切り抜きには不向き |

---

## 6. チャプター検出モジュール (ChapterDetector)

### 6.1 入出力仕様

#### 出力
```python
@dataclass
class ChapterResult:
    chapters: List[Chapter]

@dataclass
class Chapter:
    id: int                # チャプターID
    start: float           # 開始時間
    end: float             # 終了時間
    title: str             # チャプタータイトル
    summary: str           # チャプター要約
    segment_ids: List[int] # 含まれるセグメントID
```

### 6.2 チャプター検出プロンプト

```python
CHAPTER_SYSTEM_PROMPT = """
あなたは動画構成の分析専門家です。
文字起こしテキストからトピックの変化を検出し、チャプター分けしてください。

## チャプター分けの基準
1. **話題の転換**: 新しいトピックへの移行
2. **場面の変化**: 状況説明の変化
3. **構成の区切り**: 導入→本題→まとめ など
4. **時間の経過**: 「次は」「続いて」などの接続

## 出力形式
JSON形式で出力してください：
{
  "chapters": [
    {
      "start_segment_id": 1,
      "end_segment_id": 20,
      "title": "オープニング",
      "summary": "チャプターの概要（50字程度）"
    }
  ]
}
"""
```

---

## 7. タイトル生成モジュール (TitleGenerator)

### 7.1 入出力仕様

#### 出力
```python
@dataclass
class TitleResult:
    main_title: str                  # メインタイトル
    alternative_titles: List[str]    # 代替タイトル候補
    tags: List[str]                  # 推奨タグ
    description: str                 # 説明文

@dataclass
class SectionTitle:
    chapter_id: int
    title: str                       # 表示用タイトル
    style: str                       # スタイル（bold, highlight等）
```

### 7.2 タイトル生成プロンプト

```python
TITLE_SYSTEM_PROMPT = """
あなたはYouTube動画のタイトル作成専門家です。
視聴者の興味を引く、クリック率の高いタイトルを生成してください。

## タイトルの要件
1. 30文字以内
2. 内容を的確に表現
3. 興味を引くフック
4. 不要な装飾は避ける

## Shorts用タイトル
- 15文字以内
- インパクト重視

## 出力形式
{
  "main_title": "メインタイトル",
  "alternative_titles": ["候補1", "候補2", "候補3"],
  "shorts_title": "Shorts用タイトル",
  "tags": ["タグ1", "タグ2"],
  "description": "動画の説明文（200字程度）"
}
"""
```

---

## 8. コスト最適化戦略

### 8.1 処理順序の最適化

```
┌─────────────────────────────────────────────────────────┐
│ Phase 1: 分析（低コスト）                                │
│ ├─ 見どころ検出                                         │
│ ├─ チャプター検出                                       │
│ └─ タイトル生成                                         │
│                                                         │
│ ※ テキストのみの処理なのでトークン消費が少ない           │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 2: 人間によるレビュー                              │
│ └─ 切り抜き範囲の確定                                   │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 3: 翻訳（確定部分のみ）                            │
│ └─ コスト最小化                                         │
└─────────────────────────────────────────────────────────┘
```

### 8.2 トークン使用量の見積もり

| 処理 | 入力トークン | 出力トークン | 備考 |
|------|-------------|-------------|------|
| 見どころ検出 | ~2000 | ~500 | 動画全体を1回分析 |
| チャプター検出 | ~2000 | ~300 | 動画全体を1回分析 |
| タイトル生成 | ~500 | ~200 | チャプターごと |
| 翻訳 | ~100/セグメント | ~100/セグメント | 確定部分のみ |

### 8.3 キャッシュ戦略

```python
@dataclass
class AnalysisCache:
    video_id: str
    transcript_hash: str     # 文字起こし結果のハッシュ
    highlights: Optional[HighlightResult]
    chapters: Optional[ChapterResult]
    translations: Dict[str, TranslationResult]  # lang -> result
    created_at: datetime
    expires_at: datetime
```

---

## 9. Ollamaクライアント

### OllamaClient クラス

```python
class OllamaClient:
    """Ollamaローカルモデル用クライアント"""

    def __init__(self, config: OllamaConfig):
        self.config = config
        self.base_url = config.host

    async def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        **kwargs
    ) -> LLMResponse:
        """
        テキスト生成

        Args:
            prompt: ユーザープロンプト
            system_prompt: システムプロンプト

        Returns:
            LLMResponse: 応答
        """
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_ctx": self.config.num_ctx,
            }
        }

        if system_prompt:
            payload["system"] = system_prompt

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                result = await response.json()
                return LLMResponse(
                    text=result["response"],
                    provider="ollama",
                    model=self.config.model,
                )

    async def is_available(self) -> bool:
        """Ollamaが利用可能か確認"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """インストール済みモデル一覧を取得"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/api/tags") as response:
                data = await response.json()
                return [m["name"] for m in data.get("models", [])]

    async def pull_model(
        self,
        model: str,
        progress_callback: Callable[[float, str], None] = None
    ) -> bool:
        """モデルをダウンロード"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/pull",
                json={"name": model, "stream": True}
            ) as response:
                async for line in response.content:
                    data = json.loads(line)
                    if "completed" in data and "total" in data:
                        progress = data["completed"] / data["total"] * 100
                        if progress_callback:
                            progress_callback(progress, f"Downloading {model}...")
                    if data.get("status") == "success":
                        return True
        return False
```

### LLMResponse データクラス

```python
@dataclass
class LLMResponse:
    text: str                    # 応答テキスト
    provider: str                # プロバイダ名 (ollama/gemini)
    model: str                   # 使用モデル名
    tokens_used: int = 0         # 使用トークン数（Geminiのみ）
    latency_ms: float = 0.0      # レイテンシ
```

---

## 10. エラーハンドリング

### エラー種別
| エラー | 原因 | 対処 |
|--------|------|------|
| `APIKeyError` | 無効なAPIキー（Gemini） | キーの再設定を促す |
| `RateLimitError` | レート制限（Gemini） | 指数バックオフでリトライ |
| `QuotaExceededError` | 使用量上限（Gemini） | ユーザーに通知 |
| `InvalidResponseError` | 不正なレスポンス | リトライ、フォールバック |
| `TimeoutError` | タイムアウト | リトライ |
| `OllamaNotRunningError` | Ollamaサービス未起動 | 自動起動試行 or フォールバック |
| `ModelNotFoundError` | モデル未ダウンロード | モデルDL促す or フォールバック |
| `OllamaConnectionError` | Ollama接続エラー | Geminiへフォールバック |

### リトライ戦略
```python
RETRY_CONFIG = {
    "max_retries": 3,
    "base_delay": 1.0,
    "max_delay": 60.0,
    "exponential_base": 2,
    "jitter": True,
}
```

---

## 10. ファイル構成

```
src/core/ai_analyzer/
├── __init__.py
├── analyzer.py           # メインクラス: AIAnalyzer
├── translator.py         # 翻訳: Translator
├── highlight_detector.py # 見どころ検出: HighlightDetector
├── chapter_detector.py   # チャプター検出: ChapterDetector
├── title_generator.py    # タイトル生成: TitleGenerator
├── llm/
│   ├── __init__.py
│   ├── router.py         # LLMルーター（タスク振り分け）
│   ├── base.py           # LLMクライアント基底クラス
│   ├── ollama_client.py  # Ollamaクライアント
│   └── gemini_client.py  # Geminiクライアント
├── prompts/
│   ├── translation.py
│   ├── highlight.py
│   ├── chapter.py
│   └── title.py
├── models.py             # データモデル
├── config.py             # 設定（LLMConfig含む）
├── cache.py              # キャッシュ管理
└── exceptions.py         # カスタム例外
```

---

## 11. インターフェース定義

### AIAnalyzer クラス
```python
class AIAnalyzer:
    def __init__(self, config: LLMConfig):
        """
        初期化

        Args:
            config: ハイブリッドLLM設定
        """
        self.config = config
        self.router = LLMRouter(config)

    async def analyze_full(
        self,
        input: AnalysisInput,
        progress_callback: Callable[[float, str], None] = None
    ) -> FullAnalysisResult:
        """
        全分析を実行（見どころ + チャプター + タイトル）

        Returns:
            FullAnalysisResult: 全分析結果
        """

    async def detect_highlights(
        self,
        segments: List[TranscriptionSegment]
    ) -> HighlightResult:
        """見どころ検出のみ"""

    async def detect_chapters(
        self,
        segments: List[TranscriptionSegment]
    ) -> ChapterResult:
        """チャプター検出のみ"""

    async def translate(
        self,
        segments: List[TranscriptionSegment],
        target_lang: str
    ) -> TranslationResult:
        """翻訳のみ"""

    async def generate_titles(
        self,
        chapters: List[Chapter],
        context: str
    ) -> TitleResult:
        """タイトル生成のみ"""

    def estimate_cost(
        self,
        segments: List[TranscriptionSegment]
    ) -> CostEstimate:
        """処理コストの見積もり"""
```

---

## 12. 使用例

```python
from core.ai_analyzer import AIAnalyzer, LLMConfig

# ハイブリッドLLM設定
config = LLMConfig(
    provider="hybrid",

    # ローカルLLM設定
    local_enabled=True,
    local_model="gemma-2-jpn:2b",
    ollama_host="http://localhost:11434",

    # クラウドLLM設定
    gemini_enabled=True,
    gemini_api_key="YOUR_API_KEY",
    gemini_model="gemini-3-flash",

    # フォールバック有効
    fallback_to_gemini=True,
)

analyzer = AIAnalyzer(config)

# 全分析実行
result = await analyzer.analyze_full(
    input=AnalysisInput(
        segments=transcription_result.segments,
        source_language="en",
        video_metadata=video_metadata
    ),
    progress_callback=lambda p, s: print(f"[{p:.1f}%] {s}")
)

# 見どころ確認
for highlight in result.highlights.highlights:
    print(f"[{highlight.start:.1f}s - {highlight.end:.1f}s]")
    print(f"  Score: {highlight.score}")
    print(f"  Reason: {highlight.reason}")

# 確定した部分のみ翻訳（コスト最適化）
selected_segment_ids = [1, 2, 3, 10, 11, 12]  # ユーザーが選択
selected_segments = [s for s in segments if s.id in selected_segment_ids]

translation = await analyzer.translate(
    segments=selected_segments,
    target_lang="ja"
)
```

---

## 13. テスト項目

### ユニットテスト
- [ ] 翻訳精度（日→英、英→日）
- [ ] 見どころ検出の妥当性
- [ ] チャプター区切りの適切さ
- [ ] タイトル生成の品質
- [ ] プロンプトのパース

### 統合テスト
- [ ] 長時間動画（1時間以上）の処理
- [ ] 多言語混在コンテンツ
- [ ] エラーリカバリ
- [ ] レート制限対応
- [ ] キャッシュ動作
