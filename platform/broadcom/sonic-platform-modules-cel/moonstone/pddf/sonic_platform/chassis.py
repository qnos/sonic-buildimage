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
    from .event import XcvrEvent
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
        self.STATUS_LED_COLOR_AUTO = 'auto'
        self.STATUS_LED_COLOR_MIX_BLINK = 'mix_blink'
        self.STATUS_LED_COLOR_GREEN_BLINK = 'green_blink'
        self.STATUS_LED_COLOR_AMBER_BLINK = 'green_blink'
        self.STATUS_LED_COLOR_UNKNOWN = 'unknown'

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
        
    def get_revision(self):
        return self._eeprom.revision_str()
        
    @staticmethod
    def get_position_in_parent():
        return -1
        
    @staticmethod
    def is_replaceable():
        return True  

    def set_system_led(self, device_name, color):
        if device_name == "ALARM_LED" or device_name == "SYS_LED":
            color_dict = {
                self.STATUS_LED_COLOR_GREEN: 0x10,
                self.STATUS_LED_COLOR_AMBER: 0x20,
                self.STATUS_LED_COLOR_MIX_BLINK: 0x01,
                self.STATUS_LED_COLOR_GREEN_BLINK: 0x11,
                self.STATUS_LED_COLOR_AMBER_BLINK: 0x21,
                self.STATUS_LED_COLOR_OFF: 0x30
            }
            val = color_dict.get(color, 0xf)
            if val == 0xf: return False                
            if device_name == "SYS_LED":
                return self._api_helper.cpld_lpc_write(0xA162, val)
            else:
                return self._api_helper.cpld_lpc_write(0xA163, val)
        elif device_name == "PSU_Front_LED":
            color_dict = {
                self.STATUS_LED_COLOR_GREEN: 0x2,
                self.STATUS_LED_COLOR_AMBER: 0x1,
                self.STATUS_LED_COLOR_OFF: 0x3,
                self.STATUS_LED_COLOR_AUTO: 0x8
            }
            val = color_dict.get(color, 0x0)
            if val == 0x0: return False
            return self._api_helper.cpld_lpc_write(0xA161, val)
        elif device_name == "FAN_Front_LED":
            color_dict = {
                self.STATUS_LED_COLOR_GREEN: 0x2,
                self.STATUS_LED_COLOR_AMBER: 0x1,
                self.STATUS_LED_COLOR_OFF: 0x3,
                self.STATUS_LED_COLOR_AUTO: 0x8
            }
            val = color_dict.get(color, 0x0)
            if val == 0x0: return False
            return self._api_helper.cpld_lpc_write(0xA165, val)
        elif device_name == "FANTRAY1_LED":
            return self._fan_list[0].set_status_led(color)
        elif device_name == "FANTRAY2_LED":
            return self._fan_list[1].set_status_led(color)
        elif device_name == "FANTRAY3_LED":
            return self._fan_list[2].set_status_led(color)
        else:
            raise NotImplementedError   

    def get_system_led(self, device_name):               
        if device_name == "ALARM_LED" or device_name == "SYS_LED":
            if device_name == "SYS_LED":
                reg = 0xA162
            else:
                reg = 0xA163
                
            status, result = self._api_helper.cpld_lpc_read(reg)
            if status == True:
                result = int(result, 16) & 0x33
            else:
                return self.STATUS_LED_COLOR_UNKNOWN

            status_led = {
                0x30: self.STATUS_LED_COLOR_OFF,
                0x33: self.STATUS_LED_COLOR_OFF,
                0x10: self.STATUS_LED_COLOR_GREEN,
                0x20: self.STATUS_LED_COLOR_AMBER,
                0x00: self.STATUS_LED_COLOR_MIX_BLINK,
                0x01: self.STATUS_LED_COLOR_MIX_BLINK,
                0x02: self.STATUS_LED_COLOR_MIX_BLINK,
                0x03: self.STATUS_LED_COLOR_MIX_BLINK,
                0x11: self.STATUS_LED_COLOR_GREEN_BLINK,
                0x12: self.STATUS_LED_COLOR_GREEN_BLINK,
                0x21: self.STATUS_LED_COLOR_AMBER_BLINK,
                0x22: self.STATUS_LED_COLOR_AMBER_BLINK
            }
            
            return status_led.get(result, self.STATUS_LED_COLOR_UNKNOWN)
        if device_name == "PSU_Front_LED":
            status, result = self._api_helper.cpld_lpc_read(0xA161)
            if status == True:
                result = int(result, 16) & 0x3
            else:
                return self.STATUS_LED_COLOR_UNKNOWN

            status_led = {
                0x0: self.STATUS_LED_COLOR_OFF,
                0x3: self.STATUS_LED_COLOR_OFF,
                0x2: self.STATUS_LED_COLOR_GREEN,
                0x1: self.STATUS_LED_COLOR_AMBER,
            }
            return status_led.get(result)
        if device_name == "FAN_Front_LED":
            status, result = self._api_helper.cpld_lpc_read(0xA165)
            if status == True:
                result = int(result, 16) & 0x3
            else:
                return self.STATUS_LED_COLOR_UNKNOWN

            status_led = {
                0x0: self.STATUS_LED_COLOR_OFF,
                0x3: self.STATUS_LED_COLOR_OFF,
                0x2: self.STATUS_LED_COLOR_GREEN,
                0x1: self.STATUS_LED_COLOR_AMBER,
            }
            return status_led.get(result)
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
            raise NotImplementedError 
            
    def set_status_led(self, color):
        return self.set_system_led("ALARM_LED", color)
        
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
        return self.get_system_led("ALARM_LED")

    def get_port_or_cage_type(self, index):
        if index in range(1, 64+1):
            return SfpBase.SFP_PORT_TYPE_BIT_OSFP
        elif index in range(65, 66+1):
            return SfpBase.SFP_PORT_TYPE_BIT_SFP28
        else:
            raise NotImplementedError

    ##############################################################
    ###################### Event methods #########################
    ##############################################################
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
                  value is a dictionary with key:value pairs in the format of
                  {'device_id':'device_event'},
                  where device_id is the device ID for this device and
                        device_event,
                             status='1' represents device inserted,
                             status='0' represents device removed.
                  Ex. {'fan':{'0':'0', '2':'1'}, 'sfp':{'11':'0'}}
                      indicates that fan 0 has been removed, fan 2
                      has been inserted and sfp 11 has been removed.
        """
        # SFP event
        if self.get_num_sfps() == 0:
            for index in range(self.platform_inventory['num_ports']):
                sfp = Sfp(index, self.pddf_obj, self.plugin_data)
                self._sfp_list.append(sfp)

        succeed, sfp_event = XcvrEvent(self._sfp_list).get_xcvr_event(timeout)
        if succeed:
            return True, {'sfp': sfp_event}

        return False, {'sfp': {}}
