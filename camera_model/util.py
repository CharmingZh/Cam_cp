



class myLog:
    def __init__(self):
        pass

    def print_log(self, camera_type=0, log_type=0, log_msg=""):
        camera_types = {
            0: 'Azure Kinect DK',
            1: 'ZED X Stereo   ',
            2: 'RealSense L515 '
        }

        LOG_PRE_STR = f'[LOG - {camera_types[camera_type]}]'

        match log_type:
            case 0:  # Camera not found Error
                print(LOG_PRE_STR + f'< ERROR >' + str(log_msg))
                # 执行 Kinect DK 相关命令
            case 1:
                print(LOG_PRE_STR + f'< INFO >' + str(log_msg))
                # 执行 Azure Kinect 相关命令
            case 2:
                print("Executing command for RealSense D435")
                # 执行 RealSense D435 相关命令
            case 3:
                print("Executing command for RealSense L515")
                # 执行 RealSense L515 相关命令
            case _:
                print("Unknown camera type")