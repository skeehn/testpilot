"""
TestPilot Streaming and Caching System
======================================

Advanced performance features for TestPilot 2.0:
- Real-time token streaming for immediate feedback
- SQLite-based caching for prompt→test mapping
- Parallel processing for large codebases
- Performance monitoring and optimization
"""

import asyncio
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, AsyncGenerator, Callable
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
import os


class TestPilotCache:
    """SQLite-based caching system for test generation results."""
    
    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            cache_dir = os.path.join(tempfile.gettempdir(), "testpilot_cache")
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.db_path = self.cache_dir / "testpilot.db"
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_hash TEXT UNIQUE NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    test_code TEXT NOT NULL,
                    quality_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS context_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_hash TEXT NOT NULL,
                    context_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source_hash ON test_cache(source_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON context_cache(file_path)")
            conn.commit()
    
    def _hash_content(self, content: str) -> str:
        """Generate SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def get_cached_test(self, source_code: str, prompt: str, provider: str, model: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached test generation result."""
        source_hash = self._hash_content(source_code)
        prompt_hash = self._hash_content(prompt)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT test_code, quality_score, created_at
                FROM test_cache 
                WHERE source_hash = ? AND prompt_hash = ? AND provider = ? AND model = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (source_hash, prompt_hash, provider, model))
            
            row = cursor.fetchone()
            if row:
                # Update last accessed time
                conn.execute("""
                    UPDATE test_cache 
                    SET last_accessed = CURRENT_TIMESTAMP 
                    WHERE source_hash = ? AND prompt_hash = ? AND provider = ? AND model = ?
                """, (source_hash, prompt_hash, provider, model))
                conn.commit()
                
                return {
                    'test_code': row['test_code'],
                    'quality_score': row['quality_score'],
                    'created_at': row['created_at']
                }
        
        return None
    
    def cache_test(self, source_code: str, prompt: str, provider: str, model: str, 
                   test_code: str, quality_score: Optional[float] = None):
        """Cache a test generation result."""
        source_hash = self._hash_content(source_code)
        prompt_hash = self._hash_content(prompt)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO test_cache 
                (source_hash, prompt_hash, provider, model, test_code, quality_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (source_hash, prompt_hash, provider, model, test_code, quality_score))
            conn.commit()
    
    def get_cached_context(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached context analysis."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT context_data, file_hash, created_at
                FROM context_cache 
                WHERE file_path = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (file_path,))
            
            row = cursor.fetchone()
            if row:
                # Check if file has changed
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        current_hash = self._hash_content(f.read())
                    
                    if current_hash == row['file_hash']:
                        return {
                            'context': json.loads(row['context_data']),
                            'created_at': row['created_at']
                        }
                except Exception:
                    pass
        
        return None
    
    def cache_context(self, file_path: str, context_data: Dict[str, Any]):
        """Cache context analysis result."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_hash = self._hash_content(f.read())
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO context_cache 
                    (file_path, file_hash, context_data)
                    VALUES (?, ?, ?)
                """, (file_path, file_hash, json.dumps(context_data)))
                conn.commit()
        except Exception:
            pass  # Fail silently for caching errors
    
    def clear_old_entries(self, days: int = 30):
        """Clear cache entries older than specified days."""
        with sqlite3.connect(self.db_path) as conn:
            if days == 0:
                # Clear all entries
                conn.execute("DELETE FROM test_cache")
                conn.execute("DELETE FROM context_cache")
            else:
                conn.execute("""
                    DELETE FROM test_cache 
                    WHERE created_at < datetime('now', '-{} days')
                """.format(days))
                
                conn.execute("""
                    DELETE FROM context_cache 
                    WHERE created_at < datetime('now', '-{} days')
                """.format(days))
            conn.commit()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM test_cache")
            test_count = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) as count FROM context_cache")
            context_count = cursor.fetchone()[0]
            
            cursor = conn.execute("""
                SELECT AVG(quality_score) as avg_quality 
                FROM test_cache 
                WHERE quality_score IS NOT NULL
            """)
            avg_quality = cursor.fetchone()[0] or 0.0
            
            return {
                'test_cache_entries': test_count,
                'context_cache_entries': context_count,
                'average_quality_score': avg_quality
            }


class StreamingGenerator:
    """Real-time streaming for test generation with progress feedback."""
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        self.progress_callback = progress_callback or self._default_progress
        self.start_time = None
        self.tokens_generated = 0
    
    def _default_progress(self, message: str):
        """Default progress callback that prints to console."""
        print(f"🔄 {message}")
    
    async def stream_generation(self, provider, prompt: str, model: str, **kwargs) -> AsyncGenerator[str, None]:
        """Stream test generation with real-time progress updates."""
        self.start_time = time.time()
        self.tokens_generated = 0
        
        self.progress_callback("Starting test generation...")
        
        try:
            # Check if provider supports streaming
            if hasattr(provider, 'stream_text'):
                async for chunk in provider.stream_text(prompt, model, **kwargs):
                    self.tokens_generated += len(chunk.split())
                    elapsed = time.time() - self.start_time
                    rate = self.tokens_generated / elapsed if elapsed > 0 else 0
                    
                    self.progress_callback(
                        f"Generated {self.tokens_generated} tokens ({rate:.1f} tokens/sec)"
                    )
                    yield chunk
            else:
                # Fallback to non-streaming with progress simulation
                self.progress_callback("Generating tests (non-streaming mode)...")
                result = provider.generate_text(prompt, model, **kwargs)
                
                # Simulate streaming by yielding chunks
                chunk_size = 50
                for i in range(0, len(result), chunk_size):
                    chunk = result[i:i + chunk_size]
                    self.tokens_generated += len(chunk.split())
                    yield chunk
                    await asyncio.sleep(0.01)  # Small delay for visual effect
        
        except Exception as e:
            self.progress_callback(f"Error during generation: {e}")
            raise
        
        finally:
            elapsed = time.time() - self.start_time
            self.progress_callback(
                f"Generation complete! {self.tokens_generated} tokens in {elapsed:.1f}s"
            )


class ParallelProcessor:
    """Parallel processing for batch test generation."""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def process_files_parallel(self, files: List[str], generation_func: Callable, 
                             progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Process multiple files in parallel."""
        results = {}
        futures = {}
        
        # Submit all tasks
        for file_path in files:
            future = self.executor.submit(generation_func, file_path)
            futures[future] = file_path
        
        # Collect results as they complete
        completed = 0
        for future in as_completed(futures):
            file_path = futures[future]
            completed += 1
            
            if progress_callback:
                progress_callback(f"Completed {completed}/{len(files)}: {file_path}")
            
            try:
                results[file_path] = future.result()
            except Exception as e:
                results[file_path] = {'error': str(e)}
        
        return results
    
    def __del__(self):
        """Clean up the thread pool."""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)


class PerformanceMonitor:
    """Monitor and optimize TestPilot performance."""
    
    def __init__(self):
        self.metrics = {
            'generation_times': [],
            'validation_times': [],
            'context_analysis_times': [],
            'cache_hits': 0,
            'cache_misses': 0,
            'total_requests': 0
        }
    
    def record_generation_time(self, duration: float):
        """Record test generation time."""
        self.metrics['generation_times'].append(duration)
        self.metrics['total_requests'] += 1
    
    def record_validation_time(self, duration: float):
        """Record validation time."""
        self.metrics['validation_times'].append(duration)
    
    def record_context_time(self, duration: float):
        """Record context analysis time."""
        self.metrics['context_analysis_times'].append(duration)
    
    def record_cache_hit(self):
        """Record cache hit."""
        self.metrics['cache_hits'] += 1
    
    def record_cache_miss(self):
        """Record cache miss."""
        self.metrics['cache_misses'] += 1
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report."""
        report = {
            'total_requests': self.metrics['total_requests'],
            'cache_hit_rate': 0.0,
            'average_generation_time': 0.0,
            'average_validation_time': 0.0,
            'average_context_time': 0.0
        }
        
        total_cache_requests = self.metrics['cache_hits'] + self.metrics['cache_misses']
        if total_cache_requests > 0:
            report['cache_hit_rate'] = self.metrics['cache_hits'] / total_cache_requests
        
        if self.metrics['generation_times']:
            report['average_generation_time'] = sum(self.metrics['generation_times']) / len(self.metrics['generation_times'])
        
        if self.metrics['validation_times']:
            report['average_validation_time'] = sum(self.metrics['validation_times']) / len(self.metrics['validation_times'])
        
        if self.metrics['context_analysis_times']:
            report['average_context_time'] = sum(self.metrics['context_analysis_times']) / len(self.metrics['context_analysis_times'])
        
        return report
    
    def optimize_recommendations(self) -> List[str]:
        """Provide optimization recommendations based on metrics."""
        recommendations = []
        
        cache_hit_rate = 0.0
        total_cache_requests = self.metrics['cache_hits'] + self.metrics['cache_misses']
        if total_cache_requests > 0:
            cache_hit_rate = self.metrics['cache_hits'] / total_cache_requests
        
        if cache_hit_rate < 0.3:
            recommendations.append("Consider using more consistent prompts to improve cache hit rate")
        
        if self.metrics['generation_times'] and sum(self.metrics['generation_times']) / len(self.metrics['generation_times']) > 30:
            recommendations.append("Generation times are high - consider using faster models or local inference")
        
        if self.metrics['validation_times'] and sum(self.metrics['validation_times']) / len(self.metrics['validation_times']) > 10:
            recommendations.append("Validation is slow - consider optimizing test execution environment")
        
        if not recommendations:
            recommendations.append("Performance is optimal!")
        
        return recommendations


# Global instances for easy access
_cache = TestPilotCache()
_monitor = PerformanceMonitor()


def get_cache() -> TestPilotCache:
    """Get the global cache instance."""
    return _cache


def get_monitor() -> PerformanceMonitor:
    """Get the global performance monitor."""
    return _monitor