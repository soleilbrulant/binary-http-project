# Annotated Hexdump Analysis: B-HTTP v1

This document provides a step-by-step breakdown of a single request and response cycle between `bcurl` and `bserve`.

## 1. The Request Frame
**Request:** `python3 bcurl.py localhost:9000/index.html`

### Raw Bytes (Hex):
`01 01 00 00 00 0d 00 00 00 0b 2f 69 6e 64 65 78 2e 68 74 6d 6c`

### Breakdown:
| Hex Bytes | Field | Value | Interpretation |
| :--- | :--- | :--- | :--- |
| `01` | Version | 1 | B-HTTP v1 |
| `01` | Type | 1 | Request Frame |
| `00 00 00 0d` | Length | 13 | The payload is 13 bytes long |
| `00 00` | Reserved | 0 | Padding |
| `00 0b` | Path Len | 11 | The path string is 11 characters |
| `2f 69 6e 64 65 78 2e 68 74 6d 6c` | Path | `/index.html` | The requested resource |

---

## 2. The Response Frame
**Response:** Server finds the file and returns Status 200.

### Raw Bytes (Hex):
`01 02 00 00 00 2d 00 00 00 c8 00 1b 43 6f 6e 74 65 6e 74 2d 54 79 70 65 3a 20 74 65 78 74 2f 68 74 6d 6c 3c 68 31 3e 57 65 6c 63 6f 6d 65 3c 2f 68 31 3e`

### Breakdown:
| Hex Bytes | Field | Value | Interpretation |
| :--- | :--- | :--- | :--- |
| `01` | Version | 1 | B-HTTP v1 |
| `02` | Type | 2 | Response Frame |
| `00 00 00 2d` | Length | 45 | The payload is 45 bytes long |
| `00 00` | Reserved | 0 | Padding |
| `00 c8` | Status | 200 | OK (Success) |
| `00 1b` | Header Len | 27 | Headers section is 27 bytes |
| `43 6f ... 6c` | Headers | `Content-Type: text/html` | Metadata about the response |
| `3c 68 31 3e...` | Body | `<h1>Welcome</h1>` | The actual content of index.html |
