import sys
import os

# Load a cool font
font = font.absolute

def update():
    # Clear the screen with black background
    screen.pen = color.rgb(0, 0, 0)
    screen.shape(shape.rectangle(0, 0, 160, 120))
    
    # Set up white text
    screen.pen = color.rgb(255, 255, 255)
    screen.font = font
    
    # Draw "hello world" centered on screen
    text = "hello world"
    w, h = screen.measure_text(text)
    screen.text(text, 80 - (w / 2), 60 - (h / 2))
    
    return None

run(update)
