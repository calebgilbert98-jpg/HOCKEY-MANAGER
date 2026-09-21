"""
Memory optimization system for Hockey Manager
Implements memory pools, object recycling, and memory monitoring for large datasets
"""

import gc
import time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from collections import deque
import threading
import weakref

# Note: For full memory monitoring, install psutil: pip install psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Note: Install psutil for advanced memory monitoring: pip install psutil")


@dataclass
class MemoryStats:
    """Memory usage statistics"""
    total_memory_mb: float
    used_memory_mb: float
    available_memory_mb: float
    python_memory_mb: float
    memory_percent: float
    timestamp: float = field(default_factory=time.time)


class ObjectPool:
    """Generic object pool for memory optimization"""
    
    def __init__(self, object_type, max_size: int = 1000):
        self.object_type = object_type
        self.max_size = max_size
        self.available_objects = deque()
        self.in_use_objects: Set[weakref.ref] = set()
        self.total_created = 0
        self.total_reused = 0
        self.lock = threading.Lock()
    
    def get_object(self, *args, **kwargs):
        """Get an object from the pool or create a new one"""
        with self.lock:
            if self.available_objects:
                obj = self.available_objects.popleft()
                # Reset object state if it has a reset method
                if hasattr(obj, 'reset'):
                    obj.reset(*args, **kwargs)
                elif hasattr(obj, '__init__'):
                    obj.__init__(*args, **kwargs)
                
                self.total_reused += 1
                ref = weakref.ref(obj, self._object_finalized)
                self.in_use_objects.add(ref)
                return obj
            else:
                # Create new object
                obj = self.object_type(*args, **kwargs)
                self.total_created += 1
                ref = weakref.ref(obj, self._object_finalized)
                self.in_use_objects.add(ref)
                return obj
    
    def return_object(self, obj):
        """Return an object to the pool"""
        with self.lock:
            if len(self.available_objects) < self.max_size:
                # Clear object data if it has a clear method
                if hasattr(obj, 'clear_data'):
                    obj.clear_data()
                
                self.available_objects.append(obj)
    
    def _object_finalized(self, ref):
        """Called when a pooled object is garbage collected"""
        with self.lock:
            self.in_use_objects.discard(ref)
    
    def get_stats(self) -> Dict:
        """Get pool statistics"""
        with self.lock:
            return {
                'available': len(self.available_objects),
                'in_use': len(self.in_use_objects),
                'total_created': self.total_created,
                'total_reused': self.total_reused,
                'reuse_rate': f"{(self.total_reused / max(1, self.total_created + self.total_reused)) * 100:.1f}%"
            }


class MemoryMonitor:
    """Monitor system and application memory usage"""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.memory_history: List[MemoryStats] = []
        self.max_history = 100
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.last_error_time = 0  # Track last error to prevent spam
        self.error_cooldown = 60  # Only show errors every 60 seconds
        self.thresholds = {
            'warning': 80.0,  # Warning at 80% memory usage
            'critical': 90.0  # Critical at 90% memory usage
        }
        self.callbacks = {
            'warning': [],
            'critical': []
        }
    
    def start_monitoring(self):
        """Start memory monitoring in background thread"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("Memory monitoring started")
    
    def stop_monitoring(self):
        """Stop memory monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        print("Memory monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                stats = self.get_current_stats()
                self._check_thresholds(stats)
                self._add_to_history(stats)
                time.sleep(self.check_interval)
            except Exception as e:
                print(f"Memory monitoring error: {e}")
                time.sleep(self.check_interval)
    
    def get_current_stats(self) -> MemoryStats:
        """Get current memory statistics"""
        try:
            if PSUTIL_AVAILABLE:
                # System memory
                virtual_memory = psutil.virtual_memory()
                
                # Python process memory
                process = psutil.Process()
                process_memory = process.memory_info()
                
                return MemoryStats(
                    total_memory_mb=virtual_memory.total / (1024 * 1024),
                    used_memory_mb=virtual_memory.used / (1024 * 1024),
                    available_memory_mb=virtual_memory.available / (1024 * 1024),
                    python_memory_mb=process_memory.rss / (1024 * 1024),
                    memory_percent=virtual_memory.percent
                )
            else:
                # Fallback memory stats (basic estimation for Windows)
                import os
                
                # Try to get memory usage from resource module (Unix-like systems only)
                python_memory_mb = 0
                try:
                    import resource
                    python_memory_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    # On Linux, ru_maxrss is in KB, on macOS it's in bytes
                    if os.name == 'posix':
                        python_memory_mb = python_memory_kb / 1024
                    else:
                        python_memory_mb = python_memory_kb / (1024 * 1024)
                except ImportError:
                    # Windows doesn't have resource module, use basic estimation
                    python_memory_mb = 100  # Basic estimate
                except Exception:
                    python_memory_mb = 0
                
                # Estimate system memory (basic fallback)
                total_memory_mb = 8192  # Assume 8GB default
                used_memory_mb = max(python_memory_mb * 10, 1024)  # Rough estimate
                available_memory_mb = total_memory_mb - used_memory_mb
                memory_percent = (used_memory_mb / total_memory_mb) * 100
                
                return MemoryStats(
                    total_memory_mb=total_memory_mb,
                    used_memory_mb=used_memory_mb,
                    available_memory_mb=available_memory_mb,
                    python_memory_mb=python_memory_mb,
                    memory_percent=memory_percent
                )
        except Exception as e:
            # Only print error messages every 60 seconds to avoid spam
            current_time = time.time()
            if current_time - self.last_error_time > self.error_cooldown:
                print(f"Memory stats warning: {e} (Windows compatibility mode)")
                self.last_error_time = current_time
            return MemoryStats(0, 0, 0, 0, 0)
    
    def _check_thresholds(self, stats: MemoryStats):
        """Check if memory usage exceeds thresholds"""
        if stats.memory_percent >= self.thresholds['critical']:
            self._trigger_callbacks('critical', stats)
        elif stats.memory_percent >= self.thresholds['warning']:
            self._trigger_callbacks('warning', stats)
    
    def _trigger_callbacks(self, level: str, stats: MemoryStats):
        """Trigger callbacks for memory threshold events"""
        for callback in self.callbacks.get(level, []):
            try:
                callback(stats)
            except Exception as e:
                print(f"Error in memory callback: {e}")
    
    def _add_to_history(self, stats: MemoryStats):
        """Add stats to history with size limit"""
        self.memory_history.append(stats)
        if len(self.memory_history) > self.max_history:
            self.memory_history.pop(0)
    
    def add_callback(self, level: str, callback):
        """Add callback for memory threshold events"""
        if level in self.callbacks:
            self.callbacks[level].append(callback)
    
    def get_memory_report(self) -> str:
        """Get detailed memory usage report"""
        current = self.get_current_stats()
        
        report = [
            "Memory Usage Report:",
            "=" * 30,
            f"System Memory: {current.used_memory_mb:.1f} MB / {current.total_memory_mb:.1f} MB ({current.memory_percent:.1f}%)",
            f"Available: {current.available_memory_mb:.1f} MB",
            f"Python Process: {current.python_memory_mb:.1f} MB",
            ""
        ]
        
        if len(self.memory_history) > 1:
            # Calculate trends
            recent = self.memory_history[-10:]  # Last 10 measurements
            if len(recent) >= 2:
                trend = recent[-1].memory_percent - recent[0].memory_percent
                trend_str = "increasing" if trend > 1 else "decreasing" if trend < -1 else "stable"
                report.append(f"Memory Trend: {trend_str} ({trend:+.1f}%)")
        
        return "\n".join(report)


class MemoryOptimizer:
    """Main memory optimization coordinator"""
    
    def __init__(self):
        self.monitor = MemoryMonitor()
        self.object_pools: Dict[str, ObjectPool] = {}
        self.optimization_strategies = []
        self.auto_optimize = True
        self.last_optimization = 0
        self.optimization_interval = 60  # 1 minute
        
        # Set up automatic optimization callbacks
        self.monitor.add_callback('warning', self._on_memory_warning)
        self.monitor.add_callback('critical', self._on_memory_critical)
    
    def initialize(self):
        """Initialize memory optimization"""
        print("Initializing memory optimization...")
        
        # Start memory monitoring
        self.monitor.start_monitoring()
        
        # Create object pools for common objects
        self._setup_object_pools()
        
        # Register optimization strategies
        self._setup_optimization_strategies()
        
        print("Memory optimization initialized")
    
    def _setup_object_pools(self):
        """Set up object pools for commonly used objects"""
        # These would be actual game objects in a real implementation
        self.object_pools['game_events'] = ObjectPool(dict, max_size=500)
        self.object_pools['player_stats'] = ObjectPool(dict, max_size=1000)
        self.object_pools['temp_calculations'] = ObjectPool(list, max_size=200)
    
    def _setup_optimization_strategies(self):
        """Set up memory optimization strategies"""
        self.optimization_strategies = [
            self._garbage_collection_strategy,
            self._cache_cleanup_strategy,
            self._object_pool_cleanup_strategy
        ]
    
    def _on_memory_warning(self, stats: MemoryStats):
        """Handle memory warning threshold"""
        print(f"Memory warning: {stats.memory_percent:.1f}% usage")
        if self.auto_optimize:
            self.optimize_memory(aggressive=False)
    
    def _on_memory_critical(self, stats: MemoryStats):
        """Handle memory critical threshold"""
        print(f"Memory critical: {stats.memory_percent:.1f}% usage")
        if self.auto_optimize:
            self.optimize_memory(aggressive=True)
    
    def optimize_memory(self, aggressive: bool = False):
        """Run memory optimization strategies"""
        current_time = time.time()
        
        # Avoid too frequent optimizations
        if current_time - self.last_optimization < self.optimization_interval and not aggressive:
            return
        
        print(f"Running {'aggressive' if aggressive else 'normal'} memory optimization...")
        start_stats = self.monitor.get_current_stats()
        
        # Run optimization strategies
        for strategy in self.optimization_strategies:
            try:
                strategy(aggressive)
            except Exception as e:
                print(f"Optimization strategy failed: {e}")
        
        # Update timing
        self.last_optimization = current_time
        
        # Report results
        end_stats = self.monitor.get_current_stats()
        memory_freed = start_stats.python_memory_mb - end_stats.python_memory_mb
        if memory_freed > 0:
            print(f"Memory optimization freed {memory_freed:.1f} MB")
    
    def _garbage_collection_strategy(self, aggressive: bool):
        """Garbage collection optimization strategy"""
        if aggressive:
            # Full garbage collection
            collected = gc.collect()
            print(f"Aggressive GC collected {collected} objects")
        else:
            # Quick generation 0 collection
            collected = gc.collect(0)
            if collected > 100:  # Only report if significant
                print(f"Quick GC collected {collected} objects")
    
    def _cache_cleanup_strategy(self, aggressive: bool):
        """Cache cleanup optimization strategy"""
        try:
            # Clean up lazy loading caches
            from lazy_loading import get_lazy_manager
            lazy_manager = get_lazy_manager()
            if lazy_manager:
                if aggressive:
                    lazy_manager.clear_all_caches()
                    print("Cleared all lazy loading caches")
                else:
                    lazy_manager.optimize_memory_usage()
            
            # Clean up performance caches
            from performance_optimizations import get_global_cache
            perf_cache = get_global_cache()
            if perf_cache:
                if aggressive:
                    perf_cache.clear_cache()
                    print("Cleared performance cache")
                elif perf_cache.should_refresh_cache():
                    # Only clear if cache is old
                    perf_cache.clear_cache()
                    print("Refreshed performance cache")
        except Exception as e:
            print(f"Cache cleanup error: {e}")
    
    def _object_pool_cleanup_strategy(self, aggressive: bool):
        """Object pool cleanup optimization strategy"""
        for name, pool in self.object_pools.items():
            initial_size = len(pool.available_objects)
            
            if aggressive:
                # Clear most of the pool
                while len(pool.available_objects) > pool.max_size // 4:
                    pool.available_objects.popleft()
            else:
                # Clean up excess objects
                while len(pool.available_objects) > pool.max_size:
                    pool.available_objects.popleft()
            
            final_size = len(pool.available_objects)
            if initial_size > final_size:
                print(f"Pool {name}: reduced from {initial_size} to {final_size} objects")
    
    def get_pool_stats(self) -> Dict:
        """Get statistics for all object pools"""
        return {name: pool.get_stats() for name, pool in self.object_pools.items()}
    
    def get_optimization_report(self) -> str:
        """Get comprehensive optimization report"""
        report = [
            "Memory Optimization Report:",
            "=" * 35,
            "",
            self.monitor.get_memory_report(),
            "",
            "Object Pool Statistics:",
            "-" * 25
        ]
        
        pool_stats = self.get_pool_stats()
        for name, stats in pool_stats.items():
            report.append(f"{name}: {stats['reuse_rate']} reuse rate, {stats['available']} available")
        
        return "\n".join(report)
    
    def shutdown(self):
        """Shutdown memory optimization"""
        print("Shutting down memory optimization...")
        self.monitor.stop_monitoring()
        
        # Clear all pools
        for pool in self.object_pools.values():
            pool.available_objects.clear()
        
        print("Memory optimization shutdown complete")


# Global memory optimizer instance
_global_memory_optimizer: Optional[MemoryOptimizer] = None

def get_memory_optimizer() -> Optional[MemoryOptimizer]:
    """Get the global memory optimizer instance"""
    return _global_memory_optimizer

def initialize_memory_optimizer() -> MemoryOptimizer:
    """Initialize the global memory optimizer"""
    global _global_memory_optimizer
    _global_memory_optimizer = MemoryOptimizer()
    _global_memory_optimizer.initialize()
    return _global_memory_optimizer
