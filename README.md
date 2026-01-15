# ubv_transcribe
UniFi Protect camera audio transcription app

## Features

### Download Scheduler

The download scheduler downloads footage in 1-hour chunks with a single concurrent stream and robust retry/backoff logic.

- **Sequential processing**: Single download worker processes chunks one at a time (no parallel downloads)
- **Hourly chunks**: Each day is partitioned into 1-hour intervals
- **Retry/backoff**: Handles transient failures including rate limiting (429 errors) without crashing
- **Flexible selection**: Download from all cameras or specific camera IDs
- **Timezone aware**: Uses consistent local time (default: US/Pacific)

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

## Submodules

This repository includes the following git submodule:

- **unifi-protect-video-downloader**: Tool to download footage from a local UniFi Protect system
  - Repository: https://github.com/danielfernau/unifi-protect-video-downloader
  - Path: `unifi-protect-video-downloader/`

### Cloning with submodules

To clone this repository with all submodules:

```bash
git clone --recurse-submodules https://github.com/AaronWebster/ubv_transcribe.git
```

Or if you've already cloned the repository:

```bash
git submodule update --init --recursive
```
