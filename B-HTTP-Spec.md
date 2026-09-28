# B-HTTP Protocol Specification
**Version 1.0**

## 1. Introduction
B-HTTP is a lightweight, binary framing protocol for HTTP, inspired by HTTP/2. It uses a fixed-size frame header to exchange headers and data between a client and a server. It features a simplified HPACK-like header compression mechanism to reduce the overhead of repetitive header names.

## 2. Framing Structure
All communication in B-HTTP is performed via frames. Every frame has a fixed 8-byte header, followed by a variable-length payload.

### 2.1 Frame Header (8 bytes)

```
+-----------------------------------------------+
|                 Length (16)                   |
+---------------+---------------+---------------+
|    Type (8)   |   Flags (8)   |
+---------------+---------------+---------------+
|               Stream ID (32)                  |
+-----------------------------------------------+
```

* **Length (16 bits, unsigned)**: The length of the frame payload in bytes. A 16-bit length limits payload size to 64KB per frame, which naturally bounds memory usage and encourages chunking of large files, improving responsiveness and avoiding head-of-line blocking if multiplexing were added later.
* **Type (8 bits)**: The frame type. See Section 3 for defined types.
* **Flags (8 bits)**: Boolean flags specific to the frame type.
  * `0x01` (`END_STREAM`): Signals that this frame is the last one for the stream.
* **Stream ID (32 bits, unsigned)**: The identifier of the stream. B-HTTP uses this to tie requests and responses together.

**Why 8 bytes?**
An 8-byte header is optimal. It maps neatly to modern 64-bit architectures, avoiding padding issues. We chose 16 bits for length (defending memory and encouraging chunking), 8 bits for Type (256 types is plenty), 8 bits for Flags, and 32 bits for Stream ID to accommodate millions of concurrent multiplexed requests in future versions.

### 2.2 Forward Compatibility (The "Must Skip Cleanly" Rule)
A core tenet of B-HTTP: **A receiver meeting a frame type it does not know MUST skip it cleanly.**
Since the header contains the exact payload length, any endpoint receiving an unknown `Type` must read exactly `Length` bytes and discard them without terminating the connection. This guarantees that newer versions (V2) can safely introduce new frame types.

## 3. Frame Types

### 3.1 HEADERS (Type = 1)
Used to transmit HTTP headers.
The payload consists of a sequence of encoded header fields (see Section 4).

### 3.2 DATA (Type = 2)
Used to transmit the HTTP message body (e.g., file contents).
The payload contains the raw bytes of the body. If the `END_STREAM` flag (0x01) is set, no more frames will be sent on this stream.

## 4. Header Compression
B-HTTP implements a binary header encoding format to eliminate string-parsing overhead and reduce bandwidth usage.

### 4.1 The Static Table
B-HTTP defines a static, numbered table of the 10 most commonly used header names:
1. `:method`
2. `:path`
3. `:status`
4. `content-type`
5. `content-length`
6. `server`
7. `connection`
8. `accept`
9. `user-agent`
10. `date`

### 4.2 Header Encoding Format
Headers are encoded as a sequence of fields. A 1-byte prefix determines if the name is indexed (from the table) or literal (a string).

**Indexed Name (Prefix bit 7 is 1)**
```
+---+-------------------+
| 1 |    Index (7)      |
+---+-------------------+
|   Value Length (16)   |
+-----------------------+
|    Value (String)     |
+-----------------------+
```

**Literal Name (Prefix bit 7 is 0)**
```
+---+-------------------+
| 0 |    Reserved (7)   |
+---+-------------------+
|    Name Length (16)   |
+-----------------------+
|   Value Length (16)   |
+-----------------------+
|     Name (String)     |
+-----------------------+
|    Value (String)     |
+-----------------------+
```

Strings are transmitted as raw UTF-8 bytes without null-terminators. Length fields indicate the exact byte count.

---

## 5. Security & Performance Analysis

### 5.1 Security Considerations
- **Memory Exhaustion (DoS)**: The protocol prevents memory-based Denial of Service by using a `uint16` length field. A malicious client cannot force the server to allocate gigabytes of memory for a single frame, as the maximum allocation is capped at 65,535 bytes.
- **Buffer Overflow Prevention**: By using Python's `struct` module and explicit length-based reading (`recv_exactly`), the implementation avoids common C-style buffer overflow vulnerabilities.
- **Path Traversal**: The server uses `os.path.normpath` and `lstrip('/')` to prevent "Directory Traversal" attacks (e.g., requesting `../../etc/passwd`).

### 5.2 Performance Analysis
- **Bandwidth Efficiency**: By using a static table for headers, a typical request for a page is reduced from ~200 bytes of text to ~40 bytes of binary data.
- **Computational Overhead**: Binary parsing via `struct` is significantly faster than string splitting and regex parsing required by HTTP/1.1, reducing CPU cycles per request.
- **Latency**: The use of binary framing allows for future implementation of multiplexing, which would eliminate Head-of-Line (HoL) blocking.

Below is an annotated hexdump of a complete request and response, including an unknown frame type (Type 99) sent by the server to prove the client gracefully skips it.

## 1. Request: HEADERS Frame
The client requests `GET /index.html`.

```
00 26                  # Frame Length: 38 bytes (payload)
01                     # Frame Type: 1 (HEADERS)
01                     # Flags: 1 (END_STREAM flag set)
00 00 00 01            # Stream ID: 1
81                     # Header 1: Indexed Name (1 = :method)
00 03                  # Value Length: 3 bytes
47 45 54               # Value: "GET"
82                     # Header 2: Indexed Name (2 = :path)
00 0b                  # Value Length: 11 bytes
2f 69 6e 64 65 78 2e 68 74 6d 6c # Value: "/index.html"
89                     # Header 3: Indexed Name (9 = user-agent)
00 09                  # Value Length: 9 bytes
62 63 75 72 6c 2f 31 2e 30       # Value: "bcurl/1.0"
88                     # Header 4: Indexed Name (8 = accept)
00 03                  # Value Length: 3 bytes
2a 2f 2a               # Value: "*/*"
```

## 2. Response: HEADERS Frame
The server responds with a 200 OK, standard headers, and one literal custom header.

```
00 45                  # Frame Length: 69 bytes
01                     # Frame Type: 1 (HEADERS)
00                     # Flags: 0 (No END_STREAM yet)
00 00 00 01            # Stream ID: 1
83                     # Header 1: Indexed Name (3 = :status)
00 03                  # Value Length: 3 bytes
32 30 30               # Value: "200"
84                     # Header 2: Indexed Name (4 = content-type)
00 09                  # Value Length: 9 bytes
74 65 78 74 2f 68 74 6d 6c # Value: "text/html"
85                     # Header 3: Indexed Name (5 = content-length)
00 02                  # Value Length: 2 bytes
32 32                  # Value: "22"
86                     # Header 4: Indexed Name (6 = server)
00 0a                  # Value Length: 10 bytes
62 73 65 72 76 65 2f 31 2e 30 # Value: "bserve/1.0"
00                     # Header 5: Literal Name (MSB = 0)
00 0d                  # Name Length: 13 bytes
00 0f                  # Value Length: 15 bytes
63 75 73 74 6f 6d 2d 68 65 61 64 65 72 # Name: "custom-header"
6c 69 74 65 72 61 6c 2d 65 78 61 6d 70 6c 65 # Value: "literal-example"
```

## 3. Response: UNKNOWN Frame (Demonstrating the Skip Cleanly rule)
The server injects a Type 99 frame. The client parses the header, reads 11 bytes of payload, and cleanly ignores them.

```
00 0b                  # Frame Length: 11 bytes
63                     # Frame Type: 99 (UNKNOWN)
00                     # Flags: 0
00 00 00 01            # Stream ID: 1
69 67 6e 6f 72 65 20 74 68 69 73 # Payload: "ignore this"
```

## 4. Response: DATA Frame
The server sends the body (HTML) and closes the stream.

```
00 16                  # Frame Length: 22 bytes
02                     # Frame Type: 2 (DATA)
01                     # Flags: 1 (END_STREAM flag set)
00 00 00 01            # Stream ID: 1
3c 68 31 3e 48 65 6c 6c 6f 20 57 6f 72 6c 64 21 3c 2f 68 31 3e 0a # Payload: "<h1>Hello World!</h1>\n"
```
