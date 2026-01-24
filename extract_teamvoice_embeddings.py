#!/usr/bin/env python3
"""Extract speaker embeddings from team voice clips with known timestamps"""

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

# Known segments from T1 team voice videos where specific players are speaking
# These timestamps are manually identified from watching the videos
KNOWN_SEGMENTS = {
    "data/team_voice/t1_worlds2025_teamvoice.mp4": [
        # Based on typical team voice video structure
        # The order is usually: Zeus, Oner, Faker, Gumayusi, Keria (top to bot)
        # We'll extract from clear solo speaking moments
    ],
    "data/team_voice/lck_mic_check_2025.mp4": [
        # LCK mic check typically has clearer audio
    ],
}

# More reliable: use interview audio but adapt for team voice
# Combine interview embeddings with additional processing

TEAM_VOICE_DIR = "data/team_voice"
EMBEDDINGS_DIR = "data/speaker_embeddings_v2"

def convert_to_wav(input_path: str, output_path: str):
    """Convert audio to 16kHz mono WAV"""
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-ar', '16000', '-ac', '1', '-acodec', 'pcm_s16le',
        output_path
    ]
    subprocess.run(cmd, capture_output=True)
    return output_path

def extract_embedding(encoder, wav_path: str, start: float, duration: float):
    """Extract embedding from audio segment"""
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

        embedding = encoder.encode_batch(segment)
        return embedding.squeeze().numpy()
    except Exception as e:
        print(f"  Error: {e}")
        return None

def cosine_similarity(a, b):
    """Calculate cosine similarity between two embeddings"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def main():
    print("Loading SpeechBrain encoder...")
    encoder = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir="data/speechbrain_cache"
    )

    # Load existing embeddings
    print("\n=== Loading existing embeddings ===")
    speaker_embeddings = {}
    for filename in os.listdir(EMBEDDINGS_DIR):
        if filename.endswith('.npy'):
            player_name = filename.replace('.npy', '').title()
            embedding = np.load(os.path.join(EMBEDDINGS_DIR, filename))
            speaker_embeddings[player_name] = embedding
            print(f"  Loaded {player_name}: dim={embedding.shape}")

    # Analyze team voice videos to find potential speaker segments
    print("\n=== Analyzing team voice videos ===")

    for tv_file in os.listdir(TEAM_VOICE_DIR):
        if not tv_file.endswith('.mp4'):
            continue

        tv_path = os.path.join(TEAM_VOICE_DIR, tv_file)
        print(f"\nAnalyzing: {tv_file}")

        wav_path = tv_path.replace('.mp4', '_temp.wav')
        convert_to_wav(tv_path, wav_path)

        # Get audio duration
        import torchaudio
        waveform, sr = torchaudio.load(wav_path)
        duration = waveform.shape[1] / sr
        print(f"  Duration: {duration:.1f}s")

        # Sample every 5 seconds and find high-confidence matches
        high_confidence_matches = []
        for start in range(0, int(duration) - 3, 5):
            embedding = extract_embedding(encoder, wav_path, start, 3.0)
            if embedding is None:
                continue

            best_match = None
            best_score = 0.0

            for player_name, player_embedding in speaker_embeddings.items():
                score = cosine_similarity(embedding, player_embedding)
                if score > best_score:
                    best_score = score
                    best_match = player_name

            if best_score >= 0.40:
                high_confidence_matches.append({
                    'start': start,
                    'player': best_match,
                    'score': best_score
                })

        print(f"  Found {len(high_confidence_matches)} high-confidence segments (>0.40)")
        for m in high_confidence_matches[:10]:
            print(f"    [{m['start']}s] {m['player']}: {m['score']:.3f}")

        # Clean up
        if os.path.exists(wav_path):
            os.remove(wav_path)

    # Print summary of current embeddings
    print("\n=== Current Speaker Database Summary ===")
    for player, emb in speaker_embeddings.items():
        print(f"  {player}: embedding dim = {emb.shape}")

    # Show similarity matrix between speakers
    print("\n=== Speaker Similarity Matrix ===")
    players = sorted(speaker_embeddings.keys())
    print("       " + " ".join(f"{p[:4]:>6}" for p in players))
    for p1 in players:
        scores = []
        for p2 in players:
            sim = cosine_similarity(speaker_embeddings[p1], speaker_embeddings[p2])
            scores.append(f"{sim:.2f}")
        print(f"{p1[:6]:>6} " + " ".join(f"{s:>6}" for s in scores))

if __name__ == "__main__":
    main()
