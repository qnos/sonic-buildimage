#!/usr/bin/python

import os
import re
import struct
import subprocess

class APIHelper():

    def __init__(self):
        pass
        
    def with_bmc(self):
        status, result = self.grep("ipmitool mc info", "Firmware Revision")
        if status:
            bmc_ver_data = result.split(":")
            if len(bmc_ver_data) > 0:
                return True
        return False
        
    def run_command(self, cmd):
        status = True
        result = ""
        try:
            p = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            raw_data, err = p.communicate()
            if err.decode('UTF-8') == '':
                result = raw_data.strip().decode('UTF-8')
        except Exception:
            status = False
        return status, result
        
    def get_register_value(self, getreg_path, register):
        cmd = "echo {1} > {0}; cat {0}".format(getreg_path, register)
        return self.run_command(cmd)
        
    def set_register_value(self, setreg_path, register, value):
        cmd = "echo {1} {2} > {0}".format(setreg_path, register, value)
        status, result = self.run_command(cmd)
        return status

    def cpld_lpc_read(self, reg):
        register = "0x{:X}".format(reg)
        return self.get_register_value("/sys/devices/platform/sys_cpld/getreg", register)

    def cpld_lpc_write(self, reg, val):
        register = "0x{:X}".format(reg)
        value = "0x{:X}".format(val)
        return self.set_register_value("/sys/devices/platform/sys_cpld/setreg", register, value)

    def grep(self, cmd, key):
        status, result = self.run_command("{0} | grep '{1}'".format(cmd, key))
        m = re.search(key, result)
        if status:
            status = True if m else False
        return status, result

    def read_txt_file(self, file_path):
        try:
            with open(file_path, 'r') as fd:
                data = fd.read()
                return data.strip()
        except IOError:
            pass
        return None
        
    def ipmi_fru(self, id=0, key=None):
        status = True
        result = ""
        cmd = "ipmitool fru print {0}".format(id)
        if not key:
            try:
                status, result = self.run_command(cmd)
            except:
                status = False
        else:
            status, result = self.grep(cmd, str(key))
        return status, result

# only for test
if __name__ == "__main__":
    API = APIHelper()
    print(API.with_bmc())