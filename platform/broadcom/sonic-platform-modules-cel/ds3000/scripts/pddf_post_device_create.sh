#!/bin/bash

declare -r CPLD_SETREG="/sys/bus/platform/devices/baseboard/setreg"
declare -r CPLD_GETREG="/sys/bus/platform/devices/baseboard/getreg"

# Set SYS_LED to Green, assuming everything came up fine.
echo "0xa162 0xdc" > ${CPLD_SETREG}

# Enable thermal shutdown by default
echo "0xa175 0x1" > ${CPLD_SETREG}
