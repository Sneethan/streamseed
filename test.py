"""StreamSeed Test Suite"""

import unittest
import os
import boto3
import logging
import datetime
import json
from unittest.mock import patch, MagicMock, mock_open
from main import (
    verify_recording,
    upload_to_s3,
    cleanup_local_file,
    record_stream,
    send_discord_notification,
    upload_latest,
    MIN_FILE_SIZE,
    retry_decorator,
    log_info,
    log_error,
    log_success
)

class TestStreamSeed(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.test_dir = "test_recordings"
        self.test_file = os.path.join(self.test_dir, "test_recording.mp3")
        
        # Create test directory and file
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)
        
        # Create a dummy file with known size
        with open(self.test_file, 'wb') as f:
            f.write(b'0' * (MIN_FILE_SIZE + 1000))
            
    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)

    @patch('main.log_error')
    def test_verify_recording(self, mock_log_error):
        """Test recording verification"""
        # Test valid file
        self.assertTrue(verify_recording(self.test_file))
        mock_log_error.assert_not_called()
        
        # Test non-existent file
        self.assertFalse(verify_recording("nonexistent.mp3"))
        mock_log_error.assert_called_with("Recording file not found: nonexistent.mp3")
        
        # Test undersized file
        small_file = os.path.join(self.test_dir, "small.mp3")
        with open(small_file, 'wb') as f:
            f.write(b'0' * 100)
        
        self.assertFalse(verify_recording(small_file))
        mock_log_error.assert_called_with(f"Recording file too small (100 bytes): {small_file}")
        
        os.remove(small_file)

    @patch('boto3.session.Session.client')
    @patch('main.log_info')
    @patch('main.log_error')
    def test_upload_to_s3(self, mock_log_error, mock_log_info, mock_s3_client):
        """Test S3 upload functionality"""
        mock_client = MagicMock()
        mock_s3_client.return_value = mock_client

        # Test successful upload
        mock_client.put_object.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}
        
        # Mock the retry decorator to only try once
        with patch('main.retry_decorator', lambda *args, **kwargs: lambda func: func):
            # Test successful upload
            self.assertTrue(upload_to_s3(self.test_file, "test.mp3"))
            mock_log_info.assert_called_with(f"Uploaded {self.test_file} to Vultr Object Storage as test.mp3")
            
            # Reset mocks for next test
            mock_client.put_object.reset_mock()
            mock_log_error.reset_mock()
            mock_log_info.reset_mock()
            
            # Test failed upload
            mock_client.put_object.side_effect = Exception("Upload failed")
            self.assertFalse(upload_to_s3(self.test_file, "test.mp3"))
            mock_log_error.assert_called_with(f"Error uploading {self.test_file}: Upload failed")

    @patch('main.log_info')
    @patch('main.log_error')
    def test_cleanup_local_file(self, mock_log_error, mock_log_info):
        """Test local file cleanup"""
        temp_file = os.path.join(self.test_dir, "temp.mp3")
        with open(temp_file, 'w') as f:
            f.write("test")
            
        self.assertTrue(os.path.exists(temp_file))
        cleanup_local_file(temp_file)
        self.assertFalse(os.path.exists(temp_file))
        mock_log_info.assert_called_with(f"Cleaned up local file: {temp_file}")

        # Test cleanup of non-existent file
        nonexistent_file = "nonexistent.mp3"
        cleanup_local_file(nonexistent_file)
        # Check that the error message contains the key parts without being system-specific
        error_call = mock_log_error.call_args[0][0]
        self.assertIn("Error cleaning up nonexistent.mp3", error_call)
        self.assertIn("No such file", error_call.lower())
        self.assertIn("nonexistent.mp3", error_call)

    @patch('requests.post')
    def test_discord_notification_levels(self, mock_post):
        """Test Discord notification levels"""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        # Test with NOTIFICATION_LEVEL = 'all' and webhook URL set
        with patch('main.NOTIFICATION_LEVEL', 'all'), \
             patch('main.DISCORD_WEBHOOK_URL', 'https://fake-webhook.url'):
            self.assertTrue(send_discord_notification("Test info", "info"))
            self.assertTrue(send_discord_notification("Test error", "error"))

        # Test with NOTIFICATION_LEVEL = 'error'
        with patch('main.NOTIFICATION_LEVEL', 'error'), \
             patch('main.DISCORD_WEBHOOK_URL', 'https://fake-webhook.url'):
            self.assertFalse(send_discord_notification("Test info", "info"))
            self.assertTrue(send_discord_notification("Test error", "error"))

        # Test with NOTIFICATION_LEVEL = 'none'
        with patch('main.NOTIFICATION_LEVEL', 'none'), \
             patch('main.DISCORD_WEBHOOK_URL', 'https://fake-webhook.url'):
            self.assertFalse(send_discord_notification("Test info", "info"))
            self.assertFalse(send_discord_notification("Test error", "error"))

    @patch('subprocess.run')
    @patch('main.log_info')
    @patch('main.log_error')
    def test_record_stream(self, mock_log_error, mock_log_info, mock_run):
        """Test stream recording"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        expected_output = os.path.join("recordings", f"show_{timestamp}.mp3")

        # Test successful recording
        mock_run.return_value = MagicMock(returncode=0)
        result = record_stream()
        self.assertEqual(result, expected_output)
        mock_log_info.assert_any_call(f"Recording started: {expected_output}")
        mock_log_info.assert_any_call(f"Recording finished: {expected_output}")

        # Test failed recording
        mock_run.return_value = MagicMock(returncode=1, stderr="FFmpeg error")
        result = record_stream()
        self.assertIsNone(result)
        mock_log_error.assert_called_with("Recording failed: FFmpeg error")

    @patch('main.upload_to_s3')
    def test_upload_latest(self, mock_upload):
        """Test upload_latest functionality"""
        mock_upload.return_value = True
        upload_latest(self.test_file)
        mock_upload.assert_called_once_with(self.test_file, "latest.mp3")

    def test_retry_decorator(self):
        """Test retry decorator functionality"""
        mock_func = MagicMock()
        mock_func.side_effect = [Exception("Error"), Exception("Error"), True]
        
        @retry_decorator(max_retries=3, delay=0)
        def test_func():
            return mock_func()

        result = test_func()
        self.assertTrue(result)
        self.assertEqual(mock_func.call_count, 3)

if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
    unittest.main()
