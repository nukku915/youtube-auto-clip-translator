#!/usr/bin/env python3
"""Download LCK team voice videos for speaker database"""

import os
from pytubefix import YouTube
from pytubefix.cli import on_progress

# Team voice videos - these are the most valuable for speaker identification
TEAM_VOICE_VIDEOS = [
    # T1 2025 Worlds team voice
    ("https://www.youtube.com/watch?v=y6ZgwIfljRg", "t1_worlds2025_teamvoice"),
    ("https://www.youtube.com/watch?v=v7kY2OkKM34", "t1_worlds2025_finals_teamvoice"),

    # T1 2024 documentary/behind the scenes
    ("https://www.youtube.com/watch?v=MPcUGG8zvrc", "t1_discord_2024"),

    # LCK mic check
    ("https://www.youtube.com/watch?v=tKz2IV5Um58", "lck_mic_check_2025"),
]

def download_audio(url: str, filename: str, output_dir: str = "data/team_voice"):
    """Download audio from YouTube video"""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{filename}.mp4")

    if os.path.exists(output_path):
        print(f"Already exists: {output_path}")
        return output_path

    try:
        print(f"Downloading: {url}")
        yt = YouTube(url, on_progress_callback=on_progress)
        print(f"Title: {yt.title}")

        stream = yt.streams.filter(only_audio=True).first()
        if not stream:
            stream = yt.streams.filter(progressive=True).order_by('resolution').first()

        if stream:
            print(f"Downloading stream: {stream}")
            stream.download(output_path=output_dir, filename=f"{filename}.mp4")
            print(f"Saved to: {output_path}")
            return output_path
        else:
            print(f"No suitable stream found for {url}")
            return None
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None

def main():
    print("=== Downloading LCK Team Voice Videos ===\n")

    downloaded = []
    for url, filename in TEAM_VOICE_VIDEOS:
        result = download_audio(url, filename)
        if result:
            downloaded.append(result)
        print()

    print(f"\n=== Downloaded {len(downloaded)}/{len(TEAM_VOICE_VIDEOS)} videos ===")
    for path in downloaded:
        print(f"  - {path}")

if __name__ == "__main__":
    main()
