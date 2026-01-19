# 出力・エクスポートモジュール詳細計画書

## 1. 概要

### 目的
編集済みの動画と関連ファイルを様々な形式・用途に応じて出力する

### 責務
- 動画ファイルの出力（通常動画/Shorts）
- 字幕ファイルの出力（SRT/ASS/VTT）
- プロジェクトファイルの保存/読み込み
- バッチ出力（複数セグメントの一括出力）
- 出力履歴の管理

---

## 2. 出力パターン

### 2.1 出力形式一覧

| 出力タイプ | 説明 | ファイル形式 |
|-----------|------|-------------|
| 通常動画 | 16:9 横型動画 | MP4, WebM |
| Shorts動画 | 9:16 縦型動画 | MP4 |
| 結合動画 | 全セグメントを結合 | MP4 |
| 個別動画 | セグメントごとに分割 | MP4 |
| 字幕ファイル | 翻訳字幕 | SRT, ASS, VTT |
| 原文字幕 | 原言語の字幕 | SRT, ASS, VTT |
| プロジェクト | 編集状態の保存 | JSON (zip圧縮) |

### 2.2 出力パターン例

```
出力パターン A: 結合動画 + Shorts
├── video_title.mp4            # 結合した通常動画
├── video_title_shorts_01.mp4  # セグメント1 Shorts
├── video_title_shorts_02.mp4  # セグメント2 Shorts
├── video_title.srt            # 通常動画用字幕
└── video_title.ass            # 通常動画用字幕（スタイル付き）

出力パターン B: 個別動画
├── video_title_01_opening.mp4     # セグメント1
├── video_title_02_main.mp4        # セグメント2
├── video_title_01_opening.srt     # セグメント1 字幕
├── video_title_02_main.srt        # セグメント2 字幕
└── ...

出力パターン C: 全形式出力
├── normal/
│   ├── video_title.mp4
│   ├── video_title.srt
│   └── video_title.ass
├── shorts/
│   ├── video_title_shorts_01.mp4
│   ├── video_title_shorts_02.mp4
│   └── ...
└── subtitles/
    ├── video_title_ja.srt
    ├── video_title_en.srt
    └── ...
```

---

## 3. 入出力仕様

### 入力
```python
@dataclass
class ExportRequest:
    project: Project                    # プロジェクトデータ
    segments: List[EditSegment]         # 出力対象セグメント
    output_config: ExportConfig         # 出力設定
    subtitle_config: SubtitleExportConfig  # 字幕出力設定
```

### ExportConfig
```python
@dataclass
class ExportConfig:
    # 出力先
    output_dir: Path

    # 動画出力
    export_normal: bool = True          # 通常動画を出力
    export_shorts: bool = True          # Shorts動画を出力
    combine_segments: bool = True       # セグメントを結合
    export_individual: bool = False     # 個別動画も出力

    # ファイル名
    filename_template: str = "{title}_{format}"
    # 利用可能変数: {title}, {format}, {date}, {index}, {chapter}

    # エンコード設定
    encoding_preset: str = "balanced"
    resolution: Optional[tuple] = None  # None = 元動画と同じ
    hw_accel: bool = True

    # 字幕
    burn_subtitles: bool = True         # 字幕焼き付け
    export_subtitle_files: bool = True  # 字幕ファイルも出力
```

### SubtitleExportConfig
```python
@dataclass
class SubtitleExportConfig:
    formats: List[str] = field(default_factory=lambda: ["srt", "ass"])
    languages: List[str] = field(default_factory=lambda: ["translated"])
    # "translated", "original", "both"
    bilingual: bool = False
```

### 出力
```python
@dataclass
class ExportResult:
    success: bool
    output_files: List[ExportedFile]
    total_duration: float
    total_size: int
    export_time: float
    errors: List[str]

@dataclass
class ExportedFile:
    path: Path
    type: str  # "video_normal", "video_shorts", "subtitle", "project"
    size: int
    duration: Optional[float]
```

---

## 4. 処理フロー

```
┌─────────────────────────────────────────────────────────┐
│                   ExportRequest 入力                     │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 1. 出力計画の作成                                        │
│    ├─ 出力ファイル一覧の生成                             │
│    ├─ ディスク容量チェック                               │
│    └─ 推定時間の計算                                     │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 2. 出力ディレクトリ準備                                  │
│    ├─ ディレクトリ作成                                   │
│    └─ 既存ファイルの確認                                 │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 3. 字幕ファイル生成                                      │
│    ├─ SRT/ASS/VTT生成                                   │
│    └─ 各言語版の生成                                     │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 4. 動画編集・エンコード                                  │
│    ├─ 通常動画の生成                                     │
│    ├─ Shorts動画の生成                                   │
│    └─ 個別動画の生成（オプション）                        │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 5. 後処理                                                │
│    ├─ ファイル検証                                       │
│    ├─ メタデータ書き込み                                 │
│    └─ 出力履歴の記録                                     │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   ExportResult 返却                      │
└─────────────────────────────────────────────────────────┘
```

---

## 5. プロジェクトファイル

### 5.1 プロジェクト構造

```python
@dataclass
class Project:
    # メタデータ
    id: str                            # プロジェクトID（UUID）
    name: str                          # プロジェクト名
    created_at: datetime
    updated_at: datetime
    version: str = "1.0"

    # 元動画情報
    source_url: str
    source_video_path: Path
    video_metadata: VideoMetadata

    # 処理結果
    transcription: TranscriptionResult
    ai_analysis: FullAnalysisResult
    translation: Optional[TranslationResult]

    # 編集状態
    segments: List[EditSegment]
    subtitles: List[SubtitleEntry]

    # 設定
    export_config: ExportConfig
    subtitle_style: SubtitleStyleConfig
```

### 5.2 プロジェクトファイル形式

```
project.yact  (YouTube Auto Clip Translator)
├── project.json          # プロジェクトメタデータ
├── transcription.json    # 文字起こし結果
├── analysis.json         # AI分析結果
├── segments.json         # セグメント情報
├── subtitles.json        # 字幕データ
├── thumbnails/           # サムネイル画像
│   └── thumb_001.jpg
└── cache/                # キャッシュデータ
    └── ...
```

### 5.3 保存/読み込み

```python
class ProjectManager:
    def save(self, project: Project, path: Path) -> None:
        """
        プロジェクトを保存

        - ZIP形式で圧縮
        - 拡張子: .yact
        """

    def load(self, path: Path) -> Project:
        """
        プロジェクトを読み込み
        """

    def export_json(self, project: Project, path: Path) -> None:
        """
        JSONとして出力（デバッグ/互換性用）
        """

    def get_recent_projects(self, limit: int = 10) -> List[ProjectInfo]:
        """
        最近のプロジェクト一覧
        """
```

---

## 6. バッチ出力

### 6.1 バッチ処理設定

```python
@dataclass
class BatchExportConfig:
    # 並列処理
    parallel_exports: int = 2          # 同時出力数
    priority: str = "normal"           # low, normal, high

    # 通知
    notify_on_complete: bool = True
    notify_on_error: bool = True

    # エラー処理
    continue_on_error: bool = True     # エラー時も続行
    retry_failed: bool = True          # 失敗したものを再試行
    max_retries: int = 2
```

### 6.2 バッチ出力フロー

```python
class BatchExporter:
    async def export_batch(
        self,
        requests: List[ExportRequest],
        config: BatchExportConfig,
        progress_callback: Callable[[BatchProgress], None] = None
    ) -> BatchExportResult:
        """
        複数の出力リクエストをバッチ処理
        """

@dataclass
class BatchProgress:
    total: int
    completed: int
    current_file: str
    current_progress: float
    errors: List[str]

@dataclass
class BatchExportResult:
    total_requests: int
    successful: int
    failed: int
    results: List[ExportResult]
    total_time: float
```

---

## 7. 出力履歴

### 7.1 履歴データ

```python
@dataclass
class ExportHistory:
    id: str
    project_id: str
    project_name: str
    exported_at: datetime
    output_files: List[ExportedFile]
    config_snapshot: ExportConfig
    success: bool
    error_message: Optional[str]
```

### 7.2 履歴管理

```python
class HistoryManager:
    def __init__(self, db_path: Path):
        """SQLiteで履歴を管理"""

    def add(self, history: ExportHistory) -> None:
        """履歴を追加"""

    def get_recent(self, limit: int = 50) -> List[ExportHistory]:
        """最近の履歴を取得"""

    def get_by_project(self, project_id: str) -> List[ExportHistory]:
        """プロジェクトの出力履歴を取得"""

    def delete_old(self, days: int = 30) -> int:
        """古い履歴を削除"""

    def cleanup_orphaned_files(self) -> int:
        """孤立したファイルを削除"""
```

---

## 8. ファイル名テンプレート

### 8.1 利用可能変数

| 変数 | 説明 | 例 |
|------|------|-----|
| {title} | 動画タイトル | "Amazing Video" |
| {format} | 出力形式 | "normal", "shorts" |
| {date} | 出力日 | "20260119" |
| {datetime} | 出力日時 | "20260119_153045" |
| {index} | セグメント番号 | "01", "02" |
| {chapter} | チャプター名 | "opening" |
| {lang} | 言語コード | "ja", "en" |
| {resolution} | 解像度 | "1080p" |

### 8.2 テンプレート例

```python
FILENAME_TEMPLATES = {
    "default": "{title}_{format}",
    "dated": "{title}_{format}_{date}",
    "detailed": "{title}_{index}_{chapter}_{format}_{datetime}",
    "simple": "{title}",
}

# 出力例
# "Amazing_Video_normal.mp4"
# "Amazing_Video_shorts_01.mp4"
# "Amazing_Video_01_opening_normal_20260119_153045.mp4"
```

---

## 9. ディスク容量管理

### 9.1 容量チェック

```python
def check_disk_space(
    output_dir: Path,
    estimated_size: int
) -> DiskSpaceResult:
    """
    出力先の空き容量をチェック

    Returns:
        DiskSpaceResult: 容量情報
    """

@dataclass
class DiskSpaceResult:
    available: int           # 利用可能容量（bytes）
    required: int            # 必要容量（bytes）
    is_sufficient: bool      # 十分かどうか
    warning_threshold: float = 0.1  # 警告閾値（10%）
    shows_warning: bool      # 警告表示が必要か
```

### 9.2 容量見積もり

```python
def estimate_output_size(
    segments: List[EditSegment],
    config: ExportConfig
) -> int:
    """
    出力ファイルサイズを見積もり

    考慮要素:
    - 動画長
    - 解像度
    - エンコード設定
    - 出力形式数
    """
```

---

## 10. 依存関係

### Python パッケージ
```
# 標準ライブラリ
zipfile
sqlite3
json

# 追加パッケージ
pydantic>=2.0.0   # データバリデーション
```

---

## 11. ファイル構成

```
src/core/exporter/
├── __init__.py
├── exporter.py           # メインクラス: Exporter
├── project_manager.py    # プロジェクト管理: ProjectManager
├── batch_exporter.py     # バッチ出力: BatchExporter
├── history_manager.py    # 履歴管理: HistoryManager
├── filename_generator.py # ファイル名生成
├── disk_manager.py       # ディスク容量管理
├── models.py             # データモデル
├── config.py             # 設定
└── exceptions.py         # カスタム例外
```

---

## 12. インターフェース定義

### Exporter クラス

```python
class Exporter:
    def __init__(
        self,
        video_editor: VideoEditor,
        subtitle_generator: SubtitleGenerator
    ):
        """初期化"""

    async def export(
        self,
        request: ExportRequest,
        progress_callback: Callable[[float, str], None] = None
    ) -> ExportResult:
        """
        出力を実行

        Args:
            request: 出力リクエスト
            progress_callback: 進捗コールバック

        Returns:
            ExportResult
        """

    def create_export_plan(
        self,
        request: ExportRequest
    ) -> ExportPlan:
        """
        出力計画を作成（プレビュー用）
        """

    def estimate_size(
        self,
        request: ExportRequest
    ) -> int:
        """
        出力サイズを見積もり
        """

    def estimate_time(
        self,
        request: ExportRequest
    ) -> float:
        """
        出力時間を見積もり（秒）
        """

    def cancel(self) -> None:
        """出力をキャンセル"""
```

---

## 13. 使用例

### 13.1 基本的な出力

```python
from core.exporter import Exporter, ExportRequest, ExportConfig

# 出力設定
config = ExportConfig(
    output_dir=Path("./output"),
    export_normal=True,
    export_shorts=True,
    combine_segments=True,
    burn_subtitles=True,
    encoding_preset="balanced"
)

# リクエスト作成
request = ExportRequest(
    project=project,
    segments=selected_segments,
    output_config=config
)

# 出力実行
exporter = Exporter(video_editor, subtitle_generator)
result = await exporter.export(
    request,
    progress_callback=lambda p, s: print(f"[{p:.1f}%] {s}")
)

# 結果確認
if result.success:
    print(f"出力完了: {len(result.output_files)} ファイル")
    for file in result.output_files:
        print(f"  - {file.path} ({file.size / 1024 / 1024:.1f}MB)")
else:
    print(f"エラー: {result.errors}")
```

### 13.2 プロジェクト保存

```python
from core.exporter import ProjectManager

manager = ProjectManager()

# 保存
manager.save(project, Path("./projects/my_project.yact"))

# 読み込み
loaded_project = manager.load(Path("./projects/my_project.yact"))

# 最近のプロジェクト
recent = manager.get_recent_projects(limit=5)
for info in recent:
    print(f"{info.name} - {info.updated_at}")
```

### 13.3 バッチ出力

```python
from core.exporter import BatchExporter, BatchExportConfig

batch_config = BatchExportConfig(
    parallel_exports=2,
    continue_on_error=True
)

batch_exporter = BatchExporter(exporter)

requests = [request1, request2, request3]

result = await batch_exporter.export_batch(
    requests,
    batch_config,
    progress_callback=lambda p: print(f"Batch: {p.completed}/{p.total}")
)

print(f"成功: {result.successful}/{result.total_requests}")
```

---

## 14. テスト項目

### ユニットテスト
- [ ] 出力計画の作成
- [ ] ファイル名テンプレート
- [ ] 容量見積もり
- [ ] プロジェクト保存/読み込み
- [ ] 履歴管理

### 統合テスト
- [ ] 通常動画の出力
- [ ] Shorts動画の出力
- [ ] 複数形式の同時出力
- [ ] バッチ出力
- [ ] エラーリカバリ
- [ ] ディスク容量不足時の動作
