#!/bin/bash

#Require sudo
if [ $EUID != 0 ]; then
    sudo "$0" "$@"
    exit $?
fi

#echo "setting to /usr/local/bin/secvision/..."
#rm -r /usr/bin/secvision/ 2>/dev/null
#mkdir -p /usr/local/bin/secvision
#cp detect_yolo.py /usr/local/bin/secvision/
#cp async_frames_cv.py /usr/local/bin/secvision/
#cp settings.ini /usr/local/bin/secvision/
#sudo -H ln -s /home/jetsonman/tensorrt_demos/yolo/ /usr/local/bin/secvision/yolo
#sudo -H ln -s /home/jetsonman/tensorrt_demos/plugins/ /usr/local/bin/secvision/plugins
#sudo -H ln -s /home/jetsonman/tensorrt_demos/utils/ /usr/local/bin/secvision/utils
#echo "done"

echo "adding service to /lib/systemd/system/..."
cp detect_yolo.service /etc/systemd/system/
chmod 644 /etc/systemd/system/detect_yolo.service
echo "done"

echo "starting and enabling service..."
systemctl daemon-reload
systemctl enable detect_yolo
systemctl start detect_yolo
echo "done"

echo "SecVision - Yolo installed successfully!"
echo ""
echo "log output can be viewed by running"
echo "sudo journalctl -u detect_yolo.service -f -n"