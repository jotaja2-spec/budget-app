"""Debug CPU temperature via HWiNFO shared memory. Run with: python debug_temp.py"""
import ctypes, struct

HWINFO_SM_NAME    = "Global\\HWiNFO_SENS_SM2"
HWINFO_SM_SIZE    = 1 * 1024 * 1024
HWINFO_SIGNATURE  = 0x53697748
READING_TYPE_TEMP = 1
SENSOR_STR        = 128
UNIT_STR          = 16

print("=== HWiNFO Shared Memory Test ===\n")

FILE_MAP_READ = 0x0004
k32 = ctypes.windll.kernel32
h   = k32.OpenFileMappingW(FILE_MAP_READ, False, HWINFO_SM_NAME)

if not h:
    print("FAILED: Could not open HWiNFO shared memory.")
    print("Make sure HWiNFO64 is running and Shared Memory Support is enabled:")
    print("  HWiNFO64 -> Settings (gear) -> Sensors -> check 'Shared Memory Support'")
    input("\nPress Enter to close...")
    exit()

print("Shared memory opened OK")
ptr  = k32.MapViewOfFile(h, FILE_MAP_READ, 0, 0, HWINFO_SM_SIZE)
data = ctypes.string_at(ptr, HWINFO_SM_SIZE)
k32.UnmapViewOfFile(ptr)
k32.CloseHandle(h)

hdr_fmt = "<IIIqIIIIII"
sig, ver, rev, poll, off_sensor, sz_sensor, num_sensor, \
    off_reading, sz_reading, num_reading = struct.unpack_from(hdr_fmt, data)

print(f"Signature: 0x{sig:08X} ({'OK' if sig == HWINFO_SIGNATURE else 'WRONG - not HWiNFO data'})")
print(f"Readings:  {num_reading}")
print()

rd_fmt  = f"<III{SENSOR_STR}s{SENSOR_STR}s{UNIT_STR}sdddd"
rd_size = struct.calcsize(rd_fmt)

print("All temperature readings found:")
for i in range(num_reading):
    off   = off_reading + i * sz_reading
    chunk = data[off: off + rd_size]
    if len(chunk) < rd_size:
        break
    t_reading, _, _, label_orig, _, unit, val, *_ = struct.unpack(rd_fmt, chunk)
    if t_reading == READING_TYPE_TEMP:
        label = label_orig.rstrip(b"\x00").decode("utf-8", errors="ignore")
        u     = unit.rstrip(b"\x00").decode("utf-8", errors="ignore")
        print(f"  {label:<40} {val:.1f} {u}")

input("\nDone. Press Enter to close...")
