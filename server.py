from threading import Thread, Event
from time import time, sleep
import socket
import os
import json
import queue
import argparse

from aiy._drivers._rgbled import PrivacyLED
from aiy.vision.inference import CameraInference
from aiy.vision.models import object_detection, face_detection
from picamera import PiCamera

from flask import Flask, Response

socket_connected = False
q = queue.Queue(maxsize=1)  # we'll use this for inter-process communication
capture_width = 1640        # The max horizontal resolution of PiCam v2
capture_height = 922        # Max vertical resolution on PiCam v2 with a 16:9 ratio


# Control connection to the linux socket and send messages to it
def socket_data(run_event, send_rate):
    socket_path = '/tmp/uv4l-raspidisp.socket'
    global socket_connected

    try:
        os.unlink(socket_path)
    except OSError:
        if os.path.exists(socket_path):
            raise

    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as s:
        s.bind(socket_path)
        s.listen(1)
        s.settimeout(1)

        print('socket waiting for connection...')

        while run_event.is_set():
            try:
                connection, client_address = s.accept()  # ToDo: findout why the client_address doesn't populate

                print('socket connected')
                socket_connected = True

                # ToDo: this does not exit cleanly if we don't get to this point

                while run_event.is_set():

                    if q.qsize() > 0:
                        message = q.get()
                        connection.send(str(message).encode())

                    sleep(send_rate)

            # break the inner loop on polling timeout and start over
            except socket.timeout:
                print("socket timeout")
                sleep(1)
                continue

            # On error assume the far end detached and start over
            except socket.error as err:
                print("socket error: %s" % err)
                socket_connected = False
                s.detach()
                s.bind(socket_path)
                print('Detached. Socket waiting for new connection...')
                continue

        socket_connected = False
        s.detach()
        return


# added to put object in JSON
class Object(object):
    def __init__(self):
        self.name = "webrtcHacks AIY Vision Server REST API"

    def to_json(self):
        return json.dumps(self.__dict__)


# AIY Vision setup and inference
def run_inference(run_event, model="face", framerate=15, cammode=5, hres=1640, vres=922):

    global socket_connected

    with PiCamera() as camera, PrivacyLED():
        camera.sensor_mode = cammode
        camera.resolution = (hres, vres)
        camera.framerate = framerate
        camera.start_preview(fullscreen=True)

        if model == "object":
            tf_model = object_detection.model()
        elif model == "face":
            tf_model = face_detection.model()
        else:
            print("No model or invalid model specified - exiting..")
            camera.stop_preview()
            os._exit(0)
            return

        with CameraInference(tf_model) as inference:
            print("%s model loaded" % model)

            last_time = time()  # measure inference time
            time_log = []

            for i, result in enumerate(inference.run()):

                # exit on shutdown
                if not run_event.is_set():
                    camera.stop_preview()
                    return

                output = Object()
                output.objects = []
                output.version = "0.0.1"
                output.numObjects = 0

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
                        '''
                        item['name'] = 'object'
                        item['class_name'] = obj._LABELS[obj.kind]
                        item['score'] = obj.score
                        item['x'] = obj.bounding_box[0] / capture_width
                        item['y'] = obj.bounding_box[1] / capture_height
                        item['width'] = obj.bounding_box[2] / capture_width
                        item['height'] = obj.bounding_box[3] / capture_height
                        '''

                        output.numObjects += 1
                        output.objects.append(item)

                # handler for the AIY Vision face detection model
                elif model == "face":
                    faces = face_detection.get_faces(result)

                    for face in faces:
                        print(face)
                        item = {
                            'name': 'face',
                            'score': face.face_score,
                            'joy': face.joy_score,
                            'x': face.bounding_box[0] / capture_width,
                            'y': face.bounding_box[1] / capture_height,
                            'width': face.bounding_box[2] / capture_width,
                            'height': face.bounding_box[3] / capture_height,
                        }
                        '''
                        item['name'] = 'face'
                        item['score'] = face.face_score
                        item['joy'] = face.joy_score

                        # convert to percentages
                        item['x'] = face.bounding_box[0] / capture_width
                        item['y'] = face.bounding_box[1] / capture_height
                        item['width'] = face.bounding_box[2] / capture_width
                        item['height'] = face.bounding_box[3] / capture_height
                        '''

                        output.numObjects += 1
                        output.objects.append(item)

                now = time()
                output.inferenceTime = (now - last_time)
                last_time = now

                # No need to do anything else if there are no objects
                if output.numObjects > 0:
                    output_json = output.to_json()
                    print(output_json)

                    # Send the json object if there is a socket connection
                    if socket_connected is True:
                        q.put(output_json)

                # Just for tests to improve inference time / CPU usage
                # time_log.append(output.inferenceTime)
                # print("Avg inference time: %s" % (sum(time_log)/len(time_log)))


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

    # Command line parameters to help with testing
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--model',
        '-m',
        dest='model',
        default='face',
        help='Sets the model to use: "face" or "object" ')
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
    args = parser.parse_args()

    is_running = Event()
    is_running.set()

    # run this ahead of a flask connection so we can test it with the uv4l console
    socket_thread = Thread(target=socket_data, args=(is_running, 1 / args.framerate,))
    socket_thread.start()

    detection_thread = Thread(target=run_inference,
                              args=(is_running, args.model, args.framerate, args.cam_mode, args.hres, args.vres,))
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
