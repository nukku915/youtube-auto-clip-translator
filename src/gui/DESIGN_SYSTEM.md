# Nani-inspired デザインシステム

nani.now からインスパイアされた、YouTube Auto Clip Translator のデザインシステム。

## デザイン分析結果

### 全体の印象

nani.now は以下の特徴を持つモダンで洗練されたデザイン:

- **清潔感**: 白基調の背景、十分な余白
- **親しみやすさ**: 大きめの角丸、マスコットキャラクター
- **視認性**: 明確なコントラスト、読みやすいフォント
- **軽やかさ**: 柔らかい影、淡いグラデーション

---

## カラーパレット

### Primary Colors (青系)
| 名前 | 色コード | 用途 |
|------|---------|------|
| PRIMARY | `#24AFFF` | ボタン、リンク、アクセント |
| PRIMARY_DARK | `#099BFF` | ホバー状態 |
| PRIMARY_DARKER | `#0089F2` | アクティブ状態 |
| PRIMARY_BG | `#EBF6FF` | 青の背景（薄い） |

### Background Colors
| 名前 | 色コード | 用途 |
|------|---------|------|
| BG_MAIN | `#FFFFFF` | メイン背景 |
| BG_SECONDARY | `#F6F9FB` | サイドバー、セカンダリ |
| BG_HOVER | `#E9EEF1` | ホバー時 |

### Text Colors
| 名前 | 色コード | 用途 |
|------|---------|------|
| TEXT_PRIMARY | `#080D12` | 見出し、本文 |
| TEXT_SECONDARY | `#4B5256` | 説明文 |
| TEXT_MUTED | `#7F8B91` | ヒント、注釈 |
| TEXT_PLACEHOLDER | `#93A0A7` | プレースホルダー |

### Accent Colors
| 名前 | 色コード | 用途 |
|------|---------|------|
| ORANGE | `#FFA861` | WIP、注目要素 |
| PURPLE | `#6F8CFF` | Beta、特別な要素 |
| DANGER | `#FF6161` | エラー、削除 |
| SUCCESS | `#10B981` | 成功、完了 |

---

## タイポグラフィ

### フォントファミリー
```
Primary: Inter
Fallback: Hiragino Kaku Gothic ProN, Hiragino Sans, Noto Sans JP
```

### フォントサイズ
| 名前 | サイズ | 用途 |
|------|-------|------|
| xs | 11px | タグ、バッジ |
| sm | 13px | 補助テキスト |
| base | 14px | 本文 |
| md | 16px | 強調テキスト |
| lg | 18px | サブ見出し |
| xl | 20px | セクション見出し |
| 2xl | 24px | ページタイトル |

---

## スペーシング

8px ベースのスペーシングシステム:

| 名前 | 値 | 用途 |
|------|-----|------|
| xs | 4px | タイトな間隔 |
| sm | 8px | 小さな間隔 |
| md | 12px | 中間の間隔 |
| base | 16px | デフォルト |
| lg | 20px | やや大きい間隔 |
| xl | 24px | セクション間 |
| xxl | 32px | 大きなセクション間 |

---

## 角丸 (Border Radius)

| 名前 | 値 | 用途 |
|------|-----|------|
| sm | 4px | タグ、小さい要素 |
| default | 8px | 入力フィールド |
| md | 10px | ボタン |
| lg | 12px | カード |
| xl | 16px | モーダル |
| pill | 9999px | 丸いボタン |

---

## アニメーション

### トランジション
- **Duration**: 150ms〜300ms
- **Easing**: `cubic-bezier(0.4, 0, 0.2, 1)` (ease-out)

### 主なアニメーション
1. **ホバー**: 背景色のフェード (150ms)
2. **フェードイン**: opacity 0→1 (300ms)
3. **スライドイン**: translateY 20px→0 (300ms)
4. **スケール**: scale 0.95→1 (200ms)

---

## 使用例

### 基本的な使い方

```python
import customtkinter as ctk
from src.gui.theme import apply_nani_theme, NaniTheme, COLORS
from src.gui.widgets import (
    NaniButton, NaniEntry, NaniLabel, NaniCard,
    NaniTag, NaniProgressBar
)

# テーマを適用
apply_nani_theme()

# アプリ作成
app = ctk.CTk()
app.title("YouTube Auto Clip Translator")
app.configure(fg_color=COLORS.BG_MAIN)

# ボタン
primary_btn = NaniButton(app, text="翻訳開始", variant="primary")
primary_btn.pack(pady=10)

secondary_btn = NaniButton(app, text="キャンセル", variant="secondary")
secondary_btn.pack(pady=10)

# 入力フィールド
entry = NaniEntry(app, placeholder_text="URLを入力...", width=300)
entry.pack(pady=10)

# ラベル
title = NaniLabel(app, text="翻訳設定", variant="heading")
title.pack(pady=10)

# カード
card = NaniCard(app)
card.pack(pady=10, padx=20, fill="x")

# タグ
tag_wip = NaniTag(card, text="WIP", variant="wip")
tag_wip.pack(side="left", padx=5)

tag_done = NaniTag(card, text="done", variant="done")
tag_done.pack(side="left", padx=5)

# プログレスバー
progress = NaniProgressBar(app)
progress.pack(pady=10)
progress.set(0.7)

app.mainloop()
```

### カスタムスタイルの適用

```python
from src.gui.theme import NaniTheme

# ボタンスタイルを取得してカスタマイズ
button_style = NaniTheme.get_button_style("primary")

# フォント設定
heading_font = NaniTheme.get_font("xl", "bold")
body_font = NaniTheme.get_font("base")

# 入力フィールドスタイル
input_style = NaniTheme.get_input_style()
```

### アニメーションの追加

```python
from src.gui.animation import (
    Animator, create_hover_effect, animate_color_transition
)

# ホバーエフェクト
create_hover_effect(
    button,
    normal_color=COLORS.PRIMARY,
    hover_color=COLORS.PRIMARY_DARK
)

# 色のトランジション
animate_color_transition(
    widget,
    property_name="fg_color",
    start_color="#FFFFFF",
    end_color="#24AFFF",
    duration=200
)

# カスタムアニメーション
animator = Animator(widget)
animator.slide_in(direction="up", distance=20, duration=300)
```

---

## ファイル構成

```
src/gui/
├── __init__.py
├── theme.py          # カラー、タイポグラフィ、スペーシング定義
├── animation.py      # アニメーションユーティリティ
├── widgets.py        # スタイル適用済みウィジェット
├── components/       # 複合コンポーネント
│   └── __init__.py
├── views/            # 画面
│   └── __init__.py
└── DESIGN_SYSTEM.md  # このドキュメント
```

---

## 参考: nani.now の CSS 変数

実際にサイトから抽出した CSS 変数:

```css
--color-primary: #24afff;
--color-primary-dark: #099bff;
--color-primary-bg: #ebf6ff;
--color-main-body: #080d12;
--color-main-bg: #fff;
--color-placeholder: #93a0a7;
--color-danger: #ff6161;
--color-orange: #ffa861;
--color-purple: #6f8cff;
--shadow-sm: 0 2px 5px -2px #00142814;
--bg-gradient-sky: linear-gradient(0deg,#f8fcff,#e4f2ff 85%);
```
