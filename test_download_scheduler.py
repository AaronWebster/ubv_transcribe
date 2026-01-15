#!/usr/bin/env python3
"""
Unit tests for download_scheduler module.

Tests the download scheduling functionality without requiring actual UniFi Protect access.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
import pytz

import download_scheduler


class TestGenerateHourlyChunks(unittest.TestCase):
    """Test hourly chunk generation."""
    
    def test_single_hour(self):
        """Test generating chunks for a single hour."""
        tz = pytz.timezone('US/Pacific')
        start = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        end = tz.localize(datetime(2024, 1, 1, 1, 0, 0))
        
        chunks = download_scheduler.generate_hourly_chunks(start, end)
        
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0][0], start)
        self.assertEqual(chunks[0][1], end)
    
    def test_multiple_hours(self):
        """Test generating chunks for multiple hours."""
        tz = pytz.timezone('US/Pacific')
        start = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        end = tz.localize(datetime(2024, 1, 1, 3, 0, 0))
        
        chunks = download_scheduler.generate_hourly_chunks(start, end)
        
        self.assertEqual(len(chunks), 3)
        # Verify first chunk
        self.assertEqual(chunks[0][0], start)
        self.assertEqual(chunks[0][1], start + timedelta(hours=1))
        # Verify last chunk
        self.assertEqual(chunks[2][0], start + timedelta(hours=2))
        self.assertEqual(chunks[2][1], end)
    
    def test_full_day(self):
        """Test generating chunks for a full 24-hour day."""
        tz = pytz.timezone('US/Pacific')
        start = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        end = tz.localize(datetime(2024, 1, 2, 0, 0, 0))
        
        chunks = download_scheduler.generate_hourly_chunks(start, end)
        
        self.assertEqual(len(chunks), 24)
    
    def test_partial_hour(self):
        """Test generating chunks with partial hour at the end."""
        tz = pytz.timezone('US/Pacific')
        start = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        end = tz.localize(datetime(2024, 1, 1, 2, 30, 0))
        
        chunks = download_scheduler.generate_hourly_chunks(start, end)
        
        self.assertEqual(len(chunks), 3)
        # Last chunk should be partial
        self.assertEqual(chunks[2][0], start + timedelta(hours=2))
        self.assertEqual(chunks[2][1], end)
    
    def test_invalid_range(self):
        """Test with start date after end date."""
        tz = pytz.timezone('US/Pacific')
        start = tz.localize(datetime(2024, 1, 2, 0, 0, 0))
        end = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        
        chunks = download_scheduler.generate_hourly_chunks(start, end)
        
        self.assertEqual(len(chunks), 0)
    
    def test_same_start_end(self):
        """Test with start and end at the same time."""
        tz = pytz.timezone('US/Pacific')
        start = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        end = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        
        chunks = download_scheduler.generate_hourly_chunks(start, end)
        
        self.assertEqual(len(chunks), 0)


class TestDownloadWithRetry(unittest.TestCase):
    """Test download with retry logic."""
    
    @patch('download_scheduler.downloader_adapter.download_chunk')
    @patch('download_scheduler.time.sleep')
    def test_successful_download(self, mock_sleep, mock_download):
        """Test successful download on first attempt."""
        mock_download.return_value = "/path/to/video.mp4"
        
        result = download_scheduler.download_with_retry(
            camera_id='cam1',
            camera_name='Test Camera',
            start_dt=datetime.now(pytz.UTC),
            end_dt=datetime.now(pytz.UTC) + timedelta(hours=1),
            out_path='/tmp/videos',
            address='https://test.local',
            username='test',
            password='test',
            max_retries=3,
        )
        
        self.assertEqual(result, "/path/to/video.mp4")
        self.assertEqual(mock_download.call_count, 1)
        mock_sleep.assert_not_called()
    
    @patch('download_scheduler.downloader_adapter.download_chunk')
    @patch('download_scheduler.time.sleep')
    def test_retry_on_failure(self, mock_sleep, mock_download):
        """Test retry logic on transient failure."""
        # Fail twice, then succeed
        mock_download.side_effect = [
            Exception("Connection error"),
            Exception("Timeout"),
            "/path/to/video.mp4"
        ]
        
        result = download_scheduler.download_with_retry(
            camera_id='cam1',
            camera_name='Test Camera',
            start_dt=datetime.now(pytz.UTC),
            end_dt=datetime.now(pytz.UTC) + timedelta(hours=1),
            out_path='/tmp/videos',
            address='https://test.local',
            username='test',
            password='test',
            max_retries=3,
            initial_backoff=1.0,
        )
        
        self.assertEqual(result, "/path/to/video.mp4")
        self.assertEqual(mock_download.call_count, 3)
        # Should have slept twice (after first two failures)
        self.assertEqual(mock_sleep.call_count, 2)
    
    @patch('download_scheduler.downloader_adapter.download_chunk')
    @patch('download_scheduler.time.sleep')
    def test_exponential_backoff(self, mock_sleep, mock_download):
        """Test exponential backoff on retries."""
        mock_download.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            Exception("Error 3"),
            "/path/to/video.mp4"
        ]
        
        result = download_scheduler.download_with_retry(
            camera_id='cam1',
            camera_name='Test Camera',
            start_dt=datetime.now(pytz.UTC),
            end_dt=datetime.now(pytz.UTC) + timedelta(hours=1),
            out_path='/tmp/videos',
            address='https://test.local',
            username='test',
            password='test',
            max_retries=5,
            initial_backoff=1.0,
            max_backoff=100.0,
        )
        
        self.assertEqual(result, "/path/to/video.mp4")
        # Verify exponential backoff pattern: 1, 2, 4
        calls = mock_sleep.call_args_list
        self.assertEqual(calls[0][0][0], 1.0)
        self.assertEqual(calls[1][0][0], 2.0)
        self.assertEqual(calls[2][0][0], 4.0)
    
    @patch('download_scheduler.downloader_adapter.download_chunk')
    @patch('download_scheduler.time.sleep')
    def test_rate_limit_handling(self, mock_sleep, mock_download):
        """Test special handling for rate limit errors."""
        mock_download.side_effect = [
            Exception("429 Too Many Requests"),
            "/path/to/video.mp4"
        ]
        
        result = download_scheduler.download_with_retry(
            camera_id='cam1',
            camera_name='Test Camera',
            start_dt=datetime.now(pytz.UTC),
            end_dt=datetime.now(pytz.UTC) + timedelta(hours=1),
            out_path='/tmp/videos',
            address='https://test.local',
            username='test',
            password='test',
            max_retries=3,
            initial_backoff=1.0,
        )
        
        self.assertEqual(result, "/path/to/video.mp4")
        # Rate limit should trigger longer backoff (2x)
        self.assertEqual(mock_sleep.call_args[0][0], 2.0)
    
    @patch('download_scheduler.downloader_adapter.download_chunk')
    @patch('download_scheduler.time.sleep')
    def test_max_retries_exceeded(self, mock_sleep, mock_download):
        """Test failure after exceeding max retries."""
        mock_download.side_effect = Exception("Persistent error")
        
        result = download_scheduler.download_with_retry(
            camera_id='cam1',
            camera_name='Test Camera',
            start_dt=datetime.now(pytz.UTC),
            end_dt=datetime.now(pytz.UTC) + timedelta(hours=1),
            out_path='/tmp/videos',
            address='https://test.local',
            username='test',
            password='test',
            max_retries=2,
            initial_backoff=1.0,
        )
        
        self.assertIsNone(result)
        # Should attempt 3 times total (initial + 2 retries)
        self.assertEqual(mock_download.call_count, 3)


class TestDownloadFootageSequential(unittest.TestCase):
    """Test sequential footage download."""
    
    @patch('download_scheduler.download_with_retry')
    def test_single_camera_single_hour(self, mock_download):
        """Test downloading one hour for one camera."""
        mock_download.return_value = "/path/to/video.mp4"
        
        cameras = [{'id': 'cam1', 'name': 'Test Camera'}]
        tz = pytz.timezone('US/Pacific')
        start = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        end = tz.localize(datetime(2024, 1, 1, 1, 0, 0))
        
        result = download_scheduler.download_footage_sequential(
            cameras=cameras,
            start_date=start,
            end_date=end,
            out_path='/tmp/videos',
            address='https://test.local',
            username='test',
            password='test',
        )
        
        self.assertEqual(result['total_chunks'], 1)
        self.assertEqual(result['successful_chunks'], 1)
        self.assertEqual(result['failed_chunks'], 0)
        self.assertEqual(result['cameras_processed'], 1)
        # Verify download_with_retry was called once
        self.assertEqual(mock_download.call_count, 1)
    
    @patch('download_scheduler.download_with_retry')
    def test_multiple_cameras_multiple_hours(self, mock_download):
        """Test downloading multiple hours for multiple cameras."""
        mock_download.return_value = "/path/to/video.mp4"
        
        cameras = [
            {'id': 'cam1', 'name': 'Camera 1'},
            {'id': 'cam2', 'name': 'Camera 2'},
        ]
        tz = pytz.timezone('US/Pacific')
        start = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        end = tz.localize(datetime(2024, 1, 1, 3, 0, 0))
        
        result = download_scheduler.download_footage_sequential(
            cameras=cameras,
            start_date=start,
            end_date=end,
            out_path='/tmp/videos',
            address='https://test.local',
            username='test',
            password='test',
        )
        
        # 2 cameras × 3 hours = 6 total chunks
        self.assertEqual(result['total_chunks'], 6)
        self.assertEqual(result['successful_chunks'], 6)
        self.assertEqual(result['failed_chunks'], 0)
        self.assertEqual(result['cameras_processed'], 2)
        self.assertEqual(mock_download.call_count, 6)
    
    @patch('download_scheduler.download_with_retry')
    def test_sequential_processing(self, mock_download):
        """Test that chunks are processed sequentially."""
        call_order = []
        
        def track_calls(*args, **kwargs):
            call_order.append((kwargs['camera_name'], kwargs['start_dt']))
            return "/path/to/video.mp4"
        
        mock_download.side_effect = track_calls
        
        cameras = [
            {'id': 'cam1', 'name': 'Camera 1'},
            {'id': 'cam2', 'name': 'Camera 2'},
        ]
        tz = pytz.timezone('US/Pacific')
        start = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        end = tz.localize(datetime(2024, 1, 1, 2, 0, 0))
        
        download_scheduler.download_footage_sequential(
            cameras=cameras,
            start_date=start,
            end_date=end,
            out_path='/tmp/videos',
            address='https://test.local',
            username='test',
            password='test',
        )
        
        # Verify sequential order: all chunks for cam1, then all chunks for cam2
        self.assertEqual(len(call_order), 4)
        self.assertEqual(call_order[0][0], 'Camera 1')
        self.assertEqual(call_order[1][0], 'Camera 1')
        self.assertEqual(call_order[2][0], 'Camera 2')
        self.assertEqual(call_order[3][0], 'Camera 2')
    
    @patch('download_scheduler.download_with_retry')
    def test_continue_after_failure(self, mock_download):
        """Test that processing continues after individual chunk failures."""
        # First two chunks fail, rest succeed
        mock_download.side_effect = [
            None,  # Failure
            None,  # Failure
            "/path/to/video.mp4",
            "/path/to/video.mp4",
        ]
        
        cameras = [
            {'id': 'cam1', 'name': 'Camera 1'},
            {'id': 'cam2', 'name': 'Camera 2'},
        ]
        tz = pytz.timezone('US/Pacific')
        start = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        end = tz.localize(datetime(2024, 1, 1, 2, 0, 0))
        
        result = download_scheduler.download_footage_sequential(
            cameras=cameras,
            start_date=start,
            end_date=end,
            out_path='/tmp/videos',
            address='https://test.local',
            username='test',
            password='test',
        )
        
        # Should process all 4 chunks despite failures
        self.assertEqual(result['total_chunks'], 4)
        self.assertEqual(result['successful_chunks'], 2)
        self.assertEqual(result['failed_chunks'], 2)
        self.assertEqual(mock_download.call_count, 4)
    
    @patch('download_scheduler.download_with_retry')
    def test_zero_chunks(self, mock_download):
        """Test handling of zero chunks (e.g., invalid date range)."""
        mock_download.return_value = "/path/to/video.mp4"
        
        cameras = [{'id': 'cam1', 'name': 'Test Camera'}]
        tz = pytz.timezone('US/Pacific')
        # Start and end at same time = no chunks
        start = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        end = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        
        result = download_scheduler.download_footage_sequential(
            cameras=cameras,
            start_date=start,
            end_date=end,
            out_path='/tmp/videos',
            address='https://test.local',
            username='test',
            password='test',
        )
        
        # Should handle zero chunks gracefully
        self.assertEqual(result['total_chunks'], 0)
        self.assertEqual(result['successful_chunks'], 0)
        self.assertEqual(result['failed_chunks'], 0)
        # No downloads should be attempted
        mock_download.assert_not_called()


if __name__ == '__main__':
    unittest.main()
