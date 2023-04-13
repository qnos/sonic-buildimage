#############################################################################
# PDDF
#
# PDDF syseeprom base class inherited from the base class
#############################################################################

try:
    from sonic_platform_base.component_base import ComponentBase
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")

class PddfComponent(ComponentBase):
    """PDDF Platform-common Component class"""
    pddf_obj = {}
    plugin_data = {}

    def __init__(self, component_index=0, pddf_data=None, pddf_plugin_data=None):
        ComponentBase.__init__(self)
        if not pddf_data or not pddf_plugin_data:
            raise ValueError('PDDF JSON data error')

        self.pddf_obj = pddf_data
        self.plugin_data = pddf_plugin_data

        self.index = component_index + 1
        self.component_data = None

    def _get_component_data(self):
        device = "COMPONENT{}".format(self.index)
        return self.pddf_obj.get_attr_name_component_output(device, "version")

    def get_type(self):
        """
        Retrieves the name of the component
        Returns:
        A string containing the name of the component
        """
        if self.component_data == None:
            self.component_data = self._get_component_data()
        return self.component_data["type"]

    def get_name(self):
        """
        Retrieves the name of the component
        Returns:
        A string containing the name of the component
        """
        if self.component_data == None:
            self.component_data = self._get_component_data()
        return self.component_data["name"]

    def get_description(self):
        """
        Retrieves the description of the component
        Returns:
        A string containing the description of the component
        """
        if self.component_data == None:
            self.component_data = self._get_component_data()
        return self.component_data["description"]

    def get_firmware_version(self):
        """
        Retrieves the firmware version of the component
        Returns:
        A string containing the firmware version of the component
        """
        if self.component_data == None:
            self.component_data = self._get_component_data()
        return self.component_data["version"]

    def install_firmware(self, image_path):
        """
        Installs firmware to the component
        Args:
        image_path: A string, path to firmware image
        Returns:
        A boolean, True if install was successful, False if not
        """
        return False
