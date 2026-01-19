"""
Nani-styled Widget Components
=============================

nani.now のデザインを反映したカスタムウィジェットコンポーネント。
CustomTkinterをベースに、一貫したスタイリングを提供。
"""

import customtkinter as ctk
from typing import Optional, Callable, Any, List, Tuple

from ..theme import NaniTheme, COLORS, SPACING, RADIUS
from ..animation import create_hover_effect, Animator

# 動画編集コンポーネント
from .video_player import VideoPlayer, SubtitleEntry
from .timeline import Timeline, TimelineSegment


class NaniButton(ctk.CTkButton):
    """
    Nani-styled ボタン

    使用例:
        button = NaniButton(
            parent,
            text="翻訳する",
            variant="primary",
            command=on_click
        )
    """

    def __init__(
        self,
        master: Any,
        text: str = "",
        variant: str = "primary",
        size: str = "default",
        command: Optional[Callable] = None,
        **kwargs,
    ):
        """
        Args:
            master: 親ウィジェット
            text: ボタンテキスト
            variant: "primary", "secondary", "outline", "ghost", "danger"
            size: "sm", "default", "lg"
            command: クリック時のコールバック
        """
        style = NaniTheme.get_button_style(variant)

        # サイズに応じたパディングとフォント
        size_config = {
            "sm": {"height": 28, "font": NaniTheme.get_font("sm")},
            "default": {"height": 36, "font": NaniTheme.get_font("base")},
            "lg": {"height": 44, "font": NaniTheme.get_font("md")},
        }
        config = size_config.get(size, size_config["default"])

        # border_colorがtransparentの場合は指定しない
        border_color = style.get("border_color")
        border_width = style.get("border_width", 0)

        init_kwargs = {
            "text": text,
            "command": command,
            "fg_color": style["fg_color"],
            "hover_color": style["hover_color"],
            "text_color": style["text_color"],
            "corner_radius": style["corner_radius"],
            "height": config["height"],
            "font": config["font"],
            "border_width": border_width,
        }

        # border_colorが有効な値の場合のみ追加
        if border_color and border_color != "transparent":
            init_kwargs["border_color"] = border_color

        super().__init__(master, **init_kwargs, **kwargs)


class NaniEntry(ctk.CTkEntry):
    """
    Nani-styled テキスト入力フィールド

    使用例:
        entry = NaniEntry(
            parent,
            placeholder_text="好きな言語で入力…",
            width=300
        )
    """

    def __init__(
        self,
        master: Any,
        placeholder_text: str = "",
        width: int = 200,
        height: int = 40,
        **kwargs,
    ):
        style = NaniTheme.get_input_style()

        super().__init__(
            master,
            placeholder_text=placeholder_text,
            width=width,
            height=height,
            fg_color=style["fg_color"],
            border_color=style["border_color"],
            text_color=style["text_color"],
            placeholder_text_color=style["placeholder_text_color"],
            corner_radius=style["corner_radius"],
            border_width=style["border_width"],
            font=NaniTheme.get_font("base"),
            **kwargs,
        )

        # フォーカス時のボーダー色変更
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_in(self, event):
        self.configure(border_color=COLORS.BORDER_FOCUS)

    def _on_focus_out(self, event):
        self.configure(border_color=COLORS.BORDER_DEFAULT)


class NaniTextbox(ctk.CTkTextbox):
    """
    Nani-styled テキストエリア

    使用例:
        textbox = NaniTextbox(
            parent,
            width=400,
            height=200
        )
    """

    def __init__(
        self,
        master: Any,
        width: int = 300,
        height: int = 150,
        **kwargs,
    ):
        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=COLORS.BG_MAIN,
            text_color=COLORS.TEXT_PRIMARY,
            border_color=COLORS.BORDER_DEFAULT,
            border_width=1,
            corner_radius=RADIUS.MD,
            font=NaniTheme.get_font("base"),
            **kwargs,
        )


class NaniLabel(ctk.CTkLabel):
    """
    Nani-styled ラベル

    使用例:
        label = NaniLabel(
            parent,
            text="翻訳結果",
            variant="heading"
        )
    """

    def __init__(
        self,
        master: Any,
        text: str = "",
        variant: str = "default",
        **kwargs,
    ):
        """
        Args:
            variant: "default", "secondary", "muted", "heading", "title"
        """
        style = NaniTheme.get_label_style(variant)

        super().__init__(
            master,
            text=text,
            text_color=style["text_color"],
            font=style["font"],
            **kwargs,
        )


class NaniCard(ctk.CTkFrame):
    """
    Nani-styled カードコンポーネント

    使用例:
        card = NaniCard(parent, padding=20)
        label = NaniLabel(card, text="カード内容")
        label.pack()
    """

    def __init__(
        self,
        master: Any,
        padding: int = 20,
        **kwargs,
    ):
        style = NaniTheme.get_card_style()

        super().__init__(
            master,
            fg_color=style["fg_color"],
            corner_radius=style["corner_radius"],
            border_width=style["border_width"],
            border_color=style["border_color"],
            **kwargs,
        )

        # 内部パディングをシミュレート
        self._padding = padding

    def pack(self, **kwargs):
        # パディングを考慮したpack
        super().pack(padx=kwargs.pop("padx", 0), pady=kwargs.pop("pady", 0), **kwargs)


class NaniProgressBar(ctk.CTkProgressBar):
    """
    Nani-styled プログレスバー

    使用例:
        progress = NaniProgressBar(parent)
        progress.set(0.5)  # 50%
    """

    def __init__(
        self,
        master: Any,
        width: int = 200,
        height: int = 8,
        **kwargs,
    ):
        style = NaniTheme.get_progress_style()

        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=style["fg_color"],
            progress_color=style["progress_color"],
            corner_radius=style["corner_radius"],
            **kwargs,
        )


class NaniSwitch(ctk.CTkSwitch):
    """
    Nani-styled スイッチ

    使用例:
        switch = NaniSwitch(
            parent,
            text="文体を調整",
            command=on_toggle
        )
    """

    def __init__(
        self,
        master: Any,
        text: str = "",
        command: Optional[Callable] = None,
        **kwargs,
    ):
        style = NaniTheme.get_switch_style()

        super().__init__(
            master,
            text=text,
            command=command,
            fg_color=style["fg_color"],
            progress_color=style["progress_color"],
            button_color=style["button_color"],
            button_hover_color=style["button_hover_color"],
            text_color=COLORS.TEXT_PRIMARY,
            font=NaniTheme.get_font("base"),
            **kwargs,
        )


class NaniTag(ctk.CTkLabel):
    """
    Nani-styled タグ/バッジ

    使用例:
        tag = NaniTag(parent, text="WIP", variant="wip")
        tag = NaniTag(parent, text="done", variant="done")
    """

    def __init__(
        self,
        master: Any,
        text: str = "",
        variant: str = "default",
        **kwargs,
    ):
        """
        Args:
            variant: "default", "primary", "success", "warning", "danger",
                    "wip", "beta", "done"
        """
        style = NaniTheme.get_tag_style(variant)

        super().__init__(
            master,
            text=text,
            fg_color=style["fg_color"],
            text_color=style["text_color"],
            corner_radius=style["corner_radius"],
            font=NaniTheme.get_font("xs"),
            padx=8,
            pady=2,
            **kwargs,
        )


class NaniSegmentedButton(ctk.CTkSegmentedButton):
    """
    Nani-styled セグメントボタン（タブ切り替え）

    使用例:
        tabs = NaniSegmentedButton(
            parent,
            values=["月ごと", "年ごと"],
            command=on_change
        )
    """

    def __init__(
        self,
        master: Any,
        values: List[str],
        command: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(
            master,
            values=values,
            command=command,
            fg_color=COLORS.BG_SECONDARY,
            selected_color=COLORS.PRIMARY,
            selected_hover_color=COLORS.PRIMARY_DARK,
            unselected_color=COLORS.BG_SECONDARY,
            unselected_hover_color=COLORS.BG_HOVER,
            text_color=COLORS.TEXT_PRIMARY,
            text_color_disabled=COLORS.TEXT_MUTED,
            corner_radius=RADIUS.MD,
            font=NaniTheme.get_font("sm"),
            **kwargs,
        )


class NaniSidebar(ctk.CTkFrame):
    """
    Nani-styled サイドバー

    使用例:
        sidebar = NaniSidebar(parent, width=250)
    """

    def __init__(
        self,
        master: Any,
        width: int = 250,
        **kwargs,
    ):
        style = NaniTheme.get_sidebar_style()

        super().__init__(
            master,
            width=width,
            fg_color=style["fg_color"],
            corner_radius=style["corner_radius"],
            **kwargs,
        )


class NaniScrollableFrame(ctk.CTkScrollableFrame):
    """
    Nani-styled スクロール可能フレーム

    使用例:
        scroll_frame = NaniScrollableFrame(parent, width=400, height=300)
    """

    def __init__(
        self,
        master: Any,
        width: int = 300,
        height: int = 200,
        **kwargs,
    ):
        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=COLORS.BG_MAIN,
            corner_radius=RADIUS.MD,
            scrollbar_button_color=COLORS.BORDER_DARK,
            scrollbar_button_hover_color=COLORS.TEXT_MUTED,
            **kwargs,
        )


class NaniOptionMenu(ctk.CTkOptionMenu):
    """
    Nani-styled ドロップダウンメニュー

    使用例:
        menu = NaniOptionMenu(
            parent,
            values=["英語", "日本語", "スペイン語"],
            command=on_select
        )
    """

    def __init__(
        self,
        master: Any,
        values: List[str],
        command: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(
            master,
            values=values,
            command=command,
            fg_color=COLORS.BG_MAIN,
            button_color=COLORS.BG_SECONDARY,
            button_hover_color=COLORS.BG_HOVER,
            dropdown_fg_color=COLORS.BG_MAIN,
            dropdown_hover_color=COLORS.PRIMARY_BG,
            text_color=COLORS.TEXT_PRIMARY,
            dropdown_text_color=COLORS.TEXT_PRIMARY,
            corner_radius=RADIUS.MD,
            font=NaniTheme.get_font("base"),
            **kwargs,
        )


# === Layout Helpers ===

def create_section_header(
    parent: Any,
    title: str,
    description: Optional[str] = None,
) -> ctk.CTkFrame:
    """
    セクションヘッダーを作成

    Args:
        parent: 親ウィジェット
        title: セクションタイトル
        description: 説明文（オプション）

    Returns:
        ヘッダーフレーム
    """
    frame = ctk.CTkFrame(parent, fg_color="transparent")

    title_label = NaniLabel(frame, text=title, variant="heading")
    title_label.pack(anchor="w")

    if description:
        desc_label = NaniLabel(frame, text=description, variant="muted")
        desc_label.pack(anchor="w", pady=(4, 0))

    return frame


def create_form_field(
    parent: Any,
    label: str,
    placeholder: str = "",
    width: int = 300,
) -> Tuple[ctk.CTkFrame, NaniEntry]:
    """
    ラベル付きフォームフィールドを作成

    Args:
        parent: 親ウィジェット
        label: フィールドラベル
        placeholder: プレースホルダーテキスト
        width: 入力フィールドの幅

    Returns:
        (フレーム, エントリーウィジェット)
    """
    frame = ctk.CTkFrame(parent, fg_color="transparent")

    label_widget = NaniLabel(frame, text=label, variant="secondary")
    label_widget.pack(anchor="w", pady=(0, 4))

    entry = NaniEntry(frame, placeholder_text=placeholder, width=width)
    entry.pack(anchor="w")

    return frame, entry


def create_button_group(
    parent: Any,
    buttons: List[dict],
    spacing: int = 8,
) -> ctk.CTkFrame:
    """
    ボタングループを作成

    Args:
        parent: 親ウィジェット
        buttons: [{"text": "...", "variant": "...", "command": ...}, ...]
        spacing: ボタン間のスペース

    Returns:
        ボタングループフレーム
    """
    frame = ctk.CTkFrame(parent, fg_color="transparent")

    for i, btn_config in enumerate(buttons):
        button = NaniButton(
            frame,
            text=btn_config.get("text", ""),
            variant=btn_config.get("variant", "secondary"),
            command=btn_config.get("command"),
        )
        button.pack(side="left", padx=(0 if i == 0 else spacing, 0))

    return frame


__all__ = [
    # 基本ウィジェット
    "NaniButton",
    "NaniEntry",
    "NaniTextbox",
    "NaniLabel",
    "NaniCard",
    "NaniProgressBar",
    "NaniSwitch",
    "NaniTag",
    "NaniSegmentedButton",
    "NaniSidebar",
    "NaniScrollableFrame",
    "NaniOptionMenu",
    # ヘルパー関数
    "create_section_header",
    "create_form_field",
    "create_button_group",
    # 動画編集コンポーネント
    "VideoPlayer",
    "SubtitleEntry",
    "Timeline",
    "TimelineSegment",
]
