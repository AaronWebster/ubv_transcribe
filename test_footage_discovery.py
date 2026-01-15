#!/usr/bin/env python3
"""
Unit tests for footage_discovery module.

Tests the footage discovery functionality without requiring actual UniFi Protect access.
"""

import unittest
from datetime import datetime, timedelta, time
from unittest.mock import patch, MagicMock
import pytz

import footage_discovery


class TestGetTimezone(unittest.TestCase):
    """Test timezone handling."""
    
    def test_default_timezone(self):
        """Test that default timezone is US/Pacific."""
        tz = footage_discovery.get_timezone(None)
        self.assertEqual(tz.zone, 'US/Pacific')
    
    def test_valid_timezone(self):
        """Test that valid timezone strings are handled correctly."""
        tz = footage_discovery.get_timezone('US/Eastern')
        self.assertEqual(tz.zone, 'US/Eastern')
        
        tz = footage_discovery.get_timezone('UTC')
        self.assertEqual(tz.zone, 'UTC')
    
    def test_invalid_timezone(self):
        """Test that invalid timezone strings fall back to default."""
        tz = footage_discovery.get_timezone('Invalid/Timezone')
        self.assertEqual(tz.zone, 'US/Pacific')


class TestCheckFootageExists(unittest.TestCase):
    """Test footage existence checking."""
    
    @patch('footage_discovery.downloader_adapter.list_cameras')
    def test_no_recording_history(self, mock_list_cameras):
        """Test camera with no recording history."""
        mock_list_cameras.return_value = [{
            'id': 'camera1',
            'name': 'Test Camera',
            'recording_start': datetime.min,
        }]
        
        tz = pytz.timezone('US/Pacific')
        check_date = tz.localize(datetime.combine(datetime.now().date(), time.min))
        
        result = footage_discovery.check_footage_exists(
            camera_id='camera1',
            camera_name='Test Camera',
            check_date=check_date,
            address='https://test.local',
            username='test',
            password='test',
        )
        
        self.assertFalse(result)
    
    @patch('footage_discovery.downloader_adapter.list_cameras')
    def test_footage_exists(self, mock_list_cameras):
        """Test camera with footage on the check date."""
        # Recording started 10 days ago
        recording_start = datetime.now(pytz.UTC) - timedelta(days=10)
        
        mock_list_cameras.return_value = [{
            'id': 'camera1',
            'name': 'Test Camera',
            'recording_start': recording_start,
        }]
        
        tz = pytz.timezone('US/Pacific')
        # Check for footage 5 days ago (should exist)
        check_date = tz.localize(datetime.combine(
            (datetime.now() - timedelta(days=5)).date(),
            time.min
        ))
        
        result = footage_discovery.check_footage_exists(
            camera_id='camera1',
            camera_name='Test Camera',
            check_date=check_date,
            address='https://test.local',
            username='test',
            password='test',
        )
        
        self.assertTrue(result)
    
    @patch('footage_discovery.downloader_adapter.list_cameras')
    def test_footage_does_not_exist(self, mock_list_cameras):
        """Test camera without footage on the check date."""
        # Recording started 5 days ago
        recording_start = datetime.now(pytz.UTC) - timedelta(days=5)
        
        mock_list_cameras.return_value = [{
            'id': 'camera1',
            'name': 'Test Camera',
            'recording_start': recording_start,
        }]
        
        tz = pytz.timezone('US/Pacific')
        # Check for footage 10 days ago (should NOT exist)
        check_date = tz.localize(datetime.combine(
            (datetime.now() - timedelta(days=10)).date(),
            time.min
        ))
        
        result = footage_discovery.check_footage_exists(
            camera_id='camera1',
            camera_name='Test Camera',
            check_date=check_date,
            address='https://test.local',
            username='test',
            password='test',
        )
        
        self.assertFalse(result)


class TestDiscoverFootageRange(unittest.TestCase):
    """Test footage range discovery."""
    
    @patch('footage_discovery.downloader_adapter.list_cameras')
    def test_no_cameras(self, mock_list_cameras):
        """Test discovery with no cameras."""
        mock_list_cameras.return_value = []
        
        result = footage_discovery.discover_footage_range(
            address='https://test.local',
            username='test',
            password='test',
        )
        
        self.assertEqual(len(result['cameras']), 0)
        self.assertIsNone(result['earliest_date'])
        self.assertIsNone(result['latest_date'])
        self.assertEqual(result['days_with_footage'], 0)
    
    @patch('footage_discovery.check_footage_exists')
    @patch('footage_discovery.downloader_adapter.list_cameras')
    def test_footage_discovery(self, mock_list_cameras, mock_check_footage):
        """Test basic footage discovery."""
        # Mock one camera with 3 days of footage
        mock_list_cameras.return_value = [{
            'id': 'camera1',
            'name': 'Test Camera',
            'recording_start': datetime.now(pytz.UTC) - timedelta(days=3),
        }]
        
        # Simulate footage existing for 3 days, then none
        call_count = [0]
        def check_footage_side_effect(*args, **kwargs):
            call_count[0] += 1
            return call_count[0] <= 3
        
        mock_check_footage.side_effect = check_footage_side_effect
        
        result = footage_discovery.discover_footage_range(
            address='https://test.local',
            username='test',
            password='test',
            max_days_back=10,
        )
        
        self.assertEqual(len(result['cameras']), 1)
        self.assertIsNotNone(result['earliest_date'])
        self.assertIsNotNone(result['latest_date'])
        self.assertEqual(result['days_with_footage'], 3)
        self.assertEqual(result['timezone'], 'US/Pacific')


if __name__ == '__main__':
    unittest.main()
