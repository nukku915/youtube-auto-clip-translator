"""LOL用語を自動修正するスクリプト."""
import os
import re
from pathlib import Path
from lol_dictionary import correct_text, create_correction_dict


def correct_with_ai(srt_content: str, api_key: str) -> str:
    """AIを使ってLOL用語と不明瞭な表現を修正."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""あなたはLeague of Legends(LOL)のエキスパートです。
以下のSRT字幕ファイルには、音声認識の誤りや不明瞭な表現が含まれている可能性があります。

LOLの文脈で意味が通るように修正してください。特に：

1. **チャンピオン名の修正**：
   - Aatrox = エイトロックス（アトロックス、アートロックスは誤り）
   - Sion = サイオン
   - Maokai = マオカイ
   - その他のチャンピオン名も正しい日本語表記に

2. **ゲーム用語の修正**：
   - タンク、イニシエート、フィール（Feel/視界確認）、バースト など
   - シールドバリア = シールドバッテリー（バロンのシールド）の可能性

3. **意味不明な表現の推測**：
   - 「やばいtragedyだ」→ 文脈から推測して修正（例：「やばいTP（テレポート）だ」「やばいトレードだ」など）
   - 音が似ている別の単語を推測

4. **韓国語が混じっている場合**：
   - 適切な日本語に翻訳

修正後のSRT形式のみを返してください。番号とタイムスタンプは変更しないでください。

--- SRT内容 ---
{srt_content}
--- ここまで ---

修正後のSRT:"""

    response = model.generate_content(prompt)
    result = response.text.strip()

    # コードブロックを除去
    if result.startswith("```"):
        lines = result.split("\n")
        if lines[-1].strip() == "```":
            result = "\n".join(lines[1:-1])
        else:
            result = "\n".join(lines[1:])

    return result


def apply_dictionary(content: str) -> str:
    """辞書ベースの単純な置換."""
    return correct_text(content)


def main():
    input_srt = Path("./output/clips/player_clip_01_ja_speakers.srt")
    output_srt = Path("./output/clips/player_clip_01_ja_corrected.srt")

    with open(input_srt, "r", encoding="utf-8") as f:
        content = f.read()

    print("元の字幕内容:")
    print(content[:500])
    print("...\n")

    # 1. 辞書ベースの置換
    content = apply_dictionary(content)

    # 2. AIによる文脈修正
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        print("AIで文脈修正中...")
        try:
            content = correct_with_ai(content, api_key)
            print("AI修正完了")
        except Exception as e:
            print(f"AI修正エラー: {e}")
            print("辞書ベースの修正のみ適用")
    else:
        print("GEMINI_API_KEY未設定。辞書ベースの修正のみ適用")

    with open(output_srt, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n修正後の字幕: {output_srt}")
    print("\n修正後の内容:")
    print(content[:500])


if __name__ == "__main__":
    main()
