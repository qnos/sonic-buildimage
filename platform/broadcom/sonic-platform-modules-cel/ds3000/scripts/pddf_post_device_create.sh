#!/bin/bash
# Set SYS_LED to Green, assuming everything came up fine.
ipmitool raw 0x3A 0x0C 0x00 0x03 0x62 0xdc

# Enable thermal shutdown by default
i2cset -y -f 103 0x0d 0x75 0x1

# Write firmware version info into /var/log/firmware_versions
FIRMWARE_VER_FILE="/var/log/firmware_versions"
echo "BIOS: `dmidecode -s bios-version`-`dmidecode -s bios-release-date`" > ${FIRMWARE_VER_FILE}
VERARR=(`ipmitool raw 0x6 0x1 | cut -d ' ' -f 4,5,16,15,14`)
echo "BMC: ${VERARR[0]}.${VERARR[1]}.${VERARR[4]}.${VERARR[3]}${VERARR[2]}" >> ${FIRMWARE_VER_FILE}
echo "BaseBoard CPLD: `ipmitool raw 0x3A 0x0C 0x00 0x02 0x0 | tr a-z A-Z | cut -d ' ' -f 2`" >> ${FIRMWARE_VER_FILE}
echo "SwitchBoard CPLD1: `i2cget -y -f 102 0x30 0 | tr a-z A-Z | cut -d 'X' -f 2`" >> ${FIRMWARE_VER_FILE}
echo "SwitchBoard CPLD2: `i2cget -y -f 102 0x31 0 | tr a-z A-Z | cut -d 'X' -f 2`" >> ${FIRMWARE_VER_FILE}
#echo "PCIE Firmware: `bcmcmd 'pciephy fw version' | grep 'PCIe FW version' | cut -d ' ' -f 4`" >> ${FIRMWARE_VER_FILE}
