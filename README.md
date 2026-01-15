# ubv_transcribe
UniFi Protect camera audio transcription app

## Features

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
