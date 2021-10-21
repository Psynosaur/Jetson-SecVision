#### SecVision

This will be a computer vision project to classify persons with RTSP video/HTTP Image feeds common to many security systems

Technologies used
 
 - Jetson Nano 
 - Jetson Inference - Detectnet
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

      python3 detect.py

   Takes approximately 2 seconds to do its thing for 8x2MP images, sometimes a little longer at 2.8s when writing files

   ### Automatic / Continuous Operation
   
      $ sudo cp detect.service /etc/systemd/system/
      $ sudo nano /etc/systemd/system/detect.service
   
   Change usr and paths in detect.service file to suite you environment then 

      $ sudo systemctl enable detect.service
      $ sudo systemctl start detect.service

   Check status of service 

      $ sudo systemctl status detect.service
      ● detect.service - secvision
         Loaded: loaded (/etc/systemd/system/detect.service; enabled; vendor preset: enabled)
         Active: active (running) since Thu 2021-10-21 21:16:44 SAST; 13min ago
       Main PID: 11801 (python3)
          Tasks: 6 (limit: 4181)
         CGroup: /system.slice/detect.service
                 └─11801 /usr/bin/python3 /home/jetsonman/SecVisionJetson/detect.py --threshold 0.7
   
      Oct 21 21:16:52 jetson secvision[11801]: [TRT]    Using cuDNN as a tactic source
      Oct 21 21:16:52 jetson secvision[11801]: [TRT]    [MemUsageChange] Init cuDNN: CPU +240, GPU +298, now: CPU 683, GPU 3042 (MiB)
      Oct 21 21:16:52 jetson secvision[11801]: [TRT]    [MemUsageChange] Init cuBLAS/cuBLASLt: CPU +0, GPU +0, now: CPU 683, GPU 3042 (MiB)
      Oct 21 21:16:52 jetson secvision[11801]: [TRT]    Deserialization required 3106252 microseconds.
      Oct 21 21:16:52 jetson secvision[11801]: [TRT]    [MemUsageSnapshot] deserializeCudaEngine end: CPU 683 MiB, GPU 3042 MiB
      Oct 21 21:16:52 jetson secvision[11801]: [TRT]    [MemUsageSnapshot] ExecutionContext creation begin: CPU 683 MiB, GPU 3042 MiB
      Oct 21 21:16:52 jetson secvision[11801]: [TRT]    Using cublas a tactic source
      Oct 21 21:16:52 jetson secvision[11801]: [TRT]    [MemUsageChange] Init cuBLAS/cuBLASLt: CPU +1, GPU +0, now: CPU 684, GPU 3042 (MiB)
      Oct 21 21:16:52 jetson secvision[11801]: [TRT]    Using cuDNN as a tactic source
      Oct 21 21:16:52 jetson secvision[11801]: [TRT]    [MemUsageChange] Init cuDNN: CPU +0, GPU +0, now: CPU 684, GPU 3042 (MiB)

   The log output can be viewed by running, this will be further implemented at a later stage...

      $ sudo journalctl -u detect.service -f -n
   
   To stop the service, simply run:

      $ sudo systemctl stop detect.service