# Phase 3: Rendering Optimizations
# Advanced rendering and visual performance improvements

import tkinter as tk
from tkinter import ttk
import time
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import threading
from collections import defaultdict
import weakref

@dataclass
class RenderState:
    """Track rendering state for optimization"""
    last_render_time: float = 0.0
    render_count: int = 0
    dirty_regions: List[Tuple[int, int, int, int]] = field(default_factory=list)
    needs_full_refresh: bool = False
    visible_items: set = field(default_factory=set)


class DirtyRegionTracker:
    """Track which parts of the UI need re-rendering"""
    
    def __init__(self):
        self.dirty_regions: List[Tuple[int, int, int, int]] = []
        self.full_refresh_needed = False
    
    def mark_dirty(self, x: int, y: int, width: int, height: int):
        """Mark a region as needing re-rendering"""
        self.dirty_regions.append((x, y, width, height))
    
    def mark_full_refresh(self):
        """Mark that a full refresh is needed"""
        self.full_refresh_needed = True
        self.dirty_regions.clear()
    
    def get_dirty_regions(self) -> List[Tuple[int, int, int, int]]:
        """Get all dirty regions and clear the list"""
        if self.full_refresh_needed:
            self.full_refresh_needed = False
            return [(-1, -1, -1, -1)]  # Special marker for full refresh
        
        regions = self.dirty_regions.copy()
        self.dirty_regions.clear()
        return regions
    
    def optimize_regions(self) -> List[Tuple[int, int, int, int]]:
        """Merge overlapping dirty regions for efficient rendering"""
        if not self.dirty_regions:
            return []
        
        # Sort regions by x coordinate
        sorted_regions = sorted(self.dirty_regions, key=lambda r: (r[0], r[1]))
        merged = [sorted_regions[0]]
        
        for current in sorted_regions[1:]:
            last = merged[-1]
            
            # Check if regions overlap or are adjacent
            if (current[0] <= last[0] + last[2] and 
                current[1] <= last[1] + last[3]):
                # Merge regions
                new_x = min(last[0], current[0])
                new_y = min(last[1], current[1])
                new_width = max(last[0] + last[2], current[0] + current[2]) - new_x
                new_height = max(last[1] + last[3], current[1] + current[3]) - new_y
                merged[-1] = (new_x, new_y, new_width, new_height)
            else:
                merged.append(current)
        
        return merged


class RenderOptimizer:
    """Optimize rendering operations for better performance"""
    
    def __init__(self):
        self.render_states: Dict[str, RenderState] = {}
        self.dirty_tracker = DirtyRegionTracker()
        self.frame_rate_limit = 60  # Target FPS
        self.min_frame_time = 1.0 / self.frame_rate_limit
        self.last_frame_time = 0.0
        
        # Render batching
        self.pending_renders: Dict[str, Any] = {}
        self.render_timer = None
        
    def should_render(self, widget_id: str) -> bool:
        """Check if a widget should be rendered based on timing"""
        current_time = time.time()
        
        if current_time - self.last_frame_time < self.min_frame_time:
            return False
        
        state = self.render_states.get(widget_id)
        if state and current_time - state.last_render_time < self.min_frame_time:
            return False
        
        return True
    
    def mark_for_render(self, widget_id: str, widget: tk.Widget):
        """Mark a widget for rendering"""
        self.pending_renders[widget_id] = widget
        
        if self.render_timer is None:
            self.render_timer = widget.after_idle(self._batch_render)
    
    def _batch_render(self):
        """Render all pending widgets in a batch"""
        start_time = time.time()
        
        for widget_id, widget in self.pending_renders.items():
            if widget.winfo_exists():
                self._render_widget(widget_id, widget)
        
        self.pending_renders.clear()
        self.render_timer = None
        self.last_frame_time = time.time()
        
        # Track render performance
        render_time = time.time() - start_time
        if render_time > self.min_frame_time * 2:
            print(f"Render Warning: Batch took {render_time:.3f}s")
    
    def _render_widget(self, widget_id: str, widget: tk.Widget):
        """Render an individual widget"""
        try:
            widget.update_idletasks()
            
            # Update render state
            if widget_id not in self.render_states:
                self.render_states[widget_id] = RenderState()
            
            state = self.render_states[widget_id]
            state.last_render_time = time.time()
            state.render_count += 1
            
        except tk.TclError:
            # Widget was destroyed
            if widget_id in self.render_states:
                del self.render_states[widget_id]


class VisibilityOptimizer:
    """Optimize rendering based on widget visibility"""
    
    def __init__(self, root_widget):
        self.root = root_widget
        self.visible_widgets: set = set()
        self.viewport_cache: Dict[str, Tuple[int, int, int, int]] = {}
        
    def is_widget_visible(self, widget: tk.Widget) -> bool:
        """Check if a widget is currently visible"""
        try:
            if not widget.winfo_exists() or not widget.winfo_viewable():
                return False
            
            # Get widget geometry
            x = widget.winfo_x()
            y = widget.winfo_y()
            width = widget.winfo_width()
            height = widget.winfo_height()
            
            # Get root window geometry
            root_width = self.root.winfo_width()
            root_height = self.root.winfo_height()
            
            # Check if widget is within viewport
            return (x + width > 0 and x < root_width and 
                   y + height > 0 and y < root_height)
                   
        except tk.TclError:
            return False
    
    def update_visible_widgets(self):
        """Update the set of visible widgets"""
        new_visible = set()
        
        def check_widget(widget):
            if self.is_widget_visible(widget):
                new_visible.add(widget)
            
            # Check children
            try:
                for child in widget.winfo_children():
                    check_widget(child)
            except tk.TclError:
                pass
        
        check_widget(self.root)
        self.visible_widgets = new_visible
    
    def get_visible_widgets(self) -> set:
        """Get currently visible widgets"""
        return self.visible_widgets.copy()


class TextRenderOptimizer:
    """Optimize text rendering for large text widgets"""
    
    def __init__(self):
        self.text_cache: Dict[str, str] = {}
        self.syntax_cache: Dict[str, List[Tuple[str, str]]] = {}
        
    def optimize_text_widget(self, text_widget: tk.Text):
        """Apply optimizations to a text widget"""
        # Disable automatic text wrapping for performance
        text_widget.configure(wrap='none')
        
        # Use fixed-width font for better performance
        text_widget.configure(font=('Courier', 10))
        
        # Limit undo stack
        text_widget.configure(undo=True, maxundo=50)
        
        # Optimize tag rendering
        self._optimize_text_tags(text_widget)
    
    def _optimize_text_tags(self, text_widget: tk.Text):
        """Optimize text tag configuration"""
        # Configure common tags with optimized settings
        text_widget.tag_configure('highlight', background='yellow', 
                                 foreground='black')
        text_widget.tag_configure('bold', font=('Courier', 10, 'bold'))
        text_widget.tag_configure('italic', font=('Courier', 10, 'italic'))


class ImageOptimizer:
    """Optimize image loading and caching"""
    
    def __init__(self):
        self.image_cache: Dict[str, tk.PhotoImage] = {}
        self.scaled_cache: Dict[Tuple[str, int, int], tk.PhotoImage] = {}
        
    def load_optimized_image(self, path: str, max_width: int = None, 
                           max_height: int = None) -> Optional[tk.PhotoImage]:
        """Load and cache an optimized image"""
        cache_key = (path, max_width or -1, max_height or -1)
        
        if cache_key in self.scaled_cache:
            return self.scaled_cache[cache_key]
        
        try:
            # Load base image
            if path not in self.image_cache:
                self.image_cache[path] = tk.PhotoImage(file=path)
            
            base_image = self.image_cache[path]
            
            # Scale if needed
            if max_width or max_height:
                scaled = self._scale_image(base_image, max_width, max_height)
                self.scaled_cache[cache_key] = scaled
                return scaled
            else:
                return base_image
                
        except Exception as e:
            print(f"Error loading image {path}: {e}")
            return None
    
    def _scale_image(self, image: tk.PhotoImage, max_width: int, 
                    max_height: int) -> tk.PhotoImage:
        """Scale an image while maintaining aspect ratio"""
        original_width = image.width()
        original_height = image.height()
        
        # Calculate scaling factor
        width_ratio = max_width / original_width if max_width else 1.0
        height_ratio = max_height / original_height if max_height else 1.0
        scale_factor = min(width_ratio, height_ratio, 1.0)  # Don't upscale
        
        if scale_factor >= 1.0:
            return image
        
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        
        # Create scaled image
        scaled = tk.PhotoImage(width=new_width, height=new_height)
        
        # Simple scaling by sampling
        x_step = original_width / new_width
        y_step = original_height / new_height
        
        for y in range(new_height):
            src_y = int(y * y_step)
            for x in range(new_width):
                src_x = int(x * x_step)
                try:
                    pixel = image.get(src_x, src_y)
                    scaled.put(pixel, (x, y))
                except:
                    continue
        
        return scaled
    
    def clear_cache(self):
        """Clear image caches to free memory"""
        self.image_cache.clear()
        self.scaled_cache.clear()


class RenderingManager:
    """Main manager for all rendering optimizations"""
    
    def __init__(self, root_app):
        self.app = root_app
        self.render_optimizer = RenderOptimizer()
        self.visibility_optimizer = VisibilityOptimizer(root_app)
        self.text_optimizer = TextRenderOptimizer()
        self.image_optimizer = ImageOptimizer()
        
        # Performance monitoring
        self.frame_times: List[float] = []
        self.render_stats = defaultdict(int)
        
        # Setup periodic optimizations
        self._setup_periodic_optimizations()
    
    def _setup_periodic_optimizations(self):
        """Setup periodic optimization tasks"""
        # Update visibility every 100ms
        self.app.after(100, self._update_visibility)
        
        # Clean caches every 30 seconds
        self.app.after(30000, self._cleanup_caches)
    
    def _update_visibility(self):
        """Periodic visibility update"""
        self.visibility_optimizer.update_visible_widgets()
        self.app.after(100, self._update_visibility)
    
    def _cleanup_caches(self):
        """Periodic cache cleanup"""
        # Clear old render states
        current_time = time.time()
        old_states = [
            widget_id for widget_id, state in self.render_optimizer.render_states.items()
            if current_time - state.last_render_time > 300  # 5 minutes
        ]
        
        for widget_id in old_states:
            del self.render_optimizer.render_states[widget_id]
        
        # Clean image cache if it's getting large
        if len(self.image_optimizer.image_cache) > 50:
            self.image_optimizer.clear_cache()
        
        self.app.after(30000, self._cleanup_caches)
    
    def optimize_widget(self, widget: tk.Widget, widget_id: str = None):
        """Apply optimizations to a specific widget"""
        if widget_id is None:
            widget_id = str(id(widget))
        
        # Apply widget-specific optimizations
        if isinstance(widget, tk.Text):
            self.text_optimizer.optimize_text_widget(widget)
        elif isinstance(widget, ttk.Treeview):
            self._optimize_treeview(widget)
        elif isinstance(widget, tk.Canvas):
            self._optimize_canvas(widget)
    
    def _optimize_treeview(self, tree: ttk.Treeview):
        """Optimize treeview performance"""
        # Configure for better performance
        tree.configure(height=20)  # Limit visible rows
        
        # Note: Don't override yscrollcommand as it interferes with normal scrolling
        # The treeview's built-in scrolling is already optimized
    
    def _optimize_canvas(self, canvas: tk.Canvas):
        """Optimize canvas performance"""
        # Enable optimized rendering
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except:
            pass
    
    def mark_for_render(self, widget: tk.Widget, widget_id: str = None):
        """Mark a widget for optimized rendering"""
        if widget_id is None:
            widget_id = str(id(widget))
        
        self.render_optimizer.mark_for_render(widget_id, widget)
    
    def load_optimized_image(self, path: str, max_width: int = None, 
                           max_height: int = None) -> Optional[tk.PhotoImage]:
        """Load an optimized image"""
        return self.image_optimizer.load_optimized_image(path, max_width, max_height)
    
    def get_render_stats(self) -> Dict[str, Any]:
        """Get rendering performance statistics"""
        visible_count = len(self.visibility_optimizer.get_visible_widgets())
        
        return {
            'visible_widgets': visible_count,
            'cached_images': len(self.image_optimizer.image_cache),
            'scaled_images': len(self.image_optimizer.scaled_cache),
            'render_states': len(self.render_optimizer.render_states),
            'pending_renders': len(self.render_optimizer.pending_renders),
            'target_fps': self.render_optimizer.frame_rate_limit,
            'min_frame_time': self.render_optimizer.min_frame_time
        }


# Integration helpers
def setup_rendering_optimizations(app):
    """Setup rendering optimizations for an app"""
    if not hasattr(app, 'rendering_manager'):
        app.rendering_manager = RenderingManager(app)
    return app.rendering_manager


def optimize_window_rendering(window):
    """Apply rendering optimizations to a window"""
    if hasattr(window, 'parent') and hasattr(window.parent, 'rendering_manager'):
        manager = window.parent.rendering_manager
        
        # Optimize all widgets in the window
        def optimize_widgets(widget):
            manager.optimize_widget(widget)
            try:
                for child in widget.winfo_children():
                    optimize_widgets(child)
            except tk.TclError:
                pass
        
        optimize_widgets(window)
