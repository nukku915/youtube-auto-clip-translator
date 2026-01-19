"""
結果表示ビュー
==============

処理完了後の結果を表示する画面。
"""

import subprocess
import platform
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ..theme import COLORS, SPACING
from ..widgets import (
    NaniButton,
    NaniLabel,
    NaniCard,
)
from .base import BaseView

if TYPE_CHECKING:
    from ..app import App


class ResultView(BaseView):
    """結果表示ビュー."""

    def __init__(self, master, app: "App", **kwargs) -> None:
        self._video_title: str = ""
        self._video_id: str = ""
        self._subtitle_path: Optional[Path] = None
        self._srt_path: Optional[Path] = None
        self._output_dir: Optional[Path] = None
        super().__init__(master, app, **kwargs)

    def _setup_ui(self) -> None:
        """UIを構築."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 中央コンテナ
        center_container = ctk.CTkFrame(self, fg_color="transparent")
        center_container.grid(row=0, column=0)

        # 成功アイコン
        success_icon = ctk.CTkLabel(
            center_container,
            text="✓",
            font=ctk.CTkFont(size=48, weight="bold"),
            text_color=COLORS.SUCCESS,
        )
        success_icon.pack(pady=(0, SPACING.MD))

        # タイトル
        self._title_label = NaniLabel(
            center_container,
            text="処理完了!",
            variant="title",
        )
        self._title_label.pack(pady=(0, SPACING.SM))

        # 動画タイトル
        self._video_title_label = NaniLabel(
            center_container,
            text="",
            variant="secondary",
        )
        self._video_title_label.pack(pady=(0, SPACING.XL))

        # 結果カード
        result_card = NaniCard(center_container, width=500)
        result_card.pack(pady=SPACING.MD)

        card_content = ctk.CTkFrame(result_card, fg_color="transparent")
        card_content.pack(padx=SPACING.XL, pady=SPACING.XL, fill="both", expand=True)

        # 生成されたファイル
        files_label = NaniLabel(
            card_content,
            text="生成されたファイル",
            variant="subtitle",
        )
        files_label.pack(anchor="w", pady=(0, SPACING.MD))

        # ファイルリスト
        self._files_frame = ctk.CTkFrame(card_content, fg_color="transparent")
        self._files_frame.pack(fill="x", pady=(0, SPACING.LG))

        # ASS ファイル
        self._ass_row = self._create_file_row(
            self._files_frame,
            "ASS形式",
            "スタイル付き字幕",
        )
        self._ass_row.pack(fill="x", pady=SPACING.XS)

        # SRT ファイル
        self._srt_row = self._create_file_row(
            self._files_frame,
            "SRT形式",
            "汎用字幕形式",
        )
        self._srt_row.pack(fill="x", pady=SPACING.XS)

        # アクションボタン
        actions_frame = ctk.CTkFrame(card_content, fg_color="transparent")
        actions_frame.pack(fill="x", pady=(SPACING.MD, 0))

        # フォルダを開くボタン
        open_folder_btn = NaniButton(
            actions_frame,
            text="📁 フォルダを開く",
            variant="secondary",
            command=self._on_open_folder,
        )
        open_folder_btn.pack(side="left", padx=(0, SPACING.SM))

        # 編集ボタン
        edit_btn = NaniButton(
            actions_frame,
            text="✏️ 字幕を編集",
            variant="primary",
            command=self._on_edit_clicked,
        )
        edit_btn.pack(side="left", padx=SPACING.SM)

        # 下部ボタン
        bottom_frame = ctk.CTkFrame(center_container, fg_color="transparent")
        bottom_frame.pack(pady=SPACING.XL)

        # 新規処理ボタン
        new_btn = NaniButton(
            bottom_frame,
            text="新しい動画を処理",
            variant="ghost",
            command=self._on_new_clicked,
        )
        new_btn.pack(side="left", padx=SPACING.SM)

    def _create_file_row(
        self,
        parent,
        file_type: str,
        description: str,
    ) -> ctk.CTkFrame:
        """ファイル行を作成."""
        row = ctk.CTkFrame(parent, fg_color=COLORS.BG_SECONDARY, corner_radius=8)

        content = ctk.CTkFrame(row, fg_color="transparent")
        content.pack(padx=SPACING.MD, pady=SPACING.SM, fill="x", expand=True)

        # ファイルタイプ
        type_label = ctk.CTkLabel(
            content,
            text=file_type,
            font=ctk.CTkFont(weight="bold"),
            text_color=COLORS.TEXT_PRIMARY,
        )
        type_label.pack(anchor="w")

        # 説明
        desc_label = NaniLabel(
            content,
            text=description,
            variant="caption",
        )
        desc_label.pack(anchor="w")

        return row

    def on_show(self, **kwargs) -> None:
        """ビュー表示時."""
        self._video_title = kwargs.get("video_title", "")
        self._video_id = kwargs.get("video_id", "")
        self._subtitle_path = kwargs.get("subtitle_path")
        self._srt_path = kwargs.get("srt_path")
        self._output_dir = kwargs.get("output_dir")

        # UIを更新
        if self._video_title:
            self._video_title_label.configure(text=self._video_title)

    def _on_open_folder(self) -> None:
        """フォルダを開く."""
        if self._output_dir and self._output_dir.exists():
            if platform.system() == "Darwin":
                subprocess.run(["open", str(self._output_dir)])
            elif platform.system() == "Windows":
                subprocess.run(["explorer", str(self._output_dir)])
            else:
                subprocess.run(["xdg-open", str(self._output_dir)])

    def _on_edit_clicked(self) -> None:
        """編集ボタンクリック時."""
        self.navigate_to(
            "editor",
            subtitle_path=self._subtitle_path,
            video_title=self._video_title,
        )

    def _on_new_clicked(self) -> None:
        """新規処理ボタンクリック時."""
        self.navigate_to("home")
