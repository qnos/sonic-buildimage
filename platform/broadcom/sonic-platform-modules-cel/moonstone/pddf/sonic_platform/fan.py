#!/usr/bin/env python

#############################################################################
# Celestica
#
# Component contains an implementation of SONiC Platform Base API and
# provides the fan management function
#
#############################################################################

try:
    from sonic_platform_pddf_base.pddf_fan import PddfFan
    from .helper import APIHelper       
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")


class Fan(PddfFan):
    """PDDF Platform-Specific Fan class"""

    def __init__(self, tray_idx, fan_idx=0, pddf_data=None, pddf_plugin_data=None, is_psu_fan=False, psu_index=0):
        # idx is 0-based 
        PddfFan.__init__(self, tray_idx, fan_idx, pddf_data, pddf_plugin_data, is_psu_fan, psu_index)
        self._api_helper = APIHelper()
        self.target_speed = 100
        self.fan_fru_id = [215, 142, 30]

    # Provide the functions/variables below for which implementation is to be overwritten

    def get_presence(self):
        if self._api_helper.with_bmc():
            if self.is_psu_fan:
                return True
            else:
                reg = [0xA141, 0xA141, 0xA145, 0xA145, 0xA149, 0xA149]
                idx = (self.fantray_index-1)*self.platform['num_fans_pertray'] + self.fan_index
                
                status, result = self._api_helper.cpld_lpc_read(reg[idx - 1])
                
                if (int(result, 16) & 0x4 == 0x0) and status == True:
                    return True
                else:
                    return False
        else:
            return PddfFan.get_presence(self)

    def get_direction(self):
        """
        Retrieves the direction of fan

        Returns:
            A string, either FAN_DIRECTION_INTAKE or FAN_DIRECTION_EXHAUST
            depending on fan direction
        """
        return self.FAN_DIRECTION_INTAKE

    def get_speed_tolerance(self):
        """
        Retrieves the speed tolerance of the fan
        Returns:
            An integer, the percentage of variance from target speed which is
            considered tolerable
        """
        if self.get_presence():
            tolerance = 20
        else:
            tolerance = 0

        return tolerance

    def get_speed(self):
        """
        Retrieves the speed of fan as a percentage of full speed

        Returns:
            An integer, the percentage of full fan speed, in the range 0 (off)
                 to 100 (full speed)
        """
        if self._api_helper.with_bmc():
            if self.is_psu_fan:
                return PddfFan.get_speed(self)
            else:
                # TODO This calculation should change based on MAX FAN SPEED
                reg = [0xA140, 0xA140, 0xA144, 0xA144, 0xA148, 0xA148]
                idx = (self.fantray_index-1)*self.platform['num_fans_pertray'] + self.fan_index
                
                status, fpwm = self._api_helper.cpld_lpc_read(reg[idx - 1])

                pwm_to_dc = eval(self.plugin_data['FAN']['pwm_to_duty_cycle'])
                speed_percentage = int(round(pwm_to_dc(int(fpwm, 16))))
                self.target_speed = speed_percentage

                return speed_percentage
        else:
            return PddfFan.get_speed(self)
            
    def get_speed_rpm(self):
        """
        Retrieves the speed of fan in RPM

        Returns:
            An integer, Speed of fan in RPM
        """
        if self._api_helper.with_bmc():
            if self.is_psu_fan:
                return PddfFan.get_speed_rpm(self)
            else:
                reg = [0xA142, 0xA143, 0xA146, 0xA147, 0xA14A, 0xA14B]
                idx = (self.fantray_index-1)*self.platform['num_fans_pertray'] + self.fan_index
                
                status, fpwm = self._api_helper.cpld_lpc_read(reg[idx - 1])

                if self.fan_index == 1:
                    rpm_speed = 69 * int(fpwm, 16)
                else:
                    rpm_speed = 78 * int(fpwm, 16)
                
                return rpm_speed
        else:
            return PddfFan.get_speed_rpm(self)
            
    def get_speed_tolerance(self):
        """
        Retrieves the speed tolerance of the fan

        Returns:
            An integer, the percentage of variance from target speed which is
                 considered tolerable
        """
        return 20

    def get_target_speed(self):
        """
        Retrieves the target (expected) speed of the fan

        Returns:
            An integer, the percentage of full fan speed, in the range 0 (off)
                 to 100 (full speed)
        """
        return self.target_speed

    def set_speed(self, speed):
        """
        Sets the fan speed
        
        Args:
            speed: An integer, the percentage of full fan speed to set fan to,
                   in the range 0 (off) to 100 (full speed)

        Returns:
            A boolean, True if speed is set successfully, False if not
        """
        
        if self._api_helper.with_bmc():
            if self.is_psu_fan:
                result = False
            else:
                reg = [0xA140, 0xA140, 0xA144, 0xA144, 0xA148, 0xA148]
                
                hex_value = int(speed * 255 / 100)
                idx = (self.fantray_index-1)*self.platform['num_fans_pertray'] + self.fan_index
                
                result = self._api_helper.cpld_lpc_write(reg[idx - 1], hex_value)
        else:
            result = PddfFan.set_speed(self, speed)

        if result: self.target_speed = speed
        return result

    def set_status_led(self, color):
        if self._api_helper.with_bmc():
            if self.is_psu_fan:
                return False

            bmc_color_dict = {
                self.STATUS_LED_COLOR_GREEN: 0x5,
                self.STATUS_LED_COLOR_AMBER: 0x6,
                self.STATUS_LED_COLOR_OFF: 0x4
            }

            reg = [0xA137, 0xA137, 0xA138, 0xA138, 0xA139, 0xA139]
            idx = (self.fantray_index-1)*self.platform['num_fans_pertray'] + self.fan_index
         
            return self._api_helper.cpld_lpc_write(reg[idx - 1], bmc_color_dict.get(color, 0x0))
        else:
            color_dict = {
                self.STATUS_LED_COLOR_GREEN: "green",
                self.STATUS_LED_COLOR_AMBER: "amber",
                self.STATUS_LED_COLOR_OFF: "off"
            }
            return PddfFan.set_status_led(self, color_dict.get(color, "off"))

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
            if self.is_psu_fan:
                return False

            reg = [0xA141, 0xA141, 0xA145, 0xA145, 0xA149, 0xA149]
            idx = (self.fantray_index-1)*self.platform['num_fans_pertray'] + self.fan_index

            status, result = self._api_helper.cpld_lpc_read(reg[idx - 1])
            if status == True:
                result = int(result, 16) & 0x3
            else:
                result = 0

            status_led = {
                0: self.STATUS_LED_COLOR_OFF,
                1: self.STATUS_LED_COLOR_GREEN,
                2: self.STATUS_LED_COLOR_AMBER,
            }.get(result, self.STATUS_LED_COLOR_OFF)
            
        else:
            result =  PddfFan.get_status_led(self)
            
            status_led = {
                "off": self.STATUS_LED_COLOR_OFF,
                "green": self.STATUS_LED_COLOR_GREEN,
                "amber": self.STATUS_LED_COLOR_AMBER,
            }.get(result, self.STATUS_LED_COLOR_OFF)

        return status_led

    def get_model(self):
        """
        Retrieves the model number (or part number) of the device
        Returns:
            string: Model/part number of device
        """
        if self.is_psu_fan:
            return "Unknown"

        model = "Unknown"
        if self._api_helper.with_bmc():     
            ipmi_fru_idx = self.fan_fru_id[self.fantray_index -1]
            status, raw_model = self._api_helper.ipmi_fru(ipmi_fru_idx, "Board Part Number")

            fru_pn_list = raw_model.split()
            if len(fru_pn_list) > 4:
                model = fru_pn_list[4]

        return model

    def get_serial(self):
        """
        Retrieves the serial number of the device
        Returns:
            string: Serial number of device
        """
        if self.is_psu_fan:
            return "Unknown"

        serial = "Unknown"
        if self._api_helper.with_bmc():         
            ipmi_fru_idx = self.fan_fru_id[self.fantray_index -1]
            status, raw_model = self._api_helper.ipmi_fru(ipmi_fru_idx, "Board Serial")

            fru_sr_list = raw_model.split()
            if len(fru_sr_list) > 3:
                serial = fru_sr_list[3]

        return serial
