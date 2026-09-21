"""
Patch to fix main() function in main.py
Run this to update main.py to use the splash launcher
"""

def patch_main_py():
    """Patch the main() function to use splash launcher"""
    
    # Read the entire file
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find and replace the main() function
    old_main = '''def main():
    """Main function to start the game - direct launch for simplicity"""
    try:
        print("🏒 Starting Puck Dynasty...")
        
        # Use direct launch for reliability
        print("🚀 Using direct launch method...")
        _direct_launch()
            
    except KeyboardInterrupt:
        print("🛑 Interrupted by user")
        
    except Exception as e:
        import traceback
        print("❌ Critical error launching Hockey Manager:", e)
        traceback.print_exc()
        try:
            from tkinter import messagebox
            messagebox.showerror("Critical Launch Error", f"Failed to start Hockey Manager:\\n{str(e)}")
        except:
            pass'''
    
    new_main = '''def main():
    """Main function to start the game with splash launcher"""
    try:
        print("🏒 Starting Puck Dynasty...")
        
        # Import and launch splash screen first
        try:
            from splash_launcher import SplashLauncher
            print("🎨 Launching splash screen...")
            splash = SplashLauncher()
            splash.mainloop()
            print("✅ Application completed")
            
        except ImportError as e:
            print(f"⚠️ Splash launcher not available: {e}")
            print("🔄 Falling back to direct launch...")
            _direct_launch()
            
        except Exception as e:
            print(f"❌ Splash launcher error: {e}")
            import traceback
            traceback.print_exc()
            print("🔄 Falling back to direct launch...")
            _direct_launch()
            
    except KeyboardInterrupt:
        print("🛑 Interrupted by user")
        
    except Exception as e:
        import traceback
        print("❌ Critical error launching Hockey Manager:", e)
        traceback.print_exc()
        try:
            from tkinter import messagebox
            messagebox.showerror("Critical Launch Error", f"Failed to start Hockey Manager:\\n{str(e)}")
        except:
            pass'''
    
    if old_main in content:
        print("✅ Found main() function - applying patch...")
        content = content.replace(old_main, new_main)
        
        # Write back
        with open('main.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Patch applied successfully!")
        print("Now run: python main.py")
        return True
    else:
        print("❌ Could not find exact match for main() function")
        print("The function may have already been patched or has different formatting")
        return False

if __name__ == "__main__":
    import os
    os.chdir(r"C:\Users\caleb\OneDrive\Desktop\HOCKEY MANAGER")
    patch_main_py()
