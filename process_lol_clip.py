"""LOLクリップ処理パイプライン.

1. 音声を文字起こし
2. 話者を識別（データベースがあれば）
3. 日本語に翻訳
4. LOL用語を修正
5. 字幕を動画に焼き付け
"""
import os
import re
import gc
from pathlib import Path
from lol_dictionary import correct_text


def format_timestamp(seconds: float) -> str:
    """秒をSRT形式のタイムスタンプに変換."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def timestamp_to_seconds(ts: str) -> float:
    """タイムスタンプを秒に変換."""
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def transcribe_audio(video_path: Path) -> tuple:
    """Whisperで文字起こし."""
    from faster_whisper import WhisperModel

    print("Whisperモデルを読み込み中...")
    model = WhisperModel("large-v3", device="cpu", compute_type="int8")

    print("文字起こし中...")
    segments_iter, info = model.transcribe(
        str(video_path),
        beam_size=5,
        language=None,
        vad_filter=True,
    )

    segments = list(segments_iter)
    print(f"検出言語: {info.language}")
    print(f"セグメント数: {len(segments)}")

    # メモリ解放
    del model
    gc.collect()

    return info.language, segments


def translate_to_japanese(text: str, api_key: str) -> str:
    """韓国語を日本語に翻訳."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""Translate the following Korean text to natural Japanese.
This is League of Legends esports team voice communication.
Keep gaming terms and player callouts natural.

Korean: {text}

Japanese translation only:"""

    response = model.generate_content(prompt)
    return response.text.strip()


def identify_speakers_simple(segments: list, speaker_db=None) -> list:
    """話者を識別（簡易版：内容ベース）."""
    # 話者データベースがない場合は内容ベースで推測
    results = []

    for seg in segments:
        text = seg.text.strip()
        speaker = "Unknown"

        # 内容ベースの簡易判定（NS RedForce用）
        # これは仮の実装。実際の話者識別はvoice embeddingを使用
        if any(word in text for word in ["시야", "와드", "필"]):
            speaker = "Lehends"  # サポートは視界管理
        elif any(word in text for word in ["정글", "갱", "카정"]):
            speaker = "Sponge"  # ジャングラー
        elif "초" in text and any(c.isdigit() for c in text):
            speaker = "Sponge"  # タイマーコールはジャングラー

        results.append({
            "start": seg.start,
            "end": seg.end,
            "text": text,
            "speaker": speaker,
        })

    return results


def create_srt_with_speakers(segments: list, output_path: Path, translate: bool = True, api_key: str = None):
    """話者付きSRTファイルを作成."""
    lines = []

    for i, seg in enumerate(segments, 1):
        start_ts = format_timestamp(seg["start"])
        end_ts = format_timestamp(seg["end"])

        text = seg["text"]

        # 翻訳
        if translate and api_key:
            try:
                text = translate_to_japanese(text, api_key)
            except Exception as e:
                print(f"翻訳エラー: {e}")

        # LOL用語修正
        text = correct_text(text)

        # 話者名付加
        if seg.get("speaker") and seg["speaker"] != "Unknown":
            text = f"[{seg['speaker']}] {text}"

        lines.append(f"{i}")
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(text)
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"SRTファイル作成: {output_path}")


def burn_subtitles(video_path: Path, srt_path: Path, output_path: Path):
    """字幕を動画に焼き付け."""
    from moviepy import VideoFileClip, TextClip, CompositeVideoClip

    print("動画を読み込み中...")
    video = VideoFileClip(str(video_path))

    print("字幕をパース中...")
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.+?)(?=\n\n|\Z)'
    matches = re.findall(pattern, content, re.DOTALL)

    print(f"字幕数: {len(matches)}")

    subtitle_clips = []
    for match in matches:
        idx, start, end, text = match
        start_sec = timestamp_to_seconds(start)
        end_sec = timestamp_to_seconds(end)
        text = text.strip().replace("\n", " ")

        try:
            txt_clip = TextClip(
                text=text,
                font_size=32,
                color="white",
                stroke_color="black",
                stroke_width=2,
                font="/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
                size=(video.w - 100, None),
                method="caption",
            )
            txt_clip = txt_clip.with_position(("center", video.h - 80))
            txt_clip = txt_clip.with_start(start_sec)
            txt_clip = txt_clip.with_end(end_sec)
            subtitle_clips.append(txt_clip)
        except Exception as e:
            print(f"警告: 字幕作成失敗 - {text[:20]}... - {e}")

    print("動画を合成中...")
    final = CompositeVideoClip([video] + subtitle_clips)

    print("書き出し中...")
    final.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        fps=video.fps,
        preset="fast",
    )

    video.close()
    final.close()
    print(f"完了: {output_path}")


def process_clip(
    video_path: Path,
    output_dir: Path = None,
    translate: bool = True,
    burn: bool = True,
):
    """クリップを処理するメインパイプライン."""
    output_dir = output_dir or video_path.parent
    stem = video_path.stem

    api_key = os.environ.get("GEMINI_API_KEY")

    print(f"\n=== LOLクリップ処理: {video_path.name} ===\n")

    # 1. 文字起こし
    print("--- Step 1: 文字起こし ---")
    detected_lang, segments = transcribe_audio(video_path)

    # 2. 話者識別
    print("\n--- Step 2: 話者識別 ---")
    segments_with_speakers = identify_speakers_simple(segments)

    # 3. SRT作成（翻訳 + LOL用語修正）
    print("\n--- Step 3: SRT作成 ---")
    srt_path = output_dir / f"{stem}_ja.srt"
    create_srt_with_speakers(
        segments_with_speakers,
        srt_path,
        translate=(translate and detected_lang != "ja"),
        api_key=api_key,
    )

    # 4. 字幕焼き付け
    if burn:
        print("\n--- Step 4: 字幕焼き付け ---")
        output_video = output_dir / f"{stem}_subtitled.mp4"
        burn_subtitles(video_path, srt_path, output_video)
        return output_video

    return srt_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        video_path = Path(sys.argv[1])
    else:
        video_path = Path("./output/clips/player_clip_01_68m56s.mp4")

    if video_path.exists():
        process_clip(video_path)
    else:
        print(f"ファイルが見つかりません: {video_path}")
