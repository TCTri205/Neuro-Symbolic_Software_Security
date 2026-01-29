# 05b. Kịch Bản Demo Thực Tế (Walkthrough)

Tài liệu này hướng dẫn cách triển khai hệ thống NSSS trên Google Colab và chạy thử nghiệm từ Laptop.

---

## Phần 1: Chuẩn Bị (Trên Google Colab)

Chúng ta sẽ sử dụng Google Colab làm **AI Server** (Backend) vì nó cung cấp GPU miễn phí để chạy mô hình Qwen2.5-Coder đã fine-tune.

### Lựa Chọn A: Quick Start (Khuyến Nghị cho Beginner)

**Sử dụng Notebook mẫu có sẵn:**

1.  Mở notebook template: **[NSSS_Colab_Simple.ipynb](https://github.com/Hieureal1305/Neuro-Symbolic_Software_Security/blob/main/notebooks/NSSS_Colab_Simple.ipynb)**
2.  Click **"Open in Colab"** (nút ở đầu notebook)
3.  Chọn **Runtime > Change runtime type > T4 GPU**
4.  Thay `YOUR_NGROK_TOKEN_HERE` bằng token của bạn (lấy tại [Ngrok Dashboard](https://dashboard.ngrok.com/get-started/your-authtoken))
5.  Nhấn **Shift + Enter** để chạy cell
6.  Đợi ~5 phút (lần đầu tiên) để cài đặt
7.  Copy **Public URL** hiển thị cuối cùng

**Ưu điểm:** Tự động hóa hoàn toàn, chỉ cần 1 cell, phù hợp cho demo nhanh.

---

### Lựa Chọn B: Advanced Setup (Cho Power User)

**Sử dụng Notebook nâng cao với nhiều tùy chọn:**

1.  Mở notebook nâng cao: **[NSSS_Colab_Runner.ipynb](https://github.com/Hieureal1305/Neuro-Symbolic_Software_Security/blob/main/notebooks/NSSS_Colab_Runner.ipynb)**
2.  Notebook này cung cấp:
    *   Hybrid Sync (Code trên Drive, chạy trên Colab VM)
    *   Model Persistence (không cần download lại mỗi lần)
    *   Static Domain support
    *   Configurable settings

**Ưu điểm:** Tối ưu cho sử dụng dài hạn, persistent model, tùy chỉnh cao.

---

### Lựa Chọn C: Manual Setup (Cho Developer)

Nếu bạn muốn cài đặt thủ công hoặc tùy chỉnh chi tiết:

1.  Mở Google Colab: [https://colab.research.google.com/](https://colab.research.google.com/)
2.  Tạo Notebook mới.
3.  Chọn **Runtime > Change runtime type > T4 GPU**.
4.  Copy toàn bộ nội dung dưới đây vào Cell đầu tiên và chạy (Shift + Enter):

```bash
# Clone Repository
!git clone https://github.com/Hieureal1305/Neuro-Symbolic_Software_Security.git
%cd Neuro-Symbolic_Software_Security

# Cài đặt môi trường
!chmod +x scripts/setup_colab.sh
!bash scripts/setup_colab.sh

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

---

## Phần 5: So Sánh Các Notebook Template

| Feature | NSSS_Colab_Simple | NSSS_Colab_Runner | Manual Setup |
|---------|-------------------|-------------------|--------------|
| **Độ Phức Tạp** | ⭐ Đơn giản nhất | ⭐⭐⭐ Nâng cao | ⭐⭐ Trung bình |
| **Setup Time** | ~5 phút (lần đầu) | ~10 phút (lần đầu) | ~5 phút |
| **Cells** | 1 cell chính | 4 cells tùy chỉnh | Manual copy-paste |
| **Auto Setup** | ✅ Hoàn toàn tự động | ✅ Tự động + Options | ⚠️ Thủ công |
| **Model Persistence** | ❌ | ✅ Lưu trên Drive | ❌ |
| **Static Domain** | ❌ | ✅ | ❌ |
| **Ideal For** | Demo, Testing | Long-term usage | Customization |

**Khuyến Nghị:**
- **Lần đầu sử dụng:** Chọn `NSSS_Colab_Simple.ipynb`
- **Sử dụng thường xuyên:** Chọn `NSSS_Colab_Runner.ipynb` (tiết kiệm thời gian do model được cache)
- **Cần tùy chỉnh:** Manual Setup
