"""
Animation Utilities for CustomTkinter
======================================

nani.now のような滑らかなアニメーションを
CustomTkinterで実現するためのユーティリティ。

CustomTkinterは組み込みのアニメーションを持たないため、
after()メソッドを使って手動でアニメーションを実装する。
"""

from typing import Callable, Any, Optional
import math


class EasingFunctions:
    """
    イージング関数コレクション

    nani.now で使用されているイージングを再現:
    - cubic-bezier(0.4, 0, 0.2, 1) - ease-out (Material Design)
    - linear easing with bounce
    """

    @staticmethod
    def linear(t: float) -> float:
        """線形補間"""
        return t

    @staticmethod
    def ease_out(t: float) -> float:
        """
        イーズアウト (減速)
        cubic-bezier(0.4, 0, 0.2, 1) の近似
        """
        return 1 - (1 - t) ** 3

    @staticmethod
    def ease_in(t: float) -> float:
        """イーズイン (加速)"""
        return t ** 3

    @staticmethod
    def ease_in_out(t: float) -> float:
        """イーズインアウト"""
        if t < 0.5:
            return 4 * t ** 3
        else:
            return 1 - ((-2 * t + 2) ** 3) / 2

    @staticmethod
    def bounce_out(t: float) -> float:
        """
        バウンスアウト
        nani.now の "bouncy" アニメーションに近い
        """
        n1 = 7.5625
        d1 = 2.75

        if t < 1 / d1:
            return n1 * t * t
        elif t < 2 / d1:
            t -= 1.5 / d1
            return n1 * t * t + 0.75
        elif t < 2.5 / d1:
            t -= 2.25 / d1
            return n1 * t * t + 0.9375
        else:
            t -= 2.625 / d1
            return n1 * t * t + 0.984375

    @staticmethod
    def elastic_out(t: float) -> float:
        """エラスティックアウト (ゴムのような動き)"""
        if t == 0:
            return 0
        if t == 1:
            return 1
        p = 0.3
        s = p / 4
        return math.pow(2, -10 * t) * math.sin((t - s) * (2 * math.pi) / p) + 1

    @staticmethod
    def spring(t: float, damping: float = 0.5, stiffness: float = 100) -> float:
        """
        スプリングアニメーション
        nani.now のlinear() easingに近い挙動
        """
        # 簡易的なスプリング近似
        return 1 - math.exp(-t * 6) * math.cos(t * 10 * (1 - damping))


class Animator:
    """
    CustomTkinterウィジェットのアニメーションを管理するクラス

    使用例:
        animator = Animator(widget)

        # フェードイン
        animator.fade_in(duration=200)

        # 位置移動
        animator.move_to(x=100, y=50, duration=300)

        # カスタムプロパティのアニメーション
        animator.animate(
            property_name="fg_color",
            start_value="#FFFFFF",
            end_value="#24AFFF",
            duration=200
        )
    """

    def __init__(self, widget):
        """
        Args:
            widget: CustomTkinterウィジェット
        """
        self.widget = widget
        self._animation_id: Optional[str] = None
        self._is_animating: bool = False

    def stop(self):
        """現在のアニメーションを停止"""
        if self._animation_id:
            try:
                self.widget.after_cancel(self._animation_id)
            except Exception:
                pass
            self._animation_id = None
        self._is_animating = False

    def animate_value(
        self,
        start: float,
        end: float,
        duration: int,
        on_update: Callable[[float], None],
        on_complete: Optional[Callable[[], None]] = None,
        easing: Callable[[float], float] = EasingFunctions.ease_out,
        fps: int = 60,
    ):
        """
        汎用的な値のアニメーション

        Args:
            start: 開始値
            end: 終了値
            duration: アニメーション時間 (ミリ秒)
            on_update: 各フレームで呼ばれるコールバック (現在の値を受け取る)
            on_complete: アニメーション完了時のコールバック
            easing: イージング関数
            fps: フレームレート
        """
        self.stop()
        self._is_animating = True

        frame_duration = 1000 // fps
        total_frames = max(1, duration // frame_duration)
        current_frame = 0

        def update():
            nonlocal current_frame

            if not self._is_animating:
                return

            progress = current_frame / total_frames
            eased_progress = easing(min(1.0, progress))
            current_value = start + (end - start) * eased_progress

            try:
                on_update(current_value)
            except Exception:
                self.stop()
                return

            current_frame += 1

            if current_frame <= total_frames:
                self._animation_id = self.widget.after(frame_duration, update)
            else:
                self._is_animating = False
                if on_complete:
                    on_complete()

        update()

    def fade_in(
        self,
        duration: int = 200,
        on_complete: Optional[Callable[[], None]] = None,
    ):
        """
        フェードインアニメーション

        Note: CustomTkinterは直接的な透明度制御をサポートしていないため、
              背景色のアルファ値や見える/見えないの切り替えで近似する。
        """
        # 簡易的な実装: ウィジェットを表示
        try:
            self.widget.configure(fg_color=self.widget.cget("fg_color"))
        except Exception:
            pass

        if on_complete:
            self.widget.after(duration, on_complete)

    def scale_in(
        self,
        duration: int = 200,
        start_scale: float = 0.95,
        on_complete: Optional[Callable[[], None]] = None,
    ):
        """
        スケールインアニメーション（擬似的）

        Note: CustomTkinterはスケール変換をサポートしていないため、
              サイズの変更で近似。
        """
        # 実装は限定的。フォントサイズやパディングの変更で近似可能
        if on_complete:
            self.widget.after(duration, on_complete)

    def slide_in(
        self,
        direction: str = "up",
        distance: int = 20,
        duration: int = 200,
        on_complete: Optional[Callable[[], None]] = None,
    ):
        """
        スライドインアニメーション

        Args:
            direction: "up", "down", "left", "right"
            distance: 移動距離 (ピクセル)
            duration: アニメーション時間 (ミリ秒)
        """
        # place()を使用している場合のみ機能
        try:
            info = self.widget.place_info()
            if not info:
                if on_complete:
                    on_complete()
                return

            current_x = int(info.get("x", 0))
            current_y = int(info.get("y", 0))

            if direction == "up":
                start_y = current_y + distance
                end_y = current_y
                start_x = end_x = current_x
            elif direction == "down":
                start_y = current_y - distance
                end_y = current_y
                start_x = end_x = current_x
            elif direction == "left":
                start_x = current_x + distance
                end_x = current_x
                start_y = end_y = current_y
            else:  # right
                start_x = current_x - distance
                end_x = current_x
                start_y = end_y = current_y

            # 初期位置に移動
            self.widget.place(x=start_x, y=start_y)

            def update_position(progress: float):
                x = start_x + (end_x - start_x) * progress
                y = start_y + (end_y - start_y) * progress
                self.widget.place(x=int(x), y=int(y))

            self.animate_value(
                start=0,
                end=1,
                duration=duration,
                on_update=update_position,
                on_complete=on_complete,
            )

        except Exception:
            if on_complete:
                on_complete()


def animate_color_transition(
    widget,
    property_name: str,
    start_color: str,
    end_color: str,
    duration: int = 200,
    on_complete: Optional[Callable[[], None]] = None,
):
    """
    色のトランジションアニメーション

    Args:
        widget: CustomTkinterウィジェット
        property_name: "fg_color", "text_color", "border_color" など
        start_color: 開始色 (hex)
        end_color: 終了色 (hex)
        duration: アニメーション時間 (ミリ秒)
    """

    def hex_to_rgb(hex_color: str) -> tuple:
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    def rgb_to_hex(rgb: tuple) -> str:
        return "#{:02x}{:02x}{:02x}".format(
            max(0, min(255, int(rgb[0]))),
            max(0, min(255, int(rgb[1]))),
            max(0, min(255, int(rgb[2]))),
        )

    start_rgb = hex_to_rgb(start_color)
    end_rgb = hex_to_rgb(end_color)

    animator = Animator(widget)

    def update_color(progress: float):
        current_rgb = tuple(
            start_rgb[i] + (end_rgb[i] - start_rgb[i]) * progress for i in range(3)
        )
        try:
            widget.configure(**{property_name: rgb_to_hex(current_rgb)})
        except Exception:
            pass

    animator.animate_value(
        start=0,
        end=1,
        duration=duration,
        on_update=update_color,
        on_complete=on_complete,
    )

    return animator


def create_hover_effect(
    widget,
    normal_color: str,
    hover_color: str,
    property_name: str = "fg_color",
    duration: int = 150,
):
    """
    ホバーエフェクトを追加

    Args:
        widget: CustomTkinterウィジェット
        normal_color: 通常時の色
        hover_color: ホバー時の色
        property_name: 変更するプロパティ
        duration: トランジション時間
    """
    current_animator: Optional[Animator] = None

    def on_enter(event):
        nonlocal current_animator
        if current_animator:
            current_animator.stop()
        current_animator = animate_color_transition(
            widget, property_name, normal_color, hover_color, duration
        )

    def on_leave(event):
        nonlocal current_animator
        if current_animator:
            current_animator.stop()
        current_animator = animate_color_transition(
            widget, property_name, hover_color, normal_color, duration
        )

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


def create_press_effect(
    widget,
    normal_color: str,
    press_color: str,
    property_name: str = "fg_color",
):
    """
    プレスエフェクト（クリック時）を追加

    nani.now のボタンはクリック時に少し暗くなる。
    """

    def on_press(event):
        try:
            widget.configure(**{property_name: press_color})
        except Exception:
            pass

    def on_release(event):
        try:
            widget.configure(**{property_name: normal_color})
        except Exception:
            pass

    widget.bind("<ButtonPress-1>", on_press)
    widget.bind("<ButtonRelease-1>", on_release)
