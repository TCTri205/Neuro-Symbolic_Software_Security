# 05b. Kịch Bản Demo Thực Tế (Walkthrough)

Tài liệu này hướng dẫn cách triển khai hệ thống NSSS trên Google Colab và chạy thử nghiệm từ Laptop.

---

## Phần 1: Chuẩn Bị (Trên Google Colab)

Chúng ta sẽ sử dụng Google Colab làm **AI Server** (Backend) vì nó cung cấp GPU miễn phí để chạy mô hình Qwen2.5-Coder đã fine-tune.

1.  Mở Google Colab: [https://colab.research.google.com/](https://colab.research.google.com/)
2.  Tạo Notebook mới.
3.  Chọn **Runtime > Change runtime type > T4 GPU**.
4.  Copy toàn bộ nội dung dưới đây vào Cell đầu tiên và chạy (Shift + Enter):

```bash
# Clone Repository
!git clone https://github.com/your-repo/Neuro-Symbolic_Software_Security.git
%cd Neuro-Symbolic_Software_Security

# Cài đặt môi trường
!chmod +x scripts/setup_colab.sh
!source scripts/setup_colab.sh

# Thiết lập Ngrok (Thay TOKEN của bạn vào đây)
# Lấy token tại: https://dashboard.ngrok.com/get-started/your-authtoken
import os
os.environ["NGROK_AUTHTOKEN"] = "YOUR_NGROK_TOKEN_HERE"

# Chạy Server
!python -m src.server.start_colab
```

**Kết quả:**
Bạn sẽ thấy output tương tự:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
Public URL: https://xyz-123.ngrok-free.app
```
👉 **Copy Public URL này** (ví dụ: `https://xyz-123.ngrok-free.app`).

---

## Phần 2: Chạy Client Kiểm Thử (Trên Laptop)

Trên máy tính cá nhân (hoặc môi trường dev của bạn), bạn sẽ đóng vai trò là Client gửi yêu cầu phân tích code.

1.  Mở Terminal tại thư mục dự án `Neuro-Symbolic_Software_Security`.
2.  Đảm bảo bạn đã cài đặt Python và thư viện requests:
    ```bash
    pip install requests
    ```
3.  Chạy script kiểm thử có sẵn:

    ```bash
    python scripts/test_inference_api.py --url https://xyz-123.ngrok-free.app
    ```
    *(Thay URL bằng Public URL bạn copy từ Colab)*

---

## Phần 3: Kết Quả Mẫu

Nếu hệ thống hoạt động đúng, bạn sẽ nhận được phản hồi JSON chi tiết từ AI Server:

```json
Testing endpoint: https://xyz-123.ngrok-free.app/analyze
Status Code: 200
Time Taken: 2.34s

Response Data:
{
  "status": "success",
  "data": {
    "is_vulnerable": true,
    "confidence_score": 0.95,
    "risk_level": "CRITICAL",
    "reasoning_trace": "The code constructs a SQL query using an f-string...",
    "analysis_summary": "SQL Injection detected due to direct interpolation of user input.",
    "fix_suggestion": "Use parameterized queries. Example: cursor.execute('SELECT * FROM users WHERE id = %s', (uid,))",
    "secure_code_snippet": "def get_user(uid):\n    sql = 'SELECT * FROM users WHERE id = %s'\n    cursor.execute(sql, (uid,))",
    "constraint_check": {
      "syntax_valid": true,
      "logic_sound": true
    }
  },
  "processing_time_ms": 2340.5
}
```

---

## Phần 4: Đánh Giá Hiệu Năng (Tùy Chọn)

Để đo lường hiệu quả của mô hình (FPR, Accuracy), bạn có thể chạy script đánh giá (yêu cầu có model chạy local hoặc kết nối tới server):

```bash
# Nếu chạy local (cần GPU):
python scripts/evaluate_model.py --provider local

# Nếu chạy qua Mock (để test logic):
python scripts/evaluate_model.py --provider mock
```
