# 動画取得モジュール詳細計画書

## 1. 概要

### 目的
YouTube動画URLから動画ファイルをダウンロードし、後続処理で使用できる形式で保存する

### 責務
- YouTube URL の検証
- 動画メタデータの取得
- 動画ファイルのダウンロード
- 通常動画 / Shorts の判別
- ダウンロード進捗の通知

---

## 2. 入出力仕様

### 入力
| 項目 | 型 | 必須 | 説明 |
|------|-----|------|------|
| url | string | Yes | YouTube動画URL |
| output_dir | Path | Yes | 保存先ディレクトリ |
| quality | string | No | 画質設定（デフォルト: "best"） |

### 出力
```python
@dataclass
class VideoFetchResult:
    video_path: Path           # ダウンロードした動画ファイルパス
    metadata: VideoMetadata    # 動画メタデータ
    is_shorts: bool            # Shortsかどうか
    duration: float            # 動画長（秒）
    original_url: str          # 元URL
```

### VideoMetadata
```python
@dataclass
class VideoMetadata:
    video_id: str              # YouTube動画ID
    title: str                 # 動画タイトル
    channel: str               # チャンネル名
    upload_date: str           # アップロード日
    duration: float            # 長さ（秒）
    width: int                 # 幅（px）
    height: int                # 高さ（px）
    fps: float                 # フレームレート
    description: str           # 説明文
    thumbnail_url: str         # サムネイルURL
```

---

## 3. 処理フロー

```
┌─────────────────────────────────────────────────────────┐
│                    URL入力                               │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 1. URL検証                                               │
│    ├─ YouTube URL形式チェック                            │
│    ├─ 動画ID抽出                                         │
│    └─ アクセス可能性確認                                  │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 2. メタデータ取得                                         │
│    ├─ yt-dlp --dump-json                                │
│    ├─ Shorts判定（縦横比 + duration）                    │
│    └─ 利用可能フォーマット一覧取得                        │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 3. フォーマット選択                                       │
│    ├─ 最適な動画+音声フォーマット選択                     │
│    └─ MP4形式を優先                                      │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 4. ダウンロード実行                                       │
│    ├─ 進捗コールバック発火                               │
│    ├─ 一時ファイルとしてDL                               │
│    └─ 完了後リネーム                                     │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 5. 後処理                                                │
│    ├─ ファイル整合性チェック                             │
│    ├─ メタデータJSONの保存                               │
│    └─ 結果オブジェクト生成                               │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 VideoFetchResult 返却                    │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Shorts判定ロジック

### 判定条件
```python
def is_shorts(metadata: VideoMetadata) -> bool:
    # 条件1: 縦型動画（高さ > 幅）
    is_vertical = metadata.height > metadata.width

    # 条件2: 60秒以下
    is_short_duration = metadata.duration <= 60

    # 条件3: URLに /shorts/ が含まれる（補助的）
    # is_shorts_url = "/shorts/" in original_url

    return is_vertical and is_short_duration
```

---

## 5. エラーハンドリング

### エラー種別
| エラー | 原因 | 対処 |
|--------|------|------|
| `InvalidURLError` | 不正なURL形式 | ユーザーに再入力を促す |
| `VideoNotFoundError` | 動画が存在しない/非公開 | エラーメッセージ表示 |
| `AgeRestrictedError` | 年齢制限動画 | Cookie設定を案内 |
| `GeoBlockedError` | 地域制限 | VPN利用を案内 |
| `DownloadError` | DL中のエラー | リトライ（最大3回） |
| `DiskSpaceError` | 容量不足 | 空き容量確認を促す |

### リトライ戦略
```python
RETRY_CONFIG = {
    "max_retries": 3,
    "backoff_factor": 2,  # 2秒, 4秒, 8秒
    "retryable_errors": [
        "DownloadError",
        "NetworkError",
    ]
}
```

---

## 6. 設定オプション

### ダウンロード設定
```python
@dataclass
class FetcherConfig:
    # 画質設定
    quality: str = "best"  # best, 1080p, 720p, 480p, 360p

    # フォーマット設定
    prefer_format: str = "mp4"  # mp4, webm

    # ネットワーク設定
    timeout: int = 30  # 秒
    retries: int = 3

    # プロキシ設定（オプション）
    proxy: Optional[str] = None

    # Cookie設定（年齢制限動画用）
    cookies_file: Optional[Path] = None

    # Deno パス（yt-dlp依存）
    deno_path: Optional[Path] = None
```

---

## 7. 依存関係

### 外部ツール（自動インストール対象）
| ツール | バージョン | 用途 | インストール方法 |
|--------|-----------|------|-----------------|
| yt-dlp | 2025.12+ | 動画ダウンロード | pip install |
| Deno | 最新 | yt-dlp YouTube対応 | 公式インストーラー |
| FFmpeg | 5.0+ | フォーマット変換 | バイナリ自動DL |

### 自動インストールフロー

```
アプリ起動
    ↓
依存関係チェック (check_dependencies())
    ↓
不足ツールあり？
    ├─ Yes → インストールダイアログ表示
    │         [自動インストール] [手動] [キャンセル]
    │              ↓
    │         インストール実行（進捗表示）
    │
    └─ No → 通常起動
```

### インストール先
```
~/.youtube-auto-clip-translator/
├── bin/
│   ├── ffmpeg(.exe)
│   ├── ffprobe(.exe)
│   └── deno(.exe)
└── ...
```

### Python パッケージ
```
yt-dlp>=2025.12.0
```

---

## 8. ファイル構成

```
src/core/video_fetcher/
├── __init__.py
├── fetcher.py          # メインクラス: VideoFetcher
├── metadata.py         # メタデータ処理
├── validators.py       # URL検証
├── exceptions.py       # カスタム例外
└── config.py           # 設定クラス
```

---

## 9. インターフェース定義

### VideoFetcher クラス
```python
class VideoFetcher:
    def __init__(self, config: FetcherConfig = None):
        """初期化"""

    async def fetch(
        self,
        url: str,
        output_dir: Path,
        progress_callback: Callable[[float, str], None] = None
    ) -> VideoFetchResult:
        """
        動画をダウンロード

        Args:
            url: YouTube動画URL
            output_dir: 保存先ディレクトリ
            progress_callback: 進捗通知コールバック (progress: 0-100, status: str)

        Returns:
            VideoFetchResult

        Raises:
            InvalidURLError: 無効なURL
            VideoNotFoundError: 動画が見つからない
            DownloadError: ダウンロード失敗
        """

    async def get_metadata(self, url: str) -> VideoMetadata:
        """メタデータのみ取得（ダウンロードなし）"""

    def validate_url(self, url: str) -> bool:
        """URL形式の検証"""

    def cancel(self) -> None:
        """ダウンロードをキャンセル"""
```

---

## 10. 使用例

```python
from core.video_fetcher import VideoFetcher, FetcherConfig

# 設定
config = FetcherConfig(quality="1080p")
fetcher = VideoFetcher(config)

# 進捗コールバック
def on_progress(progress: float, status: str):
    print(f"[{progress:.1f}%] {status}")

# ダウンロード実行
result = await fetcher.fetch(
    url="https://www.youtube.com/watch?v=XXXXX",
    output_dir=Path("./downloads"),
    progress_callback=on_progress
)

print(f"Downloaded: {result.video_path}")
print(f"Duration: {result.duration}s")
print(f"Is Shorts: {result.is_shorts}")
```

---

## 11. テスト項目

### ユニットテスト
- [ ] URL検証（正常系・異常系）
- [ ] メタデータ取得
- [ ] Shorts判定ロジック
- [ ] エラーハンドリング

### 統合テスト
- [ ] 通常動画のダウンロード
- [ ] Shorts動画のダウンロード
- [ ] 長時間動画のダウンロード（1時間以上）
- [ ] キャンセル処理
- [ ] リトライ処理

---

## 12. 追加仕様

### 12.1 プレイリスト対応

**MVPでは非対応**。単一動画のみ処理可能。

```python
# プレイリストURL検出
def is_playlist_url(url: str) -> bool:
    """プレイリストURLかどうかを判定"""
    return "list=" in url or "/playlist" in url

# プレイリストURLが入力された場合の対処
if is_playlist_url(url):
    raise PlaylistNotSupportedError(
        "プレイリストは現在対応していません。個別の動画URLを入力してください。"
    )
```

### 12.2 ライブ配信アーカイブ

| 状態 | 対応 | 説明 |
|------|------|------|
| ライブ配信中 | ❌ | エラー表示「ライブ配信は処理できません」 |
| アーカイブ処理中 | ❌ | エラー表示「アーカイブ処理中です。しばらくお待ちください」 |
| アーカイブ完了 | ✅ | 通常の動画として処理可能 |

```python
def check_video_status(metadata: dict) -> str:
    """動画のステータスを確認"""
    if metadata.get("is_live"):
        raise LiveStreamError("ライブ配信中の動画は処理できません")
    if metadata.get("live_status") == "post_live":
        # アーカイブ処理中の可能性
        if not metadata.get("duration"):
            raise ArchiveProcessingError("アーカイブ処理中です")
    return "available"
```

### 12.3 Cookie設定（年齢制限動画）

年齢制限動画をダウンロードするためのCookie設定手順：

#### ブラウザからCookieをエクスポート

1. **Chrome拡張機能を使用**
   - 「Get cookies.txt LOCALLY」等の拡張機能をインストール
   - YouTubeにログインした状態でCookieをエクスポート
   - `cookies.txt` として保存

2. **保存場所**
   ```
   ~/.youtube-auto-clip-translator/cookies.txt
   ```

3. **設定ファイルで指定**
   ```yaml
   fetcher:
     cookies_file: "~/.youtube-auto-clip-translator/cookies.txt"
   ```

#### Cookie自動検出

```python
def find_cookies_file() -> Optional[Path]:
    """Cookieファイルを自動検出"""
    candidates = [
        Path.home() / ".youtube-auto-clip-translator" / "cookies.txt",
        Path.home() / "cookies.txt",
        Path.cwd() / "cookies.txt",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None
```

### 12.4 プロキシ設定

```python
@dataclass
class ProxyConfig:
    # プロキシURL（例: "http://127.0.0.1:8080"）
    url: str = ""

    # 認証情報（必要な場合）
    username: str = ""
    password: str = ""

    # プロキシタイプ
    type: str = "http"  # http, https, socks5

def build_proxy_url(config: ProxyConfig) -> str:
    """プロキシURLを構築"""
    if not config.url:
        return ""

    if config.username and config.password:
        # 認証付きプロキシ
        parsed = urlparse(config.url)
        return f"{parsed.scheme}://{config.username}:{config.password}@{parsed.netloc}"

    return config.url
```

### 12.5 ダウンロード中断・再開

```python
@dataclass
class DownloadState:
    url: str
    output_path: Path
    downloaded_bytes: int
    total_bytes: int
    temp_file: Path
    timestamp: datetime

class ResumableDownloader:
    """中断可能なダウンローダー"""

    def __init__(self, state_path: Path):
        self.state_path = state_path

    def save_state(self, state: DownloadState) -> None:
        """ダウンロード状態を保存"""
        with open(self.state_path, "w") as f:
            json.dump(asdict(state), f)

    def load_state(self) -> Optional[DownloadState]:
        """中断したダウンロードの状態を復元"""
        if not self.state_path.exists():
            return None
        with open(self.state_path) as f:
            data = json.load(f)
            return DownloadState(**data)

    def can_resume(self, state: DownloadState) -> bool:
        """再開可能かチェック"""
        # 一時ファイルが存在し、24時間以内の場合は再開可能
        if not state.temp_file.exists():
            return False
        age = datetime.now() - state.timestamp
        return age.total_seconds() < 86400  # 24時間
```

### 12.6 既存字幕のダウンロード

YouTubeに既存の字幕がある場合、それをダウンロードして活用可能：

```python
@dataclass
class SubtitleInfo:
    language: str
    language_name: str
    is_auto_generated: bool
    url: str

async def get_available_subtitles(url: str) -> List[SubtitleInfo]:
    """利用可能な字幕一覧を取得"""
    # yt-dlp --list-subs を使用
    ...

async def download_subtitle(
    url: str,
    language: str,
    output_path: Path,
    prefer_manual: bool = True  # 手動作成字幕を優先
) -> Path:
    """字幕をダウンロード"""
    # yt-dlp --write-sub --sub-lang {language} を使用
    ...
```

**字幕活用フロー**:
```
1. 字幕一覧を取得
2. 手動作成字幕があれば優先使用（文字起こしスキップ可能）
3. 自動生成字幕のみの場合は参考として使用
4. 字幕がない場合は WhisperX で文字起こし
```

---

## 13. 制限事項・注意点

1. **著作権**: ダウンロードは個人利用目的に限定。再配布は利用者の責任。
2. **利用規約**: YouTube利用規約に準拠した使用を推奨。
3. **レート制限**: 短時間に大量リクエストを避ける。
4. **Deno依存**: yt-dlpの次期バージョンからDenoが必須。
5. **プレイリスト**: MVP では非対応（将来対応予定）
6. **ライブ配信**: アーカイブ完了後のみ対応

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-01-19 | 初版作成 |
| 2026-01-19 | 追加仕様（プレイリスト、Cookie、プロキシ等）を追記 |
