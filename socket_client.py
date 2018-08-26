import socket
import os
from time import time, sleep

socket_path = '/tmp/uv4l-raspidisp.socket'


def print_socket():

    # wait for a connection
    def wait_to_connect():

        print('connecting...')
        while True:
            try:
                connection, client_address = s.accept()
                print('socket connected')

                data = connection.recv(64)
                if len(data) > 0:
                    print(data)
                    break

                sleep(0.001)

            except socket.timeout:
                print("timeout..")
                continue

            except socket.error as err:
                print("socket error: %s" % err)
                raise

        print("closing socket")
        s.close()

    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        s.connect(socket_path)

        while True:
            data = s.recv(64)
            print(repr(data))
            sleep(0.001)


    except OSError:
            raise
    except socket.error as sock_err:
        print("socket error: %s" % sock_err)
        return
    except:
        print("closing..")
        s.close()
        raise


if __name__ == '__main__':
    print_socket()
