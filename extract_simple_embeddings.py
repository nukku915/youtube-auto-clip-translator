#!/usr/bin/env python3
"""Simple speaker embedding extraction from interviews"""

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

# Simple mapping: interview file -> player name (for solo/clear interviews)
# We'll extract from the first 30-60 seconds where the player typically speaks
SOLO_INTERVIEWS = {
    "gumayusi_worlds2024_solo": "Gumayusi",
    "oner_t1_vs_drx_lckcup2025": "Oner",
    "faker_t1_vs_drx_lck2025": "Faker",
    "drx_rich_lck2025": "Rich",
    "drx_teddy_lck2025": "Teddy",
}

# Duo interviews where we extract the first-named player (typically speaks more)
DUO_INTERVIEWS_FIRST = {
    "keria_faker_lck_spring2024": "Keria",
    "keria_faker_spring2024_3": "Keria",
    "keria_gumayusi_summer2024": "Keria",
    "doran_faker_worlds2025": "Doran",
    "zeus_faker_worlds2024": "Zeus",
    "zeus_oner_spring2024": "Zeus",
    "zeus_keria_spring2024": "Zeus",
    # Additional interviews for more samples
    "faker_keria_spring2024_2": "Faker",
    "faker_keria_worlds2024": "Faker",
    "gumayusi_faker_lck2024": "Gumayusi",
    "gumayusi_faker_spring2024_2": "Gumayusi",
    "gumayusi_oner_worlds2024": "Gumayusi",
    "gumayusi_zeus_summer2024": "Gumayusi",
    "oner_faker_summer2024": "Oner",
    "oner_keria_summer2024": "Oner",
}

INTERVIEWS_DIR = "data/interviews"
DOWNLOADS_DIR = "downloads"
OUTPUT_DIR = "data/speaker_embeddings_v2"

# Individual interview files (different audio environment)
INDIVIDUAL_INTERVIEWS = {
    "faker_interview": "Faker",
    "keria_interview": "Keria",
    "zeus_interview": "Zeus",
    "oner_interview": "Oner",
    "gumayusi_interview": "Gumayusi",
    "doran_interview": "Doran",
    "teddy_interview": "Teddy",
    "rich_interview": "Rich",
    # Additional LCK players
    "chovy_interview": "Chovy",
    "canyon_interview": "Canyon",
    "bdd_interview": "BDD",
    "aiming_interview": "Aiming",
    "kiin_interview": "Kiin",
    "kingen_interview": "Kingen",
    "deokdam_interview": "Deokdam",
    "kellin_interview": "Kellin",
    "kanavi_interview": "Kanavi",
    "ghost_interview": "Ghost",
    "ruler_interview": "Ruler",
    "showmaker_interview": "Showmaker",
    "clozer_interview": "Clozer",
}

def convert_to_wav(input_path: str, output_path: str):
    """Convert audio to 16kHz mono WAV"""
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-ar', '16000', '-ac', '1', '-acodec', 'pcm_s16le',
        output_path
    ]
    subprocess.run(cmd, capture_output=True)
    return output_path

def extract_embedding(encoder, wav_path: str, start: float = 5.0, duration: float = 30.0):
    """Extract speaker embedding from a time range"""
    import torchaudio
    try:
        # Load audio
        waveform, sr = torchaudio.load(wav_path)

        # Convert to 16kHz if needed
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(sr, 16000)
            waveform = resampler(waveform)
            sr = 16000

        # Extract segment
        start_sample = int(start * sr)
        end_sample = int((start + duration) * sr)
        segment = waveform[:, start_sample:end_sample]

        # Get embedding
        embedding = encoder.encode_batch(segment)
        return embedding.squeeze().numpy()
    except Exception as e:
        print(f"  Error: {e}")
        return None

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading SpeechBrain encoder...")
    encoder = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir="data/speechbrain_cache"
    )

    embeddings = {}

    # Process solo interviews
    print("\n=== Processing Solo Interviews ===")
    for filename, player in SOLO_INTERVIEWS.items():
        audio_path = os.path.join(INTERVIEWS_DIR, f"{filename}.mp4")
        if not os.path.exists(audio_path):
            print(f"Skipping {filename} - not found")
            continue

        print(f"\nProcessing: {filename} -> {player}")

        # Convert to WAV
        wav_path = audio_path.replace('.mp4', '_temp.wav')
        convert_to_wav(audio_path, wav_path)

        # Extract multiple segments
        all_embeddings = []
        for start in [5, 15, 25, 35]:  # Extract from multiple time points
            emb = extract_embedding(encoder, wav_path, start=start, duration=15.0)
            if emb is not None:
                all_embeddings.append(emb)
                print(f"  Extracted from {start}s-{start+15}s")

        if all_embeddings:
            # Average embeddings
            avg_embedding = np.mean(all_embeddings, axis=0)
            if player not in embeddings:
                embeddings[player] = []
            embeddings[player].append(avg_embedding)
            print(f"  Got {len(all_embeddings)} segments for {player}")

        # Clean up
        if os.path.exists(wav_path):
            os.remove(wav_path)

    # Process duo interviews (extract first speaker)
    print("\n=== Processing Duo Interviews (First Speaker) ===")
    for filename, player in DUO_INTERVIEWS_FIRST.items():
        audio_path = os.path.join(INTERVIEWS_DIR, f"{filename}.mp4")
        if not os.path.exists(audio_path):
            print(f"Skipping {filename} - not found")
            continue

        print(f"\nProcessing: {filename} -> {player}")

        # Convert to WAV
        wav_path = audio_path.replace('.mp4', '_temp.wav')
        convert_to_wav(audio_path, wav_path)

        # Extract from early parts where first-named player typically speaks
        # In Korean interviews, the first player usually speaks in the first 30 seconds
        all_embeddings = []
        for start in [3, 10, 20]:  # Early time points
            emb = extract_embedding(encoder, wav_path, start=start, duration=10.0)
            if emb is not None:
                all_embeddings.append(emb)
                print(f"  Extracted from {start}s-{start+10}s")

        if all_embeddings:
            # Average embeddings
            avg_embedding = np.mean(all_embeddings, axis=0)
            if player not in embeddings:
                embeddings[player] = []
            embeddings[player].append(avg_embedding)
            print(f"  Got {len(all_embeddings)} segments for {player}")

        # Clean up
        if os.path.exists(wav_path):
            os.remove(wav_path)

    # Process individual interview files from downloads folder
    print("\n=== Processing Individual Interviews ===")
    for filename, player in INDIVIDUAL_INTERVIEWS.items():
        audio_path = os.path.join(DOWNLOADS_DIR, f"{filename}.mp4")
        if not os.path.exists(audio_path):
            print(f"Skipping {filename} - not found")
            continue

        print(f"\nProcessing: {filename} -> {player}")

        # Convert to WAV
        wav_path = audio_path.replace('.mp4', '_temp.wav')
        convert_to_wav(audio_path, wav_path)

        # Extract from multiple time points
        all_embeddings = []
        for start in [5, 15, 25, 35]:
            emb = extract_embedding(encoder, wav_path, start=start, duration=15.0)
            if emb is not None:
                all_embeddings.append(emb)
                print(f"  Extracted from {start}s-{start+15}s")

        if all_embeddings:
            avg_embedding = np.mean(all_embeddings, axis=0)
            if player not in embeddings:
                embeddings[player] = []
            embeddings[player].append(avg_embedding)
            print(f"  Got {len(all_embeddings)} segments for {player}")

        # Clean up
        if os.path.exists(wav_path):
            os.remove(wav_path)

    # Save embeddings
    print("\n=== Saving Embeddings ===")
    for player, emb_list in embeddings.items():
        avg_embedding = np.mean(emb_list, axis=0)
        output_path = os.path.join(OUTPUT_DIR, f"{player.lower()}.npy")
        np.save(output_path, avg_embedding)
        print(f"Saved {player}: {len(emb_list)} sources -> {output_path}")

    # Save summary
    summary = {
        player: {
            'num_samples': len(emb_list),
            'embedding_path': os.path.join(OUTPUT_DIR, f"{player.lower()}.npy")
        }
        for player, emb_list in embeddings.items()
    }
    with open(os.path.join(OUTPUT_DIR, "summary.json"), 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n=== Done! Processed {len(embeddings)} players ===")

if __name__ == "__main__":
    main()
