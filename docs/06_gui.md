# GUIモジュール詳細計画書

## 1. 概要

### 目的
CustomTkinterを使用して、直感的で使いやすいデスクトップアプリケーションを提供する

### 責務
- ユーザーインターフェースの提供
- ワークフローのナビゲーション
- プレビュー・編集機能
- 進捗表示・ステータス管理
- 設定管理

---

## 2. 画面構成

### 2.1 画面一覧

| 画面 | 説明 |
|------|------|
| HomeView | ホーム画面（URL入力） |
| ProcessingView | 処理中画面（進捗表示） |
| EditorView | 編集画面（メイン） |
| PreviewView | プレビュー画面 |
| ExportView | 出力設定画面 |
| SettingsView | 設定画面 |

### 2.2 画面遷移

```
┌──────────────┐
│   HomeView   │  URL入力
└──────┬───────┘
       │ 処理開始
       ▼
┌──────────────┐
│ProcessingView│  ダウンロード → 文字起こし → AI分析
└──────┬───────┘
       │ 完了
       ▼
┌──────────────┐
│  EditorView  │  切り抜き編集・字幕編集・チャプター編集
└──────┬───────┘
       │ プレビュー
       ▼
┌──────────────┐
│ PreviewView  │  動画プレビュー
└──────┬───────┘
       │ 戻る
       ▼
┌──────────────┐
│  EditorView  │
└──────┬───────┘
       │ 書き出し
       ▼
┌──────────────┐
│  ExportView  │  出力設定・書き出し実行
└──────────────┘
```

---

## 3. 各画面の詳細設計

### 3.1 HomeView（ホーム画面）

```
┌─────────────────────────────────────────────────────────────┐
│  YouTube Auto Clip Translator                          [⚙]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                      🎬                                     │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ YouTube URL を入力してください                       │   │
│   │ https://www.youtube.com/watch?v=...                 │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│                    [  処理を開始  ]                         │
│                                                             │
│   ─────────────────────────────────────────────────────     │
│                                                             │
│   最近のプロジェクト                                        │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ 📁 動画タイトル1         2024/01/15  [開く]         │   │
│   │ 📁 動画タイトル2         2024/01/14  [開く]         │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### コンポーネント
| コンポーネント | 種類 | 機能 |
|---------------|------|------|
| url_entry | CTkEntry | URL入力 |
| start_button | CTkButton | 処理開始 |
| recent_list | CTkScrollableFrame | 最近のプロジェクト |
| settings_button | CTkButton | 設定画面へ |

---

### 3.2 ProcessingView（処理中画面）

```
┌─────────────────────────────────────────────────────────────┐
│  処理中...                                            [×]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   動画タイトル: Amazing Video Title                         │
│   URL: https://www.youtube.com/watch?v=XXXXX               │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ ████████████████████░░░░░░░░░░░░░░░░░░░  45%        │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   現在の処理: 文字起こし中...                               │
│                                                             │
│   ─────────────────────────────────────────────────────     │
│                                                             │
│   ✓ 動画ダウンロード完了         00:32                      │
│   ✓ 音声抽出完了                 00:05                      │
│   ○ 文字起こし中...              01:23                      │
│   ○ AI分析                       待機中                     │
│                                                             │
│                     [キャンセル]                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 処理ステップ
1. 動画ダウンロード
2. 音声抽出
3. 文字起こし
4. AI分析（見どころ・チャプター・タイトル）

---

### 3.3 EditorView（編集画面）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  エディター                                                    [保存] [⚙]  │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌───────────────────────────────────────┐ ┌───────────────────────────────┐ │
│ │                                       │ │  セグメント一覧              │ │
│ │                                       │ │  ┌─────────────────────────┐ │ │
│ │           動画プレビュー               │ │  │ ☑ Ch1: オープニング     │ │ │
│ │                                       │ │  │   0:00 - 1:30  ⭐85     │ │ │
│ │                                       │ │  ├─────────────────────────┤ │ │
│ │                                       │ │  │ ☑ Ch2: メイン解説       │ │ │
│ │              ▶ 00:00 / 10:00          │ │  │   2:00 - 5:00  ⭐92     │ │ │
│ └───────────────────────────────────────┘ │  ├─────────────────────────┤ │ │
│                                           │  │ ☐ Ch3: 補足説明        │ │ │
│ タイムライン                               │  │   5:30 - 7:00  ⭐45     │ │ │
│ ┌───────────────────────────────────────┐ │  └─────────────────────────┘ │ │
│ │ ╭──╮   ╭────╮  ╭─╮    ╭──────╮   ╭─╮ │ │                               │ │
│ │ │  │   │    │  │ │    │      │   │ │ │ │  [+ セグメント追加]           │ │
│ │ ╰──╯   ╰────╯  ╰─╯    ╰──────╯   ╰─╯ │ │                               │ │
│ │|Ch1|   | Ch2  |       | Ch3  |      │ │ ─────────────────────────────  │ │
│ │ ▼      ▼       ▼       ▼            │ │                               │ │
│ │ 0:00  1:30   2:00    5:00   5:30    │ │  選択中セグメント編集          │ │
│ └───────────────────────────────────────┘ │  タイトル: [Ch1: オープニング]│ │
│                                           │  開始: [0:00.00]  終了: [1:30]│ │
├───────────────────────────────────────────┴───────────────────────────────┤
│ 字幕一覧                                                                   │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ # │ 時間        │ 原文                    │ 訳文                       │ │
│ ├───┼────────────┼────────────────────────┼───────────────────────────┤ │
│ │ 1 │ 0:01-0:04  │ Hello everyone         │ 皆さんこんにちは            │ │
│ │ 2 │ 0:04-0:08  │ Welcome to my channel  │ チャンネルへようこそ         │ │
│ │ 3 │ 0:08-0:12  │ Today we will discuss  │ 今日は...について話します    │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────┤
│                           [プレビュー]  [書き出し]                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### コンポーネント詳細

##### 動画プレビューエリア
- 動画の埋め込み表示
- 再生/一時停止コントロール
- シークバー
- 音量調整

##### タイムラインエリア
- 波形表示
- セグメント範囲表示（ドラッグで調整可能）
- チャプターマーカー
- 現在位置インジケーター
- ズーム機能

##### セグメント一覧
- チェックボックスで選択/非選択
- 見どころスコア表示
- ドラッグで順序変更
- 編集・削除ボタン

##### 字幕一覧
- 原文・訳文の並列表示
- インライン編集
- タイミング調整
- 一括編集機能

---

### 3.4 PreviewView（プレビュー画面）

```
┌─────────────────────────────────────────────────────────────┐
│  プレビュー                                          [×]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                                                     │   │
│   │                                                     │   │
│   │                  動画プレビュー                      │   │
│   │              （字幕焼き付け済み）                    │   │
│   │                                                     │   │
│   │                                                     │   │
│   │              ▶ 00:00 / 03:30                        │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   出力形式:  ○ 通常動画 (16:9)   ○ Shorts (9:16)           │
│                                                             │
│               [エディターに戻る]  [書き出し]                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### 3.5 ExportView（出力設定画面）

```
┌─────────────────────────────────────────────────────────────┐
│  書き出し設定                                         [×]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   出力形式                                                  │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ ☑ 通常動画 (16:9)                                   │   │
│   │ ☑ YouTube Shorts (9:16)                             │   │
│   │ ☐ 両方を1つの動画に結合                              │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   品質設定                                                  │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ プリセット: [▼ Balanced (推奨)              ]       │   │
│   │ 解像度:     [▼ 1920x1080 (元動画と同じ)     ]       │   │
│   │ 字幕:       ☑ 動画に焼き付け                        │   │
│   │ タイトル:   ☑ タイトルカードを挿入                   │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   出力先                                                    │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ /Users/xxx/Videos/output          [フォルダを選択]   │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   ファイル名: video_title_{format}_{date}                   │
│                                                             │
│   推定サイズ: 約 150 MB (通常) + 50 MB (Shorts)             │
│   推定時間:   約 2 分                                       │
│                                                             │
│                    [キャンセル]  [書き出し開始]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### 3.6 SettingsView（設定画面）

```
┌─────────────────────────────────────────────────────────────┐
│  設定                                                 [×]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   一般設定                                                  │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ テーマ:        [▼ ダーク              ]             │   │
│   │ 言語:          [▼ 日本語              ]             │   │
│   │ 作業ディレクトリ: /Users/xxx/Documents   [変更]     │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   API設定                                                   │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ Gemini API Key: [••••••••••••••••••••] [表示] [検証]│   │
│   │ ステータス: ✓ 有効                                  │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   処理設定                                                  │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ WhisperXモデル:  [▼ distil-large-v3    ]            │   │
│   │ デバイス:        [▼ 自動検出 (GPU)     ]            │   │
│   │ 話者分離:        ☐ 有効化                           │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   字幕設定                                                  │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ フォント:        [▼ Noto Sans JP       ]            │   │
│   │ フォントサイズ:  [48] px                            │   │
│   │ 二言語表示:      ☑ 有効                             │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│                              [保存]  [キャンセル]            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. コンポーネント設計

### 4.1 共通コンポーネント

```
src/gui/components/
├── video_player.py       # 動画プレーヤー
├── timeline.py           # タイムライン
├── waveform.py           # 波形表示
├── segment_list.py       # セグメント一覧
├── subtitle_table.py     # 字幕テーブル
├── progress_bar.py       # 進捗バー
└── toast.py              # 通知トースト
```

### 4.2 VideoPlayer コンポーネント（mpv埋め込み）

**決定事項**: mpvを使用したリアルタイム音声再生・字幕表示

```python
import mpv

class VideoPlayer(CTkFrame):
    """
    動画プレーヤーコンポーネント（mpv埋め込み）

    機能:
    - 動画の再生/一時停止（音声付き）
    - リアルタイム字幕表示（ASSファイル対応）
    - シーク
    - 音量調整
    - 現在時間表示
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        # mpvプレーヤーをウィンドウに埋め込み
        self.player = mpv.MPV(
            wid=str(int(self.winfo_id())),  # CustomTkinterウィンドウに埋め込み
            vo="gpu",                        # GPUレンダリング
            hwdec="auto",                    # ハードウェアデコード
            keep_open=True,                  # 終了時も開いたまま
        )

    def load(self, video_path: Path, subtitle_path: Path = None) -> None:
        """動画をロード"""
        self.player.play(str(video_path))
        if subtitle_path:
            self.player.sub_file = str(subtitle_path)

    def update_subtitle(self, subtitle_path: Path) -> None:
        """
        字幕ファイルを更新（編集時のリアルタイム反映）

        字幕編集 → 一時ASSファイル生成 → この関数で反映
        """
        self.player.sub_file = str(subtitle_path)
        self.player.command("sub-reload")

    def play(self) -> None:
        """再生"""
        self.player.pause = False

    def pause(self) -> None:
        """一時停止"""
        self.player.pause = True

    def seek(self, time: float) -> None:
        """指定時間にシーク"""
        self.player.seek(time, "absolute")

    def get_current_time(self) -> float:
        """現在の再生時間を取得"""
        return self.player.time_pos or 0.0

    def set_volume(self, volume: float) -> None:
        """音量設定（0.0-1.0）"""
        self.player.volume = volume * 100

    def on_time_update(self, callback: Callable[[float], None]) -> None:
        """時間更新コールバック登録"""
        @self.player.property_observer("time-pos")
        def on_time_pos(_name, value):
            if value is not None:
                callback(value)

    def destroy(self) -> None:
        """クリーンアップ"""
        self.player.terminate()
        super().destroy()
```

### 字幕リアルタイム更新フロー

```
字幕編集（GUIで変更）
    ↓
一時ASSファイルを生成（即座に）
    ↓
VideoPlayer.update_subtitle(temp_ass_path)
    ↓
mpvが字幕を再読み込み
    ↓
プレビューに即座に反映
```

### 4.3 Timeline コンポーネント

```python
class Timeline(CTkFrame):
    """
    タイムラインコンポーネント

    機能:
    - 波形表示
    - セグメント範囲表示/編集
    - ズーム/スクロール
    - マーカー表示
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

    def set_waveform(self, waveform_data: np.ndarray, sample_rate: int) -> None:
        """波形データを設定"""

    def set_segments(self, segments: List[EditSegment]) -> None:
        """セグメントを設定"""

    def set_current_time(self, time: float) -> None:
        """現在時間を設定"""

    def zoom(self, level: float) -> None:
        """ズームレベル設定"""

    def on_segment_change(self, callback: Callable[[EditSegment], None]) -> None:
        """セグメント変更コールバック"""

    def on_seek(self, callback: Callable[[float], None]) -> None:
        """シークコールバック"""
```

### 4.4 SubtitleTable コンポーネント

```python
class SubtitleTable(CTkScrollableFrame):
    """
    字幕テーブルコンポーネント

    機能:
    - 字幕一覧表示
    - インライン編集
    - 選択/ハイライト
    - ソート/フィルター
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

    def set_subtitles(self, subtitles: List[SubtitleEntry]) -> None:
        """字幕データを設定"""

    def get_subtitles(self) -> List[SubtitleEntry]:
        """編集済み字幕を取得"""

    def highlight_row(self, index: int) -> None:
        """行をハイライト"""

    def on_edit(self, callback: Callable[[int, SubtitleEntry], None]) -> None:
        """編集コールバック"""

    def on_select(self, callback: Callable[[int], None]) -> None:
        """選択コールバック"""
```

---

## 5. 状態管理

### 5.1 アプリケーション状態

```python
@dataclass
class AppState:
    # 現在のビュー
    current_view: str = "home"

    # プロジェクト
    project: Optional[Project] = None
    is_modified: bool = False

    # 処理状態
    is_processing: bool = False
    processing_step: str = ""
    processing_progress: float = 0.0

    # 編集状態
    selected_segment_id: Optional[int] = None
    selected_subtitle_id: Optional[int] = None
    current_time: float = 0.0

    # 設定
    settings: AppSettings = field(default_factory=AppSettings)
```

### 5.2 状態管理クラス

```python
class StateManager:
    """
    アプリケーション状態の管理

    - 状態の更新
    - 変更通知（Observer パターン）
    - 永続化
    """

    def __init__(self):
        self._state = AppState()
        self._observers: List[Callable] = []

    def get_state(self) -> AppState:
        """現在の状態を取得"""

    def update(self, **kwargs) -> None:
        """状態を更新"""

    def subscribe(self, callback: Callable[[AppState], None]) -> None:
        """変更通知を購読"""

    def unsubscribe(self, callback: Callable) -> None:
        """購読解除"""

    def save(self) -> None:
        """状態を永続化"""

    def load(self) -> None:
        """状態を復元"""
```

---

## 6. テーマ・スタイリング

### 6.1 カラースキーム

```python
THEMES = {
    "dark": {
        "bg_primary": "#1a1a2e",
        "bg_secondary": "#16213e",
        "bg_tertiary": "#0f3460",
        "text_primary": "#ffffff",
        "text_secondary": "#a0a0a0",
        "accent": "#e94560",
        "success": "#4ade80",
        "warning": "#fbbf24",
        "error": "#ef4444",
    },
    "light": {
        "bg_primary": "#ffffff",
        "bg_secondary": "#f3f4f6",
        "bg_tertiary": "#e5e7eb",
        "text_primary": "#1f2937",
        "text_secondary": "#6b7280",
        "accent": "#3b82f6",
        "success": "#22c55e",
        "warning": "#f59e0b",
        "error": "#ef4444",
    }
}
```

### 6.2 フォント設定

```python
FONTS = {
    "heading": ("Noto Sans JP", 24, "bold"),
    "subheading": ("Noto Sans JP", 18, "bold"),
    "body": ("Noto Sans JP", 14, "normal"),
    "small": ("Noto Sans JP", 12, "normal"),
    "mono": ("Noto Sans Mono", 14, "normal"),
}
```

---

## 7. 依存関係

### Python パッケージ
```
customtkinter>=5.2.0
pillow>=10.0.0
python-mpv>=1.0.0     # 動画プレビュー（mpv埋め込み）
numpy>=1.24.0
librosa>=0.10.0       # 波形表示
```

### 外部ツール（自動インストール対象）
```
mpv                   # 動画プレーヤー
```

---

## 7.5 自動保存と確認ダイアログ

### プロジェクト自動保存

**決定事項**: 30秒ごとに自動保存 + 手動保存

```python
AUTO_SAVE_CONFIG = {
    "interval_seconds": 30,
    "save_path": "~/.youtube-auto-clip-translator/autosave/",
    "max_autosaves": 5,  # 古いものは削除
}

class AutoSaveManager:
    def __init__(self, state_manager: StateManager):
        self.timer = None
        self.start_auto_save()

    def start_auto_save(self):
        """自動保存タイマー開始"""
        self.timer = threading.Timer(
            AUTO_SAVE_CONFIG["interval_seconds"],
            self._save_and_reschedule
        )
        self.timer.start()

    def _save_and_reschedule(self):
        self._save_draft()
        self.start_auto_save()  # 次のタイマーをセット

    def _save_draft(self):
        """ドラフト保存"""
        ...
```

### 処理中の確認ダイアログ

**決定事項**: 処理中はアプリを閉じれないように確認ダイアログを表示

```python
class App(CTk):
    def __init__(self):
        super().__init__()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        """閉じるボタン押下時"""
        if self.state_manager.get_state().is_processing:
            # 処理中の場合
            result = self._show_close_dialog()
            if result == "cancel":
                return  # 閉じない
            elif result == "force_close":
                self._cancel_processing()
                self.destroy()
        else:
            # 処理中でない場合
            if self.state_manager.get_state().is_modified:
                result = self._show_save_dialog()
                if result == "save":
                    self._save_project()
                elif result == "cancel":
                    return
            self.destroy()

    def _show_close_dialog(self) -> str:
        """処理中の確認ダイアログ"""
        dialog = CTkMessagebox(
            title="処理中です",
            message="処理中です。終了すると進行中の処理は破棄されます。\n終了しますか？",
            options=["キャンセル", "終了"]
        )
        return dialog.get()
```

```
┌─────────────────────────────────────────────────────────┐
│ 処理中です                                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ 処理中です。終了すると進行中の処理は破棄されます。       │
│ 終了しますか？                                          │
│                                                         │
│                    [キャンセル]  [終了]                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 8. ファイル構成

```
src/gui/
├── __init__.py
├── app.py              # メインアプリケーション
├── views/
│   ├── __init__.py
│   ├── home.py         # HomeView
│   ├── processing.py   # ProcessingView
│   ├── editor.py       # EditorView
│   ├── preview.py      # PreviewView
│   ├── export.py       # ExportView
│   └── settings.py     # SettingsView
├── components/
│   ├── __init__.py
│   ├── video_player.py
│   ├── timeline.py
│   ├── waveform.py
│   ├── segment_list.py
│   ├── subtitle_table.py
│   ├── progress_bar.py
│   └── toast.py
├── state/
│   ├── __init__.py
│   ├── app_state.py
│   └── state_manager.py
├── theme/
│   ├── __init__.py
│   ├── colors.py
│   └── fonts.py
└── utils/
    ├── __init__.py
    └── async_utils.py  # 非同期処理ヘルパー
```

---

## 9. 非同期処理

### 9.1 バックグラウンド処理

```python
class AsyncWorker:
    """
    バックグラウンドでタスクを実行

    GUIをブロックせずに重い処理を実行
    """

    def __init__(self, app: CTk):
        self.app = app
        self._executor = ThreadPoolExecutor(max_workers=4)

    def run(
        self,
        task: Callable,
        on_complete: Callable = None,
        on_error: Callable = None,
        on_progress: Callable = None
    ) -> None:
        """タスクをバックグラウンドで実行"""

    def cancel(self) -> None:
        """実行中のタスクをキャンセル"""
```

### 9.2 進捗更新

```python
def update_progress_from_thread(
    app: CTk,
    progress_bar: CTkProgressBar,
    value: float
) -> None:
    """
    別スレッドからGUIを安全に更新
    """
    app.after(0, lambda: progress_bar.set(value))
```

---

## 10. キーボードショートカット

| ショートカット | 機能 |
|--------------|------|
| Space | 再生/一時停止 |
| ← / → | 5秒戻る/進む |
| Shift + ← / → | 1秒戻る/進む |
| Ctrl + S | プロジェクト保存 |
| Ctrl + Z | 元に戻す |
| Ctrl + Shift + Z | やり直し |
| Ctrl + E | 書き出し |
| Delete | 選択セグメント削除 |
| Escape | 選択解除 |

---

## 11. インターフェース定義

### App クラス

```python
class App(CTk):
    def __init__(self):
        super().__init__()
        self.state_manager = StateManager()
        self.worker = AsyncWorker(self)

    def navigate_to(self, view_name: str) -> None:
        """ビューを切り替え"""

    def show_toast(self, message: str, type: str = "info") -> None:
        """トースト通知を表示"""

    def show_dialog(
        self,
        title: str,
        message: str,
        buttons: List[str]
    ) -> str:
        """ダイアログを表示"""

    def start_processing(self, url: str) -> None:
        """処理を開始"""

    def cancel_processing(self) -> None:
        """処理をキャンセル"""
```

---

## 12. テスト項目

### UIテスト
- [ ] 各画面の表示
- [ ] 画面遷移
- [ ] ボタン操作
- [ ] キーボードショートカット
- [ ] レスポンシブ対応

### 統合テスト
- [ ] URL入力から完了までの一連のフロー
- [ ] 編集操作
- [ ] 書き出し処理
- [ ] エラーハンドリング
