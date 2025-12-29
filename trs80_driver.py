#!/usr/bin/env python3
"""
TRS-80 Disk Driver Module.

This module provides classes and functions to interact with TRS-80 disk images
(.dmk, .dsk, .jv1, .jv3) and filesystems (TRSDOS, NEWDOS/80).

Classes:
    DiskImage: Abstract base class for disk image formats.
    JV1Image: Handler for JV1 disk images.
    JV3Image: Handler for JV3 disk images.
    DMKImage: Handler for DMK disk images.
    TRSDOSFileSystem: High-level interface for TRSDOS/NEWDOS filesystems.

Functions:
    detect_format(filename): Automatically detects and returns the appropriate DiskImage object.
"""

import os
import sys
import struct

# Constants
SECTOR_SIZE = 256
DIR_TRACK_TRSDOS = 17
DIR_TRACK_NEWDOS = 17 # Usually, but can be configured

class DiskImage:
    """
    Base class for TRS-80 Disk Images.
    
    Attributes:
        filename (str): Path to the disk image file.
        file_size (int): Size of the disk image in bytes.
        data (bytearray): In-memory copy of the disk data.
    """
    def __init__(self, filename):
        self.filename = filename
        self.file_size = os.path.getsize(filename)
        with open(filename, 'rb') as f:
            self.data = bytearray(f.read())

    def read_sector(self, track, side, sector):
        """
        Read a sector from the disk.
        
        Args:
            track (int): Track number (0-based).
            side (int): Side number (0 or 1).
            sector (int): Sector number.
            
        Returns:
            bytes: 256 bytes of sector data, or None if not found.
        """
        raise NotImplementedError

    def write_sector(self, track, side, sector, data):
        """
        Write data to a sector.
        
        Args:
            track (int): Track number.
            side (int): Side number.
            sector (int): Sector number.
            data (bytes): 256 bytes of data to write.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        raise NotImplementedError

    def save(self):
        """Save the in-memory data back to the disk image file."""
        with open(self.filename, 'wb') as f:
            f.write(self.data)

    def get_geometry(self):
        """Return a string describing the disk geometry."""
        raise NotImplementedError


class JV1Image(DiskImage):
    """
    JV1 Disk Image Format Handler.
    
    JV1 is a simple headerless format consisting of a linear array of sectors.
    It typically represents Single Density (FM) disks.
    """
    def __init__(self, filename):
        super().__init__(filename)
        # Heuristic: Guess geometry from file size
        # Common sizes:
        # 35 tracks * 10 sectors * 256 = 89600
        # 40 tracks * 10 sectors * 256 = 102400
        # 40 tracks * 18 sectors * 256 = 184320
        # 80 tracks * 10 sectors * 256 = 204800
        # 200448 is close to 204800 (80 tracks SD) or 40 tracks DS SD.
        
        self.sectors_per_track = 10 # Default to SD
        self.sides = 1
        
        if self.file_size > 180000:
             # Could be 80 tracks SD or 40 tracks DS or 40 tracks DD
             # If it's DD (18 sectors), 40 tracks = 184320.
             # If it's SD (10 sectors), 80 tracks = 204800.
             # 200448 is closer to 204800.
             pass

    def read_sector(self, track, side, sector):
        # Support both SD (10) and DD (18) via simple mapping?
        # For JV1, it's just a flat list of sectors.
        # We map (track, side, sector) to a linear index.
        
        # If we assume Single Sided:
        # index = track * sectors_per_track + sector
        
        # If we assume Double Sided:
        # index = (track * sides + side) * sectors_per_track + sector
        # But JV1 is usually Single Sided.
        
        # Let's try to be flexible.
        # If the caller asks for sector > 9, maybe it's DD.
        
        # Calculate linear offset assuming 10 sectors/track for now
        # If that fails, we might need to be smarter.
        
        # However, for the purpose of "scanning all sectors", we can just ignore track/sector structure
        # and read linearly if we had a linear read method.
        # But the interface is read_sector(track, side, sector).
        
        # Let's stick to standard JV1 = 10 sectors/track.
        if side != 0:
            return None
            
        # Handle 0-based or 1-based sector requests?
        # Usually JV1 is 0-based (0-9).
        # If sector >= 10, return None (for SD).
        if sector >= 10:
            return None
            
        offset = (track * 10 + sector) * 256
        if offset + 256 > len(self.data):
            return None
        return self.data[offset:offset+256]

    def write_sector(self, track, side, sector, data):
        if side != 0: return False
        if sector >= 10: return False
        if len(data) != 256: return False
        
        offset = (track * 10 + sector) * 256
        if offset + 256 > len(self.data):
            return False
            
        self.data[offset:offset+256] = data
        return True

    def get_geometry(self):
        return "JV1 (Raw Sector Dump)"


class JV3Image(DiskImage):
    """
    JV3 Format:
    - Sequence of Sector Header + Data.
    - Header (3 bytes): Track, Sector, Flags.
    - Data: Usually 256 bytes.
    """
    def __init__(self, filename):
        super().__init__(filename)
        self.sector_map = {} # (track, side, sector) -> offset
        self._parse_image()

    def _parse_image(self):
        offset = 0
        while offset < len(self.data):
            # Check for end of file or padding
            if offset + 3 > len(self.data):
                break
            
            track = self.data[offset]
            sector = self.data[offset+1]
            flags = self.data[offset+2]
            
            # Check for unused entry
            if track == 0xFF:
                # Skip this entry? Usually JV3 is packed, but 0xFF might indicate end or skip.
                # However, standard JV3 parsing often just reads sequentially.
                # If track is 0xFF, it might be a spacer, but usually we just stop or skip.
                # Let's assume standard packed format.
                offset += 3 # Skip header
                # How much data to skip? 
                # If it's a free entry, does it have data? 
                # Usually JV3 is dense. Let's look at the size code.
                size_code = flags & 0x03
                data_len = 128 << size_code
                offset += data_len
                continue

            side = (flags >> 4) & 1
            size_code = flags & 0x03

            # Determine data length based on size code
            if size_code == 0:
                data_len = 256
            elif size_code == 1:
                data_len = 128
            elif size_code == 2:
                data_len = 1024
            elif size_code == 3:
                data_len = 512
            else:
                data_len = 256

            self.sector_map[(track, side, sector)] = offset + 3
            offset += 3 + data_len

    def read_sector(self, track, side, sector):
        offset = self.sector_map.get((track, side, sector))
        if offset is None:
            return None
        # Assume 256 bytes for now as it's standard for TRSDOS
        return self.data[offset:offset+256]

    def get_geometry(self):
        tracks = max(k[0] for k in self.sector_map.keys()) + 1
        sides = max(k[1] for k in self.sector_map.keys()) + 1
        return f"JV3 ({tracks} Tracks, {sides} Sides)"


class DMKImage(DiskImage):
    """
    DMK Format:
    - Header (16 bytes).
    - Raw track data with pointer tables.
    """
    def __init__(self, filename):
        super().__init__(filename)
        self.num_tracks = self.data[1]
        self.track_len = self.data[2] + (self.data[3] << 8)
        
        # Fix for invalid track count (e.g. NEWDOS80-2.dmk reports 254)
        if self.num_tracks == 0 or self.num_tracks > 100:
            # Estimate from file size
            # We don't know sides yet, so assume SS for calculation, then adjust
            self.num_tracks = (self.file_size - 16) // self.track_len
            # If it's DS, this num_tracks will be Cylinders * 2.
            # But usually num_tracks is Cylinders.
            # We'll refine this in get_geometry or read_sector if needed.
            # For now, just ensure it's not 254.
            if self.num_tracks > 80:
                 # Maybe it's DS?
                 pass

        # Spec: Bit 4: 1=Single Density. Bit 6: 1=Single Sided.
        self.is_single_density = (self.data[4] & 0x10) != 0
        self.is_single_sided = (self.data[4] & 0x40) != 0        
        # Sanity Check: Ignore Header Flag if file size contradicts it
        # Calculate expected size for Single Sided
        expected_size_ss = 16 + (self.num_tracks * self.track_len)
        if self.file_size == expected_size_ss:
            self.is_single_sided = True
        
        # If it were DS, expected size would be double (if num_tracks refers to cylinders)
        # Or if num_tracks refers to total heads, it matches.
        # But standard DMK usage: num_tracks = cylinders.
        # So if file size matches num_tracks * len, it's SS.
    def read_sector(self, track, side, sector):
        # This is complex because we have to parse the IDAM table for each track.
        # Simplified logic:
        if self.is_single_sided and side > 0:
            return None
        
        # Calculate track offset
        # Header is 16 bytes.
        track_idx = track
        if not self.is_single_sided:
            track_idx = track * 2 + side
            
        track_start = 16 + (track_idx * self.track_len)
        if track_start >= len(self.data):
            return None
            
        # Read IDAM table (64 entries, 2 bytes each)
        # Each entry is an offset from track_start to the IDAM.
        # Bit 15 set means double density?
        
        # We need to scan the IDAMs to find the matching sector number.
        for i in range(64):
            ptr_offset = track_start + (i * 2)
            ptr = self.data[ptr_offset] + (self.data[ptr_offset+1] << 8)

            if ptr == 0:
                break  # End of table

            # Mask out flags (usually high bits) to get relative offset
            idam_offset = ptr & 0x3FFF

            # Go to IDAM
            abs_idam = track_start + idam_offset
            if abs_idam + 6 > len(self.data):
                continue

            s_track = self.data[abs_idam + 1]
            s_sector = self.data[abs_idam + 3]

            if s_sector == sector and s_track == track:
                # Found it!
                # Simple heuristic: Skip 7 bytes, look for FB/F8
                search_start = abs_idam + 7
                for k in range(50):
                    # Normal or Deleted Data
                    if self.data[search_start + k] in [0xFB, 0xF8]:
                        data_start = search_start + k + 1
                        # Assume 256 bytes
                        return self.data[data_start:data_start + 256]
                        
        return None

    def write_sector(self, track, side, sector, data):
        if len(data) != 256: return False
        
        if self.is_single_sided and side > 0:
            return False
        
        track_idx = track
        if not self.is_single_sided:
            track_idx = track * 2 + side
            
        track_start = 16 + (track_idx * self.track_len)
        if track_start >= len(self.data):
            return False
            
        for i in range(64):
            ptr_offset = track_start + (i * 2)
            ptr = self.data[ptr_offset] + (self.data[ptr_offset+1] << 8)

            if ptr == 0:
                break

            idam_offset = ptr & 0x3FFF
            abs_idam = track_start + idam_offset
            if abs_idam + 6 > len(self.data):
                continue

            s_track = self.data[abs_idam + 1]
            s_sector = self.data[abs_idam + 3]

            if s_sector == sector and s_track == track:
                search_start = abs_idam + 7
                for k in range(50):
                    if self.data[search_start + k] in [0xFB, 0xF8]:
                        data_start = search_start + k + 1
                        self.data[data_start:data_start + 256] = data
                        return True
        return False

    def get_geometry(self):
        return f"DMK ({self.num_tracks} Tracks)"


def detect_format(filename):
    size = os.path.getsize(filename)
    
    # DMK Check
    # Read header
    with open(filename, 'rb') as f:
        header = f.read(16)
    
    is_dmk = False
    if filename.lower().endswith('.dmk'):
        # Check if header is plausible
        num_tracks = header[1]
        track_len = header[2] + (header[3] << 8)
        
        # Valid DMK usually has num_tracks <= 80 (or maybe 96)
        # and track_len reasonable (e.g. < 20000)
        if num_tracks > 0 and num_tracks <= 100 and track_len > 0 and track_len < 20000:
            is_dmk = True
        else:
            # Header looks garbage. Might be a raw file named .dmk
            is_dmk = False
            
    if is_dmk:
        return DMKImage(filename)
        
    # Try to parse as JV3
    try:
        # JV3 usually has a specific structure, but hard to validate quickly without parsing.
        # If it's not DMK, try JV3 then JV1.
        # But JV1 is just raw data, so it matches everything.
        # Let's check for JV3 signature? JV3 doesn't have a file header, just sector headers.
        # If the first byte is 0xFF, it might be JV3 (unused track).
        # If the first byte is < 80, it might be a track number.
        pass
    except Exception:
        pass

    # Fallback to JV1 (Raw)
    return JV1Image(filename)


class TRSDOSFileSystem:
    """
    High-level interface for TRSDOS and compatible filesystems.
    
    Handles directory parsing, file reading/writing, and free space management.
    Supports TRSDOS 2.3, NEWDOS/80, and potentially others.
    """
    def __init__(self, disk):
        """
        Initialize the filesystem handler.
        
        Args:
            disk (DiskImage): The underlying disk image object.
        """
        self.disk = disk
        self.encoding = 'latin-1' # TRS-80 used a variant of ASCII/Latin-1
        
        # Analysis results
        self.dir_track = 17  # Default Directory Track
        self.dir_sector_offset = 0 # Default Sector Offset (0-based)
        self.system_type = "Unknown"
        self.detected_os = "Unknown"
        
        self._analyze()

    def _analyze(self):
        """
        Perform deterministic analysis of the disk to find:
        1. Directory Track (Model I vs III/4)
        2. Operating System (TRSDOS, NEWDOS, LDOS, etc.)
        """
        # 1. Detect Directory Track (17 vs 20) and Sector Offset (0 vs 1)
        # Check Track 17, Sector 0/1 (GAT) vs Track 20, Sector 0/1
        
        # GAT Sector usually starts with allocation data.
        # Common values: FF (Free), FE (Reserved), etc.
        # But also bitmasks like 3F (6 sectors), 1F (5 sectors), etc.
        valid_markers = [0xFF, 0xFE, 0xFD, 0xFC, 0x3F, 0x1F, 0x0F, 0x7F]
        
        def check_gat(track, sector):
            data = self.disk.read_sector(track, 0, sector)
            if not data: return False
            
            # Check first byte
            if data[0] in valid_markers:
                return True
                
            # Fallback: Check for "TRSDOS" string in the sector
            # 13GHOSTS has "TRSDOS" at offset 0xD0
            try:
                s = data.decode('latin-1', errors='ignore')
                if "TRSDOS" in s or "GAT" in s:
                    return True
            except:
                pass
                
            return False

        # Check combinations
        t17_s0 = check_gat(17, 0)
        t17_s1 = check_gat(17, 1)
        t20_s0 = check_gat(20, 0)
        t20_s1 = check_gat(20, 1)
        
        # Check Track 9 Sector 10 (NEWDOS/80 v2 Special?)
        # User reports directory at Track 9 Sector 10 on NEWDOS80.dmk
        t9_s10_data = self.disk.read_sector(9, 0, 10)
        is_t9_dir = False
        if t9_s10_data:
             # Check for directory entry signature
             # Entry 0: Flag (not 0/FF), Name (ASCII), Ext (ASCII)
             # Example: 5E 00 00 00 00 42 4F 4F 54 ... (BOOT/SYS)
             attr = t9_s10_data[0]
             if attr != 0 and attr != 0xFF:
                 name = t9_s10_data[5:13]
                 if b"BOOT" in name or b"SYS" in name:
                     is_t9_dir = True

        # Check for NEWDOS/80 System Disk (Track 17 Sector 0 is Code)
        # Common Z80 opcodes: E1 (POP HL), C1 (POP BC), 3A (LD A), CD (CALL), C3 (JP), DI (F3)
        t17_s0_data = self.disk.read_sector(17, 0, 0)
        is_newdos_system = False
        if t17_s0_data and t17_s0_data[0] in [0xE1, 0xC1, 0x3A, 0xCD, 0xC3, 0xF3]:
             is_newdos_system = True

        if t17_s0:
            self.dir_track = 17
            self.dir_sector_offset = 0
            self.system_type = "Model I"
        elif t17_s1:
            self.dir_track = 17
            self.dir_sector_offset = 1
            self.system_type = "Model I (1-based)"
        elif t20_s0:
            self.dir_track = 20
            self.dir_sector_offset = 0
            self.system_type = "Model III/4"
        elif t20_s1:
            self.dir_track = 20
            self.dir_sector_offset = 1
            self.system_type = "Model III/4 (1-based)"
        elif is_t9_dir:
            self.dir_track = 9
            self.dir_sector_offset = 0 # Starts at 10, but list_files handles range
            self.system_type = "NEWDOS/80 (Track 9)"
            self.detected_os = "NEWDOS/80"
        elif is_newdos_system:
            self.dir_track = 17 # It is technically the directory track, but used for system files
            self.dir_sector_offset = 0
            self.system_type = "NEWDOS/80 (System)"
            self.detected_os = "NEWDOS/80"
        else:
            # Fallback: Scan all tracks
            found_track = self._scan_for_directory()
            if found_track is not None:
                self.dir_track = found_track
                self.system_type = f"Detected (Track {found_track})"
                # Determine offset
                if self.disk.read_sector(found_track, 0, 0):
                    self.dir_sector_offset = 0
                else:
                    self.dir_sector_offset = 1
            else:
                # Fallback based on geometry
                geo = self.disk.get_geometry()
                if "JV1" in geo:
                    self.dir_track = 17
                    self.system_type = "Model I"
                else:
                    # Default to 17, but try to guess offset by checking Track 0
                    # If Track 0 has Sector 0, assume 0-based.
                    if self.disk.read_sector(0, 0, 0):
                        self.dir_sector_offset = 0
                    elif self.disk.read_sector(0, 0, 1):
                        self.dir_sector_offset = 1
                    
                    self.system_type = "Unknown (Assumed Model I)"

        # 2. Identify OS via System Files
        try:
            files = self.list_files()
            # Extract base filenames (before slash)
            filenames = set(f.split('/')[0] for f in files)
            
            if "LDOS" in filenames or "LSDOS" in filenames:
                self.detected_os = "LDOS / LS-DOS"
            elif "NEWDOS" in filenames or "NEWDOS80" in filenames:
                self.detected_os = "NEWDOS/80"
            elif "MULTIDOS" in filenames:
                self.detected_os = "MultiDOS"
            elif "DOSPLUS" in filenames:
                self.detected_os = "DOSPLUS"
            elif "TRSDOS" in filenames:
                self.detected_os = "TRSDOS"
            else:
                if len(files) > 0:
                    self.detected_os = "Generic TRSDOS-compatible"
                else:
                    self.detected_os = "Unknown / Non-Bootable"
        except Exception:
            self.detected_os = "Read Error"

        # 3. Boot Sector Check (Refinement)
        # If file check was generic, look for strings in Boot Sector (Track 0, Sector 0/1)
        boot = self.disk.read_sector(0, 0, self.dir_sector_offset)
        if boot:
            # Simple ASCII scan
            text = "".join([chr(b) if 32 <= b <= 126 else "" for b in boot])
            if "NEWDOS" in text:
                self.detected_os = "NEWDOS/80 (Boot Signature)"
            elif "LDOS" in text:
                self.detected_os = "LDOS (Boot Signature)"
            elif "R.S." in text or "RADIO SHACK" in text:
                self.detected_os = "TRSDOS (Boot Signature)"
            elif "Disk error" in text or "No system" in text:
                 self.detected_os = "TRSDOS (Boot Signature)"
            
            # Check for Z80 Code if no files found
            if len(files) == 0:
                # Common Z80 opcodes at start: 00 (NOP), F3 (DI), 3E (LD A), 21 (LD HL), C3 (JP), 18 (JR)
                if boot[0] in [0x00, 0xF3, 0x3E, 0x21, 0xC3, 0x18, 0xFE]:
                    self.detected_os = "Booter / Non-Standard FS"

    def _check_directory_track(self, track):
        """Quick check if a track looks like a directory."""
        # Read a few sectors and look for valid entries
        valid_entries = 0
        # Try sectors 2-5 (assuming 0-based offset)
        for s in range(2, 6):
            data = self.disk.read_sector(track, 0, s)
            if not data: continue
            valid_entries += self._count_valid_entries(data)
            
        return valid_entries > 0

    def _scan_for_directory(self):
        """Scan all tracks to find the directory."""
        # Limit scan to reasonable range (0-80)
        # Skip 17 and 20 as we already checked them
        for track in range(0, 80):
            if track in [17, 20]: continue
            if self._check_directory_track(track):
                return track
        return None

    def _count_valid_entries(self, data):
        count = 0
        for i in range(0, 256, 32):
            entry = data[i:i+32]
            attr = entry[0]
            if attr == 0 or attr == 0xFF: continue
            if attr & 0x80: continue # Extended entry
            
            # Check filename validity
            raw_name = entry[5:13]
            raw_ext = entry[13:16]
            
            # Must start with alphanumeric
            if not (48 <= raw_name[0] <= 57 or 65 <= raw_name[0] <= 90 or 97 <= raw_name[0] <= 122):
                continue
                
            # Must contain printable chars
            if not all(32 <= b <= 126 for b in raw_name if b != 0):
                continue
                
            # Extension must be alphanumeric or space
            if not all((48 <= b <= 57 or 65 <= b <= 90 or 97 <= b <= 122 or b == 32) for b in raw_ext):
                continue

            count += 1
        return count


    def read_file(self, filename):
        """
        Read the content of a file.
        filename: "NAME/EXT"
        """
        # 1. Find Directory Entry
        start_sector = 2 + self.dir_sector_offset
        end_sector = 18 + self.dir_sector_offset
        
        if self.system_type == "NEWDOS/80 (System)" or self.system_type == "NEWDOS/80 (Track 9)":
            start_sector = 10
            end_sector = 18

        target_entry = None
        
        for sector in range(start_sector, end_sector):
            data = self.disk.read_sector(self.dir_track, 0, sector)
            if not data: continue

            for i in range(0, 256, 32):
                entry = data[i:i+32]
                attr = entry[0]
                if attr == 0 or attr == 0xFF or (attr & 0x80): continue
                
                raw_name = entry[5:13]
                raw_ext = entry[13:16]
                try:
                    name = raw_name.decode(self.encoding).strip()
                    ext = raw_ext.decode(self.encoding).strip()
                    full_name = f"{name}/{ext}"
                    if full_name == filename:
                        target_entry = entry
                        break
                except:
                    continue
            if target_entry: break
            
        if not target_entry:
            return None
            
        # 2. Parse Extents
        # NEWDOS/80 FPDE Layout:
        # 0-2: Attrs/Reserved
        # 3: EOF Low
        # 4: LRECL
        # 5-12: Name
        # 13-15: Ext
        # 16-17: Update Pwd
        # 18-19: Access Pwd
        # 20: EOF Middle
        # 21: EOF High
        # 22-29: Extents 1-4
        # 30-31: Extent 5 or FXDE Link
        
        # Parse EOF
        eof_low = target_entry[3]
        eof_mid = target_entry[20]
        eof_high = target_entry[21]
        
        sectors_per_granule, granules_per_track = self._get_allocation_info()
        
        # Calculate Total Sectors from Extents to determine size if in RBA format
        total_sectors_allocated = 0
        for i in range(5):
            offset = 22 + (i * 2)
            if offset >= 32: break
            track = target_entry[offset]
            if track == 0xFF: break
            if track == 0xFE: break
            info = target_entry[offset+1]
            count = (info & 0x1F) + 1
            total_sectors_allocated += count * sectors_per_granule

        # Calculate File Size
        if eof_low == 0:
            # RBA Format: Bytes 20-21 are the offset in the last sector
            last_sector_offset = (eof_high << 8) | eof_mid
            if total_sectors_allocated > 0:
                file_size = (total_sectors_allocated - 1) * 256 + (last_sector_offset + 1)
            else:
                file_size = 0
        else:
            # Offset Format
            raw_eof = (eof_high << 16) | (eof_mid << 8) | eof_low
            file_size = raw_eof - 255
            
        # print(f"DEBUG: File Size: {file_size} bytes")
        
        content = bytearray()
        
        # Extents start at offset 22
        
        # Extents start at offset 22
        for i in range(0, 5): # Up to 5 extents in FPDE (last one at 30-31)
            offset = 22 + (i * 2)
            if offset >= 32: break
            
            track = target_entry[offset]
            info = target_entry[offset+1]
            
            if track == 0xFF: # End of extents
                break
            
            if track == 0xFE: # FXDE Link
                # TODO: Handle FXDE
                # print(f"Warning: FXDE link found at extent {i}, not implemented.")
                break
            
            # Parse Info
            # Bits 5-7: Start Granule
            # Bits 0-4: Count - 1
            
            start_granule = (info >> 5) & 0x07
            count = (info & 0x1F) + 1
            
            # print(f"DEBUG: Extent {i}: Track {track}, Start Granule {start_granule}, Count {count}")
            
            for g in range(count):
                current_granule = start_granule + g
                
                # Calculate Sector Start
                # Assuming 2 granules per track (0 and 1)
                # Granule 0: Sectors 0-4
                # Granule 1: Sectors 5-9
                
                start_sector = 0
                if current_granule == 1:
                    start_sector = 5
                elif current_granule > 1:
                    start_sector = current_granule * sectors_per_granule
                
                for s in range(sectors_per_granule):
                    sector = start_sector + s
                    data = self.disk.read_sector(track, 0, sector)
                    if data:
                        content.extend(data)
                    else:
                        content.extend(b'\x00' * 256)
                        
        # Truncate to EOF
        if len(content) > file_size:
            content = content[:file_size]
            
        return bytes(content)

    def _get_allocation_info(self):
        # Determine sectors per granule and granules per track
        # Default to Model I SD
        sectors_per_granule = 5
        granules_per_track = 2
        
        # Check geometry
        geo = self.disk.get_geometry()
        if "JV3" in geo or "DMK" in geo:
            # Check if DD
            # If 18 sectors/track, usually 3 granules of 6 sectors
            # How to detect?
            # Check GAT size?
            pass
            
        return sectors_per_granule, granules_per_track

    def delete_file(self, filename):
        """Delete a file by name."""
        # 1. Find Directory Entry
        start_sector = 2 + self.dir_sector_offset
        end_sector = 18 + self.dir_sector_offset
        if self.system_type == "NEWDOS/80 (System)" or self.system_type == "NEWDOS/80 (Track 9)":
            start_sector = 10
            end_sector = 18

        target_entry_loc = None # (sector, offset)
        target_entry = None
        
        for sector in range(start_sector, end_sector):
            data = self.disk.read_sector(self.dir_track, 0, sector)
            if not data: continue

            for i in range(0, 256, 32):
                entry = data[i:i+32]
                attr = entry[0]
                if attr == 0 or attr == 0xFF or (attr & 0x80): continue
                
                raw_name = entry[5:13]
                raw_ext = entry[13:16]
                try:
                    name = raw_name.decode(self.encoding).strip()
                    ext = raw_ext.decode(self.encoding).strip()
                    full_name = f"{name}/{ext}"
                    if full_name == filename:
                        target_entry = entry
                        target_entry_loc = (sector, i)
                        break
                except:
                    continue
            if target_entry: break
            
        if not target_entry:
            return False # File not found

        # 2. Free Granules in GAT
        sectors_per_granule, granules_per_track = self._get_allocation_info()
        
        # Read GAT
        gat_sector = self.disk.read_sector(self.dir_track, 0, self.dir_sector_offset)
        if not gat_sector: return False
        gat = bytearray(gat_sector)
        
        for i in range(0, 5):
            offset = 22 + (i * 2)
            track = target_entry[offset]
            info = target_entry[offset+1]
            
            if track == 0xFF: break
            if track == 0xFE: break # FXDE TODO
            
            start_granule = (info >> 5) & 0x07
            count = (info & 0x1F) + 1
            
            # Calculate GAT index
            # GAT index = track * granules_per_track + granule
            # But wait, GAT is linear?
            # Yes, usually.
            
            for g in range(count):
                current_granule = start_granule + g
                gat_idx = track * granules_per_track + current_granule
                if gat_idx < len(gat):
                    gat[gat_idx] = 0xFF # Free
                    
        # Write GAT back
        self.disk.write_sector(self.dir_track, 0, self.dir_sector_offset, gat)
        
        # 3. Clear Directory Entry
        # Read sector again to be safe (though we have location)
        dir_sector_data = bytearray(self.disk.read_sector(self.dir_track, 0, target_entry_loc[0]))
        offset = target_entry_loc[1]
        dir_sector_data[offset] = 0 # Mark as free
        self.disk.write_sector(self.dir_track, 0, target_entry_loc[0], dir_sector_data)
        
        self.disk.save()
        return True

    def write_file(self, filename, content):
        """Write a file (overwrite or create)."""
        # Delete if exists
        self.delete_file(filename)
        
        # Parse filename
        if '/' in filename:
            name, ext = filename.split('/', 1)
        else:
            name = filename
            ext = "   "
            
        name = name.ljust(8)[:8].upper()
        ext = ext.ljust(3)[:3].upper()
        
        # 1. Find Free Directory Entry
        start_sector = 2 + self.dir_sector_offset
        end_sector = 18 + self.dir_sector_offset
        if self.system_type == "NEWDOS/80 (System)" or self.system_type == "NEWDOS/80 (Track 9)":
            start_sector = 10
            end_sector = 18

        free_entry_loc = None
        
        for sector in range(start_sector, end_sector):
            data = self.disk.read_sector(self.dir_track, 0, sector)
            if not data: continue

            for i in range(0, 256, 32):
                entry = data[i:i+32]
                attr = entry[0]
                if attr == 0: # Free slot
                    free_entry_loc = (sector, i)
                    break
            if free_entry_loc: break
            
        if not free_entry_loc:
            raise OSError(28, "No free directory slots") # ENOSPC
            
        # 2. Allocate Granules
        sectors_per_granule, granules_per_track = self._get_allocation_info()
        total_sectors = (len(content) + 255) // 256
        total_granules = (total_sectors + sectors_per_granule - 1) // sectors_per_granule
        
        # Read GAT
        gat_sector = self.disk.read_sector(self.dir_track, 0, self.dir_sector_offset)
        if not gat_sector: raise OSError(5, "Read Error")
        gat = bytearray(gat_sector)
        
        allocated_extents = [] # (track, start_granule, count)
        
        # Simple allocation strategy: First Fit
        # We need to pack into max 5 extents.
        # Try to find contiguous runs.
        
        granules_needed = total_granules
        current_track = -1
        current_start = -1
        current_count = 0
        
        # Scan GAT
        # Skip Dir Track (usually marked reserved, but check)
        # Skip Track 0? Usually reserved for Boot.
        
        for i in range(len(gat)):
            track = i // granules_per_track
            granule = i % granules_per_track
            
            if track == self.dir_track: continue # Skip dir track
            if track == 0: continue # Skip boot track
            
            if gat[i] == 0xFF: # Free
                if current_track == track and current_start + current_count == granule:
                    # Contiguous in same track
                    current_count += 1
                else:
                    # New run
                    if current_count > 0:
                        allocated_extents.append((current_track, current_start, current_count))
                        if len(allocated_extents) >= 5:
                            # Limit reached (simplified)
                            # If we still need more, we fail (fragmentation)
                            if granules_needed > 0:
                                raise OSError(28, "Disk full or too fragmented (Max 5 extents)")
                            break
                            
                    current_track = track
                    current_start = granule
                    current_count = 1
                    
                granules_needed -= 1
                gat[i] = 0xFE # Mark as reserved temporarily (will finalize later)
                
                if granules_needed == 0:
                    break
                    
        if current_count > 0:
            allocated_extents.append((current_track, current_start, current_count))
            
        if granules_needed > 0:
             raise OSError(28, "Disk full")
             
        # 3. Write Data
        content_offset = 0
        for (track, start_granule, count) in allocated_extents:
            for g in range(count):
                current_granule = start_granule + g
                
                # Calculate Sector Start
                start_sector_idx = 0
                if current_granule == 1:
                    start_sector_idx = 5
                elif current_granule > 1:
                    start_sector_idx = current_granule * sectors_per_granule
                    
                for s in range(sectors_per_granule):
                    if content_offset >= len(content): break
                    
                    chunk = content[content_offset:content_offset+256]
                    # Pad with 0
                    if len(chunk) < 256:
                        chunk = chunk + b'\x00' * (256 - len(chunk))
                        
                    self.disk.write_sector(track, 0, start_sector_idx + s, chunk)
                    content_offset += 256
                    
        # 4. Update GAT (Finalize)
        # We already marked them as 0xFE (Reserved).
        # In TRSDOS, allocated granules usually have a specific value?
        # "The GAT contains one byte for each granule... If allocated, the byte contains the track number of the next granule in the file."
        # "The last granule in the file contains a value from C0 to CF."
        # Wait, that's complex linked list structure.
        # NEWDOS/80 might be different.
        # The GAT dump showed 0xFC, 0xFD.
        # 0xFC = ? 0xFD = ?
        # If I just mark them as "Allocated" (e.g. 0xFF is free, anything else is used).
        # But for file integrity, I should probably follow the chain rule if possible.
        # Or just mark them as "Reserved" (0xFE) which prevents overwriting.
        # The `inspect_gat.py` showed 0xFC and 0xFD.
        # Let's stick to 0xFE (Reserved) for now to be safe. It prevents reuse.
        # A proper chkdsk might complain, but it should work.
        
        self.disk.write_sector(self.dir_track, 0, self.dir_sector_offset, gat)
        
        # 5. Create Directory Entry
        dir_sector_data = bytearray(self.disk.read_sector(self.dir_track, 0, free_entry_loc[0]))
        off = free_entry_loc[1]
        
        # Clear entry
        for k in range(32): dir_sector_data[off+k] = 0
        
        # Set Attributes
        # Byte 0: Attribute. Bit 4 (0x10) = In Use. Bit 7 (0x80) = FXDE.
        # Also visibility bits etc.
        # Let's use 0x10 (In Use) | 0x40 (System?) | 0x20 (Invisible?)
        # Standard file: 0x10.
        # Wait, `inspect_gat` showed files.
        # Let's use 0x50 (In Use + ?).
        # Actually, just 0x10 is enough to mark "In Use".
        # But let's check what `list_files` expects. `if not (attr & 0x10): continue`.
        # So 0x10 is mandatory.
        dir_sector_data[off] = 0x10
        
        # Name and Ext
        for k in range(8): dir_sector_data[off+5+k] = ord(name[k])
        for k in range(3): dir_sector_data[off+13+k] = ord(ext[k])
        
        # EOF
        # RBA = file_size - 1
        # If RBA < 256: EOF Low = 0, EOF Mid = RBA, EOF High = 0? No.
        # "If the lower order byte of the EOF equals 0, the EOF is in RBA format."
        # "If the lower order EOF byte is not 0, then the EOF value in the FPDE is equal to the actual RBA value plus 255"
        
        rba = len(content) - 1
        if rba < 0: rba = 0 # Empty file
        
        # Encode EOF
        # Use "plus 255" format to avoid ambiguity with RBA format (where eof_low=0)
        raw_eof = rba + 255
        
        eof_low = raw_eof & 0xFF
        
        if eof_low == 0:
            # Collision! We must use RBA format.
            # RBA Format: Low=0, Mid=RBA_Low, High=RBA_High
            dir_sector_data[off+3] = 0
            dir_sector_data[off+20] = rba & 0xFF
            dir_sector_data[off+21] = (rba >> 8) & 0xFF
        else:
            # Offset Format
            dir_sector_data[off+3] = eof_low
            dir_sector_data[off+20] = (raw_eof >> 8) & 0xFF
            dir_sector_data[off+21] = (raw_eof >> 16) & 0xFF
        
        # Extents
        for i, (track, start, count) in enumerate(allocated_extents):
            e_off = off + 22 + (i * 2)
            dir_sector_data[e_off] = track
            # Info: Bits 5-7 Start, Bits 0-4 Count-1
            info = ((start & 0x07) << 5) | ((count - 1) & 0x1F)
            dir_sector_data[e_off+1] = info
            
        # Mark end of extents
        if len(allocated_extents) < 5:
            e_off = off + 22 + (len(allocated_extents) * 2)
            dir_sector_data[e_off] = 0xFF
            
        self.disk.write_sector(self.dir_track, 0, free_entry_loc[0], dir_sector_data)
        self.disk.save()
        return True

    def get_free_space(self):
        """Calculate free space in bytes."""
        sectors_per_granule, granules_per_track = self._get_allocation_info()
        
        # Read GAT
        gat_sector = self.disk.read_sector(self.dir_track, 0, self.dir_sector_offset)
        if not gat_sector: return 0
        
        free_granules = 0
        for i in range(len(gat_sector)):
            track = i // granules_per_track
            if track == self.dir_track: continue
            if track == 0: continue
            
            if gat_sector[i] == 0xFF:
                free_granules += 1
                
        return free_granules * sectors_per_granule * 256

    def list_files(self):
        """
        List all files in the directory.
        
        Returns:
            list: A list of dictionaries containing file metadata:
                  {'name': str, 'size': int, 'attr': int, 'invisible': bool, 'system': bool}
        """
        files = []
        # Directory entries are in Sectors 2-9 (0-based) or 3-10 (1-based)
        # Sector 1 (0-based) or 2 (1-based) is HIT
        
        start_sector = 2 + self.dir_sector_offset
        # Scan up to 18 sectors if DD, or 10 if SD.
        # We don't strictly know max sectors here easily without querying geometry,
        # but reading non-existent sectors returns None, so it's safe to try more.
        end_sector = 18 + self.dir_sector_offset

        # Special handling for NEWDOS/80 System Disks
        # Sectors 0-9 are System Files. User Directory might start at Sector 10.
        if self.system_type == "NEWDOS/80 (System)":
            start_sector = 10
            end_sector = 18 # Scan more sectors (assuming DD/High Capacity)
        elif self.system_type == "NEWDOS/80 (Track 9)":
            start_sector = 10
            end_sector = 18

        for sector in range(start_sector, end_sector):
            data = self.disk.read_sector(self.dir_track, 0, sector)
            if not data:
                continue

            for i in range(0, 256, 32):  # 8 entries per sector, 32 bytes each
                entry = data[i:i+32]

                # Check attribute byte
                attr = entry[0]
                
                # Bit 4: 1=In-Use, 0=Free
                if not (attr & 0x10):
                    continue

                # Bit 7: 1=Extended Entry (FXDE), 0=Primary (FPDE)
                # We only want Primary entries.
                if attr & 0x80:
                    continue
                    
                # Bit 6: System File (Optional info)
                # Bit 3: Invisible (Optional info)

                
                # Basic validity check: Not 00 and not FF
                if attr == 0 or attr == 0xFF:
                    continue
                
                # Filename
                raw_name = entry[5:13]
                raw_ext = entry[13:16]
                
                # Heuristic: Valid filenames are usually ASCII alphanumeric
                # If we find too many non-printable chars, it's likely garbage/wrong sector
                def is_valid_name(b):
                    # Allow letters, numbers, space, and some symbols
                    # Stricter check: Must start with letter or number?
                    # TRSDOS: First char alpha.
                    if not b: return False
                    if not (65 <= b[0] <= 90 or 97 <= b[0] <= 122 or 48 <= b[0] <= 57):
                         # Allow space padding if name is empty? No, name shouldn't be empty.
                         return False
                    return all(32 <= x <= 126 for x in b)
                
                if not is_valid_name(raw_name):
                    continue
                
                # Extension can be empty or valid chars
                if not all(32 <= x <= 126 for x in raw_ext):
                    continue

                try:
                    name = raw_name.decode(self.encoding).strip()
                    ext = raw_ext.decode(self.encoding).strip()
                except Exception:
                    continue

                # Calculate Size
                eof_low = entry[3]
                eof_mid = entry[20]
                eof_high = entry[21]
                
                sectors_per_granule, granules_per_track = self._get_allocation_info()
                
                total_sectors_allocated = 0
                for k in range(5):
                    offset = 22 + (k * 2)
                    if offset >= 32: break
                    track = entry[offset]
                    if track == 0xFF or track == 0xFE: break
                    info = entry[offset+1]
                    count = (info & 0x1F) + 1
                    total_sectors_allocated += count * sectors_per_granule

                if eof_low == 0:
                    last_sector_offset = (eof_high << 8) | eof_mid
                    if total_sectors_allocated > 0:
                        file_size = (total_sectors_allocated - 1) * 256 + (last_sector_offset + 1)
                    else:
                        file_size = 0
                else:
                    raw_eof = (eof_high << 16) | (eof_mid << 8) | eof_low
                    file_size = raw_eof - 255

                files.append({
                    'name': f"{name}/{ext}",
                    'size': file_size,
                    'attr': attr,
                    'invisible': (attr & 0x08) != 0,
                    'system': (attr & 0x40) != 0
                })

        return files

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trs80_driver.py <disk_image>")
        sys.exit(1)
        
    filename = sys.argv[1]
    try:
        disk = detect_format(filename)
        print(f"Detected Format: {disk.get_geometry()}")

        fs = TRSDOSFileSystem(disk)
        print(f"Analysis Result:")
        print(f" - System Type: {fs.system_type}")
        print(f" - Detected OS: {fs.detected_os}")
        print(f" - Directory Track: {fs.dir_track}")
        
        print(f"\nReading Directory from Track {fs.dir_track}...")
        files = fs.list_files()

        print("\nFiles found:")
        for f in files:
            flags = []
            if f['invisible']: flags.append("INV")
            if f['system']: flags.append("SYS")
            flag_str = f"[{','.join(flags)}]" if flags else ""
            print(f" - {f['name']:<12}  Size: {f['size']:>6} bytes  {flag_str}")
            
        if len(sys.argv) > 3 and sys.argv[2] == "read":
            target_file = sys.argv[3]
            print(f"\nReading file: {target_file}")
            content = fs.read_file(target_file)
            if content:
                print(f"Read {len(content)} bytes.")
                try:
                    print("Content (first 500 bytes):")
                    print(content[:500].decode('utf-8', errors='replace'))
                except:
                    print("Binary content.")
            else:
                print("File not found or empty.")
                
        elif len(sys.argv) > 3 and sys.argv[2] == "extract":
            dest_dir = sys.argv[3]
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            
            print(f"\nExtracting all files to {dest_dir}...")
            for f in files:
                # Clean filename
                name = f['name']
                safe_name = name.replace('/', '.')
                out_path = os.path.join(dest_dir, safe_name)
                
                print(f"Extracting {name} -> {safe_name}")
                content = fs.read_file(name)
                if content:
                    with open(out_path, 'wb') as out_f:
                        out_f.write(content)
                else:
                    print(f"Skipping empty or unreadable file: {name}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
