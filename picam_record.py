# modified from: https://picamera.readthedocs.io/en/release-1.2/recipes2.html#splitting-to-from-a-circular-stream
# Output needs to be entered into ffmpeg -
#   example: ffmpeg -framerate 15 -i "concat:1535935485_before.h264|1535935485_after.h264" 1535935485.mp4

import io
import os
from time import time

from picamera import PiCameraCircularIO

is_recording = False


def init(before_detection=5, timeout=5, max_length=30):
    global record_time_before_detection, no_detection_timeout, max_recording_length
    record_time_before_detection = before_detection
    no_detection_timeout = timeout
    max_recording_length = max_length


# Start recording
def start(cam):

    # setup globals
    global camera, stream
    camera = cam

    stream = PiCameraCircularIO(camera, seconds=record_time_before_detection)
    camera.start_recording(stream, format='h264')

    camera.wait_recording(5)  # make sure recording is loaded
    print("recording initialized")


def write_video(stream, file):
    # Write the entire content of the circular buffer to disk. No need to
    # lock the stream here as we're definitely not writing to it
    # simultaneously
    with io.open(file, 'wb') as output:
        for frame in stream.frames:
            if frame.header:
                stream.seek(frame.position)
                break
        while True:
            buf = stream.read1()
            if not buf:
                break
            output.write(buf)

        print("wrote %s" % file)
    # Wipe the circular stream once we're done
    stream.seek(0)
    stream.truncate()


before_file = "error.h264"
after_file = "error.h264"


def detection(detected):
    # Recording
    global is_recording, recording_start_time, last_detection_time, before_file, after_file


    now = time()

    if detected:
        if not is_recording:
            print("Detection started")
            is_recording = True
            recording_start_time = int(now)
            before_file = (os.path.join('./recordings', '%d_before.h264' % recording_start_time))
            after_file = (os.path.join('./recordings', '%d_after.h264' % recording_start_time))
            # start recording frames after the initial detection
            camera.split_recording(after_file)
            # Write the 10 seconds "before" detection
            write_video(stream, before_file)

        # write to disk if max recording length exceeded
        elif int(now) - recording_start_time > max_recording_length - record_time_before_detection:
            print("Max recording length reached. Writing %s" % after_file)
            # Split here: write to after_file, and start capturing to the stream again
            camera.split_recording(stream)
            is_recording = False

        last_detection_time = now
    else:
        if is_recording and int(now)-last_detection_time > no_detection_timeout:
            print("No more detections, writing %s" % after_file)
            # Split here: write to after_file, and start capturing to the stream again
            camera.split_recording(stream)
            is_recording = False
