import os

try:
    from sonic_platform_pddf_base.pddf_fan import PddfFan
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")


class Fan(PddfFan):
    """PDDF Platform-Specific Fan class"""

    def __init__(self, tray_idx, fan_idx=0, pddf_data=None, pddf_plugin_data=None, is_psu_fan=False, psu_index=0):
        # idx is 0-based
        PddfFan.__init__(self, tray_idx, fan_idx, pddf_data, pddf_plugin_data, is_psu_fan, psu_index)

    def get_presence(self):
        """
          Retrieves the presence of fan
        """
        if self.is_psu_fan:
            return super().get_presence()
        return super().get_presence() and self.get_status()

    def get_direction(self):
        """
          Retrieves the direction of fan

          Returns:
               A string, either FAN_DIRECTION_INTAKE or FAN_DIRECTION_EXHAUST
               depending on fan direction
               Or N/A if fan removed or abnormal
        """
        if not self.get_status():
           return 'N/A'

        return super().get_direction()


    def get_target_speed(self):
        """
        Retrieves the target (expected) speed of the fan

        Returns:
            An integer, the percentage of full fan speed, in the range 0 (off)
                 to 100 (full speed)
        """
        target_speed = 0
        if self.is_psu_fan:
            # Target speed not usually supported for PSU fans
            raise NotImplementedError
        else:
            speed_rpm = self.get_speed_rpm()
            max_fan_rpm = eval(self.plugin_data['FAN']['FAN_MAX_RPM_SPEED'])
            speed_percentage = round(int((speed_rpm * 100) / max_fan_rpm))
            target_speed = speed_percentage

        return target_speed

    def get_speed(self):
        """
        Retrieves the speed of fan as a percentage of full speed

        Returns:
            An integer, the percentage of full fan speed, in the range 0 (off)
                 to 100 (full speed)
        """
        if self.is_psu_fan:
            attr = "psu_fan{}_speed_rpm".format(self.fan_index)
            device = "PSU{}".format(self.fans_psu_index)
            output = self.pddf_obj.get_attr_name_output(device, attr)
            if not output:
                return 0

            output['status'] = output['status'].rstrip()
            if output['status'].isalpha():
                return 0
            else:
                speed = int(float(output['status']))

            max_speed = int(self.plugin_data['PSU']['PSU_FAN_MAX_SPEED'])
            speed_percentage = round((speed*100)/max_speed)
            return speed_percentage
        else:
            # Get fan rpm instead of fan pwm through ipmitool
            idx = (self.fantray_index-1)*self.platform['num_fans_pertray'] + self.fan_index
            attr = "fan" + str(idx) + "_pwm"
            output = self.pddf_obj.get_attr_name_output("FAN-CTRL", attr)

            if not output:
                return 0

            output['status'] = output['status'].rstrip()
            if output['status'].isalpha():
                return 0
            else:
                speed = int(float(output['status']))

            max_speed = int(self.plugin_data['FAN']['FAN_MAX_RPM_SPEED'])
            speed_percentage = round((speed*100)/max_speed)

            return speed_percentage

    def set_speed(self, speed):
        """
        Sets the fan speed

        Args:
            speed: An integer, the percentage of full fan speed to set fan to,
                   in the range 0 (off) to 100 (full speed)

        Returns:
            A boolean, True if speed is set successfully, False if not
        """
        if self.is_psu_fan:
            print("Setting PSU fan speed is not allowed")
            return False
        else:
            if speed < 0 or speed > 100:
                print("Error: Invalid speed %d. Please provide a valid speed percentage" % speed)
                return False

            if 'duty_cycle_to_pwm' not in self.plugin_data['FAN']:
                print("Setting fan speed is not allowed !")
                return False
            else:
                duty_cycle_to_pwm = eval(self.plugin_data['FAN']['duty_cycle_to_pwm'])
                pwm = int(round(duty_cycle_to_pwm(speed)))

                if speed == 0:
                    # Enable FCS auto control mode
                    bmc_cmd = "ipmitool raw 0x3a 0x26 0x1 0x1"
                else:
                    bmc_cmd = "ipmitool raw 0x3a 0x26 0x1 0x0 && ipmitool raw 0x3a 0x26 0x2 0xfe {}".format(hex(pwm))
                try:
                    p = os.popen(bmc_cmd)
                    p.close()
                except IOError:
                    return False

                return True
