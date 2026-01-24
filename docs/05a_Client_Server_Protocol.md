# 05a. Giao Thức Client-Server (Protocol Specification)

Tài liệu này định nghĩa chuẩn giao tiếp JSON giữa **Laptop Client** (Scanner) và **Colab Server** (AI Worker).

---

## 1. Kết Nối & Endpoint

*   **Base URL:** Địa chỉ public do Ngrok cung cấp (Ví dụ: `https://a1b2-34-56-78-90.ngrok-free.app`). *Lưu ý: URL này thay đổi mỗi lần khởi động lại Colab.*
*   **Endpoint chính:** `POST /analyze`
*   **Authentication:** `X-API-Key` header (Simple Secret để tránh người lạ dùng ké GPU).
*   **Content-Type:** `application/json`

---

## 2. Cấu Trúc Request (Laptop -> Colab)

Laptop chịu trách nhiệm "sơ chế" dữ liệu. Thay vì gửi cả file code, Laptop chỉ gửi ngữ cảnh cần thiết.

```json
{
  "function_signature": "def USER_FUNC_1(USER_STR_1):\n    query = f'SELECT * FROM users WHERE name = {USER_STR_1}'\n    cursor.execute(query)",
  "language": "python",
  "vulnerability_type": "SQL Injection",
  "context": {
    "source_variable": "USER_STR_1",
    "sink_function": "cursor.execute",
    "line_number": 15,
    "file_path": "auth/login.py",
    "sanitizers_found": ["html.escape"] 
  },
  "privacy_mask": {
    "enabled": true,
    "map": {
      "USER_FUNC_1": "get_user_by_name",
      "USER_STR_1": "username_input"
    }
  },
  "metadata": {
    "mode": "precision",
    "request_id": "req_123456789"
  }
}
```

### Giải thích trường dữ liệu:
*   `function_signature`: Đoạn code (snippet) đã được **trích xuất**, **làm sạch** và **mã hóa theo kiểu (Typed-Masking)**. Ví dụ: biến chuỗi từ người dùng -> `USER_STR_n`.
*   `sanitizers_found`: Danh sách các hàm làm sạch phát hiện được trên đường đi (giúp AI đánh giá ngữ cảnh).
*   `privacy_mask`: Thông tin để Client tự giải mã khi nhận kết quả. Server nhận diện logic qua các Typed placeholders.

---

## 3. Cấu Trúc Response (Colab -> Laptop)

Colab trả về kết quả phân tích dưới dạng cấu trúc.

```json
{
  "status": "success",
  "data": {
    "is_vulnerable": true,
    "confidence_score": 0.95,
    "risk_level": "CRITICAL",
    "reasoning_trace": "1. Input USER_STR_1 is directly concatenated into SQL. 2. html.escape only targets HTML tags, not SQL metacharacters. 3. Resulting query is vulnerable to SQLi.",
    "analysis_summary": "Biến đầu vào USER_STR_1 được nối chuỗi trực tiếp vào câu lệnh SQL. Hàm 'html.escape' không ngăn chặn được SQL Injection.",
    "fix_suggestion": "Sử dụng Parameterized Query.",
    "secure_code_snippet": "query = 'SELECT * FROM users WHERE name = ?'\ncursor.execute(query, (USER_STR_1,))",
    "constraint_check": {
        "syntax_valid": true,
        "logic_sound": true
    }
  },
  "processing_time_ms": 1250
}
```

### Giải thích trường dữ liệu:
*   `is_vulnerable`: Phán quyết cuối cùng của AI.
*   `reasoning_trace`: Chuỗi suy luận (Chain-of-Thought) trích xuất từ thẻ `<thinking>` của model.
*   `analysis_summary`: Giải thích tóm tắt lý do.
*   `secure_code_snippet`: Code vá lỗi (vẫn dùng tên biến mã hóa). Client sẽ thay lại tên thật trước khi hiện cho User.
*   `constraint_check`: Kết quả kiểm tra cú pháp của code fix (đảm bảo AI không sinh code lỗi).

---

## 4. Xử Lý Lỗi (Error Handling)

Nếu có lỗi xảy ra (Colab sập, code quá dài, lỗi server), API sẽ trả về HTTP 4xx hoặc 5xx kèm JSON:

```json
{
  "status": "error",
  "error_code": "CONTEXT_TOO_LONG",
  "message": "Function signature exceeds 4096 tokens limit."
}
```

## 5. Hướng Dẫn Implement Nhanh

*   **Tại Laptop (Python Requests):**
    ```python
    import requests
    headers = {"X-API-Key": "my_secret_key"}
    payload = { ... } # JSON Request
    try:
        response = requests.post(NGROK_URL + "/analyze", json=payload, headers=headers, timeout=30)
        result = response.json()
    except requests.exceptions.Timeout:
        print("AI Server quá tải hoặc mạng yếu.")
    ```

*   **Tại Colab (FastAPI):**
    ```python
    from fastapi import FastAPI, Header, HTTPException
    from pydantic import BaseModel

    app = FastAPI()

    @app.post("/analyze")
    async def analyze_code(req: AnalysisRequest, x_api_key: str = Header(None)):
        if x_api_key != "my_secret_key":
            raise HTTPException(status_code=401, detail="Unauthorized")
        # Gọi AI model để xử lý
        return {"status": "success", ...}
    ```
