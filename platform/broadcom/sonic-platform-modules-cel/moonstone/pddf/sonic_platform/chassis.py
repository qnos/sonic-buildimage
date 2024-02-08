#!/usr/bin/env python

#############################################################################
# Celestica
#
# Component contains an implementation of SONiC Platform Base API and
# provides the chassis management function
#
#############################################################################

import os
import time

try:
    from sonic_platform_pddf_base.pddf_chassis import PddfChassis
    from sonic_platform_pddf_base.pddf_eeprom import PddfEeprom
    from sonic_platform_base.chassis_base import ChassisBase
    from sonic_platform.fan_drawer import FanDrawer
    from sonic_platform.fan import Fan
    from sonic_platform.sfp import Sfp  
    from sonic_platform.watchdog import Watchdog
    from sonic_platform.component import Component
    from .helper import APIHelper   
    import sys
    import subprocess
    from sonic_py_common import device_info
    from sonic_platform_base.sfp_base import SfpBase
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")

class Chassis(PddfChassis):
    """
    PDDF Platform-specific Chassis class
    """

    # Provide the functions/variables below for which implementation is to be overwritten
    
    def __init__(self, pddf_data=None, pddf_plugin_data=None):

        PddfChassis.__init__(self, pddf_data, pddf_plugin_data)
        self._api_helper = APIHelper()          
        self.__initialize_components()
        self._transceiver_presence = {}
        for port in range(len(self._sfp_list)):
            self._transceiver_presence[port] = False
        self.POLL_INTERVAL = 1

    def __initialize_components(self):

        self.NUM_COMPONENT = 8
    
        if self._api_helper.with_bmc(): 
            self.NUM_COMPONENT = self.NUM_COMPONENT + 1

        for index in range(0, self.NUM_COMPONENT):
            component = Component(index)
            self._component_list.append(component)

    def get_name(self):
        return "Moonstone"

    def get_all_components(self):
        return self._component_list

    def get_all_modules(self):
        return []
            
    def initizalize_system_led(self):
        return True

    def get_eeprom(self):
        return self._eeprom
        
    def get_all_sfps(self):
        return self._sfp_list
        
    def get_sfp(self, index):
        sfp = None

        try:
            if index == 0:
                raise IndexError
            sfp = self._sfp_list[index - 1]
        except IndexError:
            sys.stderr.write("override: SFP index {} out of range (1-{})\n".format(
                index, len(self._sfp_list)))

        return sfp

    def get_watchdog(self):
        """
        Retreives hardware watchdog device on this chassis
        Returns:
            An object derived from WatchdogBase representing the hardware
            watchdog device
        """
        if self._watchdog is None:
            self._watchdog = Watchdog()

        return self._watchdog

    def get_reboot_cause(self):
        """
        Retrieves the cause of the previous reboot
        Returns:
            A tuple (string, string) where the first element is a string
            containing the cause of the previous reboot. This string must be
            one of the predefined strings in this class. If the first string
            is "REBOOT_CAUSE_HARDWARE_OTHER", the second string can be used
            to pass a description of the reboot cause.
        """ 
        
        if self._api_helper.with_bmc(): 
        
            cmd_str = self._api_helper.bmc_cmd_format(self, "get_reboot_cause")
            status, result = self._api_helper.ipmi_raw(cmd_str)
            status = status.split()[0] if status and len(status.split()) > 0 else 00            
            
            reboot_cause = {
                "00": self.REBOOT_CAUSE_HARDWARE_OTHER,
                "11": self.REBOOT_CAUSE_POWER_LOSS,
                "22": self.REBOOT_CAUSE_NON_HARDWARE,
                "33": self.REBOOT_CAUSE_HARDWARE_OTHER,
                "44": self.REBOOT_CAUSE_NON_HARDWARE,
                "55": self.REBOOT_CAUSE_NON_HARDWARE,
                "66": self.REBOOT_CAUSE_WATCHDOG,
                "77": self.REBOOT_CAUSE_NON_HARDWARE
            }.get(status, self.REBOOT_CAUSE_HARDWARE_OTHER)

            description = {
                "00": "Unknown reason",
                "11": "The last reset is Power on reset",
                "22": "The last reset is soft-set CPU warm reset",
                "33": "The last reset is soft-set CPU cold reset",
                "44": "The last reset is CPU warm reset",
                "55": "The last reset is CPU cold reset",
                "66": "The last reset is watchdog reset",
                "77": "The last reset is power cycle reset"
            }.get(status, "Unknown reason")
        else:       
            reboot_cause = self.REBOOT_CAUSE_WATCHDOG
            description = 'Hardware Watchdog Reset'

        return (reboot_cause, description)
        
    def get_revision(self):
        return self._eeprom.revision_str()
        
    @staticmethod
    def get_position_in_parent():
        return -1
        
    @staticmethod
    def is_replaceable():
        return True  

    def set_system_led(self, device_name, color):
        if self._api_helper.with_bmc():
            if device_name == "DIAG_LED" or device_name == "SYS_LED":
                color_dict = {
                    self.STATUS_LED_COLOR_GREEN: 0x10,
                    self.STATUS_LED_COLOR_AMBER: 0x20,
                    self.STATUS_LED_COLOR_OFF: 0x30
                }
                
                if device_name == "SYS_LED":
                    return self._api_helper.cpld_lpc_write(0xA162, color_dict.get(color, 0x30))
                else:
                    return self._api_helper.cpld_lpc_write(0xA163, color_dict.get(color, 0x30))
            elif device_name == "FANTRAY1_LED":
                return self._fan_list[0].set_status_led(color)
            elif device_name == "FANTRAY2_LED":
                return self._fan_list[1].set_status_led(color)
            elif device_name == "FANTRAY3_LED":
                return self._fan_list[2].set_status_led(color)
            elif device_name == "PSU1_LED":
                return self._psu_list[0].set_status_led(color)
            elif device_name == "PSU2_LED":
                return self._psu_list[1].set_status_led(color)
            elif device_name == "PSU3_LED":
                return self._psu_list[2].set_status_led(color)
            elif device_name == "PSU4_LED":
                return self._psu_list[3].set_status_led(color)
            else:
                return self.STATUS_LED_COLOR_OFF
        else:    
            return PddfChassis.set_system_led(self, device_name, color)      

    def get_system_led(self, device_name):
        if self._api_helper.with_bmc():                 
            if device_name == "DIAG_LED" or device_name == "SYS_LED":
                if device_name == "SYS_LED":
                    reg = 0xA162
                else:
                    reg = 0xA163
                    
                status, result = self._api_helper.cpld_lpc_read(reg)
                if status == True:
                    result = int(result, 16) & 0xf0
                else:
                    result = 0x30

                status_led = {
                    0x30: self.STATUS_LED_COLOR_OFF,
                    0x10: self.STATUS_LED_COLOR_GREEN,
                    0x20: self.STATUS_LED_COLOR_AMBER,
                }
                
                return status_led.get(result, self.STATUS_LED_COLOR_OFF)
            elif device_name == "FANTRAY1_LED":
                return self._fan_list[0].get_status_led()
            elif device_name == "FANTRAY2_LED":
                return self._fan_list[1].get_status_led()
            elif device_name == "FANTRAY3_LED":
                return self._fan_list[2].get_status_led()
            elif device_name == "PSU1_LED":
                return self._psu_list[0].get_status_led()
            elif device_name == "PSU2_LED":
                return self._psu_list[1].get_status_led()
            elif device_name == "PSU3_LED":
                return self._psu_list[2].get_status_led()
            elif device_name == "PSU4_LED":
                return self._psu_list[3].get_status_led()
            else:
                return self.STATUS_LED_COLOR_OFF
        else:
            return PddfChassis.get_system_led(self, device_name)
            
    def set_status_led(self, color):
        return self.set_system_led("DIAG_LED", color)
        
    def get_status_led(self):
        """
        Gets the state of the alarm status LED
        Returns:
            A string, one of the predefined STATUS_LED_COLOR_* strings above

        Note:
            STATUS_LED_COLOR_GREEN = "green"
            STATUS_LED_COLOR_AMBER = "amber"
            STATUS_LED_COLOR_RED = "red"
            STATUS_LED_COLOR_OFF = "off"
        """
        return self.get_system_led("DIAG_LED")

    def get_port_or_cage_type(self, index):
        if index in range(1, 64+1):
            return SfpBase.SFP_PORT_TYPE_BIT_OSFP
        elif index in range(65, 66+1):
            return SfpBase.SFP_PORT_TYPE_BIT_SFP28
        else:
            raise NotImplementedError

    def _get_transceiver_presence(self):

        transceiver_presence = {}
        for port in range(len(self._sfp_list)):
            port_status = self.get_sfp(port+1).get_presence()
            transceiver_presence[port] = port_status

        return transceiver_presence

    def get_change_event(self, timeout=0):
        """
        Returns a nested dictionary containing all devices which have
        experienced a change at chassis level

        Args:
            timeout: Timeout in milliseconds (optional). If timeout == 0,
                this method will block until a change is detected.

        Returns:
            (bool, dict):
                - True if call successful, False if not;
                - A nested dictionary where key is a device type,
                  value is a dictionary with key:value pairs in the
                  format of {'device_id':'device_event'},
                  where device_id is the device ID for this device and
                        device_event,
                             status='1' represents device inserted,
                             status='0' represents device removed.
                  Ex. {'fan':{'0':'0', '2':'1'}, 'sfp':{'11':'0'}}
                      indicates that fan 0 has been removed, fan 2
                      has been inserted and sfp 11 has been removed.
        """
        port_dict = {}
        ret_dict = {'sfp': port_dict}
        forever = False

        if timeout == 0:
            forever = True
        elif timeout > 0:
            timeout = timeout / float(1000) # Convert to secs
        else:
            return False, ret_dict # Incorrect timeout

        while True:
            if forever:
                timer = self.POLL_INTERVAL
            else:
                timer = min(timeout, self.POLL_INTERVAL)
                start_time = time.time()

            time.sleep(timer)
            cur_presence = self._get_transceiver_presence()
            changed = False

            for port in range(len(self._sfp_list)):
                if cur_presence[port] != self._transceiver_presence[port]:
                    # qsfp_modprs True => optics is inserted
                    if cur_presence[port]:
                        port_dict[port] = '1'
                    # qsfp_modprs False => optics is removed
                    else:
                        port_dict[port] = '0'
                    changed = True

            if changed:
                self._transceiver_presence = cur_presence
                break

            if not forever:
                elapsed_time = time.time() - start_time
                timeout = round(timeout - elapsed_time, 3)
                if timeout <= 0:
                    break

        return True, ret_dict
