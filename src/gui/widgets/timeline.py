"""
タイムラインウィジェット
======================

動画編集ソフトのようなタイムライン表示。
字幕セグメントの表示・選択・編集が可能。
"""

from typing import Optional, Callable, List
from dataclasses import dataclass

import customtkinter as ctk

from ..theme import COLORS, SPACING


@dataclass
class TimelineSegment:
    """タイムラインセグメント."""
    id: int
    start_ms: int
    end_ms: int
    text: str
    color: str = None


class Timeline(ctk.CTkFrame):
    """タイムラインウィジェット."""

    def __init__(
        self,
        master,
        height: int = 100,
        **kwargs,
    ):
        super().__init__(master, fg_color=COLORS.BG_SECONDARY, **kwargs)

        self._height = height
        self._duration_ms: int = 0
        self._current_position_ms: int = 0
        self._segments: List[TimelineSegment] = []
        self._selected_segment: Optional[TimelineSegment] = None
        self._zoom_level: float = 1.0  # pixels per millisecond
        self._scroll_offset: int = 0

        # コールバック
        self._on_seek: Optional[Callable[[int], None]] = None
        self._on_segment_select: Optional[Callable[[TimelineSegment], None]] = None
        self._on_segment_move: Optional[Callable[[TimelineSegment, int, int], None]] = None

        # ドラッグ状態
        self._dragging: bool = False
        self._drag_type: str = ""  # "playhead", "segment", "segment_start", "segment_end"
        self._drag_segment: Optional[TimelineSegment] = None
        self._drag_start_x: int = 0

        self._setup_ui()

    def _setup_ui(self) -> None:
        """UIを構築."""
        # タイムスケール（上部）
        self._scale_canvas = ctk.CTkCanvas(
            self,
            height=25,
            bg=COLORS.BG_TERTIARY,
            highlightthickness=0,
        )
        self._scale_canvas.pack(fill="x")

        # メインタイムライン
        self._canvas = ctk.CTkCanvas(
            self,
            height=self._height - 25,
            bg=COLORS.BG_MAIN,
            highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True)

        # イベントバインド
        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<Configure>", self._on_resize)
        self._scale_canvas.bind("<Button-1>", self._on_scale_click)

    def set_duration(self, duration_ms: int) -> None:
        """動画の長さを設定."""
        self._duration_ms = duration_ms
        self._calculate_zoom()
        self._redraw()

    def _calculate_zoom(self) -> None:
        """ズームレベルを計算."""
        if self._duration_ms > 0:
            canvas_width = self._canvas.winfo_width() or 800
            self._zoom_level = canvas_width / self._duration_ms

    def set_segments(self, segments: List[TimelineSegment]) -> None:
        """セグメントを設定."""
        self._segments = segments
        self._redraw()

    def set_position(self, position_ms: int) -> None:
        """再生位置を設定."""
        self._current_position_ms = position_ms
        self._redraw_playhead()

    def select_segment(self, segment_id: int) -> None:
        """セグメントを選択."""
        for seg in self._segments:
            if seg.id == segment_id:
                self._selected_segment = seg
                self._redraw()
                return

    def _ms_to_x(self, ms: int) -> int:
        """ミリ秒をX座標に変換."""
        return int(ms * self._zoom_level) - self._scroll_offset

    def _x_to_ms(self, x: int) -> int:
        """X座標をミリ秒に変換."""
        return int((x + self._scroll_offset) / self._zoom_level)

    def _redraw(self) -> None:
        """全体を再描画."""
        self._redraw_scale()
        self._redraw_segments()
        self._redraw_playhead()

    def _redraw_scale(self) -> None:
        """タイムスケールを描画."""
        self._scale_canvas.delete("all")
        canvas_width = self._scale_canvas.winfo_width() or 800

        if self._duration_ms == 0:
            return

        # 適切な間隔を計算（1秒、5秒、10秒、30秒、1分など）
        intervals = [1000, 5000, 10000, 30000, 60000, 300000, 600000]
        min_pixel_gap = 50

        interval_ms = intervals[0]
        for iv in intervals:
            if iv * self._zoom_level >= min_pixel_gap:
                interval_ms = iv
                break

        # 目盛りを描画
        ms = 0
        while ms <= self._duration_ms:
            x = self._ms_to_x(ms)
            if 0 <= x <= canvas_width:
                # 時間ラベル
                time_str = self._format_time(ms)
                self._scale_canvas.create_text(
                    x, 12,
                    text=time_str,
                    fill=COLORS.TEXT_MUTED,
                    font=("Helvetica", 9),
                    anchor="center",
                )
                # 目盛り線
                self._scale_canvas.create_line(
                    x, 20, x, 25,
                    fill=COLORS.BORDER_DARK,
                )
            ms += interval_ms

    def _redraw_segments(self) -> None:
        """セグメントを描画."""
        self._canvas.delete("segment")
        canvas_height = self._canvas.winfo_height() or 75

        segment_height = canvas_height - 20
        segment_y = 10

        for seg in self._segments:
            x1 = self._ms_to_x(seg.start_ms)
            x2 = self._ms_to_x(seg.end_ms)

            # 色を決定
            if seg == self._selected_segment:
                fill_color = COLORS.PRIMARY
                outline_color = COLORS.PRIMARY_DARK
            else:
                fill_color = seg.color or COLORS.PRIMARY_BG
                outline_color = COLORS.BORDER_DEFAULT

            # セグメント矩形
            self._canvas.create_rectangle(
                x1, segment_y,
                x2, segment_y + segment_height,
                fill=fill_color,
                outline=outline_color,
                width=2,
                tags=("segment", f"seg_{seg.id}"),
            )

            # テキスト（切り詰め）
            text = seg.text.replace("\\N", " ").replace("\n", " ")
            if len(text) > 30:
                text = text[:27] + "..."

            text_width = x2 - x1 - 10
            if text_width > 20:
                self._canvas.create_text(
                    x1 + 5, segment_y + segment_height // 2,
                    text=text,
                    fill=COLORS.TEXT_PRIMARY if seg != self._selected_segment else "#FFFFFF",
                    font=("Helvetica", 10),
                    anchor="w",
                    width=text_width,
                    tags=("segment", f"seg_{seg.id}"),
                )

            # リサイズハンドル（選択時）
            if seg == self._selected_segment:
                handle_width = 6
                # 左ハンドル
                self._canvas.create_rectangle(
                    x1, segment_y,
                    x1 + handle_width, segment_y + segment_height,
                    fill=COLORS.PRIMARY_DARKER,
                    outline="",
                    tags=("segment", "handle_start", f"seg_{seg.id}"),
                )
                # 右ハンドル
                self._canvas.create_rectangle(
                    x2 - handle_width, segment_y,
                    x2, segment_y + segment_height,
                    fill=COLORS.PRIMARY_DARKER,
                    outline="",
                    tags=("segment", "handle_end", f"seg_{seg.id}"),
                )

    def _redraw_playhead(self) -> None:
        """再生ヘッドを描画."""
        self._canvas.delete("playhead")
        self._scale_canvas.delete("playhead")

        x = self._ms_to_x(self._current_position_ms)
        canvas_height = self._canvas.winfo_height() or 75

        # 再生ヘッド（縦線）
        self._canvas.create_line(
            x, 0, x, canvas_height,
            fill=COLORS.DANGER,
            width=2,
            tags="playhead",
        )

        # 再生ヘッド（三角形）
        self._scale_canvas.create_polygon(
            x - 6, 20,
            x + 6, 20,
            x, 25,
            fill=COLORS.DANGER,
            outline="",
            tags="playhead",
        )

    def _format_time(self, ms: int) -> str:
        """時間をフォーマット."""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        if minutes >= 60:
            hours = minutes // 60
            minutes = minutes % 60
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def _on_click(self, event) -> None:
        """クリックイベント."""
        x, y = event.x, event.y

        # セグメントのハンドルをチェック
        items = self._canvas.find_overlapping(x - 2, y - 2, x + 2, y + 2)
        for item in items:
            tags = self._canvas.gettags(item)
            if "handle_start" in tags:
                self._dragging = True
                self._drag_type = "segment_start"
                self._drag_segment = self._selected_segment
                self._drag_start_x = x
                return
            elif "handle_end" in tags:
                self._dragging = True
                self._drag_type = "segment_end"
                self._drag_segment = self._selected_segment
                self._drag_start_x = x
                return

        # セグメントをクリック
        for item in items:
            tags = self._canvas.gettags(item)
            for tag in tags:
                if tag.startswith("seg_"):
                    seg_id = int(tag[4:])
                    for seg in self._segments:
                        if seg.id == seg_id:
                            self._selected_segment = seg
                            self._redraw()
                            if self._on_segment_select:
                                self._on_segment_select(seg)
                            return

        # 空白クリック = シーク
        position_ms = self._x_to_ms(x)
        position_ms = max(0, min(position_ms, self._duration_ms))
        self._current_position_ms = position_ms
        self._redraw_playhead()
        if self._on_seek:
            self._on_seek(position_ms)

    def _on_scale_click(self, event) -> None:
        """スケールクリックイベント."""
        position_ms = self._x_to_ms(event.x)
        position_ms = max(0, min(position_ms, self._duration_ms))
        self._current_position_ms = position_ms
        self._redraw_playhead()
        if self._on_seek:
            self._on_seek(position_ms)

    def _on_drag(self, event) -> None:
        """ドラッグイベント."""
        if not self._dragging or not self._drag_segment:
            return

        delta_x = event.x - self._drag_start_x
        delta_ms = int(delta_x / self._zoom_level)

        if self._drag_type == "segment_start":
            new_start = max(0, self._drag_segment.start_ms + delta_ms)
            new_start = min(new_start, self._drag_segment.end_ms - 100)
            if self._on_segment_move:
                self._on_segment_move(
                    self._drag_segment,
                    new_start,
                    self._drag_segment.end_ms,
                )
            self._drag_segment.start_ms = new_start
        elif self._drag_type == "segment_end":
            new_end = min(self._duration_ms, self._drag_segment.end_ms + delta_ms)
            new_end = max(new_end, self._drag_segment.start_ms + 100)
            if self._on_segment_move:
                self._on_segment_move(
                    self._drag_segment,
                    self._drag_segment.start_ms,
                    new_end,
                )
            self._drag_segment.end_ms = new_end

        self._drag_start_x = event.x
        self._redraw()

    def _on_release(self, event) -> None:
        """リリースイベント."""
        self._dragging = False
        self._drag_type = ""
        self._drag_segment = None

    def _on_resize(self, event) -> None:
        """リサイズイベント."""
        self._calculate_zoom()
        self._redraw()

    def set_on_seek(self, callback: Callable[[int], None]) -> None:
        """シークコールバックを設定."""
        self._on_seek = callback

    def set_on_segment_select(self, callback: Callable[[TimelineSegment], None]) -> None:
        """セグメント選択コールバックを設定."""
        self._on_segment_select = callback

    def set_on_segment_move(
        self,
        callback: Callable[[TimelineSegment, int, int], None],
    ) -> None:
        """セグメント移動コールバックを設定."""
        self._on_segment_move = callback
