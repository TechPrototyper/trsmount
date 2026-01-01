#!/usr/bin/env python3
import sys
import os
import argparse
import re

PSEUDO_OPS = {
    'EQU', 'DEFL', 'DEFB', 'DEFW', 'DEFS', 'DEFM', 'ORG', 'END', 'ENT'
}

def main():
    # Allow overriding program name via environment variable (for wrapper scripts)
    prog_name = os.environ.get("TRS_PROG_NAME")

    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="Display TRS-80 ASM files."
    )
    parser.add_argument("filename", help="The ASM file to read")
    parser.add_argument("-n", "--nolinenumbers", action="store_true", help="Remove line numbers")
    parser.add_argument("-c", "--cc", action="store_true", help="Add colons to code labels")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.filename):
        print(f"Error: File '{args.filename}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.filename, 'rb') as f:
            content = f.read()
            
        # Process content
        decoded_lines = []
        current_line = bytearray()
        
        for b in content:
            val = b & 0x7F # Strip high bit
            
            if val == 0x0D: # CR -> Newline
                line_str = current_line.decode('ascii', errors='replace')
                decoded_lines.append(line_str)
                current_line = bytearray()
            elif val == 0x0A: # LF
                pass 
            else:
                current_line.append(val)
                
        if current_line:
            decoded_lines.append(current_line.decode('ascii', errors='replace'))

        # Print with smart formatting
        for line in decoded_lines:
            # Split by first tab to separate (Line# + Label) from (Opcode + Rest)
            parts = line.split('\t', 1)
            
            prefix = parts[0]
            rest = parts[1] if len(parts) > 1 else ""
            
            # Parse prefix (LineNum + Label)
            # Regex: Start with digits, optional space, optional label
            match = re.match(r'^(\d+)(\s*)(.*)$', prefix)
            
            if match:
                line_num = match.group(1)
                spacer = match.group(2)
                label = match.group(3)
            else:
                # Fallback if no line number found
                line_num = ""
                spacer = ""
                label = prefix

            # Handle -c (Add colon)
            if args.cc and label and not label.startswith(';'):
                # Check opcode
                opcode = ""
                if rest:
                    opcode = rest.strip().split()[0]
                
                if opcode and opcode.upper() not in PSEUDO_OPS:
                    label += ":"

            # Handle -n (No line numbers)
            if args.nolinenumbers:
                display_prefix = label
                min_width = 8
            else:
                # Reconstruct prefix
                # If label exists, ensure spacer exists
                if label and not spacer:
                    spacer = " "
                display_prefix = f"{line_num}{spacer}{label}"
                min_width = 16

            # Calculate padding
            prefix_len = len(display_prefix)
            
            # Round up to next tab stop (8 chars)
            target_len = (prefix_len // 8 + 1) * 8
            if target_len < min_width:
                target_len = min_width
                
            padded_prefix = display_prefix.ljust(target_len)
            
            full_line = padded_prefix + rest
            
            # Expand tabs for the rest of the line
            expanded = full_line.expandtabs(8)
            print(expanded)
            
            # Stop at END
            parts_split = expanded.split()
            if len(parts_split) > 0 and parts_split[0] == "END":
                 break
            if len(parts_split) > 1 and parts_split[1] == "END":
                 break

    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
