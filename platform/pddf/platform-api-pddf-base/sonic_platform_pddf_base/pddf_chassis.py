#############################################################################
# PDDF
# Module contains an implementation of SONiC PDDF Chassis Base API and
# provides the chassis information
#
#############################################################################

try:
    import sys
    import syslog
    from sonic_platform_base.chassis_base import ChassisBase
    from sonic_platform.sfp import Sfp
    from sonic_platform.psu import Psu
    from sonic_platform.fan_drawer import FanDrawer
    from sonic_platform.thermal import Thermal
    from sonic_platform.eeprom import Eeprom
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")


class PddfChassis(ChassisBase):
    """
    PDDF Generic Chassis class
    """
    pddf_obj = {}
    plugin_data = {}

    def __init__(self, pddf_data=None, pddf_plugin_data=None):

        ChassisBase.__init__(self)

        self.pddf_obj = pddf_data if pddf_data else None
        self.plugin_data = pddf_plugin_data if pddf_plugin_data else None
        if not self.pddf_obj or not self.plugin_data:
            try:
                from . import pddfapi
                import json
                self.pddf_obj = pddfapi.PddfApi()
                with open('/usr/share/sonic/platform/pddf/pd-plugin.json') as pd:
                    self.plugin_data = json.load(pd)
            except Exception as e:
                raise Exception("Error: Unable to load PDDF JSON data - %s" % str(e))

        self.platform_inventory = self.pddf_obj.get_platform()

        # Initialize EEPROM
        try:
            self._eeprom = Eeprom(self.pddf_obj, self.plugin_data)
        except Exception as err:
            syslog.syslog(syslog.LOG_ERR, "Unable to initialize syseeprom - {}".format(repr(err)))
            # Dont exit as we dont want failure in loading other components


        # FANs
        for i in range(self.platform_inventory['num_fantrays']):
            fandrawer = FanDrawer(i, self.pddf_obj, self.plugin_data)
            self._fan_drawer_list.append(fandrawer)
            self._fan_list.extend(fandrawer._fan_list)

        # PSUs
        for i in range(self.platform_inventory['num_psus']):
            psu = Psu(i, self.pddf_obj, self.plugin_data)
            self._psu_list.append(psu)

        # OPTICs
        for index in range(self.platform_inventory['num_ports']):
            sfp = Sfp(index, self.pddf_obj, self.plugin_data)
            self._sfp_list.append(sfp)

        # THERMALs
        for i in range(self.platform_inventory['num_temps']):
            thermal = Thermal(i, self.pddf_obj, self.plugin_data)
            self._thermal_list.append(thermal)

        # Component firmware version initialization
        if 'num_components' in self.platform_inventory:
           from sonic_platform.component import Component
           for i in range(self.platform_inventory['num_components']):
               component = Component(i, self.pddf_obj, self.plugin_data)
               self._component_list.append(component)

        # SYSTEM LED Test Cases
        """
        #comment out test cases
        sys_led_list= { "LOC":0,
                "DIAG":0,
                "FAN":0,
                "SYS":0,
                "PSU1":0,
                "PSU2":1
                  }

        for led in sys_led_list:
            color=self.get_system_led(led, sys_led_list[led])
            print color

        self.set_system_led("LOC_LED","STATUS_LED_COLOR_GREEN")
        color=self.get_system_led("LOC_LED")
        print "Set Green: " + color
        self.set_system_led("LOC_LED", "STATUS_LED_COLOR_OFF")
        color=self.get_system_led("LOC_LED")
        print "Set off: " + color
        """

    def get_name(self):
        """
        Retrieves the name of the chassis
        Returns:
            string: The name of the chassis
        """
        return self._eeprom.modelstr()

    def get_presence(self):
        """
        Retrieves the presence of the chassis
        Returns:
            bool: True if chassis is present, False if not
        """
        return True

    def get_model(self):
        """
        Retrieves the model number (or part number) of the chassis
        Returns:
            string: Model/part number of chassis
        """
        return self._eeprom.part_number_str()

    def get_serial(self):
        """
        Retrieves the serial number of the chassis (Service tag)
        Returns:
            string: Serial number of chassis
        """
        return self._eeprom.serial_str()

    def get_status(self):
        """
        Retrieves the operational status of the chassis
        Returns:
            bool: A boolean value, True if chassis is operating properly
            False if not
        """
        return True

    def get_base_mac(self):
        """
        Retrieves the base MAC address for the chassis

        Returns:
            A string containing the MAC address in the format
            'XX:XX:XX:XX:XX:XX'
        """
        return self._eeprom.base_mac_addr()

    def get_serial_number(self):
        """
        Retrieves the hardware serial number for the chassis

        Returns:
            A string containing the hardware serial number for this
            chassis.
        """
        return self._eeprom.serial_number_str()

    def get_system_eeprom_info(self):
        """
        Retrieves the full content of system EEPROM information for the chassis
        Returns:
            A dictionary where keys are the type code defined in
            OCP ONIE TlvInfo EEPROM format and values are their corresponding
            values.
        """
        return self._eeprom.system_eeprom_info()

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
        hw_reboot_cause = ""
        import os
        if os.path.exists('/sys/class/watchdog/watchdog0/bootstatus'):
            try:
                with open("/sys/class/watchdog/watchdog0/bootstatus", "r") as f:
                    hw_reboot_cause = f.read().strip('\n')
                if hw_reboot_cause == "32":
                    reboot_cause = self.REBOOT_CAUSE_WATCHDOG
                    description = 'Hardware Watchdog Reset'
                    return (reboot_cause, description)
            except Exception as e:
                raise Exception('Error while trying to find the HW reboot cause - {}'.format(str(e)))

        elif os.path.exists('/sys/class/watchdog/watchdog0/reboot_reason'):
            try:
                with open("/sys/class/watchdog/watchdog0/reboot_reason", "r") as f:
                    hw_reboot_cause = f.read().strip('\n')

                if hw_reboot_cause == "2":
                    reboot_cause = self.REBOOT_CAUSE_WATCHDOG
                    description = 'Hardware Watchdog Reset'
                    return (reboot_cause, description)
            except Exception as e:
                raise Exception('Error while trying to find the HW reboot cause - {}'.format(str(e)))

        else:
            syslog.syslog(syslog.LOG_INFO, "Watchdog is not supported on this platform")

        reboot_cause = self.REBOOT_CAUSE_NON_HARDWARE
        description = 'Unknown reason'

        return (reboot_cause, description)

    ##############################################
    # Component methods
    ##############################################
    def get_component_name_list(self):
        """
        Retrieves a list of the names of components available on the chassis (e.g., BIOS, CPLD, FPGA, etc.)

        Returns:
            A list containing the names of components available on the chassis
        """
        return self._component_name_list

    ##############################################
    # Module methods
    ##############################################
    # All module methods are part of chassis_base.py
    # if they need to be overwritten, define them here

    ##############################################
    # Fan methods
    ##############################################
    # All fan methods are part of chassis_base.py
    # if they need to be overwritten, define them here

    ##############################################
    # PSU methods
    ##############################################
    # All psu methods are part of chassis_base.py
    # if they need to be overwritten, define them here

    ##############################################
    # THERMAL methods
    ##############################################
    # All thermal methods are part of chassis_base.py
    # if they need to be overwritten, define them here

    ##############################################
    # SFP methods
    ##############################################
    # All sfp methods are part of chassis_base.py
    # if they need to be overwritten, define them here

    ##############################################
    # All Front Panel System LED  methods
    ##############################################
    # APIs used by PDDF (pddf_ledutil) to allow debug front panel
    # system LED and fantray LED issues
    def set_system_led(self, led_device_name, color):
        """
        Sets the color of an LED device in PDDF
        Args:
           led_device_name: a pre-defined LED device name list used in pddf-device.json.
           color: A string representing the color with which to set a LED
        Returns:
           bool: True if the LED state is set successfully, False if not
        """
        result, msg = self.pddf_obj.set_system_led_color(led_device_name, color)
        if not result and msg:
            print(msg)
        return (result)

    def get_system_led(self, led_device_name):
        """
        Gets the color of an LED device in PDDF
        Returns:
            string: color of LED or message if failed.
        """
        result, output = self.pddf_obj.get_system_led_color(led_device_name)
        return (output)


    ##############################################
    # System LED methods
    ##############################################

    def set_status_led(self, led_type, color):
        """
        Sets the state of the system LED
        Args:
            led_type: A string representing the type of LED
            color: A string representing the color with which to set the
                   system LED
        Returns:
            bool: True if system LED state is set successfully, False if not
        """
        if (led_type is self.CHASSIS_LED_TYPE_FAN) and ('fan_master_led_color' in self.plugin_data['FAN']):
            led_color_map = self.plugin_data['FAN']['fan_master_led_color']['colmap']
            if color in led_color_map:
                # change the color properly
                new_color = led_color_map[color]
                color = new_color
        result, msg = self.pddf_obj.set_system_led_color(led_type, color)
        return (result)

    def get_status_led(self, led_type):
        """
        Gets the state of the system LED
        Args:
            led_type: A string representing the type of LED
        Returns:
            A string, one of the valid LED color strings which could be vendor
            specified.
        """
        result, output = self.pddf_obj.get_system_led_color(led_type)
        return (output)


    ##############################################
    # Other methods
    ##############################################

    def get_watchdog(self):
        """
        Retreives hardware watchdog device on this chassis

        Returns:
            An object derived from WatchdogBase representing the hardware
            watchdog device
        """
        try:
            if self._watchdog is None:
                from sonic_platform.watchdog import Watchdog
                # Create the watchdog Instance
                self._watchdog = Watchdog()

        except Exception as e:
            syslog.syslog(syslog.LOG_ERR, "Fail to load watchdog due to {}".format(e))
        return self._watchdog
