#!/bin/bash

#Require sudo
if [ $EUID != 0 ]; then
    sudo "$0" "$@"
    exit $?
fi

echo "removing service..."
systemctl stop detect
systemctl disable detect
echo "done"


echo "removing /usr/local/bin/secvision/..."
rm -r /usr/local/bin/secvision
rm -r /usr/bin/secvision 2>/dev/null
echo "done"

echo "removing service from /lib/systemd/system/..."
rm /lib/systemd/system/detect.service
echo "done"

echo "reloading services"
systemctl daemon-reload
echo "done"

echo "SecVision - detect uninstalled successfully!"
echo "Huzzah"
