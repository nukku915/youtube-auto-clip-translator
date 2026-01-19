"""
YouTube Auto Clip Translator - メインアプリケーション
=====================================================

CustomTkinterベースのデスクトップアプリケーション。
"""

import asyncio
import threading
from pathlib import Path
from typing import Optional, Callable

import customtkinter as ctk

from .theme import apply_nani_theme, COLORS, SPACING, NaniTheme


class App(ctk.CTk):
    """メインアプリケーションクラス."""

    APP_NAME = "YouTube Auto Clip Translator"
    DEFAULT_WIDTH = 1200
    DEFAULT_HEIGHT = 800
    MIN_WIDTH = 900
    MIN_HEIGHT = 600

    def __init__(self) -> None:
        """アプリケーションを初期化."""
        super().__init__()

        # テーマを適用
        apply_nani_theme()

        # ウィンドウ設定
        self.title(self.APP_NAME)
        self.geometry(f"{self.DEFAULT_WIDTH}x{self.DEFAULT_HEIGHT}")
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)

        # 背景色
        self.configure(fg_color=COLORS.BG_MAIN)

        # ビューのコンテナ
        self._views: dict = {}
        self._current_view: Optional[ctk.CTkFrame] = None

        # 非同期イベントループ
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None

        # UIを構築
        self._setup_ui()

        # 非同期ループを開始
        self._start_async_loop()

        # 初期ビューを表示
        self.show_view("home")

    def _setup_ui(self) -> None:
        """UIを構築."""
        # メインコンテナ
        self._main_container = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        self._main_container.pack(fill="both", expand=True)

        # グリッド設定
        self._main_container.grid_rowconfigure(0, weight=1)
        self._main_container.grid_columnconfigure(0, weight=1)

    def _start_async_loop(self) -> None:
        """非同期イベントループを開始."""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

    def run_async(self, coro) -> asyncio.Future:
        """非同期タスクを実行.

        Args:
            coro: 実行するコルーチン

        Returns:
            Future オブジェクト
        """
        if self._loop is None:
            raise RuntimeError("Event loop not started")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def show_view(self, view_name: str, **kwargs) -> None:
        """ビューを表示.

        Args:
            view_name: ビュー名 ("home", "processing", "settings")
            **kwargs: ビューに渡す引数
        """
        # 既存のビューを非表示
        if self._current_view is not None:
            self._current_view.grid_forget()

        # ビューを取得または作成
        if view_name not in self._views:
            self._views[view_name] = self._create_view(view_name)

        view = self._views[view_name]

        # ビューを初期化（必要に応じて）
        if hasattr(view, "on_show"):
            view.on_show(**kwargs)

        # ビューを表示
        view.grid(row=0, column=0, sticky="nsew")
        self._current_view = view

    def _create_view(self, view_name: str) -> ctk.CTkFrame:
        """ビューを作成.

        Args:
            view_name: ビュー名

        Returns:
            作成したビュー
        """
        from .views import (
            HomeView,
            ProcessingView,
            SettingsView,
            ResultView,
            EditorView,
        )

        view_classes = {
            "home": HomeView,
            "processing": ProcessingView,
            "settings": SettingsView,
            "result": ResultView,
            "editor": EditorView,
        }

        view_class = view_classes.get(view_name)
        if view_class is None:
            raise ValueError(f"Unknown view: {view_name}")

        return view_class(self._main_container, app=self)

    def on_closing(self) -> None:
        """アプリケーション終了時の処理."""
        # 非同期ループを停止
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

        self.destroy()

    def run(self) -> None:
        """アプリケーションを実行."""
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.mainloop()


def main() -> None:
    """アプリケーションのエントリーポイント."""
    app = App()
    app.run()


if __name__ == "__main__":
    main()
