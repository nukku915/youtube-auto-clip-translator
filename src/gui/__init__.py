"""
GUI Module - Nani-inspired Design System
========================================

nani.now からインスパイアされたデザインシステムを提供。
"""

from .app import App, main
from .theme import (
    NaniTheme,
    ColorPalette,
    Typography,
    Spacing,
    BorderRadius,
    Shadows,
    Animation,
    COLORS,
    TYPOGRAPHY,
    SPACING,
    RADIUS,
    apply_nani_theme,
)

from .animation import (
    EasingFunctions,
    Animator,
    animate_color_transition,
    create_hover_effect,
    create_press_effect,
)

from .widgets import (
    NaniButton,
    NaniEntry,
    NaniTextbox,
    NaniLabel,
    NaniCard,
    NaniProgressBar,
    NaniSwitch,
    NaniTag,
    NaniSegmentedButton,
    NaniSidebar,
    NaniScrollableFrame,
    NaniOptionMenu,
    create_section_header,
    create_form_field,
    create_button_group,
)

__all__ = [
    # App
    "App",
    "main",
    # Theme
    "NaniTheme",
    "ColorPalette",
    "Typography",
    "Spacing",
    "BorderRadius",
    "Shadows",
    "Animation",
    "COLORS",
    "TYPOGRAPHY",
    "SPACING",
    "RADIUS",
    "apply_nani_theme",
    # Animation
    "EasingFunctions",
    "Animator",
    "animate_color_transition",
    "create_hover_effect",
    "create_press_effect",
    # Widgets
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
    "create_section_header",
    "create_form_field",
    "create_button_group",
]
