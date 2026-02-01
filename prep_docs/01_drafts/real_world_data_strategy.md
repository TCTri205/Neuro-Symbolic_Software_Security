# [Draft] Chiến lược Dữ liệu Thực tế (Real-world Data Strategy)

**Người đề xuất:** NSSS Team
**Ngày:** 01/02/2026
**Trạng thái:** Draft

## 1. Mục tiêu
*   Kiểm chứng sức mạnh của NSSS trên "chiến trường" thực tế, nơi code lộn xộn, thiếu docs và dùng nhiều meta-programming.
*   Xây dựng kho dữ liệu "Ground Truth" để làm giàu cho module Librarian và Fine-tuning.

## 2. Nguồn Dữ liệu Công khai (Public Datasets)
Chúng ta sẽ không tự thu thập từ đầu mà đứng trên vai người khổng lồ:

| Tên Dataset | Mô tả | Ứng dụng cho NSSS |
|---|---|---|
| **CodeQL Database** (GitHub) | Hàng nghìn repo đã biên dịch sẵn | Dùng làm nguồn tham chiếu (Ground Truth) để so sánh kết quả phân tích tĩnh. |
| **Big-Vuln** (Fan et al.) | Cặp hàm Lỗi/Vá trích xuất từ CVE thực | Dùng train AI nhận diện mẫu lỗi (Pattern Recognition). |
| **SecurityEval** | Dataset chứa các prompt dụ dỗ AI viết code lỗi | Dùng để Red-team lớp AI, kiểm tra xem nó có bị lừa không. |
| **OSS-Fuzz** (Google) | Hàng nghìn lỗi crash/vuln tìm thấy bởi fuzzer | Kiểm tra khả năng phát hiện lỗi sâu (Deep Bugs) mà mắt thường khó thấy. |
| **PyUp Safety DB** | DB các thư viện Python bị lỗi | Nguồn dữ liệu chính cho module `Librarian`. |

## 3. Kế hoạch Khai thác
### Giai đoạn 1: Ingest (Nhập liệu)
*   Tải tập con (Subset) của **Big-Vuln** (lọc lấy Python).
*   Tích hợp dữ liệu từ **PyUp** vào `Librarian` để cảnh báo dependency lỗi.

### Giai đoạn 2: Verify (Kiểm chứng)
*   Chạy NSSS trên 50 mẫu ngẫu nhiên từ **Big-Vuln**.
*   Đánh giá: NSSS có phát hiện ra lỗi mà Big-Vuln đã dán nhãn không?

### Giai đoạn 3: Enrich (Làm giàu)
*   Dùng các mẫu lỗi "lạ" tìm thấy trong **OSS-Fuzz** để tạo Rule mới cho Semgrep (Static Layer).

## 4. Checklist Triển khai
- [ ] Tải sample Big-Vuln dataset (file JSON/CSV).
- [ ] Viết script `scripts/ingest_bigvuln.py` để convert data sang định dạng huấn luyện của NSSS.
- [ ] Chọn 3 repo Python nổi tiếng trên GitHub (VD: `flask`, `requests`, `ansible`) để làm mục tiêu scan thử nghiệm "Real-world".
