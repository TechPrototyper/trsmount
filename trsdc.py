#!/usr/bin/env python3
"""
trsdc - TRS-80 Disk Convert Utility.

Converts TRS-80 disk images between DMK, JV3, and JV1/Raw formats with
automatic format detection and optional geometry specification flags.

Usage:
    trsdc -i <input_file> -o <output_file> [-if <spec>] [-of <spec>] [-v]
"""

import sys
import os
import argparse
import trs80_driver


def parse_format_spec(spec):
    """
    Parse a format specification string into a geometry dictionary.
    
    Examples:
        'dmk'
        'format=jv3,tracks=40,sides=1,density=sd'
        'jv1,40t,1s,sd'
    """
    if not spec:
        return {}

    res = {}
    tokens = [t.strip() for t in spec.replace(';', ',').split(',') if t.strip()]

    for token in tokens:
        if '=' in token:
            k, v = token.split('=', 1)
            k = k.strip().lower()
            v = v.strip().lower()
            if k in ('format', 'fmt', 'type'):
                res['format'] = v
            elif k in ('tracks', 'track', 't', 'cyl', 'cylinders'):
                res['tracks'] = int(v)
            elif k in ('sides', 'side', 'heads', 'head', 's', 'h'):
                res['sides'] = int(v)
            elif k in ('density', 'den', 'd'):
                res['density'] = 'sd' if 's' in v else 'dd'
            elif k in ('sectors', 'sectr', 'spt', 'sectors_per_track'):
                res['sectors_per_track'] = int(v)
            elif k in ('secsize', 'size', 'bytes'):
                res['sector_size'] = int(v)
        else:
            token_lower = token.lower()
            if token_lower in ('dmk', 'jv3', 'jv1', 'dsk', 'raw'):
                res['format'] = 'jv3' if token_lower == 'dsk' else ('jv1' if token_lower == 'raw' else token_lower)
            elif token_lower.endswith('t') and token_lower[:-1].isdigit():
                res['tracks'] = int(token_lower[:-1])
            elif token_lower.endswith('s') and token_lower[:-1].isdigit():
                res['sides'] = int(token_lower[:-1])
            elif token_lower in ('sd', 'single', 'fm'):
                res['density'] = 'sd'
            elif token_lower in ('dd', 'double', 'mfm'):
                res['density'] = 'dd'
            elif token_lower.isdigit():
                num = int(token_lower)
                if num in (35, 40, 77, 80):
                    res['tracks'] = num
                elif num in (1, 2):
                    res['sides'] = num
                elif num in (10, 18):
                    res['sectors_per_track'] = num

    return res


def infer_format_from_filename(filename):
    """Infer disk format string from filename extension."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.dmk':
        return 'dmk'
    elif ext in ('.jv3', '.dsk'):
        return 'jv3'
    elif ext == '.jv1':
        return 'jv1'
    return 'jv3'


def main():
    prog_name = os.environ.get("TRS_PROG_NAME", "trsdc")

    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="TRS-80 Disk Convert Utility (trsdc)."
    )
    parser.add_argument("-i", "--input", required=True, help="Input disk image file path")
    parser.add_argument("-o", "--output", required=True, help="Output disk image file path")
    parser.add_argument("-if", "--input-format", help="Input format/geometry specification (e.g. 'dmk', 'tracks=40,sides=1,density=sd')")
    parser.add_argument("-of", "--output-format", help="Output format/geometry specification (e.g. 'jv3', 'tracks=80,sides=2,density=dd')")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed conversion progress")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.", file=sys.stderr)
        sys.exit(1)

    in_spec = parse_format_spec(args.input_format)
    out_spec = parse_format_spec(args.output_format)

    # 1. Load input disk
    input_disk = trs80_driver.detect_format(args.input, format_hint=in_spec.get('format'))
    in_geom = input_disk.get_geometry_info()

    # Override input geometry if specified in -if
    for k in ('tracks', 'sides', 'sectors_per_track', 'density', 'sector_size'):
        if k in in_spec:
            in_geom[k] = in_spec[k]

    sectors_map = input_disk.get_all_sectors()

    if args.verbose:
        print(f"Input File: {args.input}")
        print(f"Detected Format: {in_geom.get('format', 'unknown').upper()}")
        print(f"Input Geometry: {in_geom.get('tracks')} Tracks, {in_geom.get('sides')} Side(s), "
              f"{in_geom.get('sectors_per_track')} Sectors/Track, Density: {in_geom.get('density', 'sd').upper()}")
        print(f"Sectors Read: {len(sectors_map)}")

    # 2. Determine target format & geometry
    out_fmt = out_spec.get('format') or infer_format_from_filename(args.output)

    out_geom = dict(in_geom)
    out_geom['format'] = out_fmt

    for k in ('tracks', 'sides', 'sectors_per_track', 'density', 'sector_size'):
        if k in out_spec:
            out_geom[k] = out_spec[k]

    if args.verbose:
        print(f"\nTarget File: {args.output}")
        print(f"Target Format: {out_fmt.upper()}")
        print(f"Target Geometry: {out_geom.get('tracks')} Tracks, {out_geom.get('sides')} Side(s), "
              f"{out_geom.get('sectors_per_track')} Sectors/Track, Density: {out_geom.get('density', 'sd').upper()}")

    # 3. Export to target format buffer
    if out_fmt == 'dmk':
        output_buffer = trs80_driver.export_dmk(sectors_map, out_geom)
    elif out_fmt == 'jv3':
        output_buffer = trs80_driver.export_jv3(sectors_map, out_geom)
    elif out_fmt == 'jv1':
        output_buffer = trs80_driver.export_jv1(sectors_map, out_geom)
    else:
        print(f"Error: Unsupported output format '{out_fmt}'.", file=sys.stderr)
        sys.exit(1)

    # 4. Write output file
    try:
        with open(args.output, 'wb') as f:
            f.write(output_buffer)
    except Exception as e:
        print(f"Error writing to '{args.output}': {e}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Successfully wrote {len(output_buffer)} bytes to '{args.output}'.")
    else:
        print(f"Converted '{args.input}' -> '{args.output}' [{out_fmt.upper()}] ({len(sectors_map)} sectors)")


if __name__ == '__main__':
    main()
