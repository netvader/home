import sys
import os

sys.path.insert(0, "/system/apps/copilot-loop")
os.chdir("/system/apps/copilot-loop")



frame_index = 1
last_frame_time = 0
FRAME_DURATION = 33  # ~1/30th of a second in milliseconds (33.33ms)
LAST_FRAME_PAUSE = 10000  # 10 seconds in milliseconds
TOTAL_FRAMES = 39

def update():
    global frame_index, last_frame_time
    
    is_last_frame = (frame_index == TOTAL_FRAMES)
    pause_duration = LAST_FRAME_PAUSE if is_last_frame else FRAME_DURATION
    
    # Update frame with appropriate timing
    if badge.ticks - last_frame_time >= pause_duration:
        frame_index = (frame_index % TOTAL_FRAMES) + 1
        last_frame_time = badge.ticks
        
    # Draw the current frame
    screen.blit(image.load(f"frames/frame_{frame_index:04d}.png"), 0, 0)
    
run(update)
