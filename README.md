## How to build the environment?

### Python Interpreter used in this project

> Python version: `3.11.10`.


```python
pip install matplotlib numpy
```

### Azure Kinect Sensor SDK

- [SDK installer](https://download.microsoft.com/download/d/c/1/dc1f8a76-1ef2-4a1a-ac89-a7e22b3da491/Azure%20Kinect%20SDK%201.4.2.exe), The installer will put all the needed headers, binaries, and tools in the location you choose (by default this is `C:\Program Files\Azure Kinect SDK version\sdk`).;
- Copy `k4a.dll` and `depthengine_2_0.dll` files from ``;
- Put them in to `.../Azure-Kinect-Sensor-SDK\src\python\k4a\src\k4a\_libs`;
- run the script `src/python/k4a/build_wheel.ps1`, get the `.whl` file in `build/`. (`powershell -ExecutionPolicy Bypass -File .\build_wheel.ps1`)
- then in conda env and terminal ` pip install ..\src\python\k4a\build\k4a-0.0.2-py3-none-any.whl`

### RealSense L515

- `pip install pyrealsense2==2.54.2.5684`