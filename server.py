# Copyright (c) 2018 Chad Wallace Hart
# Attribution notice:
#   Large portions of this code are from https://github.com/google/aiyprojects-raspbian
#   Copyright 2017 Google Inc.
#   http://www.apache.org/licenses/LICENSE-2.0

from threading import Thread, Event
from time import time, sleep
import socket
import os
import json
import queue
import argparse

from aiy.vision.leds import Leds
from aiy.vision.leds import PrivacyLed
from aiy.vision.inference import CameraInference, ImageInference
from aiy.vision.models import object_detection, face_detection, image_classification
from picamera import PiCamera

from flask import Flask, Response

socket_connected = False
q = queue.Queue(maxsize=1)  # we'll use this for inter-process communication
capture_width = 1640        # The max horizontal resolution of PiCam v2
capture_height = 922        # Max vertical resolution on PiCam v2 with a 16:9 ratio
time_log = []


# Control connection to the linux socket and send messages to it
def socket_data(run_event, send_rate):
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
    except OSError:
        if os.path.exists(socket_path):
            print("Error accessing %s\nTry running 'sudo chown pi: %s'" % (socket_path, socket_path))
            os._exit(0)
            return
        else:
            print("Socket file not found. Did you configure uv4l-raspidisp to use %s?" % socket_path)
            raise
    except socket.error as sock_err:
        print("socket error: %s" % sock_err)
        return
    except:
        raise


# helper class to convert inference output to JSON
class ApiObject(object):
    def __init__(self):
        self.name = "webrtcHacks AIY Vision Server REST API"
        self.version = "0.2.0"
        self.numObjects = 0
        self.objects = []

    def to_json(self):
        return json.dumps(self.__dict__)


# AIY Vision setup and inference
def run_inference(run_event, model="face", framerate=15, cammode=5, hres=1640, vres=922, stats=True):
    # See the Raspicam documentation for mode and framerate limits:
    # https://picamera.readthedocs.io/en/release-1.13/fov.html#sensor-modes
    # Default to the highest resolution possible at 16:9 aspect ratio

    global socket_connected, time_log

    leds = Leds()

    with PiCamera() as camera, PrivacyLed(leds):
        camera.sensor_mode = cammode
        camera.resolution = (hres, vres)
        camera.framerate = framerate
        camera.video_stabilization = True
        camera.start_preview()  # fullscreen=True)

        def model_selector(argument):
            options = {
                "object": object_detection.model(),
                "face": face_detection.model(),
                "class": image_classification.model()
            }
            return options.get(argument, "nothing")

        tf_model = model_selector(model)

        # this is not needed because the function defaults to "face"
        if tf_model == "nothing":
            print("No tensorflow model or invalid model specified - exiting..")
            camera.stop_preview()
            os._exit(0)
            return

        with CameraInference(tf_model) as inference:
            print("%s model loaded" % model)

            last_time = time()  # measure inference time

            for result in inference.run():

                # exit on shutdown
                if not run_event.is_set():
                    camera.stop_preview()
                    return

                output = ApiObject()

                # handler for the AIY Vision object detection model
                if model == "object":
                    output.threshold = 0.3
                    objects = object_detection.get_objects(result, output.threshold)

                    for obj in objects:
                        # print(object)
                        item = {
                            'name': 'object',
                            'class_name': obj._LABELS[obj.kind],
                            'score': obj.score,
                            'x': obj.bounding_box[0] / capture_width,
                            'y': obj.bounding_box[1] / capture_height,
                            'width': obj.bounding_box[2] / capture_width,
                            'height': obj.bounding_box[3] / capture_height
                        }

                        output.numObjects += 1
                        output.objects.append(item)

                # handler for the AIY Vision face detection model
                elif model == "face":
                    faces = face_detection.get_faces(result)

                    for face in faces:
                        # print(face)
                        item = {
                            'name': 'face',
                            'score': face.face_score,
                            'joy': face.joy_score,
                            'x': face.bounding_box[0] / capture_width,
                            'y': face.bounding_box[1] / capture_height,
                            'width': face.bounding_box[2] / capture_width,
                            'height': face.bounding_box[3] / capture_height,
                        }

                        output.numObjects += 1
                        output.objects.append(item)

                elif model == "class":
                    output.threshold = 0.3
                    classes = image_classification.get_classes(result)

                    s = ""

                    for (obj, prob) in classes:
                        if prob > output.threshold:
                            s += '%s=%1.2f\t|\t' % (obj, prob)

                            item = {
                                'name': 'class',
                                'class_name': obj,
                                'score': prob
                            }

                            output.numObjects += 1
                            output.objects.append(item)

                    # print('%s\r' % s)

                now = time()
                output.timeStamp = now
                output.inferenceTime = (now - last_time)
                last_time = now

                # No need to do anything else if there are no objects
                if output.numObjects > 0:
                    output_json = output.to_json()
                    print(output_json)

                    # Send the json object if there is a socket connection
                    if socket_connected is True:
                        q.put(output_json)

                # Additional data to measure inference time
                if stats is True:
                    time_log.append(output.inferenceTime)
                    time_log = time_log[-10:]  # just keep the last 10 times
                    print("Avg inference time: %s" % (sum(time_log)/len(time_log)))


# Web server setup
app = Flask(__name__)


def flask_server():
    app.run(debug=False, host='0.0.0.0', threaded=True)  # use_reloader=False


@app.route('/')
def index():
    return Response(open('static/index.html').read(), mimetype="text/html")


# test route to verify the flask is working
@app.route('/ping')
def ping():
    return Response("pong")


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
    parser.epilog = 'For more info see the github repo: https://github.com/webrtcHacks/aiy_vision_web_server/' \
                    ' or the webrtcHacks blog post: https://webrtchacks.com/?p=2824'
    args = parser.parse_args()

    is_running = Event()
    is_running.set()

    # run this independent of a flask connection so we can test it with the uv4l console
    socket_thread = Thread(target=socket_data, args=(is_running, 1 / args.framerate,))
    socket_thread.start()

    # thread for running AIY Tensorflow inference
    detection_thread = Thread(target=run_inference,
                              args=(is_running, args.model, args.framerate, args.cam_mode,
                                    args.hres, args.vres, args.stats, ))
    detection_thread.start()

    # run Flask in the main thread
    webserver.run(debug=False, host='0.0.0.0')

    # close threads when flask is done
    print("exiting...")
    is_running.clear()
    detection_thread.join(0)
    socket_thread.join(0)


if __name__ == '__main__':
    main(app)
