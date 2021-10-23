#!/bin/bash

#Require sudo
if [ $EUID != 0 ]; then
    sudo "$0" "$@"
    exit $?
fi

echo "removing service..."
systemctl stop detect_yolo
systemctl disable detect_yolo
echo "done"


#echo "removing /usr/local/bin/secvision/..."
#rm -r /usr/local/bin/secvision
#rm -r /usr/bin/secvision 2>/dev/null
#echo "done"

echo "removing service from /etc/systemd/system/..."
rm /etc/systemd/system/detect_yolo.service
echo "done"

echo "reloading services"
systemctl daemon-reload
echo "done"

echo "SecVision - detect uninstalled successfully!"
echo "Huzzah"
