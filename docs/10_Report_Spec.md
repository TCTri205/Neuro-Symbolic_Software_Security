# 10. Reporting Standard & SARIF Spec

Tài liệu này quy định định dạng đầu ra (Output Format) của hệ thống NSSS. Chúng ta sử dụng **SARIF v2.1.0** làm chuẩn chính để đảm bảo khả năng tích hợp với các công cụ hiện đại (GitHub Security, VS Code, SonarQube).

## 1. Các Loại Báo Cáo

Hệ thống sinh ra 2 loại file báo cáo sau mỗi lần quét:

1.  **`nsss_report.sarif`** (Chính): Chuẩn công nghiệp. Dùng để hiển thị lỗi, tích hợp CI/CD.
2.  **`nsss_debug.json`** (Phụ): Format nội bộ chi tiết. Dùng để debug, chứa raw data từ SSA và LLM reasoning trace.
3.  **`nsss_graph.json`** (Visualization): Format đồ thị taint path. Xem chi tiết tại [14_Graph_Visualization_Spec.md](./14_Graph_Visualization_Spec.md).

## 2. Cấu Trúc SARIF Mapping

Logic mapping từ kết quả phân tích sang SARIF object (tham chiếu `src/report/sarif.py`).

### 2.1. Verdict & Levels
Kết luận của AI (Verdict) sẽ quyết định mức độ nghiêm trọng (Level) trong SARIF.

| AI Verdict | SARIF Level | Ý nghĩa hiển thị |
| :--- | :--- | :--- |
| **True Positive** | `error` | **Lỗi đỏ**. Cần fix gấp. Chặn Merge PR. |
| **Unverified** | `warning` | **Cảnh báo vàng**. AI không chắc chắn hoặc chưa chạy verify. Cần người review. |
| **False Positive** | `note` | **Thông báo xanh/xám**. Đã được AI kiểm tra và đánh dấu là an toàn (nhưng vẫn log để audit). |

### 2.2. Result Mapping

Mỗi lỗ hổng (`finding`) được map thành một `result` trong danh sách `runs[0].results`.

```json
{
  "ruleId": "PYTHON-SQL-INJECTION-001",  // Mapping từ check_id (Semgrep Rule ID)
  "level": "error",                      // Mapping từ Verdict
  "message": {
    "text": "True Positive: Input 'user_input' nối trực tiếp vào SQL Query.\n\nRemediation:\nSử dụng Parameterized Query."
  },
  "locations": [
    {
      "physicalLocation": {
        "artifactLocation": { "uri": "src/auth/login.py" },
        "region": {
          "startLine": 15,
          "startColumn": 4
        }
      }
    }
  ],
  "properties": {
    "verdict": "true positive",
    "confidence": 0.95,
    "ai_reasoning": "Model detected variable usage in f-string..."
  }
}
```

## 3. Lifecycle của một Issue

1.  **Discovery (Stage 1-3):** Semgrep tìm thấy pattern tiềm năng. Trạng thái mặc định là `Unverified`.
2.  **Verification (Stage 4):**
    *   Gửi context lên AI Server.
    *   AI trả về: `is_vulnerable: true/false`.
3.  **Finalization (Reporting):**
    *   Nếu `true` -> Update level thành `error`.
    *   Nếu `false` -> Update level thành `note` (hoặc `none` tùy cấu hình filter).
    *   Nếu lỗi kết nối/timeout -> Giữ nguyên `warning` (Fail-open để an toàn).

## 4. Tích Hợp GitHub Actions

File SARIF này có thể được upload trực tiếp lên GitHub Security Tab thông qua action `github/codeql-action/upload-sarif`.

```yaml
- name: Upload SARIF file
  uses: github/codeql-action/upload-sarif@v2
  with:
    sarif_file: reports/nsss_report.sarif
```
