"""
動画プレイヤーウィジェット
========================

OpenCVベースの動画プレイヤー。字幕オーバーレイ機能付き。
"""

import threading
import time
from pathlib import Path
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont
import customtkinter as ctk


@dataclass
class SubtitleEntry:
    """字幕エントリ."""
    start_ms: int
    end_ms: int
    text: str
    style: dict = None


class VideoPlayer(ctk.CTkFrame):
    """動画プレイヤーウィジェット."""

    def __init__(
        self,
        master,
        width: int = 800,
        height: int = 450,
        **kwargs,
    ):
        super().__init__(master, **kwargs)

        self._width = width
        self._height = height
        self._video_path: Optional[Path] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self._fps: float = 30.0
        self._total_frames: int = 0
        self._current_frame: int = 0
        self._duration_ms: int = 0
        self._is_playing: bool = False
        self._play_thread: Optional[threading.Thread] = None
        self._stop_flag: bool = False

        # 字幕
        self._subtitles: List[SubtitleEntry] = []
        self._current_subtitle: Optional[SubtitleEntry] = None
        self._forced_subtitle: Optional[SubtitleEntry] = None  # 強制表示用
        self._subtitle_font: Optional[ImageFont.FreeTypeFont] = None
        self._subtitle_style = {
            "font_size": 32,
            "font_color": (255, 255, 255),
            "outline_color": (0, 0, 0),
            "outline_width": 2,
            "position": "bottom",  # bottom, top, center
            "margin": 40,
        }

        # コールバック
        self._on_position_change: Optional[Callable[[int], None]] = None
        self._on_play_state_change: Optional[Callable[[bool], None]] = None

        self._setup_ui()
        self._load_subtitle_font()

    def _setup_ui(self) -> None:
        """UIを構築."""
        # 動画表示キャンバス
        self._canvas = ctk.CTkCanvas(
            self,
            width=self._width,
            height=self._height,
            bg="black",
            highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True)

        # プレースホルダー画像
        self._show_placeholder()

    def _load_subtitle_font(self) -> None:
        """字幕用フォントを読み込み."""
        try:
            # macOSの日本語フォント
            font_paths = [
                "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/Library/Fonts/Arial Unicode.ttf",
                "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            ]
            for font_path in font_paths:
                if Path(font_path).exists():
                    self._subtitle_font = ImageFont.truetype(
                        font_path,
                        self._subtitle_style["font_size"],
                    )
                    break
            if self._subtitle_font is None:
                self._subtitle_font = ImageFont.load_default()
        except Exception:
            self._subtitle_font = ImageFont.load_default()

    def _show_placeholder(self) -> None:
        """プレースホルダーを表示."""
        self._canvas.delete("all")
        self._canvas.create_text(
            self._width // 2,
            self._height // 2,
            text="動画を読み込んでください",
            fill="#666666",
            font=("Helvetica", 16),
        )

    def load_video(self, video_path: Path) -> bool:
        """動画を読み込み."""
        self.stop()

        if not video_path.exists():
            return False

        self._video_path = video_path
        self._cap = cv2.VideoCapture(str(video_path))

        if not self._cap.isOpened():
            return False

        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._duration_ms = int((self._total_frames / self._fps) * 1000)
        self._current_frame = 0

        # 最初のフレームを表示
        self._show_frame(0)
        return True

    def set_subtitles(self, subtitles: List[SubtitleEntry]) -> None:
        """字幕を設定."""
        self._subtitles = subtitles

    def set_subtitle_style(self, **style) -> None:
        """字幕スタイルを設定."""
        self._subtitle_style.update(style)
        if "font_size" in style:
            self._load_subtitle_font()

    def set_forced_subtitle(self, subtitle: Optional[SubtitleEntry]) -> None:
        """強制表示する字幕を設定（セグメント選択時用）."""
        self._forced_subtitle = subtitle

    def clear_forced_subtitle(self) -> None:
        """強制表示をクリア."""
        self._forced_subtitle = None

    def _get_current_subtitle(self, position_ms: int) -> Optional[SubtitleEntry]:
        """現在位置の字幕を取得."""
        for sub in self._subtitles:
            if sub.start_ms <= position_ms <= sub.end_ms:
                return sub
        return None

    def _draw_subtitle_on_frame(
        self,
        frame: np.ndarray,
        subtitle: SubtitleEntry,
    ) -> np.ndarray:
        """フレームに字幕を描画."""
        if not subtitle or not subtitle.text:
            return frame

        # OpenCV BGR -> PIL RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        draw = ImageDraw.Draw(pil_image)

        text = subtitle.text.replace("\\N", "\n").replace("\\n", "\n")
        h, w = frame.shape[:2]

        # テキストサイズを取得
        bbox = draw.textbbox((0, 0), text, font=self._subtitle_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 位置を計算
        x = (w - text_width) // 2
        if self._subtitle_style["position"] == "bottom":
            y = h - text_height - self._subtitle_style["margin"]
        elif self._subtitle_style["position"] == "top":
            y = self._subtitle_style["margin"]
        else:  # center
            y = (h - text_height) // 2

        # アウトライン（縁取り）を描画
        outline_width = self._subtitle_style["outline_width"]
        outline_color = self._subtitle_style["outline_color"]
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    draw.text(
                        (x + dx, y + dy),
                        text,
                        font=self._subtitle_font,
                        fill=outline_color,
                    )

        # メインテキストを描画
        draw.text(
            (x, y),
            text,
            font=self._subtitle_font,
            fill=self._subtitle_style["font_color"],
        )

        # PIL -> OpenCV BGR
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    def _show_frame(self, frame_number: int) -> None:
        """指定フレームを表示."""
        if self._cap is None:
            return

        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self._cap.read()

        if not ret:
            return

        self._current_frame = frame_number
        position_ms = int((frame_number / self._fps) * 1000)

        # 字幕を描画（強制表示が設定されていればそれを使用）
        if self._forced_subtitle:
            current_sub = self._forced_subtitle
        else:
            current_sub = self._get_current_subtitle(position_ms)

        if current_sub:
            frame = self._draw_subtitle_on_frame(frame, current_sub)
            self._current_subtitle = current_sub

        # リサイズ
        frame_h, frame_w = frame.shape[:2]
        scale = min(self._width / frame_w, self._height / frame_h)
        new_w = int(frame_w * scale)
        new_h = int(frame_h * scale)
        frame = cv2.resize(frame, (new_w, new_h))

        # OpenCV BGR -> RGB -> PIL -> PhotoImage
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        self._photo = ImageTk.PhotoImage(pil_image)

        # キャンバスに表示
        self._canvas.delete("all")
        x_offset = (self._width - new_w) // 2
        y_offset = (self._height - new_h) // 2
        self._canvas.create_image(x_offset, y_offset, anchor="nw", image=self._photo)

        # コールバック
        if self._on_position_change:
            self._on_position_change(position_ms)

    def play(self) -> None:
        """再生開始."""
        if self._cap is None or self._is_playing:
            return

        # 再生開始時は強制字幕をクリア
        self._forced_subtitle = None

        self._is_playing = True
        self._stop_flag = False

        if self._on_play_state_change:
            self._on_play_state_change(True)

        self._play_thread = threading.Thread(target=self._play_loop, daemon=True)
        self._play_thread.start()

    def _play_loop(self) -> None:
        """再生ループ."""
        frame_interval = 1.0 / self._fps

        while not self._stop_flag and self._current_frame < self._total_frames - 1:
            start_time = time.time()

            self._current_frame += 1
            self.after(0, lambda f=self._current_frame: self._show_frame(f))

            # フレームレート維持
            elapsed = time.time() - start_time
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        self._is_playing = False
        if self._on_play_state_change:
            self.after(0, lambda: self._on_play_state_change(False))

    def pause(self) -> None:
        """一時停止."""
        self._stop_flag = True
        self._is_playing = False

        if self._on_play_state_change:
            self._on_play_state_change(False)

    def stop(self) -> None:
        """停止."""
        self._stop_flag = True
        self._is_playing = False

        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=1.0)

        self._current_frame = 0

        if self._on_play_state_change:
            self._on_play_state_change(False)

    def seek(self, position_ms: int) -> None:
        """指定位置にシーク."""
        if self._cap is None:
            return

        frame_number = int((position_ms / 1000.0) * self._fps)
        frame_number = max(0, min(frame_number, self._total_frames - 1))
        self._show_frame(frame_number)

    def seek_frame(self, frame_number: int) -> None:
        """指定フレームにシーク."""
        if self._cap is None:
            return

        frame_number = max(0, min(frame_number, self._total_frames - 1))
        self._show_frame(frame_number)

    def get_position_ms(self) -> int:
        """現在位置をミリ秒で取得."""
        return int((self._current_frame / self._fps) * 1000)

    def get_duration_ms(self) -> int:
        """動画の長さをミリ秒で取得."""
        return self._duration_ms

    def is_playing(self) -> bool:
        """再生中かどうか."""
        return self._is_playing

    def set_on_position_change(self, callback: Callable[[int], None]) -> None:
        """位置変更コールバックを設定."""
        self._on_position_change = callback

    def set_on_play_state_change(self, callback: Callable[[bool], None]) -> None:
        """再生状態変更コールバックを設定."""
        self._on_play_state_change = callback

    def destroy(self) -> None:
        """クリーンアップ."""
        self.stop()
        if self._cap:
            self._cap.release()
        super().destroy()
