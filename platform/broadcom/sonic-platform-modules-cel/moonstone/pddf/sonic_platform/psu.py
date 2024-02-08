#!/usr/bin/env python

#############################################################################
# Celestica
#
# Component contains an implementation of SONiC Platform Base API and
# provides the psu management function
#
#############################################################################

try:
    from sonic_platform_pddf_base.pddf_psu import PddfPsu
    from .helper import APIHelper
except ImportError as e:
    raise ImportError (str(e) + "- required module not found")


class Psu(PddfPsu):
    """PDDF Platform-Specific PSU class"""

    def __init__(self, index, pddf_data=None, pddf_plugin_data=None):
        PddfPsu.__init__(self, index, pddf_data, pddf_plugin_data)
        self._api_helper = APIHelper()

    # Provide the functions/variables below for which implementation is to be overwritten

    def get_presence(self):

        idx = self.psu_index - 1
        status, result = self._api_helper.cpld_lpc_read(0xA160)

        if (int(result, 16) & (1 << (idx + 4)) == (1 << (idx + 4))) and status == True:
            return True
        else:
            return False

    def get_powergood_status(self):

        idx = self.psu_index - 1
        status, result = self._api_helper.cpld_lpc_read(0xA160)

        if (int(result, 16) & (1 << idx) == (1 << idx)) and status == True:
            return True
        else:
            return False

    def get_type(self):
        """
        Gets the type of the PSU

        Returns:
            A string, the type of PSU (AC/DC)
        """
        # This platform supports AC PSU
        return "AC"

    def get_revision(self):
        return "N/A"

    def set_status_led(self, color):
        if self._api_helper.with_bmc():
            bmc_color_dict = {
                self.STATUS_LED_COLOR_GREEN: 0x2,
                self.STATUS_LED_COLOR_AMBER: 0x1,
                self.STATUS_LED_COLOR_OFF: 0x3
            }

            reg = [0xA161, 0xA161, 0xA161, 0xA161, 0xA161, 0xA161]
            idx = self.psu_index - 1

            return self._api_helper.cpld_lpc_write(reg[idx], bmc_color_dict.get(color, 0x3))
        else:
            color_dict = {
                self.STATUS_LED_COLOR_GREEN: "green",
                self.STATUS_LED_COLOR_AMBER: "amber",
                self.STATUS_LED_COLOR_OFF: "off"
            }
            return PddfPsu.set_status_led(self, color_dict.get(color, "off"))

    def get_status_led(self):
        """
        Gets the state of the fan status LED
        Returns:
            A string, one of the predefined STATUS_LED_COLOR_* strings above

        Note:
            STATUS_LED_COLOR_GREEN = "green"
            STATUS_LED_COLOR_AMBER = "amber"
            STATUS_LED_COLOR_RED = "red"
            STATUS_LED_COLOR_OFF = "off"
        """
        if self._api_helper.with_bmc():

            reg = [0xA161, 0xA161, 0xA161, 0xA161, 0xA161, 0xA161]
            idx = self.psu_index - 1

            status, result = self._api_helper.cpld_lpc_read(reg[idx])
            if status == True:
                result = int(result, 16) & 0x3
            else:
                result = 0

            status_led = {
                0: self.STATUS_LED_COLOR_OFF,
                3: self.STATUS_LED_COLOR_OFF,
                1: self.STATUS_LED_COLOR_GREEN,
                2: self.STATUS_LED_COLOR_AMBER,
            }.get(result, self.STATUS_LED_COLOR_OFF)

        else:
            result =  PddfPsu.get_status_led(self)

            status_led = {
                "off": self.STATUS_LED_COLOR_OFF,
                "green": self.STATUS_LED_COLOR_GREEN,
                "amber": self.STATUS_LED_COLOR_AMBER,
            }.get(result, self.STATUS_LED_COLOR_OFF)

        return status_led
