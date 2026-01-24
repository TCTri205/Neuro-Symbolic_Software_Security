# 05b. Kịch Bản Demo Thực Tế (Walkthrough)

Tài liệu này cung cấp mã nguồn đầy đủ để bạn chạy thử nghiệm hệ thống **ngay lập tức**.
Bạn cần chuẩn bị: 1 Laptop (có Python) và 1 Tài khoản Google (để dùng Colab).

---

## Phần 1: Chuẩn Bị File Mục Tiêu (Trên Laptop)

Tạo một file tên là `vulnerable_app.py`. Đây là file "nạn nhân" mà chúng ta sẽ quét để tìm lỗi.

```python
# vulnerable_app.py
import sqlite3
import os

# LỖI 1: Hardcoded Secret (Lộ API Key)
AWS_SECRET_KEY = "AKIA1234567890SECRETKEY"

def get_user_info(username):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # LỖI 2: SQL Injection (Nối chuỗi trực tiếp)
    # Kẻ tấn công có thể nhập: admin' OR '1'='1
    query = f"SELECT * FROM users WHERE username = '{username}'"
    
    print(f"Executing query: {query}")
    cursor.execute(query) # <--- SINK POINT
    return cursor.fetchall()

if __name__ == "__main__":
    user_input = input("Nhập username: ")
    get_user_info(user_input)
```

---

## Phần 2: Thiết Lập AI Server (Trên Google Colab)

Mở Google Colab (https://colab.research.google.com/), tạo Notebook mới, chọn **Runtime > Change runtime type > T4 GPU**.
Copy đoạn code sau vào Cell đầu tiên và chạy (Play):

```python
# --- COLAB SERVER SCRIPT ---
# 1. Cài đặt thư viện cần thiết
!pip install -q fastapi uvicorn pyngrok llama-cpp-python nest-asyncio

# 2. Tải Model DeepSeek-Coder (GGUF - Bản nén nhẹ cho T4)
!wget -O deepseek-coder-1.3b.gguf https://huggingface.co/TheBloke/deepseek-coder-1.3b-instruct-GGUF/resolve/main/deepseek-coder-1.3b-instruct.Q4_K_M.gguf

# 3. Khởi tạo Server
import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from llama_cpp import Llama
from pyngrok import ngrok
import nest_asyncio

# Load Model
print("⏳ Đang load AI Model...")
llm = Llama(model_path="./deepseek-coder-1.3b.gguf", n_gpu_layers=-1, n_ctx=2048)
print("✅ Model loaded!")

app = FastAPI()

class AnalyzeRequest(BaseModel):
    function_signature: str
    vulnerability_type: str
    context: Optional[Dict] = None

@app.post("/analyze")
def analyze(req: AnalyzeRequest, x_api_key: str = Header(None)):
    # Simple Authentication
    if x_api_key != "demo_secret":
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # Prompt kỹ thuật (Engineering Prompt) - Khớp schema 05a
    prompt = f"""### Instruction:
Analyze this Python code for {req.vulnerability_type}.
Code Snippet:
{req.function_signature}

Is this vulnerable? Answer strictly in JSON format:
{{
  "is_vulnerable": true/false,
  "confidence_score": 0.0-1.0,
  "risk_level": "CRITICAL/HIGH/MEDIUM/LOW",
  "analysis_summary": "...",
  "fix_suggestion": "...",
  "secure_code_snippet": "...",
  "constraint_check": {{"syntax_valid": true, "logic_sound": true}}
}}
### Response:
"""
    output = llm(prompt, max_tokens=500, stop=["###"], echo=False)
    # Trích xuất JSON từ phản hồi của AI
    import json
    try:
        result_json = json.loads(output['choices'][0]['text'].strip())
        return {"status": "success", "data": result_json}
    except:
        return {"status": "success", "data": output['choices'][0]['text'].strip()}

# 4. Mở đường hầm Ngrok
# Thay token của bạn vào đây (Lấy tại dashboard.ngrok.com)
NGROK_TOKEN = "YOUR_NGROK_TOKEN_HERE" 
ngrok.set_auth_token(NGROK_TOKEN)
public_url = ngrok.connect(8000).public_url
print(f"🚀 SERVER IS READY! Public URL: {public_url}")

# Chạy Server
nest_asyncio.apply()
uvicorn.run(app, port=8000)
```

**Lưu lại URL** mà Colab in ra (ví dụ: `https://abcd-123.ngrok-free.app`).

---

## Phần 3: Chạy Client Quét Lỗi (Trên Laptop)

Tạo file `demo_client.py` cùng thư mục với `vulnerable_app.py`.
Thay `COLAB_URL` bằng link bạn vừa copy ở trên.

```python
# demo_client.py
import requests
import re

# Dán URL từ Colab vào đây
COLAB_URL = "https://abcd-123.ngrok-free.app" 
API_KEY = "demo_secret"

def scan_file(filename):
    print(f"🔍 Đang quét file: {filename}...")
    
    with open(filename, 'r') as f:
        content = f.read()

    # 1. Phát hiện sơ bộ bằng Regular Expression (giả lập Rule Engine)
    # Tìm mẫu f-string trong câu lệnh SQL
    sql_pattern = re.search(r'(SELECT.*WHERE.*=.*f"|f".*SELECT.*)', content, re.IGNORECASE)
    
    if sql_pattern:
        print("⚠️  PHÁT HIỆN NGHI VẤN: Có khả năng SQL Injection!")
        print("🚀 Đang gửi sang AI Server để thẩm định...")
        
        # Trích xuất đoạn code lỗi (đơn giản hóa cho demo)
        context_code = content[max(0, sql_pattern.start()-50) : min(len(content), sql_pattern.end()+50)]
        
        payload = {
            "function_signature": context_code,
            "vulnerability_type": "SQL Injection",
            "context": {"file": filename}
        }
        
        headers = {"X-API-Key": API_KEY}

        try:
            # Gửi Request lên Colab
            response = requests.post(f"{COLAB_URL}/analyze", json=payload, headers=headers)
            if response.status_code == 200:
                resp_json = response.json()
                print("\n" + "="*40)
                print("🤖 KẾT QUẢ TỪ AI (QWEN2.5/DEEPSEEK):")
                print(resp_json['data'])
                print("="*40)
            else:
                print(f"❌ Server Error: {response.status_code} - {response.text}")
            
        except Exception as e:
            print(f"❌ Lỗi kết nối Server: {e}")
    else:
        print("✅ File có vẻ an toàn (theo bộ lọc cơ bản).")

if __name__ == "__main__":
    scan_file("vulnerable_app.py")
```

---

## Phần 4: Chạy Thử & Kết Quả

1.  Mở Terminal tại thư mục chứa code.
2.  Cài thư viện requests: `pip install requests`
3.  Chạy lệnh: `python demo_client.py`

**Kết quả mong đợi:**

```text
🔍 Đang quét file: vulnerable_app.py...
⚠️  PHÁT HIỆN NGHI VẤN: Có khả năng SQL Injection!
🚀 Đang gửi sang AI Server để thẩm định...

========================================
🤖 KẾT QUẢ TỪ AI (QWEN2.5/DEEPSEEK):
{
  "is_vulnerable": true,
  "confidence_score": 0.95,
  "risk_level": "CRITICAL",
  "analysis_summary": "The code uses Python f-strings to construct a SQL query directly from user input...",
  "fix_suggestion": "Use parameterized queries...",
  "secure_code_snippet": "...",
  "constraint_check": {"syntax_valid": true, "logic_sound": true}
}
========================================
```

Chúc mừng! Bạn đã vừa vận hành thành công một hệ thống **Hybrid Neuro-Symbolic Security** ngay trên máy tính cá nhân.
