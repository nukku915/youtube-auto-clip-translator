# 設計決定事項

このドキュメントは、実装前に決定した設計上の重要事項をまとめたものです。

---

## 1. データ受け渡し方式

### 決定: ハイブリッド方式

| データ種別 | 保存方式 | 理由 |
|-----------|---------|------|
| 動画/音声ファイル | ファイル保存 | サイズが大きい |
| 文字起こし結果 | メモリ + JSON保存 | 途中再開に必要 |
| AI分析結果 | メモリ + JSON保存 | 途中再開に必要 |
| 編集状態 | メモリ + 自動保存 | 30秒ごと |

### 処理中の動作

```
処理中にアプリを閉じようとした場合:
    ↓
確認ダイアログ表示
「処理中です。終了すると進行中の処理は破棄されます。終了しますか？」
    ↓
[キャンセル] → 処理継続
[終了] → 処理破棄、アプリ終了
```

### 途中再開

- 保存済みのプロジェクト（.yact）から再開可能
- 未保存の処理は破棄される

---

## 2. 非同期処理とキャンセル

### 決定: asyncio + ThreadPoolExecutor

```python
# 処理構成
Main Thread (GUI)
    ↓
asyncio event loop
    ↓
ThreadPoolExecutor (重い処理)
    ├─ FFmpeg呼び出し（サブプロセス）
    ├─ WhisperX処理
    └─ API呼び出し
```

### キャンセル処理

- 各処理にキャンセルフラグを実装
- キャンセル時は現在の処理を中断し、一時ファイルをクリーンアップ

---

## 3. プロジェクト自動保存

### 決定: 30秒ごと自動保存 + 手動保存

```python
AUTO_SAVE_CONFIG = {
    "interval_seconds": 30,
    "save_path": "~/.youtube-auto-clip-translator/autosave/",
    "max_autosaves": 5,  # 古いものは削除
}
```

### 保存タイミング

| タイミング | 動作 |
|-----------|------|
| 30秒ごと | 自動保存（ドラフト） |
| Ctrl+S | 手動保存（正式保存） |
| 処理完了時 | 自動保存 |
| アプリ終了時 | 確認ダイアログ後に保存 |

---

## 4. 動画プレビュー

### 決定: mpv埋め込み + 自動インストール

| 項目 | 内容 |
|------|------|
| プレーヤー | mpv（python-mpv経由） |
| 埋め込み | CustomTkinterウィンドウに埋め込み |
| 字幕表示 | ASSファイルをリアルタイム適用 |
| インストール | 自動インストール対象 |

### 技術的な実装

```python
# mpv埋め込みの基本構造
import mpv

class VideoPlayer(CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.player = mpv.MPV(
            wid=str(int(self.winfo_id())),  # ウィンドウに埋め込み
            vo="gpu",
            hwdec="auto"
        )

    def load_video(self, video_path: Path, subtitle_path: Path = None):
        self.player.play(str(video_path))
        if subtitle_path:
            self.player.sub_file = str(subtitle_path)

    def update_subtitle(self, subtitle_path: Path):
        """字幕ファイルを更新（編集時のリアルタイム反映）"""
        self.player.sub_file = str(subtitle_path)
        self.player.sub_reload = True
```

### 字幕編集時のフロー

```
字幕を編集
    ↓
一時ASSファイルを生成（即座に）
    ↓
mpvに字幕ファイルパスを渡す
    ↓
プレーヤーで即座に反映
```

---

## 5. APIキー管理

### 決定: 設定ファイル保存（平文）、GUIから設定

### 設定ファイル構造

```yaml
# ~/.youtube-auto-clip-translator/config.yaml
api:
  gemini:
    api_key: "YOUR_API_KEY_HERE"
    model: "gemini-3-flash"

# または環境変数からも読み込み可能
# GEMINI_API_KEY 環境変数が設定されている場合はそちらを優先
```

### GUI設定画面

```
┌─────────────────────────────────────────────────────────┐
│ API設定                                                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Gemini API Key                                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ ••••••••••••••••••••••••••••••                      │ │
│ └─────────────────────────────────────────────────────┘ │
│ [表示/非表示]  [接続テスト]                              │
│                                                         │
│ ステータス: ✓ 接続成功                                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### セキュリティ考慮

- 暗号化は一旦不要
- 設定ファイルは `~/.youtube-auto-clip-translator/` に保存
- ファイルパーミッションは 600（ユーザーのみ読み書き可）

---

## 6. 外部ツール自動インストール

### 決定: 自動インストール実施

### 対象ツール

| ツール | 用途 | インストール方法 |
|--------|------|-----------------|
| FFmpeg | 動画処理 | バイナリダウンロード |
| Deno | yt-dlp依存 | 公式インストーラー |
| mpv | プレビュー再生 | バイナリダウンロード |
| Ollama | ローカルLLM | 公式インストーラー + モデルDL |

### プラットフォーム別インストール

#### Windows
```python
INSTALL_URLS = {
    "ffmpeg": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    "deno": "https://deno.land/install.ps1",
    "mpv": "https://sourceforge.net/projects/mpv-player-windows/files/...",
    "ollama": "https://ollama.com/download/OllamaSetup.exe",
}
```

#### macOS
```python
# Homebrew経由 or バイナリダウンロード
INSTALL_COMMANDS = {
    "ffmpeg": "brew install ffmpeg",
    "deno": "brew install deno",
    "mpv": "brew install mpv",
    "ollama": "brew install ollama",
}
# Homebrewがない場合はバイナリをダウンロード
# Ollama: https://ollama.com/download/Ollama-darwin.zip
```

#### Linux
```python
INSTALL_COMMANDS = {
    "ffmpeg": "apt install ffmpeg / dnf install ffmpeg",
    "deno": "curl -fsSL https://deno.land/install.sh | sh",
    "mpv": "apt install mpv / dnf install mpv",
    "ollama": "curl -fsSL https://ollama.com/install.sh | sh",
}
```

### インストールフロー

```
アプリ起動
    ↓
依存関係チェック（FFmpeg, Deno, mpv, Ollama）
    ↓
不足あり？
    ├─ Yes → インストールダイアログ表示
    │         「以下のツールが必要です: FFmpeg, mpv, Ollama」
    │         [自動インストール] [手動でインストール] [キャンセル]
    │              ↓
    │         インストール実行（進捗表示）
    │              ↓
    │         完了 → アプリ起動継続
    │
    └─ No → アプリ起動継続
```

### Ollama自動セットアップ

```
Ollamaインストール完了
    ↓
Ollamaサービス起動確認
    ├─ 起動中 → 次へ
    └─ 未起動 → 自動起動 (ollama serve)
    ↓
モデルダウンロード
    ├─ gemma-2-jpn:2b が存在？
    │     ├─ Yes → 完了
    │     └─ No → ダウンロード確認ダイアログ
    │              「ローカルLLM用モデル（約1.5GB）をダウンロードしますか？」
    │              [ダウンロード] [後で] [スキップ]
    │                   ↓
    │              ollama pull gemma-2-jpn:2b
    │              （進捗表示）
    ↓
セットアップ完了
```

### モデルダウンロードの実装

```python
async def setup_ollama():
    """Ollamaのセットアップ"""

    # 1. Ollamaインストール確認
    if not is_ollama_installed():
        await install_ollama()

    # 2. サービス起動
    if not await is_ollama_running():
        await start_ollama_service()

    # 3. モデル確認・ダウンロード
    installed_models = await get_installed_models()
    required_model = "gemma-2-jpn:2b"

    if required_model not in installed_models:
        # ダウンロード確認
        if await confirm_model_download(required_model, size="~1.5GB"):
            await pull_model(required_model, progress_callback)


async def pull_model(model: str, progress_callback):
    """モデルをダウンロード"""
    process = await asyncio.create_subprocess_exec(
        "ollama", "pull", model,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    # 進捗をパースしてコールバック
    async for line in process.stdout:
        progress = parse_progress(line)
        progress_callback(progress, f"Downloading {model}...")
```

### インストール先

```
~/.youtube-auto-clip-translator/
├── bin/
│   ├── ffmpeg(.exe)
│   ├── ffprobe(.exe)
│   └── mpv(.exe)
├── config.yaml
└── ...

# Ollamaは独自のパスにインストール
# Windows: %LOCALAPPDATA%\Ollama
# macOS: /usr/local/bin/ollama
# Linux: /usr/local/bin/ollama

# Ollamaモデルの保存先
# Windows: %USERPROFILE%\.ollama\models
# macOS/Linux: ~/.ollama/models
```

---

## 7. Shorts変換（9:16）

### 決定: パディング方式 + グラスモーフィズム背景

### レイアウト

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

### FFmpeg実装

```bash
ffmpeg -i input.mp4 -filter_complex "
  # 背景: 拡大 + ぼかし + 暗く
  [0:v]scale=1080:1920:force_original_aspect_ratio=increase,
       crop=1080:1920,
       boxblur=30:30,
       eq=brightness=-0.3:saturation=0.8[bg];

  # 前景: アスペクト比維持でスケール
  [0:v]scale=1080:-1:force_original_aspect_ratio=decrease[fg];

  # 合成: 中央配置
  [bg][fg]overlay=(W-w)/2:(H-h)/2[out]
" -map "[out]" -map 0:a output_shorts.mp4
```

### オプション設定

```python
@dataclass
class ShortsBackgroundConfig:
    # 背景スタイル
    style: str = "glassmorphism"  # glassmorphism, solid, gradient

    # グラスモーフィズム設定
    blur_radius: int = 30
    brightness: float = -0.3  # 暗くする度合い
    saturation: float = 0.8   # 彩度

    # ソリッドカラー（style="solid"の場合）
    solid_color: str = "#000000"

    # グラデーション（style="gradient"の場合）
    gradient_start: str = "#1a1a2e"
    gradient_end: str = "#16213e"
```

---

## 8. 字幕タイミング調整UI

### 決定: 数値入力 + ドラッグ + 波形連動

### UI構成

```
┌─────────────────────────────────────────────────────────────┐
│ タイムライン                                                 │
├─────────────────────────────────────────────────────────────┤
│ ╭──╮   ╭────────╮  ╭──╮    ╭──────────╮                     │
│ │  │   │        │  │  │    │          │    ← 音声波形       │
│ ╰──╯   ╰────────╯  ╰──╯    ╰──────────╯                     │
│ ┌──┐   ┌────────┐         ┌──────────┐                      │
│ │S1│   │   S2   │         │    S3    │     ← 字幕ブロック   │
│ └──┘   └────────┘         └──────────┘       (ドラッグ可)   │
│ ├──────┼────────┼─────────┼──────────┤                      │
│ 0:00   0:02    0:04      0:06      0:10                     │
├─────────────────────────────────────────────────────────────┤
│ 選択中: S2                                                   │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 開始: [00:02.500] [+0.1s] [-0.1s]                       │ │
│ │ 終了: [00:04.800] [+0.1s] [-0.1s]                       │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 操作方法

| 操作 | 動作 |
|------|------|
| ドラッグ（左右端） | 開始/終了時間を調整 |
| ドラッグ（中央） | 字幕全体を移動 |
| ダブルクリック | 数値入力モード |
| ホイール | タイムラインズーム |
| ショートカット (+/-) | 0.1秒単位で調整 |

### 波形との連動

- 波形のピーク（発話開始）に字幕開始をスナップ
- 無音区間に字幕終了をスナップ
- スナップは Shift キーで一時的に無効化

---

## 9. エラーリカバリ

### 決定: 自動リトライ + スキップ選択 + 状態保存

### エラー種別と対処

| エラー種別 | 対処 |
|-----------|------|
| ネットワークエラー | 自動リトライ（3回、指数バックオフ） |
| API レート制限 | 待機後リトライ |
| API エラー | ユーザーに選択肢提示 |
| ファイルエラー | エラー報告、状態保存 |
| 致命的エラー | 状態保存、エラー報告 |

### APIエラー時のダイアログ

```
┌─────────────────────────────────────────────────────────┐
│ エラーが発生しました                                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ 翻訳処理中にエラーが発生しました。                       │
│                                                         │
│ エラー: API rate limit exceeded                         │
│                                                         │
│ [再試行]  [スキップして続行]  [中止]                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 状態保存

- エラー発生時は現在の状態を自動保存
- 次回起動時に復元オプションを表示

---

## 10. ハイブリッドLLM構成

### 決定: ローカルLLM（Ollama）+ クラウドLLM（Gemini）のハイブリッド

コスト削減とオフライン対応のため、タスクに応じてローカルLLMとクラウドLLMを使い分ける。

### 構成

| プロバイダ | 用途 | モデル |
|-----------|------|--------|
| Ollama（ローカル） | 見どころ検出、チャプター検出 | gemma-2-jpn:2b |
| Gemini（クラウド） | 翻訳、タイトル生成 | gemini-3-flash |

### タスク別振り分け

```python
@dataclass
class LLMConfig:
    # プロバイダ設定
    provider: str = "hybrid"  # "local", "gemini", "hybrid"

    # ローカルLLM（Ollama）設定
    local_enabled: bool = True
    local_model: str = "gemma-2-jpn:2b"
    ollama_host: str = "http://localhost:11434"

    # クラウドLLM（Gemini）設定
    gemini_enabled: bool = True
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash"

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
    fallback_to_gemini: bool = True  # ローカル失敗時にGeminiへ
```

### 振り分け理由

| タスク | 推奨 | 理由 |
|--------|------|------|
| 見どころ検出 | ローカル | テキスト分析のみ、精度要求が低め |
| チャプター検出 | ローカル | 構造認識、ローカルで十分 |
| 翻訳 | クラウド | 高品質な翻訳が必要 |
| タイトル生成 | クラウド | 創造性・ニュアンスが重要 |

### フォールバック動作

```
ローカルLLM処理開始
    ↓
成功？
    ├─ Yes → 結果を返却
    │
    └─ No → fallback_to_gemini が true？
              ├─ Yes → Geminiで再試行
              │          ↓
              │        成功 → 結果を返却
              │        失敗 → エラー
              │
              └─ No → エラー
```

### GUI設定画面

```
┌─────────────────────────────────────────────────────────┐
│ LLM設定                                                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ [モード選択]                                            │
│ ○ ハイブリッド（推奨）- ローカル + クラウド併用         │
│ ○ ローカルのみ - Ollama使用、オフライン動作可          │
│ ○ クラウドのみ - Gemini API使用                        │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ ローカルLLM (Ollama)                                    │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ ステータス: ✓ 起動中                                │ │
│ │ モデル: gemma-2-jpn:2b                              │ │
│ │ ホスト: http://localhost:11434                      │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Ollama起動] [モデルダウンロード]                        │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ クラウドLLM (Gemini)                                    │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ API Key: ••••••••••••••••                           │ │
│ └─────────────────────────────────────────────────────┘ │
│ [表示/非表示] [接続テスト]                              │
│ ステータス: ✓ 接続成功                                  │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ ☑ ローカル失敗時にクラウドへフォールバック             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 11. テスト戦略

### 決定: 手動テストのみ

### テスト方針

- 自動テストは書かない
- 開発中に手動で動作確認
- 主要フローを重点的にテスト

### 手動テスト項目

| フロー | テスト内容 |
|--------|-----------|
| ダウンロード | 通常動画、Shorts、長時間動画 |
| 文字起こし | 日本語、英語、ノイズ多い動画 |
| 翻訳 | 日→英、英→日、長文 |
| 編集 | 切り抜き、字幕編集、プレビュー |
| 書き出し | 通常、Shorts、両方 |

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-01-19 | 初版作成 |
| 2026-01-19 | ハイブリッドLLM構成（Section 10）、Ollama自動セットアップを追加 |
