"""
ベースビュークラス
=================

全てのビューの基底クラス。
"""

from typing import TYPE_CHECKING, Any, Optional

import customtkinter as ctk

from ..theme import COLORS, SPACING, NaniTheme

if TYPE_CHECKING:
    from ..app import App


class BaseView(ctk.CTkFrame):
    """ベースビュークラス."""

    def __init__(
        self,
        master: Any,
        app: "App",
        **kwargs,
    ) -> None:
        """初期化.

        Args:
            master: 親ウィジェット
            app: アプリケーションインスタンス
        """
        super().__init__(
            master,
            fg_color=COLORS.BG_MAIN,
            **kwargs,
        )
        self.app = app
        self._setup_ui()

    def _setup_ui(self) -> None:
        """UIを構築（サブクラスでオーバーライド）."""
        pass

    def on_show(self, **kwargs) -> None:
        """ビュー表示時に呼ばれる（サブクラスでオーバーライド）."""
        pass

    def on_hide(self) -> None:
        """ビュー非表示時に呼ばれる（サブクラスでオーバーライド）."""
        pass

    def navigate_to(self, view_name: str, **kwargs) -> None:
        """他のビューへ遷移.

        Args:
            view_name: 遷移先ビュー名
            **kwargs: ビューに渡す引数
        """
        self.app.show_view(view_name, **kwargs)
