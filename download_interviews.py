#!/usr/bin/env python3
"""Download LCK interview videos for speaker database"""

import os
from pytubefix import YouTube
from pytubefix.cli import on_progress

# Interview videos to download
INTERVIEWS = [
    # Faker & Keria Worlds 2024
    ("https://www.youtube.com/watch?v=7hGo157iks8", "faker_keria_worlds2024"),
    # Gumayusi & Faker LCK 2024
    ("https://www.youtube.com/watch?v=5V50mTUxgIE", "gumayusi_faker_lck2024"),
    # Doran & Faker Worlds 2025
    ("https://www.youtube.com/watch?v=XFs6SlzJS7M", "doran_faker_worlds2025"),
    # Keria & Faker LCK Spring 2024
    ("https://www.youtube.com/watch?v=cms4TN-dRBE", "keria_faker_lck_spring2024"),
    # Zeus & Faker Worlds 2024
    ("https://www.youtube.com/watch?v=_qv6hZQsjTk", "zeus_faker_worlds2024"),
]

def download_audio(url: str, filename: str, output_dir: str = "data/interviews"):
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

        # Get audio stream
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
    print("=== Downloading LCK Interview Videos ===\n")

    downloaded = []
    for url, filename in INTERVIEWS:
        result = download_audio(url, filename)
        if result:
            downloaded.append(result)
        print()

    print(f"\n=== Downloaded {len(downloaded)}/{len(INTERVIEWS)} videos ===")
    for path in downloaded:
        print(f"  - {path}")

if __name__ == "__main__":
    main()
