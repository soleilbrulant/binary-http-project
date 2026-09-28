# B-HTTP Binary Protocol Project

A lightweight, binary framing protocol for HTTP, inspired by HTTP/2. This project replaces traditional text-based HTTP headers with a binary framing system to improve efficiency, memory safety, and forward compatibility.

## 🚀 Features

- **Fixed-Size Binary Framing**: Uses an 8-byte frame header to bound memory usage and prevent head-of-line blocking.
- **HPACK-lite Header Compression**: Implements a static table for the 10 most common HTTP headers, reducing overhead via a single-byte index.
- **Forward Compatibility**: Implements a "Must Skip Cleanly" rule, allowing clients to ignore unknown frame types without terminating the connection.
- **Memory Defense**: Payload lengths are capped at 16-bits (64KB), encouraging efficient chunking of large files.
- **Robust Client/Server**: Includes a complete server (`bserve.py`) and a verbose client (`bcurl.py`) for testing and verification.

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.x

### Project Structure
```text
.
├── B-HTTP-Spec.md      # Full Protocol Specification & Hexdumps
├── bserve.py          # B-HTTP Server
├── bcurl.py           # B-HTTP Client
└── www/               # Root directory for served files
    └── index.html     # Sample home page
```

## 📖 How to Run

### 1. Start the Server
Run the server by specifying the root web directory and the port:
```bash
python3 bserve.py ./www 9000
```

### 2. Run the Client
Request a page from the server. Use the `-v` flag to see the binary frames and hexdumps in real-time:
```bash
python3 bcurl.py -v localhost:9000/index.html
```

## 🧪 Testing the Requirements

| Requirement | How to Verify |
| :--- | :--- |
| **Binary Framing** | Run `bcurl -v`. Observe the `Length`, `Type`, and `Stream ID` in the hexdump. |
| **Header Compression** | Check the `HEADERS` frame in verbose mode; common headers like `:method` are encoded as single bytes. |
| **Forward Compatibility** | The server sends a `Type 99` (UNKNOWN) frame; observe the client skipping it cleanly in the logs. |
| **Error Handling** | Request a non-existent file: `python3 bcurl.py localhost:9000/none.html`. Observe the `404` status and non-zero exit code. |
| **File Chunking** | The server automatically chunks files larger than 64KB into multiple `DATA` frames. |

## 📄 Specification
For a deep dive into the frame layout, the static header table, and annotated hexdumps of the communication flow, please refer to [B-HTTP-Spec.md](./B-HTTP-Spec.md).
