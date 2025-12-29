# trsmount - TRS-80 Disk Image FUSE Driver

**trsmount** allows you to mount TRS-80 disk images (`.dmk`, `.dsk`) as local directories on your computer. This enables you to read and write files to legacy TRSDOS and NEWDOS/80 disks using standard tools like Finder, Explorer, or the terminal.

![TRS-80 Floppy Disk](https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/TRS-80_Model_III.jpg/640px-TRS-80_Model_III.jpg)
*(Image placeholder: Imagine a 5.25" floppy disk with a Radio Shack logo here)*

## Motivation

Accessing data on vintage TRS-80 disk images often requires specialized tools or emulators. **trsmount** bridges the gap by integrating these images directly into your modern operating system. Whether you are researching old software, recovering data, or just curious about the file structures of the 80s, this tool makes it seamless.

## Features

- **Read/Write Support**: Copy files to and from disk images.
- **Format Support**: Handles DMK and DSK container formats.
- **Filesystem Support**: Supports TRSDOS 2.3 and NEWDOS/80 filesystems.
- **Superzap Utility**: Includes a sector-level inspector for low-level analysis.

## Prerequisites

- **macOS**: Requires [FUSE-T](https://github.com/macos-fuse-t/fuse-t) (recommended) or macFUSE.
- **Linux**: Requires `libfuse`.
- **Python 3.6+**

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/timw/trsmount.git
   cd trsmount
   ```

2. Run the setup script:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
   
   The script will offer to install the tools system-wide (e.g., `/usr/local/bin/trsmount`).

## Usage

### Mounting a Disk

```bash
trsmount disk.dmk ./mnt
```

You can now access `./mnt` to see the files. When finished, unmount the directory:

```bash
umount ./mnt
# or on macOS
diskutil unmount ./mnt
```

### Inspecting a Disk (Superzap)

Use the `superzap` utility to view raw sectors:

```bash
superzap disk.dmk
```

## Resources

- [Tim Mann's TRS-80 Pages](http://www.tim-mann.org/trs80.html) - Essential emulator and technical info.
- [Ira Goldklang's TRS-80 Revived Site](http://www.trs-80.com/) - Comprehensive history and archive.
- [48k.ca](https://48k.ca/) - George Philips great pool of resources, including world's most famous trs80gp TRS-80 emulator.
- [Willus.com TRS-80 Library](http://www.willus.com/trs80/) - Massive archive of manuals and software.

## License

MIT License
