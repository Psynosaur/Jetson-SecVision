#### SecVision

Technologies used
  - Jetson Nano
 - Jetson Inference - Detectnet
 - TensorRT - Yolov4-416  
 - Networks
 - HikVision DVR

### Setup prior to use

- detect.py
  - **PLEASE BUILD THIS PROJECT FIRST** 
  - https://github.com/dusty-nv/jetson-inference/blob/master/docs/building-repo-2.md
  - SSD-MOBILENET-V2 **OR** change model hardcoded in code
- detect_yolo.py
  - **PLEASE BUILD THIS PROJECT FIRST**
  - https://github.com/jkjung-avt/tensorrt_demos
  - Environment is ready when Demo #5 runs with yolov4-416 model
    

### Goals

 - Use still frames from HTTP GET from DVR to analyze zones(cameras)
 - Detected persons
   - HTTP PUT to HikVision DVR
   - Use DVR output connected to input to trigger recording on DVR
 
 ### Usage

   Setup settings.ini
   
   On DVR set basic auth for HTTP request
   
    git clone https://github.com/Psynosaur/JetsonSecVision && cd JetsonSecVision
    pip3 install aiofiles aiohttp asyncio

   ### jetson inference stack - supports terminal args

    python3 detect_mobile/detect.py

   Takes approximately 1.1 seconds to do its thing for 8x2MP images, sometimes a little longer at 1.5s when writing files
   
   ### Tensort stack with yolov4, needs symlinks to tensorrt_demo project - supports terminal args
   #### Setup environment

    cd detect_yolo 
    ln -s ${HOME}/tensorrt_demos/utils/ ./utils
    ln -s ${HOME}/tensorrt_demos/plugins/ ./plugins
    ln -s ${HOME}/tensorrt_demos/yolo/ ./yolo

   #### Run script

     python3 detect_yolo/detect_yolo.py -m yolov4-416

   Takes approximately 2.6 seconds round trip to do its thing for 8x2MP images and is very accurate
   Detection step takes 1.75s for a network fps of **~4.57FPS**.

   ### Automatic / Continuous Operation
   
   #### Run install scripts

   ##### Jetson-Inference

    $ sudo detect_mobile/install.sh
    
   ##### TensorRT-Yolov4-416
    
    

   Installation

    $ sudo detect_yolo/install_yolo.sh


   ### Check status of service jetson.utils using ssd-mobilenet-v2

    $ sudo service detect status

   or yolov4-416 with openCV

    $ sudo service detect_yolo status
     
   ### To stop the service, simply run:

    $ sudo service detect stop

   or

    $ sudo service detect_yolo stop

   ### To uninstall the service

    $ sudo detect_mobile/uninstall.sh

   or

    $ sudo detect_yolo/uninstall_yolo.sh

### Developers

    $ sudo detect_mobile/refresh.sh
 
  or

    $ sudo detect_yolo/refresh_yolo.sh

### Expected output 

    Oct 26 20:36:26 jetson secvision_yolo[26856]: INFO: 501 Person found - Zone 3 start recording
    Oct 26 20:36:26 jetson secvision_yolo[26856]: INFO: Zone 3 triggered on
    Oct 26 20:36:27 jetson secvision_yolo[26856]: INFO: Network 4.53fps
    Oct 26 20:36:29 jetson secvision_yolo[26856]: INFO: 501 Person found 2.737577s ago
    Oct 26 20:36:29 jetson secvision_yolo[26856]: INFO: CPU 32.50°C / GPU 31.50°C / PLL 28.00°C
    Oct 26 20:36:29 jetson secvision_yolo[26856]: INFO: AO 38.50°C / THERM 32.25°C / FAN 1195.0RPM
    Oct 26 20:36:30 jetson secvision_yolo[26856]: INFO: Network 4.58fps
    Oct 26 20:36:32 jetson secvision_yolo[26856]: INFO: Network 4.79fps
    Oct 26 20:36:34 jetson secvision_yolo[26856]: INFO: 501 Person found 8.268842s ago
    Oct 26 20:36:34 jetson secvision_yolo[26856]: INFO: CPU 34.00°C / GPU 30.50°C / PLL 28.00°C
    Oct 26 20:36:34 jetson secvision_yolo[26856]: INFO: AO 40.00°C / THERM 32.50°C / FAN 1312.0RPM
    Oct 26 20:36:34 jetson secvision_yolo[26856]: INFO: Network 4.60fps
    Oct 26 20:36:37 jetson secvision_yolo[26856]: INFO: Network 4.76fps
    Oct 26 20:36:39 jetson secvision_yolo[26856]: INFO: Network 4.78fps
    Oct 26 20:36:40 jetson secvision_yolo[26856]: INFO: 501 Person found 13.755617s ago
    Oct 26 20:36:40 jetson secvision_yolo[26856]: INFO: CPU 32.00°C / GPU 30.00°C / PLL 28.00°C
    Oct 26 20:36:40 jetson secvision_yolo[26856]: INFO: AO 36.50°C / THERM 32.00°C / FAN 1125.0RPM
    Oct 26 20:36:42 jetson secvision_yolo[26856]: INFO: Network 4.76fps
    Oct 26 20:36:44 jetson secvision_yolo[26856]: INFO: Network 4.79fps
    Oct 26 20:36:45 jetson secvision_yolo[26856]: INFO: 501 Person found 19.258132s ago
    Oct 26 20:36:45 jetson secvision_yolo[26856]: INFO: CPU 32.00°C / GPU 30.00°C / PLL 28.00°C
    Oct 26 20:36:45 jetson secvision_yolo[26856]: INFO: AO 35.50°C / THERM 31.00°C / FAN 1289.0RPM
    Oct 26 20:36:47 jetson secvision_yolo[26856]: INFO: Network 4.74fps
    Oct 26 20:36:49 jetson secvision_yolo[26856]: INFO: Network 4.76fps
    Oct 26 20:36:51 jetson secvision_yolo[26856]: INFO: 501 Person found 24.786598s ago
    Oct 26 20:36:51 jetson secvision_yolo[26856]: INFO: CPU 33.50°C / GPU 30.50°C / PLL 28.50°C
    Oct 26 20:36:51 jetson secvision_yolo[26856]: INFO: AO 40.00°C / THERM 32.50°C / FAN 1062.0RPM
    Oct 26 20:36:52 jetson secvision_yolo[26856]: INFO: Network 4.59fps
    Oct 26 20:36:54 jetson secvision_yolo[26856]: INFO: Network 4.78fps
    Oct 26 20:36:56 jetson secvision_yolo[26856]: INFO: 501 Person found 30.318584s ago
    Oct 26 20:36:56 jetson secvision_yolo[26856]: INFO: CPU 33.50°C / GPU 31.00°C / PLL 28.50°C
    Oct 26 20:36:56 jetson secvision_yolo[26856]: INFO: AO 40.00°C / THERM 33.25°C / FAN 1328.0RPM
    Oct 26 20:36:57 jetson secvision_yolo[26856]: INFO: Network 4.70fps
    Oct 26 20:36:57 jetson secvision_yolo[26856]: INFO: Zone 3 triggered off
    