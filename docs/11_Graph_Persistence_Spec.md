# 11. Graph Persistence Specification (Architecture)

Tài liệu này định nghĩa cơ chế lưu trữ đồ thị (IR/SSA Graph) xuống đĩa cứng (Disk Persistence). Đây là nền tảng kỹ thuật cho tính năng **Incremental Scanning** (Quét tăng phân) và **Fast Reload**.

## 1. Vấn Đề & Giải Pháp

*   **Vấn đề:** Việc phân tích code (Parsing -> SSA -> CFG) tốn nhiều tài nguyên CPU. Quét lại toàn bộ dự án chỉ vì 1 file thay đổi là lãng phí.
*   **Giải Pháp:** Lưu trạng thái đồ thị đã phân tích xuống Cache. Lần sau chỉ cần load lên và vá (patch) phần thay đổi.

## 2. Format: JSON Lines (.jsonl)

Chúng ta chọn **JSON Lines** vì:
*   **Stream Processing:** Đọc/Ghi tuần tự, không cần load toàn bộ file vào RAM (Tối ưu cho dự án lớn).
*   **Append-only friendly:** Dễ dàng ghi nối tiếp log.
*   **Human Readable:** Dễ debug hơn binary format (Pickle/MsgPack) dù chậm hơn một chút.

### 2.1. Cấu Trúc File Cache

File cache nằm tại: `.nsss/cache/{project_hash}/graph_v1.jsonl`

File bao gồm 2 phần: **Header** (Metadata) và **Body** (Nodes/Edges).

#### Line 1: Header (Metadata)
```json
{"type": "meta", "version": "1.0", "timestamp": 1716300000, "project_root": "/path/to/repo", "commit_hash": "a1b2c3d"}
```

#### Line 2+: Data (Nodes & Edges)
Mỗi dòng là một Node hoặc Edge.

```json
{"type": "node", "id": "Func:main", "kind": "Function", "attrs": {...}}
{"type": "node", "id": "Var:x_1", "kind": "SSA_Var", "attrs": {...}}
{"type": "edge", "src": "Func:main", "dst": "Var:x_1", "kind": "def"}
```

## 3. Chiến Lược Caching (Content-Addressable)

Để đảm bảo tính toàn vẹn (Integrity) và hiệu quả:

1.  **File Hashing:** Mỗi file nguồn (`.py`) được hash (SHA-256).
2.  **Manifest:** Hệ thống duy trì một file `manifest.json` ánh xạ: `filepath -> file_hash -> cache_chunk_id`.
3.  **Invalidation:**
    *   Khi quét, kiểm tra Hash hiện tại của file so với Manifest.
    *   Nếu **Match:** Bỏ qua phân tích file đó, load subgraph từ Cache.
    *   Nếu **Mismatch:** Parse lại file, update subgraph và ghi đè Cache mới.

## 4. Quy Trình Load & Save

### 4.1. Save (Serialization)
1.  Duyệt đồ thị NetworkX trong RAM.
2.  Mở file `.jsonl` mode write (`w`).
3.  Ghi dòng Meta.
4.  Duyệt qua tất cả Nodes -> `json.dump` -> Ghi dòng.
5.  Duyệt qua tất cả Edges -> `json.dump` -> Ghi dòng.

### 4.2. Load (Deserialization)
1.  Mở file `.jsonl`.
2.  Đọc dòng đầu check version.
3.  Đọc từng dòng tiếp theo:
    *   Nếu `type == node`: `graph.add_node(...)`
    *   Nếu `type == edge`: `graph.add_edge(...)`
4.  Rebuild Index (nếu cần).

## 5. Implementation Roadmap
*   **Phase 1:** Implement `JsonlGraphSerializer` class trong `src/core/persistence/`.
*   **Phase 2:** Tích hợp vào Pipeline chính (Check cache trước khi Parse).
*   **Phase 3:** Xử lý Invalidation logic (Xóa node cũ khi file thay đổi).
