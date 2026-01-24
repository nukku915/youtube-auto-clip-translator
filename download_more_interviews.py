#!/usr/bin/env python3
"""Download more LCK interview videos for speaker database"""

import os
from pytubefix import YouTube
from pytubefix.cli import on_progress

# More interview videos to download
INTERVIEWS = [
    # Oner interviews
    ("https://www.youtube.com/watch?v=MhP5Pc845Ak", "oner_faker_summer2024"),
    ("https://www.youtube.com/watch?v=4hJQpQKg-AE", "zeus_oner_spring2024"),
    ("https://www.youtube.com/watch?v=xknyXeAOggM", "gumayusi_oner_worlds2024"),
    ("https://www.youtube.com/watch?v=l5vuZV7r3bw", "oner_keria_summer2024"),

    # Gumayusi interviews
    ("https://www.youtube.com/watch?v=gPFNW-V_4ew", "gumayusi_faker_spring2024_2"),
    ("https://www.youtube.com/watch?v=eZFG1xpUbHo", "gumayusi_worlds2024_solo"),
    ("https://www.youtube.com/watch?v=vg8xIP1Hvf0", "keria_gumayusi_summer2024"),

    # Keria interviews
    ("https://www.youtube.com/watch?v=_Ym9OvFJUzY", "faker_keria_spring2024_2"),
    ("https://www.youtube.com/watch?v=I7ZmtFUNfmw", "keria_faker_spring2024_3"),

    # Zeus interviews (for reference)
    ("https://www.youtube.com/watch?v=5PoWCe0HnH0", "zeus_keria_spring2024"),
    ("https://www.youtube.com/watch?v=5pDWbs6YF_g", "gumayusi_zeus_summer2024"),

    # Full team interview
    ("https://www.youtube.com/watch?v=DK6HTLem6tw", "t1_full_team_worlds2024"),
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
    print("=== Downloading More LCK Interview Videos ===\n")

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
