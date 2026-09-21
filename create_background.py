"""
Create a simple hockey-themed background image for testing
This script creates a basic background if PIL is available
"""

try:
    from PIL import Image, ImageDraw, ImageFont
    
    def create_sample_background():
        """Create a simple hockey rink background"""
        # Create image
        width, height = 1000, 700
        img = Image.new('RGB', (width, height), color='#0B2F5C')  # Hockey blue
        draw = ImageDraw.Draw(img)
        
        # Draw center ice circle
        center_x, center_y = width // 2, height // 2
        circle_radius = 80
        draw.ellipse([center_x - circle_radius, center_y - circle_radius,
                     center_x + circle_radius, center_y + circle_radius], 
                     outline='white', width=3)
        
        # Draw center line
        draw.line([center_x, 0, center_x, height], fill='red', width=4)
        
        # Draw goal lines
        goal_line_1 = width // 4
        goal_line_2 = 3 * width // 4
        draw.line([goal_line_1, 0, goal_line_1, height], fill='red', width=2)
        draw.line([goal_line_2, 0, goal_line_2, height], fill='red', width=2)
        
        # Draw face-off circles
        faceoff_radius = 50
        faceoff_y = height // 2
        
        # Left faceoff circle
        draw.ellipse([goal_line_1 - faceoff_radius, faceoff_y - faceoff_radius,
                     goal_line_1 + faceoff_radius, faceoff_y + faceoff_radius], 
                     outline='blue', width=2)
        
        # Right faceoff circle
        draw.ellipse([goal_line_2 - faceoff_radius, faceoff_y - faceoff_radius,
                     goal_line_2 + faceoff_radius, faceoff_y + faceoff_radius], 
                     outline='blue', width=2)
        
        # Add some text overlay areas (darker for text readability)
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 120))
        img = Image.alpha_composite(img.convert('RGBA'), overlay)
        
        # Save the image
        img.save('hockey_bg.png')
        print("Created hockey_bg.png background image")
        
    create_sample_background()
    
except ImportError:
    print("PIL not available - cannot create background image")
    print("Install Pillow with: pip install Pillow")
