import os
from glob import glob
import re
import subprocess
import argparse

def make_videos(files_to_process):

    for id in files_to_process:
        print("creating %s.mp4" % id)
        subprocess.call('./join_videos.sh %s' % id, shell=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--view',
        '-v',
        dest='view',
        default=False,
        action='store_true',
        help="View-only mode - do not process any files")

    parser.add_argument(
        '--framerate',
        '-f',
        type=int,
        dest='framerate',
        default=15,
        help='Sets the camera framerate. Default is 15')



    args = parser.parse_args()

    path = "./recordings"
    mp4_files = glob(os.path.join(path, "[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]*.mp4"))
    h264_files = glob(os.path.join(path, "[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]*_*.h264"))

    h264_ids = []
    to_process = []

    for file in mp4_files:
        m = re.search(r"([0-9]{10,})", file)
        h264_ids.append(m.group(1))

    for file in h264_files:
        m = re.search(r"([0-9]{10,})_(before|after)(\.h264)", file)
        vid = m.group(1)
        if vid not in h264_ids:
            to_process.append(vid)

    to_process = list(set(to_process)) # dedupe

    if args.view:
        print("Existing videos")
        for file in mp4_files:
            print(file)

        print("Recordings without video")
        for file in to_process:
            print(file)
    else:
        make_videos(to_process)


if __name__ == '__main__':
    main()
