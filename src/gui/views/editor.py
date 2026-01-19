"""
字幕編集ビュー（動画編集モード）
================================

動画プレビュー + タイムライン + 字幕編集を統合した編集画面。
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional, List

import customtkinter as ctk
import pysubs2

from ..theme import COLORS, SPACING, NaniTheme
from ..widgets import (
    NaniButton,
    NaniLabel,
    NaniEntry,
)
from ..widgets.video_player import VideoPlayer, SubtitleEntry
from ..widgets.timeline import Timeline, TimelineSegment
from .base import BaseView

if TYPE_CHECKING:
    from ..app import App


class EditorView(BaseView):
    """字幕編集ビュー（動画編集モード）."""

    def __init__(self, master, app: "App", **kwargs) -> None:
        self._subtitle_path: Optional[Path] = None
        self._video_path: Optional[Path] = None
        self._video_title: str = ""
        self._output_dir: Optional[Path] = None
        self._subs: Optional[pysubs2.SSAFile] = None
        self._segments: List[TimelineSegment] = []
        self._selected_segment: Optional[TimelineSegment] = None
        self._has_changes: bool = False
        super().__init__(master, app, **kwargs)

    def _setup_ui(self) -> None:
        """UIを構築."""
        # グリッド設定
        self.grid_rowconfigure(1, weight=1)  # メインコンテンツ
        self.grid_columnconfigure(0, weight=1)

        # === ヘッダー ===
        header = ctk.CTkFrame(self, fg_color=COLORS.BG_SECONDARY, height=50)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        # 戻るボタン
        back_btn = NaniButton(
            header,
            text="← 戻る",
            variant="ghost",
            width=80,
            command=self._on_back_clicked,
        )
        back_btn.grid(row=0, column=0, padx=SPACING.MD, pady=SPACING.SM)

        # タイトル
        self._title_label = NaniLabel(
            header,
            text="字幕編集",
            variant="heading",
        )
        self._title_label.grid(row=0, column=1, pady=SPACING.SM)

        # 保存ボタン
        self._save_btn = NaniButton(
            header,
            text="保存",
            variant="primary",
            width=100,
            command=self._on_save_clicked,
        )
        self._save_btn.grid(row=0, column=2, padx=SPACING.MD, pady=SPACING.SM)

        # === メインコンテンツ ===
        main_content = ctk.CTkFrame(self, fg_color="transparent")
        main_content.grid(row=1, column=0, sticky="nsew", padx=SPACING.MD, pady=SPACING.SM)
        main_content.grid_rowconfigure(0, weight=3)  # 動画プレビュー
        main_content.grid_rowconfigure(1, weight=0)  # コントロール
        main_content.grid_rowconfigure(2, weight=0)  # タイムライン
        main_content.grid_rowconfigure(3, weight=2)  # 字幕編集パネル
        main_content.grid_columnconfigure(0, weight=1)

        # === 動画プレビュー ===
        preview_frame = ctk.CTkFrame(main_content, fg_color=COLORS.BG_MAIN)
        preview_frame.grid(row=0, column=0, sticky="nsew", pady=(0, SPACING.SM))

        self._video_player = VideoPlayer(
            preview_frame,
            width=960,
            height=540,
            fg_color="black",
        )
        self._video_player.pack(expand=True, fill="both", padx=2, pady=2)
        self._video_player.set_on_position_change(self._on_position_change)

        # === 再生コントロール ===
        controls_frame = ctk.CTkFrame(main_content, fg_color="transparent", height=50)
        controls_frame.grid(row=1, column=0, sticky="ew", pady=SPACING.XS)

        # 再生/一時停止ボタン
        self._play_btn = NaniButton(
            controls_frame,
            text="▶ 再生",
            variant="secondary",
            width=100,
            command=self._on_play_clicked,
        )
        self._play_btn.pack(side="left", padx=SPACING.SM)

        # 停止ボタン
        stop_btn = NaniButton(
            controls_frame,
            text="■ 停止",
            variant="ghost",
            width=80,
            command=self._on_stop_clicked,
        )
        stop_btn.pack(side="left", padx=SPACING.XS)

        # 時間表示
        self._time_label = NaniLabel(
            controls_frame,
            text="00:00 / 00:00",
            variant="muted",
        )
        self._time_label.pack(side="left", padx=SPACING.MD)

        # 現在の字幕表示
        self._current_subtitle_label = NaniLabel(
            controls_frame,
            text="",
            variant="default",
        )
        self._current_subtitle_label.pack(side="left", padx=SPACING.MD, fill="x", expand=True)

        # === タイムライン ===
        timeline_frame = ctk.CTkFrame(main_content, fg_color=COLORS.BG_SECONDARY)
        timeline_frame.grid(row=2, column=0, sticky="ew", pady=SPACING.XS)

        self._timeline = Timeline(timeline_frame, height=80)
        self._timeline.pack(fill="x", expand=True)
        self._timeline.set_on_seek(self._on_timeline_seek)
        self._timeline.set_on_segment_select(self._on_segment_selected)
        self._timeline.set_on_segment_move(self._on_segment_moved)

        # === 字幕編集パネル ===
        edit_panel = ctk.CTkFrame(main_content, fg_color=COLORS.BG_SECONDARY)
        edit_panel.grid(row=3, column=0, sticky="nsew", pady=(SPACING.SM, 0))
        edit_panel.grid_columnconfigure(1, weight=1)

        # パネルヘッダー
        panel_header = ctk.CTkFrame(edit_panel, fg_color="transparent")
        panel_header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=SPACING.MD, pady=SPACING.SM)

        edit_title = NaniLabel(
            panel_header,
            text="字幕編集",
            variant="subtitle",
        )
        edit_title.pack(side="left")

        # 字幕リストボタン
        list_btn = NaniButton(
            panel_header,
            text="字幕一覧",
            variant="ghost",
            width=100,
            command=self._show_subtitle_list,
        )
        list_btn.pack(side="right")

        # タイミング編集
        timing_frame = ctk.CTkFrame(edit_panel, fg_color="transparent")
        timing_frame.grid(row=1, column=0, padx=SPACING.MD, pady=SPACING.SM, sticky="nw")

        NaniLabel(timing_frame, text="開始", variant="caption").grid(row=0, column=0, sticky="w")
        self._start_entry = NaniEntry(
            timing_frame,
            width=100,
            placeholder_text="00:00.000",
        )
        self._start_entry.grid(row=1, column=0, pady=SPACING.XS)
        self._start_entry.bind("<FocusOut>", self._on_timing_changed)

        NaniLabel(timing_frame, text="終了", variant="caption").grid(row=0, column=1, padx=(SPACING.SM, 0), sticky="w")
        self._end_entry = NaniEntry(
            timing_frame,
            width=100,
            placeholder_text="00:00.000",
        )
        self._end_entry.grid(row=1, column=1, padx=(SPACING.SM, 0), pady=SPACING.XS)
        self._end_entry.bind("<FocusOut>", self._on_timing_changed)

        # 長さ表示
        self._duration_label = NaniLabel(
            timing_frame,
            text="長さ: --",
            variant="muted",
        )
        self._duration_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(SPACING.XS, 0))

        # テキスト編集
        text_frame = ctk.CTkFrame(edit_panel, fg_color="transparent")
        text_frame.grid(row=1, column=1, padx=SPACING.MD, pady=SPACING.SM, sticky="nsew")
        text_frame.grid_rowconfigure(1, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        NaniLabel(text_frame, text="字幕テキスト", variant="caption").grid(row=0, column=0, sticky="w")
        self._text_entry = ctk.CTkTextbox(
            text_frame,
            height=80,
            fg_color=COLORS.BG_MAIN,
            border_color=COLORS.BORDER_DEFAULT,
            border_width=1,
            corner_radius=4,
            font=NaniTheme.get_font("base"),
        )
        self._text_entry.grid(row=1, column=0, sticky="nsew", pady=SPACING.XS)
        self._text_entry.bind("<KeyRelease>", self._on_text_changed)

        # スタイル編集
        style_frame = ctk.CTkFrame(edit_panel, fg_color="transparent")
        style_frame.grid(row=1, column=2, padx=SPACING.MD, pady=SPACING.SM, sticky="ne")

        NaniLabel(style_frame, text="スタイル", variant="caption").pack(anchor="w")

        # フォントサイズ
        size_frame = ctk.CTkFrame(style_frame, fg_color="transparent")
        size_frame.pack(fill="x", pady=SPACING.XS)
        NaniLabel(size_frame, text="サイズ:", variant="muted").pack(side="left")
        self._font_size_var = ctk.StringVar(value="32")
        font_size_menu = ctk.CTkOptionMenu(
            size_frame,
            values=["24", "28", "32", "36", "40", "48"],
            variable=self._font_size_var,
            width=80,
            fg_color=COLORS.BG_MAIN,
            button_color=COLORS.BG_HOVER,
            command=self._on_style_changed,
        )
        font_size_menu.pack(side="left", padx=(SPACING.XS, 0))

        # 位置
        pos_frame = ctk.CTkFrame(style_frame, fg_color="transparent")
        pos_frame.pack(fill="x", pady=SPACING.XS)
        NaniLabel(pos_frame, text="位置:", variant="muted").pack(side="left")
        self._position_var = ctk.StringVar(value="bottom")
        position_menu = ctk.CTkOptionMenu(
            pos_frame,
            values=["bottom", "top", "center"],
            variable=self._position_var,
            width=80,
            fg_color=COLORS.BG_MAIN,
            button_color=COLORS.BG_HOVER,
            command=self._on_style_changed,
        )
        position_menu.pack(side="left", padx=(SPACING.XS, 0))

        # プレビュー更新ボタン
        preview_btn = NaniButton(
            style_frame,
            text="プレビュー更新",
            variant="outline",
            width=120,
            command=self._refresh_preview,
        )
        preview_btn.pack(pady=SPACING.SM)

        # 初期状態：編集パネルを無効化
        self._set_edit_panel_enabled(False)

    def _set_edit_panel_enabled(self, enabled: bool) -> None:
        """編集パネルの有効/無効を切り替え."""
        state = "normal" if enabled else "disabled"
        self._start_entry.configure(state=state)
        self._end_entry.configure(state=state)
        self._text_entry.configure(state=state)

    def on_show(self, **kwargs) -> None:
        """ビュー表示時."""
        self._subtitle_path = kwargs.get("subtitle_path")
        self._video_title = kwargs.get("video_title", "")
        self._output_dir = kwargs.get("output_dir")

        # 動画パスを探す
        if self._subtitle_path:
            self._find_video_path()

        if self._video_title:
            self._title_label.configure(text=f"編集: {self._video_title[:30]}...")

        # 字幕を読み込み
        if self._subtitle_path:
            self._load_subtitles()

        # 動画を読み込み
        if self._video_path:
            self._load_video()

    def _find_video_path(self) -> None:
        """動画ファイルのパスを探す."""
        if not self._subtitle_path:
            return

        # 字幕ファイルと同じディレクトリで動画を探す
        subtitle_dir = Path(self._subtitle_path).parent
        video_extensions = [".mp4", ".webm", ".mkv", ".avi", ".mov"]

        # 同じ名前の動画を探す
        base_name = Path(self._subtitle_path).stem
        for ext in video_extensions:
            video_path = subtitle_dir / f"{base_name}{ext}"
            if video_path.exists():
                self._video_path = video_path
                return

        # downloadsディレクトリを探す
        downloads_dir = subtitle_dir / "downloads"
        if downloads_dir.exists():
            for ext in video_extensions:
                for video_file in downloads_dir.glob(f"*{ext}"):
                    self._video_path = video_file
                    return

    def _load_subtitles(self) -> None:
        """字幕ファイルを読み込み."""
        if not self._subtitle_path or not Path(self._subtitle_path).exists():
            return

        try:
            self._subs = pysubs2.load(str(self._subtitle_path))
            self._segments = []

            for i, event in enumerate(self._subs.events):
                segment = TimelineSegment(
                    id=i,
                    start_ms=event.start,
                    end_ms=event.end,
                    text=event.text,
                )
                self._segments.append(segment)

            # タイムラインに設定
            if self._segments:
                max_end = max(seg.end_ms for seg in self._segments)
                self._timeline.set_duration(max_end + 5000)  # 5秒余裕
            self._timeline.set_segments(self._segments)

            # 動画プレイヤーに字幕を設定
            subtitle_entries = [
                SubtitleEntry(
                    start_ms=seg.start_ms,
                    end_ms=seg.end_ms,
                    text=seg.text,
                )
                for seg in self._segments
            ]
            self._video_player.set_subtitles(subtitle_entries)

            self._has_changes = False

        except Exception as e:
            self._show_error(f"字幕の読み込みに失敗しました: {e}")

    def _load_video(self) -> None:
        """動画を読み込み."""
        if not self._video_path:
            return

        success = self._video_player.load_video(self._video_path)
        if success:
            duration = self._video_player.get_duration_ms()
            self._timeline.set_duration(duration)
            self._update_time_display()
        else:
            self._show_error("動画の読み込みに失敗しました")

    def _on_play_clicked(self) -> None:
        """再生/一時停止ボタンクリック."""
        if self._video_player.is_playing():
            self._video_player.pause()
            self._play_btn.configure(text="▶ 再生")
        else:
            self._video_player.play()
            self._play_btn.configure(text="⏸ 一時停止")

    def _on_stop_clicked(self) -> None:
        """停止ボタンクリック."""
        self._video_player.stop()
        self._video_player.seek(0)
        self._play_btn.configure(text="▶ 再生")
        self._timeline.set_position(0)
        self._update_time_display()

    def _on_position_change(self, position_ms: int) -> None:
        """再生位置変更時."""
        self._timeline.set_position(position_ms)
        self._update_time_display()

        # 現在の字幕を表示
        for seg in self._segments:
            if seg.start_ms <= position_ms <= seg.end_ms:
                text = seg.text.replace("\\N", " ")[:50]
                self._current_subtitle_label.configure(text=f"📝 {text}")
                return
        self._current_subtitle_label.configure(text="")

    def _on_timeline_seek(self, position_ms: int) -> None:
        """タイムラインシーク時."""
        # シーク時は強制字幕をクリア（通常の字幕表示に戻す）
        self._video_player.clear_forced_subtitle()
        self._video_player.seek(position_ms)
        self._update_time_display()

    def _on_segment_selected(self, segment: TimelineSegment) -> None:
        """セグメント選択時."""
        self._selected_segment = segment
        self._set_edit_panel_enabled(True)

        # 編集パネルを更新
        self._start_entry.delete(0, "end")
        self._start_entry.insert(0, self._format_time_ms(segment.start_ms))

        self._end_entry.delete(0, "end")
        self._end_entry.insert(0, self._format_time_ms(segment.end_ms))

        duration_ms = segment.end_ms - segment.start_ms
        self._duration_label.configure(text=f"長さ: {duration_ms / 1000:.1f}秒")

        self._text_entry.delete("1.0", "end")
        self._text_entry.insert("1.0", segment.text)

        # 選択されたセグメントの字幕を強制表示
        forced_sub = SubtitleEntry(
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            text=segment.text,
        )
        self._video_player.set_forced_subtitle(forced_sub)

        # その位置にシーク
        self._video_player.seek(segment.start_ms)

    def _on_segment_moved(self, segment: TimelineSegment, new_start: int, new_end: int) -> None:
        """セグメント移動時."""
        # pysubs2のイベントを更新
        if self._subs and segment.id < len(self._subs.events):
            self._subs.events[segment.id].start = new_start
            self._subs.events[segment.id].end = new_end

        self._has_changes = True
        self._update_save_button()

        # 動画プレイヤーの字幕も更新
        self._update_video_subtitles()

        # 編集パネルを更新（選択中の場合）
        if self._selected_segment == segment:
            self._start_entry.delete(0, "end")
            self._start_entry.insert(0, self._format_time_ms(new_start))
            self._end_entry.delete(0, "end")
            self._end_entry.insert(0, self._format_time_ms(new_end))
            duration_ms = new_end - new_start
            self._duration_label.configure(text=f"長さ: {duration_ms / 1000:.1f}秒")

    def _on_timing_changed(self, event=None) -> None:
        """タイミング変更時."""
        if not self._selected_segment:
            return

        try:
            start_ms = self._parse_time_ms(self._start_entry.get())
            end_ms = self._parse_time_ms(self._end_entry.get())

            if start_ms >= end_ms:
                return

            self._selected_segment.start_ms = start_ms
            self._selected_segment.end_ms = end_ms

            # pysubs2のイベントを更新
            if self._subs and self._selected_segment.id < len(self._subs.events):
                self._subs.events[self._selected_segment.id].start = start_ms
                self._subs.events[self._selected_segment.id].end = end_ms

            self._has_changes = True
            self._update_save_button()
            self._timeline.set_segments(self._segments)
            self._update_video_subtitles()

            duration_ms = end_ms - start_ms
            self._duration_label.configure(text=f"長さ: {duration_ms / 1000:.1f}秒")

        except ValueError:
            pass

    def _on_text_changed(self, event=None) -> None:
        """テキスト変更時."""
        if not self._selected_segment:
            return

        new_text = self._text_entry.get("1.0", "end-1c")
        self._selected_segment.text = new_text

        # pysubs2のイベントを更新
        if self._subs and self._selected_segment.id < len(self._subs.events):
            self._subs.events[self._selected_segment.id].text = new_text

        self._has_changes = True
        self._update_save_button()
        self._update_video_subtitles()

    def _on_style_changed(self, value=None) -> None:
        """スタイル変更時."""
        font_size = int(self._font_size_var.get())
        position = self._position_var.get()

        self._video_player.set_subtitle_style(
            font_size=font_size,
            position=position,
        )

    def _refresh_preview(self) -> None:
        """プレビューを更新."""
        self._update_video_subtitles()
        current_pos = self._video_player.get_position_ms()
        self._video_player.seek(current_pos)

    def _update_video_subtitles(self) -> None:
        """動画プレイヤーの字幕を更新."""
        subtitle_entries = [
            SubtitleEntry(
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                text=seg.text,
            )
            for seg in self._segments
        ]
        self._video_player.set_subtitles(subtitle_entries)

    def _update_time_display(self) -> None:
        """時間表示を更新."""
        current = self._video_player.get_position_ms()
        total = self._video_player.get_duration_ms()
        self._time_label.configure(
            text=f"{self._format_time_short(current)} / {self._format_time_short(total)}"
        )

    def _update_save_button(self) -> None:
        """保存ボタンの状態を更新."""
        if self._has_changes:
            self._save_btn.configure(text="保存 *")
        else:
            self._save_btn.configure(text="保存")

    def _format_time_ms(self, ms: int) -> str:
        """ミリ秒を MM:SS.mmm 形式にフォーマット."""
        seconds = ms / 1000
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:06.3f}"

    def _format_time_short(self, ms: int) -> str:
        """ミリ秒を MM:SS 形式にフォーマット."""
        seconds = ms // 1000
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"

    def _parse_time_ms(self, time_str: str) -> int:
        """時間文字列をミリ秒に変換."""
        parts = time_str.split(":")
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            return int((minutes * 60 + seconds) * 1000)
        raise ValueError(f"Invalid time format: {time_str}")

    def _on_save_clicked(self) -> None:
        """保存ボタンクリック時."""
        if not self._subs or not self._subtitle_path:
            return

        try:
            # 保存
            self._subs.save(str(self._subtitle_path))

            # SRT形式も更新
            srt_path = Path(self._subtitle_path).with_suffix(".srt")
            self._subs.save(str(srt_path))

            self._has_changes = False
            self._update_save_button()
            self._show_success("保存しました")

        except Exception as e:
            self._show_error(f"保存に失敗しました: {e}")

    def _on_back_clicked(self) -> None:
        """戻るボタンクリック時."""
        self._video_player.stop()
        self.navigate_to("home")

    def _show_subtitle_list(self) -> None:
        """字幕一覧を表示."""
        # 簡易実装：モーダルウィンドウで表示
        if not self._segments:
            return

        list_window = ctk.CTkToplevel(self)
        list_window.title("字幕一覧")
        list_window.geometry("600x400")
        list_window.transient(self.winfo_toplevel())

        # スクロール可能なリスト
        scrollable = ctk.CTkScrollableFrame(list_window)
        scrollable.pack(fill="both", expand=True, padx=10, pady=10)

        for seg in self._segments:
            frame = ctk.CTkFrame(scrollable, fg_color=COLORS.BG_SECONDARY)
            frame.pack(fill="x", pady=2)

            time_str = f"{self._format_time_short(seg.start_ms)} - {self._format_time_short(seg.end_ms)}"
            NaniLabel(frame, text=time_str, variant="caption").pack(side="left", padx=5)

            text = seg.text.replace("\\N", " ")[:40]
            NaniLabel(frame, text=text, variant="default").pack(side="left", padx=5, fill="x", expand=True)

            # ジャンプボタン
            jump_btn = NaniButton(
                frame,
                text="→",
                variant="ghost",
                width=30,
                command=lambda s=seg: self._jump_to_segment(s, list_window),
            )
            jump_btn.pack(side="right", padx=5)

    def _jump_to_segment(self, segment: TimelineSegment, window: ctk.CTkToplevel) -> None:
        """指定セグメントにジャンプ."""
        window.destroy()
        self._timeline.select_segment(segment.id)
        self._on_segment_selected(segment)

    def _show_error(self, message: str) -> None:
        """エラーメッセージを表示."""
        self._title_label.configure(text=message, text_color=COLORS.DANGER)
        self.after(3000, lambda: self._title_label.configure(
            text="字幕編集" if not self._video_title else f"編集: {self._video_title[:30]}...",
            text_color=COLORS.TEXT_PRIMARY,
        ))

    def _show_success(self, message: str) -> None:
        """成功メッセージを表示."""
        self._title_label.configure(text=message, text_color=COLORS.SUCCESS)
        self.after(2000, lambda: self._title_label.configure(
            text="字幕編集" if not self._video_title else f"編集: {self._video_title[:30]}...",
            text_color=COLORS.TEXT_PRIMARY,
        ))

    def destroy(self) -> None:
        """クリーンアップ."""
        if hasattr(self, '_video_player'):
            self._video_player.destroy()
        super().destroy()
