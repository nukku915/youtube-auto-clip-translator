# エラーコード体系

## 1. エラーコード形式

```
YACT-{カテゴリ}{番号}

例: YACT-F001（Fetcherのエラー#001）
```

### カテゴリ一覧

| コード | カテゴリ | モジュール |
|--------|---------|-----------|
| F | Fetcher | video_fetcher |
| A | Audio | audio_processor |
| T | Transcription | transcriber |
| L | LLM | ai_analyzer |
| S | Subtitle | subtitle_generator |
| E | Editor | video_editor |
| X | Export | exporter |
| C | Config | config_manager |
| G | GUI | gui |
| P | Project | project_manager |

---

## 2. エラー種別

| 種別 | 説明 | 対処方針 |
|------|------|---------|
| **回復可能** | リトライで解決する可能性 | 自動リトライ or ユーザーに再試行を提案 |
| **ユーザー操作必要** | ユーザーの設定変更が必要 | ガイダンス表示、設定画面へ誘導 |
| **致命的** | 処理続行不可 | 状態保存、エラー報告 |

---

## 3. エラーコード詳細

### 3.1 Fetcher (F)

| コード | エラー名 | 種別 | 説明 | ユーザー向けメッセージ |
|--------|---------|------|------|----------------------|
| YACT-F001 | InvalidURLError | ユーザー操作 | 無効なURL形式 | 「正しいYouTube URLを入力してください」 |
| YACT-F002 | VideoNotFoundError | ユーザー操作 | 動画が存在しない | 「動画が見つかりません。URLを確認してください」 |
| YACT-F003 | VideoPrivateError | ユーザー操作 | 非公開動画 | 「この動画は非公開のためダウンロードできません」 |
| YACT-F004 | AgeRestrictedError | ユーザー操作 | 年齢制限 | 「年齢制限動画です。Cookie設定が必要です」 |
| YACT-F005 | GeoBlockedError | ユーザー操作 | 地域制限 | 「この動画はお住まいの地域では利用できません」 |
| YACT-F006 | DownloadError | 回復可能 | ダウンロード失敗 | 「ダウンロードに失敗しました。再試行しますか？」 |
| YACT-F007 | NetworkError | 回復可能 | ネットワークエラー | 「ネットワーク接続を確認してください」 |
| YACT-F008 | DiskSpaceError | 致命的 | 容量不足 | 「ディスク容量が不足しています」 |
| YACT-F009 | VideoTooLongError | ユーザー操作 | 動画が長すぎる | 「2時間を超える動画は処理できません」 |
| YACT-F010 | LiveStreamError | ユーザー操作 | ライブ配信 | 「ライブ配信は処理できません。アーカイブをお待ちください」 |

### 3.2 Audio Processor (A)

| コード | エラー名 | 種別 | 説明 | ユーザー向けメッセージ |
|--------|---------|------|------|----------------------|
| YACT-A001 | AudioExtractionError | 回復可能 | 音声抽出失敗 | 「音声の抽出に失敗しました」 |
| YACT-A002 | FFmpegNotFoundError | ユーザー操作 | FFmpegが見つからない | 「FFmpegがインストールされていません」 |
| YACT-A003 | InvalidAudioFormatError | 致命的 | 対応していない音声形式 | 「この動画の音声形式は対応していません」 |
| YACT-A004 | NoAudioTrackError | 致命的 | 音声トラックがない | 「この動画には音声がありません」 |

### 3.3 Transcriber (T)

| コード | エラー名 | 種別 | 説明 | ユーザー向けメッセージ |
|--------|---------|------|------|----------------------|
| YACT-T001 | ModelLoadError | ユーザー操作 | モデルロード失敗 | 「文字起こしモデルの読み込みに失敗しました」 |
| YACT-T002 | OutOfMemoryError | ユーザー操作 | メモリ/VRAM不足 | 「メモリが不足しています。小さいモデルに変更してください」 |
| YACT-T003 | TranscriptionError | 回復可能 | 文字起こし失敗 | 「文字起こしに失敗しました」 |
| YACT-T004 | EmptyTranscriptionError | 致命的 | 文字起こし結果が空 | 「音声を認識できませんでした」 |
| YACT-T005 | LanguageDetectionError | 回復可能 | 言語検出失敗 | 「言語を自動検出できませんでした」 |
| YACT-T006 | CUDAError | ユーザー操作 | GPU エラー | 「GPUエラーが発生しました。CPU モードに切り替えますか？」 |

### 3.4 LLM / AI Analyzer (L)

| コード | エラー名 | 種別 | 説明 | ユーザー向けメッセージ |
|--------|---------|------|------|----------------------|
| YACT-L001 | APIKeyError | ユーザー操作 | APIキーが無効 | 「Gemini APIキーが無効です。設定を確認してください」 |
| YACT-L002 | APIKeyMissingError | ユーザー操作 | APIキーが未設定 | 「Gemini APIキーが設定されていません」 |
| YACT-L003 | RateLimitError | 回復可能 | レート制限 | 「API制限に達しました。しばらく待ってから再試行します」 |
| YACT-L004 | QuotaExceededError | ユーザー操作 | 使用量上限 | 「APIの使用量上限に達しました」 |
| YACT-L005 | APITimeoutError | 回復可能 | タイムアウト | 「APIがタイムアウトしました。再試行しますか？」 |
| YACT-L006 | InvalidResponseError | 回復可能 | 不正なレスポンス | 「AIからの応答を解析できませんでした」 |
| YACT-L007 | OllamaNotRunningError | ユーザー操作 | Ollama未起動 | 「Ollamaが起動していません。起動しますか？」 |
| YACT-L008 | OllamaModelNotFoundError | ユーザー操作 | モデル未DL | 「Ollamaモデルがありません。ダウンロードしますか？」 |
| YACT-L009 | TranslationError | 回復可能 | 翻訳失敗 | 「翻訳に失敗しました」 |
| YACT-L010 | PartialTranslationError | 回復可能 | 一部失敗 | 「一部の翻訳に失敗しました。再試行しますか？」 |

### 3.5 Subtitle Generator (S)

| コード | エラー名 | 種別 | 説明 | ユーザー向けメッセージ |
|--------|---------|------|------|----------------------|
| YACT-S001 | SubtitleWriteError | 回復可能 | 書き込み失敗 | 「字幕ファイルの保存に失敗しました」 |
| YACT-S002 | FontNotFoundError | 回復可能 | フォントがない | 「指定されたフォントが見つかりません。デフォルトを使用します」 |
| YACT-S003 | InvalidTimingError | 回復可能 | タイミングエラー | 「字幕のタイミングに問題があります」 |

### 3.6 Video Editor (E)

| コード | エラー名 | 種別 | 説明 | ユーザー向けメッセージ |
|--------|---------|------|------|----------------------|
| YACT-E001 | FFmpegError | 回復可能 | FFmpegエラー | 「動画の編集中にエラーが発生しました」 |
| YACT-E002 | EncodingError | 回復可能 | エンコード失敗 | 「動画のエンコードに失敗しました」 |
| YACT-E003 | InvalidSegmentError | ユーザー操作 | 無効なセグメント | 「セグメントの開始/終了時間が無効です」 |
| YACT-E004 | TitleCardError | 回復可能 | タイトル生成失敗 | 「タイトルカードの生成に失敗しました」 |
| YACT-E005 | DiskSpaceError | 致命的 | 容量不足 | 「ディスク容量が不足しています」 |
| YACT-E006 | HWAccelError | 回復可能 | HWエンコーダーエラー | 「ハードウェアエンコードに失敗。ソフトウェアに切り替えます」 |

### 3.7 Exporter (X)

| コード | エラー名 | 種別 | 説明 | ユーザー向けメッセージ |
|--------|---------|------|------|----------------------|
| YACT-X001 | ExportError | 回復可能 | 出力失敗 | 「ファイルの出力に失敗しました」 |
| YACT-X002 | DiskSpaceError | 致命的 | 容量不足 | 「ディスク容量が不足しています」 |
| YACT-X003 | PermissionError | ユーザー操作 | 権限エラー | 「出力先に書き込み権限がありません」 |
| YACT-X004 | FileExistsError | ユーザー操作 | ファイル存在 | 「同名のファイルが存在します。上書きしますか？」 |

### 3.8 Config (C)

| コード | エラー名 | 種別 | 説明 | ユーザー向けメッセージ |
|--------|---------|------|------|----------------------|
| YACT-C001 | ConfigLoadError | 回復可能 | 設定読み込み失敗 | 「設定ファイルを読み込めません。デフォルト設定を使用します」 |
| YACT-C002 | ConfigSaveError | 回復可能 | 設定保存失敗 | 「設定の保存に失敗しました」 |
| YACT-C003 | ConfigValidationError | ユーザー操作 | バリデーションエラー | 「設定値が無効です」 |

### 3.9 Project (P)

| コード | エラー名 | 種別 | 説明 | ユーザー向けメッセージ |
|--------|---------|------|------|----------------------|
| YACT-P001 | ProjectLoadError | 回復可能 | 読み込み失敗 | 「プロジェクトを読み込めません」 |
| YACT-P002 | ProjectSaveError | 回復可能 | 保存失敗 | 「プロジェクトの保存に失敗しました」 |
| YACT-P003 | ProjectCorruptedError | 致命的 | 破損 | 「プロジェクトファイルが破損しています」 |
| YACT-P004 | AutoSaveError | 回復可能 | 自動保存失敗 | 「自動保存に失敗しました」 |

---

## 4. エラー実装

### 4.1 基底クラス

```python
# utils/exceptions.py
from dataclasses import dataclass
from enum import Enum

class ErrorSeverity(str, Enum):
    RECOVERABLE = "recoverable"
    USER_ACTION = "user_action"
    FATAL = "fatal"

@dataclass
class YACTError(Exception):
    code: str
    message: str
    user_message: str
    severity: ErrorSeverity
    details: dict = None

    def __str__(self):
        return f"[{self.code}] {self.message}"
```

### 4.2 モジュール別例外

```python
# core/video_fetcher/exceptions.py
from utils.exceptions import YACTError, ErrorSeverity

class FetcherError(YACTError):
    pass

class InvalidURLError(FetcherError):
    def __init__(self, url: str):
        super().__init__(
            code="YACT-F001",
            message=f"Invalid URL: {url}",
            user_message="正しいYouTube URLを入力してください",
            severity=ErrorSeverity.USER_ACTION,
            details={"url": url}
        )

class VideoNotFoundError(FetcherError):
    def __init__(self, video_id: str):
        super().__init__(
            code="YACT-F002",
            message=f"Video not found: {video_id}",
            user_message="動画が見つかりません。URLを確認してください",
            severity=ErrorSeverity.USER_ACTION,
            details={"video_id": video_id}
        )
```

### 4.3 エラーハンドリング

```python
# app/workflow_engine.py
async def run_full_pipeline(self, url: str, ...):
    try:
        result = await self.video_fetcher.fetch(url)
    except InvalidURLError as e:
        # ユーザー操作必要 → GUIでダイアログ表示
        self._notify_error(e)
        raise
    except DownloadError as e:
        # 回復可能 → リトライ提案
        if await self._ask_retry():
            return await self.run_full_pipeline(url, ...)
        raise
    except DiskSpaceError as e:
        # 致命的 → 状態保存して中止
        await self._save_state()
        self._notify_error(e)
        raise
```

---

## 5. ログ出力

エラー発生時は以下の形式でログ出力:

```
2026-01-19 15:30:45 ERROR [YACT-F001] Invalid URL: https://example.com
  Severity: user_action
  Details: {"url": "https://example.com"}
  Stack trace:
    File "video_fetcher.py", line 45, in fetch
    ...
```

---

## 6. GUI表示

### エラーダイアログ

```
┌─────────────────────────────────────────────────────────┐
│ エラー                                            [×]   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ⚠️ 動画が見つかりません                                │
│                                                         │
│  URLを確認してください。                                │
│                                                         │
│  エラーコード: YACT-F002                                │
│                                                         │
│              [詳細を表示]    [OK]                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-01-19 | 初版作成 |

