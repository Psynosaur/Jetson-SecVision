#### SecVision

Technologies used
 
 - Jetson Nano 
 - Networks
   - detect.py
     - Jetson Inference - Detectnet 
   - detect_yolo.py
     - TensorRT - Yolov4 - **PLEASE BUILD THIS PROJECT FIRST** 
     - https://github.com/jkjung-avt/tensorrt_demos
     - Environment is ready when Demo #5 runs  
 - HikVision DVR

### Goals

 - Use still frames from HTTP GET from DVR to analyze zones(cameras)
 - Detected persons
   - HTTP PUT to HikVision DVR
   - Use DVR output connected to input to trigger recording on DVR
 
 ### Usage

   Setup username and password and channel count
   
   Uses basic auth for HTTP request to DVR
   
      pip3 install aiofiles aiohttp asyncio

   ### jetson inference stack 

      python3 detect.py

   Takes approximately 1.1 seconds to do its thing for 8x2MP images, sometimes a little longer at 1.5s when writing files
   
   ### Tensort stack with yolov4, needs symlinks to tensorrt_demo project

      python3 detect_yolo.py

   Takes approximately 2.6 seconds round trip to do its thing for 8x2MP images and is very accurate
   Detection step takes 1.75s for a network fps of **~4.57FPS**.

   ### Automatic / Continuous Operation
   
   Change User in detect.service file to suite your environment then 

      $ sudo ./install.sh
    
   Change User in detect_yolo.service file to suite your environment then 

      $ sudo ./install_yolo.sh

   ### Check status of service jetson.utils using ssd-mobilenet-v2

      $ sudo service detect status

   or yolov4-416 with openCV

      $ sudo service detect_yolo status
     
   ### To stop the service, simply run:

      $ sudo service detect stop

   or

      $ sudo service detect_yolo stop

   ### Symlinks for running yolov4 version

      $ ln -s ${HOME}/tensorrt_demos/utils/ ./utils
      $ ln -s ${HOME}/tensorrt_demos/plugins/ ./plugins
      $ ln -s ${HOME}/tensorrt_demos/yolo/ ./yolo

   ### To uninstall the service

      $ sudo ./uninstall.sh

   or

      $ sudo ./uninstall_yolo.sh
