"""
Nani-inspired Design System for CustomTkinter
==============================================

nani.now のデザインからインスパイアされたデザインシステム。
清潔感のある白基調に、鮮やかな青をアクセントカラーとして使用。
柔らかな角丸と軽やかな影で、モダンで親しみやすい印象を演出。
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ColorPalette:
    """
    Nani-inspired カラーパレット

    特徴:
    - 清潔感のある白基調
    - 鮮やかなスカイブルーをアクセントに
    - グレーのトーンで階層を表現
    """

    # === Primary Colors (青系 - メインアクセント) ===
    PRIMARY: str = "#24AFFF"           # メインの青（ボタン、リンク）
    PRIMARY_DARK: str = "#099BFF"      # ホバー時の青
    PRIMARY_DARKER: str = "#0089F2"    # アクティブ時の青
    PRIMARY_LIGHT: str = "#3BB7FF"     # 明るい青
    PRIMARY_BG: str = "#EBF6FF"        # 青の背景色（薄い）
    PRIMARY_BG_DARK: str = "#E5F3FF"   # 青の背景色（やや濃い）

    # === Background Colors (背景) ===
    BG_MAIN: str = "#FFFFFF"           # メイン背景（白）
    BG_SECONDARY: str = "#F6F9FB"      # セカンダリ背景（うすいグレー）
    BG_TERTIARY: str = "#F1F6F9"       # サードレベル背景
    BG_CARD: str = "#FFFFFF"           # カード背景
    BG_SIDEBAR: str = "#F3F8FB"        # サイドバー背景
    BG_HOVER: str = "#E9EEF1"          # ホバー時の背景

    # === Text Colors (テキスト) ===
    TEXT_PRIMARY: str = "#080D12"      # メインテキスト（ほぼ黒）
    TEXT_SECONDARY: str = "#4B5256"    # セカンダリテキスト
    TEXT_TERTIARY: str = "#6F767A"     # サードテキスト
    TEXT_MUTED: str = "#7F8B91"        # ミュートテキスト
    TEXT_PLACEHOLDER: str = "#93A0A7"  # プレースホルダー
    TEXT_LIGHT: str = "#99A2A7"        # 薄いテキスト
    TEXT_ON_PRIMARY: str = "#FFFFFF"   # 青ボタン上のテキスト

    # === Border Colors (ボーダー) ===
    BORDER_LIGHT: str = "#E9EEF1"      # 薄いボーダー
    BORDER_DEFAULT: str = "#E2EAEE"    # デフォルトボーダー
    BORDER_DARK: str = "#CAD3D8"       # 濃いボーダー
    BORDER_FOCUS: str = "#24AFFF"      # フォーカス時のボーダー

    # === Accent Colors (アクセント) ===
    ACCENT_ORANGE: str = "#FFA861"     # オレンジ（警告、注目）
    ACCENT_ORANGE_BG: str = "#FEF8EF"  # オレンジ背景
    ACCENT_PURPLE: str = "#6F8CFF"     # パープル（特別な要素）

    # === Status Colors (ステータス) ===
    SUCCESS: str = "#10B981"           # 成功（グリーン）
    SUCCESS_BG: str = "#ECFDF5"        # 成功背景
    WARNING: str = "#F59E0B"           # 警告（イエロー）
    WARNING_BG: str = "#FFFBEB"        # 警告背景
    DANGER: str = "#FF6161"            # エラー（レッド）
    DANGER_BG: str = "#FEF2F3"         # エラー背景
    DANGER_DARK: str = "#FF4D4D"       # エラーダーク
    INFO: str = "#24AFFF"              # 情報（ブルー）
    INFO_BG: str = "#EBF6FF"           # 情報背景

    # === Gradient Stops (グラデーション) ===
    GRADIENT_START: str = "#F8FCFF"    # グラデーション開始
    GRADIENT_END: str = "#E4F2FF"      # グラデーション終了

    # === Dark Mode Colors (ダークモード用) ===
    DARK_BG_MAIN: str = "#0F1419"      # ダークモード背景
    DARK_BG_SECONDARY: str = "#1A2027" # ダークモードセカンダリ背景
    DARK_BG_CARD: str = "#1F262D"      # ダークモードカード
    DARK_TEXT_PRIMARY: str = "#F1F6F9" # ダークモードテキスト
    DARK_TEXT_SECONDARY: str = "#99A2A7"
    DARK_BORDER: str = "#2A3540"       # ダークモードボーダー


@dataclass(frozen=True)
class Typography:
    """
    タイポグラフィ設定

    nani.now は Inter フォントを使用。
    日本語は Hiragino Kaku Gothic ProN をフォールバック。
    """

    # === Font Families ===
    FONT_FAMILY_PRIMARY: str = "Inter"
    FONT_FAMILY_FALLBACK: str = "Hiragino Kaku Gothic ProN"
    FONT_FAMILY_SYSTEM: str = "system-ui"

    # === Font Sizes (px) ===
    SIZE_XS: int = 11
    SIZE_SM: int = 13
    SIZE_BASE: int = 14
    SIZE_MD: int = 16
    SIZE_LG: int = 18
    SIZE_XL: int = 20
    SIZE_2XL: int = 24
    SIZE_3XL: int = 30
    SIZE_4XL: int = 36

    # === Font Weights ===
    WEIGHT_NORMAL: str = "normal"
    WEIGHT_MEDIUM: str = "medium"  # CustomTkinterでは効かないことも
    WEIGHT_BOLD: str = "bold"

    # === Line Heights (multiplier) ===
    LINE_HEIGHT_TIGHT: float = 1.25
    LINE_HEIGHT_NORMAL: float = 1.5
    LINE_HEIGHT_RELAXED: float = 1.75


@dataclass(frozen=True)
class Spacing:
    """
    スペーシングシステム

    8px ベースのスペーシング。
    """

    # === Base Unit ===
    UNIT: int = 8

    # === Named Spacing ===
    NONE: int = 0
    XS: int = 4      # 0.5 unit
    SM: int = 8      # 1 unit
    MD: int = 12     # 1.5 unit
    BASE: int = 16   # 2 units
    LG: int = 20     # 2.5 units
    XL: int = 24     # 3 units
    XXL: int = 32    # 4 units
    XXXL: int = 48   # 6 units

    # === Component Specific ===
    PADDING_BUTTON: Tuple[int, int] = (16, 10)   # (horizontal, vertical)
    PADDING_INPUT: Tuple[int, int] = (12, 10)
    PADDING_CARD: int = 20
    PADDING_SECTION: int = 32

    GAP_SM: int = 8
    GAP_MD: int = 12
    GAP_LG: int = 16
    GAP_XL: int = 24


@dataclass(frozen=True)
class BorderRadius:
    """
    角丸設定

    nani.now は比較的大きめの角丸を使用。
    柔らかく親しみやすい印象を演出。
    """

    NONE: int = 0
    SM: int = 4
    DEFAULT: int = 8
    MD: int = 10
    LG: int = 12
    XL: int = 16
    XXL: int = 20
    PILL: int = 9999   # 完全な丸（ボタンなど）
    CIRCLE: str = "50%"


@dataclass(frozen=True)
class Shadows:
    """
    シャドウ設定

    nani.now は青みがかった柔らかい影を使用。
    rgba(0, 20, 40, alpha) のような色味。

    ※ CustomTkinterでは直接シャドウを使えないため、
      代替手法（重なり、グラデーション）で表現する際の参考値。
    """

    # シャドウの色 (参考)
    SHADOW_COLOR: str = "#001428"

    # シャドウ定義 (CSS形式 - 参考用)
    XS: str = "0 2px 3px -1.5px rgba(0, 20, 40, 0.05)"
    SM: str = "0 2px 5px -2px rgba(0, 20, 40, 0.08)"
    MD: str = "0 2px 8px -1px rgba(0, 20, 40, 0.07)"
    LG: str = "0 6px 14px 0 rgba(0, 20, 40, 0.08)"
    XL: str = "0 0 18px 0 rgba(0, 20, 40, 0.13)"


@dataclass(frozen=True)
class Animation:
    """
    アニメーション設定

    nani.now は滑らかで自然なアニメーションを使用。
    主に 0.2s~0.3s の短いトランジション。

    ※ CustomTkinterではafter()メソッドでアニメーションを実装。
    """

    # === Duration (ms) ===
    DURATION_FAST: int = 150
    DURATION_DEFAULT: int = 200
    DURATION_SLOW: int = 300
    DURATION_SLOWER: int = 500

    # === Easing (参考 - Pythonでの実装時に活用) ===
    # cubic-bezier(0.4, 0, 0.2, 1) - Material Design standard
    EASE_DEFAULT: str = "ease-out"

    # === Animation Steps (フレーム数の目安) ===
    STEPS_FAST: int = 10
    STEPS_DEFAULT: int = 15
    STEPS_SLOW: int = 20


class NaniTheme:
    """
    Nani-inspired テーマをCustomTkinterに適用するためのユーティリティクラス
    """

    colors = ColorPalette()
    typography = Typography()
    spacing = Spacing()
    radius = BorderRadius()
    shadows = Shadows()
    animation = Animation()

    @classmethod
    def get_button_style(cls, variant: str = "primary") -> dict:
        """
        ボタンスタイルを取得

        Args:
            variant: "primary", "secondary", "outline", "ghost", "danger"
        """
        styles = {
            "primary": {
                "fg_color": cls.colors.PRIMARY,
                "hover_color": cls.colors.PRIMARY_DARK,
                "text_color": cls.colors.TEXT_ON_PRIMARY,
                "corner_radius": cls.radius.MD,
            },
            "secondary": {
                "fg_color": cls.colors.BG_SECONDARY,
                "hover_color": cls.colors.BG_HOVER,
                "text_color": cls.colors.TEXT_PRIMARY,
                "corner_radius": cls.radius.MD,
            },
            "outline": {
                "fg_color": "transparent",
                "hover_color": cls.colors.PRIMARY_BG,
                "text_color": cls.colors.PRIMARY,
                "border_width": 1,
                "border_color": cls.colors.PRIMARY,
                "corner_radius": cls.radius.MD,
            },
            "ghost": {
                "fg_color": "transparent",
                "hover_color": cls.colors.BG_HOVER,
                "text_color": cls.colors.TEXT_PRIMARY,
                "corner_radius": cls.radius.MD,
            },
            "danger": {
                "fg_color": cls.colors.DANGER,
                "hover_color": cls.colors.DANGER_DARK,
                "text_color": cls.colors.TEXT_ON_PRIMARY,
                "corner_radius": cls.radius.MD,
            },
        }
        return styles.get(variant, styles["primary"])

    @classmethod
    def get_input_style(cls) -> dict:
        """入力フィールドのスタイル"""
        return {
            "fg_color": cls.colors.BG_MAIN,
            "border_color": cls.colors.BORDER_DEFAULT,
            "text_color": cls.colors.TEXT_PRIMARY,
            "placeholder_text_color": cls.colors.TEXT_PLACEHOLDER,
            "corner_radius": cls.radius.MD,
            "border_width": 1,
        }

    @classmethod
    def get_card_style(cls) -> dict:
        """カードのスタイル"""
        return {
            "fg_color": cls.colors.BG_CARD,
            "corner_radius": cls.radius.LG,
            "border_width": 1,
            "border_color": cls.colors.BORDER_LIGHT,
        }

    @classmethod
    def get_sidebar_style(cls) -> dict:
        """サイドバーのスタイル"""
        return {
            "fg_color": cls.colors.BG_SIDEBAR,
            "corner_radius": 0,
        }

    @classmethod
    def get_font(cls, size: str = "base", weight: str = "normal") -> tuple:
        """
        フォント設定を取得

        Args:
            size: "xs", "sm", "base", "md", "lg", "xl", "2xl", "3xl", "4xl"
            weight: "normal", "bold"
        """
        size_map = {
            "xs": cls.typography.SIZE_XS,
            "sm": cls.typography.SIZE_SM,
            "base": cls.typography.SIZE_BASE,
            "md": cls.typography.SIZE_MD,
            "lg": cls.typography.SIZE_LG,
            "xl": cls.typography.SIZE_XL,
            "2xl": cls.typography.SIZE_2XL,
            "3xl": cls.typography.SIZE_3XL,
            "4xl": cls.typography.SIZE_4XL,
        }
        font_size = size_map.get(size, cls.typography.SIZE_BASE)
        font_weight = weight if weight in ("normal", "bold") else "normal"

        return (cls.typography.FONT_FAMILY_PRIMARY, font_size, font_weight)

    @classmethod
    def get_label_style(cls, variant: str = "default") -> dict:
        """ラベルのスタイル"""
        styles = {
            "default": {
                "text_color": cls.colors.TEXT_PRIMARY,
                "font": cls.get_font("base"),
            },
            "secondary": {
                "text_color": cls.colors.TEXT_SECONDARY,
                "font": cls.get_font("sm"),
            },
            "muted": {
                "text_color": cls.colors.TEXT_MUTED,
                "font": cls.get_font("sm"),
            },
            "caption": {
                "text_color": cls.colors.TEXT_MUTED,
                "font": cls.get_font("xs"),
            },
            "subtitle": {
                "text_color": cls.colors.TEXT_PRIMARY,
                "font": cls.get_font("md", "bold"),
            },
            "heading": {
                "text_color": cls.colors.TEXT_PRIMARY,
                "font": cls.get_font("xl", "bold"),
            },
            "title": {
                "text_color": cls.colors.TEXT_PRIMARY,
                "font": cls.get_font("2xl", "bold"),
            },
        }
        return styles.get(variant, styles["default"])

    @classmethod
    def get_progress_style(cls) -> dict:
        """プログレスバーのスタイル"""
        return {
            "fg_color": cls.colors.BG_SECONDARY,
            "progress_color": cls.colors.PRIMARY,
            "corner_radius": cls.radius.PILL,
        }

    @classmethod
    def get_switch_style(cls) -> dict:
        """スイッチのスタイル"""
        return {
            "fg_color": cls.colors.BORDER_DARK,
            "progress_color": cls.colors.PRIMARY,
            "button_color": cls.colors.BG_MAIN,
            "button_hover_color": cls.colors.BG_SECONDARY,
        }

    @classmethod
    def get_tag_style(cls, variant: str = "default") -> dict:
        """タグ/バッジのスタイル"""
        styles = {
            "default": {
                "fg_color": cls.colors.BG_SECONDARY,
                "text_color": cls.colors.TEXT_SECONDARY,
                "corner_radius": cls.radius.SM,
            },
            "primary": {
                "fg_color": cls.colors.PRIMARY_BG,
                "text_color": cls.colors.PRIMARY_DARK,
                "corner_radius": cls.radius.SM,
            },
            "success": {
                "fg_color": cls.colors.SUCCESS_BG,
                "text_color": cls.colors.SUCCESS,
                "corner_radius": cls.radius.SM,
            },
            "warning": {
                "fg_color": cls.colors.WARNING_BG,
                "text_color": cls.colors.WARNING,
                "corner_radius": cls.radius.SM,
            },
            "danger": {
                "fg_color": cls.colors.DANGER_BG,
                "text_color": cls.colors.DANGER,
                "corner_radius": cls.radius.SM,
            },
            "wip": {
                "fg_color": cls.colors.ACCENT_ORANGE_BG,
                "text_color": cls.colors.ACCENT_ORANGE,
                "corner_radius": cls.radius.SM,
            },
            "beta": {
                "fg_color": "#F3F0FF",
                "text_color": cls.colors.ACCENT_PURPLE,
                "corner_radius": cls.radius.SM,
            },
            "done": {
                "fg_color": cls.colors.SUCCESS_BG,
                "text_color": cls.colors.SUCCESS,
                "corner_radius": cls.radius.SM,
            },
        }
        return styles.get(variant, styles["default"])


# === Quick Access Shortcuts ===
COLORS = NaniTheme.colors
TYPOGRAPHY = NaniTheme.typography
SPACING = NaniTheme.spacing
RADIUS = NaniTheme.radius


def apply_nani_theme():
    """
    CustomTkinterにNaniテーマを適用する

    使用例:
        import customtkinter as ctk
        from src.gui.theme import apply_nani_theme

        apply_nani_theme()

        app = ctk.CTk()
        ...
    """
    import customtkinter as ctk

    # アピアランスモードの設定
    ctk.set_appearance_mode("light")

    # デフォルトカラーテーマの上書き
    # Note: CustomTkinterは限定的なテーマカスタマイズしかサポートしていない
    # 完全なカスタマイズには各ウィジェット生成時に個別にスタイルを適用する必要がある

    # JSONテーマファイルを使う方法もあるが、
    # より柔軟な制御のため、このモジュールの関数を使ってスタイルを適用することを推奨
    pass
