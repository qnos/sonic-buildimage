#!/usr/bin/env python

#############################################################################
# Celestica
#
# Component contains an implementation of SONiC Platform Base API and
# provides the watchdog management function
#
#############################################################################

import os

try:
    from sonic_platform_base.watchdog_base import WatchdogBase
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")

class CpldWatchdog(WatchdogBase):

    def __init__(self):
        pass

    def is_armed(self):
        """
        Retrieves the armed state of the hardware watchdog.

        Returns:
            A boolean, True if watchdog is armed, False if not
        """

        with open("/sys/devices/platform/cpld_wdt/watchdog/watchdog0/state", "r") as fd:
            txt = fd.read()
        state = txt.strip()
        self.is_armed = True if state == "active" else False

        return self.is_armed

    def disarm(self):
        """
        Disarm the hardware watchdog
        Returns:
            A boolean, True if watchdog is disarmed successfully, False if not
        """

        if self.watchdog is not None:
            self.watchdog.write('v')
            self.watchdog.close()
            self.watchdog = None

        if self.is_armed:
            return False
        else:
            return True

    def arm(self, seconds):
        """
        Arm the hardware watchdog with a timeout of <seconds> seconds.
        If the watchdog is currently armed, calling this function will
        simply reset the timer to the provided value. If the underlying
        hardware does not support the value provided in <seconds>, this
        method should arm the watchdog with the *next greater* available
        value.
        Returns:
            An integer specifying the *actual* number of seconds the watchdog
            was armed with. On failure returns -1.
        """

        if self.watchdog is None:
            self.watchdog = os.open("/dev/watchdog0", os.O_RDWR)

        with open("/sys/devices/platform/cpld_wdt/watchdog/watchdog0/settimeout", "w") as fd:
            fd.write("%d" % seconds)
        self.watchdog.write('k')

        if self.is_armed():
            with open("/sys/devices/platform/cpld_wdt/watchdog/watchdog0/settimeout", "r") as fd:
                timeout = int(fd.read().strip())
        else:
            timeout = -1
        return timeout

    def get_remaining_time(self):
        """
        If the watchdog is armed, retrieve the number of seconds remaining on
        the watchdog timer
        Returns:
            An integer specifying the number of seconds remaining on thei
            watchdog timer. If the watchdog is not armed, returns -1.
        """

        if self.is_armed():
            with open("/sys/devices/platform/cpld_wdt/watchdog/watchdog0/timeleft", "r") as fd:
                timeleft = int(fd.read().strip())
            return timeleft
        else:
            return -1

    def __del__(self):
        """
        Close watchdog
        """

        self.disarm()

class Watchdog(CpldWatchdog):
    """PDDF Platform-Specific Watchdog Class"""

    def __init__(self):
        CpldWatchdog.__init__(self)

    # Provide the functions/variables below for which implementation is to be overwritten
