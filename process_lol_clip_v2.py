#!/usr/bin/env python3
"""LOLクリップ処理パイプライン V2 - 話者識別機能付き.

1. 音声を文字起こし
2. 話者を識別（voice embedding使用）
3. 日本語に翻訳（Gemini + LoL用語辞書）
4. 字幕を動画に焼き付け
"""
import os
import re
import gc
import subprocess
import numpy as np
import torch
from pathlib import Path as PathLib

# .envファイルを読み込む
env_path = PathLib(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)
from pathlib import Path

# Monkey-patch torch.load for PyTorch 2.6+ compatibility
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

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


def convert_to_wav(input_path: str, output_path: str):
    """動画をWAVに変換."""
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-ar', '16000', '-ac', '1', '-acodec', 'pcm_s16le',
        output_path
    ]
    subprocess.run(cmd, capture_output=True)
    return output_path


class SpeakerIdentifier:
    """話者識別クラス."""

    def __init__(self, embeddings_dir: str = "data/speaker_embeddings_v2"):
        self.embeddings_dir = embeddings_dir
        self.encoder = None
        self.speaker_embeddings = {}

    def load_models(self):
        """モデルと埋め込みを読み込み."""
        from speechbrain.inference.speaker import EncoderClassifier

        print("SpeechBrainエンコーダーを読み込み中...")
        self.encoder = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir="data/speechbrain_cache"
        )

        print("話者埋め込みを読み込み中...")
        for filename in os.listdir(self.embeddings_dir):
            if filename.endswith('.npy'):
                player_name = filename.replace('.npy', '').title()
                embedding = np.load(os.path.join(self.embeddings_dir, filename))
                self.speaker_embeddings[player_name] = embedding
                print(f"  {player_name}")

        print(f"話者数: {len(self.speaker_embeddings)}")

    def extract_embedding(self, wav_path: str, start: float, duration: float):
        """音声セグメントから埋め込みを抽出."""
        import torchaudio

        try:
            waveform, sr = torchaudio.load(wav_path)

            if sr != 16000:
                resampler = torchaudio.transforms.Resample(sr, 16000)
                waveform = resampler(waveform)
                sr = 16000

            start_sample = int(start * sr)
            end_sample = int((start + duration) * sr)

            if end_sample > waveform.shape[1]:
                end_sample = waveform.shape[1]
            if start_sample >= end_sample:
                return None

            segment = waveform[:, start_sample:end_sample]

            if segment.shape[1] < sr * 0.5:
                return None

            embedding = self.encoder.encode_batch(segment)
            return embedding.squeeze().numpy()
        except Exception as e:
            return None

    def cosine_similarity(self, a, b):
        """コサイン類似度を計算."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def identify_speaker(self, embedding, threshold: float = 0.40):
        """埋め込みから話者を識別."""
        if embedding is None:
            return None, 0.0

        best_match = None
        best_score = -1

        for player_name, player_embedding in self.speaker_embeddings.items():
            score = self.cosine_similarity(embedding, player_embedding)
            if score > best_score:
                best_score = score
                best_match = player_name

        if best_score >= threshold:
            return best_match, best_score
        return None, best_score


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

    del model
    gc.collect()

    return info.language, segments


def identify_speakers_with_embeddings(
    video_path: Path,
    segments: list,
    identifier: SpeakerIdentifier,
    threshold: float = 0.40
) -> list:
    """埋め込みベースの話者識別."""
    # WAVに変換
    wav_path = str(video_path).replace('.mp4', '_temp_spk.wav')
    convert_to_wav(str(video_path), wav_path)

    results = []

    for seg in segments:
        text = seg.text.strip()
        start = seg.start
        end = seg.end
        duration = end - start

        speaker = None
        confidence = 0.0

        # 1秒以上のセグメントのみ話者識別
        if duration >= 1.0:
            embedding = identifier.extract_embedding(wav_path, start, duration)
            speaker, confidence = identifier.identify_speaker(embedding, threshold)

        results.append({
            "start": start,
            "end": end,
            "text": text,
            "speaker": speaker,
            "confidence": confidence,
        })

    # クリーンアップ
    if os.path.exists(wav_path):
        os.remove(wav_path)

    return results


def translate_batch_to_japanese(segments: list, api_key: str) -> list:
    """セグメントをバッチで翻訳（効率化のため）."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    # テキストをまとめて翻訳
    texts = [seg["text"] for seg in segments]

    # 10セグメントずつバッチ処理
    batch_size = 10
    translated_segments = []

    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        batch_texts = [s["text"] for s in batch]

        # バッチプロンプト
        numbered_texts = "\n".join([f"{j+1}. {t}" for j, t in enumerate(batch_texts)])

        prompt = f"""あなたはLeague of Legends(LoL)のeスポーツ専門翻訳者です。
以下の韓国語のチームボイス（試合中の選手間コミュニケーション）を自然な日本語に翻訳してください。

重要なルール:
1. 番号付きで翻訳を返してください（入力と同じ形式）
2. ゲーム用語やコールアウトは自然に翻訳
3. 緊迫感を維持
4. 翻訳のみを返す（説明は不要）

入力テキスト:
{numbered_texts}

翻訳（番号付き）:"""

        try:
            response = model.generate_content(prompt)
            translated_text = response.text.strip()

            # 翻訳結果をパース
            lines = translated_text.split('\n')
            translations = []

            for line in lines:
                # "1. 翻訳文" の形式をパース
                match = re.match(r'^\d+\.\s*(.+)$', line.strip())
                if match:
                    translations.append(match.group(1))

            # 翻訳結果を適用
            for j, seg in enumerate(batch):
                new_seg = seg.copy()
                if j < len(translations):
                    new_seg["text_ja"] = correct_text(translations[j])
                else:
                    new_seg["text_ja"] = correct_text(seg["text"])
                translated_segments.append(new_seg)

        except Exception as e:
            print(f"翻訳エラー: {e}")
            # エラー時はLoL用語修正のみ
            for seg in batch:
                new_seg = seg.copy()
                new_seg["text_ja"] = correct_text(seg["text"])
                translated_segments.append(new_seg)

    return translated_segments


def create_srt_with_speakers(
    segments: list,
    output_path: Path,
    show_speaker: bool = True,
    use_japanese: bool = True
):
    """話者付きSRTファイルを作成."""
    lines = []

    for i, seg in enumerate(segments, 1):
        start_ts = format_timestamp(seg["start"])
        end_ts = format_timestamp(seg["end"])

        # テキスト選択
        if use_japanese and "text_ja" in seg:
            text = seg["text_ja"]
        else:
            text = seg["text"]

        # 話者名付加（高信頼度のみ）
        if show_speaker and seg.get("speaker") and seg.get("confidence", 0) >= 0.45:
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
    identify_speakers: bool = True,
    speaker_threshold: float = 0.35,  # Lowered threshold for better detection
):
    """クリップを処理するメインパイプライン."""
    output_dir = output_dir or video_path.parent
    stem = video_path.stem

    api_key = os.environ.get("GEMINI_API_KEY")

    print(f"\n=== LOLクリップ処理 V2: {video_path.name} ===\n")

    # 1. 文字起こし
    print("--- Step 1: 文字起こし ---")
    detected_lang, segments = transcribe_audio(video_path)

    # 2. 話者識別
    print("\n--- Step 2: 話者識別 ---")
    if identify_speakers and os.path.exists("data/speaker_embeddings_v2"):
        identifier = SpeakerIdentifier()
        identifier.load_models()
        segments_with_speakers = identify_speakers_with_embeddings(
            video_path, segments, identifier, speaker_threshold
        )
        # メモリ解放
        del identifier
        gc.collect()
    else:
        print("話者データベースなし - スキップ")
        segments_with_speakers = [
            {"start": s.start, "end": s.end, "text": s.text.strip(), "speaker": None, "confidence": 0.0}
            for s in segments
        ]

    # 3. 翻訳
    print("\n--- Step 3: 翻訳 ---")
    if translate and detected_lang != "ja" and api_key:
        segments_translated = translate_batch_to_japanese(segments_with_speakers, api_key)
    else:
        # 翻訳なしでLoL用語修正のみ
        segments_translated = []
        for seg in segments_with_speakers:
            new_seg = seg.copy()
            new_seg["text_ja"] = correct_text(seg["text"])
            segments_translated.append(new_seg)

    # 4. SRT作成
    print("\n--- Step 4: SRT作成 ---")
    srt_path = output_dir / f"{stem}_ja.srt"
    create_srt_with_speakers(segments_translated, srt_path)

    # 話者識別結果のサマリー
    identified = [s for s in segments_translated if s.get("speaker")]
    if identified:
        print(f"\n話者識別結果:")
        from collections import Counter
        speaker_counts = Counter(s["speaker"] for s in identified)
        for speaker, count in speaker_counts.most_common():
            avg_conf = np.mean([s["confidence"] for s in identified if s["speaker"] == speaker])
            print(f"  {speaker}: {count}回 (平均信頼度: {avg_conf:.2f})")

    # 5. 字幕焼き付け
    if burn:
        print("\n--- Step 5: 字幕焼き付け ---")
        output_video = output_dir / f"{stem}_subtitled.mp4"
        burn_subtitles(video_path, srt_path, output_video)
        return output_video

    return srt_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        video_path = Path(sys.argv[1])
    else:
        print("Usage: python process_lol_clip_v2.py <video_path>")
        sys.exit(1)

    if video_path.exists():
        process_clip(video_path)
    else:
        print(f"ファイルが見つかりません: {video_path}")
