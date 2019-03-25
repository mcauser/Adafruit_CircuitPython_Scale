# The MIT License (MIT)
#
# Copyright (c) 2019 ladyada for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""
`adafruit_scale`
================================================================================

CircuitPython helper library for dymo scales


* Author(s): ladyada, brentru

Implementation Notes
--------------------

**Hardware:**


**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases
"""

import time
from pulseio import PulseIn

OUNCES = const(0x0B)   # data in weight is in ounces
GRAMS = const(0x02)    # data in weight is in grams
PULSEWIDTH = 72.5

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_scale.git"

class Scale:
    """Interface to a DYMO postal scale.
    """
    def __init__(self, pin, timeout=1.0):
        """Sets up a DYMO postal scale.
        :param ~pulseio.PulseIn pin: The digital pin the scale is connected to.
        :param double timeout: The timeout, in seconds.
        """
        self.timeout = timeout
        self.dymo = PulseIn(pin, maxlen=96, idle_state=True)
        try:
            self.check_scale()
        except RuntimeError as e:
            raise RuntimeError("Failed to inititalize the scale - is the scale on?")
        # units we're measuring
        self.units = None
        # is the measurement stable?
        self.stable = None
        # the weight of what we're measuring
        self.weight = None

    def check_scale(self):
        """Checks for data from the scale.
        """
        timestamp = time.monotonic()
        self.dymo.pause()
        self.dymo.clear()
        self.dymo.resume()

        while len(self.dymo) < 35:
            if (time.monotonic() - timestamp) > self.timeout:
                raise RuntimeError("Timed out waiting for data")
        self.dymo.pause()

    def get_scale_data(self):
        """Read a pulse of SPI data on a pin that corresponds to DYMO scale
        output protocol (12 bytes of data at about 14KHz), timeout is in seconds
        """
        # check the scale's state
        self.check_scale()
        bits = [0] * 96   # there are 12 bytes = 96 bits of data
        bit_idx = 0       # we will count a bit at a time
        bit_val = False   # first pulses will be LOW
        for i in range(len(self.dymo)):
            if self.dymo[i] == 65535:     # This is the pulse between transmits
                break
            num_bits = int(self.dymo[i] / PULSEWIDTH + 0.5)  # ~14KHz == ~7.5us per clock
            for bit in range(num_bits):
                bits[bit_idx] = bit_val
                bit_idx += 1
                if bit_idx == 96:      # we have read all the data we wanted
                    break
            bit_val = not bit_val
        data_bytes = [0] * 12
        for byte_n in range(12):
            thebyte = 0
            for bit_n in range(8):
                thebyte <<= 1
                thebyte |= bits[byte_n*8 + bit_n]
            data_bytes[byte_n] = thebyte
        # do some very basic data checking
        if data_bytes[0] != 3 or data_bytes[1] != 3 or data_bytes[7] != 4 \
        or data_bytes[8] != 0x1C or data_bytes[9] != 0 or data_bytes[10] \
        or data_bytes[11] != 0:
            raise RuntimeError("Bad data capture")

        self.stable = data_bytes[2] & 0x4
        self.units = data_bytes[3]
        self.weight = data_bytes[5] + (data_bytes[6] << 8)
        if data_bytes[2] & 0x1:
            self.weight *= -1
        if self.units == OUNCES:
            # oi no easy way to cast to int8_t
            if data_bytes[4] & 0x80:
                data_bytes[4] -= 0x100
            self.weight *= 10 ** data_bytes[4]
        # convert units to readable string
        if self.units == OUNCES:
            self.units = "oz"
        elif self.units == GRAMS:
            self.units = "g"
