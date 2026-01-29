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

Hệ thống NSSS sử dụng monitoring thresholds tự động để phát hiện vấn đề hoạt động và chất lượng.

### 2.1. Monitoring Thresholds (Ngưỡng Giám sát)

#### Token Usage Thresholds (Chi phí Token)

| Metric | Warning Threshold | Critical Threshold | Mô tả |
|--------|-------------------|--------------------|-----------------------|
| **Tokens per Request** | 6,000 tokens | 8,000 tokens | Số token cho một LLM call |
| **Tokens per Scan** | 75,000 tokens | 100,000 tokens | Tổng token cho toàn bộ scan |
| **Cost per Scan** | $3.00 USD | $5.00 USD | Chi phí ước tính (GPT-4 pricing) |

**Mục đích:**
- Ngăn ngừa chi phí API vượt kiểm soát
- Phát hiện prompt expansion quá lớn
- Circuit Breaker tự động kích hoạt khi vượt Critical threshold

**Cách điều chỉnh:** Xem `src/core/telemetry/thresholds.py` - `TokenThreshold`

#### Latency Thresholds (Thời gian phản hồi)

| Operation | Warning (ms) | Critical (ms) | Mô tả |
|-----------|--------------|---------------|-------|
| **Parse** | 3,000 | 5,000 | Phân tích AST từ source code |
| **CFG Build** | 7,000 | 10,000 | Xây dựng Control Flow Graph |
| **LLM Call** | 20,000 | 30,000 | Một LLM API call (semantic verification) |
| **Total Scan** | 90,000 (1.5m) | 120,000 (2m) | Toàn bộ scan một project |

**Mục đích:**
- Phát hiện performance degradation
- Xác định bottleneck trong pipeline
- Cảnh báo timeout trước khi xảy ra

**Cách điều chỉnh:** Xem `src/core/telemetry/thresholds.py` - `LatencyThreshold`

#### Quality Metrics Thresholds (Chất lượng phát hiện)

| Metric | Warning Threshold | Critical Threshold | Mô tả |
|--------|-------------------|--------------------|-----------------------|
| **Precision** | < 80% | < 70% | TP / (TP + FP) - Độ chính xác |
| **Recall** | < 70% | < 60% | TP / (TP + FN) - Độ phủ |
| **False Positive Rate** | > 20% | > 30% | FP / (FP + TN) - Tỷ lệ báo sai |

**Mục đích:**
- Đảm bảo chất lượng phát hiện lỗ hổng
- Cân bằng giữa Precision và Recall
- Phát hiện sớm model degradation

**Cách điều chỉnh:** Xem `src/core/telemetry/thresholds.py` - `QualityThreshold`

### 2.2. Cách sử dụng Monitoring Thresholds

#### Trong Code (Programmatic)

```python
from src.core.telemetry.thresholds import ThresholdChecker, get_threshold_checker

# Sử dụng checker mặc định
checker = get_threshold_checker()

# Kiểm tra token usage
alerts = checker.check_token_usage(
    prompt_tokens=4000,
    completion_tokens=2500,
    scan_total_tokens=50000
)

# Kiểm tra latency
alerts = checker.check_latency("llm_call", duration_ms=25000)

# Kiểm tra quality metrics
alerts = checker.check_quality_metrics(
    precision=0.85,
    recall=0.75,
    fpr=0.18
)

# Lấy tất cả alerts
all_alerts = checker.get_alerts()
critical_alerts = checker.get_alerts(level=AlertLevel.CRITICAL)
token_alerts = checker.get_alerts(category="token")
```

#### Custom Thresholds (Tùy chỉnh ngưỡng)

```python
from src.core.telemetry.thresholds import (
    MonitoringThresholds,
    TokenThreshold,
    ThresholdChecker
)

# Tạo custom thresholds cho môi trường production nghiêm ngặt hơn
custom_thresholds = MonitoringThresholds(
    token=TokenThreshold(
        max_tokens_per_request=6000,  # Giảm từ 8000
        max_tokens_per_scan=80_000,  # Giảm từ 100_000
        max_cost_per_scan_usd=3.0  # Giảm từ 5.0
    )
)

# Sử dụng custom thresholds
checker = ThresholdChecker(custom_thresholds)
```

### 2.3. Alert Levels và Response

#### INFO
- **Mô tả:** Thông tin bình thường, không cần hành động
- **Action:** Ghi log để phân tích sau

#### WARNING
- **Mô tả:** Tiệm cận ngưỡng, cần theo dõi
- **Action:**
  - Ghi log và thông báo team
  - Kiểm tra trend (nếu liên tục tăng -> cần tối ưu)
  - Không cần dừng scan

#### CRITICAL
- **Mô tả:** Vượt ngưỡng tối đa, có thể gây lỗi
- **Action:**
  - **Token:** Circuit Breaker kích hoạt, dừng scan
  - **Latency:** Timeout risk, cần investigation ngay
  - **Quality:** Model đang underperform, cần retrain/điều chỉnh

### 2.4. Monitoring Best Practices

#### 1. Thiết lập Alerts

```python
# Ví dụ: Gửi alert qua email/Slack khi CRITICAL
def send_alert(alert):
    if alert.level == AlertLevel.CRITICAL:
        slack.send_message(f"🚨 CRITICAL: {alert.message}")
        email.send(f"Alert: {alert.message}")

# Hook vào logging
import logging
logging.basicConfig(
    level=logging.WARNING,
    handlers=[
        logging.FileHandler(".nsss/logs/monitoring.log"),
        logging.StreamHandler()
    ]
)
```

#### 2. Định kỳ Review Metrics

```bash
# Dump metrics ra file để phân tích
from src.core.telemetry.metrics import MetricsCollector

collector = MetricsCollector()
collector.dump_to_file(".nsss/metrics/summary.json")
```

**Frequency:**
- **Hourly:** Check critical alerts
- **Daily:** Review warning alerts, analyze trends
- **Weekly:** Generate report, tune thresholds nếu cần

#### 3. Tùy chỉnh Thresholds theo Environment

| Environment | Token Budget | Latency Tolerance | Quality Target |
|-------------|--------------|-------------------|----------------|
| **Development** | High (test với sample nhỏ) | High (có thể chậm) | Medium (70% precision OK) |
| **CI/CD** | Medium (scan PR) | Medium (< 2 min) | High (80%+ precision) |
| **Production** | Low (chi phí quan trọng) | Low (< 1 min) | Very High (90%+ precision) |

### 2.5. Troubleshooting Threshold Violations

#### Token Usage Exceeded

**Nguyên nhân:**
- Code file quá lớn (> 1000 LOC)
- Speculative Expansion quá rộng
- Nhiều LLM calls cho một file

**Giải pháp:**
```bash
# 1. Chia nhỏ file lớn
# 2. Giảm expansion depth trong config
# 3. Enable Hierarchical Summarization
# 4. Sử dụng smaller model cho preliminary scan
```

#### Latency Exceeded

**Nguyên nhân:**
- Network latency tới LLM API
- Model overloaded
- Complex code graph

**Giải pháp:**
```bash
# 1. Sử dụng local LLM (Qwen2.5-Coder-7B)
# 2. Enable caching (LLM cache + Graph cache)
# 3. Parallel processing cho multiple files
# 4. Timeout configuration trong circuit breaker
```

#### Quality Metrics Degraded

**Nguyên nhân:**
- Model drift
- New vulnerability patterns chưa học
- Feedback loop chưa cập nhật

**Giải pháp:**
```bash
# 1. Review feedback data
nsss ops health  # Check feedback store

# 2. Update Librarian profiles
# 3. Retrain Risk Ranker với feedback mới
# 4. Fine-tune LLM nếu cần

# 5. Tạm thời giảm threshold để avoid false alarms
```

---

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
