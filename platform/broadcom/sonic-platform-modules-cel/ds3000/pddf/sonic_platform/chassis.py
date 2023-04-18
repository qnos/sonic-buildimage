#############################################################################
# PDDF
# Module contains an implementation of SONiC Chassis API
#
#############################################################################

try:
    import os
    import subprocess
    from .event import XcvrEvent
    from sonic_py_common import logger
    from sonic_platform_pddf_base.pddf_chassis import PddfChassis
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")

CPLD_VERSION_CMD = "i2cget -y -f 103 0x0d 0x00 b"
REBOOT_REASON_CMD = "i2cget -y -f 103 0x0d 0x06 b"
SYS_LED_COLOR_SET_CMD = "ipmitool raw 0x3a 0x0a 0x00 {}"
LED_CTRL_MODE_GET_CMD = "ipmitool raw 0x3a 0x0f 0x01"

SYSLOG_IDENTIFIER = "Chassis"
helper_logger = logger.Logger(SYSLOG_IDENTIFIER)

class Chassis(PddfChassis):
    """
    PDDF Platform-specific Chassis class
    """
    # SYS LED color defines
    SYS_LED_COLOR_OFF = 0x0
    SYS_LED_COLOR_AMBER = 0x1
    SYS_LED_COLOR_AMBER_BLINK = 0x3
    SYS_LED_COLOR_AMBER_BLINK_4HZ = 0x2
    SYS_LED_COLOR_AMBER_BLINK_1HZ = 0x3
    SYS_LED_COLOR_GREEN = 0x4
    SYS_LED_COLOR_GREEN_BLINK = 0x6
    SYS_LED_COLOR_GREEN_BLINK_4HZ = 0x5
    SYS_LED_COLOR_GREEN_BLINK_1HZ = 0x6

    def __init__(self, pddf_data=None, pddf_plugin_data=None):
        PddfChassis.__init__(self, pddf_data, pddf_plugin_data)
        self.baseboard_cpld_ver = 0
        if os.getuid() == 0:
            status, cpld_ver = self._getstatusoutput(CPLD_VERSION_CMD)
        else:
            status, cpld_ver = self._getstatusoutput("sudo " + CPLD_VERSION_CMD)
        if status != 0:
            pass
        self.baseboard_cpld_ver = int(cpld_ver, 16)

    def _getstatusoutput(self, cmd):
        try:
            data = subprocess.check_output(cmd, shell=True,
                    universal_newlines=True, stderr=subprocess.STDOUT)
            status = 0
        except subprocess.CalledProcessError as ex:
            data = ex.output
            status = ex.returncode
        if data[-1:] == '\n':
            data = data[:-1]
        return status, data

    def initizalize_system_led(self):
        """
        This function is not defined in chassis base class,
        system-health command would invoke chassis.initizalize_system_led(),
        add this stub function just to let the command sucessfully execute
        """
        pass

    def get_status_led(self):
        """
        Gets the state of the system LED
        Args:
            None
        Returns:
            A string, one of the valid LED color strings which could be vendor
            specified.
        """
        return PddfChassis.get_status_led(self, "SYS_LED")

    def set_status_led(self, color):
        """
        Sets the state of the system LED
        Args:
            color: A string representing the color with which to set the
                   system LED
        Returns:
            bool: True if system LED state is set successfully, False if not
        """
        color_val = self.SYS_LED_COLOR_GREEN
        if color == "off":
            color_val = self.SYS_LED_COLOR_OFF
        elif color == "amber":
            color_val = self.SYS_LED_COLOR_AMBER
        elif color == "amber_blink":
            color_val = self.SYS_LED_COLOR_AMBER_BLINK
        elif color == "amber_blink_4hz":
            color_val = self.SYS_LED_COLOR_AMBER_BLINK_4HZ
        elif color == "amber_blink_1hz":
            color_val = self.SYS_LED_COLOR_AMBER_BLINK_1HZ
        elif color == "green":
            color_val = self.SYS_LED_COLOR_GREEN
        elif color == "green_blink":
            color_val = self.SYS_LED_COLOR_GREEN_BLINK
        elif color == "green_blink_4hz":
            color_val = self.SYS_LED_COLOR_GREEN_BLINK_4HZ
        elif color == "green_blink_1hz":
            color_val = self.SYS_LED_COLOR_GREEN_BLINK_1HZ
        else:
            helper_logger.log_error("SYS LED color {} not support!".format(color))
            return False

        cmd = SYS_LED_COLOR_SET_CMD.format(color_val)
        led_mode_cmd = LED_CTRL_MODE_GET_CMD
        if os.getuid() != 0:
            cmd = "sudo " + cmd
            led_mode_cmd = "sudo " + led_mode_cmd
        status, mode = self._getstatusoutput(led_mode_cmd)
        # led take automatic control mode, led not settable
        if status != 0 or mode.strip() == "01":
            helper_logger.log_info("SYS LED takes automatic ctrl mode!")
            return False
        status, _ = self._getstatusoutput(cmd)
        if status != 0:
            return False
        return True

    def get_sfp(self, index):
        """
        Retrieves sfp represented by (1-based) index <index>
        For Quanta the index in sfputil.py starts from 1, so override
        Args:
            index: An integer, the index (1-based) of the sfp to retrieve.
            The index should be the sequence of a physical port in a chassis,
            starting from 1.
        Returns:
            An object dervied from SfpBase representing the specified sfp
        """
        sfp = None

        try:
            if (index == 0):
                raise IndexError
            sfp = self._sfp_list[index-1]
        except IndexError:
            sys.stderr.write("override: SFP index {} out of range (1-{})\n".format(
                index, len(self._sfp_list)))

        return sfp
    # Provide the functions/variables below for which implementation is to be overwritten

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
        # Newer baseboard CPLD to get reboot cause from CPLD register
        if self.baseboard_cpld_ver >= 0x18:
            hw_reboot_cause = ""
            if os.getuid == 0:
                status, hw_reboot_cause = self._getstatusoutput(REBOOT_REASON_CMD)
            else:
                status, hw_reboot_cause = self._getstatusoutput("sudo " + REBOOT_REASON_CMD)
            if status != 0:
                pass

            if hw_reboot_cause == "0x99":
                reboot_cause = self.REBOOT_CAUSE_THERMAL_OVERLOAD_ASIC
                description = 'ASIC Overload Reboot'
            elif hw_reboot_cause == "0x88":
                reboot_cause = self.REBOOT_CAUSE_THERMAL_OVERLOAD_CPU
                description = 'CPU Overload Reboot'
            elif hw_reboot_cause == "0x77":
                reboot_cause = self.REBOOT_CAUSE_WATCHDOG
                description = 'Hardware Watchdog Reset'
            elif hw_reboot_cause == "0x55":
                reboot_cause = self.REBOOT_CAUSE_HARDWARE_OTHER
                description = 'CPU Cold Reset'
            elif hw_reboot_cause == "0x44":
                reboot_cause = self.REBOOT_CAUSE_NON_HARDWARE
                description = 'CPU Warm Reset'
            elif hw_reboot_cause == "0x33":
                reboot_cause = self.REBOOT_CAUSE_NON_HARDWARE
                description = 'Soft-Set Cold Reset'
            elif hw_reboot_cause == "0x22":
                reboot_cause = self.REBOOT_CAUSE_NON_HARDWARE
                description = 'Soft-Set Warm Reset'
            elif hw_reboot_cause == "0x11":
                reboot_cause = self.REBOOT_CAUSE_POWER_LOSS
                description = 'Power Off Reset'
            elif hw_reboot_cause == "0x00":
                reboot_cause = self.REBOOT_CAUSE_POWER_LOSS
                description = 'Power Cycle Reset'
            else:
                reboot_cause = self.REBOOT_CAUSE_HARDWARE_OTHER
                description = 'Hardware reason'

            return (reboot_cause, description)
        else:
            return PddfChassis.get_reboot_cause()

    def get_watchdog(self):
        """
        Retreives hardware watchdog device on this chassis

        Returns:
            An object derived from WatchdogBase representing the hardware
            watchdog device
        """
        try:
            if self._watchdog is None:
                if self.baseboard_cpld_ver >= 0x18:
                    from sonic_platform.cpld_watchdog import Watchdog
                    # Create the watchdog Instance from cpld watchdog
                    self._watchdog = Watchdog()
                else:
                    from sonic_platform.watchdog import Watchdog
                    # Create the watchdog Instance
                    self._watchdog = Watchdog()

        except Exception as e:
            helper_logger.log_error("Fail to load watchdog due to {}".format(e))
        return self._watchdog

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
