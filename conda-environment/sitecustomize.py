# Under amd64 emulation on Apple Silicon the Jupyter kernel deadlocks while
# starting the debugpy debugger (cells stay at "[ ]"): hide debugpy there.
# On a real x86 host /proc/cpuinfo has "vendor_id", so nothing is hidden.
import sys

try:
    _cpu = open("/proc/cpuinfo").read()
except OSError:
    _cpu = ""
if "VirtualApple" in _cpu or "CPU implementer" in _cpu:
    sys.modules["debugpy"] = None
