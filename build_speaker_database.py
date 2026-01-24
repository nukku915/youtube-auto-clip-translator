#!/usr/bin/env python3
"""Build speaker database from LCK interviews using diarization"""

import os
import json
import subprocess
import numpy as np
import torch
from collections import defaultdict

# Monkey-patch torch.load for PyTorch 2.6+ compatibility
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

from pyannote.audio import Pipeline
from speechbrain.inference.speaker import EncoderClassifier

# Interview metadata: filename -> list of players in the interview
INTERVIEW_PLAYERS = {
    # Faker interviews
    "faker_keria_worlds2024": ["Faker", "Keria"],
    "faker_keria_spring2024_2": ["Faker", "Keria"],
    "faker_t1_vs_drx_lck2025": ["Faker"],
    "gumayusi_faker_lck2024": ["Gumayusi", "Faker"],
    "gumayusi_faker_spring2024_2": ["Gumayusi", "Faker"],
    "doran_faker_worlds2025": ["Doran", "Faker"],
    "zeus_faker_worlds2024": ["Zeus", "Faker"],
    "keria_faker_lck_spring2024": ["Keria", "Faker"],
    "keria_faker_spring2024_3": ["Keria", "Faker"],
    "oner_faker_summer2024": ["Oner", "Faker"],

    # Keria interviews
    "keria_gumayusi_summer2024": ["Keria", "Gumayusi"],
    "zeus_keria_spring2024": ["Zeus", "Keria"],
    "oner_keria_summer2024": ["Oner", "Keria"],

    # Oner interviews
    "zeus_oner_spring2024": ["Zeus", "Oner"],
    "gumayusi_oner_worlds2024": ["Gumayusi", "Oner"],
    "oner_t1_vs_drx_lckcup2025": ["Oner"],

    # Gumayusi interviews
    "gumayusi_worlds2024_solo": ["Gumayusi"],
    "gumayusi_zeus_summer2024": ["Gumayusi", "Zeus"],

    # Full team
    "t1_full_team_worlds2024": ["Zeus", "Oner", "Faker", "Gumayusi", "Keria"],

    # DRX interviews
    "drx_lck2025": ["DRX_Unknown"],
    "drx_rich_lck2025": ["Rich"],
    "drx_teddy_lck2025": ["Teddy"],
    "drx_dk_lck2025": ["DRX_Unknown"],
}

HF_TOKEN = os.getenv("HF_TOKEN")
INTERVIEWS_DIR = "data/interviews"
OUTPUT_DIR = "data/speaker_embeddings"

def convert_to_wav(input_path: str, output_path: str):
    """Convert audio to 16kHz mono WAV"""
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-ar', '16000', '-ac', '1', '-acodec', 'pcm_s16le',
        output_path
    ]
    subprocess.run(cmd, capture_output=True)
    return output_path

def process_interview(pipeline, encoder, audio_path: str, players: list):
    """Process an interview and extract speaker embeddings"""
    print(f"\nProcessing: {audio_path}")
    print(f"Expected players: {players}")

    # Convert to WAV
    wav_path = audio_path.replace('.mp4', '.wav')
    if not os.path.exists(wav_path):
        convert_to_wav(audio_path, wav_path)

    # Run diarization
    print("Running diarization...")
    diarization = pipeline(wav_path)

    # Collect segments by speaker
    speaker_segments = defaultdict(list)
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        duration = turn.end - turn.start
        if duration >= 2.0:  # Only segments >= 2 seconds
            speaker_segments[speaker].append({
                'start': turn.start,
                'end': turn.end,
                'duration': duration
            })

    print(f"Found {len(speaker_segments)} speakers")

    # Extract embeddings for each speaker
    embeddings_by_speaker = {}
    for speaker_label, segments in speaker_segments.items():
        # Sort by duration, take longest segments
        segments.sort(key=lambda x: x['duration'], reverse=True)
        top_segments = segments[:5]  # Top 5 longest segments

        all_embeddings = []
        for seg in top_segments:
            try:
                embedding = encoder.encode_file(
                    wav_path,
                    start=seg['start'],
                    stop=seg['end']
                )
                all_embeddings.append(embedding.squeeze().numpy())
            except Exception as e:
                print(f"  Error extracting embedding: {e}")

        if all_embeddings:
            # Average embedding
            avg_embedding = np.mean(all_embeddings, axis=0)
            embeddings_by_speaker[speaker_label] = {
                'embedding': avg_embedding,
                'num_segments': len(segments),
                'total_duration': sum(s['duration'] for s in segments)
            }
            print(f"  Speaker {speaker_label}: {len(segments)} segments, {embeddings_by_speaker[speaker_label]['total_duration']:.1f}s total")

    # Clean up
    if os.path.exists(wav_path):
        os.remove(wav_path)

    return embeddings_by_speaker

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load models
    print("Loading pyannote pipeline...")
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=HF_TOKEN
    )

    print("Loading SpeechBrain encoder...")
    encoder = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir="data/speechbrain_cache"
    )

    # Process each interview
    all_embeddings = defaultdict(list)  # player_name -> list of embeddings

    for filename, players in INTERVIEW_PLAYERS.items():
        audio_path = os.path.join(INTERVIEWS_DIR, f"{filename}.mp4")
        if not os.path.exists(audio_path):
            print(f"Skipping {filename} - file not found")
            continue

        try:
            speaker_embeddings = process_interview(pipeline, encoder, audio_path, players)

            # For solo interviews, assign to the single player
            if len(players) == 1:
                player = players[0]
                for speaker_label, data in speaker_embeddings.items():
                    # Take the speaker with most duration (likely the interviewee)
                    pass
                # Get the speaker with most duration
                if speaker_embeddings:
                    main_speaker = max(speaker_embeddings.items(), key=lambda x: x[1]['total_duration'])
                    all_embeddings[player].append(main_speaker[1]['embedding'])
                    print(f"  Assigned to {player}")

            # For duo interviews, assign based on speaking order/duration
            elif len(players) == 2:
                if len(speaker_embeddings) >= 2:
                    # Sort by total duration
                    sorted_speakers = sorted(
                        speaker_embeddings.items(),
                        key=lambda x: x[1]['total_duration'],
                        reverse=True
                    )
                    # First player listed usually speaks first/more
                    for i, player in enumerate(players):
                        if i < len(sorted_speakers):
                            all_embeddings[player].append(sorted_speakers[i][1]['embedding'])
                            print(f"  Assigned speaker {sorted_speakers[i][0]} to {player}")
                elif len(speaker_embeddings) == 1:
                    # Only one speaker detected - assign to first player
                    main_speaker = list(speaker_embeddings.values())[0]
                    all_embeddings[players[0]].append(main_speaker['embedding'])

        except Exception as e:
            print(f"Error processing {filename}: {e}")
            continue

    # Save embeddings
    print("\n=== Saving embeddings ===")
    for player, embeddings in all_embeddings.items():
        if embeddings:
            # Average all embeddings for this player
            avg_embedding = np.mean(embeddings, axis=0)
            output_path = os.path.join(OUTPUT_DIR, f"{player.lower()}.npy")
            np.save(output_path, avg_embedding)
            print(f"Saved {player}: {len(embeddings)} samples -> {output_path}")

    # Also save as JSON for reference
    summary = {
        player: {
            'num_samples': len(embeddings),
            'embedding_path': os.path.join(OUTPUT_DIR, f"{player.lower()}.npy")
        }
        for player, embeddings in all_embeddings.items()
    }
    with open(os.path.join(OUTPUT_DIR, "summary.json"), 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n=== Done! Processed {len(all_embeddings)} players ===")

if __name__ == "__main__":
    main()
