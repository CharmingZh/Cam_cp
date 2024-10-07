import k4a
import cv2
import numpy as np

import re

import os
import time
import json
from datetime import datetime

# import threading
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from queue import Queue

from camera_model.util import myLog

# Need to be setting
KINECT_EXPOSURE_TIME    = 8330 # 500, 1250, 2500, 8330
KINECT_GAIN_VALUE       = 128
KINECT_WHITE_BALANCE    = 4500

# 定义全局队列，主线程存储捕获数据，处理线程取出数据处理
capture_queue = Queue(maxsize=32)

# 全局计数器和锁
frame_counter = 0
counter_lock = Lock()

log_v = myLog()

def set_up():
    # Open a device using the static function Device.open().
    device_v = k4a.Device.open()

    if device_v is None:
        log_v.print_log(0, 0, 'Camera Device not found.')
        return None
    else:
        # Print the device serial number, hardware_version, and
        # color control capabilities.
        log_v.print_log(0, 1, device_v.serial_number)
        # log_v.print_log(0, 1, device_v.hardware_version)
        log_v.print_log(0, 1, device_v.color_ctrl_cap)

    # 配置设备参数
    device_config = k4a.DeviceConfiguration(
        color_format                        = k4a.EImageFormat.COLOR_BGRA32,
        color_resolution                    = k4a.EColorResolution.RES_1080P,
        depth_mode                          = k4a.EDepthMode.NFOV_UNBINNED,
        camera_fps                          = k4a.EFramesPerSecond.FPS_30,
        synchronized_images_only            = True,
        depth_delay_off_color_usec          = 0,
        wired_sync_mode                     = k4a.EWiredSyncMode.STANDALONE,
        subordinate_delay_off_master_usec   = 0,
        disable_streaming_indicator         = False
    )

    # 手动设置曝光时间，例如 5000 微秒 (5ms)
    device_v.set_color_control(
        k4a.EColorControlCommand.EXPOSURE_TIME_ABSOLUTE,
        k4a.EColorControlMode.MANUAL,
        KINECT_EXPOSURE_TIME
    )

    # 设置增益手动控制并调整增益值（类似于ISO）
    device_v.set_color_control(
        k4a.EColorControlCommand.GAIN,
        k4a.EColorControlMode.MANUAL,
        KINECT_GAIN_VALUE
    )

    # 设置自动白平衡关闭，手动设置白平衡值
    device_v.set_color_control(
        k4a.EColorControlCommand.WHITEBALANCE,
        k4a.EColorControlMode.MANUAL,
        KINECT_WHITE_BALANCE
    )

    return device_v, device_config

def _capture_frames(device, folder_path):
    global frame_counter
    try:
        # 打开time.stamp文件用于追加写入
        time_stamp_file = os.path.join(folder_path, 'time.stamp')
        with open(time_stamp_file, 'a') as f:
            while True:
                try:
                    capture     = device.get_capture(-1)  # Capture frame
                    timestamp   = time.perf_counter()

                    if capture is None:
                        log_v.print_log(0, 0, 'No Capture Frame.')
                        continue

                    # Safely manage the queue
                    if capture_queue.full():
                        print("Full, drop!")
                        capture_queue.get_nowait()  # Safely discard old frames

                    with counter_lock:
                        frame_number = frame_counter
                        frame_counter += 1

                    capture_queue.put((capture, frame_number))
                    f.write(f"{frame_number}, {timestamp}\n")

                    if capture.color is not None:
                        cv2.imshow("Color Image", capture.color.data)

                    if capture.depth is not None:
                        depth_image = capture.depth.data

                        depth_min = 500  # 0.75米
                        depth_max = 1000  # 3米

                        # 深度图像归一化和伪彩色化
                        depth_image_clipped = np.clip(depth_image, depth_min, depth_max)
                        depth_image_normalized = (depth_image_clipped - depth_min) / (depth_max - depth_min) * 255
                        depth_image_normalized = depth_image_normalized.astype(np.uint8)
                        depth_colormap = cv2.applyColorMap(depth_image_normalized, cv2.COLORMAP_JET)
                        cv2.imshow("Depth Image", depth_colormap)

                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                except Exception as e:
                    print(f"Error during frame capture: {e}")
                    break
    finally:
        print("Capture thread ending.")


def _save_frames(folder_path):
    rgb_folder = os.path.join(folder_path, "rgb")
    dep_folder = os.path.join(folder_path, "depth")

    os.makedirs(rgb_folder, exist_ok=True)
    os.makedirs(dep_folder, exist_ok=True)

    # Metadata file to store information about image resolution and dtype
    metadata_file = os.path.join(folder_path, "metadata.txt")

    # Flags to indicate if metadata has been saved
    metadata_saved = False

    with open(metadata_file, 'a') as meta_file:
        while True:
            if not capture_queue.empty():
                (capture, frame_number) = capture_queue.get()

                # Save color image as binary
                if capture.color is not None:
                    color_image = capture.color.data
                    color_image_path = os.path.join(rgb_folder, f"color_{frame_number:04d}.bin")
                    color_image.tofile(color_image_path)  # Save as binary

                    # Only save metadata for RGB image once
                    if not metadata_saved:
                        meta_file.write(f"RGB - resolution: {color_image.shape}, dtype: {color_image.dtype}\n")

                # Save depth image as binary
                if capture.depth is not None:
                    depth_image = capture.depth.data
                    depth_image_path = os.path.join(dep_folder, f"depth_{frame_number:04d}.bin")
                    depth_image.tofile(depth_image_path)  # Save as binary

                    # Only save metadata for depth image once
                    if not metadata_saved:
                        meta_file.write(f"Depth - resolution: {depth_image.shape}, dtype: {depth_image.dtype}\n")
                        metadata_saved = True  # Ensure metadata is only written once

                # Flush metadata after writing (ensuring it's written to disk)
                meta_file.flush()


def record():
    device = None

    """根据当前时间创建文件夹"""
    # 获取当前时间的格式化字符串
    current_time_str = datetime.now().strftime("kinect_%Y%m%d_%H%M%S")
    # 构建文件夹路径
    folder_path = os.path.join("image_sequence", current_time_str)

    # 如果文件夹不存在，创建它
    os.makedirs(folder_path, exist_ok=True)


    try:
        # 设置Azure Kinect设备
        device, device_config = set_up()  # 假设已经实现set_up函数
        device.start_cameras(device_config)

        # 使用线程池处理捕获和处理流程
        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(_capture_frames, device, folder_path)
            executor.submit(_save_frames, folder_path)

    finally:
        # 确保资源正确释放
        device.stop_cameras()
        cv2.destroyAllWindows()


import os
import cv2
import numpy as np
import time
import re
from queue import Queue
from concurrent.futures import ThreadPoolExecutor


def _play(folder_path):
    """Replay the recorded RGB and depth frames based on timestamps using multithreading."""

    # Paths to metadata, timestamp, rgb, and depth folders
    metadata_file = os.path.join(folder_path, "metadata.txt")
    timestamp_file = os.path.join(folder_path, "time.stamp")
    rgb_folder = os.path.join(folder_path, "rgb")
    depth_folder = os.path.join(folder_path, "depth")

    # Read metadata to get image resolution and dtype
    with open(metadata_file, 'r') as f:
        metadata = f.readlines()

    rgb_metadata = metadata[0].strip().split("resolution: ")[1].split(", dtype: ")
    rgb_resolution = tuple(map(int, re.findall(r'\d+', rgb_metadata[0])))  # Get resolution as tuple
    rgb_dtype = np.dtype(rgb_metadata[1])  # Get dtype

    depth_metadata = metadata[1].strip().split("resolution: ")[1].split(", dtype: ")
    depth_resolution = tuple(map(int, re.findall(r'\d+', depth_metadata[0])))  # Get resolution as tuple
    depth_dtype = np.dtype(depth_metadata[1])  # Get dtype

    # Read timestamp file to get timestamps and frame numbers
    timestamps = []
    with open(timestamp_file, 'r') as f:
        for line in f:
            frame_number, timestamp = line.strip().split(', ')
            timestamps.append((int(frame_number), float(timestamp)))

    # Queue for storing preloaded frames (shared between the threads)
    frame_queue = Queue(maxsize=10)  # Limit queue size to prevent excessive memory usage

    def load_frames():
        """Thread function for loading frames."""
        for i in range(len(timestamps) - 1):
            frame_number, timestamp = timestamps[i]

            # Load RGB image from binary file
            rgb_file_path = os.path.join(rgb_folder, f"color_{frame_number:04d}.bin")
            rgb_image = np.fromfile(rgb_file_path, dtype=rgb_dtype).reshape(rgb_resolution)

            # Load depth image from binary file
            depth_file_path = os.path.join(depth_folder, f"depth_{frame_number:04d}.bin")
            depth_image = np.fromfile(depth_file_path, dtype=depth_dtype).reshape(depth_resolution)

            # Add frame to queue
            frame_queue.put((rgb_image, depth_image, timestamp))

        # Signal that loading is complete by adding a sentinel value (None)
        frame_queue.put(None)

    def play_frames():
        """Thread function for playing frames."""
        prev_timestamp = timestamps[0][1]

        while True:
            # Get the next frame from the queue
            frame_data = frame_queue.get()

            if frame_data is None:
                break  # Exit loop if sentinel value (None) is encountered

            rgb_image, depth_image, current_timestamp = frame_data

            # Display RGB image
            cv2.imshow('RGB Image', rgb_image)

            # Normalize and display depth image
            depth_min = 500
            depth_max = 1000
            depth_image_clipped = np.clip(depth_image, depth_min, depth_max)
            depth_image_normalized = (depth_image_clipped - depth_min) / (depth_max - depth_min) * 255
            depth_image_normalized = depth_image_normalized.astype(np.uint8)
            depth_colormap = cv2.applyColorMap(depth_image_normalized, cv2.COLORMAP_JET)
            cv2.imshow('Depth Image', depth_colormap)

            # Wait for the time difference between current and previous frame's timestamp
            time_difference = current_timestamp - prev_timestamp
            prev_timestamp = current_timestamp
            time.sleep(time_difference)  # Use time.sleep() to sync frame display with recording time

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cv2.destroyAllWindows()

    # Create and manage the threads for loading and playing
    with ThreadPoolExecutor(max_workers=2) as executor:
        executor.submit(load_frames)  # Thread 1: Loads frames
        executor.submit(play_frames)  # Thread 2: Plays frames


# def _play(folder_path):
#     """Replay the recorded RGB and depth frames based on timestamps."""
#
#     # Paths to metadata, timestamp, rgb, and depth folders
#     metadata_file = os.path.join(folder_path, "metadata.txt")
#     timestamp_file = os.path.join(folder_path, "time.stamp")
#     rgb_folder = os.path.join(folder_path, "rgb")
#     depth_folder = os.path.join(folder_path, "depth")
#
#     # Read metadata to get image resolution and dtype
#     with open(metadata_file, 'r') as f:
#         metadata = f.readlines()
#
#     rgb_metadata = metadata[0].strip().split("resolution: ")[1].split(", dtype: ")
#     rgb_resolution = tuple(map(int, re.findall(r'\d+', rgb_metadata[0])))  # Get resolution as tuple
#     rgb_dtype = np.dtype(rgb_metadata[1])  # Get dtype
#
#     depth_metadata = metadata[1].strip().split("resolution: ")[1].split(", dtype: ")
#     depth_resolution = tuple(map(int, re.findall(r'\d+', depth_metadata[0])))  # Get resolution as tuple
#     depth_dtype = np.dtype(depth_metadata[1])  # Get dtype
#
#     # Read timestamp file to get timestamps and frame numbers
#     timestamps = []
#     with open(timestamp_file, 'r') as f:
#         for line in f:
#             frame_number, timestamp = line.strip().split(', ')
#             timestamps.append((int(frame_number), float(timestamp)))
#
#     # Loop through each timestamp and load corresponding RGB and depth images
#     for i in range(len(timestamps) - 1):
#         frame_number, timestamp = timestamps[i]
#         next_frame_number, next_timestamp = timestamps[i + 1]
#
#         # Load RGB image from binary file
#         rgb_file_path = os.path.join(rgb_folder, f"color_{frame_number:04d}.bin")
#         rgb_image = np.fromfile(rgb_file_path, dtype=rgb_dtype).reshape(rgb_resolution)
#
#         # Load depth image from binary file
#         depth_file_path = os.path.join(depth_folder, f"depth_{frame_number:04d}.bin")
#         depth_image = np.fromfile(depth_file_path, dtype=depth_dtype).reshape(depth_resolution)
#
#         # Display RGB image
#         cv2.imshow('RGB Image', rgb_image)
#
#         # Normalize and display depth image
#         depth_min = 500
#         depth_max = 1000
#         depth_image_clipped = np.clip(depth_image, depth_min, depth_max)
#         depth_image_normalized = (depth_image_clipped - depth_min) / (depth_max - depth_min) * 255
#         depth_image_normalized = depth_image_normalized.astype(np.uint8)
#         depth_colormap = cv2.applyColorMap(depth_image_normalized, cv2.COLORMAP_JET)
#         cv2.imshow('Depth Image', depth_colormap)
#
#         # Wait for the time difference between current and next frame's timestamp
#         time_difference = next_timestamp - timestamp
#         cv2.waitKey(int(time_difference * 1000))  # Convert seconds to milliseconds
#
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break
#
#     cv2.destroyAllWindows()


def parse_calibration_string(calibration_str):
    """Parse a calibration string and return extrinsics and intrinsics."""
    extrinsics_pattern = r"rotation=\[\[([0-9.,\s-]+)\]\] translation=\[([0-9.,\s-]+)\]"
    intrinsics_pattern = r"parameters=cx=([0-9.-]+), cy=([0-9.-]+), fx=([0-9.-]+), fy=([0-9.-]+), k1=([0-9.-]+), k2=([0-9.-]+), k3=([0-9.-]+), k4=([0-9.-]+), k5=([0-9.-]+), k6=([0-9.-]+)"

    extrinsics_matches = re.findall(extrinsics_pattern, calibration_str)
    intrinsics_matches = re.findall(intrinsics_pattern, calibration_str)

    # Parse extrinsics
    extrinsics_list = []
    for rotation, translation in extrinsics_matches:
        rotation_values = [[float(num) for num in row.split(',')] for row in rotation.split('][')]
        translation_values = [float(num) for num in translation.split(',')]
        extrinsics_list.append({
            'rotation': rotation_values,
            'translation': translation_values
        })

    # Parse intrinsics
    intrinsics_list = []
    for intrinsics in intrinsics_matches:
        cx, cy, fx, fy, k1, k2, k3, k4, k5, k6 = map(float, intrinsics)
        intrinsics_list.append({
            'cx': cx, 'cy': cy, 'fx': fx, 'fy': fy,
            'k1': k1, 'k2': k2, 'k3': k3, 'k4': k4, 'k5': k5, 'k6': k6
        })

    logging.info("Extrinsics and Intrinsics parsed successfully.")
    return extrinsics_list, intrinsics_list