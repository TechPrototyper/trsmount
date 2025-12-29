import sys
from trs80_driver import detect_format, TRSDOSFileSystem

def inspect_dir(filename):
    disk = detect_format(filename)
    fs = TRSDOSFileSystem(disk)
    
    print(f"System: {fs.system_type}")
    print(f"Dir Track: {fs.dir_track}")
    
    start_sector = 2 + fs.dir_sector_offset
    end_sector = 18 + fs.dir_sector_offset
    if "NEWDOS/80" in fs.system_type:
        start_sector = 10
        end_sector = 18

    for sector in range(start_sector, end_sector):
        data = disk.read_sector(fs.dir_track, 0, sector)
        if not data: continue

        for i in range(0, 256, 32):
            entry = data[i:i+32]
            attr = entry[0]
            if attr == 0 or attr == 0xFF or (attr & 0x80): continue
            
            raw_name = entry[5:13]
            raw_ext = entry[13:16]
            try:
                name = raw_name.decode('ascii').strip()
                ext = raw_ext.decode('ascii').strip()
                full_name = f"{name}/{ext}"
                
                if "SYS" in full_name:
                    print(f"\nFile: {full_name}")
                    print(f"Raw Entry: {entry.hex()}")
                    
                    eof_low = entry[3]
                    eof_mid = entry[20]
                    eof_high = entry[21]
                    print(f"EOF Bytes: Low={hex(eof_low)}, Mid={hex(eof_mid)}, High={hex(eof_high)}")
                    
                    if eof_low == 0:
                        rba = (eof_high << 8) | eof_mid
                        print(f"Calc (RBA Format): {rba} + 1 = {rba+1}")
                    else:
                        raw_eof = (eof_high << 16) | (eof_mid << 8) | eof_low
                        rba = raw_eof - 255
                        print(f"Calc (Offset Format): {raw_eof} - 255 = {rba} -> Size: {rba+1}")

            except:
                continue

if __name__ == "__main__":
    inspect_dir("test/NEWDOS80.dmk")
