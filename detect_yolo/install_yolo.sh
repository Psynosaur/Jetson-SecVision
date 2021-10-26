#!/bin/bash

#Require sudo
if [ $EUID != 0 ]; then
    sudo "$0" "$@"
    exit $?
fi

pwd=${pwd}
sed -i "s?placeholder?$PWD?g" detect_yolo.service
sed -i "s?suchuser?$SUDO_USER?g" detect_yolo.service

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