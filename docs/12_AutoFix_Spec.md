# 12. Auto-fix Suggestion Specification

Tài liệu này định nghĩa cơ chế gợi ý sửa lỗi tự động (Auto-fix) dựa trên GenAI, cách tích hợp vào luồng phân tích và định dạng đầu ra trong báo cáo SARIF.

## 1. Tổng Quan

*   **Mục tiêu:** Cung cấp code an toàn thay thế cho đoạn code bị đánh dấu là lỗ hổng.
*   **Nguyên tắc:** "Human-in-the-loop". Auto-fix chỉ là gợi ý, developer phải review trước khi apply.
*   **Đầu vào:**
    *   Vulnerable Code Snippet.
    *   Vulnerability Type (e.g., SQL Injection).
    *   Surrounding Context (các dòng code lân cận).
*   **Đầu ra:**
    *   `fix_suggestion`: Text giải thích.
    *   `secure_code_snippet`: Code đã fix.
    *   `diff`: (Optional) Định dạng diff để apply patch.

## 2. Kiến Trúc Tích Hợp

Module Auto-fix nằm trong `src/core/ai/`, được kích hoạt trong giai đoạn **Verification (Stage 4)**.

### 2.1. Prompt Engineering
Khi gửi request lên AI Server (Colab), prompt cần yêu cầu thêm phần fix.

```json
// Request
{
  "task": "verify_and_fix",
  "code": "cursor.execute(f'SELECT * FROM users WHERE id = {uid}')",
  "vuln_type": "SQL Injection"
}
```

```json
// Response Schema
{
  "is_vulnerable": true,
  "fix": {
    "description": "Sử dụng Parameterized Query để ngăn chặn injection.",
    "code": "cursor.execute('SELECT * FROM users WHERE id = %s', (uid,))"
  }
}
```

## 3. SARIF Mapping

Chuẩn SARIF hỗ trợ hiển thị fix thông qua property `fixes`.

```json
"results": [
  {
    "ruleId": "PYTHON-SQLI-001",
    "message": { "text": "SQL Injection detected." },
    "locations": [...],
    "fixes": [
      {
        "description": { "text": "Replace with parameterized query." },
        "artifactChanges": [
          {
            "artifactLocation": { "uri": "src/db.py" },
            "replacements": [
              {
                "deletedRegion": {
                  "startLine": 10,
                  "startColumn": 4,
                  "endColumn": 60
                },
                "insertedContent": {
                  "text": "cursor.execute('SELECT * FROM users WHERE id = %s', (uid,))"
                }
              }
            ]
          }
        ]
      }
    ]
  }
]
```

## 4. Yêu Cầu Implementation

1.  **AI Client Update (`src/core/ai/client.py`):**
    *   Update `AnalyzeResponse` Pydantic model để chứa trường `fix_suggestion` và `secure_code`.
2.  **Prompt Template (`src/core/ai/prompts.py`):**
    *   Thêm instruction cho model: "If vulnerable, provide a secure version of the code respecting original indentation."
3.  **Report Renderer (`src/report/sarif.py`):**
    *   Map kết quả từ AI sang đối tượng `fixes` của SARIF.
    *   Tính toán `deletedRegion` dựa trên location của lỗ hổng.

## 5. Rủi Ro & Giới Hạn

*   **Hallucination:** Model có thể sinh ra code sai cú pháp hoặc sai logic nghiệp vụ.
*   **Context Limit:** Nếu lỗ hổng phụ thuộc vào biến ở file khác, model có thể thiếu context để fix đúng.
*   **Mitigation:** Luôn gắn nhãn `confidence` và khuyến cáo user review thủ công.
