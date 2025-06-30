#!/usr/bin/bash
## See https://github.com/luxonis/depthai-docs-website/blob/master/source/pages/troubleshooting.rst#id3
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666"' | sudo tee /etc/udev/rules.d/80-movidius.rules
sudo udevadm control --reload-rules && sudo udevadm trigger