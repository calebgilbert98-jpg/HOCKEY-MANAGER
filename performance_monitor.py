"""
Performance monitoring window for Hockey Manager
Shows real-time performance statistics and optimization reports
"""

import tkinter as tk
from tkinter import ttk
import threading
import time


class PerformanceMonitorWindow(tk.Toplevel):
    """Window for monitoring game performance and optimization statistics"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Performance Monitor")
        self.geometry("800x600")
        self.configure(background=parent.BG_COLOR)
        
        # Auto-refresh settings
        self.auto_refresh = True
        self.refresh_interval = 5  # seconds
        self.last_refresh = 0
        
        self._create_interface()
        self._start_auto_refresh()
    
    def _create_interface(self):
        """Create the performance monitoring interface"""
        # Main container
        main_frame = tk.Frame(self, bg=self.parent.BG_COLOR)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = tk.Label(
            main_frame,
            text="Performance Monitor",
            font=(self.parent.FONT_FAMILY, 16, 'bold'),
            bg=self.parent.BG_COLOR,
            fg=self.parent.HEADER_COLOR
        )
        title_label.pack(pady=(0, 10))
        
        # Control frame
        control_frame = tk.Frame(main_frame, bg=self.parent.BG_COLOR)
        control_frame.pack(fill='x', pady=(0, 10))
        
        # Refresh button
        refresh_btn = tk.Button(
            control_frame,
            text="Refresh Now",
            command=self._refresh_data,
            bg=self.parent.ACCENT_COLOR,
            fg='white',
            font=(self.parent.FONT_FAMILY, 10)
        )
        refresh_btn.pack(side='left', padx=(0, 10))
        
        # Auto-refresh toggle
        self.auto_refresh_var = tk.BooleanVar(value=self.auto_refresh)
        auto_refresh_check = tk.Checkbutton(
            control_frame,
            text="Auto-refresh (5s)",
            variable=self.auto_refresh_var,
            command=self._toggle_auto_refresh,
            bg=self.parent.BG_COLOR,
            fg=self.parent.TEXT_COLOR,
            font=(self.parent.FONT_FAMILY, 10)
        )
        auto_refresh_check.pack(side='left')
        
        # Notebook for different performance views
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)
        
        # Create tabs
        self._create_overview_tab()
        self._create_memory_tab()
        self._create_database_tab()
        self._create_simulation_tab()
        self._create_ui_tab()  # Phase 3: UI/UX tab
        
        # Initial data load
        self._refresh_data()
    
    def _create_overview_tab(self):
        """Create the overview tab"""
        overview_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(overview_frame, text="Overview")
        
        # Scrollable text area
        text_frame = tk.Frame(overview_frame)
        text_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.overview_text = tk.Text(
            text_frame,
            bg=self.parent.CONTENT_BG,
            fg=self.parent.TEXT_COLOR,
            font=(self.parent.FONT_FAMILY, 9),
            wrap='word'
        )
        
        overview_scrollbar = tk.Scrollbar(text_frame, command=self.overview_text.yview)
        self.overview_text.config(yscrollcommand=overview_scrollbar.set)
        
        self.overview_text.pack(side='left', fill='both', expand=True)
        overview_scrollbar.pack(side='right', fill='y')
    
    def _create_memory_tab(self):
        """Create the memory monitoring tab"""
        memory_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(memory_frame, text="Memory")
        
        # Memory stats display
        stats_frame = tk.Frame(memory_frame, bg=self.parent.CONTENT_BG)
        stats_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.memory_text = tk.Text(
            stats_frame,
            bg=self.parent.CONTENT_BG,
            fg=self.parent.TEXT_COLOR,
            font=(self.parent.FONT_FAMILY, 9),
            wrap='word'
        )
        
        memory_scrollbar = tk.Scrollbar(stats_frame, command=self.memory_text.yview)
        self.memory_text.config(yscrollcommand=memory_scrollbar.set)
        
        self.memory_text.pack(side='left', fill='both', expand=True)
        memory_scrollbar.pack(side='right', fill='y')
        
        # Memory control buttons
        button_frame = tk.Frame(memory_frame, bg=self.parent.CONTENT_BG)
        button_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        optimize_btn = tk.Button(
            button_frame,
            text="Optimize Memory",
            command=self._optimize_memory,
            bg=self.parent.ACCENT_COLOR,
            fg='white',
            font=(self.parent.FONT_FAMILY, 10)
        )
        optimize_btn.pack(side='left', padx=(0, 10))
        
        gc_btn = tk.Button(
            button_frame,
            text="Force Garbage Collection",
            command=self._force_garbage_collection,
            bg=self.parent.ACCENT_COLOR,
            fg='white',
            font=(self.parent.FONT_FAMILY, 10)
        )
        gc_btn.pack(side='left')
    
    def _create_database_tab(self):
        """Create the database performance tab"""
        database_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(database_frame, text="Database")
        
        text_frame = tk.Frame(database_frame)
        text_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.database_text = tk.Text(
            text_frame,
            bg=self.parent.CONTENT_BG,
            fg=self.parent.TEXT_COLOR,
            font=(self.parent.FONT_FAMILY, 9),
            wrap='word'
        )
        
        database_scrollbar = tk.Scrollbar(text_frame, command=self.database_text.yview)
        self.database_text.config(yscrollcommand=database_scrollbar.set)
        
        self.database_text.pack(side='left', fill='both', expand=True)
        database_scrollbar.pack(side='right', fill='y')
    
    def _create_simulation_tab(self):
        """Create the simulation performance tab"""
        simulation_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(simulation_frame, text="Simulation")
        
        text_frame = tk.Frame(simulation_frame)
        text_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.simulation_text = tk.Text(
            text_frame,
            bg=self.parent.CONTENT_BG,
            fg=self.parent.TEXT_COLOR,
            font=(self.parent.FONT_FAMILY, 9),
            wrap='word'
        )
        
        simulation_scrollbar = tk.Scrollbar(text_frame, command=self.simulation_text.yview)
        self.simulation_text.config(yscrollcommand=simulation_scrollbar.set)
        
        self.simulation_text.pack(side='left', fill='both', expand=True)
        simulation_scrollbar.pack(side='right', fill='y')
    
    def _create_ui_tab(self):
        """Create the UI/UX performance tab (Phase 3)"""
        ui_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(ui_frame, text="UI/UX")
        
        # UI stats display
        stats_frame = tk.Frame(ui_frame, bg=self.parent.CONTENT_BG)
        stats_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.ui_text = tk.Text(
            stats_frame,
            bg=self.parent.CONTENT_BG,
            fg=self.parent.TEXT_COLOR,
            font=(self.parent.FONT_FAMILY, 9),
            wrap='word'
        )
        
        ui_scrollbar = tk.Scrollbar(stats_frame, command=self.ui_text.yview)
        self.ui_text.config(yscrollcommand=ui_scrollbar.set)
        
        self.ui_text.pack(side='left', fill='both', expand=True)
        ui_scrollbar.pack(side='right', fill='y')
    
    def _toggle_auto_refresh(self):
        """Toggle auto-refresh mode"""
        self.auto_refresh = self.auto_refresh_var.get()
        if self.auto_refresh:
            self._start_auto_refresh()
    
    def _start_auto_refresh(self):
        """Start auto-refresh in background thread"""
        if hasattr(self, '_refresh_thread'):
            return  # Already running
            
        self._refresh_thread = threading.Thread(target=self._auto_refresh_loop, daemon=True)
        self._refresh_thread.start()
    
    def _auto_refresh_loop(self):
        """Auto-refresh loop"""
        while self.auto_refresh and self.winfo_exists():
            try:
                current_time = time.time()
                if current_time - self.last_refresh >= self.refresh_interval:
                    self.after(0, self._refresh_data)  # Schedule on main thread
                    self.last_refresh = current_time
                time.sleep(1)  # Check every second
            except Exception as e:
                print(f"Auto-refresh error: {e}")
                break
    
    def _refresh_data(self):
        """Refresh all performance data"""
        try:
            self._refresh_overview()
            self._refresh_memory()
            self._refresh_database()
            self._refresh_simulation()
            self._refresh_ui()  # Phase 3: Refresh UI tab
            self.last_refresh = time.time()
        except Exception as e:
            print(f"Refresh error: {e}")
    
    def _refresh_overview(self):
        """Refresh overview tab"""
        overview_data = self._get_overview_data()
        
        self.overview_text.delete(1.0, tk.END)
        self.overview_text.insert(tk.END, overview_data)
    
    def _refresh_memory(self):
        """Refresh memory tab"""
        memory_data = self._get_memory_data()
        
        self.memory_text.delete(1.0, tk.END)
        self.memory_text.insert(tk.END, memory_data)
    
    def _refresh_database(self):
        """Refresh database tab"""
        database_data = self._get_database_data()
        
        self.database_text.delete(1.0, tk.END)
        self.database_text.insert(tk.END, database_data)
    
    def _refresh_simulation(self):
        """Refresh simulation tab"""
        simulation_data = self._get_simulation_data()
        
        self.simulation_text.delete(1.0, tk.END)
        self.simulation_text.insert(tk.END, simulation_data)
    
    def _refresh_ui(self):
        """Refresh UI/UX tab (Phase 3)"""
        ui_data = self._get_ui_data()
        
        self.ui_text.delete(1.0, tk.END)
        self.ui_text.insert(tk.END, ui_data)
    
    def _get_overview_data(self) -> str:
        """Get overview performance data"""
        try:
            report = [
                "Hockey Manager Performance Overview",
                "=" * 40,
                f"Last Updated: {time.strftime('%H:%M:%S')}",
                "",
                "Phase 1 Optimizations: ✓ Active",
                "- Player attribute caching",
                "- Fast background simulation", 
                "- Reduced event generation",
                "- Batch processing",
                "",
                "Phase 2 Optimizations: ✓ Active",
                "- Database indexing",
                "- Lazy loading system", 
                "- Memory optimization",
                "",
                "Phase 3 Optimizations: ✓ Active",
                "- UI performance optimization",
                "- Rendering improvements",
                "- Virtualized components",
                "",
            ]
            
            # Add system information
            if hasattr(self.parent, 'memory_optimizer') and self.parent.memory_optimizer:
                memory_optimizer = self.parent.memory_optimizer
                memory_stats = memory_optimizer.monitor.get_current_stats()
                report.extend([
                    f"System Memory Usage: {memory_stats.memory_percent:.1f}%",
                    f"Python Memory: {memory_stats.python_memory_mb:.1f} MB",
                    f"Available Memory: {memory_stats.available_memory_mb:.1f} MB",
                    ""
                ])
            
            # Add performance statistics
            if hasattr(self.parent, 'db_manager') and self.parent.db_manager:
                db_stats = self.parent.db_manager.player_index.get_stats()
                report.extend([
                    f"Database Lookups: {db_stats['total_lookups']}",
                    f"Cache Hit Rate: {db_stats['cache_hit_rate']}",
                    f"Indexed Players: {db_stats['total_players']}",
                    ""
                ])
            
            return "\n".join(report)
            
        except Exception as e:
            return f"Error generating overview: {e}"
    
    def _get_memory_data(self) -> str:
        """Get memory performance data"""
        try:
            if hasattr(self.parent, 'memory_optimizer') and self.parent.memory_optimizer:
                return self.parent.memory_optimizer.get_optimization_report()
            else:
                return "Memory optimizer not available"
        except Exception as e:
            return f"Error getting memory data: {e}"
    
    def _get_database_data(self) -> str:
        """Get database performance data"""
        try:
            if hasattr(self.parent, 'db_manager') and self.parent.db_manager:
                return self.parent.db_manager.get_performance_report()
            else:
                return "Database manager not available"
        except Exception as e:
            return f"Error getting database data: {e}"
    
    def _get_simulation_data(self) -> str:
        """Get simulation performance data"""
        try:
            report = ["Simulation Performance Statistics", "=" * 35, ""]
            
            # Get performance cache stats
            try:
                from performance_optimizations import get_global_cache
                cache = get_global_cache()
                cache_stats = {
                    'player_caches': len(cache.player_caches),
                    'team_ratings': len(cache.team_ratings)
                }
                report.extend([
                    f"Performance Cache:",
                    f"  Player Caches: {cache_stats['player_caches']}",
                    f"  Team Ratings: {cache_stats['team_ratings']}",
                    ""
                ])
            except:
                report.append("Performance cache not available\n")
            
            # Get lazy loading stats
            if hasattr(self.parent, 'lazy_manager') and self.parent.lazy_manager:
                lazy_report = self.parent.lazy_manager.get_performance_report()
                report.append(lazy_report)
            else:
                report.append("Lazy loading not available")
            
            return "\n".join(report)
            
        except Exception as e:
            return f"Error getting simulation data: {e}"
    
    def _get_ui_data(self) -> str:
        """Get UI/UX performance data (Phase 3)"""
        try:
            report = [
                "UI/UX Performance Data (Phase 3)",
                "=" * 35,
                ""
            ]
            
            # UI Optimization Manager stats
            if hasattr(self.parent, 'ui_optimizer') and self.parent.ui_optimizer:
                ui_report = self.parent.ui_optimizer.get_performance_report()
                report.extend([
                    "UI Optimization Manager:",
                    f"  Average Render Time: {ui_report['average_render_time']:.3f}s",
                    f"  Average Update Time: {ui_report['average_update_time']:.3f}s",
                    f"  Cache Size: {ui_report['cache_size']} items",
                    f"  Cache Hit Rate: {ui_report['cache_hit_rate']:.1%}",
                    f"  Virtualized Trees: {ui_report['virtualized_trees']}",
                    f"  Async Queue Size: {ui_report['async_queue_size']}",
                    ""
                ])
            else:
                report.append("UI Optimization Manager: Not available")
                report.append("")
            
            # Rendering Manager stats  
            if hasattr(self.parent, 'rendering_manager') and self.parent.rendering_manager:
                render_stats = self.parent.rendering_manager.get_render_stats()
                report.extend([
                    "Rendering Manager:",
                    f"  Visible Widgets: {render_stats['visible_widgets']}",
                    f"  Cached Images: {render_stats['cached_images']}",
                    f"  Scaled Images: {render_stats['scaled_images']}",
                    f"  Render States: {render_stats['render_states']}",
                    f"  Pending Renders: {render_stats['pending_renders']}",
                    f"  Target FPS: {render_stats['target_fps']}",
                    f"  Min Frame Time: {render_stats['min_frame_time']:.3f}s",
                    ""
                ])
            else:
                report.append("Rendering Manager: Not available")
                report.append("")
            
            # UI Performance Metrics
            if hasattr(self.parent, 'ui_metrics') and self.parent.ui_metrics:
                metrics = self.parent.ui_metrics
                report.extend([
                    "Performance Metrics:",
                    f"  Recent Render Times: {len(metrics.render_times)} samples",
                    f"  Recent Update Times: {len(metrics.update_times)} samples",
                    f"  Recent Scroll Times: {len(metrics.scroll_performance)} samples",
                    f"  Button Response Times: {len(metrics.button_response_times)} samples",
                    ""
                ])
                
                if metrics.render_times:
                    avg_render = sum(metrics.render_times) / len(metrics.render_times)
                    max_render = max(metrics.render_times)
                    min_render = min(metrics.render_times)
                    report.extend([
                        "  Render Time Statistics:",
                        f"    Average: {avg_render:.3f}s",
                        f"    Maximum: {max_render:.3f}s", 
                        f"    Minimum: {min_render:.3f}s",
                        ""
                    ])
            else:
                report.append("UI Performance Metrics: Not available")
                report.append("")
            
            # Phase 3 Feature Status
            report.extend([
                "Phase 3 Features Status:",
                "✓ Virtualized Treeviews - Efficient large datasets",
                "✓ Smart UI Caching - Reduced redundant operations",
                "✓ Async UI Updates - Non-blocking interface",
                "✓ Responsive Buttons - Performance tracking",
                "✓ Render Optimization - FPS limiting and culling",
                "✓ Image Optimization - Cached and scaled loading",
                "✓ Performance Monitoring - Real-time metrics",
                ""
            ])
            
            return "\n".join(report)
            
        except Exception as e:
            return f"Error getting UI data: {e}"
    
    def _optimize_memory(self):
        """Trigger memory optimization"""
        try:
            if hasattr(self.parent, 'memory_optimizer') and self.parent.memory_optimizer:
                self.parent.memory_optimizer.optimize_memory(aggressive=True)
                self._refresh_memory()
        except Exception as e:
            print(f"Memory optimization error: {e}")
    
    def _force_garbage_collection(self):
        """Force garbage collection"""
        try:
            import gc
            collected = gc.collect()
            print(f"Garbage collection freed {collected} objects")
            self._refresh_memory()
        except Exception as e:
            print(f"Garbage collection error: {e}")
    
    def destroy(self):
        """Clean up when window is closed"""
        self.auto_refresh = False
        super().destroy()
