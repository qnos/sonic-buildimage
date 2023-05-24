#!/bin/bash
# Set SYS_LED to Green, assuming everything came up fine.
ipmitool raw 0x3A 0x39 0x02 0x00 0x02

# Enable thermal shutdown by default
#i2cset -y -f 103 0x0d 0x75 0x1
