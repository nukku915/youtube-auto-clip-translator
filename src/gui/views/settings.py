"""
設定ビュー
==========

アプリケーションの設定画面。
"""

import subprocess
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ..theme import COLORS, SPACING, NaniTheme
from ..widgets import (
    NaniButton,
    NaniEntry,
    NaniLabel,
    NaniCard,
    NaniSwitch,
    NaniProgressBar,
    NaniTag,
    create_section_header,
)
from .base import BaseView

if TYPE_CHECKING:
    from ..app import App


# 利用可能なモデル一覧
AVAILABLE_MODELS = [
    {"name": "qwen3:8b", "size": "5.2 GB", "description": "高速・軽量（推奨）"},
    {"name": "gemma3:12b", "size": "8.1 GB", "description": "高品質"},
    {"name": "qwen3:14b", "size": "9.0 GB", "description": "より高品質"},
    {"name": "llama3.1:8b", "size": "4.7 GB", "description": "汎用"},
]


class SettingsView(BaseView):
    """設定ビュー."""

    def __init__(self, master, app: "App", **kwargs) -> None:
        self._model_widgets: dict = {}
        self._installing_model: Optional[str] = None
        super().__init__(master, app, **kwargs)

    def _setup_ui(self) -> None:
        """UIを構築."""
        # スクロール可能なコンテナ
        self._scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        self._scroll_frame.pack(fill="both", expand=True, padx=SPACING.XL, pady=SPACING.XL)

        # ヘッダー
        header_frame = ctk.CTkFrame(self._scroll_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, SPACING.XL))

        back_button = NaniButton(
            header_frame,
            text="← 戻る",
            variant="ghost",
            command=self._on_back_clicked,
        )
        back_button.pack(side="left")

        title_label = NaniLabel(
            header_frame,
            text="設定",
            variant="title",
        )
        title_label.pack(side="left", padx=SPACING.MD)

        # === Ollamaステータス ===
        ollama_section = create_section_header(
            self._scroll_frame,
            title="Ollama モデル管理",
            description="翻訳に使用するAIモデルのインストール状況",
        )
        ollama_section.pack(fill="x", pady=(0, SPACING.MD), anchor="w")

        ollama_card = NaniCard(self._scroll_frame)
        ollama_card.pack(fill="x", pady=(0, SPACING.XL))

        ollama_content = ctk.CTkFrame(ollama_card, fg_color="transparent")
        ollama_content.pack(padx=SPACING.XL, pady=SPACING.XL, fill="x")

        # Ollamaステータス行
        status_frame = ctk.CTkFrame(ollama_content, fg_color="transparent")
        status_frame.pack(fill="x", pady=(0, SPACING.MD))

        status_label = NaniLabel(
            status_frame,
            text="Ollamaステータス:",
            variant="secondary",
        )
        status_label.pack(side="left")

        self._ollama_status_tag = NaniTag(
            status_frame,
            text="確認中...",
            variant="default",
        )
        self._ollama_status_tag.pack(side="left", padx=SPACING.SM)

        refresh_button = NaniButton(
            status_frame,
            text="更新",
            variant="ghost",
            size="sm",
            command=self._refresh_ollama_status,
        )
        refresh_button.pack(side="right")

        # 区切り線
        separator = ctk.CTkFrame(ollama_content, height=1, fg_color=COLORS.BORDER_LIGHT)
        separator.pack(fill="x", pady=SPACING.MD)

        # モデル一覧
        models_label = NaniLabel(
            ollama_content,
            text="利用可能なモデル",
            variant="default",
        )
        models_label.pack(anchor="w", pady=(0, SPACING.SM))

        self._models_frame = ctk.CTkFrame(ollama_content, fg_color="transparent")
        self._models_frame.pack(fill="x")

        # モデル行を作成
        for model_info in AVAILABLE_MODELS:
            self._create_model_row(model_info)

        # インストール進捗
        self._progress_frame = ctk.CTkFrame(ollama_content, fg_color="transparent")
        self._progress_frame.pack(fill="x", pady=(SPACING.MD, 0))

        self._progress_label = NaniLabel(
            self._progress_frame,
            text="",
            variant="muted",
        )
        self._progress_label.pack(anchor="w")

        self._progress_bar = NaniProgressBar(self._progress_frame, width=400)
        self._progress_bar.pack(anchor="w", pady=(SPACING.XS, 0))
        self._progress_bar.set(0)
        self._progress_frame.pack_forget()  # 初期は非表示

        # === LLM設定 ===
        llm_section = create_section_header(
            self._scroll_frame,
            title="LLM設定",
            description="翻訳に使用するモデルの選択",
        )
        llm_section.pack(fill="x", pady=(0, SPACING.MD), anchor="w")

        llm_card = NaniCard(self._scroll_frame)
        llm_card.pack(fill="x", pady=(0, SPACING.XL))

        llm_content = ctk.CTkFrame(llm_card, fg_color="transparent")
        llm_content.pack(padx=SPACING.XL, pady=SPACING.XL, fill="x")

        # Ollamaホスト
        ollama_host_frame = ctk.CTkFrame(llm_content, fg_color="transparent")
        ollama_host_frame.pack(fill="x", pady=(0, SPACING.MD))

        ollama_host_label = NaniLabel(
            ollama_host_frame,
            text="Ollama ホスト:",
            variant="secondary",
        )
        ollama_host_label.pack(side="left")

        self._ollama_host_entry = NaniEntry(
            ollama_host_frame,
            placeholder_text="http://localhost:11434",
            width=300,
        )
        self._ollama_host_entry.pack(side="right")
        self._ollama_host_entry.insert(0, "http://localhost:11434")

        # 使用するモデル
        ollama_model_frame = ctk.CTkFrame(llm_content, fg_color="transparent")
        ollama_model_frame.pack(fill="x", pady=(0, SPACING.MD))

        ollama_model_label = NaniLabel(
            ollama_model_frame,
            text="使用するモデル:",
            variant="secondary",
        )
        ollama_model_label.pack(side="left")

        self._ollama_model_var = ctk.StringVar(value="qwen3:8b")
        self._ollama_model_menu = ctk.CTkOptionMenu(
            ollama_model_frame,
            values=["qwen3:8b"],  # 初期値、後で更新
            variable=self._ollama_model_var,
            width=200,
            fg_color=COLORS.BG_SECONDARY,
            button_color=COLORS.BG_HOVER,
            dropdown_fg_color=COLORS.BG_MAIN,
            font=NaniTheme.get_font("base"),
        )
        self._ollama_model_menu.pack(side="right")

        # Gemini APIキー
        gemini_frame = ctk.CTkFrame(llm_content, fg_color="transparent")
        gemini_frame.pack(fill="x", pady=(0, SPACING.MD))

        gemini_label = NaniLabel(
            gemini_frame,
            text="Gemini API Key (オプション):",
            variant="secondary",
        )
        gemini_label.pack(side="left")

        self._gemini_key_entry = NaniEntry(
            gemini_frame,
            placeholder_text="AIzaSy...",
            width=300,
        )
        self._gemini_key_entry.pack(side="right")

        # Geminiフォールバック
        fallback_frame = ctk.CTkFrame(llm_content, fg_color="transparent")
        fallback_frame.pack(fill="x", pady=(0, SPACING.SM))

        self._fallback_switch = NaniSwitch(
            fallback_frame,
            text="Ollama失敗時にGeminiにフォールバック",
        )
        self._fallback_switch.pack(side="left")

        # === 文字起こし設定 ===
        transcription_section = create_section_header(
            self._scroll_frame,
            title="文字起こし設定",
            description="WhisperXの設定",
        )
        transcription_section.pack(fill="x", pady=(0, SPACING.MD), anchor="w")

        transcription_card = NaniCard(self._scroll_frame)
        transcription_card.pack(fill="x", pady=(0, SPACING.XL))

        transcription_content = ctk.CTkFrame(transcription_card, fg_color="transparent")
        transcription_content.pack(padx=SPACING.XL, pady=SPACING.XL, fill="x")

        # モデル選択
        model_frame = ctk.CTkFrame(transcription_content, fg_color="transparent")
        model_frame.pack(fill="x", pady=(0, SPACING.MD))

        model_label = NaniLabel(
            model_frame,
            text="WhisperXモデル:",
            variant="secondary",
        )
        model_label.pack(side="left")

        self._whisper_model_var = ctk.StringVar(value="large-v3")
        whisper_model_menu = ctk.CTkOptionMenu(
            model_frame,
            values=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
            variable=self._whisper_model_var,
            width=200,
            fg_color=COLORS.BG_SECONDARY,
            button_color=COLORS.BG_HOVER,
            dropdown_fg_color=COLORS.BG_MAIN,
            font=NaniTheme.get_font("base"),
        )
        whisper_model_menu.pack(side="right")

        # デバイス選択
        device_frame = ctk.CTkFrame(transcription_content, fg_color="transparent")
        device_frame.pack(fill="x", pady=(0, SPACING.MD))

        device_label = NaniLabel(
            device_frame,
            text="デバイス:",
            variant="secondary",
        )
        device_label.pack(side="left")

        self._device_var = ctk.StringVar(value="auto")
        device_menu = ctk.CTkOptionMenu(
            device_frame,
            values=["auto", "cuda", "mps", "cpu"],
            variable=self._device_var,
            width=200,
            fg_color=COLORS.BG_SECONDARY,
            button_color=COLORS.BG_HOVER,
            dropdown_fg_color=COLORS.BG_MAIN,
            font=NaniTheme.get_font("base"),
        )
        device_menu.pack(side="right")

        # === 出力設定 ===
        output_section = create_section_header(
            self._scroll_frame,
            title="出力設定",
            description="ファイルの保存先",
        )
        output_section.pack(fill="x", pady=(0, SPACING.MD), anchor="w")

        output_card = NaniCard(self._scroll_frame)
        output_card.pack(fill="x", pady=(0, SPACING.XL))

        output_content = ctk.CTkFrame(output_card, fg_color="transparent")
        output_content.pack(padx=SPACING.XL, pady=SPACING.XL, fill="x")

        # 出力ディレクトリ
        output_dir_frame = ctk.CTkFrame(output_content, fg_color="transparent")
        output_dir_frame.pack(fill="x", pady=(0, SPACING.MD))

        output_dir_label = NaniLabel(
            output_dir_frame,
            text="出力ディレクトリ:",
            variant="secondary",
        )
        output_dir_label.pack(side="left")

        output_dir_right = ctk.CTkFrame(output_dir_frame, fg_color="transparent")
        output_dir_right.pack(side="right")

        self._output_dir_entry = NaniEntry(
            output_dir_right,
            placeholder_text="./output",
            width=200,
        )
        self._output_dir_entry.pack(side="left", padx=(0, SPACING.SM))
        self._output_dir_entry.insert(0, "./output")

        browse_button = NaniButton(
            output_dir_right,
            text="参照",
            variant="secondary",
            size="sm",
            command=self._on_browse_clicked,
        )
        browse_button.pack(side="left")

        # === ボタン ===
        button_frame = ctk.CTkFrame(self._scroll_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=SPACING.XL)

        save_button = NaniButton(
            button_frame,
            text="設定を保存",
            variant="primary",
            command=self._on_save_clicked,
        )
        save_button.pack(side="right", padx=SPACING.SM)

        reset_button = NaniButton(
            button_frame,
            text="リセット",
            variant="secondary",
            command=self._on_reset_clicked,
        )
        reset_button.pack(side="right")

        # ステータスメッセージ
        self._status_label = NaniLabel(
            self._scroll_frame,
            text="",
            variant="muted",
        )
        self._status_label.pack(anchor="w")

    def _create_model_row(self, model_info: dict) -> None:
        """モデル行を作成."""
        model_name = model_info["name"]

        row_frame = ctk.CTkFrame(self._models_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=SPACING.XS)

        # モデル名
        name_label = NaniLabel(
            row_frame,
            text=model_name,
            variant="default",
        )
        name_label.pack(side="left")

        # サイズ
        size_label = NaniLabel(
            row_frame,
            text=f"({model_info['size']})",
            variant="muted",
        )
        size_label.pack(side="left", padx=(SPACING.XS, 0))

        # 説明
        desc_label = NaniLabel(
            row_frame,
            text=f"- {model_info['description']}",
            variant="muted",
        )
        desc_label.pack(side="left", padx=(SPACING.XS, 0))

        # ステータスタグ
        status_tag = NaniTag(
            row_frame,
            text="確認中",
            variant="default",
        )
        status_tag.pack(side="right", padx=(SPACING.SM, 0))

        # インストールボタン
        install_button = NaniButton(
            row_frame,
            text="インストール",
            variant="outline",
            size="sm",
            command=lambda m=model_name: self._install_model(m),
        )
        install_button.pack(side="right")
        install_button.pack_forget()  # 初期は非表示

        self._model_widgets[model_name] = {
            "row": row_frame,
            "status_tag": status_tag,
            "install_button": install_button,
        }

    def _refresh_ollama_status(self) -> None:
        """Ollamaステータスを更新."""
        self._ollama_status_tag.configure(text="確認中...", fg_color=COLORS.BG_SECONDARY)

        # バックグラウンドで確認
        thread = threading.Thread(target=self._check_ollama_status)
        thread.daemon = True
        thread.start()

    def _check_ollama_status(self) -> None:
        """Ollamaステータスを確認（バックグラウンド）."""
        try:
            # Ollamaが起動しているか確認
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                # インストール済みモデルをパース
                installed_models = set()
                lines = result.stdout.strip().split("\n")
                for line in lines[1:]:  # ヘッダーをスキップ
                    if line.strip():
                        parts = line.split()
                        if parts:
                            installed_models.add(parts[0])

                # UIを更新
                self.after(0, lambda: self._update_ollama_ui(True, installed_models))
            else:
                self.after(0, lambda: self._update_ollama_ui(False, set()))

        except FileNotFoundError:
            self.after(0, lambda: self._update_ollama_ui(False, set(), "未インストール"))
        except subprocess.TimeoutExpired:
            self.after(0, lambda: self._update_ollama_ui(False, set(), "タイムアウト"))
        except Exception as e:
            self.after(0, lambda: self._update_ollama_ui(False, set(), str(e)))

    def _update_ollama_ui(
        self,
        is_running: bool,
        installed_models: set,
        error_msg: Optional[str] = None,
    ) -> None:
        """OllamaのUIを更新."""
        if error_msg:
            self._ollama_status_tag.configure(
                text=error_msg,
                fg_color=COLORS.DANGER_BG,
                text_color=COLORS.DANGER,
            )
        elif is_running:
            self._ollama_status_tag.configure(
                text="起動中",
                fg_color=COLORS.SUCCESS_BG,
                text_color=COLORS.SUCCESS,
            )
        else:
            self._ollama_status_tag.configure(
                text="停止中",
                fg_color=COLORS.WARNING_BG,
                text_color=COLORS.WARNING,
            )

        # 各モデルのステータスを更新
        available_models = []
        for model_info in AVAILABLE_MODELS:
            model_name = model_info["name"]
            widgets = self._model_widgets.get(model_name)
            if not widgets:
                continue

            if model_name in installed_models:
                widgets["status_tag"].configure(
                    text="インストール済",
                    fg_color=COLORS.SUCCESS_BG,
                    text_color=COLORS.SUCCESS,
                )
                widgets["install_button"].pack_forget()
                available_models.append(model_name)
            else:
                widgets["status_tag"].configure(
                    text="未インストール",
                    fg_color=COLORS.BG_SECONDARY,
                    text_color=COLORS.TEXT_MUTED,
                )
                if is_running and not self._installing_model:
                    widgets["install_button"].pack(side="right")
                else:
                    widgets["install_button"].pack_forget()

        # モデル選択メニューを更新
        if available_models:
            self._ollama_model_menu.configure(values=available_models)
            if self._ollama_model_var.get() not in available_models:
                self._ollama_model_var.set(available_models[0])

    def _install_model(self, model_name: str) -> None:
        """モデルをインストール."""
        if self._installing_model:
            return

        self._installing_model = model_name

        # UIを更新
        widgets = self._model_widgets.get(model_name)
        if widgets:
            widgets["status_tag"].configure(
                text="インストール中...",
                fg_color=COLORS.PRIMARY_BG,
                text_color=COLORS.PRIMARY,
            )
            widgets["install_button"].pack_forget()

        # 進捗表示
        self._progress_frame.pack(fill="x", pady=(SPACING.MD, 0))
        self._progress_label.configure(text=f"{model_name} をインストール中...")
        self._progress_bar.set(0)

        # 全モデルのインストールボタンを非表示
        for name, w in self._model_widgets.items():
            w["install_button"].pack_forget()

        # バックグラウンドでインストール
        thread = threading.Thread(target=self._run_model_install, args=(model_name,))
        thread.daemon = True
        thread.start()

        # 進捗アニメーション開始
        self._animate_progress()

    def _run_model_install(self, model_name: str) -> None:
        """モデルインストールを実行（バックグラウンド）."""
        try:
            result = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True,
                text=True,
                timeout=1800,  # 30分タイムアウト
            )

            success = result.returncode == 0
            self.after(0, lambda: self._on_install_complete(model_name, success))

        except Exception as e:
            self.after(0, lambda: self._on_install_complete(model_name, False, str(e)))

    def _animate_progress(self) -> None:
        """進捗バーをアニメーション."""
        if not self._installing_model:
            return

        current = self._progress_bar.get()
        # 90%まで徐々に進める
        if current < 0.9:
            self._progress_bar.set(current + 0.01)
            self.after(500, self._animate_progress)

    def _on_install_complete(
        self,
        model_name: str,
        success: bool,
        error_msg: Optional[str] = None,
    ) -> None:
        """インストール完了時."""
        self._installing_model = None
        self._progress_bar.set(1.0 if success else 0)

        if success:
            self._progress_label.configure(
                text=f"{model_name} のインストールが完了しました",
                text_color=COLORS.SUCCESS,
            )
        else:
            error_text = f"{model_name} のインストールに失敗しました"
            if error_msg:
                error_text += f": {error_msg}"
            self._progress_label.configure(
                text=error_text,
                text_color=COLORS.DANGER,
            )

        # 3秒後に進捗を非表示
        self.after(3000, lambda: self._progress_frame.pack_forget())

        # ステータスを再確認
        self.after(1000, self._refresh_ollama_status)

    def _on_back_clicked(self) -> None:
        """戻るボタンクリック時."""
        self.navigate_to("home")

    def _on_browse_clicked(self) -> None:
        """参照ボタンクリック時."""
        from tkinter import filedialog

        directory = filedialog.askdirectory(
            title="出力ディレクトリを選択",
            initialdir=self._output_dir_entry.get() or ".",
        )

        if directory:
            self._output_dir_entry.delete(0, "end")
            self._output_dir_entry.insert(0, directory)

    def _on_save_clicked(self) -> None:
        """保存ボタンクリック時."""
        self._status_label.configure(
            text="設定を保存しました",
            text_color=COLORS.SUCCESS,
        )
        self.after(3000, lambda: self._status_label.configure(text=""))

    def _on_reset_clicked(self) -> None:
        """リセットボタンクリック時."""
        self._ollama_host_entry.delete(0, "end")
        self._ollama_host_entry.insert(0, "http://localhost:11434")

        self._ollama_model_var.set("qwen3:8b")
        self._gemini_key_entry.delete(0, "end")
        self._fallback_switch.deselect()
        self._whisper_model_var.set("large-v3")
        self._device_var.set("auto")

        self._output_dir_entry.delete(0, "end")
        self._output_dir_entry.insert(0, "./output")

        self._status_label.configure(
            text="設定をリセットしました",
            text_color=COLORS.TEXT_SECONDARY,
        )
        self.after(3000, lambda: self._status_label.configure(text=""))

    def on_show(self, **kwargs) -> None:
        """ビュー表示時."""
        # Ollamaステータスを確認
        self._refresh_ollama_status()
