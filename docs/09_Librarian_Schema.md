# 09. Librarian Schema Specification

Tài liệu này định nghĩa cấu trúc dữ liệu (Data Model) cho module **The Librarian**. Đây là chuẩn "Single Source of Truth" để mô tả hành vi bảo mật của các thư viện bên thứ 3 (Third-party libraries).

## 1. Mục Tiêu
*   **Chuẩn hóa:** Đảm bảo tính nhất quán khi lưu trữ Profile thư viện (trong DB hoặc File).
*   **Automation:** Giúp AI (LLM) hiểu định dạng cần sinh ra khi gặp thư viện mới.
*   **Interoperability:** Dễ dàng chia sẻ Knowledge Base giữa các team/dự án.

## 2. Core Models (Pydantic Mapping)

Schema này phản ánh trực tiếp cấu trúc code tại `src/librarian/models.py`.

### 2.1. SecurityLabel (Enum)
Phân loại vai trò bảo mật của một hàm/biến.

| Label | Ý nghĩa | Ví dụ |
| :--- | :--- | :--- |
| `source` | Điểm nhập dữ liệu không tin cậy (Untrusted Input). | `flask.request.args`, `input()` |
| `sink` | Điểm thực thi nhạy cảm (Sensitive Execution). | `os.system()`, `cursor.execute()` |
| `sanitizer` | Hàm làm sạch dữ liệu (Data Cleaning). | `html.escape()`, `shlex.quote()` |
| `none` | Hàm trung tính, không ảnh hưởng bảo mật. | `math.sqrt()`, `str.upper()` |

### 2.2. ParameterSpec
Mô tả tham số của hàm.

```json
{
  "name": "string (Tên tham số)",
  "index": "int (Vị trí, -1 nếu keyword-only)",
  "tags": ["list", "of", "strings"],
  "description": "string (Optional)"
}
```

*   **Tags quan trọng:** `taint_propagator` (truyền bẩn), `sensitive` (dữ liệu mật).

### 2.3. FunctionSpec
Mô tả hành vi bảo mật của một hàm cụ thể.

```json
{
  "name": "string (Fully Qualified Name)",
  "label": "SecurityLabel (source|sink|sanitizer|none)",
  "parameters": ["List[ParameterSpec]"],
  "returns_tainted": "bool (True nếu kết quả trả về bị bẩn)",
  "description": "string",
  "cwe_id": "string (Ví dụ: CWE-78)"
}
```

### 2.4. LibraryVersion & Library
Cấu trúc cấp cao nhất quản lý thư viện.

```json
{
  "name": "requests",
  "ecosystem": "pypi",
  "versions": [
    {
      "version": "2.26.0",
      "functions": [ ...FunctionSpec objects... ],
      "release_date": "2021-10-01",
      "deprecated": false
    }
  ]
}
```

## 3. JSON Example (Thực Tế)

Dưới đây là ví dụ profile cho thư viện chuẩn `subprocess` (chứa Sink) và `flask` (chứa Source).

```json
{
  "name": "subprocess",
  "ecosystem": "python-stdlib",
  "versions": [
    {
      "version": "3.10",
      "functions": [
        {
          "name": "subprocess.call",
          "label": "sink",
          "cwe_id": "CWE-78",
          "description": "Executes shell commands.",
          "parameters": [
            {
              "name": "args",
              "index": 0,
              "tags": ["command_execution"]
            },
            {
              "name": "shell",
              "index": -1,
              "tags": ["configuration"]
            }
          ],
          "returns_tainted": false
        }
      ]
    }
  ]
}
```

## 4. Quy Trình AI Fallback

Khi hệ thống gặp một thư viện lạ không có trong Database:

1.  **Trigger:** `Librarian` không tìm thấy package trong Local DB.
2.  **Action:** Gửi request lên LLM với prompt yêu cầu sinh JSON theo Schema này.
3.  **Validation:** Parse kết quả JSON bằng Pydantic `Library` model.
    *   Nếu lỗi format -> Retry.
    *   Nếu thành công -> Lưu vào Temporary Cache và sử dụng ngay.
