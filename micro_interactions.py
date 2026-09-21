# micro_interactions.py
# Smooth animations and micro-interactions for enhanced UX

import tkinter as tk
from typing import Callable, Dict, Any
import math

class SmoothAnimations:
    """Handles smooth animations and transitions"""
    
    def __init__(self, root):
        self.root = root
        self.active_animations = {}
        self.animation_id_counter = 0
        
    def fade_in_widget(self, widget, duration=300, callback=None):
        """Fade in a widget smoothly"""
        self.animation_id_counter += 1
        animation_id = self.animation_id_counter
        
        steps = 15
        step_duration = duration // steps
        
        def animate_step(step):
            if animation_id not in self.active_animations:
                return
                
            if step <= steps:
                # Simulate fade by adjusting relief and border
                if step < steps // 2:
                    widget.configure(relief='flat', bd=0)
                else:
                    widget.configure(relief='raised', bd=1)
                
                self.root.after(step_duration, lambda: animate_step(step + 1))
            else:
                if animation_id in self.active_animations:
                    del self.active_animations[animation_id]
                if callback:
                    callback()
        
        self.active_animations[animation_id] = True
        animate_step(0)
        return animation_id
    
    def slide_in_from_bottom(self, widget, distance=50, duration=400, callback=None):
        """Slide widget in from bottom"""
        self.animation_id_counter += 1
        animation_id = self.animation_id_counter
        
        steps = 20
        step_duration = duration // steps
        step_distance = distance / steps
        
        # Store original position
        original_y = widget.winfo_y()
        start_y = original_y + distance
        
        def animate_step(step):
            if animation_id not in self.active_animations:
                return
                
            if step <= steps:
                # Calculate current position using easing
                progress = step / steps
                eased_progress = self._ease_out_quad(progress)
                current_y = start_y - (distance * eased_progress)
                
                # For grid widgets, we can't easily move them, so simulate with padding
                try:
                    widget.grid_configure(pady=(max(0, int(current_y - original_y)), 0))
                except:
                    pass
                
                self.root.after(step_duration, lambda: animate_step(step + 1))
            else:
                widget.grid_configure(pady=0)
                if animation_id in self.active_animations:
                    del self.active_animations[animation_id]
                if callback:
                    callback()
        
        self.active_animations[animation_id] = True
        animate_step(0)
        return animation_id
    
    def scale_bounce(self, widget, duration=600, callback=None):
        """Bounce scale animation for emphasis"""
        self.animation_id_counter += 1
        animation_id = self.animation_id_counter
        
        steps = 30
        step_duration = duration // steps
        
        def animate_step(step):
            if animation_id not in self.active_animations:
                return
                
            if step <= steps:
                # Calculate scale using bounce easing
                progress = step / steps
                scale = 1.0 + (0.1 * math.sin(progress * math.pi * 4) * (1 - progress))
                
                # Simulate scaling by adjusting padding
                padding_adjustment = int(5 * (scale - 1.0))
                try:
                    current_padx = widget.cget('padx')
                    current_pady = widget.cget('pady')
                    new_padx = max(0, current_padx + padding_adjustment)
                    new_pady = max(0, current_pady + padding_adjustment)
                    widget.configure(padx=new_padx, pady=new_pady)
                except:
                    pass
                
                self.root.after(step_duration, lambda: animate_step(step + 1))
            else:
                # Reset to original padding
                try:
                    widget.configure(padx=12, pady=8)  # Default padding
                except:
                    pass
                if animation_id in self.active_animations:
                    del self.active_animations[animation_id]
                if callback:
                    callback()
        
        self.active_animations[animation_id] = True
        animate_step(0)
        return animation_id
    
    def color_transition(self, widget, start_color, end_color, duration=300, callback=None):
        """Smooth color transition"""
        self.animation_id_counter += 1
        animation_id = self.animation_id_counter
        
        steps = 20
        step_duration = duration // steps
        
        # Parse colors (simplified - assumes hex colors)
        start_rgb = self._hex_to_rgb(start_color)
        end_rgb = self._hex_to_rgb(end_color)
        
        def animate_step(step):
            if animation_id not in self.active_animations:
                return
                
            if step <= steps:
                progress = step / steps
                eased_progress = self._ease_in_out_quad(progress)
                
                # Interpolate color
                current_rgb = [
                    int(start_rgb[i] + (end_rgb[i] - start_rgb[i]) * eased_progress)
                    for i in range(3)
                ]
                current_color = self._rgb_to_hex(current_rgb)
                
                try:
                    widget.configure(bg=current_color)
                except:
                    pass
                
                self.root.after(step_duration, lambda: animate_step(step + 1))
            else:
                widget.configure(bg=end_color)
                if animation_id in self.active_animations:
                    del self.active_animations[animation_id]
                if callback:
                    callback()
        
        self.active_animations[animation_id] = True
        animate_step(0)
        return animation_id
    
    def stop_animation(self, animation_id):
        """Stop a specific animation"""
        if animation_id in self.active_animations:
            del self.active_animations[animation_id]
    
    def stop_all_animations(self):
        """Stop all active animations"""
        self.active_animations.clear()
    
    # Easing functions
    def _ease_out_quad(self, t):
        """Quadratic ease out"""
        return 1 - (1 - t) * (1 - t)
    
    def _ease_in_out_quad(self, t):
        """Quadratic ease in/out"""
        if t < 0.5:
            return 2 * t * t
        return 1 - pow(-2 * t + 2, 2) / 2
    
    # Color utilities
    def _hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _rgb_to_hex(self, rgb):
        """Convert RGB tuple to hex color"""
        return '#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])

class InteractiveEffects:
    """Handles interactive effects and hover states"""
    
    def __init__(self, animations: SmoothAnimations):
        self.animations = animations
        
    def add_hover_lift(self, widget, lift_amount=2):
        """Add hover lift effect to widget"""
        original_relief = widget.cget('relief')
        original_bd = widget.cget('bd')
        
        def on_enter(event):
            widget.configure(relief='raised', bd=lift_amount)
            
        def on_leave(event):
            widget.configure(relief=original_relief, bd=original_bd)
            
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)
    
    def add_hover_color_change(self, widget, hover_color):
        """Add hover color change effect"""
        original_bg = widget.cget('bg')
        
        def on_enter(event):
            self.animations.color_transition(widget, original_bg, hover_color, 150)
            
        def on_leave(event):
            self.animations.color_transition(widget, hover_color, original_bg, 150)
            
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)
    
    def add_click_bounce(self, widget):
        """Add click bounce effect"""
        def on_click(event):
            self.animations.scale_bounce(widget, 300)
            
        widget.bind('<Button-1>', on_click)
    
    def add_focus_glow(self, widget, glow_color="#FFD700"):
        """Add focus glow effect for input widgets"""
        original_bg = widget.cget('bg')
        
        def on_focus_in(event):
            self.animations.color_transition(widget, original_bg, glow_color, 200)
            
        def on_focus_out(event):
            self.animations.color_transition(widget, glow_color, original_bg, 200)
            
        widget.bind('<FocusIn>', on_focus_in)
        widget.bind('<FocusOut>', on_focus_out)

class LoadingAnimations:
    """Specialized loading and progress animations"""
    
    def __init__(self, root):
        self.root = root
        
    def create_loading_spinner(self, parent, size=20, color="#D13438"):
        """Create animated loading spinner"""
        canvas = tk.Canvas(parent, width=size, height=size, 
                          bg=parent.cget('bg'), highlightthickness=0)
        
        # Draw spinner arc
        spinner_arc = canvas.create_arc(2, 2, size-2, size-2,
                                       start=0, extent=90,
                                       outline=color, width=3,
                                       style='arc')
        
        # Animation function
        angle = 0
        def animate_spinner():
            nonlocal angle
            angle = (angle + 15) % 360
            canvas.itemconfig(spinner_arc, start=angle)
            canvas.after(50, animate_spinner)
        
        animate_spinner()
        return canvas
    
    def create_progress_bar(self, parent, width=200, height=6, 
                           bg_color="#333333", fill_color="#D13438"):
        """Create animated progress bar"""
        canvas = tk.Canvas(parent, width=width, height=height,
                          bg=parent.cget('bg'), highlightthickness=0)
        
        # Background
        canvas.create_rectangle(0, 0, width, height, fill=bg_color, outline="")
        
        # Progress fill
        progress_rect = canvas.create_rectangle(0, 0, 0, height, 
                                               fill=fill_color, outline="")
        
        def update_progress(percentage):
            """Update progress (0-100)"""
            fill_width = int((percentage / 100) * width)
            canvas.coords(progress_rect, 0, 0, fill_width, height)
        
        canvas.update_progress = update_progress
        return canvas
    
    def create_pulse_dot(self, parent, color="#D13438", size=8):
        """Create pulsing dot indicator"""
        canvas = tk.Canvas(parent, width=size*2, height=size*2,
                          bg=parent.cget('bg'), highlightthickness=0)
        
        dot = canvas.create_oval(size//2, size//2, size*1.5, size*1.5,
                                fill=color, outline="")
        
        # Pulse animation
        scale = 1.0
        direction = 1
        
        def animate_pulse():
            nonlocal scale, direction
            scale += direction * 0.1
            if scale >= 1.5:
                direction = -1
            elif scale <= 0.8:
                direction = 1
            
            # Update dot size
            center = size
            radius = size * scale / 2
            canvas.coords(dot, center - radius, center - radius,
                         center + radius, center + radius)
            
            canvas.after(100, animate_pulse)
        
        animate_pulse()
        return canvas

class NotificationSystem:
    """In-app notification system with animations"""
    
    def __init__(self, root, animations: SmoothAnimations):
        self.root = root
        self.animations = animations
        self.active_notifications = []
        
    def show_success_notification(self, message, duration=3000):
        """Show success notification"""
        return self._show_notification(message, "success", duration)
    
    def show_warning_notification(self, message, duration=4000):
        """Show warning notification"""
        return self._show_notification(message, "warning", duration)
    
    def show_error_notification(self, message, duration=5000):
        """Show error notification"""
        return self._show_notification(message, "error", duration)
    
    def _show_notification(self, message, type_name, duration):
        """Show notification with animation"""
        # Colors based on type
        colors = {
            "success": {"bg": "#28A745", "fg": "white"},
            "warning": {"bg": "#FFC107", "fg": "black"},
            "error": {"bg": "#DC3545", "fg": "white"}
        }
        
        color_scheme = colors.get(type_name, colors["success"])
        
        # Create notification frame
        notification_frame = tk.Toplevel(self.root)
        notification_frame.withdraw()  # Hide initially
        notification_frame.overrideredirect(True)  # Remove window decorations
        notification_frame.configure(bg=color_scheme["bg"])
        
        # Position at top right
        notification_frame.geometry("300x60+{}+50".format(
            self.root.winfo_x() + self.root.winfo_width() - 320
        ))
        
        # Notification content
        content_frame = tk.Frame(notification_frame, bg=color_scheme["bg"], padx=16, pady=12)
        content_frame.pack(fill='both', expand=True)
        
        # Icon
        icons = {"success": "✓", "warning": "⚠", "error": "✗"}
        icon_label = tk.Label(content_frame, text=icons.get(type_name, "ℹ"),
                             font=('Segoe UI', 16),
                             fg=color_scheme["fg"], bg=color_scheme["bg"])
        icon_label.pack(side='left', padx=(0, 8))
        
        # Message
        message_label = tk.Label(content_frame, text=message,
                                font=('Segoe UI', 10),
                                fg=color_scheme["fg"], bg=color_scheme["bg"],
                                wraplength=220, justify='left')
        message_label.pack(side='left', fill='x', expand=True)
        
        # Show with animation
        notification_frame.deiconify()
        self.animations.slide_in_from_bottom(notification_frame, 20, 300)
        
        # Auto-hide after duration
        def hide_notification():
            if notification_frame.winfo_exists():
                self.animations.fade_in_widget(notification_frame, 200, 
                                             lambda: notification_frame.destroy())
        
        self.root.after(duration, hide_notification)
        
        # Add to active notifications
        self.active_notifications.append(notification_frame)
        
        return notification_frame
