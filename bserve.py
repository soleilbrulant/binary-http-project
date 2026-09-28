import socket
import struct
import os
import sys

# --- PROTOCOL CONSTANTS ---
FRAME_TYPE_HEADERS = 1
FRAME_TYPE_DATA = 2
FRAME_TYPE_UNKNOWN = 99  # Example for testing ignore

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

def encode_headers(headers):
    """
    Encode headers using HPACK-lite.
    """
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

def handle_client(conn, addr, root_dir):
    try:
        while True:
            # Read Frame Header
            header_data = recv_exactly(conn, HEADER_SIZE)
            if not header_data:
                break

            try:
                length, frame_type, flags, stream_id = struct.unpack("!H B B I", header_data)
                payload = recv_exactly(conn, length)
                if payload is None:
                    print("[!] Connection closed while reading payload.")
                    break
            except struct.error:
                print("[!] Malformed frame header received. Closing connection.")
                break

            if frame_type == FRAME_TYPE_HEADERS:
                # Decode headers
                req_headers = decode_headers(payload)
                req_dict = dict(req_headers)
                
                method = req_dict.get(":method", "GET")
                path = req_dict.get(":path", "/")
                
                print(f"[*] {method} {path}")
                
                # Resolve file
                safe_path = os.path.normpath(path).lstrip('/')
                if safe_path == "":
                    safe_path = "index.html"
                full_path = os.path.join(root_dir, safe_path)
                
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    with open(full_path, "rb") as f:
                        content = f.read()
                    
                    res_headers = [
                        (":status", "200"),
                        ("content-type", "text/html"),
                        ("content-length", str(len(content))),
                        ("server", "bserve/1.0"),
                        ("custom-header", "literal-example")
                    ]
                    
                    # Send Headers frame
                    headers_payload = encode_headers(res_headers)
                    conn.sendall(build_frame(len(headers_payload), FRAME_TYPE_HEADERS, 0, stream_id, headers_payload))
                    
                    # Send Unknown frame to prove client skips it cleanly
                    dummy_payload = b"ignore this"
                    conn.sendall(build_frame(len(dummy_payload), FRAME_TYPE_UNKNOWN, 0, stream_id, dummy_payload))
                    
                    # Send Data frame
                    # We could chunk it, but we'll send it in chunks up to 64KB (since length is uint16)
                    offset = 0
                    while offset < len(content):
                        chunk = content[offset:offset+65535]
                        # Flag 1 means END_STREAM if it's the last chunk
                        f = 1 if (offset + len(chunk) == len(content)) else 0
                        conn.sendall(build_frame(len(chunk), FRAME_TYPE_DATA, f, stream_id, chunk))
                        offset += len(chunk)
                else:
                    res_headers = [
                        (":status", "404"),
                        ("content-length", "14")
                    ]
                    headers_payload = encode_headers(res_headers)
                    conn.sendall(build_frame(len(headers_payload), FRAME_TYPE_HEADERS, 0, stream_id, headers_payload))
                    
                    err_msg = b"File Not Found"
                    conn.sendall(build_frame(len(err_msg), FRAME_TYPE_DATA, 1, stream_id, err_msg))

            elif frame_type == FRAME_TYPE_DATA:
                print(f"[*] Received DATA frame ({length} bytes)")
            else:
                # MUST skip cleanly
                print(f"[*] Unknown frame type {frame_type}, skipping {length} bytes cleanly.")
                
    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        conn.close()

def main():
    if len(sys.argv) < 3:
        # Default for running without args during testing
        print("Usage: ./bserve <root_dir> <port>")
        sys.argv = ["bserve.py", "./www", "9000"]
        
    root_dir = sys.argv[1]
    port = int(sys.argv[2])
    
    if not os.path.exists(root_dir):
        os.makedirs(root_dir)
        with open(os.path.join(root_dir, "index.html"), "w") as f:
            f.write("<h1>Welcome to B-HTTP Server!</h1><p>It works!</p>")
            
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(5)
    print(f"[*] bserve listening on port {port} (Root: {root_dir})")
    
    try:
        while True:
            conn, addr = server.accept()
            handle_client(conn, addr, root_dir)
    except KeyboardInterrupt:
        pass
    finally:
        server.close()

if __name__ == "__main__":
    main()
