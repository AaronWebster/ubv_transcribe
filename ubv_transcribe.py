#!/usr/bin/env python3
"""
ubv_transcribe - UniFi Protect camera audio transcription app

Main executable script with CLI, logging, and directory management.
"""

import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path


def setup_logging(log_level=logging.INFO):
    """
    Configure structured logging with info/warn/error levels.
    
    Args:
        log_level: The logging level to use (default: INFO)
    """
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def _show_submodule_error(message):
    """
    Display a clear error message about submodule initialization.
    
    Args:
        message: Specific error message to display
    """
    logging.error(message)
    logging.error("Please initialize the submodule with:")
    logging.error("  git submodule update --init --recursive")
    sys.exit(1)


def check_submodule():
    """
    Check if the unifi-protect-video-downloader submodule is initialized.
    
    Raises:
        SystemExit: If the submodule is not initialized with a clear error message.
    """
    script_dir = Path(__file__).parent.absolute()
    submodule_path = script_dir / 'unifi-protect-video-downloader'
    
    if not submodule_path.exists():
        _show_submodule_error("Submodule 'unifi-protect-video-downloader' directory does not exist.")
    
    if not submodule_path.is_dir():
        _show_submodule_error("Submodule 'unifi-protect-video-downloader' path is not a directory.")
    
    # Check if submodule is empty (not initialized)
    if not any(submodule_path.iterdir()):
        _show_submodule_error("Submodule 'unifi-protect-video-downloader' is not initialized.")
    
    logging.info(f"Submodule found at: {submodule_path}")


def get_temp_directory():
    """
    Get a secure temp working directory for the application.
    Uses a predictable location within the user's temp directory with
    appropriate permissions.
    
    Returns:
        Path: Path object pointing to the temp directory
    """
    # Use a subdirectory in the system temp to keep it predictable but secure
    # The parent temp directory already has appropriate permissions
    base_temp = Path(tempfile.gettempdir())
    temp_dir = base_temp / 'ubv_transcribe'
    
    # Create with restricted permissions (owner only)
    temp_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    logging.info(f"Temp working directory: {temp_dir}")
    return temp_dir


def setup_transcripts_directory():
    """
    Create the transcripts/ directory if it doesn't exist.
    Does not create any additional persistent state files.
    
    Returns:
        Path: Path object pointing to the transcripts directory
    """
    script_dir = Path(__file__).parent.absolute()
    transcripts_dir = script_dir / 'transcripts'
    transcripts_dir.mkdir(exist_ok=True)
    logging.info(f"Transcripts directory: {transcripts_dir}")
    return transcripts_dir


def parse_arguments():
    """
    Parse command-line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='UniFi Protect camera audio transcription app',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --help
  %(prog)s --verbose

For more information, visit:
  https://github.com/AaronWebster/ubv_transcribe
        """
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose (DEBUG) logging'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 0.1.0'
    )
    
    return parser.parse_args()


def main():
    """
    Main entry point for the ubv_transcribe application.
    """
    args = parse_arguments()
    
    # Setup logging based on verbosity
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(log_level)
    
    logging.info("Starting ubv_transcribe")
    
    # Check that the submodule is initialized
    check_submodule()
    
    # Setup working directories
    temp_dir = get_temp_directory()
    transcripts_dir = setup_transcripts_directory()
    
    logging.info("Initialization complete")
    logging.info("ubv_transcribe is ready to use")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
