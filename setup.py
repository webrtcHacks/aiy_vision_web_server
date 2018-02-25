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
    subprocess.Popen("sudo chown pi: %s" %socket_path,shell=True)

except:
    print("Error changing permissions on %s. Is that file setup in uv4l-raspidisp.conf?" % socket_path)
    raise
