import sys

def inspect():
    filename = "test/mnt/3DTTTTAS.ASM"
    with open(filename, 'rb') as f:
        content = f.read()
    
    # Strip high bits
    stripped = bytes(b & 0x7F for b in content)
    
    # Find RAN10
    idx = stripped.find(b"RAN10")
    if idx == -1:
        print("RAN10 not found")
        return

    # Get context
    start = max(0, idx - 50)
    end = min(len(stripped), idx + 100)
    chunk = stripped[start:end]
    
    print(f"Context around RAN10 (bytes): {chunk}")
    
    # Split into lines to see structure
    lines = chunk.split(b'\r')
    for line in lines:
        print(f"Line: {line}")

if __name__ == "__main__":
    inspect()
