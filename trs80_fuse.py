#!/usr/bin/env python3
"""
TRS-80 FUSE Filesystem Implementation.

This module provides a FUSE (Filesystem in Userspace) interface for TRS-80 disk images.
It allows mounting .dmk and .dsk images as local directories, enabling standard file
operations (ls, cp, cat, etc.) on TRSDOS/NEWDOS files.

Dependencies:
    - fusepy
    - trs80_driver
"""

import os
import sys
import errno
import time
import logging

# Configure FUSE library path for macOS with FUSE-T
if sys.platform == 'darwin' and not os.environ.get('FUSE_LIBRARY_PATH'):
    if os.path.exists('/usr/local/lib/libfuse-t.dylib'):
        os.environ['FUSE_LIBRARY_PATH'] = '/usr/local/lib/libfuse-t.dylib'

from fuse import FUSE, FuseOSError, Operations
from trs80_driver import detect_format, TRSDOSFileSystem

class TRSDOS_FUSE(Operations):
    """
    FUSE Operations implementation for TRSDOS filesystems.
    
    Handles mapping between POSIX filesystem calls and TRSDOS disk operations.
    Implements a write-back cache for file modifications.
    """
    def __init__(self, disk_image):
        self.disk_image = disk_image
        self.disk = detect_format(disk_image)
        self.fs = TRSDOSFileSystem(self.disk)
        print(f"Mounted {disk_image} ({self.fs.system_type})")
        
        # Cache directory listing
        self.files = {} # filename -> trsdos_name
        self.file_stats = {} # filename -> dict (size, attr, etc)
        self.buffers = {} # path -> bytearray
        self.failed_paths = set() # Paths that failed to write
        self._refresh_files()

    def _refresh_files(self):
        self.files = {}
        self.file_stats = {}
        file_list = self.fs.list_files()
        # Deduplicate and clean names
        for f in file_list:
            # f is now a dict: {'name': 'NAME/EXT', 'size': 123, ...}
            trsdos_name = f['name']
            
            # Map to "NAME.EXT" for modern OS
            if '/' in trsdos_name:
                name, ext = trsdos_name.split('/', 1)
                filename = f"{name}.{ext}"
            else:
                filename = trsdos_name
                
            self.files[filename] = trsdos_name
            self.file_stats[filename] = f

    def _get_trsdsk_name(self, path):
        filename = path[1:] # Remove leading /
        if filename in self.files:
            return self.files[filename]
        
        # Convert new filename to TRSDOS format
        # NAME.EXT -> NAME/EXT
        if '.' in filename:
            name, ext = filename.rsplit('.', 1)
            return f"{name}/{ext}".upper()
        return f"{filename}/   ".upper()

    def getattr(self, path, fh=None):
        if path == '/':
            return dict(st_mode=(0o40755), st_nlink=2)
        
        filename = path[1:]
        
        # Check if in buffer (being written)
        if path in self.buffers:
            size = len(self.buffers[path])
            return dict(st_mode=(0o100644), st_nlink=1, st_size=size, 
                        st_ctime=time.time(), st_mtime=time.time(), st_atime=time.time())

        if filename in self.files:
            stats = self.file_stats.get(filename, {})
            size = stats.get('size', 0)
            
            # Handle attributes
            # UF_HIDDEN = 0x8000 (macOS/BSD)
            # Linux doesn't support st_flags in standard stat, but FUSE might pass it.
            # For visibility, we can also rely on the dot-prefix convention, but that changes names.
            # Let's try setting st_flags for macOS.
            st_flags = 0
            if stats.get('invisible', False):
                st_flags = 0x8000
                
            return dict(st_mode=(0o100644), st_nlink=1, st_size=size, 
                        st_ctime=time.time(), st_mtime=time.time(), st_atime=time.time(),
                        st_flags=st_flags)
            
        raise FuseOSError(errno.ENOENT)

    def readdir(self, path, fh):
        if path != '/':
            return []
        # Include files in buffer (newly created)
        buffered_files = [p[1:] for p in self.buffers.keys() if p not in self.failed_paths]
        all_files = list(self.files.keys()) + buffered_files
        return ['.', '..'] + list(set(all_files))

    def create(self, path, mode, fi=None):
        self.buffers[path] = bytearray()
        self.failed_paths.discard(path)
        return 0

    def open(self, path, flags):
        self.failed_paths.discard(path)
        # If opening for write, load content
        if (flags & os.O_WRONLY) or (flags & os.O_RDWR):
            if path not in self.buffers:
                filename = path[1:]
                if filename in self.files:
                    content = self.fs.read_file(self.files[filename])
                    self.buffers[path] = bytearray(content) if content else bytearray()
                else:
                    self.buffers[path] = bytearray()
        return 0

    def read(self, path, length, offset, fh):
        if path in self.buffers:
            return bytes(self.buffers[path][offset:offset+length])
            
        filename = path[1:]
        if filename in self.files:
            content = self.fs.read_file(self.files[filename])
            if content:
                return bytes(content[offset:offset+length])
        return b''

    def write(self, path, buf, offset, fh):
        if path not in self.buffers:
            self.buffers[path] = bytearray()
            
        end = offset + len(buf)
        
        # Check free space
        # We must account for all data currently buffered in memory but not yet on disk
        total_buffered = sum(len(b) for p, b in self.buffers.items() if p != path)
        free_space = self.fs.get_free_space()
        
        if (total_buffered + end) > free_space:
             self.failed_paths.add(path)
             if path in self.buffers: del self.buffers[path]
             raise FuseOSError(errno.ENOSPC)

        if end > len(self.buffers[path]):
            self.buffers[path].extend(b'\x00' * (end - len(self.buffers[path])))
        
        self.buffers[path][offset:end] = buf
        return len(buf)

    def truncate(self, path, length, fh=None):
        if path not in self.buffers:
             # Load first
             self.open(path, os.O_RDWR)
             
        if len(self.buffers[path]) > length:
            self.buffers[path] = self.buffers[path][:length]
        elif len(self.buffers[path]) < length:
            free_space = self.fs.get_free_space()
            if length > free_space:
                raise FuseOSError(errno.ENOSPC)
            self.buffers[path].extend(b'\x00' * (length - len(self.buffers[path])))
        return 0

    def unlink(self, path):
        if path in self.buffers:
            del self.buffers[path]
            
        filename = path[1:]
        if filename in self.files:
            trsdos_name = self.files[filename]
            if self.fs.delete_file(trsdos_name):
                self._refresh_files()
                return 0
        return 0

    def release(self, path, fh):
        if path in self.buffers:
            trsdos_name = self._get_trsdsk_name(path)
            try:
                # Final check before committing to disk
                if len(self.buffers[path]) > self.fs.get_free_space():
                    print(f"Error writing {path}: Disk full (release)")
                    self.failed_paths.add(path)
                    del self.buffers[path]
                    return 0

                self.fs.write_file(trsdos_name, self.buffers[path])
                del self.buffers[path]
                self._refresh_files()
            except Exception as e:
                print(f"Error writing {path}: {e}")
                # If write failed, remove from buffer so it doesn't persist as a ghost file
                self.failed_paths.add(path)
                del self.buffers[path]
                # We can't return error here, but at least ls won't show it anymore
        return 0

    def statfs(self, path):
        # Return dummy stats
        return dict(f_bsize=256, f_frsize=256, f_blocks=1000, f_bfree=500, f_bavail=500)

    def access(self, path, mode):
        return 0

    def chmod(self, path, mode):
        return 0

    def chown(self, path, uid, gid):
        return 0

    def utimens(self, path, times=None):
        return 0



if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Mount TRS-80 disk images (DMK/JV1/JV3) as a FUSE filesystem.",
        epilog="Example: trsmount disk.dmk ./mnt"
    )
    parser.add_argument("disk_image", help="Path to the disk image file (.dmk, .dsk)")
    parser.add_argument("mountpoint", help="Directory to mount the filesystem")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--foreground", "-f", action="store_true", help="Run in foreground (default: False)")
    
    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    if not os.path.exists(args.mountpoint):
        print(f"Error: Mount point '{args.mountpoint}' does not exist.")
        sys.exit(1)
        
    try:
        # allow_other is often needed for Finder access, but requires permissions
        # foreground=True blocks, foreground=False daemonizes
        fuse = FUSE(TRSDOS_FUSE(args.disk_image), args.mountpoint, foreground=args.foreground, ro=False, nothreads=True)
    except Exception as e:
        print(f"Failed to mount: {e}")
        print("Ensure FUSE-T or macFUSE is installed and libfuse is available.")
        sys.exit(1)
