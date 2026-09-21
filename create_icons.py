import os
from PIL import Image, ImageDraw

def create_player_icon(color='#3498db', size=30, filename='player_icon.png'):
    """Create a circular player icon and save as PNG"""
    # Create a new image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Parse the hex color to RGB
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    
    # Draw a filled circle
    draw.ellipse((0, 0, size-1, size-1), fill=(r, g, b, 255))
    
    # Save the image
    img.save(filename)
    print(f"Created {filename}")

def create_goalie_icon(color='#e74c3c', size=30, filename='goalie_icon.png'):
    """Create a circular goalie icon and save as PNG"""
    # Create a new image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Parse the hex color to RGB
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    
    # Draw a filled circle
    draw.ellipse((0, 0, size-1, size-1), fill=(r, g, b, 255))
    
    # Save the image
    img.save(filename)
    print(f"Created {filename}")

if __name__ == "__main__":
    # Create player icon (blue)
    create_player_icon('#3498db', 30, 'player_icon.png')
    
    # Create goalie icon (red)
    create_goalie_icon('#e74c3c', 30, 'goalie_icon.png')
    
    print("Icons created successfully!")
