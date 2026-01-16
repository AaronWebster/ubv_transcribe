# ubv_transcribe
UniFi Protect camera audio transcription app

## Prerequisites

### Required Software

- **Python 3**: Python 3.6 or higher
- **ffmpeg**: Required for video-to-audio transcoding
  - Install on Ubuntu/Debian: `sudo apt-get install ffmpeg`
  - Install on macOS: `brew install ffmpeg`
  - Install on other systems: See [ffmpeg.org](https://ffmpeg.org/download.html)
- **Git**: For cloning the repository and initializing submodules
- **whisper.cpp** (optional): Required for audio transcription
  - Clone and build from: [https://github.com/ggerganov/whisper.cpp](https://github.com/ggerganov/whisper.cpp)
  - Default binary path: `~/whisper.cpp/build/bin/whisper-cli`
  - Download a model (e.g., `ggml-large-v3.bin`) to: `~/whisper.cpp/models/`
  - See [whisper.cpp README](https://github.com/ggerganov/whisper.cpp/blob/master/README.md) for build instructions

### Python Dependencies

The following Python packages are required (see `requirements.txt`):

- `python-dotenv>=1.0.0` - Environment variable management
- `pytz>=2023.3` - Timezone handling
- `ffmpeg-python>=0.2.0` - FFmpeg wrapper for video transcoding

## Installation

### 1. Clone the Repository with Submodules

This repository includes the `unifi-protect-video-downloader` as a git submodule. Clone with submodules included:

```bash
git clone --recurse-submodules https://github.com/AaronWebster/ubv_transcribe.git
cd ubv_transcribe
```

**Or** if you've already cloned the repository without submodules:

```bash
cd ubv_transcribe
git submodule update --init --recursive
```

### 2. Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

Or install individually:

```bash
pip3 install python-dotenv pytz ffmpeg-python
```

### 3. Configure Environment Variables

Create a `.env` file in the project root directory with your UniFi Protect credentials:

```bash
cp .env.example .env
```

Edit `.env` and fill in your actual credentials:

```env
# UniFi Protect username
UNIFI_PROTECT_USERNAME=your_username_here

# UniFi Protect password
UNIFI_PROTECT_PASSWORD=your_password_here

# UniFi Protect address (e.g., https://192.168.1.1 or https://unifi.local)
UNIFI_PROTECT_ADDRESS=https://your_unifi_address_here
```

**Required environment variables:**
- `UNIFI_PROTECT_USERNAME` - Your UniFi Protect username
- `UNIFI_PROTECT_PASSWORD` - Your UniFi Protect password
- `UNIFI_PROTECT_ADDRESS` - URL to your UniFi Protect system (e.g., `https://192.168.1.1`)

### 4. (Optional) Set Up whisper.cpp

If you want automatic transcription, install and build whisper.cpp:

```bash
# Clone whisper.cpp
cd ~
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp

# Build (see whisper.cpp README for platform-specific instructions)
make

# Download a model
bash ./models/download-ggml-model.sh large-v3
```

The default paths expected by ubv_transcribe are:
- Binary: `~/whisper.cpp/build/bin/whisper-cli`
- Model: `~/whisper.cpp/models/ggml-large-v3.bin`

You can specify custom paths using `--whisper-bin` and `--model-path` arguments if needed.

### 5. Verify Installation

Test that everything is set up correctly:

```bash
python3 ubv_transcribe.py
```

This should connect to your UniFi Protect system and list available cameras.

## Quick Start

### Discover Available Footage

Find out what footage is available from your cameras:

```bash
python3 ubv_transcribe.py --discover-footage
```

### Download and Transcribe Footage

Download footage for a specific date range (this will also transcode to audio and create transcripts if whisper.cpp is configured):

```bash
# Download footage for all cameras
python3 ubv_transcribe.py --download --start-date 2024-01-01 --end-date 2024-01-02

# Download for specific cameras only
python3 ubv_transcribe.py --download \
  --start-date 2024-01-01 --end-date 2024-01-02 \
  --camera-ids abc123 def456
```

### Output Files

The application creates the following output structure:

- **Videos**: `videos/` directory (or custom path via `--output-dir`)
  - Raw video files downloaded from UniFi Protect
  - Files are cleaned up after processing by default
- **Transcripts**: `transcripts/YYYY/YYYY-MM-DD_CAMERANAME.md`
  - Daily transcript files organized by year
  - Example: `transcripts/2024/2024-01-15_Front Door.md`
  - Automatic deduplication prevents re-transcribing the same footage

## Features

### Download Scheduler

The download scheduler downloads footage in 1-hour chunks with a single concurrent stream and robust retry/backoff logic. It automatically transcodes videos to WAV format, transcribes them with Whisper, and merges transcripts into daily Markdown files.

- **Sequential processing**: Single download worker processes chunks one at a time (no parallel downloads)
- **Hourly chunks**: Each day is partitioned into 1-hour intervals
- **Retry/backoff**: Handles transient failures including rate limiting (429 errors) without crashing
- **Flexible selection**: Download from all cameras or specific camera IDs
- **Timezone aware**: Uses consistent local time (default: US/Pacific)
- **Automatic transcription**: Transcodes video to WAV and transcribes with Whisper (if configured)
- **Daily transcript merging**: Combines hourly transcripts into per-day Markdown files with deduplication

#### Usage

```bash
# Download footage for a date range (all cameras)
python3 ubv_transcribe.py --download --start-date 2024-01-01 --end-date 2024-01-02

# Download for specific cameras only
python3 ubv_transcribe.py --download \
  --start-date 2024-01-01 --end-date 2024-01-02 \
  --camera-ids abc123 def456

# Use a different timezone and output directory
python3 ubv_transcribe.py --download \
  --start-date 2024-01-01 --end-date 2024-01-02 \
  --timezone US/Eastern \
  --output-dir /path/to/videos

# Enable verbose logging for detailed information
python3 ubv_transcribe.py --download \
  --start-date 2024-01-01 --end-date 2024-01-02 \
  --verbose
```

#### Output

The download scheduler will:
- Create hourly video chunks for each camera
- Transcode videos to WAV format (16kHz, mono, pcm_s16le)
- Transcribe audio with Whisper (if configured)
- Merge transcripts into daily Markdown files at `transcripts/YYYY/YYYY-MM-DD_CAMERANAME.md`
- Log progress for each chunk
- Automatically retry failed downloads with exponential backoff
- Provide a summary of successful and failed downloads

Example output:
```
Starting sequential download for 2 camera(s)
Processing 48 total chunks (2 cameras × 24 time intervals)

Processing camera 1/2: Front Door (abc123)
Downloading chunk for Front Door (2024-01-01 00:00 to 01:00)
Successfully downloaded chunk to: videos/Front Door - 2024-01-01 - 00.00.00+0000.mp4
...

DOWNLOAD SUMMARY
==============================================================
Total chunks attempted: 48
Successful downloads: 48
Failed downloads: 0
Success rate: 100.0%
==============================================================
```

#### Transcript Output Format

Transcripts are automatically merged into daily Markdown files:

- **Location**: `transcripts/YYYY/YYYY-MM-DD_CAMERANAME.md`
- **Structure**: 
  - Header with date and camera name
  - Hourly sections with timestamps (HH:MM:SS - HH:MM:SS)
  - Transcript text for each hour
  - Hidden chunk markers for deduplication tracking
- **Deduplication**: Each time segment is only transcribed once, even if the download is run multiple times

Example transcript file (`transcripts/2024/2024-01-15_Front Door.md`):

```markdown
# 2024-01-15 - Front Door

Transcript for camera **Front Door** on 2024-01-15.

---

<!-- CHUNK: Front Door_2024-01-15_14:00:00 -->

## 14:00:00 - 15:00:00

[Transcript text for this hour]

---

<!-- CHUNK: Front Door_2024-01-15_15:00:00 -->

## 15:00:00 - 16:00:00

[Transcript text for this hour]

---
```

### Footage Discovery

The footage discovery feature allows you to iterate backward through days to determine the available footage range across all cameras.

- **Start from today**: Begins checking from the current date
- **Go backwards**: Iterates day by day into the past
- **Stops when no footage**: Stops when the API indicates no earlier footage exists
- **Per-camera tracking**: Tracks footage ranges individually for each camera
- **Timezone aware**: Uses consistent local time (default: US/Pacific)

#### Usage

```bash
# Discover footage range using default timezone (US/Pacific)
python3 ubv_transcribe.py --discover-footage

# Use a different timezone
python3 ubv_transcribe.py --discover-footage --timezone US/Eastern
python3 ubv_transcribe.py --discover-footage --timezone UTC

# Enable verbose logging for detailed information
python3 ubv_transcribe.py --discover-footage --verbose
```

#### Output

The footage discovery will output:
- Total number of cameras found
- Earliest and latest dates with footage
- Total days with footage available
- Per-camera footage ranges

Example output:
```
Found 2 camera(s):
  - Front Door (ID: abc123)
  - Backyard (ID: def456)

Footage found on 2026-01-15
Footage found on 2026-01-14
...
No footage found on 2026-01-01 - stopping

DISCOVERY RESULTS
==============================================================
Timezone: US/Pacific
Total cameras: 2
Earliest footage: 2026-01-02
Latest footage: 2026-01-15
Total days with footage: 14

Per-camera footage ranges:
  Front Door: 2026-01-05 to 2026-01-15
  Backyard: 2026-01-02 to 2026-01-15
```

## Additional Information

### Submodules

This repository includes the `unifi-protect-video-downloader` as a git submodule for downloading footage from UniFi Protect. The submodule is automatically initialized when you follow the installation instructions above.

- **Repository**: https://github.com/danielfernau/unifi-protect-video-downloader
- **Path**: `unifi-protect-video-downloader/`

### Troubleshooting

If you encounter issues:

1. **Submodule not initialized**: Make sure you ran `git submodule update --init --recursive`
2. **Missing ffmpeg**: Install ffmpeg using your system's package manager
3. **Whisper.cpp not found**: The app will work without whisper.cpp but won't generate transcripts. Install it if you need transcription functionality.
4. **Authentication errors**: Verify your `.env` file has the correct UniFi Protect credentials and address

For more help, please open an issue on GitHub.
