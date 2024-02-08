import os.path
import sys
sys.path.append('/usr/share/sonic/platform/plugins')
import pddfparse
import json

try:
    import time
    from ctypes import create_string_buffer
    from sonic_sfp.sfputilbase import SfpUtilBase
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")


class SfpUtil(SfpUtilBase):
    """Platform generic PDDF SfpUtil class"""

    _port_to_eeprom_mapping = {}
    _port_start = 0
    _port_end = 0
    _port_to_type_mapping = {}
    _qsfp_ports = []
    _sfp_ports = []

    def __init__(self):
        SfpUtilBase.__init__(self)
        global pddf_obj
        global plugin_data
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)) + '/../pddf/pd-plugin.json')) as pd:
            plugin_data = json.load(pd)

        pddf_obj = pddfparse.PddfParse()
        self.platform = pddf_obj.get_platform()
        self._port_start = 0
        self._port_end = self.get_num_ports()

        self._transceiver_presence = {}
        for port_num in range(self._port_start, self._port_end):
            device = "PORT" + "%d" % (port_num+1)
            port_eeprom_path = pddf_obj.get_path(device, "eeprom")
            self._port_to_eeprom_mapping[port_num] = port_eeprom_path
            port_type = pddf_obj.get_device_type(device)
            self._port_to_type_mapping[port_num] = port_type
            self.populate_port_type(port_num)
            self._transceiver_presence[port_num] = False
        self.POLL_INTERVAL = 1

    def get_num_ports(self):
        return int(self.platform['num_ports'])

    def is_valid_port(self, port_num):
        if port_num < self._port_start or port_num > self._port_end:
            return False
        else:
            return True

    def get_presence(self, port_num):
        if port_num < self._port_start or port_num > self._port_end:
            return False

        device = "PORT" + "%d" % (port_num+1)
        output = pddf_obj.get_attr_name_output(device, 'xcvr_present')
        if not output:
            return False

        #mode = output['mode']
        modpres = output['status'].rstrip()
        if 'XCVR' in plugin_data:
            if 'xcvr_present' in plugin_data['XCVR']:
                ptype = self._port_to_type_mapping[port_num]
                vtype = 'valmap-'+ptype
                if vtype in plugin_data['XCVR']['xcvr_present']:
                    vmap = plugin_data['XCVR']['xcvr_present'][vtype]
                    if modpres in vmap:
                        return vmap[modpres]
                    else:
                        return False
        # if plugin_data doesn't specify anything regarding Transceivers
        if modpres == '1':
            return True

        return False

    def populate_port_type(self, port):
        if self._port_to_type_mapping[port] == 'SFP' or self._port_to_type_mapping[port] == 'SFP28':
            self._sfp_ports.append(port)
        else
            self._qsfp_ports.append(port)

    @property
    def port_start(self):
        return self._port_start

    @property
    def port_end(self):
        return (self._port_end - 1)

    @property
    def port_to_eeprom_mapping(self):
        return self._port_to_eeprom_mapping

    @property
    def qsfp_ports(self):
        return self._qsfp_ports

    def reset(self, port_num):
        # Check for invalid port_num
        if port_num < self._port_start or port_num > self._port_end:
            return False

        if not self.get_presence(port_num):
            return False

        device = "PORT" + "%d" % (port_num+1)
        output = pddf_obj.get_attr_name_output(device, 'xcvr_reset')
        if not output:
            return False
        else:
            #mode = output['mode']
            status = int(output['status'].rstrip())

            if status == 1:
                return True
            else:
                return False

    def get_low_power_mode(self, port_num):
        # Check for invalid port_num
        if port_num < self._port_start or port_num > self._port_end:
            return False

        if not self.get_presence(port_num):
            return False

        device = "PORT" + "%d" % (port_num+1)
        output = pddf_obj.get_attr_name_output(device, 'xcvr_lpmode')
        if not output:
            if port_num not in self.qsfp_ports:
                return False  # Read from eeprom only for QSFP ports
            try:
                eeprom = None
                eeprom = open(self.port_to_eeprom_mapping[port_num], "rb")
                # check for valid connector type
                eeprom.seek(2)
                ctype = eeprom.read(1)
                if ctype in ['21', '23']:
                    return False

                eeprom.seek(93)
                lpmode = ord(eeprom.read(1))

                if ((lpmode & 0x3) == 0x3):
                    return True  # Low Power Mode if "Power override" bit is 1 and "Power set" bit is 1
                else:
                    # High Power Mode if one of the following conditions is matched:
                    # 1. "Power override" bit is 0
                    # 2. "Power override" bit is 1 and "Power set" bit is 0
                    return False
            except IOError as e:
                print("Error: unable to open file: %s" % str(e))
                return False
            finally:
                if eeprom is not None:
                    eeprom.close()
                    time.sleep(0.01)
        else:
            #mode = output['mode']
            status = int(output['status'].rstrip())

            if status == 1:
                return True
            else:
                return False

    def set_low_power_mode(self, port_num, lpmode):
        # Check for invalid port_num
        if port_num < self._port_start or port_num > self._port_end:
            return False

        if not self.get_presence(port_num):
            return False  # Port is not present, unable to set the eeprom

        device = "PORT" + "%d" % (port_num+1)
        port_ps = pddf_obj.get_path(device, "xcvr_lpmode")
        if port_ps is None:
            if port_num not in self.qsfp_ports:
                return False  # Write to eeprom only for QSFP ports
            try:
                eeprom = None
                eeprom = open(self.port_to_eeprom_mapping[port_num], "r+b")
                # check for valid connector type
                eeprom.seek(2)
                ctype = eeprom.read(1)
                if ctype in ['21', '23']:
                    return False

                # Fill in write buffer
                regval = 0x3 if lpmode else 0x1  # 0x3:Low Power Mode, 0x1:High Power Mode
                buffer = create_string_buffer(1)
                buffer[0] = chr(regval)

                # Write to eeprom
                eeprom.seek(93)
                eeprom.write(buffer[0])
                return True
            except IOError as e:
                print("Error: unable to open file: %s" % str(e))
                return False
            finally:
                if eeprom is not None:
                    eeprom.close()
                    time.sleep(0.01)
        else:
            try:
                f = open(port_ps, 'w')
                if lpmode:
                    f.write('1')
                else:
                    f.write('0')
                f.close()
                return True
            except IOError as e:
                return False

    def _get_transceiver_presence(self):

        transceiver_presence = {}
        for port in range(self.port_end):
            port_status = self.get_presence(port+1)
            transceiver_presence[port] = port_status

        return transceiver_presence

    def get_transceiver_change_event(self, timeout=0):
        """
        Returns a dictionary containing optics insertion/removal status.
        Args:
            timeout: Timeout in milliseconds (optional). If timeout == 0,
                this method will block until a change is detected.
        Returns:
            (bool, dict):
                - True if call successful, False if not;
        """
        port_dict = {}
        forever = False

        if timeout == 0:
            forever = True
        elif timeout > 0:
            timeout = timeout / float(1000) # Convert to secs
        else:
            return False, port_dict # Incorrect timeout

        while True:
            if forever:
                timer = self.POLL_INTERVAL
            else:
                timer = min(timeout, self.POLL_INTERVAL)
                start_time = time.time()

            time.sleep(timer)
            cur_presence = self._get_transceiver_presence()
            changed = False

            for port in range(self.port_end):
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

        return True, port_dict

    def dump_sysfs(self):
        return pddf_obj.cli_dump_dsysfs('xcvr')
