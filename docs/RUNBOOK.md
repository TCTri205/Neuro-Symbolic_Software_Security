# RUNBOOK - Neuro-Symbolic Software Security

Tài liệu hướng dẫn vận hành và bảo trì hệ thống Neuro-Symbolic Software Security (V2.3).

## 1. Quy trình Triển khai (Deployment Procedures)

Hệ thống hỗ trợ hai hình thức triển khai chính:

### Centralized AI Server (Khuyến nghị)
1.  **Cài đặt GPU Server:** Triển khai API phục vụ LLM (Self-hosted) hoặc cấu hình Gateway tới OpenAI/Anthropic.
2.  **Cài đặt Backend:** Triển khai các module Stage 1, 2, 3 trên hạ tầng CI/CD hoặc Server riêng biệt.
3.  **Cấu hình Privacy Masking:** Đảm bảo mã hóa tên biến nhạy cảm trước khi gửi tới Cloud LLM.

### Local Deployment
*   Sử dụng cho mục đích Audit nội bộ hoặc môi trường Air-gapped.
*   Yêu cầu GPU có đủ VRAM để chạy các model GNN và Local LLM. **Qwen2.5-Coder-7B** được khuyến nghị là Canonical Model cho bước kiểm chứng ngữ nghĩa (Inference hoặc Fine-tuned). DeepSeek-Coder/Llama 3 có thể sử dụng làm phương án dự phòng.

## 2. Giám sát và Cảnh báo (Monitoring & Alerts)

*   **Token Usage:** Theo dõi chi phí Token nếu sử dụng Cloud API. Hệ thống có cơ chế **Circuit Breaker** để ngắt scan nếu chi phí vượt ngưỡng.
*   **Scan Latency:** Giám sát thời gian phân tích của từng Stage, đặc biệt là Stage 4 (LLM Verification).
*   **False Positive Rate:** Theo dõi phản hồi từ Developer thông qua Feedback Loop để tinh chỉnh Risk Ranker.

## 3. Các vấn đề Thường gặp và Cách xử lý (Common Issues)

| Vấn đề | Nguyên nhân | Cách xử lý |
| :--- | :--- | :--- |
| **Đứt gãy luồng SSA** | Python dynamic dispatch phức tạp hoặc Monkey Patching. | Kiểm tra log "Unscannable Area", thực hiện review thủ công hoặc bổ sung Framework Plugin. |
| **Token Cost quá cao** | Speculative Expansion quá rộng hoặc file quá lớn. | Điều chỉnh `Hard Limits` cho Speculative Expansion hoặc dùng `Hierarchical Summarization`. |
| **Kết quả không nhất quán** | LLM Hallucination hoặc tính ngẫu nhiên. | Đảm bảo `temperature=0` và kiểm tra `Strict Caching`. |

## 4. Quy trình Khôi phục (Rollback Procedures)

Hệ thống NSSS cung cấp các lệnh CLI tự động để tạo backup và khôi phục trạng thái hệ thống.

### 4.1. Tạo Backup

Backup tự động được tạo trước các thay đổi quan trọng. Có thể tạo backup thủ công:

```bash
# Backup tất cả các thành phần
nsss ops backup --target all --project-root /path/to/project

# Backup một thành phần cụ thể
nsss ops backup --target baseline --project-root /path/to/project
nsss ops backup --target graph --project-root /path/to/project
nsss ops backup --target llm-cache --project-root /path/to/project
nsss ops backup --target feedback --project-root /path/to/project

# Giới hạn số lượng backup lưu trữ (mặc định: 10)
nsss ops backup --target all --keep 5
```

**Các thành phần được backup:**
- **baseline**: File `.nsss/baseline.json` - Chứa các finding đã được chấp nhận
- **graph**: IR Graph cache trong `.nsss/cache/<project_hash>/graph_v1.jsonl`
- **llm-cache**: Cache LLM responses trong `.nsss/cache/llm_cache.json`
- **feedback**: User feedback trong `.nsss/feedback.json`

**Định dạng backup:** Các file backup được lưu với timestamp:
```
baseline.json.backup.20260129143000
graph_v1.jsonl.backup.20260129143000
llm_cache.json.backup.20260129143000
feedback.json.backup.20260129143000
```

### 4.2. Liệt kê Backup khả dụng

```bash
# Xem tất cả backup có sẵn
nsss ops rollback --list --project-root /path/to/project
```

Output mẫu:
```
Available backups:

BASELINE:
  - /path/to/project/.nsss/baseline.json.backup.20260129143000
    Size: 2.4 KB, Modified: 2026-01-29T14:30:00
  - /path/to/project/.nsss/baseline.json.backup.20260129120000
    Size: 2.1 KB, Modified: 2026-01-29T12:00:00

GRAPH:
  - /path/to/project/.nsss/cache/.../graph_v1.jsonl.backup.20260129143000
    Size: 156.7 KB, Modified: 2026-01-29T14:30:00
```

### 4.3. Khôi phục từ Backup

#### Khôi phục tự động (backup gần nhất)

```bash
# Khôi phục một thành phần (sử dụng backup gần nhất)
nsss ops rollback --target baseline --yes --project-root /path/to/project
nsss ops rollback --target graph --yes --project-root /path/to/project

# Khôi phục tất cả thành phần
nsss ops rollback --target all --yes --project-root /path/to/project
```

#### Khôi phục từ backup cụ thể

```bash
# Chỉ định file backup cụ thể
nsss ops rollback \
  --target baseline \
  --backup-file /path/to/.nsss/baseline.json.backup.20260129120000 \
  --yes
```

#### Dry-run (Kiểm tra trước khi khôi phục)

```bash
# Xem những gì sẽ được khôi phục mà không thực sự thay đổi
nsss ops rollback --target baseline --dry-run
```

#### Khôi phục với xác nhận

```bash
# Hệ thống sẽ hỏi xác nhận trước khi khôi phục (không có --yes)
nsss ops rollback --target baseline
# Output: This will restore baseline from backup. Continue? [y/N]:
```

### 4.4. Quản lý Backup (Pruning)

```bash
# Xóa các backup cũ, chỉ giữ lại N backup gần nhất
nsss ops rollback --prune --target baseline --keep 5

# Prune tất cả các loại backup
nsss ops rollback --prune --target all --keep 5
```

### 4.5. Quy trình Khôi phục theo Kịch bản

#### Kịch bản 1: Baseline bị hỏng sau scan

```bash
# 1. Kiểm tra trạng thái hiện tại
nsss ops health --project-root /path/to/project

# 2. Xem backup khả dụng
nsss ops rollback --list

# 3. Khôi phục baseline về trạng thái ổn định gần nhất
nsss ops rollback --target baseline --yes

# 4. Xác minh khôi phục thành công
nsss ops health
```

#### Kịch bản 2: Graph cache không hợp lệ

```bash
# 1. Clear cache hiện tại (nếu cần)
nsss ops clear-cache --graph-cache

# 2. Khôi phục từ backup
nsss ops rollback --target graph --yes

# 3. Hoặc để hệ thống tái tạo graph từ source code
# (Chạy scan lại sẽ tự động tái tạo graph)
nsss scan /path/to/project
```

#### Kịch bản 3: Rollback toàn bộ hệ thống

```bash
# Trường hợp: Sau một lần scan có vấn đề, cần quay về trạng thái trước đó

# 1. Tạo snapshot hiện tại (phòng ngừa)
nsss ops backup --target all

# 2. Rollback tất cả
nsss ops rollback --target all --yes

# 3. Xác minh
nsss ops health
```

#### Kịch bản 4: Khôi phục về một thời điểm cụ thể

```bash
# 1. List backup để tìm timestamp mong muốn
nsss ops rollback --list

# 2. Khôi phục từng thành phần về cùng một timestamp
TIMESTAMP="20260129120000"
nsss ops rollback --target baseline --backup-file .nsss/baseline.json.backup.$TIMESTAMP --yes
nsss ops rollback --target graph --backup-file .nsss/cache/.../graph_v1.jsonl.backup.$TIMESTAMP --yes
nsss ops rollback --target feedback --backup-file .nsss/feedback.json.backup.$TIMESTAMP --yes
```

### 4.6. Best Practices

1.  **Backup trước thay đổi lớn:**
    ```bash
    nsss ops backup --target all
    # Thực hiện thay đổi/scan
    ```

2.  **Kiểm tra health định kỳ:**
    ```bash
    nsss ops health
    ```

3.  **Pruning backup định kỳ:**
    ```bash
    # Chạy hàng tuần/hàng tháng
    nsss ops rollback --prune --target all --keep 10
    ```

4.  **Dry-run trước rollback quan trọng:**
    ```bash
    nsss ops rollback --target all --dry-run
    # Kiểm tra output
    nsss ops rollback --target all --yes
    ```

5.  **Giữ backup trước khi nâng cấp hệ thống:**
    ```bash
    # Trước khi update NSSS
    nsss ops backup --target all --keep 20
    git pull
    pip install --upgrade -r requirements.txt
    ```

### 4.7. Khôi phục Khẩn cấp (Emergency Recovery)

Nếu các lệnh CLI không hoạt động:

1.  **Khôi phục thủ công từ backup:**
    ```bash
    cd /path/to/project/.nsss
    cp baseline.json.backup.20260129120000 baseline.json
    ```

2.  **Xóa cache và tái tạo:**
    ```bash
    rm -rf .nsss/cache/
    nsss scan /path/to/project  # Tái tạo graph và cache
    ```

3.  **Khôi phục cấu hình mặc định:**
    ```bash
    # Backup file .env hiện tại
    cp .env .env.backup
    # Khôi phục từ .env.example
    cp .env.example .env
    # Chỉnh sửa lại API keys
    ```

---
**Maintenance:** Hệ thống cần được cập nhật Librarian Profiles định kỳ để nhận diện các thư viện mới.
