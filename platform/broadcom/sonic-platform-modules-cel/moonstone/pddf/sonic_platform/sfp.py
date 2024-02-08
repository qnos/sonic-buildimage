#!/usr/bin/env python

import re
import time

#############################################################################
# Celestica
#
# Component contains an implementation of SONiC Platform Base API and
# provides the sfp management function
#
#############################################################################

try:
    from sonic_platform_pddf_base.pddf_sfp import PddfSfp
except ImportError as e:
    raise ImportError (str(e) + "- required module not found")


class Sfp(PddfSfp):
    """
    PDDF Platform-Specific Sfp class
    """

    def __init__(self, index, pddf_data=None, pddf_plugin_data=None):
        PddfSfp.__init__(self, index, pddf_data, pddf_plugin_data)

    # Provide the functions/variables below for which implementation is to be overwritten

    def get_reset_status(self):
        device = 'PORT{}'.format(self.port_index)
        if re.search('^SFP', self.pddf_obj.get_device_type(device)):
            return False
        else:
            return PddfSfp.get_reset_status(self)

    def get_tx_fault(self):
        device = 'PORT{}'.format(self.port_index)
        if re.search('^SFP', self.pddf_obj.get_device_type(device)):
            return PddfSfp.get_tx_fault(self)
        else:
            return False

    def get_tx_disable(self):
        device = 'PORT{}'.format(self.port_index)
        if re.search('^SFP', self.pddf_obj.get_device_type(device)):
            return PddfSfp.get_tx_disable(self)
        else:
            return False

    def get_lpmode(self):
        device = 'PORT{}'.format(self.port_index)
        if re.search('^SFP', self.pddf_obj.get_device_type(device)):
            return False
        else:
            return PddfSfp.get_lpmode(self)

    def reset(self):
        device = 'PORT{}'.format(self.port_index)
        if re.search('^SFP', self.pddf_obj.get_device_type(device)):
            return False
        else:
            status = False
            device = 'PORT{}'.format(self.port_index)
            path = self.pddf_obj.get_path(device, 'xcvr_reset')

            if path:
                try:
                    f = open(path, 'r+')
                except IOError as e:
                    return False

                try:
                    f.seek(0)
                    f.write('0')
                    time.sleep(2)
                    f.seek(0)
                    f.write('1')

                    f.close()
                    status = True
                except IOError as e:
                    status = False
            else:
                # Use common SfpOptoeBase implementation for reset
                status = super().reset()

            return status

    def tx_disable(self, tx_disable):
        device = 'PORT{}'.format(self.port_index)
        if re.search('^SFP', self.pddf_obj.get_device_type(device)):
            return PddfSfp.tx_disable(self, tx_disable)
        else:
            return False

    def set_lpmode(self, lpmode):
        device = 'PORT{}'.format(self.port_index)
        if re.search('^SFP', self.pddf_obj.get_device_type(device)):
            return False
        else:
            return PddfSfp.set_lpmode(self, lpmode)