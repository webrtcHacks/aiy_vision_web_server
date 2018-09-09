#!/usr/bin/env bash
framerate=${2:-15}
ffmpeg -framerate $framerate -n -i "concat:./recordings/$1_before.h264|./recordings/$1_after.h264" ./recordings/$1.mp4