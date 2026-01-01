#!/usr/bin/env python3
import sys
import os
import argparse
import re

PSEUDO_OPS = {
    'EQU', 'DEFL', 'DEFB', 'DEFW', 'DEFS', 'DEFM', 'ORG', 'END', 'ENT'
}

Z80_OPS = {
    'ADC', 'ADD', 'AND', 'BIT', 'CALL', 'CCF', 'CP', 'CPD', 'CPDR', 'CPI', 'CPIR',
    'CPL', 'DAA', 'DEC', 'DI', 'DJNZ', 'EI', 'EX', 'EXX', 'HALT', 'IM', 'IN',
    'INC', 'IND', 'INDR', 'INI', 'INIR', 'JP', 'JR', 'LD', 'LDD', 'LDDR', 'LDI',
    'LDIR', 'NEG', 'NOP', 'OR', 'OTDR', 'OTIR', 'OUT', 'OUTD', 'OUTI', 'POP',
    'PUSH', 'RES', 'RET', 'RETI', 'RETN', 'RL', 'RLA', 'RLC', 'RLCA', 'RLD',
    'RR', 'RRA', 'RRC', 'RRCA', 'RRD', 'RST', 'SBC', 'SCF', 'SET', 'SLA', 'SRA',
    'SRL', 'SUB', 'XOR'
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
        last_was_cr = False
        
        for b in content:
            val = b & 0x7F # Strip high bit
            
            if val == 0x0D: # CR -> Newline
                line_str = current_line.decode('ascii', errors='replace')
                decoded_lines.append(line_str)
                current_line = bytearray()
                last_was_cr = True
            elif val == 0x0A: # LF
                if last_was_cr:
                    last_was_cr = False
                    continue # Ignore LF after CR
                
                # LF without CR (Unix style)
                line_str = current_line.decode('ascii', errors='replace')
                decoded_lines.append(line_str)
                current_line = bytearray()
                last_was_cr = False
            else:
                current_line.append(val)
                last_was_cr = False
                
        if current_line:
            decoded_lines.append(current_line.decode('ascii', errors='replace'))

        # Print with smart formatting
        for line in decoded_lines:
            # Hybrid Parsing Logic
            # 1. Try Tab-Separated (Standard TRS-80 EDTASM)
            parts = line.split('\t', 1)
            
            if len(parts) > 1:
                # Tab found: Assume Line#+Label <TAB> Opcode+Rest
                prefix = parts[0]
                rest = parts[1]
                
                # Parse prefix (LineNum + Label)
                match = re.match(r'^(\d+)(\s*)(.*)$', prefix)
                if match:
                    line_num = match.group(1)
                    spacer = match.group(2)
                    label = match.group(3)
                else:
                    line_num = ""
                    spacer = ""
                    label = prefix
            else:
                # No Tab found: Assume Space-Separated or Fixed Width
                # Logic: 
                # 1. Extract Line Number (if any)
                # 2. Analyze remaining content:
                #    - Starts with whitespace -> No Label
                #    - Starts with non-whitespace -> Label is first word
                
                match = re.match(r'^(\d+)(\s*)(.*)$', line)
                if match:
                    line_num = match.group(1)
                    spacer = match.group(2)
                    content = match.group(3)
                else:
                    line_num = ""
                    spacer = ""
                    content = line
                
                # Analyze content for Label
                if content and not content[0].isspace():
                    # Starts with non-whitespace: First word is Label
                    subparts = content.split(maxsplit=1)
                    label = subparts[0]
                    rest = subparts[1] if len(subparts) > 1 else ""
                    
                    # Safety Check: Is the "Label" actually an Opcode?
                    # e.g. "00100 NOP" -> NOP might be opcode if user forgot indent
                    if label.upper() in PSEUDO_OPS or label.upper() in Z80_OPS:
                        # It's likely an opcode, not a label
                        label = ""
                        rest = content
                else:
                    # Starts with whitespace: No Label
                    label = ""
                    rest = content.lstrip() # Remove leading indent for 'rest'

            # Handle -c (Add colon)
            if args.cc and label and not label.startswith(';') and not label.endswith(':'):
                # Check opcode (from rest) to ensure we don't colonize if it's a pseudo-op?
                # Original logic checked opcode.
                opcode = ""
                if rest:
                    opcode = rest.strip().split()[0]
                
                # Only add colon if opcode is NOT a pseudo-op (like EQU)
                # AND the label itself is not a pseudo-op (double check)
                if opcode.upper() not in PSEUDO_OPS:
                     label += ":"

            # Handle -n (No line numbers)
            if args.nolinenumbers:
                if label:
                    print(f"{label}\t{rest}")
                else:
                    print(f"\t{rest}")
            else:
                # With line numbers:
                # Line#  Label  Opcode
                
                # Construct prefix (Line + Label)
                prefix_str = ""
                if line_num:
                    prefix_str += f"{line_num}  "
                if label:
                    prefix_str += label
                
                # Calculate padding to align Opcode
                # Target column for Opcode: 16?
                if len(prefix_str) < 16:
                    padding = " " * (16 - len(prefix_str))
                else:
                    padding = " "
                
                print(f"{prefix_str}{padding}{rest}")

    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
