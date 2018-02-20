from setuptools import find_packages
from setuptools import setup


REQUIRED_PACKAGES = ['Flask', 'argparse', 'picamera']

setup(
    name='aiy_vision_web_server',
    version='0.1',
    install_requires=REQUIRED_PACKAGES,
    include_package_data=True,
    packages=[p for p in find_packages()],
    description='AIY Vision Web Server',
)