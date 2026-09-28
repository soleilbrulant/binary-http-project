# Specification: B-HTTP v1 (Binary HTTP)

## 1. Introduction
B-HTTP v1 is a minimalist, binary-encoded request-response protocol designed to serve files over TCP. Unlike text-based HTTP/1.1, B-HTTP uses fixed-size headers and length-prefixed fields to ensure efficient parsing and the ability to skip unknown frame types.

## 2. Frame Structure
All communication occurs via "Frames." Every frame consists of a **Fixed-Size Header** followed by an optional **Payload**.

### 2.1 The Fixed-Size Header (8 Bytes)
Every frame must start with these 8 bytes:

| Offset | Field | Size | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| 0 | Version | 1 Byte | uint8 | Protocol version (v1 = `0x01`). |
| 1 | Frame Type | 1 Byte | uint8 | `0x01`: Request, `0x02`: Response, `0x03`: Error. |
| 2-5 | Payload Length | 4 Bytes | uint32 (BE) | Total size of the payload in bytes. |
| 6-7 | Reserved | 2 Bytes | - | Set to `0x00`. Used for future alignment. |

**The "Must Skip" Rule:** If a receiver encounters a `Frame Type` it does not recognize, it must read the `Payload Length` ($N$) and skip exactly $N$ bytes in the stream to reach the next frame.

---

## 3. Frame Types

### 3.1 Request Frame (Type `0x01`)
Used by the client to request a resource.

**Payload Layout:**
1. **Path Length** (2 bytes, uint16 BE): Length of the URI path.
2. **Path** (Variable, UTF-8): The resource path (e.g., `/index.html`).

### 3.2 Response Frame (Type `0x02`)
Used by the server to return a resource or an error.

**Payload Layout:**
1. **Status Code** (2 bytes, uint16 BE): e.g., `200` (OK), `400` (Bad Request), `404` (Not Found).
2. **Header Length** (2 bytes, uint16 BE): Length of the metadata section.
3. **Headers** (Variable, UTF-8): Key-value metadata (e.g., `Content-Type: text/html`).
4. **Body** (Variable, Binary): The raw bytes of the requested file.

---

## 4. Error Handling
- **400 Bad Request:** Returned if the version is incorrect or the frame is malformed.
- **404 Not Found:** Returned if the requested path does not exist on the server.
- **Connection:** The TCP connection remains open after a response to allow for persistent requests.
