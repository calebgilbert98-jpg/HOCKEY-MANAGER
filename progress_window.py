# progress_window.py
# Progress dialog for database generation

import tkinter as tk
from tkinter import ttk
import threading
import time

class ProgressWindow:
    """Professional progress window for database generation"""
    
    def __init__(self, parent=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Puck Dynasty - Database Generation")
        self.root.geometry("500x200")
        self.root.configure(bg='#1e1e1e')
        self.root.resizable(False, False)
        
        # Center the window
        self.root.transient(parent)
        self.root.grab_set()
        
        # Center on parent or screen
        if parent:
            parent.update_idletasks()
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 250
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 100
        else:
            x = (self.root.winfo_screenwidth() // 2) - 250
            y = (self.root.winfo_screenheight() // 2) - 100
        
        self.root.geometry(f"500x200+{x}+{y}")
        
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="Initializing database generation...")
        self.detail_var = tk.StringVar(value="")
        
        self._create_ui()
        
    def _create_ui(self):
        """Create the progress dialog UI"""
        # Full-bleed branded background behind the progress content
        try:
            from branding import cover_photo
            bg_canvas = tk.Canvas(self.root, highlightthickness=0, bg='#1e1e1e')
            bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._bg_photo = cover_photo('loading_bg.png', 500, 200)
            if self._bg_photo is not None:
                bg_canvas.create_image(250, 100, image=self._bg_photo)
        except Exception:
            pass  # Background is decorative; never break the progress dialog

        # Main frame with professional styling
        main_frame = tk.Frame(self.root, bg='#1e1e1e', bd=0)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Title
        title_label = tk.Label(main_frame,
                              text="Generating Hockey Database",
                              font=("Arial", 16, "bold"),
                              bg='#1e1e1e',
                              fg='#00ceb8')
        title_label.pack(pady=(0, 20))
        
        # Status label
        self.status_label = tk.Label(main_frame, 
                                   textvariable=self.status_var,
                                   font=("Arial", 12),
                                   bg='#1e1e1e', 
                                   fg='#ffffff',
                                   wraplength=450)
        self.status_label.pack(pady=(0, 10))
        
        # Progress bar with professional styling
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Professional.Horizontal.TProgressbar",
                       background='#00ceb8',
                       troughcolor='#404040',
                       borderwidth=0,
                       lightcolor='#00ceb8',
                       darkcolor='#00ceb8')
        
        self.progress_bar = ttk.Progressbar(main_frame,
                                          variable=self.progress_var,
                                          maximum=100,
                                          style="Professional.Horizontal.TProgressbar",
                                          length=400,
                                          mode='determinate')
        self.progress_bar.pack(pady=(0, 15))
        
        # Detail label for specific operations
        self.detail_label = tk.Label(main_frame, 
                                    textvariable=self.detail_var,
                                    font=("Arial", 10),
                                    bg='#1e1e1e', 
                                    fg='#B0B0B0',
                                    wraplength=450)
        self.detail_label.pack()
        
        # Prevent window closing during generation
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
    def _on_closing(self):
        """Prevent closing during generation"""
        pass  # Do nothing - prevent closing
        
    def update_progress(self, percentage, status, detail=""):
        """Update the progress bar and status"""
        self.progress_var.set(percentage)
        self.status_var.set(status)
        self.detail_var.set(detail)
        self.root.update_idletasks()
        
    def close(self):
        """Close the progress window"""
        try:
            self.root.destroy()
        except:
            pass

class DatabaseGenerationProgress:
    """Context manager for database generation progress"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.progress_window = None
        self.is_cancelled = False
        
    def __enter__(self):
        self.progress_window = ProgressWindow(self.parent)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.progress_window:
            self.progress_window.close()
            
    def update(self, percentage, status, detail=""):
        """Update progress"""
        if self.progress_window:
            self.progress_window.update_progress(percentage, status, detail)
            
    def set_status(self, status, detail=""):
        """Set status without changing percentage"""
        if self.progress_window:
            current_progress = self.progress_window.progress_var.get()
            self.progress_window.update_progress(current_progress, status, detail)

# Test the progress window
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Hide main window
    
    with DatabaseGenerationProgress() as progress:
        progress.update(0, "Starting database generation...")
        time.sleep(1)
        
        progress.update(25, "Generating teams and leagues...", "Creating NHL teams")
        time.sleep(1)
        
        progress.update(50, "Generating players...", "Creating forwards (1,250 / 2,500)")
        time.sleep(1)
        
        progress.update(75, "Generating contracts and staff...", "Assigning contracts")
        time.sleep(1)
        
        progress.update(100, "Database generation complete!", "Ready to start game")
        time.sleep(1)
    
    print("Progress test complete")
