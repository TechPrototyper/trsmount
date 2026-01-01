import sys
from trs80_driver import detect_format, TRSDOSFileSystem

def inspect_direntry(filename, target_file):
    print(f"Inspecting {target_file} on {filename}...")
    try:
        disk = detect_format(filename)
        fs = TRSDOSFileSystem(disk)
        
        target_entry = None
        for sector, offset, entry in fs._iter_directory_entries():
            raw_name = entry[5:13]
            raw_ext = entry[13:16]
            try:
                name = raw_name.decode(fs.encoding).strip()
                ext = raw_ext.decode(fs.encoding).strip()
                full_name = f"{name}/{ext}"
                if full_name == target_file:
                    target_entry = entry
                    break
            except:
                continue
        
        if target_entry:
            print(f"Found entry for {target_file}")
            print(f"Raw Entry (Hex): {target_entry.hex()}")
            print(f"Byte 3 (EOF Low): {target_entry[3]:02X}")
            print(f"Byte 20 (EOF Mid): {target_entry[20]:02X}")
            print(f"Byte 21 (EOF High): {target_entry[21]:02X}")
            
            eof_low = target_entry[3]
            eof_mid = target_entry[20]
            eof_high = target_entry[21]
            
            raw_eof = (eof_high << 16) | (eof_mid << 8) | eof_low
            print(f"Calculated raw_eof: {raw_eof}")
            
            if eof_low == 0:
                print(f"Logic: RBA Format. Size = {raw_eof}")
            else:
                print(f"Logic: Offset Format. Size = {raw_eof} - 255 = {raw_eof - 255}")

        else:
            print("File not found.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_direntry("test/disk00038.dmk", "3DTTTTAS/ASM")
    print("-" * 20)
    inspect_direntry("test/disk00200.dmk", "ADVENTUR/ASM")
