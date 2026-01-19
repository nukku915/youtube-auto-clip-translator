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

---

## 15. 追加仕様

### 15.1 YouTube直接アップロード

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Callable
from pathlib import Path
import json

class YouTubePrivacy(Enum):
    """公開設定"""
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"

class YouTubeCategory(Enum):
    """動画カテゴリ"""
    FILM_ANIMATION = "1"
    AUTOS_VEHICLES = "2"
    MUSIC = "10"
    PETS_ANIMALS = "15"
    SPORTS = "17"
    GAMING = "20"
    PEOPLE_BLOGS = "22"
    COMEDY = "23"
    ENTERTAINMENT = "24"
    NEWS_POLITICS = "25"
    HOWTO_STYLE = "26"
    EDUCATION = "27"
    SCIENCE_TECH = "28"

@dataclass
class YouTubeUploadConfig:
    """YouTubeアップロード設定"""
    title: str
    description: str = ""
    tags: List[str] = None
    category: YouTubeCategory = YouTubeCategory.ENTERTAINMENT
    privacy: YouTubePrivacy = YouTubePrivacy.PRIVATE

    # Shorts設定
    is_short: bool = False

    # 予約投稿
    publish_at: Optional[str] = None  # ISO 8601形式

    # サムネイル
    thumbnail_path: Optional[Path] = None

    # 字幕
    upload_captions: bool = True
    caption_language: str = "ja"

@dataclass
class YouTubeUploadResult:
    """アップロード結果"""
    success: bool
    video_id: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None
    upload_time: float = 0.0

class YouTubeUploader:
    """YouTube Data API v3を使用したアップローダー"""

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube"
    ]

    def __init__(self, credentials_path: Path):
        """
        Args:
            credentials_path: OAuth2.0クレデンシャルファイルパス
        """
        self.credentials_path = credentials_path
        self._youtube = None

    def authenticate(self) -> bool:
        """
        OAuth2.0認証を実行

        初回は ブラウザが開いて認証フローを完了する必要がある
        """
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            token_path = self.credentials_path.parent / "token.json"

            creds = None
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(
                    str(token_path), self.SCOPES
                )

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    from google.auth.transport.requests import Request
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path), self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                # トークン保存
                with open(token_path, 'w') as f:
                    f.write(creds.to_json())

            self._youtube = build('youtube', 'v3', credentials=creds)
            return True

        except Exception as e:
            print(f"認証エラー: {e}")
            return False

    async def upload(
        self,
        video_path: Path,
        config: YouTubeUploadConfig,
        progress_callback: Callable[[float], None] = None
    ) -> YouTubeUploadResult:
        """
        動画をYouTubeにアップロード
        """
        import time
        from googleapiclient.http import MediaFileUpload

        if not self._youtube:
            if not self.authenticate():
                return YouTubeUploadResult(
                    success=False,
                    error="認証に失敗しました"
                )

        start_time = time.time()

        try:
            # メタデータ設定
            body = {
                "snippet": {
                    "title": config.title[:100],  # 100文字制限
                    "description": config.description[:5000],  # 5000文字制限
                    "tags": config.tags or [],
                    "categoryId": config.category.value,
                },
                "status": {
                    "privacyStatus": config.privacy.value,
                    "selfDeclaredMadeForKids": False,
                }
            }

            # 予約投稿
            if config.publish_at:
                body["status"]["publishAt"] = config.publish_at

            # Shorts最適化
            if config.is_short:
                # タイトルに#Shortsを追加（自動認識のため）
                if "#Shorts" not in body["snippet"]["title"]:
                    body["snippet"]["title"] += " #Shorts"

            # メディアファイル
            media = MediaFileUpload(
                str(video_path),
                chunksize=1024 * 1024,  # 1MB chunks
                resumable=True,
                mimetype='video/mp4'
            )

            # アップロードリクエスト
            request = self._youtube.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media
            )

            # 進捗追跡付きアップロード
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status and progress_callback:
                    progress_callback(status.progress())

            video_id = response["id"]

            # サムネイルアップロード
            if config.thumbnail_path and config.thumbnail_path.exists():
                await self._upload_thumbnail(video_id, config.thumbnail_path)

            # 字幕アップロード
            if config.upload_captions:
                # 字幕ファイルを探す
                caption_path = video_path.with_suffix(".srt")
                if caption_path.exists():
                    await self._upload_caption(
                        video_id,
                        caption_path,
                        config.caption_language
                    )

            return YouTubeUploadResult(
                success=True,
                video_id=video_id,
                video_url=f"https://www.youtube.com/watch?v={video_id}",
                upload_time=time.time() - start_time
            )

        except Exception as e:
            return YouTubeUploadResult(
                success=False,
                error=str(e),
                upload_time=time.time() - start_time
            )

    async def _upload_thumbnail(
        self,
        video_id: str,
        thumbnail_path: Path
    ) -> bool:
        """サムネイルをアップロード"""
        from googleapiclient.http import MediaFileUpload

        try:
            media = MediaFileUpload(
                str(thumbnail_path),
                mimetype='image/jpeg'
            )
            self._youtube.thumbnails().set(
                videoId=video_id,
                media_body=media
            ).execute()
            return True
        except Exception:
            return False

    async def _upload_caption(
        self,
        video_id: str,
        caption_path: Path,
        language: str
    ) -> bool:
        """字幕をアップロード"""
        from googleapiclient.http import MediaFileUpload

        try:
            media = MediaFileUpload(
                str(caption_path),
                mimetype='application/x-subrip'
            )
            self._youtube.captions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "language": language,
                        "name": f"{language} subtitles"
                    }
                },
                media_body=media
            ).execute()
            return True
        except Exception:
            return False


# MVPでの制限事項
"""
YouTubeアップロード機能の制限:
1. OAuth2.0認証が必要（初回はブラウザ認証フロー）
2. YouTube Data API v3のクォータ制限に注意
   - 1日あたり10,000ユニット
   - 動画アップロード: 1,600ユニット/リクエスト
3. チャンネルが確認済みである必要がある（15分以上の動画）
4. APIキーはGoogle Cloud Consoleで取得

MVP対応範囲:
- 基本的な動画アップロード
- メタデータ設定（タイトル、説明、タグ）
- 公開設定
- サムネイル設定

将来的な拡張:
- 複数アカウント対応
- アップロードキューイング
- 分析データ連携
"""
```

### 15.2 動画メタデータ埋め込み

```python
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path
from datetime import datetime
import subprocess
import json

@dataclass
class VideoMetadataEmbed:
    """埋め込みメタデータ"""
    title: str
    description: Optional[str] = None
    author: Optional[str] = None
    copyright: Optional[str] = None
    creation_date: Optional[datetime] = None

    # カスタムタグ
    tags: List[str] = None
    language: str = "ja"

    # 元動画情報
    source_url: Optional[str] = None
    source_title: Optional[str] = None

    # アプリケーション情報
    encoder: str = "YouTube Auto Clip Translator"
    encoder_version: str = "1.0.0"

class MetadataEmbedder:
    """FFmpegを使用したメタデータ埋め込み"""

    def embed_metadata(
        self,
        video_path: Path,
        metadata: VideoMetadataEmbed,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        動画ファイルにメタデータを埋め込む

        Args:
            video_path: 入力動画パス
            metadata: 埋め込むメタデータ
            output_path: 出力パス（Noneなら上書き）

        Returns:
            出力ファイルパス
        """
        if output_path is None:
            output_path = video_path.with_stem(video_path.stem + "_meta")

        # FFmpegメタデータオプション構築
        metadata_args = self._build_metadata_args(metadata)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            *metadata_args,
            "-c", "copy",  # 再エンコードなし
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)

        # 上書きモードの場合、ファイルを置き換え
        if output_path != video_path:
            import shutil
            shutil.move(str(output_path), str(video_path))
            return video_path

        return output_path

    def _build_metadata_args(
        self,
        metadata: VideoMetadataEmbed
    ) -> List[str]:
        """FFmpegメタデータ引数を構築"""
        args = []

        # 基本メタデータ
        if metadata.title:
            args.extend(["-metadata", f"title={metadata.title}"])

        if metadata.description:
            args.extend(["-metadata", f"description={metadata.description}"])
            args.extend(["-metadata", f"comment={metadata.description}"])

        if metadata.author:
            args.extend(["-metadata", f"artist={metadata.author}"])
            args.extend(["-metadata", f"author={metadata.author}"])

        if metadata.copyright:
            args.extend(["-metadata", f"copyright={metadata.copyright}"])

        if metadata.creation_date:
            date_str = metadata.creation_date.strftime("%Y-%m-%d")
            args.extend(["-metadata", f"date={date_str}"])
            args.extend(["-metadata", f"creation_time={metadata.creation_date.isoformat()}"])

        # 言語
        args.extend(["-metadata", f"language={metadata.language}"])

        # エンコーダー情報
        args.extend(["-metadata", f"encoder={metadata.encoder} v{metadata.encoder_version}"])

        # カスタムタグ（JSON形式で埋め込み）
        if metadata.tags:
            tags_json = json.dumps(metadata.tags, ensure_ascii=False)
            args.extend(["-metadata", f"keywords={','.join(metadata.tags)}"])

        # 元動画情報（カスタムメタデータ）
        if metadata.source_url:
            args.extend(["-metadata", f"source_url={metadata.source_url}"])

        if metadata.source_title:
            args.extend(["-metadata", f"source_title={metadata.source_title}"])

        return args

    def read_metadata(self, video_path: Path) -> dict:
        """動画からメタデータを読み取る"""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(video_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        return data.get("format", {}).get("tags", {})

    def embed_chapters(
        self,
        video_path: Path,
        chapters: List[dict],
        output_path: Optional[Path] = None
    ) -> Path:
        """
        チャプター情報を埋め込む

        Args:
            chapters: [{"title": "Chapter 1", "start": 0.0, "end": 60.0}, ...]
        """
        if output_path is None:
            output_path = video_path.with_stem(video_path.stem + "_chapters")

        # チャプターメタデータファイル作成
        chapter_file = video_path.with_suffix(".chapters.txt")
        self._write_chapter_file(chapters, chapter_file)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(chapter_file),
            "-map_metadata", "1",
            "-c", "copy",
            str(output_path)
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        finally:
            chapter_file.unlink(missing_ok=True)

        return output_path

    def _write_chapter_file(
        self,
        chapters: List[dict],
        output_path: Path
    ) -> None:
        """FFmpegメタデータ形式のチャプターファイルを作成"""
        lines = [";FFMETADATA1"]

        for chapter in chapters:
            start_ms = int(chapter["start"] * 1000)
            end_ms = int(chapter["end"] * 1000)
            title = chapter["title"]

            lines.extend([
                "",
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={start_ms}",
                f"END={end_ms}",
                f"title={title}"
            ])

        output_path.write_text("\n".join(lines), encoding="utf-8")
```

### 15.3 サムネイル自動生成

```python
from dataclasses import dataclass
from typing import Optional, List, Tuple
from pathlib import Path
import subprocess
import json

@dataclass
class ThumbnailConfig:
    """サムネイル生成設定"""
    width: int = 1280
    height: int = 720
    format: str = "jpg"
    quality: int = 90

    # テキストオーバーレイ
    overlay_text: Optional[str] = None
    text_font: str = "Noto Sans JP"
    text_size: int = 72
    text_color: str = "white"
    text_outline: bool = True
    text_position: str = "center"  # "center", "bottom", "top"

    # 背景処理
    blur_background: bool = False
    darken_background: float = 0.3  # 0.0-1.0

@dataclass
class ThumbnailResult:
    """サムネイル生成結果"""
    path: Path
    width: int
    height: int
    size: int
    selected_time: float

class ThumbnailGenerator:
    """サムネイル自動生成"""

    def __init__(self, video_path: Path):
        self.video_path = video_path
        self.duration = self._get_duration()

    def _get_duration(self) -> float:
        """動画の長さを取得"""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(self.video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])

    def generate_at_time(
        self,
        time: float,
        output_path: Path,
        config: ThumbnailConfig = None
    ) -> ThumbnailResult:
        """
        指定時間のフレームからサムネイルを生成
        """
        if config is None:
            config = ThumbnailConfig()

        # フィルターチェーン構築
        filters = self._build_filters(config)

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(time),
            "-i", str(self.video_path),
            "-vframes", "1",
            "-vf", filters,
            "-q:v", str(100 - config.quality),
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)

        return ThumbnailResult(
            path=output_path,
            width=config.width,
            height=config.height,
            size=output_path.stat().st_size,
            selected_time=time
        )

    def generate_best(
        self,
        output_path: Path,
        config: ThumbnailConfig = None,
        candidates: int = 10
    ) -> ThumbnailResult:
        """
        最適なフレームを自動選択してサムネイルを生成

        選択基準:
        - 動きの少ないフレーム（ブレが少ない）
        - 明るさが適切なフレーム
        - 顔検出（オプション）
        """
        if config is None:
            config = ThumbnailConfig()

        # 候補時間を生成（動画の10%-90%の範囲で均等分割）
        start_time = self.duration * 0.1
        end_time = self.duration * 0.9
        interval = (end_time - start_time) / candidates

        candidate_times = [
            start_time + i * interval
            for i in range(candidates)
        ]

        # 各候補のスコアを計算
        best_time = candidate_times[0]
        best_score = -1

        for time in candidate_times:
            score = self._calculate_frame_score(time)
            if score > best_score:
                best_score = score
                best_time = time

        return self.generate_at_time(best_time, output_path, config)

    def _calculate_frame_score(self, time: float) -> float:
        """フレームの品質スコアを計算"""
        # 一時ファイルに抽出
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # フレーム抽出
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(time),
                "-i", str(self.video_path),
                "-vframes", "1",
                str(tmp_path)
            ]
            subprocess.run(cmd, capture_output=True)

            # スコア計算（明るさ、コントラスト、シャープネス）
            score = self._analyze_image(tmp_path)
            return score

        finally:
            tmp_path.unlink(missing_ok=True)

    def _analyze_image(self, image_path: Path) -> float:
        """画像の品質スコアを計算"""
        try:
            from PIL import Image
            import numpy as np

            img = Image.open(image_path).convert("L")  # グレースケール
            arr = np.array(img)

            # 明るさ（中程度が最適）
            brightness = arr.mean()
            brightness_score = 1 - abs(brightness - 128) / 128

            # コントラスト（標準偏差が高いほど良い）
            contrast = arr.std()
            contrast_score = min(contrast / 50, 1.0)

            # シャープネス（ラプラシアン分散）
            from scipy import ndimage
            laplacian = ndimage.laplace(arr)
            sharpness = laplacian.var()
            sharpness_score = min(sharpness / 500, 1.0)

            # 総合スコア
            return (brightness_score * 0.3 +
                    contrast_score * 0.3 +
                    sharpness_score * 0.4)

        except ImportError:
            # PIL/scipy がない場合はファイルサイズベース
            return image_path.stat().st_size / 100000

    def _build_filters(self, config: ThumbnailConfig) -> str:
        """FFmpegフィルターチェーンを構築"""
        filters = []

        # リサイズ
        filters.append(f"scale={config.width}:{config.height}:force_original_aspect_ratio=decrease")
        filters.append(f"pad={config.width}:{config.height}:(ow-iw)/2:(oh-ih)/2")

        # 背景ぼかし（Shorts用に縦長にする場合など）
        if config.blur_background:
            # 背景用にぼかしたレイヤーを作成
            # 複雑なフィルターになるため、ここでは簡略化
            pass

        # 背景を暗くする
        if config.darken_background > 0:
            filters.append(f"eq=brightness=-{config.darken_background}")

        # テキストオーバーレイ
        if config.overlay_text:
            text_filter = self._build_text_filter(config)
            filters.append(text_filter)

        return ",".join(filters)

    def _build_text_filter(self, config: ThumbnailConfig) -> str:
        """テキストオーバーレイフィルターを構築"""
        # テキスト位置
        if config.text_position == "center":
            x = "(w-tw)/2"
            y = "(h-th)/2"
        elif config.text_position == "bottom":
            x = "(w-tw)/2"
            y = "h-th-50"
        else:  # top
            x = "(w-tw)/2"
            y = "50"

        # アウトライン
        if config.text_outline:
            # 影を追加してアウトライン効果
            border = ":shadowcolor=black:shadowx=2:shadowy=2"
        else:
            border = ""

        # エスケープ処理
        text = config.overlay_text.replace(":", "\\:")

        return (
            f"drawtext=text='{text}':"
            f"fontfile=/System/Library/Fonts/{config.text_font}.ttc:"
            f"fontsize={config.text_size}:"
            f"fontcolor={config.text_color}:"
            f"x={x}:y={y}"
            f"{border}"
        )

    def generate_grid(
        self,
        output_path: Path,
        columns: int = 3,
        rows: int = 3,
        config: ThumbnailConfig = None
    ) -> Path:
        """
        複数フレームのグリッドサムネイルを生成
        """
        if config is None:
            config = ThumbnailConfig()

        total_frames = columns * rows
        interval = self.duration / (total_frames + 1)

        # 各セルのサイズ
        cell_width = config.width // columns
        cell_height = config.height // rows

        # フレーム抽出 + グリッド作成
        cmd = [
            "ffmpeg", "-y",
            "-i", str(self.video_path),
            "-vf", (
                f"fps=1/{interval},"
                f"scale={cell_width}:{cell_height},"
                f"tile={columns}x{rows}"
            ),
            "-frames:v", "1",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
```

### 15.4 並列出力時のリソース管理

```python
from dataclasses import dataclass
from typing import Optional, Dict, List
from enum import Enum
import threading
import psutil
import time

class ResourceType(Enum):
    """リソースタイプ"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK_IO = "disk_io"
    GPU = "gpu"
    GPU_MEMORY = "gpu_memory"

@dataclass
class ResourceLimits:
    """リソース制限設定"""
    max_cpu_percent: float = 80.0        # CPU使用率上限
    max_memory_percent: float = 70.0     # メモリ使用率上限
    max_disk_io_mbps: float = 100.0      # ディスクI/O上限
    max_gpu_percent: float = 90.0        # GPU使用率上限
    max_gpu_memory_percent: float = 80.0 # GPUメモリ上限

    # 並列数制限
    max_parallel_exports: int = 2
    max_parallel_encodes: int = 1        # 重いエンコードは1つずつ

@dataclass
class ResourceUsage:
    """現在のリソース使用状況"""
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_io_read_mbps: float
    disk_io_write_mbps: float
    gpu_percent: Optional[float] = None
    gpu_memory_percent: Optional[float] = None

class ResourceMonitor:
    """リソースモニタリング"""

    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_usage: Optional[ResourceUsage] = None
        self._disk_io_prev = None
        self._disk_io_time_prev = None

    def start(self) -> None:
        """モニタリング開始"""
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """モニタリング停止"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def get_current_usage(self) -> ResourceUsage:
        """現在のリソース使用状況を取得"""
        if self._last_usage:
            return self._last_usage
        return self._measure_usage()

    def _monitor_loop(self) -> None:
        """モニタリングループ"""
        while self._running:
            self._last_usage = self._measure_usage()
            time.sleep(self.interval)

    def _measure_usage(self) -> ResourceUsage:
        """リソース使用量を計測"""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # メモリ
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available / (1024 * 1024)

        # ディスクI/O
        disk_io = psutil.disk_io_counters()
        current_time = time.time()

        if self._disk_io_prev and self._disk_io_time_prev:
            time_delta = current_time - self._disk_io_time_prev
            read_delta = disk_io.read_bytes - self._disk_io_prev.read_bytes
            write_delta = disk_io.write_bytes - self._disk_io_prev.write_bytes

            read_mbps = (read_delta / time_delta) / (1024 * 1024)
            write_mbps = (write_delta / time_delta) / (1024 * 1024)
        else:
            read_mbps = 0.0
            write_mbps = 0.0

        self._disk_io_prev = disk_io
        self._disk_io_time_prev = current_time

        # GPU（オプション）
        gpu_percent = None
        gpu_memory_percent = None
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

            gpu_percent = util.gpu
            gpu_memory_percent = (memory_info.used / memory_info.total) * 100
            pynvml.nvmlShutdown()
        except Exception:
            pass

        return ResourceUsage(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_available_mb=memory_available_mb,
            disk_io_read_mbps=read_mbps,
            disk_io_write_mbps=write_mbps,
            gpu_percent=gpu_percent,
            gpu_memory_percent=gpu_memory_percent
        )

class ResourceManager:
    """並列出力時のリソース管理"""

    def __init__(self, limits: ResourceLimits = None):
        self.limits = limits or ResourceLimits()
        self.monitor = ResourceMonitor()
        self._active_jobs: Dict[str, dict] = {}
        self._lock = threading.Lock()

        # モニタリング開始
        self.monitor.start()

    def can_start_job(self, job_type: str = "export") -> bool:
        """
        新しいジョブを開始できるか判定
        """
        usage = self.monitor.get_current_usage()

        # リソース制限チェック
        if usage.cpu_percent > self.limits.max_cpu_percent:
            return False

        if usage.memory_percent > self.limits.max_memory_percent:
            return False

        if usage.gpu_percent and usage.gpu_percent > self.limits.max_gpu_percent:
            return False

        # 並列数チェック
        with self._lock:
            active_count = len(self._active_jobs)
            encode_count = sum(
                1 for j in self._active_jobs.values()
                if j.get("type") == "encode"
            )

        if active_count >= self.limits.max_parallel_exports:
            return False

        if job_type == "encode" and encode_count >= self.limits.max_parallel_encodes:
            return False

        return True

    def register_job(self, job_id: str, job_type: str = "export") -> bool:
        """ジョブを登録"""
        if not self.can_start_job(job_type):
            return False

        with self._lock:
            self._active_jobs[job_id] = {
                "type": job_type,
                "started_at": time.time()
            }
        return True

    def unregister_job(self, job_id: str) -> None:
        """ジョブを登録解除"""
        with self._lock:
            self._active_jobs.pop(job_id, None)

    def wait_for_resources(
        self,
        job_type: str = "export",
        timeout: float = 300.0
    ) -> bool:
        """リソースが利用可能になるまで待機"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.can_start_job(job_type):
                return True
            time.sleep(1.0)

        return False

    def get_recommended_settings(self) -> dict:
        """
        現在のリソース状況に基づく推奨設定を返す
        """
        usage = self.monitor.get_current_usage()

        settings = {
            "parallel_exports": self.limits.max_parallel_exports,
            "hw_accel": True,
            "preset": "medium"
        }

        # メモリ不足時
        if usage.memory_percent > 60:
            settings["parallel_exports"] = 1
            settings["preset"] = "faster"  # より軽いプリセット

        # GPU利用可能かつ余裕がある場合
        if usage.gpu_percent is not None and usage.gpu_percent < 50:
            settings["hw_accel"] = True
        elif usage.gpu_percent is None:
            settings["hw_accel"] = False

        return settings

    def shutdown(self) -> None:
        """シャットダウン"""
        self.monitor.stop()
```

### 15.5 部分出力のレジューム

```python
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from pathlib import Path
from datetime import datetime
from enum import Enum
import json

class ExportStage(Enum):
    """出力ステージ"""
    PENDING = "pending"
    SUBTITLE_GENERATION = "subtitle_generation"
    VIDEO_ENCODING = "video_encoding"
    METADATA_EMBEDDING = "metadata_embedding"
    THUMBNAIL_GENERATION = "thumbnail_generation"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ExportCheckpoint:
    """出力チェックポイント"""
    export_id: str
    stage: ExportStage
    progress: float  # 0.0-1.0

    # 完了したファイル
    completed_files: List[str] = field(default_factory=list)

    # 現在処理中のファイル
    current_file: Optional[str] = None
    current_file_progress: float = 0.0

    # エラー情報
    last_error: Optional[str] = None
    retry_count: int = 0

    # タイムスタンプ
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 設定スナップショット
    config_snapshot: Optional[dict] = None

class CheckpointManager:
    """チェックポイント管理"""

    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _get_checkpoint_path(self, export_id: str) -> Path:
        """チェックポイントファイルパス"""
        return self.checkpoint_dir / f"{export_id}.checkpoint.json"

    def save(self, checkpoint: ExportCheckpoint) -> None:
        """チェックポイントを保存"""
        checkpoint.updated_at = datetime.now()

        data = {
            "export_id": checkpoint.export_id,
            "stage": checkpoint.stage.value,
            "progress": checkpoint.progress,
            "completed_files": checkpoint.completed_files,
            "current_file": checkpoint.current_file,
            "current_file_progress": checkpoint.current_file_progress,
            "last_error": checkpoint.last_error,
            "retry_count": checkpoint.retry_count,
            "created_at": checkpoint.created_at.isoformat(),
            "updated_at": checkpoint.updated_at.isoformat(),
            "config_snapshot": checkpoint.config_snapshot
        }

        path = self._get_checkpoint_path(checkpoint.export_id)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def load(self, export_id: str) -> Optional[ExportCheckpoint]:
        """チェックポイントを読み込み"""
        path = self._get_checkpoint_path(export_id)

        if not path.exists():
            return None

        data = json.loads(path.read_text())

        return ExportCheckpoint(
            export_id=data["export_id"],
            stage=ExportStage(data["stage"]),
            progress=data["progress"],
            completed_files=data["completed_files"],
            current_file=data["current_file"],
            current_file_progress=data["current_file_progress"],
            last_error=data["last_error"],
            retry_count=data["retry_count"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            config_snapshot=data["config_snapshot"]
        )

    def delete(self, export_id: str) -> None:
        """チェックポイントを削除"""
        path = self._get_checkpoint_path(export_id)
        path.unlink(missing_ok=True)

    def list_incomplete(self) -> List[ExportCheckpoint]:
        """未完了のチェックポイント一覧"""
        checkpoints = []

        for path in self.checkpoint_dir.glob("*.checkpoint.json"):
            data = json.loads(path.read_text())
            if data["stage"] not in [ExportStage.COMPLETED.value, ExportStage.FAILED.value]:
                checkpoints.append(self.load(data["export_id"]))

        return checkpoints

class ResumableExporter:
    """レジューム可能なエクスポーター"""

    def __init__(
        self,
        exporter,  # 通常のExporter
        checkpoint_manager: CheckpointManager
    ):
        self.exporter = exporter
        self.checkpoint_manager = checkpoint_manager

    async def export_with_resume(
        self,
        request,  # ExportRequest
        export_id: Optional[str] = None
    ):
        """
        レジューム可能な出力を実行
        """
        import uuid

        if export_id is None:
            export_id = str(uuid.uuid4())

        # 既存のチェックポイントを確認
        checkpoint = self.checkpoint_manager.load(export_id)

        if checkpoint is None:
            # 新規開始
            checkpoint = ExportCheckpoint(
                export_id=export_id,
                stage=ExportStage.PENDING,
                progress=0.0,
                config_snapshot=request.output_config.__dict__
            )
            self.checkpoint_manager.save(checkpoint)

        try:
            # ステージごとに処理を再開
            if checkpoint.stage == ExportStage.PENDING:
                checkpoint.stage = ExportStage.SUBTITLE_GENERATION
                self.checkpoint_manager.save(checkpoint)

            if checkpoint.stage == ExportStage.SUBTITLE_GENERATION:
                await self._export_subtitles(request, checkpoint)
                checkpoint.stage = ExportStage.VIDEO_ENCODING
                self.checkpoint_manager.save(checkpoint)

            if checkpoint.stage == ExportStage.VIDEO_ENCODING:
                await self._export_videos(request, checkpoint)
                checkpoint.stage = ExportStage.METADATA_EMBEDDING
                self.checkpoint_manager.save(checkpoint)

            if checkpoint.stage == ExportStage.METADATA_EMBEDDING:
                await self._embed_metadata(request, checkpoint)
                checkpoint.stage = ExportStage.THUMBNAIL_GENERATION
                self.checkpoint_manager.save(checkpoint)

            if checkpoint.stage == ExportStage.THUMBNAIL_GENERATION:
                await self._generate_thumbnails(request, checkpoint)
                checkpoint.stage = ExportStage.COMPLETED
                self.checkpoint_manager.save(checkpoint)

            # 完了時にチェックポイント削除
            self.checkpoint_manager.delete(export_id)

            return {"success": True, "export_id": export_id}

        except Exception as e:
            checkpoint.last_error = str(e)
            checkpoint.retry_count += 1
            checkpoint.stage = ExportStage.FAILED
            self.checkpoint_manager.save(checkpoint)

            return {"success": False, "error": str(e), "can_resume": True}

    async def _export_subtitles(self, request, checkpoint: ExportCheckpoint):
        """字幕出力（レジューム対応）"""
        # 既に完了したファイルはスキップ
        for subtitle_config in request.subtitle_config.formats:
            output_file = f"subtitles_{subtitle_config}.srt"
            if output_file in checkpoint.completed_files:
                continue

            checkpoint.current_file = output_file
            self.checkpoint_manager.save(checkpoint)

            # 字幕生成処理
            # await self.exporter.generate_subtitle(...)

            checkpoint.completed_files.append(output_file)
            self.checkpoint_manager.save(checkpoint)

    async def _export_videos(self, request, checkpoint: ExportCheckpoint):
        """動画出力（レジューム対応）"""
        # 各セグメントを処理
        for i, segment in enumerate(request.segments):
            output_file = f"segment_{i}.mp4"
            if output_file in checkpoint.completed_files:
                continue

            checkpoint.current_file = output_file
            checkpoint.current_file_progress = 0.0
            self.checkpoint_manager.save(checkpoint)

            # エンコード処理（進捗コールバック付き）
            def progress_callback(progress):
                checkpoint.current_file_progress = progress
                self.checkpoint_manager.save(checkpoint)

            # await self.exporter.encode_segment(..., progress_callback)

            checkpoint.completed_files.append(output_file)
            self.checkpoint_manager.save(checkpoint)

    async def _embed_metadata(self, request, checkpoint: ExportCheckpoint):
        """メタデータ埋め込み"""
        pass

    async def _generate_thumbnails(self, request, checkpoint: ExportCheckpoint):
        """サムネイル生成"""
        pass
```

### 15.6 出力プリセット保存

```python
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from pathlib import Path
from datetime import datetime
import json

@dataclass
class ExportPreset:
    """出力プリセット"""
    id: str
    name: str
    description: str = ""

    # 動画設定
    export_normal: bool = True
    export_shorts: bool = True
    combine_segments: bool = True
    export_individual: bool = False

    # エンコード設定
    encoding_preset: str = "balanced"
    resolution: Optional[tuple] = None
    hw_accel: bool = True

    # 字幕設定
    burn_subtitles: bool = True
    export_subtitle_files: bool = True
    subtitle_formats: List[str] = field(default_factory=lambda: ["srt", "ass"])
    subtitle_languages: List[str] = field(default_factory=lambda: ["translated"])
    bilingual_subtitles: bool = False

    # ファイル名設定
    filename_template: str = "{title}_{format}"

    # メタデータ・YouTubeアップロード
    embed_metadata: bool = True
    auto_thumbnail: bool = True
    youtube_upload: bool = False
    youtube_privacy: str = "private"

    # メタ情報
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_default: bool = False
    usage_count: int = 0

# 組み込みプリセット
BUILTIN_PRESETS: List[ExportPreset] = [
    ExportPreset(
        id="quick",
        name="クイック出力",
        description="高速で基本的な出力",
        encoding_preset="fast",
        export_shorts=False,
        export_subtitle_files=False,
        auto_thumbnail=False
    ),
    ExportPreset(
        id="balanced",
        name="バランス出力（推奨）",
        description="品質と速度のバランスが取れた設定",
        encoding_preset="balanced",
        is_default=True
    ),
    ExportPreset(
        id="high_quality",
        name="高品質出力",
        description="最高品質でのエンコード",
        encoding_preset="quality",
        hw_accel=False,  # ソフトウェアエンコード
        subtitle_formats=["srt", "ass", "vtt"]
    ),
    ExportPreset(
        id="shorts_only",
        name="Shorts専用",
        description="YouTube Shorts向けの出力",
        export_normal=False,
        export_shorts=True,
        combine_segments=False,
        export_individual=True,
        auto_thumbnail=True
    ),
    ExportPreset(
        id="archive",
        name="アーカイブ用",
        description="すべての形式で出力（保存用）",
        export_normal=True,
        export_shorts=True,
        combine_segments=True,
        export_individual=True,
        subtitle_formats=["srt", "ass", "vtt"],
        subtitle_languages=["original", "translated"],
        bilingual_subtitles=True,
        embed_metadata=True
    ),
    ExportPreset(
        id="youtube_ready",
        name="YouTube投稿用",
        description="YouTube投稿に最適化",
        encoding_preset="balanced",
        embed_metadata=True,
        auto_thumbnail=True,
        youtube_upload=True,
        youtube_privacy="private"
    ),
]

class PresetManager:
    """出力プリセット管理"""

    def __init__(self, presets_dir: Path):
        self.presets_dir = presets_dir
        self.presets_dir.mkdir(parents=True, exist_ok=True)
        self._presets: Dict[str, ExportPreset] = {}
        self._load_presets()

    def _load_presets(self) -> None:
        """プリセットを読み込み"""
        # 組み込みプリセット
        for preset in BUILTIN_PRESETS:
            self._presets[preset.id] = preset

        # ユーザープリセット
        for path in self.presets_dir.glob("*.preset.json"):
            try:
                data = json.loads(path.read_text())
                preset = self._dict_to_preset(data)
                self._presets[preset.id] = preset
            except Exception:
                pass

    def _dict_to_preset(self, data: dict) -> ExportPreset:
        """辞書からプリセットを作成"""
        if "created_at" in data:
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if "resolution" in data and data["resolution"]:
            data["resolution"] = tuple(data["resolution"])
        return ExportPreset(**data)

    def _preset_to_dict(self, preset: ExportPreset) -> dict:
        """プリセットを辞書に変換"""
        data = asdict(preset)
        data["created_at"] = preset.created_at.isoformat()
        data["updated_at"] = preset.updated_at.isoformat()
        if data["resolution"]:
            data["resolution"] = list(data["resolution"])
        return data

    def get(self, preset_id: str) -> Optional[ExportPreset]:
        """プリセットを取得"""
        return self._presets.get(preset_id)

    def get_all(self) -> List[ExportPreset]:
        """全プリセットを取得"""
        return list(self._presets.values())

    def get_default(self) -> ExportPreset:
        """デフォルトプリセットを取得"""
        for preset in self._presets.values():
            if preset.is_default:
                return preset
        return BUILTIN_PRESETS[1]  # balanced

    def save(self, preset: ExportPreset) -> None:
        """プリセットを保存"""
        # 組み込みプリセットは上書き不可
        if preset.id in [p.id for p in BUILTIN_PRESETS]:
            raise ValueError(f"組み込みプリセット '{preset.id}' は変更できません")

        preset.updated_at = datetime.now()
        self._presets[preset.id] = preset

        # ファイルに保存
        path = self.presets_dir / f"{preset.id}.preset.json"
        data = self._preset_to_dict(preset)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def delete(self, preset_id: str) -> bool:
        """プリセットを削除"""
        if preset_id in [p.id for p in BUILTIN_PRESETS]:
            return False

        if preset_id in self._presets:
            del self._presets[preset_id]
            path = self.presets_dir / f"{preset_id}.preset.json"
            path.unlink(missing_ok=True)
            return True

        return False

    def duplicate(
        self,
        preset_id: str,
        new_name: str,
        new_id: Optional[str] = None
    ) -> ExportPreset:
        """プリセットを複製"""
        import uuid

        original = self.get(preset_id)
        if not original:
            raise ValueError(f"プリセット '{preset_id}' が見つかりません")

        new_preset = ExportPreset(
            id=new_id or str(uuid.uuid4())[:8],
            name=new_name,
            description=f"{original.description}（{original.name}のコピー）",
            export_normal=original.export_normal,
            export_shorts=original.export_shorts,
            combine_segments=original.combine_segments,
            export_individual=original.export_individual,
            encoding_preset=original.encoding_preset,
            resolution=original.resolution,
            hw_accel=original.hw_accel,
            burn_subtitles=original.burn_subtitles,
            export_subtitle_files=original.export_subtitle_files,
            subtitle_formats=original.subtitle_formats.copy(),
            subtitle_languages=original.subtitle_languages.copy(),
            bilingual_subtitles=original.bilingual_subtitles,
            filename_template=original.filename_template,
            embed_metadata=original.embed_metadata,
            auto_thumbnail=original.auto_thumbnail,
            youtube_upload=original.youtube_upload,
            youtube_privacy=original.youtube_privacy
        )

        self.save(new_preset)
        return new_preset

    def set_default(self, preset_id: str) -> None:
        """デフォルトプリセットを設定"""
        if preset_id not in self._presets:
            raise ValueError(f"プリセット '{preset_id}' が見つかりません")

        # 既存のデフォルトを解除
        for preset in self._presets.values():
            if preset.is_default:
                preset.is_default = False
                if preset.id not in [p.id for p in BUILTIN_PRESETS]:
                    self.save(preset)

        # 新しいデフォルトを設定
        self._presets[preset_id].is_default = True
        if preset_id not in [p.id for p in BUILTIN_PRESETS]:
            self.save(self._presets[preset_id])

    def record_usage(self, preset_id: str) -> None:
        """使用回数を記録"""
        if preset_id in self._presets:
            self._presets[preset_id].usage_count += 1
            if preset_id not in [p.id for p in BUILTIN_PRESETS]:
                self.save(self._presets[preset_id])

    def get_recently_used(self, limit: int = 5) -> List[ExportPreset]:
        """最近使用したプリセットを取得"""
        sorted_presets = sorted(
            self._presets.values(),
            key=lambda p: p.usage_count,
            reverse=True
        )
        return sorted_presets[:limit]

    def apply_to_config(self, preset: ExportPreset, config) -> None:
        """プリセットを設定に適用"""
        config.export_normal = preset.export_normal
        config.export_shorts = preset.export_shorts
        config.combine_segments = preset.combine_segments
        config.export_individual = preset.export_individual
        config.encoding_preset = preset.encoding_preset
        config.resolution = preset.resolution
        config.hw_accel = preset.hw_accel
        config.burn_subtitles = preset.burn_subtitles
        config.export_subtitle_files = preset.export_subtitle_files
        config.filename_template = preset.filename_template

---

## 16. 更新履歴

| 日付 | 内容 |
|------|------|
| 2024-01-15 | 初版作成 |
| 2024-01-20 | 追加仕様セクション追加（YouTube直接アップロード、メタデータ埋め込み、サムネイル自動生成、リソース管理、レジューム、プリセット保存） |
