"""
ホームビュー
============

URL入力と処理開始を行うメイン画面。
"""

import re
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ..theme import COLORS, SPACING, NaniTheme
from ..widgets import (
    NaniButton,
    NaniEntry,
    NaniLabel,
    NaniCard,
    create_section_header,
)
from .base import BaseView

if TYPE_CHECKING:
    from ..app import App


class HomeView(BaseView):
    """ホームビュー."""

    # YouTube URLの正規表現パターン
    YOUTUBE_URL_PATTERN = re.compile(
        r"^(https?://)?(www\.)?"
        r"(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)"
        r"[\w-]+"
    )

    def _setup_ui(self) -> None:
        """UIを構築."""
        # グリッド設定
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 中央コンテナ
        center_container = ctk.CTkFrame(self, fg_color="transparent")
        center_container.grid(row=0, column=0)

        # タイトル
        title_label = NaniLabel(
            center_container,
            text="YouTube Auto Clip Translator",
            variant="title",
        )
        title_label.pack(pady=(0, SPACING.XL))

        # サブタイトル
        subtitle_label = NaniLabel(
            center_container,
            text="YouTube動画を翻訳して字幕を生成",
            variant="secondary",
        )
        subtitle_label.pack(pady=(0, SPACING.XXXL))

        # URL入力カード
        input_card = NaniCard(center_container, width=500)
        input_card.pack(pady=SPACING.MD)

        # カード内のコンテンツ
        card_content = ctk.CTkFrame(input_card, fg_color="transparent")
        card_content.pack(padx=SPACING.XL, pady=SPACING.XL, fill="both", expand=True)

        # URL入力ラベル
        url_label = NaniLabel(
            card_content,
            text="YouTube URL",
            variant="secondary",
        )
        url_label.pack(anchor="w", pady=(0, SPACING.XS))

        # URL入力フィールド
        self._url_entry = NaniEntry(
            card_content,
            placeholder_text="https://www.youtube.com/watch?v=...",
            width=450,
            height=44,
        )
        self._url_entry.pack(pady=(0, SPACING.MD))

        # URL入力時のバリデーション
        self._url_entry.bind("<KeyRelease>", self._on_url_change)

        # エラーメッセージ
        self._error_label = NaniLabel(
            card_content,
            text="",
            variant="muted",
        )
        self._error_label.configure(text_color=COLORS.DANGER)
        self._error_label.pack(anchor="w", pady=(0, SPACING.SM))

        # 言語選択
        lang_frame = ctk.CTkFrame(card_content, fg_color="transparent")
        lang_frame.pack(fill="x", pady=(0, SPACING.MD))

        lang_label = NaniLabel(
            lang_frame,
            text="翻訳先言語:",
            variant="secondary",
        )
        lang_label.pack(side="left")

        self._language_var = ctk.StringVar(value="ja")
        language_menu = ctk.CTkOptionMenu(
            lang_frame,
            values=["ja (日本語)", "en (English)", "zh (中文)", "ko (한국어)", "es (Español)"],
            variable=self._language_var,
            width=150,
            fg_color=COLORS.BG_SECONDARY,
            button_color=COLORS.BG_HOVER,
            button_hover_color=COLORS.BORDER_DARK,
            dropdown_fg_color=COLORS.BG_MAIN,
            dropdown_hover_color=COLORS.PRIMARY_BG,
            font=NaniTheme.get_font("base"),
        )
        language_menu.pack(side="left", padx=(SPACING.SM, 0))

        # 処理開始ボタン
        self._start_button = NaniButton(
            card_content,
            text="処理を開始",
            variant="primary",
            size="lg",
            width=200,
            command=self._on_start_clicked,
        )
        self._start_button.pack(pady=(SPACING.MD, 0))
        self._start_button.configure(state="disabled")

        # 最近のプロジェクトセクション
        self._history_frame = ctk.CTkFrame(center_container, fg_color="transparent")
        self._history_frame.pack(fill="x", pady=SPACING.XL)

        # 区切り線
        separator = ctk.CTkFrame(
            center_container,
            height=1,
            fg_color=COLORS.BORDER_LIGHT,
        )
        separator.pack(fill="x", pady=SPACING.MD)

        # 設定ボタン
        settings_button = NaniButton(
            center_container,
            text="設定",
            variant="ghost",
            command=self._on_settings_clicked,
        )
        settings_button.pack()

    def _on_url_change(self, event=None) -> None:
        """URL入力変更時."""
        url = self._url_entry.get().strip()

        if not url:
            self._error_label.configure(text="")
            self._start_button.configure(state="disabled")
            return

        if self._is_valid_youtube_url(url):
            self._error_label.configure(text="")
            self._start_button.configure(state="normal")
        else:
            self._error_label.configure(text="有効なYouTube URLを入力してください")
            self._start_button.configure(state="disabled")

    def _is_valid_youtube_url(self, url: str) -> bool:
        """YouTube URLが有効かどうかをチェック."""
        return bool(self.YOUTUBE_URL_PATTERN.match(url))

    def _get_target_language(self) -> str:
        """選択された言語コードを取得."""
        value = self._language_var.get()
        # "ja (日本語)" -> "ja"
        return value.split(" ")[0]

    def _on_start_clicked(self) -> None:
        """処理開始ボタンクリック時."""
        url = self._url_entry.get().strip()
        target_language = self._get_target_language()

        if not self._is_valid_youtube_url(url):
            return

        # 処理画面へ遷移
        self.navigate_to(
            "processing",
            url=url,
            target_language=target_language,
        )

    def _on_settings_clicked(self) -> None:
        """設定ボタンクリック時."""
        self.navigate_to("settings")

    def on_show(self, **kwargs) -> None:
        """ビュー表示時."""
        # URLフィールドをクリア
        self._url_entry.delete(0, "end")
        self._error_label.configure(text="")
        self._start_button.configure(state="disabled")

        # 履歴を更新
        self._refresh_history()

    def _refresh_history(self) -> None:
        """履歴を更新."""
        # 既存の履歴ウィジェットをクリア
        for widget in self._history_frame.winfo_children():
            widget.destroy()

        # 履歴を取得
        from src.core.project_history import ProjectHistory
        history = ProjectHistory()
        recent_projects = history.get_recent(5)

        if not recent_projects:
            return

        # ヘッダー
        header = NaniLabel(
            self._history_frame,
            text="最近のプロジェクト",
            variant="subtitle",
        )
        header.pack(anchor="w", pady=(0, SPACING.SM))

        # プロジェクト一覧
        for project in recent_projects:
            self._create_project_item(project)

    def _create_project_item(self, project) -> None:
        """プロジェクトアイテムを作成."""
        from pathlib import Path

        item_frame = ctk.CTkFrame(
            self._history_frame,
            fg_color=COLORS.BG_SECONDARY,
            corner_radius=8,
        )
        item_frame.pack(fill="x", pady=SPACING.XS)

        content = ctk.CTkFrame(item_frame, fg_color="transparent")
        content.pack(padx=SPACING.MD, pady=SPACING.SM, fill="x", expand=True)
        content.grid_columnconfigure(1, weight=1)

        # タイトル（クリック可能）
        title_text = project.video_title[:40] + "..." if len(project.video_title) > 40 else project.video_title
        title_btn = ctk.CTkButton(
            content,
            text=title_text,
            font=NaniTheme.get_font("base"),
            fg_color="transparent",
            hover_color=COLORS.BG_HOVER,
            text_color=COLORS.TEXT_PRIMARY,
            anchor="w",
            command=lambda p=project: self._on_project_clicked(p),
        )
        title_btn.grid(row=0, column=0, columnspan=2, sticky="w")

        # 日時
        from datetime import datetime
        try:
            created = datetime.fromisoformat(project.created_at)
            date_str = created.strftime("%Y/%m/%d %H:%M")
        except Exception:
            date_str = ""

        date_label = NaniLabel(
            content,
            text=date_str,
            variant="caption",
        )
        date_label.grid(row=1, column=0, sticky="w")

        # 編集ボタン
        edit_btn = NaniButton(
            content,
            text="編集",
            variant="ghost",
            size="sm",
            width=60,
            command=lambda p=project: self._on_edit_project(p),
        )
        edit_btn.grid(row=0, column=2, rowspan=2, padx=(SPACING.SM, 0))

    def _on_project_clicked(self, project) -> None:
        """プロジェクトクリック時."""
        from pathlib import Path

        # 結果画面へ遷移
        self.navigate_to(
            "result",
            video_title=project.video_title,
            video_id=project.video_id,
            subtitle_path=Path(project.subtitle_path),
            srt_path=Path(project.srt_path),
            output_dir=Path(project.output_dir),
        )

    def _on_edit_project(self, project) -> None:
        """プロジェクト編集クリック時."""
        from pathlib import Path

        # 編集画面へ遷移
        self.navigate_to(
            "editor",
            subtitle_path=Path(project.subtitle_path),
            video_title=project.video_title,
        )
