# AI分析モジュール詳細計画書

## 1. 概要

### 目的
Gemini 3 Flash APIを使用して、文字起こしテキストの分析・翻訳を行う

### 責務
- テキストの翻訳（日本語⇔英語、自動検出）
- 見どころ検出・スコアリング
- チャプター区切り検出
- セクションタイトル生成
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

### API設定
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

## 9. エラーハンドリング

### エラー種別
| エラー | 原因 | 対処 |
|--------|------|------|
| `APIKeyError` | 無効なAPIキー | キーの再設定を促す |
| `RateLimitError` | レート制限 | 指数バックオフでリトライ |
| `QuotaExceededError` | 使用量上限 | ユーザーに通知 |
| `InvalidResponseError` | 不正なレスポンス | リトライ、フォールバック |
| `TimeoutError` | タイムアウト | リトライ |

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
├── gemini_client.py      # API クライアント
├── prompts/
│   ├── translation.py
│   ├── highlight.py
│   ├── chapter.py
│   └── title.py
├── models.py             # データモデル
├── config.py             # 設定
├── cache.py              # キャッシュ管理
└── exceptions.py         # カスタム例外
```

---

## 11. インターフェース定義

### AIAnalyzer クラス
```python
class AIAnalyzer:
    def __init__(self, config: GeminiConfig):
        """初期化"""

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
from core.ai_analyzer import AIAnalyzer, GeminiConfig

# 設定
config = GeminiConfig(
    api_key="YOUR_API_KEY",
    model="gemini-3-flash"
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
