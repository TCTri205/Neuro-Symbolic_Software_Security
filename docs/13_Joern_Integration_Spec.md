# 13. Joern Integration Specification (Stub)

Tài liệu này định nghĩa giao diện tích hợp (Interface) giữa NSSS và Joern - công cụ phân tích tĩnh mạnh mẽ cho C/C++, Java, PHP. Mục tiêu là mở rộng khả năng của NSSS sang đa ngôn ngữ trong tương lai.

## 1. Mục Tiêu

*   **Hiện tại (Phase 1):** Tạo "Stub" (vỏ bọc) để giữ chỗ trong kiến trúc.
*   **Tương lai (Phase 2):** Sử dụng Joern để parse code -> Export CPG (Code Property Graph) -> Convert sang NSSS IR.

## 2. Kiến Trúc Adapter

Chúng ta sẽ áp dụng pattern **Adapter** để biến đổi output của Joern thành input chuẩn của NSSS (Neuro-Symbolic IR).

```mermaid
graph LR
    A[Source Code (C/Java)] -->|Joern CLI| B(Joern CPG)
    B -->|Joern Export| C(GraphML/DOT)
    C -->|JoernAdapter| D[NSSS IR Graph]
    D --> E[Analysis Engine]
```

## 3. Interface Definition

File: `src/core/interop/joern.py`

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class ExternalParser(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Parse file and return IR dict compatible with NSSS."""
        pass

class JoernStub(ExternalParser):
    def check_installed(self) -> bool:
        """Kiểm tra xem Joern đã được cài đặt trong môi trường chưa."""
        # TODO: Check subprocess calls to 'joern --version'
        pass

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Mock implementation.
        Trong tương lai sẽ gọi:
        1. joern-parse <file_path>
        2. joern-export --format graphml
        3. convert_graphml_to_nsss_ir()
        """
        logger.warning("Joern integration is not yet implemented. Returning empty graph.")
        return {
            "nodes": [],
            "edges": [],
            "metadata": {"parser": "joern-stub"}
        }
```

## 4. Mapping Chiến Lược (Draft)

NSSS IR (`docs/07_IR_Schema.md`) cần được map từ Joern CPG schemas:

| Joern Node | NSSS IR Node | Ghi chú |
| :--- | :--- | :--- |
| `METHOD` | `Function` | Node bắt đầu hàm |
| `CALL` | `Call` | Lời gọi hàm |
| `IDENTIFIER` | `Variable` | Biến |
| `LITERAL` | `Constant` | Hằng số |
| `CONTROL_STRUCTURE` | `ControlFlow` | If, While, For |

## 5. Yêu Cầu Task (nsss-bce.7.8)

Task `nsss-bce.7.8` chỉ yêu cầu implement lớp `JoernStub` và unit test đảm bảo:
1.  Code gọi được class này mà không crash.
2.  Trả về cấu trúc dữ liệu rỗng (hoặc mock data) đúng chuẩn IR Schema.
3.  Log cảnh báo khi được gọi.

Không yêu cầu cài đặt Joern thật sự trong giai đoạn này.
