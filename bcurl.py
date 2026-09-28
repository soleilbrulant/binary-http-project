import socket
import struct
import sys
import argparse

# --- PROTOCOL CONSTANTS ---
FRAME_TYPE_HEADERS = 1
FRAME_TYPE_DATA = 2

HEADER_SIZE = 8

STATIC_TABLE = {
    1: ":method",
    2: ":path",
    3: ":status",
    4: "content-type",
    5: "content-length",
    6: "server",
    7: "connection",
    8: "accept",
    9: "user-agent",
    10: "date"
}
REVERSE_STATIC_TABLE = {v: k for k, v in STATIC_TABLE.items()}

def hexdump(data):
    """Returns a nicely formatted string representation of bytes in hex format."""
    return " ".join(f"{b:02x}" for b in data)

def encode_headers(headers):
    payload = b""
    for name, value in headers:
        name = name.lower()
        value_bytes = value.encode('utf-8')
        if name in REVERSE_STATIC_TABLE:
            idx = REVERSE_STATIC_TABLE[name]
            # 1 bit for indexed, 7 bits for index
            b = 0x80 | (idx & 0x7F)
            payload += struct.pack("!BH", b, len(value_bytes)) + value_bytes
        else:
            name_bytes = name.encode('utf-8')
            # 1 bit for literal (0), 7 bits reserved
            b = 0x00
            payload += struct.pack("!BHH", b, len(name_bytes), len(value_bytes))
            payload += name_bytes + value_bytes
    return payload

def decode_headers(payload):
    headers = []
    offset = 0
    while offset < len(payload):
        b = payload[offset]
        offset += 1
        if b & 0x80:
            # Indexed
            idx = b & 0x7F
            name = STATIC_TABLE.get(idx, f"unknown-{idx}")
            value_len = struct.unpack("!H", payload[offset:offset+2])[0]
            offset += 2
            value = payload[offset:offset+value_len].decode('utf-8')
            offset += value_len
            headers.append((name, value))
        else:
            # Literal
            name_len = struct.unpack("!H", payload[offset:offset+2])[0]
            offset += 2
            value_len = struct.unpack("!H", payload[offset:offset+2])[0]
            offset += 2
            name = payload[offset:offset+name_len].decode('utf-8')
            offset += name_len
            value = payload[offset:offset+value_len].decode('utf-8')
            offset += value_len
            headers.append((name, value))
    return headers

def build_frame(length, frame_type, flags, stream_id, payload):
    # Fixed Header: Length(2), Type(1), Flags(1), StreamID(4)
    header = struct.pack("!H B B I", length, frame_type, flags, stream_id)
    return header + payload

def recv_exactly(sock, num_bytes):
    data = b""
    while len(data) < num_bytes:
        chunk = sock.recv(num_bytes - len(data))
        if not chunk:
            return None
        data += chunk
    return data

def main():
    parser = argparse.ArgumentParser(description="bcurl - A binary HTTP client")
    parser.add_argument("url", help="URL to request (e.g., localhost:9000/index.html)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print hexdumps of frames")
    args = parser.parse_args()

    try:
        addr_part, path = args.url.split('/', 1)
        path = '/' + path
        host, port_str = addr_part.split(':')
        port = int(port_str)
    except ValueError:
        print("Error: URL must be in format host:port/path (e.g., localhost:9000/index.html)", file=sys.stderr)
        sys.exit(1)

    req_headers = [
        (":method", "GET"),
        (":path", path),
        ("user-agent", "bcurl/1.0"),
        ("accept", "*/*")
    ]
    
    headers_payload = encode_headers(req_headers)
    stream_id = 1
    req_frame = build_frame(len(headers_payload), FRAME_TYPE_HEADERS, 1, stream_id, headers_payload)

    if args.verbose:
        print(f"--> Sending HEADERS Frame ({len(req_frame)} bytes):", file=sys.stderr)
        print(hexdump(req_frame), file=sys.stderr)
        print("", file=sys.stderr)

    status_code = 0

    try:
        with socket.create_connection((host, port), timeout=5) as sock:
            sock.sendall(req_frame)

            while True:
                header_data = recv_exactly(sock, HEADER_SIZE)
                if not header_data:
                    break

                length, frame_type, flags, recv_stream_id = struct.unpack("!H B B I", header_data)
                payload = recv_exactly(sock, length)
                
                frame_bytes = header_data + payload

                if args.verbose:
                    type_str = "HEADERS" if frame_type == 1 else "DATA" if frame_type == 2 else f"UNKNOWN({frame_type})"
                    print(f"<-- Received {type_str} Frame ({len(frame_bytes)} bytes):", file=sys.stderr)
                    print(hexdump(frame_bytes), file=sys.stderr)
                    print("", file=sys.stderr)

                if frame_type == FRAME_TYPE_HEADERS:
                    res_headers = decode_headers(payload)
                    res_dict = dict(res_headers)
                    if ":status" in res_dict:
                        status_code = int(res_dict[":status"])
                elif frame_type == FRAME_TYPE_DATA:
                    sys.stdout.buffer.write(payload)
                    sys.stdout.flush()
                    if flags & 1:  # END_STREAM flag
                        break
                else:
                    # MUST skip cleanly. We read the payload, and we ignore it.
                    pass
                
    except ConnectionRefusedError:
        print("Error: Connection refused. Is the server running?", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    # Exit non-zero on 4xx / 5xx
    if status_code >= 400:
        sys.exit(1)

if __name__ == "__main__":
    main()
