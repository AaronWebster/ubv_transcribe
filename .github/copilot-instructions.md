# GitHub Copilot Instructions

## Overview
This is a Python application for downloading and transcribing audio from UniFi Protect camera footage. The app downloads footage in hourly chunks, transcodes video to WAV audio format, transcribes with Whisper, and merges transcripts into daily Markdown files.

## Tech Stack
- **Language**: Python 3
- **Key Dependencies**:
  - `python-dotenv` - Environment variable management
  - `pytz` - Timezone handling (default: US/Pacific)
  - `ffmpeg-python` - Video transcoding to WAV audio
- **Testing Framework**: Python `unittest` module
- **Submodules**: `unifi-protect-video-downloader` for footage download

## Testing Requirements
- **Always** add or update unit tests for any new features or behavior changes
- **Always** run unit tests before finishing a pull request, even if the change seems minor
- Tests use Python's `unittest` framework with mocking via `unittest.mock`
- Run tests with: `python3 -m unittest discover -s . -p 'test_*.py' -v`
- Test files follow the pattern `test_*.py` and mirror the module they test
- Use descriptive test method names starting with `test_` that explain what is being tested
- Use docstrings in test methods to provide additional context

## Code Structure and Conventions
- **Module organization**: Each major feature is in its own module (e.g., `download_scheduler.py`, `footage_discovery.py`, `transcoder.py`)
- **Main entry point**: `ubv_transcribe.py` provides CLI interface and orchestrates other modules
- **Type hints**: Use type hints from `typing` module (e.g., `List`, `Dict`, `Optional`, `Tuple`)
- **Docstrings**: All functions and classes must have docstrings explaining purpose, args, returns, and examples
- **Timezone handling**: Always use timezone-aware datetime objects with `pytz`
- **Logging**: Use Python's `logging` module (not print statements) for all output
- **Error handling**: Use robust retry logic with exponential backoff for network operations

## Coding Standards
- Use descriptive variable and function names
- Follow PEP 8 style guidelines
- Add shebang `#!/usr/bin/env python3` to executable scripts
- Keep functions focused and single-purpose
- Prefer composition over complex inheritance
- Use context managers (`with` statements) for file operations
- Include type hints for function parameters and return values

## Testing Best Practices
- Test files should mirror the structure of the module they test
- Use `setUp` and `tearDown` methods for test fixture management
- Use `tempfile.mkdtemp()` for temporary directories in tests
- Mock external dependencies (API calls, file I/O) using `unittest.mock.patch`
- Group related tests into test classes that inherit from `unittest.TestCase`
- Each test should be independent and not rely on other tests
- Test edge cases, error conditions, and normal operations

## Environment and Configuration
- Configuration uses `.env` files (see `.env.example` for template)
- Required environment variables: `UNIFI_PROTECT_USERNAME`, `UNIFI_PROTECT_PASSWORD`, `UNIFI_PROTECT_ADDRESS`
- Load environment variables with `python-dotenv` using `load_dotenv()`
- Never commit credentials or `.env` files to the repository

## Development Workflow
1. Make minimal, focused changes to address specific issues
2. Add or update tests for your changes
3. Run tests: `python3 -m unittest discover -s . -p 'test_*.py' -v`
4. Verify all tests pass before submitting PR
5. Update documentation (README.md, docstrings) if adding features or changing behavior

## Important Notes
- This repository uses a git submodule for the UniFi Protect downloader
- Output directories: `videos/` for downloaded footage, `transcripts/` for transcript files
- Transcript files are organized by year: `transcripts/YYYY/YYYY-MM-DD_CAMERANAME.md`
- The app processes footage sequentially (no parallel downloads) to respect API rate limits
- Retry logic includes detection of rate limiting (429 errors) with exponential backoff
