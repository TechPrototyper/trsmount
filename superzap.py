#!/usr/bin/env python3
"""
Superzap - TRS-80 Disk Image Inspector.

A utility to inspect raw sectors of TRS-80 disk images (.dmk, .dsk).
Allows navigating through tracks and sectors and viewing hex dumps.
"""

import sys
import os
import argparse
from trs80_driver import detect_format

def hex_dump(data):
    """Generate a hex dump of the provided data."""
    if not data:
        return "<No Data>"
    
    output = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        output.append(f"{i:04X}  {hex_part:<48}  |{ascii_part}|")
    return "\n".join(output)

def main():
    # Allow overriding program name via environment variable (for wrapper scripts)
    prog_name = os.environ.get("TRS_PROG_NAME")
    
    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="Superzap - TRS-80 Disk Image Inspector"
    )
    parser.add_argument("file", nargs="?", help="Disk image file (.dmk or .dsk)")
    
    args = parser.parse_args()
    
    filename = args.file
        
    if not filename:
        # List files and exit
        files = [f for f in os.listdir('.') if f.lower().endswith(('.dmk', '.dsk'))]
        
        if files:
            print("Error: No file specified.")
            print("\nAvailable disk images in current directory:")
            for f in sorted(files):
                print(f"  {f}")
            print("\nUsage: superzap <filename>")
        else:
            print("Error: No file specified and no disk images found in current directory.")
            print("Usage: superzap <filename>")
        sys.exit(1)

    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)

    print(f"\nLoading {filename}...")
    try:
        disk = detect_format(filename)
        print(f"Format: {disk.get_geometry()}")
    except Exception as e:
        print(f"Error loading disk: {e}")
        return

    track = 0
    sector = 0
    side = 0

    while True:
        print(f"\n--- Track {track} | Side {side} | Sector {sector} ---")
        data = disk.read_sector(track, side, sector)
        
        if data:
            print(hex_dump(data))
        else:
            print("<Sector Not Found / Read Error>")

        cmd = input("\n[N]ext, [P]rev, [J]ump, [Q]uit > ").lower().strip()
        if not cmd:
            cmd = 'n'

        if cmd == 'q':
            break
        elif cmd == 'n':
            sector += 1
            # Simple wrap around guess (assuming 10 sectors for now, but user can jump)
            if sector > 18: 
                sector = 0
                track += 1
        elif cmd == 'p':
            sector -= 1
            if sector < 0:
                sector = 9
                track -= 1
                if track < 0: track = 0
        elif cmd == 'j':
            try:
                t_in = input(f"Track [{track}]: ")
                if t_in: track = int(t_in)
                
                s_in = input(f"Sector [{sector}]: ")
                if s_in: sector = int(s_in)
                
                sd_in = input(f"Side [{side}]: ")
                if sd_in: side = int(sd_in)
            except ValueError:
                print("Invalid input.")

if __name__ == "__main__":
    main()
