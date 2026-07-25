"""Read precision scale via serial port (RS232) or camera OCR."""
import serial
import re
import time


class ScaleReader:
    """Read electronic scale (0.01g precision)."""

    def __init__(self, port='/dev/ttyUSB1', baudrate=9600):
        self.port = port
        self.ser = None
        try:
            self.ser = serial.Serial(port, baudrate, timeout=0.3)
        except Exception:
            pass  # Will use manual input or camera OCR

    def read(self):
        if self.ser:
            return self._read_serial()
        return None  # TODO: camera OCR fallback

    def _read_serial(self):
        for _ in range(3):
            try:
                self.ser.reset_input_buffer()
                line = self.ser.readline()
                text = line.decode('ascii', errors='ignore').strip()
                match = re.search(r'[+-]?\d+\.?\d*', text)
                if match:
                    val = float(match.group())
                    if 0 <= val <= 500:
                        return val
            except Exception:
                pass
        return None

    def wait_stable(self, tolerance=0.02, timeout=3.0):
        start = time.time()
        last = self.read()
        while time.time() - start < timeout:
            time.sleep(0.2)
            cur = self.read()
            if cur and last and abs(cur - last) < tolerance:
                return cur
            last = cur
        return last
