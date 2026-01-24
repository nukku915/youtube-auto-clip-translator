#!/usr/bin/env python3
"""Download DRX and T1 vs DRX interviews"""

import os
from pytubefix import YouTube
from pytubefix.cli import on_progress

# DRX and T1 vs DRX interviews
INTERVIEWS = [
    # T1 vs DRX LCK CUP 2025 (same match we're analyzing!)
    ("https://www.youtube.com/watch?v=fJZgAKPHqWM", "oner_t1_vs_drx_lckcup2025"),

    # DRX 2025 interviews
    ("https://www.youtube.com/watch?v=C66JEgLXtCI", "drx_lck2025"),
    ("https://www.youtube.com/watch?v=Bb7rIUAi938", "drx_rich_lck2025"),
    ("https://www.youtube.com/watch?v=e-Zqmb-ervs", "drx_teddy_lck2025"),
    ("https://www.youtube.com/watch?v=tNbICOf4xWE", "drx_dk_lck2025"),

    # More T1 2025 interviews
    ("https://www.youtube.com/watch?v=I_y_tDv6JXU", "faker_t1_vs_drx_lck2025"),
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
    print("=== Downloading DRX & T1 vs DRX Interviews ===\n")

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
