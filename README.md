#### SecVision - THIS BRANCH IS NOT BEING MAINTAINED

Technologies used
  - Jetson Nano
  - Jetson Inference - Detectnet
  - HikVision DVR

### Setup prior to use

- detect.py 
  - **PLEASE BUILD THIS PROJECT FIRST** 
  - https://github.com/dusty-nv/jetson-inference/blob/master/docs/building-repo-2.md
  - SSD-MOBILENET-V2 **OR** change model hardcoded in code
   

### Goals

 - Use still frames from HTTP GET from DVR to analyze zones(cameras)
 - Detected persons
   - HTTP PUT to HikVision DVR
   - Use DVR output connected to input to trigger recording on DVR
 
 ### Usage

   Setup settings.ini
   
   On DVR set basic auth for HTTP request
   
    git clone https://github.com/Psynosaur/JetsonSecVision && cd JetsonSecVision
    pip3 install aiofiles aiohttp asyncio colorlog

   ### jetson inference stack - supports terminal args

    python3 detect_mobile/detect.py

   Takes approximately 1.1 seconds to do its thing for 8x2MP images, sometimes a little longer at 1.5s when writing files

  
   ### Automatic / Continuous Operation
   
   #### Run install scripts

   ##### Jetson-Inference

    $ sudo detect_mobile/install.sh
    
  


   ### Check status of service jetson.utils using ssd-mobilenet-v2

    $ sudo service detect status

   
     
   ### To stop the service, simply run:

    $ sudo service detect stop

   

   ### To uninstall the service

    $ sudo detect_mobile/uninstall.sh

   

### Developers

    $ sudo detect_mobile/refresh.sh
 
