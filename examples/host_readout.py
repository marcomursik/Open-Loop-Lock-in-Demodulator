"""
host_readout.py - Beispiel: demod_out vom tt_um_gyro_lockin per SPI lesen.

MicroPython (z. B. RP2040 / Raspberry Pi Pico), SPI Mode 0, MSB first.
Verdrahtung:
    MCU SCK  -> uio[0], MCU MOSI -> uio[1], MCU MISO <- uio[2],
    MCU CS   -> uio[3], Enable   -> ui_in[1] (high), Takt -> clk.
"""

from machine import SPI, Pin
import time

# SPI Mode 0 (CPOL=0, CPHA=0), <= 1 MHz empfohlen (Synchronizer im Chip)
spi = SPI(0, baudrate=500_000, polarity=0, phase=0,
          sck=Pin(18), mosi=Pin(19), miso=Pin(16))
cs = Pin(17, Pin.OUT, value=1)

CMD_WRITE = 0x00   # Bit7=0: write, Bit0=Adresse
CMD_READ = 0x80    # Bit7=1: read,  Bit0=Adresse


def spi_xfer(b0, b1, b2):
    """Einen 3-Byte-Transfer ausfuehren, gibt die 3 MISO-Bytes zurueck."""
    tx = bytes([b0, b1, b2])
    rx = bytearray(3)
    cs.value(0)
    spi.write_readinto(tx, rx)
    cs.value(1)
    return rx


def set_period(period):
    """Modulationsperiode setzen (Halbperiode in Takten)."""
    spi_xfer(CMD_WRITE | 0, (period >> 8) & 0xFF, period & 0xFF)


def read_demod():
    """demod_out (Reg 1) lesen, signed 16-bit."""
    rx = spi_xfer(CMD_READ | 1, 0x00, 0x00)
    val = (rx[1] << 8) | rx[2]
    return val - 65536 if val >= 32768 else val


if __name__ == "__main__":
    # Periode 1000 -> f_mod = f_clk / (2 * 1000), z. B. 5 kHz bei 10 MHz
    set_period(1000)
    time.sleep(0.1)

    while True:
        rate_counts = read_demod()
        print("demod_out:", rate_counts)
        time.sleep(0.1)
