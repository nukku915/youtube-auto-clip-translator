#!/usr/bin/env python3
"""Identify speakers in team voice clips using speaker embeddings"""

import os
import json
import subprocess
import numpy as np
import torch

# Monkey-patch torch.load for PyTorch 2.6+ compatibility
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

from speechbrain.inference.speaker import EncoderClassifier

EMBEDDINGS_DIR = "data/speaker_embeddings_v2"

class SpeakerIdentifier:
    def __init__(self, embeddings_dir: str = EMBEDDINGS_DIR):
        self.embeddings_dir = embeddings_dir
        self.encoder = None
        self.speaker_embeddings = {}

    def load_models(self):
        """Load encoder and speaker embeddings"""
        print("Loading SpeechBrain encoder...")
        self.encoder = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir="data/speechbrain_cache"
        )

        # Load all speaker embeddings
        print("Loading speaker embeddings...")
        for filename in os.listdir(self.embeddings_dir):
            if filename.endswith('.npy'):
                player_name = filename.replace('.npy', '').title()
                embedding = np.load(os.path.join(self.embeddings_dir, filename))
                self.speaker_embeddings[player_name] = embedding
                print(f"  Loaded {player_name}")

        print(f"Loaded {len(self.speaker_embeddings)} speakers")

    def extract_embedding(self, wav_path: str, start: float, duration: float):
        """Extract embedding from audio segment"""
        import torchaudio

        try:
            waveform, sr = torchaudio.load(wav_path)

            # Resample to 16kHz if needed
            if sr != 16000:
                resampler = torchaudio.transforms.Resample(sr, 16000)
                waveform = resampler(waveform)
                sr = 16000

            # Extract segment
            start_sample = int(start * sr)
            end_sample = int((start + duration) * sr)

            # Make sure we have enough samples
            if end_sample > waveform.shape[1]:
                end_sample = waveform.shape[1]
            if start_sample >= end_sample:
                return None

            segment = waveform[:, start_sample:end_sample]

            # Need at least 0.5 seconds of audio
            if segment.shape[1] < sr * 0.5:
                return None

            embedding = self.encoder.encode_batch(segment)
            return embedding.squeeze().numpy()
        except Exception as e:
            print(f"  Error extracting embedding: {e}")
            return None

    def cosine_similarity(self, a, b):
        """Calculate cosine similarity between two embeddings"""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def identify_speaker(self, embedding, threshold: float = 0.5):
        """Identify speaker from embedding"""
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

    def identify_segments(self, wav_path: str, segments: list, threshold: float = 0.5):
        """Identify speakers for a list of segments"""
        results = []

        for seg in segments:
            start = seg.get('start', 0)
            end = seg.get('end', start + 1)
            duration = end - start

            # Need at least 1 second for reliable identification
            if duration < 1.0:
                results.append({
                    **seg,
                    'identified_speaker': None,
                    'confidence': 0.0
                })
                continue

            embedding = self.extract_embedding(wav_path, start, duration)
            speaker, confidence = self.identify_speaker(embedding, threshold)

            results.append({
                **seg,
                'identified_speaker': speaker,
                'confidence': float(confidence)
            })

        return results


def convert_to_wav(input_path: str, output_path: str):
    """Convert audio to 16kHz mono WAV"""
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-ar', '16000', '-ac', '1', '-acodec', 'pcm_s16le',
        output_path
    ]
    subprocess.run(cmd, capture_output=True)
    return output_path


def test_on_clip(clip_path: str, srt_path: str = None, threshold: float = 0.35):
    """Test speaker identification on a clip"""
    identifier = SpeakerIdentifier()
    identifier.load_models()

    # Convert to WAV
    wav_path = clip_path.replace('.mp4', '_temp.wav')
    convert_to_wav(clip_path, wav_path)

    if srt_path and os.path.exists(srt_path):
        # Parse SRT and identify speakers for each segment
        import re
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse SRT format
        pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.+?)(?=\n\n|\Z)'
        matches = re.findall(pattern, content, re.DOTALL)

        segments = []
        for idx, start_time, end_time, text in matches:
            # Convert timestamp to seconds
            def parse_time(ts):
                h, m, s = ts.replace(',', '.').split(':')
                return float(h) * 3600 + float(m) * 60 + float(s)

            segments.append({
                'index': int(idx),
                'start': parse_time(start_time),
                'end': parse_time(end_time),
                'text': text.strip()
            })

        print(f"\n=== Identifying speakers for {len(segments)} segments ===\n")
        results = identifier.identify_segments(wav_path, segments, threshold=threshold)

        for r in results:
            speaker = r['identified_speaker'] or 'Unknown'
            conf = r['confidence']
            text = r['text'][:50] + '...' if len(r['text']) > 50 else r['text']
            print(f"[{r['start']:.1f}s-{r['end']:.1f}s] {speaker} ({conf:.2f}): {text}")
    else:
        # Just identify across the whole clip
        print("\n=== Identifying speakers across the clip ===\n")

        # Sample every 3 seconds
        import torchaudio
        waveform, sr = torchaudio.load(wav_path)
        duration = waveform.shape[1] / sr

        for start in range(0, int(duration) - 2, 3):
            embedding = identifier.extract_embedding(wav_path, start, 3.0)
            speaker, confidence = identifier.identify_speaker(embedding, threshold=threshold)
            speaker = speaker or 'Unknown'
            print(f"[{start}s-{start+3}s] {speaker} ({confidence:.2f})")

    # Clean up
    if os.path.exists(wav_path):
        os.remove(wav_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python identify_speakers.py <clip_path> [srt_path] [threshold]")
        sys.exit(1)

    clip_path = sys.argv[1]
    srt_path = sys.argv[2] if len(sys.argv) > 2 else None
    threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 0.35

    test_on_clip(clip_path, srt_path, threshold)
