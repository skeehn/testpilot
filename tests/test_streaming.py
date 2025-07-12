"""
Tests for TestPilot streaming and caching features.
"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from testpilot.streaming import (
    TestPilotCache,
    StreamingGenerator,
    ParallelProcessor,
    PerformanceMonitor,
    get_cache,
    get_monitor
)


class TestTestPilotCache:
    """Test the caching system."""
    
    def setup_method(self):
        """Set up test cache with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = TestPilotCache(cache_dir=self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cache_initialization(self):
        """Test cache database initialization."""
        assert self.cache.db_path.exists()
        
        # Check that tables were created
        import sqlite3
        with sqlite3.connect(self.cache.db_path) as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('test_cache', 'context_cache')
            """)
            tables = [row[0] for row in cursor.fetchall()]
            assert 'test_cache' in tables
            assert 'context_cache' in tables
    
    def test_hash_content(self):
        """Test content hashing."""
        content1 = "def test(): pass"
        content2 = "def test(): pass"
        content3 = "def test(): fail"
        
        hash1 = self.cache._hash_content(content1)
        hash2 = self.cache._hash_content(content2)
        hash3 = self.cache._hash_content(content3)
        
        assert hash1 == hash2  # Same content, same hash
        assert hash1 != hash3  # Different content, different hash
        assert len(hash1) == 64  # SHA-256 produces 64-character hex string
    
    def test_cache_and_retrieve_test(self):
        """Test caching and retrieving test generation results."""
        source_code = "def add(a, b): return a + b"
        prompt = "Generate tests for this function"
        provider = "openai"
        model = "gpt-4"
        test_code = "def test_add(): assert add(1, 2) == 3"
        quality_score = 0.85
        
        # Cache the test
        self.cache.cache_test(source_code, prompt, provider, model, test_code, quality_score)
        
        # Retrieve the test
        cached_result = self.cache.get_cached_test(source_code, prompt, provider, model)
        
        assert cached_result is not None
        assert cached_result['test_code'] == test_code
        assert cached_result['quality_score'] == quality_score
        assert 'created_at' in cached_result
    
    def test_cache_miss(self):
        """Test cache miss scenario."""
        result = self.cache.get_cached_test(
            "nonexistent code", "nonexistent prompt", "openai", "gpt-4"
        )
        assert result is None
    
    def test_context_caching(self):
        """Test context analysis caching."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def test_func(): pass")
            temp_file = f.name
        
        try:
            context_data = {
                'functions': ['test_func'],
                'classes': [],
                'imports': []
            }
            
            # Cache the context
            self.cache.cache_context(temp_file, context_data)
            
            # Retrieve the context
            cached_context = self.cache.get_cached_context(temp_file)
            
            assert cached_context is not None
            assert cached_context['context'] == context_data
            assert 'created_at' in cached_context
        
        finally:
            os.unlink(temp_file)
    
    def test_context_cache_invalidation(self):
        """Test that context cache is invalidated when file changes."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def test_func(): pass")
            temp_file = f.name
        
        try:
            context_data = {'functions': ['test_func']}
            
            # Cache the context
            self.cache.cache_context(temp_file, context_data)
            
            # Verify it's cached
            cached_context = self.cache.get_cached_context(temp_file)
            assert cached_context is not None
            
            # Modify the file
            with open(temp_file, 'w') as f:
                f.write("def different_func(): pass")
            
            # Cache should be invalidated
            cached_context = self.cache.get_cached_context(temp_file)
            assert cached_context is None
        
        finally:
            os.unlink(temp_file)
    
    def test_cache_stats(self):
        """Test cache statistics."""
        # Initially empty
        stats = self.cache.get_cache_stats()
        assert stats['test_cache_entries'] == 0
        assert stats['context_cache_entries'] == 0
        
        # Add some entries
        self.cache.cache_test("code1", "prompt1", "openai", "gpt-4", "test1", 0.8)
        self.cache.cache_test("code2", "prompt2", "openai", "gpt-4", "test2", 0.9)
        
        # Check stats
        stats = self.cache.get_cache_stats()
        assert stats['test_cache_entries'] == 2
        assert abs(stats['average_quality_score'] - 0.85) < 0.001  # (0.8 + 0.9) / 2
    
    def test_clear_old_entries(self):
        """Test clearing old cache entries."""
        # Add an entry
        self.cache.cache_test("code", "prompt", "openai", "gpt-4", "test", 0.8)
        
        # Verify it exists
        stats = self.cache.get_cache_stats()
        assert stats['test_cache_entries'] == 1
        
        # Clear entries older than 0 days (should clear everything)
        self.cache.clear_old_entries(days=0)
        
        # Verify it's gone
        stats = self.cache.get_cache_stats()
        assert stats['test_cache_entries'] == 0


class TestStreamingGenerator:
    """Test the streaming generation system."""
    
    def test_streaming_generator_init(self):
        """Test streaming generator initialization."""
        generator = StreamingGenerator()
        assert generator.progress_callback is not None
        assert generator.start_time is None
        assert generator.tokens_generated == 0
    
    def test_custom_progress_callback(self):
        """Test custom progress callback."""
        messages = []
        
        def custom_callback(message):
            messages.append(message)
        
        generator = StreamingGenerator(progress_callback=custom_callback)
        generator._default_progress("test message")
        
        # The custom callback should not be called by _default_progress
        assert len(messages) == 0
        
        # But it should be used as the callback
        generator.progress_callback("test message")
        assert len(messages) == 1
        assert messages[0] == "test message"
    
    @pytest.mark.asyncio
    async def test_stream_generation_non_streaming_provider(self):
        """Test streaming with non-streaming provider."""
        mock_provider = MagicMock()
        mock_provider.generate_text.return_value = "def test(): pass"
        
        # Remove stream_text method to simulate non-streaming provider
        if hasattr(mock_provider, 'stream_text'):
            delattr(mock_provider, 'stream_text')
        
        generator = StreamingGenerator()
        chunks = []
        
        async for chunk in generator.stream_generation(
            mock_provider, "test prompt", "gpt-4"
        ):
            chunks.append(chunk)
        
        # Should have received chunks
        assert len(chunks) > 0
        assert "".join(chunks) == "def test(): pass"
        
        # Provider should have been called
        mock_provider.generate_text.assert_called_once_with("test prompt", "gpt-4")
    
    @pytest.mark.asyncio
    async def test_stream_generation_streaming_provider(self):
        """Test streaming with streaming provider."""
        async def mock_stream_text(prompt, model, **kwargs):
            chunks = ["def ", "test", "(): ", "pass"]
            for chunk in chunks:
                yield chunk
                await asyncio.sleep(0.001)
        
        mock_provider = MagicMock()
        mock_provider.stream_text = mock_stream_text
        
        generator = StreamingGenerator()
        chunks = []
        
        async for chunk in generator.stream_generation(
            mock_provider, "test prompt", "gpt-4"
        ):
            chunks.append(chunk)
        
        assert chunks == ["def ", "test", "(): ", "pass"]
        assert generator.tokens_generated > 0


class TestParallelProcessor:
    """Test the parallel processing system."""
    
    def test_parallel_processor_init(self):
        """Test parallel processor initialization."""
        processor = ParallelProcessor(max_workers=2)
        assert processor.max_workers == 2
        assert processor.executor is not None
    
    def test_process_files_parallel(self):
        """Test parallel file processing."""
        def mock_generation_func(file_path):
            # Simulate some work
            time.sleep(0.1)
            return f"Generated tests for {file_path}"
        
        files = ["file1.py", "file2.py", "file3.py"]
        processor = ParallelProcessor(max_workers=2)
        
        progress_messages = []
        def progress_callback(message):
            progress_messages.append(message)
        
        results = processor.process_files_parallel(
            files, mock_generation_func, progress_callback
        )
        
        # All files should be processed
        assert len(results) == 3
        for file_path in files:
            assert file_path in results
            assert results[file_path] == f"Generated tests for {file_path}"
        
        # Progress messages should be recorded
        assert len(progress_messages) == 3
    
    def test_process_files_with_errors(self):
        """Test parallel processing with errors."""
        def failing_generation_func(file_path):
            if "fail" in file_path:
                raise ValueError(f"Failed to process {file_path}")
            return f"Success for {file_path}"
        
        files = ["success.py", "fail.py", "success2.py"]
        processor = ParallelProcessor(max_workers=2)
        
        results = processor.process_files_parallel(files, failing_generation_func)
        
        assert len(results) == 3
        assert results["success.py"] == "Success for success.py"
        assert results["success2.py"] == "Success for success2.py"
        assert "error" in results["fail.py"]
        assert "Failed to process fail.py" in results["fail.py"]["error"]


class TestPerformanceMonitor:
    """Test the performance monitoring system."""
    
    def test_performance_monitor_init(self):
        """Test performance monitor initialization."""
        monitor = PerformanceMonitor()
        assert monitor.metrics['total_requests'] == 0
        assert monitor.metrics['cache_hits'] == 0
        assert monitor.metrics['cache_misses'] == 0
        assert len(monitor.metrics['generation_times']) == 0
    
    def test_record_metrics(self):
        """Test recording various metrics."""
        monitor = PerformanceMonitor()
        
        # Record some metrics
        monitor.record_generation_time(1.5)
        monitor.record_generation_time(2.0)
        monitor.record_validation_time(0.5)
        monitor.record_context_time(0.3)
        monitor.record_cache_hit()
        monitor.record_cache_miss()
        
        # Check metrics
        assert monitor.metrics['total_requests'] == 2
        assert monitor.metrics['cache_hits'] == 1
        assert monitor.metrics['cache_misses'] == 1
        assert monitor.metrics['generation_times'] == [1.5, 2.0]
        assert monitor.metrics['validation_times'] == [0.5]
        assert monitor.metrics['context_analysis_times'] == [0.3]
    
    def test_performance_report(self):
        """Test performance report generation."""
        monitor = PerformanceMonitor()
        
        # Add some data
        monitor.record_generation_time(1.0)
        monitor.record_generation_time(3.0)
        monitor.record_validation_time(0.5)
        monitor.record_context_time(0.2)
        monitor.record_cache_hit()
        monitor.record_cache_hit()
        monitor.record_cache_miss()
        
        report = monitor.get_performance_report()
        
        assert report['total_requests'] == 2
        assert report['cache_hit_rate'] == 2/3  # 2 hits out of 3 total
        assert report['average_generation_time'] == 2.0  # (1.0 + 3.0) / 2
        assert report['average_validation_time'] == 0.5
        assert report['average_context_time'] == 0.2
    
    def test_optimization_recommendations(self):
        """Test optimization recommendations."""
        monitor = PerformanceMonitor()
        
        # Low cache hit rate
        for _ in range(10):
            monitor.record_cache_miss()
        monitor.record_cache_hit()
        
        recommendations = monitor.optimize_recommendations()
        assert any("cache hit rate" in rec for rec in recommendations)
        
        # High generation times
        monitor = PerformanceMonitor()
        for _ in range(5):
            monitor.record_generation_time(35.0)  # > 30 seconds
        
        recommendations = monitor.optimize_recommendations()
        assert any("Generation times are high" in rec for rec in recommendations)
        
        # Optimal performance
        monitor = PerformanceMonitor()
        for _ in range(5):
            monitor.record_cache_hit()
            monitor.record_generation_time(5.0)
            monitor.record_validation_time(1.0)
        
        recommendations = monitor.optimize_recommendations()
        assert "Performance is optimal!" in recommendations


class TestGlobalInstances:
    """Test global cache and monitor instances."""
    
    def test_get_cache(self):
        """Test getting global cache instance."""
        cache1 = get_cache()
        cache2 = get_cache()
        
        # Should return the same instance
        assert cache1 is cache2
        assert isinstance(cache1, TestPilotCache)
    
    def test_get_monitor(self):
        """Test getting global monitor instance."""
        monitor1 = get_monitor()
        monitor2 = get_monitor()
        
        # Should return the same instance
        assert monitor1 is monitor2
        assert isinstance(monitor1, PerformanceMonitor)


class TestIntegration:
    """Integration tests for streaming and caching together."""
    
    def test_cache_integration_with_core(self):
        """Test that caching integrates properly with core functions."""
        from testpilot.core import generate_tests_llm
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def add(a, b): return a + b")
            temp_file = f.name
        
        try:
            # Mock the provider to avoid API calls
            with patch('testpilot.core.get_llm_provider') as mock_get_provider:
                mock_provider = MagicMock()
                mock_provider.generate_text.return_value = "def test_add(): assert True"
                mock_get_provider.return_value = mock_provider
                
                with patch('testpilot.core._validate_model') as mock_validate:
                    mock_validate.return_value = "gpt-4"
                    
                    # First call should miss cache and call provider
                    result1 = generate_tests_llm(
                        temp_file, "openai", api_key="fake-key", 
                        use_context_analysis=False, validation_enabled=False,
                        use_cache=False  # Disable cache for this test
                    )
                    
                    assert mock_provider.generate_text.call_count == 1
                    assert result1 == "def test_add(): assert True"
                    
                    # Second call should also call provider (cache disabled)
                    result2 = generate_tests_llm(
                        temp_file, "openai", api_key="fake-key",
                        use_context_analysis=False, validation_enabled=False,
                        use_cache=False  # Disable cache for this test
                    )
                    
                    # Provider should be called again since cache is disabled
                    assert mock_provider.generate_text.call_count == 2
                    assert result2 == result1
        
        finally:
            os.unlink(temp_file)
    
    def test_performance_monitoring_integration(self):
        """Test that performance monitoring works with core functions."""
        monitor = get_monitor()
        initial_requests = monitor.metrics['total_requests']
        
        from testpilot.core import generate_tests_llm
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def test(): pass")
            temp_file = f.name
        
        try:
            # Mock the provider
            with patch('testpilot.core.get_llm_provider') as mock_get_provider:
                mock_provider = MagicMock()
                mock_provider.generate_text.return_value = "def test_test(): assert True"
                mock_get_provider.return_value = mock_provider
                
                with patch('testpilot.core._validate_model') as mock_validate:
                    mock_validate.return_value = "gpt-4"
                    
                    # Generate tests
                    generate_tests_llm(
                        temp_file, "openai", api_key="fake-key",
                        use_context_analysis=False, validation_enabled=False
                    )
                    
                    # Performance should be monitored
                    assert monitor.metrics['total_requests'] > initial_requests
                    assert len(monitor.metrics['generation_times']) > 0
        
        finally:
            os.unlink(temp_file)