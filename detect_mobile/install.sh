#!/bin/bash

#Require sudo
if [ $EUID != 0 ]; then
    sudo "$0" "$@"
    exit $?
fi

echo "setting to /usr/local/bin/secvision/..."
rm -r /usr/bin/secvision/ 2>/dev/null
mkdir -p /usr/local/bin/secvision
cp detect.py /usr/local/bin/secvision/
cp async_frames.py /usr/local/bin/secvision/
cp settings.ini /usr/local/bin/secvision/
echo "done"

echo "adding service to /lib/systemd/system/..."
cp detect.service /lib/systemd/system/
chmod 644 /lib/systemd/system/detect.service
echo "done"

echo "starting and enabling service..."
systemctl daemon-reload
systemctl start detect
systemctl enable detect
echo "done"

echo "secvision installed successfully!"
echo ""
echo "log output can be viewed by running"
echo "sudo journalctl -u detect.service -f -n"