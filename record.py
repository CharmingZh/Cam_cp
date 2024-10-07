import k4a
import cv2
import os


def capture_and_save_sequence(output_folder, num_images=2000):
    # 创建保存图片的文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 打开 Kinect 设备
    device = k4a.Device.open()

    if device is None:
        print('Camera Device not found.')
        exit(-1)

    # 打印设备序列号和硬件版本
    print(device.serial_number)
    print(device.hardware_version)
    print(device.color_ctrl_cap)

    # 配置设备参数
    device_config = k4a.DeviceConfiguration(
        color_format=k4a.EImageFormat.COLOR_BGRA32,
        color_resolution=k4a.EColorResolution.RES_1080P,
        depth_mode=k4a.EDepthMode.NFOV_UNBINNED,
        camera_fps=k4a.EFramesPerSecond.FPS_15,
        synchronized_images_only=True,
        depth_delay_off_color_usec=0,
        wired_sync_mode=k4a.EWiredSyncMode.STANDALONE,
        subordinate_delay_off_master_usec=0,
        disable_streaming_indicator=False
    )

    # 启动相机
    status = device.start_cameras(device_config)
    if status != k4a.EStatus.SUCCEEDED:
        exit(-1)

    # 手动设置曝光时间为 2500 微秒
    exposure_time_usec = 3000   # 500, 1250, 2500, 8330
    device.set_color_control(k4a.EColorControlCommand.EXPOSURE_TIME_ABSOLUTE,
                             k4a.EColorControlMode.MANUAL, exposure_time_usec)

    # 设置增益为 255
    gain_value = 255
    device.set_color_control(k4a.EColorControlCommand.GAIN,
                             k4a.EColorControlMode.MANUAL, gain_value)

    # # 设置手动白平衡为 4050K
    # white_balance = 4050
    # device.set_color_control(k4a.EColorControlCommand.WHITEBALANCE,
    #                          k4a.EColorControlMode.MANUAL, white_balance)

    try:
        for i in range(num_images):
            # 获取捕获的图像
            capture = device.get_capture(-1)

            # 仅处理彩色图像
            if capture.color is not None:
                color_image = capture.color.data
                # 构建文件名
                file_name = os.path.join(output_folder, f"image_{i:03d}.png")

                # 保存图像到文件夹中
                cv2.imwrite(file_name, color_image)
                print(f"Saved {file_name}")

            # 延迟 1 毫秒（根据需要调整）
            cv2.waitKey(1)

    finally:
        # 停止设备并释放资源
        device.stop_cameras()

    print("Image sequence saved successfully.")


if __name__ == '__main__':
    # 保存图片的文件夹路径
    output_folder = "image_sequence"
    # 捕获2000张图片并保存
    capture_and_save_sequence(output_folder, num_images=2000)
