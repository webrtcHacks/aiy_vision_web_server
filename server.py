# Copyright (c) 2018 Chad Wallace Hart
# Attribution notice:
#   Large portions of this code are from https://github.com/google/aiyprojects-raspbian
#   Copyright 2017 Google Inc.
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Walkthough and function details https://webrtchacks.com/aiy-vision-kit-uv4l-web-server/
# Source repo: https://github.com/webrtcHacks/aiy_vision_web_server

from threading import Thread, Event     # Multi-threading
import queue                            # Multi-threading
from time import time, sleep
from datetime import datetime           # Timing & stats output
import socket                           # uv4l communication
import os                               # help with connecting to the socket file
import argparse                         # Commandline arguments
import random                           # Used for performance testing

from picamera import PiCamera           # PiCam hardware
from flask import Flask, Response       # Web server

from aiy_model_output import model_selector, process_inference
import picam_record as record

# AIY requirements
from aiy.leds import Leds
from aiy.leds import PrivacyLed
from aiy.vision.inference import CameraInference, ImageInference


socket_connected = False
q = queue.Queue(maxsize=1)  # we'll use this for inter-process communication
# ToDo: remove these
# capture_width = 1640        # The max horizontal resolution of PiCam v2
# capture_height = 922        # Max vertical resolution on PiCam v2 with a 16:9 ratio
time_log = []


# Control connection to the linux socket and send messages to it
def socket_data(run_event, send_rate=1/30):
    socket_path = '/tmp/uv4l-raspidisp.socket'

    # wait for a connection
    def wait_to_connect():
        global socket_connected

        print('socket waiting for connection...')
        while run_event.is_set():
            try:
                socket_connected = False
                connection, client_address = s.accept()
                print('socket connected')
                socket_connected = True
                send_data(connection)

            except socket.timeout:
                continue

            except socket.error as err:
                print("socket error: %s" % err)
                break

        print("closing socket")
        s.close()
        socket_connected = False

    # continually send data as it comes in from the q
    def send_data(connection):
        while run_event.is_set():
            try:
                if q.qsize() > 0:
                    message = q.get()
                    connection.send(str(message).encode())

                sleep(send_rate)
            except socket.error as send_err:
                print("connected socket error: %s" % send_err)
                return

    try:
        # Create the socket file if it does not exist
        if not os.path.exists(socket_path):
            f = open(socket_path, 'w')
            f.close()

        os.unlink(socket_path)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        s.bind(socket_path)
        s.listen(1)
        s.settimeout(1)
        wait_to_connect()
    except socket.error as sock_err:
        print("socket error: %s" % sock_err)
        return
    except OSError:
        if os.path.exists(socket_path):
            print("Error accessing %s\nTry running 'sudo chown pi: %s'" % (socket_path, socket_path))
            os._exit(0)
            return
        else:
            print("Socket file not found. Did you configure uv4l-raspidisp to use %s?" % socket_path)
            raise


# AIY Vision setup and inference
def run_inference(run_event, model="face", framerate=15, cam_mode=5, hres=1640, vres=922, stats=False, recording=False):
    # See the Raspicam documentation for mode and framerate limits:
    # https://picamera.readthedocs.io/en/release-1.13/fov.html#sensor-modes
    # Default to the highest resolution possible at 16:9 aspect ratio

    global socket_connected, time_log

    leds = Leds()

    with PiCamera() as camera, PrivacyLed(leds):
        camera.sensor_mode = cam_mode
        camera.resolution = (hres, vres)
        camera.framerate = framerate
        camera.video_stabilization = True
        camera.start_preview()  # fullscreen=True)

        tf_model = model_selector(model)

        # this is not needed because the function defaults to "face"
        if tf_model == "nothing":
            print("No tensorflow model or invalid model specified - exiting..")
            camera.stop_preview()
            os._exit(0)
            return

        if recording:
            record.start(camera)

        try:
            with CameraInference(tf_model) as inference:
                print("%s model loaded" % model)

                last_time = time()  # measure inference time

                for result in inference.run():

                    # exit on shutdown
                    if not run_event.is_set():
                        camera.stop_preview()
                        return

                    output = process_inference(model, result, {'height':vres , 'width': hres})

                    now = time()
                    output.timeStamp = now
                    output.inferenceTime = (now - last_time)
                    last_time = now

                    # Process detection
                    # No need to do anything else if there are no objects
                    if output.numObjects > 0:

                        # API Output
                        output_json = output.to_json()
                        print(output_json)

                        # Send the json object if there is a socket connection
                        if socket_connected is True:
                            q.put(output_json)

                    if recording:
                        record.detection(output.numObjects > 0)

                    # Additional data to measure inference time
                    if stats:
                        time_log.append(output.inferenceTime)
                        time_log = time_log[-10:]  # just keep the last 10 times
                        print("Avg inference time: %s" % (sum(time_log)/len(time_log)))
        finally:
            camera.stop_preview()
            if recording:
                camera.stop_recording()

# Web server setup
app = Flask(__name__)


def flask_server():
    app.run(debug=False, host='0.0.0.0', threaded=True)  # use_reloader=False


@app.route('/')
def index():
    return Response(open('static/index.html').read(), mimetype="text/html")

# Note: This won't be able to play the files without conversion.
# Running ffmpeg while running inference & streaming will be too intensive for the Pi Zeros
# Look to make this a user controlled process or do it in the browser
@app.route('/recordings')
def recordings():
    # before_list = glob(os.getcwd() +  '/recordings/*_before.h264')
    # after_list = glob(os.getcwd() + '/recordings/*_after.h264')

    # print(before_list)
    # print(after_list)

    files = [f for f in os.listdir('./recordings') if f.endswith(".h264")]
    files.sort()
    print(files)

    html_table = "<table><tr><th>Before Detection</th><th>After Detection</th></tr>"
    # for i in range(len(before_list)):
    #    html_table = html_table + "<tr><td>" + before_list[i] + "</td><td>" + after_list[i] + "</tr>"

    html_table = html_table + "</table>"
    print(html_table)
    page = "<HTML><TITLE>List of Recordings</TITLE><BODY><h2>The list goes here</h2>%s</BODY></HTML>" % html_table
    print(page)
    return Response(page)


# test route to verify the flask is working
@app.route('/ping')
def ping():
    return Response("pong")


@app.route('/socket-test')
def socket_test():
    return Response(open('static/socket-test.html').read(), mimetype="text/html")

'''
def socket_tester(rate):
    output = ApiObject()
    last_time = False
    count = 0

    while True:
        if socket_connected is True:
            count += 1
            current_time = time()
            output.time = (datetime.utcnow()-datetime.utcfromtimestamp(0)).total_seconds()*1000
            output.data = ''.join(random.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(1000))
            output.count = count
            q.put(output.to_json())
            print("count, timestamp, delta:     %s    %s    %s" % (output.count, current_time, current_time - last_time))
            last_time = current_time

        sleep(rate)
'''


# Main control logic to parse args and spawn threads
def main(webserver):

    # Command line parameters to help with testing and optimization
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--model',
        '-m',
        dest='model',
        default='face',
        help='Sets the model to use: "face", "object", or "class"')
    parser.add_argument(
        '--cam-mode',
        '-c',
        type=int,
        dest='cam_mode',
        default=5,
        help='Sets the camera mode. Default is 5')
    parser.add_argument(
        '--framerate',
        '-f',
        type=int,
        dest='framerate',
        default=15,
        help='Sets the camera framerate. Default is 15')
    parser.add_argument(
        '--hres',
        '-hr',
        type=int,
        dest='hres',
        default=1640,
        help='Sets the horizontal resolution')
    parser.add_argument(
        '--vres',
        '-vr',
        type=int,
        dest='vres',
        default=922,
        help='Sets the vertical resolution')
    parser.add_argument(
        '--stats',
        '-s',
        action='store_true',
        help='Show average inference timing statistics')
    parser.add_argument(
        '--perftest',
        '-t',
        dest='perftest',
        action='store_true',
        help='Start socket performance test')
    parser.add_argument(
        '--record',
        '-r',
        dest='record',
        action='store_true',
        help='Record')
    # ToDo: Add recorder parameters
    parser.epilog = 'For more info see the github repo: https://github.com/webrtcHacks/aiy_vision_web_server/' \
                    ' or the webrtcHacks blog post: https://webrtchacks.com/?p=2824'
    args = parser.parse_args()

    is_running = Event()
    is_running.set()

    '''
    if args.perftest:
        print("Socket performance test mode")

        # run this independent of a flask connection so we can test it with the uv4l console
        socket_thread = Thread(target=socket_data, args=(is_running, 1/1000,))
        socket_thread.start()

        socket_test_thread = Thread(target=socket_tester,
                              args=(0.250,))
        socket_test_thread.start()

    else:
    '''

    if args.record:
        record.init(before_detection=5, timeout=5, max_length=30)

    # run this independent of a flask connection so we can test it with the uv4l console
    socket_thread = Thread(target=socket_data, args=(is_running, 1 / args.framerate,))
    socket_thread.start()

    # thread for running AIY Tensorflow inference
    detection_thread = Thread(target=run_inference,
                              args=(is_running, args.model, args.framerate, args.cam_mode,
                                    args.hres, args.vres, args.stats, args.record))
    detection_thread.start()

    # run Flask in the main thread
    webserver.run(debug=False, host='0.0.0.0')

    # close threads when flask is done
    print("exiting...")
    is_running.clear()
    '''
    if args.perftest:
        socket_test_thread.join(0)
    else:
        detection_thread.join(0)
    '''
    socket_thread.join(0)


if __name__ == '__main__':
    main(app)
