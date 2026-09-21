# Phase 3: UI/UX Optimizations
# Implements advanced UI performance improvements and user experience enhancements

import tkinter as tk
from tkinter import ttk
import threading
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import deque
import weakref

@dataclass
class UIPerformanceMetrics:
    """Track UI performance metrics"""
    render_times: deque = field(default_factory=lambda: deque(maxlen=100))
    update_times: deque = field(default_factory=lambda: deque(maxlen=100))
    scroll_performance: deque = field(default_factory=lambda: deque(maxlen=50))
    button_response_times: deque = field(default_factory=lambda: deque(maxlen=50))
    
    def add_render_time(self, duration: float):
        self.render_times.append(duration)
    
    def add_update_time(self, duration: float):
        self.update_times.append(duration)
    
    def add_scroll_time(self, duration: float):
        self.scroll_performance.append(duration)
    
    def add_button_response(self, duration: float):
        self.button_response_times.append(duration)
    
    def get_average_render_time(self) -> float:
        return sum(self.render_times) / len(self.render_times) if self.render_times else 0.0
    
    def get_average_update_time(self) -> float:
        return sum(self.update_times) / len(self.update_times) if self.update_times else 0.0


class VirtualizedTreeview:
    """Virtualized treeview for handling large datasets efficiently"""
    
    def __init__(self, parent, tree_widget: ttk.Treeview, viewport_size: int = 50):
        self.tree = tree_widget
        self.parent = parent
        self.viewport_size = viewport_size
        self.data_source: List[Dict] = []
        self.filtered_data: List[Dict] = []
        self.current_filter = ""
        self.sort_column = None
        self.sort_reverse = False
        
        # Virtual scrolling setup
        self.visible_start = 0
        self.visible_end = viewport_size
        
        # Bind scroll events
        self.tree.bind('<MouseWheel>', self._on_mousewheel)
        self.tree.bind('<Key-Up>', self._on_key_up)
        self.tree.bind('<Key-Down>', self._on_key_down)
        
    def set_data_source(self, data: List[Dict]):
        """Set the complete dataset"""
        self.data_source = data
        self.filtered_data = data.copy()
        self._refresh_viewport()
    
    def apply_filter(self, filter_text: str):
        """Apply text filter to data"""
        start_time = time.time()
        
        if not filter_text:
            self.filtered_data = self.data_source.copy()
        else:
            filter_lower = filter_text.lower()
            self.filtered_data = [
                item for item in self.data_source 
                if any(filter_lower in str(value).lower() for value in item.values())
            ]
        
        self.visible_start = 0
        self.visible_end = min(self.viewport_size, len(self.filtered_data))
        self._refresh_viewport()
        
        # Track performance
        duration = time.time() - start_time
        if hasattr(self.parent, 'ui_metrics'):
            self.parent.ui_metrics.add_update_time(duration)
    
    def sort_by_column(self, column: str, reverse: bool = False):
        """Sort data by specified column"""
        start_time = time.time()
        
        self.sort_column = column
        self.sort_reverse = reverse
        
        try:
            # Try numeric sort first
            self.filtered_data.sort(
                key=lambda x: float(x.get(column, 0)), 
                reverse=reverse
            )
        except (ValueError, TypeError):
            # Fall back to string sort
            self.filtered_data.sort(
                key=lambda x: str(x.get(column, "")),
                reverse=reverse
            )
        
        self._refresh_viewport()
        
        # Track performance
        duration = time.time() - start_time
        if hasattr(self.parent, 'ui_metrics'):
            self.parent.ui_metrics.add_update_time(duration)
    
    def _refresh_viewport(self):
        """Refresh the visible portion of the treeview"""
        start_time = time.time()
        
        # Clear current items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add visible items
        visible_data = self.filtered_data[self.visible_start:self.visible_end]
        for item_data in visible_data:
            values = [item_data.get(col, "") for col in self.tree["columns"]]
            self.tree.insert("", "end", values=values)
        
        # Update scrollbar to reflect total data size
        if len(self.filtered_data) > self.viewport_size:
            self._update_scrollbar()
        
        # Track performance
        duration = time.time() - start_time
        if hasattr(self.parent, 'ui_metrics'):
            self.parent.ui_metrics.add_render_time(duration)
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        start_time = time.time()
        
        delta = -1 * (event.delta / 120)  # Standard wheel delta
        self._scroll_viewport(int(delta * 3))  # Scroll 3 items per wheel step
        
        duration = time.time() - start_time
        if hasattr(self.parent, 'ui_metrics'):
            self.parent.ui_metrics.add_scroll_time(duration)
    
    def _on_key_up(self, event):
        """Handle up arrow key"""
        self._scroll_viewport(-1)
    
    def _on_key_down(self, event):
        """Handle down arrow key"""
        self._scroll_viewport(1)
    
    def _scroll_viewport(self, delta: int):
        """Scroll the viewport by delta items"""
        new_start = max(0, self.visible_start + delta)
        new_end = min(len(self.filtered_data), new_start + self.viewport_size)
        
        if new_start != self.visible_start:
            self.visible_start = new_start
            self.visible_end = new_end
            self._refresh_viewport()
    
    def _update_scrollbar(self):
        """Update scrollbar position based on viewport"""
        if len(self.filtered_data) > 0:
            top = self.visible_start / len(self.filtered_data)
            bottom = self.visible_end / len(self.filtered_data)
            # This would need to be connected to an actual scrollbar widget


class AsyncUIUpdater:
    """Handles asynchronous UI updates to prevent blocking"""
    
    def __init__(self, root_widget):
        self.root = root_widget
        self.update_queue = deque()
        self.is_processing = False
        self.update_thread = None
        
    def schedule_update(self, update_func: Callable, *args, **kwargs):
        """Schedule a UI update to run asynchronously"""
        self.update_queue.append((update_func, args, kwargs))
        if not self.is_processing:
            self._start_processing()
    
    def _start_processing(self):
        """Start processing the update queue"""
        if self.update_thread and self.update_thread.is_alive():
            return
            
        self.is_processing = True
        self.update_thread = threading.Thread(target=self._process_updates)
        self.update_thread.daemon = True
        self.update_thread.start()
    
    def _process_updates(self):
        """Process updates from the queue"""
        while self.update_queue:
            try:
                update_func, args, kwargs = self.update_queue.popleft()
                
                # Schedule the actual UI update on the main thread
                self.root.after_idle(lambda f=update_func, a=args, k=kwargs: f(*a, **k))
                
                # Small delay to prevent overwhelming the UI thread
                time.sleep(0.001)
                
            except Exception as e:
                print(f"Error in async UI update: {e}")
        
        self.is_processing = False


class SmartCache:
    """Intelligent caching system for UI components"""
    
    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, Any] = {}
        self.access_times: Dict[str, float] = {}
        self.access_counts: Dict[str, int] = {}
        self.max_size = max_size
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        if key in self.cache:
            self.access_times[key] = time.time()
            self.access_counts[key] = self.access_counts.get(key, 0) + 1
            return self.cache[key]
        return None
    
    def set(self, key: str, value: Any):
        """Cache a value"""
        if len(self.cache) >= self.max_size:
            self._evict_least_used()
        
        self.cache[key] = value
        self.access_times[key] = time.time()
        self.access_counts[key] = 1
    
    def _evict_least_used(self):
        """Remove least recently used items"""
        # Sort by access time and count
        items = [(key, self.access_times.get(key, 0), self.access_counts.get(key, 0)) 
                 for key in self.cache.keys()]
        items.sort(key=lambda x: (x[1], x[2]))  # Sort by time, then count
        
        # Remove oldest 10% of items
        to_remove = max(1, len(items) // 10)
        for i in range(to_remove):
            key = items[i][0]
            del self.cache[key]
            del self.access_times[key]
            del self.access_counts[key]


class ResponsiveButton(ttk.Button):
    """Enhanced button with visual feedback and performance tracking"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent_app = parent
        self.original_command = kwargs.get('command')
        
        # Override command to add performance tracking
        if self.original_command:
            super().configure(command=self._tracked_command)
        
        # Visual feedback
        self.bind('<Button-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)
    
    def _tracked_command(self):
        """Execute command with performance tracking"""
        start_time = time.time()
        
        try:
            if self.original_command:
                self.original_command()
        finally:
            duration = time.time() - start_time
            
            # Find the UI metrics object
            app = self._find_app_root()
            if app and hasattr(app, 'ui_metrics'):
                app.ui_metrics.add_button_response(duration)
    
    def _find_app_root(self):
        """Find the main application object"""
        widget = self.parent_app
        while widget:
            if hasattr(widget, 'ui_metrics'):
                return widget
            widget = getattr(widget, 'parent', None) or getattr(widget, 'master', None)
        return None
    
    def _on_press(self, event):
        """Visual feedback on button press"""
        self.configure(relief='sunken')
    
    def _on_release(self, event):
        """Visual feedback on button release"""
        self.configure(relief='raised')


class UIOptimizationManager:
    """Main manager for all UI optimizations"""
    
    def __init__(self, root_app):
        self.app = root_app
        self.ui_metrics = UIPerformanceMetrics()
        self.smart_cache = SmartCache()
        self.async_updater = AsyncUIUpdater(root_app)
        self.virtualized_trees: Dict[str, VirtualizedTreeview] = {}
        
        # Performance monitoring
        self.monitoring_enabled = True
        self.last_performance_check = time.time()
        
        # Initialize optimizations
        self._setup_global_optimizations()
    
    def _setup_global_optimizations(self):
        """Set up global UI optimizations"""
        # Optimize tkinter settings
        if hasattr(self.app, 'tk'):
            self.app.tk.call('tk', 'scaling', 1.0)  # Consistent scaling
        
        # Schedule periodic performance monitoring
        self._schedule_performance_monitoring()
    
    def create_virtualized_treeview(self, parent, tree_widget: ttk.Treeview, 
                                  name: str, viewport_size: int = 50) -> VirtualizedTreeview:
        """Create a new virtualized treeview"""
        virt_tree = VirtualizedTreeview(self, tree_widget, viewport_size)
        self.virtualized_trees[name] = virt_tree
        return virt_tree
    
    def create_responsive_button(self, parent, **kwargs) -> ResponsiveButton:
        """Create a responsive button with performance tracking"""
        return ResponsiveButton(parent, **kwargs)
    
    def schedule_async_update(self, update_func: Callable, *args, **kwargs):
        """Schedule an asynchronous UI update"""
        self.async_updater.schedule_update(update_func, *args, **kwargs)
    
    def cache_ui_data(self, key: str, data: Any):
        """Cache UI-related data"""
        self.smart_cache.set(key, data)
    
    def get_cached_ui_data(self, key: str) -> Optional[Any]:
        """Retrieve cached UI data"""
        return self.smart_cache.get(key)
    
    def _schedule_performance_monitoring(self):
        """Schedule periodic performance checks"""
        if self.monitoring_enabled:
            current_time = time.time()
            if current_time - self.last_performance_check > 5.0:  # Check every 5 seconds
                self._check_ui_performance()
                self.last_performance_check = current_time
            
            # Schedule next check
            self.app.after(5000, self._schedule_performance_monitoring)
    
    def _check_ui_performance(self):
        """Check and optimize UI performance"""
        avg_render = self.ui_metrics.get_average_render_time()
        avg_update = self.ui_metrics.get_average_update_time()
        
        # If performance is degrading, trigger optimizations
        if avg_render > 0.1 or avg_update > 0.2:  # Thresholds in seconds
            self._trigger_performance_optimization()
    
    def _trigger_performance_optimization(self):
        """Trigger performance optimizations when needed"""
        print("UI Performance: Triggering optimizations...")
        
        # Clear old cache entries
        if len(self.smart_cache.cache) > self.smart_cache.max_size * 0.8:
            self.smart_cache._evict_least_used()
        
        # Optimize virtualized trees
        for virt_tree in self.virtualized_trees.values():
            if len(virt_tree.filtered_data) > virt_tree.viewport_size * 2:
                # Reduce viewport size temporarily if too much data
                virt_tree.viewport_size = max(25, virt_tree.viewport_size - 5)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive UI performance report"""
        return {
            'average_render_time': self.ui_metrics.get_average_render_time(),
            'average_update_time': self.ui_metrics.get_average_update_time(),
            'cache_size': len(self.smart_cache.cache),
            'cache_hit_rate': self._calculate_cache_hit_rate(),
            'virtualized_trees': len(self.virtualized_trees),
            'async_queue_size': len(self.async_updater.update_queue)
        }
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total_accesses = sum(self.smart_cache.access_counts.values())
        if total_accesses == 0:
            return 0.0
        
        # Estimate hits vs misses based on access counts
        estimated_hits = sum(count - 1 for count in self.smart_cache.access_counts.values() if count > 1)
        return estimated_hits / total_accesses if total_accesses > 0 else 0.0


# Example integration helper functions
def optimize_existing_treeview(app, tree_widget: ttk.Treeview, data: List[Dict], name: str):
    """Convert an existing treeview to use virtualization"""
    if not hasattr(app, 'ui_optimizer'):
        app.ui_optimizer = UIOptimizationManager(app)
    
    virt_tree = app.ui_optimizer.create_virtualized_treeview(
        app, tree_widget, name, viewport_size=50
    )
    virt_tree.set_data_source(data)
    return virt_tree


def add_responsive_button_to_frame(app, parent_frame, text: str, command: Callable, **kwargs):
    """Add a responsive button to a frame"""
    if not hasattr(app, 'ui_optimizer'):
        app.ui_optimizer = UIOptimizationManager(app)
    
    button = app.ui_optimizer.create_responsive_button(
        parent_frame, text=text, command=command, **kwargs
    )
    return button
