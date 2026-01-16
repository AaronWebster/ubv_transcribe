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
from datetime import datetime, time, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Import the downloader adapter, footage discovery, and download scheduler
import downloader_adapter
import footage_discovery
import download_scheduler


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


def load_env_config(env_file=None):
    """
    Load UniFi Protect credentials from .env file.
    
    Args:
        env_file: Optional path to custom .env file. If None, looks for .env in script directory.
    
    Returns:
        dict: Dictionary with username, password, and address keys
        
    Raises:
        SystemExit: If required environment variables are missing
    """
    # Determine which .env file to load
    if env_file:
        env_path = Path(env_file)
        if not env_path.exists():
            logging.error(f"Specified .env file not found: {env_file}")
            sys.exit(1)
        load_dotenv(env_path)
        logging.info(f"Loaded environment from: {env_file}")
    else:
        # Try to load from .env in script directory
        script_dir = Path(__file__).parent.absolute()
        default_env = script_dir / '.env'
        if default_env.exists():
            load_dotenv(default_env)
            logging.info(f"Loaded environment from: {default_env}")
        else:
            logging.info("No .env file found, using environment variables")
    
    # Required environment variables
    required_vars = [
        'UNIFI_PROTECT_USERNAME',
        'UNIFI_PROTECT_PASSWORD',
        'UNIFI_PROTECT_ADDRESS'
    ]
    
    # Check for missing variables
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logging.error("Missing required environment variables:")
        for var in missing_vars:
            logging.error(f"  - {var}")
        logging.error("")
        logging.error("Please set these variables in a .env file or as environment variables.")
        logging.error("See .env.example for a template.")
        sys.exit(1)
    
    # Log successful validation (without exposing secrets)
    logging.info("UniFi Protect credentials loaded successfully")
    logging.debug(f"UniFi Protect address: {os.getenv('UNIFI_PROTECT_ADDRESS')}")
    logging.debug(f"UniFi Protect username: {os.getenv('UNIFI_PROTECT_USERNAME')}")
    # Never log password, even in debug mode
    
    return {
        'username': os.getenv('UNIFI_PROTECT_USERNAME'),
        'password': os.getenv('UNIFI_PROTECT_PASSWORD'),
        'address': os.getenv('UNIFI_PROTECT_ADDRESS')
    }


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
    try:
        if not any(submodule_path.iterdir()):
            _show_submodule_error("Submodule 'unifi-protect-video-downloader' is not initialized.")
    except (PermissionError, OSError) as e:
        logging.error(f"Unable to access submodule directory: {e}")
        _show_submodule_error("Submodule 'unifi-protect-video-downloader' directory is not accessible.")
    
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
  %(prog)s --env-file /path/to/.env

Configuration:
  UniFi Protect credentials can be provided via:
  - A .env file in the script directory (default)
  - A custom .env file specified with --env-file
  - Environment variables

  Required variables:
  - UNIFI_PROTECT_USERNAME
  - UNIFI_PROTECT_PASSWORD
  - UNIFI_PROTECT_ADDRESS

  See .env.example for a template.

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
        '--env-file',
        metavar='PATH',
        help='Path to .env file (default: .env in script directory)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 0.1.0'
    )
    
    parser.add_argument(
        '--timezone',
        metavar='TZ',
        help='Timezone for footage discovery (default: US/Pacific). Examples: US/Pacific, US/Eastern, UTC'
    )
    
    parser.add_argument(
        '--discover-footage',
        action='store_true',
        help='Discover available footage date range across all cameras'
    )
    
    parser.add_argument(
        '--download',
        action='store_true',
        help='Download footage in hourly chunks with retry/backoff'
    )
    
    parser.add_argument(
        '--start-date',
        metavar='YYYY-MM-DD',
        help='Start date for download (required with --download)'
    )
    
    parser.add_argument(
        '--end-date',
        metavar='YYYY-MM-DD',
        help='End date for download (required with --download)'
    )
    
    parser.add_argument(
        '--camera-ids',
        metavar='ID',
        nargs='+',
        help='Camera IDs to download (space-separated). If not specified, downloads all cameras.'
    )
    
    parser.add_argument(
        '--output-dir',
        metavar='PATH',
        help='Output directory for downloaded videos (default: ./videos)'
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
    
    # Load UniFi Protect credentials
    config = load_env_config(args.env_file)
    
    # Check that the submodule is initialized
    check_submodule()
    
    # Setup working directories
    temp_dir = get_temp_directory()
    transcripts_dir = setup_transcripts_directory()
    
    logging.info("Initialization complete")
    
    # Track output directory for cleanup
    output_dir = None
    
    try:
        # Discover footage if requested
        if args.discover_footage:
            logging.info("=" * 60)
            logging.info("FOOTAGE DISCOVERY")
            logging.info("=" * 60)
            try:
                discovery_result = footage_discovery.discover_footage_range(
                    address=config['address'],
                    username=config['username'],
                    password=config['password'],
                    timezone_str=args.timezone,
                )
                
                logging.info("=" * 60)
                logging.info("DISCOVERY RESULTS")
                logging.info("=" * 60)
                logging.info(f"Timezone: {discovery_result['timezone']}")
                logging.info(f"Total cameras: {len(discovery_result['cameras'])}")
                
                if discovery_result['earliest_date']:
                    logging.info(f"Earliest footage: {discovery_result['earliest_date'].date()}")
                    logging.info(f"Latest footage: {discovery_result['latest_date'].date()}")
                    logging.info(f"Total days with footage: {discovery_result['days_with_footage']}")
                    
                    logging.info("")
                    logging.info("Per-camera footage ranges:")
                    for camera_id, range_info in discovery_result['per_camera_ranges'].items():
                        if range_info['earliest_date']:
                            logging.info(
                                f"  {range_info['camera_name']}: "
                                f"{range_info['earliest_date'].date()} to "
                                f"{range_info['latest_date'].date()}"
                            )
                        else:
                            logging.info(f"  {range_info['camera_name']}: No footage")
                else:
                    logging.info("No footage found for any camera")
                
                logging.info("=" * 60)
                
            except Exception as e:
                logging.error(f"Error during footage discovery: {e}")
                if args.verbose:
                    import traceback
                    logging.error(traceback.format_exc())
                return 1
        
        # Download footage if requested
        if args.download:
            logging.info("=" * 60)
            logging.info("DOWNLOAD SCHEDULER")
            logging.info("=" * 60)
            
            # Validate required arguments
            if not args.start_date or not args.end_date:
                logging.error("--start-date and --end-date are required with --download")
                logging.error("Example: --download --start-date 2024-01-01 --end-date 2024-01-02")
                return 1
            
            try:
                # Parse dates
                tz = footage_discovery.get_timezone(args.timezone)
                
                try:
                    start_date_naive = datetime.strptime(args.start_date, '%Y-%m-%d')
                    start_date = tz.localize(datetime.combine(start_date_naive.date(), time.min))
                except ValueError:
                    logging.error(f"Invalid start date format: {args.start_date}. Expected YYYY-MM-DD")
                    return 1
                
                try:
                    end_date_naive = datetime.strptime(args.end_date, '%Y-%m-%d')
                    # End date should be at the end of the day (midnight of next day)
                    end_date = tz.localize(datetime.combine(end_date_naive.date(), time.min)) + timedelta(days=1)
                except ValueError:
                    logging.error(f"Invalid end date format: {args.end_date}. Expected YYYY-MM-DD")
                    return 1
                
                # Get camera list
                logging.info("Retrieving camera list...")
                all_cameras = downloader_adapter.list_cameras(
                    address=config['address'],
                    username=config['username'],
                    password=config['password'],
                )
                
                # Filter cameras if specific IDs were requested
                if args.camera_ids:
                    cameras = [cam for cam in all_cameras if cam['id'] in args.camera_ids]
                    if len(cameras) < len(args.camera_ids):
                        found_ids = {cam['id'] for cam in cameras}
                        missing_ids = set(args.camera_ids) - found_ids
                        logging.warning(f"Some camera IDs not found: {missing_ids}")
                else:
                    cameras = all_cameras
                
                if not cameras:
                    logging.error("No cameras to download from")
                    return 1
                
                logging.info(f"Will download from {len(cameras)} camera(s):")
                for camera in cameras:
                    logging.info(f"  - {camera['name']} (ID: {camera['id']})")
                
                # Determine output directory
                if args.output_dir:
                    output_dir = Path(args.output_dir)
                else:
                    script_dir = Path(__file__).parent.absolute()
                    output_dir = script_dir / 'videos'
                
                output_dir.mkdir(parents=True, exist_ok=True)
                logging.info(f"Output directory: {output_dir}")
                
                # Run the download scheduler
                result = download_scheduler.download_footage_sequential(
                    cameras=cameras,
                    start_date=start_date,
                    end_date=end_date,
                    out_path=str(output_dir),
                    address=config['address'],
                    username=config['username'],
                    password=config['password'],
                    transcripts_dir=transcripts_dir,
                )
                
                # Report results
                if result['failed_chunks'] > 0:
                    logging.warning(
                        f"Download completed with {result['failed_chunks']} failed chunks. "
                        "Check logs for details."
                    )
                    return 1
                else:
                    logging.info("All downloads completed successfully!")
                    return 0
                    
            except Exception as e:
                logging.error(f"Error during download: {e}")
                if args.verbose:
                    import traceback
                    logging.error(traceback.format_exc())
                return 1
        
        if not args.discover_footage and not args.download:
            # Demonstrate the downloader adapter functionality
            logging.info("Testing downloader adapter...")
            try:
                cameras = downloader_adapter.list_cameras(
                    address=config['address'],
                    username=config['username'],
                    password=config['password'],
                )
                logging.info(f"Successfully listed {len(cameras)} camera(s) from UniFi Protect")
                for camera in cameras:
                    logging.info(f"  - {camera['name']} (ID: {camera['id']})")
            except Exception as e:
                logging.warning(f"Could not list cameras (this is OK if UniFi Protect is not accessible): {e}")
        
        logging.info("ubv_transcribe is ready to use")
        
        return 0
        
    finally:
        # Clean up temporary directories and leftover files (best effort)
        _cleanup_temp_directories(temp_dir, output_dir)


def _cleanup_temp_directories(temp_dir: Path, output_dir: Optional[Path]) -> None:
    """
    Clean up temporary directories and leftover files.
    
    This is a best-effort cleanup that removes:
    - Temporary working directory
    - WAV files directory
    - Empty videos output directory
    
    Args:
        temp_dir: Temporary working directory
        output_dir: Videos output directory (may be None)
    """
    import shutil
    import transcoder
    
    # Clean up transcoder WAV directory
    try:
        transcoder.cleanup_temp_files()
    except Exception as e:
        logging.warning(f"Failed to clean up transcoder temp files: {e}")
    
    # Clean up temp working directory
    if temp_dir and temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
            logging.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logging.warning(f"Failed to clean up temporary directory {temp_dir}: {e}")
    
    # Clean up videos directory if it's empty
    if output_dir and output_dir.exists():
        try:
            # Check if directory is empty
            if not any(output_dir.iterdir()):
                output_dir.rmdir()
                logging.info(f"Removed empty output directory: {output_dir}")
            else:
                # Try to remove any leftover video files
                for file_path in output_dir.glob('*.mp4'):
                    try:
                        file_path.unlink()
                        logging.info(f"Cleaned up video file: {file_path}")
                    except Exception as e:
                        logging.warning(f"Failed to clean up video file {file_path}: {e}")
                
                # Check again if directory is now empty
                if not any(output_dir.iterdir()):
                    output_dir.rmdir()
                    logging.info(f"Removed empty output directory: {output_dir}")
        except Exception as e:
            logging.warning(f"Failed to clean up output directory {output_dir}: {e}")


if __name__ == '__main__':
    sys.exit(main())
