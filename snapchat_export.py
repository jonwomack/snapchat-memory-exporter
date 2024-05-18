import argparse
import os
import cv2
import logging
import shutil
from bs4 import BeautifulSoup
from datetime import datetime
from moviepy.editor import VideoFileClip
from tqdm import tqdm
from PIL import Image

# Suppress moviepy logs
logging.getLogger("moviepy").setLevel(logging.CRITICAL)

# Define the default output folder
output_folder = "./output"

def set_output_date(output_path, date):
    # Get the timestamp from the date
    timestamp = datetime.strptime(date, "%Y-%m-%d")

    # Set the timestamp of the image to the extracted timestamp
    os.utime(output_path, (timestamp.timestamp(), timestamp.timestamp()))

def extract_date_from_media_file_path(file_path):
    # Get the filename from the file path
    filename = os.path.basename(file_path)
    
    # Extract the first 10 characters
    date = filename[:10]

    return date

def combine_video_with_overlay(video_path, overlay_image_path):
    # Open the video
    video_capture = cv2.VideoCapture(video_path)

    # Open the overlay image
    overlay_image = cv2.imread(overlay_image_path)
    overlay_image_height, overlay_image_width, _ = overlay_image.shape

    # Get video properties
    frame_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = video_capture.get(cv2.CAP_PROP_FPS)
    total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))

    # Create a VideoWriter object to write the combined video
    date = extract_date_from_media_file_path(video_path)
    output_video_path = os.path.join(output_folder, os.path.basename(video_path))
    fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264 codec
    video_writer = cv2.VideoWriter(output_video_path, fourcc, fps, (frame_width, frame_height))

    # Loop through each frame of the video
    for frame_number in range(total_frames):
        ret, frame = video_capture.read()
        if not ret:
            break

        # Resize overlay image to match frame size
        resized_overlay_image = cv2.resize(overlay_image, (frame_width, frame_height))

        # Overlay the image onto the frame
        combined_frame = cv2.addWeighted(frame, 1, resized_overlay_image, 0.5, 0)

        # Write the combined frame to the output video
        video_writer.write(combined_frame)

    # Release video capture and writer objects
    video_capture.release()
    video_writer.release()

    # Add audio from original video to video with overlay
    original_video = VideoFileClip(video_path)
    audio = original_video.audio
    video_with_overlay = VideoFileClip(output_video_path)
    video_with_overlay_and_audio = video_with_overlay.set_audio(audio)    

    # Save the resulting video to a temporary file, then move to the output_video_path
    video_with_overlay_and_audio.write_videofile(output_video_path.replace(".mp4", "-tmp.mp4"), codec="libx264", audio_codec="aac")
    os.rename(output_video_path.replace(".mp4", "-tmp.mp4"), output_video_path)

    set_output_date(output_video_path, date)

def combine_image_with_overlay(image_path, overlay_image_path):
    main_image = Image.open(image_path)

    if overlay_image_path:
        overlay_image = Image.open(overlay_image_path)
        overlay_image = overlay_image.resize(main_image.size)
        main_image.paste(overlay_image, (0, 0), overlay_image)

    date = extract_date_from_media_file_path(image_path)
    output_path = os.path.join(output_folder, os.path.basename(image_path))
    main_image.save(output_path)
    set_output_date(output_path, date)

def parse_memories(folder_path):
                
    overlay_paths_and_folder = []
    main_media_paths_and_folder = []

    # Loop over each memory file in the folder
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file == "memories.html":
                memory_file_path = os.path.join(root, file)

                with open(memory_file_path, "r") as f:
                    html_content = f.read()

                soup = BeautifulSoup(html_content, "html.parser")

                # Find all <div> tags for images
                divs = soup.find_all("div", class_="image-container")

                # Note: media and overlay may exist in separate memories.html files, 
                # which is why I've stored them in a global (across folders e.g. mydata/, mydata-2/,mydata-3/, ...) list
                for div in divs:
                    if ".png" in str(div):
                        if len(div.find_all()) == 4:
                            overlay_paths_and_folder.append((div.find("img", class_="overlay-image")["src"], root))
                        else:
                            overlay_paths_and_folder.append((div.img["src"], root))

                    if ".mp4" in str(div):
                        video_src = div.video["src"]
                        main_media_paths_and_folder.append((video_src, root))

                    if ".jpg" in str(div):
                        img_src = div.img["src"]
                        main_media_paths_and_folder.append((img_src, root))

    # Save all the images, combining overlays when necessary.
    progress_bar = tqdm(total=len(main_media_paths_and_folder), desc="Exporting snapchat memories", unit="media")

    for main_media_path, folder in main_media_paths_and_folder:
        main_media_identifier = main_media_path.replace(".//", "").rsplit("-", 1)[0]
        main_media_path = os.path.join(folder, main_media_path.replace(".//", ""))

        # Check if there is an overlay for this media
        overlay_image_path = None
        for overlay_path, overlay_folder in overlay_paths_and_folder:
            if main_media_identifier in overlay_path:
                overlay_image_path = os.path.join(overlay_folder, overlay_path.replace(".//", ""))
                break

        # Combine the media with the overlay
        if "mp4" in main_media_path:
            if overlay_image_path is None:
                output_video_path = os.path.join(output_folder, os.path.basename(main_media_path))
                shutil.copy(main_media_path, output_video_path)
                date = extract_date_from_media_file_path(main_media_path)
                set_output_date(output_video_path, date)
            else:
                combine_video_with_overlay(main_media_path, overlay_image_path)

        if "jpg" in main_media_path:
            combine_image_with_overlay(main_media_path, overlay_image_path)

        progress_bar.update(1)
    progress_bar.close()

def main():
    global output_folder 

    parser = argparse.ArgumentParser(description="Parse memories HTML files")
    parser.add_argument("folder_path", help="Path to the folder containing memories HTML files")
    parser.add_argument("--output_folder", help="Path to the output folder (default: ./output)")
    args = parser.parse_args()

    if args.output_folder:
        output_folder = args.output_folder

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    parse_memories(args.folder_path)

if __name__ == "__main__":
    main()