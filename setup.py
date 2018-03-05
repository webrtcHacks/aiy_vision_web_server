from setuptools import find_packages
from setuptools import setup
import subprocess

socket_path = '/tmp/uv4l-raspidisp.socket'

REQUIRED_PACKAGES = ['Flask', 'argparse', 'picamera']

setup(
    name='aiy_vision_web_server',
    version='0.1',
    install_requires=REQUIRED_PACKAGES,
    include_package_data=True,
    packages=[p for p in find_packages()],
    description='AIY Vision Web Server',
)

# Change the owner on the UV4L socket file

try:
    print("Disabling uv4l-raspidisp keyboard to socket and releasing %s" % socket_path)
    subprocess.Popen("./uv4l-socket.sh %s" %socket_path,shell=True)
except:
    raise
