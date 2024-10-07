import k4a
import cv2
import numpy as np

import camera_model.kinect_dk
from camera_model.util import myLog
from camera_model.kinect_dk import *

if __name__ == '__main__':
    # camera_model.kinect_dk.record()

    folder_path = "./image_sequence/kinect_20241006_160728"
    camera_model.kinect_dk._play(folder_path)


