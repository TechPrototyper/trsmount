import sys

def find_end(filename):
    with open(filename, 'rb') as f:
        content = f.read()
    
    stripped = bytes(b & 0x7F for b in content)
    
    # Search for "END"
    offset = -1
    while True:
        offset = stripped.find(b"END", offset + 1)
        if offset == -1: break
        
        print(f"Found END at {offset}")
        print(f"Context: {stripped[offset:offset+20]}")

if __name__ == "__main__":
    find_end("test/mnt/3DTTTTAS.ASM")
