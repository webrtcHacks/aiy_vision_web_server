import socket
import queue
import os
import json
import random
from datetime import datetime
from time import time, sleep
from threading import Thread

socket_connected = False
end = False
q = queue.Queue(maxsize=1)  # we'll use this for inter-process communication


# Control connection to the linux socket and send messages to it
def socket_data(send_rate=1/30):
    socket_path = '/tmp/uv4l-raspidisp.socket'

    # wait for a connection
    def wait_for_client():
        global socket_connected, end

        print('socket waiting for connection...')
        while True:
            try:
                socket_connected = False
                connection, client_address = s.accept()
                print('socket connected')
                socket_connected = True
                send_data(connection)

                if end:
                    return

            except socket.timeout:
                continue

            except socket.error as err:
                print("socket error: %s" % err)
                break

            except KeyboardInterrupt:
                return

        print("closing socket")
        s.close()
        socket_connected = False

    # continually send data as it comes in from the q
    def send_data(connection):
        while True:
            try:
                if q.qsize() > 0:
                    message = q.get()
                    connection.send(str(message).encode())
                if end:
                    return
                sleep(send_rate)

            except socket.error as send_err:
                print("connected socket error: %s" % send_err)
                return
            except KeyboardInterrupt:
                return

    try:
        # Create the socket file if it does not exist
        if not os.path.exists(socket_path):
            f = open(socket_path, 'w')
            f.close()

        os.remove(socket_path)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        s.bind(socket_path)
        s.listen(1)
        s.settimeout(1)
        wait_for_client()
    except OSError:
        if os.path.exists(socket_path):
            print("Error accessing %s\nTry running 'sudo chown pi: %s'" % (socket_path, socket_path))
            os._exit(0)
            return
        else:
            pass
    except socket.error as sock_err:
        print("socket error: %s" % sock_err)
        return


# helper class to convert inference output to JSON
class ApiObject(object):
    def __init__(self):
        self.name = "socket test"
        self.version = "0.0.1"
        self.numObjects = 0

    def to_json(self):
        return json.dumps(self.__dict__)


def socket_tester(rate):
    output = ApiObject()
    last_time = False
    count = 0

    try:
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
    except KeyboardInterrupt:
        return


def main():
    global end
    socket_thread = Thread(target=socket_data, args=(1 / 1000,))
    socket_thread.start()

    socket_tester(1/15)

    # ToDo: figure out why this does not close cleanly
    end = True
    print("Exiting..")
    socket_thread.join(0)


if __name__ == '__main__':
    main()