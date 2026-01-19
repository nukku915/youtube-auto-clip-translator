# システムアーキテクチャ

## 1. 層構造

```
┌─────────────────────────────────────────────────────────────────┐
│                          GUI層                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ HomeView │ │Processing│ │ Editor   │ │ Settings │            │
│  │          │ │   View   │ │   View   │ │   View   │            │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│                          ↓ ↑                                     │
├─────────────────────────────────────────────────────────────────┤
│                     アプリケーション層                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │  Workflow    │ │    State     │ │   Project    │             │
│  │   Engine     │ │   Manager    │ │   Manager    │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
│         │                                                        │
│         ↓ パイプライン制御                                        │
├─────────────────────────────────────────────────────────────────┤
│                         コア層                                    │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ Video   │→│ Audio   │→│Transcri-│→│   AI    │→│Subtitle │   │
│  │ Fetcher │ │Processor│ │  ber    │ │Analyzer │ │Generator│   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│                                              ↓                   │
│                              ┌─────────┐ ┌─────────┐            │
│                              │ Video   │→│Exporter │            │
│                              │ Editor  │ │         │            │
│                              └─────────┘ └─────────┘            │
├─────────────────────────────────────────────────────────────────┤
│                       外部依存                                    │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ yt-dlp  │ │ FFmpeg  │ │WhisperX │ │ Gemini  │ │  mpv    │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 各層の責務

### 2.1 GUI層

| 責務 | 説明 |
|------|------|
| ユーザー入力の受付 | URL入力、ボタンクリック、編集操作 |
| 状態の表示 | 進捗バー、プレビュー、字幕リスト |
| イベント発火 | アプリケーション層へのアクション通知 |

**含まれるもの:**
- Views（各画面）
- Components（再利用可能なUI部品）
- Theme（色、フォント）

### 2.2 アプリケーション層

| 責務 | 説明 |
|------|------|
| ワークフロー制御 | 処理の順序制御、進捗管理 |
| 状態管理 | アプリ全体の状態を一元管理 |
| プロジェクト管理 | 保存、読み込み、自動保存 |

**含まれるもの:**
- WorkflowEngine
- StateManager
- ProjectManager
- ConfigManager

### 2.3 コア層

| 責務 | 説明 |
|------|------|
| 各処理の実装 | 動画取得、文字起こし、翻訳等 |
| 外部ツール連携 | FFmpeg、WhisperX、Gemini API |
| データ変換 | 入力→出力のデータ変換 |

**含まれるもの:**
- video_fetcher
- audio_processor
- transcriber
- ai_analyzer
- subtitle_generator
- video_editor
- exporter

---

## 3. データフロー（パイプライン）

```
URL (str)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ VideoFetcher                                                 │
│ 入力: URL                                                    │
│ 出力: VideoFetchResult (video_path, metadata)                │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ AudioProcessor                                               │
│ 入力: video_path                                             │
│ 出力: audio_path (WAV 16kHz mono)                            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Transcriber                                                  │
│ 入力: audio_path                                             │
│ 出力: TranscriptionResult (segments with timestamps)         │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ AIAnalyzer                                                   │
│ 入力: TranscriptionResult                                    │
│ 出力: AnalysisResult (highlights, chapters, translation)     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼ ユーザー編集（GUI）
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ SubtitleGenerator                                            │
│ 入力: TranslationResult, StyleConfig                         │
│ 出力: SubtitleResult (ASS/SRT file path)                     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ VideoEditor                                                  │
│ 入力: video_path, segments, subtitle_path                    │
│ 出力: EditResult (edited video path)                         │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Exporter                                                     │
│ 入力: EditResult, ExportConfig                               │
│ 出力: ExportResult (output files list)                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. モジュール依存関係

### 4.1 依存関係図

```
video_fetcher ──────────────────────────────────────────┐
      │                                                  │
      ▼                                                  │
audio_processor                                          │
      │                                                  │
      ▼                                                  │
transcriber                                              │
      │                                                  │
      ▼                                                  │
ai_analyzer ──────────────────────┐                      │
      │                            │                      │
      ▼                            ▼                      │
subtitle_generator          (user editing)               │
      │                            │                      │
      ▼                            │                      │
video_editor ◄─────────────────────┘                     │
      │                                                  │
      ▼                                                  │
exporter ◄───────────────────────────────────────────────┘
           (metadata from video_fetcher)
```

### 4.2 依存ルール

| ルール | 説明 |
|--------|------|
| 上位→下位のみ | GUI層→アプリ層→コア層の方向のみ依存可 |
| コア層は独立 | コア層のモジュールは他のコア層モジュールをimportしない |
| データで疎結合 | モジュール間はデータクラスでのみ連携 |

---

## 5. ディレクトリ構造

```
src/
├── main.py                    # エントリーポイント
│
├── app/                       # アプリケーション層
│   ├── __init__.py
│   ├── workflow_engine.py     # ワークフロー制御
│   ├── state_manager.py       # 状態管理
│   ├── project_manager.py     # プロジェクト管理
│   └── config_manager.py      # 設定管理
│
├── core/                      # コア層
│   ├── __init__.py
│   ├── video_fetcher.py
│   ├── audio_processor.py
│   ├── transcriber.py
│   ├── ai_analyzer/
│   │   ├── __init__.py
│   │   ├── analyzer.py
│   │   ├── translator.py
│   │   └── llm/
│   │       ├── gemini_client.py
│   │       └── ollama_client.py
│   ├── subtitle_generator.py
│   ├── video_editor.py
│   └── exporter.py
│
├── gui/                       # GUI層
│   ├── __init__.py
│   ├── app.py                 # メインウィンドウ
│   ├── views/
│   │   ├── home.py
│   │   ├── processing.py
│   │   ├── editor.py
│   │   ├── preview.py
│   │   ├── export.py
│   │   └── settings.py
│   ├── components/
│   │   ├── video_player.py
│   │   ├── timeline.py
│   │   └── subtitle_table.py
│   └── theme/
│       └── colors.py
│
├── models/                    # 共有データモデル
│   ├── __init__.py
│   ├── project.py
│   ├── transcription.py
│   ├── translation.py
│   ├── segment.py
│   └── subtitle.py
│
├── config/                    # 設定
│   ├── __init__.py
│   └── settings.py
│
└── utils/                     # ユーティリティ
    ├── __init__.py
    ├── file_utils.py
    └── time_utils.py
```

---

## 6. WorkflowEngine

### 6.1 責務

- コア層モジュールの呼び出し順序制御
- 進捗の集約・通知
- エラーハンドリング
- キャンセル処理

### 6.2 インターフェース

```python
class WorkflowEngine:
    async def run_full_pipeline(
        self,
        url: str,
        config: PipelineConfig,
        progress_callback: Callable[[float, str], None]
    ) -> Project:
        """
        URL入力から編集準備完了まで実行

        1. VideoFetcher.fetch()
        2. AudioProcessor.extract()
        3. Transcriber.transcribe()
        4. AIAnalyzer.analyze()

        Returns: 編集可能なProjectオブジェクト
        """

    async def run_export_pipeline(
        self,
        project: Project,
        export_config: ExportConfig,
        progress_callback: Callable[[float, str], None]
    ) -> ExportResult:
        """
        編集完了後の書き出し

        1. SubtitleGenerator.generate()
        2. VideoEditor.edit()
        3. Exporter.export()
        """

    def cancel(self) -> None:
        """実行中のパイプラインをキャンセル"""
```

---

## 7. 非同期処理

### 7.1 処理モデル

```
┌─────────────────────────────────────────────────────────────┐
│ Main Thread (GUI)                                            │
│   ├─ イベントループ（CustomTkinter）                          │
│   └─ UIの更新                                                │
└─────────────────────────────────────────────────────────────┘
         │ 非同期タスク発行
         ▼
┌─────────────────────────────────────────────────────────────┐
│ asyncio Event Loop                                           │
│   ├─ WorkflowEngine.run_full_pipeline()                      │
│   └─ 各コアモジュールの非同期メソッド                          │
└─────────────────────────────────────────────────────────────┘
         │ 重い処理
         ▼
┌─────────────────────────────────────────────────────────────┐
│ ThreadPoolExecutor                                           │
│   ├─ FFmpeg実行                                              │
│   ├─ WhisperX推論                                            │
│   └─ ファイルI/O                                             │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 進捗通知

```python
# 進捗コールバックの型
ProgressCallback = Callable[[float, str], None]

# 使用例
def on_progress(progress: float, status: str):
    """
    progress: 0.0 ~ 100.0
    status: "動画をダウンロード中..." など
    """
    update_ui(progress, status)
```

---

## 8. エラーハンドリング

### 8.1 エラーの流れ

```
コア層でエラー発生
    │
    ▼
コア層: 特定の例外をraise
    │
    ▼
WorkflowEngine: 例外をキャッチ、ログ記録
    │
    ▼
WorkflowEngine: ユーザー向けエラーに変換
    │
    ▼
GUI層: エラーダイアログ表示
```

### 8.2 エラーカテゴリ

| カテゴリ | 例 | 対処 |
|----------|-----|------|
| 回復可能 | ネットワークエラー | リトライ提案 |
| ユーザー操作必要 | APIキー無効 | 設定画面へ誘導 |
| 致命的 | ディスク満杯 | 処理中止、状態保存 |

---

## 9. 設定の流れ

```
┌─────────────────────────────────────────────────────────────┐
│ 設定ファイル (~/.youtube-auto-clip-translator/config.yaml)  │
└─────────────────────────────────────────────────────────────┘
         │ 起動時読み込み
         ▼
┌─────────────────────────────────────────────────────────────┐
│ ConfigManager                                                │
│   ├─ 設定のバリデーション（Pydantic）                         │
│   ├─ 環境変数のマージ                                        │
│   └─ デフォルト値の適用                                      │
└─────────────────────────────────────────────────────────────┘
         │ 各層に注入
         ▼
┌─────────────────────────────────────────────────────────────┐
│ 各モジュール                                                 │
│   ├─ VideoFetcher(config.fetcher)                           │
│   ├─ Transcriber(config.whisper)                            │
│   └─ AIAnalyzer(config.llm)                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 10. 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-01-19 | 初版作成 |

