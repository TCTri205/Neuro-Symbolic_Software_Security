# 07. IR Schema (AST + SSA + CFG)

Tài liệu này định nghĩa schema IR thống nhất cho Parser/SSA/CFG. Mục tiêu là tạo biểu diễn ổn định, deterministic để hỗ trợ caching, taint, và các tầng phân tích phía sau.

## 1) Phạm vi

- Ngôn ngữ mục tiêu: Python (giai đoạn đầu)
- Đầu ra: JSON (graph-based)
- Tích hợp: Parser -> IR -> SSA -> CFG

## 2) Cấu trúc tổng thể

IR gồm 3 nhóm chính:

1. **Nodes**: thực thể cú pháp/ngữ nghĩa (Module, Function, Assign, Call, ...)
2. **Edges**: quan hệ điều khiển/luồng (flow/true/false/exception/...)
3. **Symbols**: bảng ký hiệu để tra cứu định danh và phiên bản SSA

## 3) Schema cơ bản

### 3.1 Node

```
Node {
  id: string,               // stable id
  kind: string,             // enum
  span: {                   // source location
    file: string,
    start_line: int,
    start_col: int,
    end_line: int,
    end_col: int
  },
  parent_id: string | null,
  scope_id: string | null,
  attrs: object             // open attributes
}
```

### 3.2 Edge

```
Edge {
  from: string,
  to: string,
  type: string,             // flow|true|false|exception|call|return|await|yield|break|continue
  guard_id: string | null
}
```

### 3.3 Symbol

```
Symbol {
  name: string,
  kind: string,             // var|param|function|class|import
  scope_id: string,
  defs: [string],           // node ids
  uses: [string]            // node ids
}
```

## 4) Node kinds (enum gợi ý)

- Module
- Class
- Function
- Block
- Assign
- Call
- If
- For
- While
- Try
- With
- Return
- Raise
- Await
- Yield
- Import
- Attribute
- Subscript
- Literal
- Name
- Lambda
- Compare
- BinOp
- UnaryOp
- BoolOp

## 5) SSA fields

SSA được gắn trên Node hoặc attrs của Node:

```
SSA {
  ssa_name: string,          // x_3
  def_id: string,            // node defining value
  use_ids: [string],         // nodes using value
  phi: [                     // phi inputs
    { var: string, source_block_id: string }
  ]
}
```

## 6) Dataflow / Taint tags (optional)

```
tags: ["source", "sink", "sanitizer", "tainted"]
check_id: string | null
rule_id: string | null
```

## 7) Normalization rules

- Strip comments/docstrings (deterministic)
- Normalize literals (string length cap + hash trong attrs)
- Decorator unrolling: biến decorator thành wrapper node rõ ràng
- Canonicalize imports/aliases trước khi SSA
- Stable ordering theo span để hash/caching ổn định

## 8) Serialization

Gợi ý 2 format:

1. Single JSON:

```
{
  "nodes": [...],
  "edges": [...],
  "symbols": [...]
}
```

2. JSON Lines:

```
{"type":"node", ...}
{"type":"edge", ...}
{"type":"symbol", ...}
```

### Reference

- `docs/08_Parser_Mapping_Spec.md`

## 9) AST -> IR mapping (node-by-node)

| Python AST | IR kind | attrs (gợi ý) | Notes |
| --- | --- | --- | --- |
| Module | Module | `body_ids`, `docstring_id` | `scope_id=scope:module` |
| ClassDef | Class | `name`, `bases`, `keywords`, `decorators`, `body_ids` | tạo scope riêng |
| FunctionDef | Function | `name`, `params`, `returns`, `decorators`, `is_async=false`, `body_ids` | tạo scope riêng |
| AsyncFunctionDef | Function | `name`, `params`, `returns`, `decorators`, `is_async=true`, `body_ids` | tạo scope riêng |
| arguments | (attrs) | `params`, `defaults`, `kwonly`, `vararg`, `kwarg` | gắn vào Function attrs |
| Assign | Assign | `targets`, `value_id` | targets: list ids |
| AnnAssign | Assign | `target`, `value_id`, `annotation` | `value_id` có thể null |
| AugAssign | Assign | `target`, `op`, `value_id` | normalize thành Assign |
| Name | Name | `name`, `ctx` | ctx: Load/Store/Del |
| Attribute | Attribute | `value_id`, `attr`, `ctx` | value_id là base |
| Subscript | Subscript | `value_id`, `slice_id`, `ctx` | slice là Index/Slice |
| Call | Call | `callee_id`, `args`, `keywords` | kwargs giữ name + value_id |
| Lambda | Lambda | `params`, `body_id` | scope riêng (optional) |
| IfExp | IfExp | `test_id`, `body_id`, `orelse_id` | ternary expression |
| NamedExpr | NamedExpr | `target_id`, `target_name`, `value_id` | walrus operator |
| If | If | `test_id`, `body_ids`, `orelse_ids` | tạo CFG true/false |
| For | For | `target_id`, `iter_id`, `body_ids`, `orelse_ids` | `is_async=false` |
| AsyncFor | For | `target_id`, `iter_id`, `body_ids`, `orelse_ids`, `is_async=true` | |
| While | While | `test_id`, `body_ids`, `orelse_ids` | |
| Break | (Edge) | - | CFG edge type `break` |
| Continue | (Edge) | - | CFG edge type `continue` |
| Return | Return | `value_id` | value_id có thể null |
| Raise | Raise | `exc_id`, `cause_id` | null nếu không có |
| Try | Try | `body_ids`, `handlers`, `orelse_ids`, `finalbody_ids` | handlers list |
| ExceptHandler | Block | `type_id`, `name`, `body_ids` | map sang block handler |
| With | With | `items`, `body_ids` | items: list context_expr_id + optional_vars_id |
| AsyncWith | With | `items`, `body_ids`, `is_async=true` | |
| Await | Await | `value_id` | tạo CFG edge type `await` |
| Yield | Yield | `value_id` | CFG edge type `yield` |
| YieldFrom | Yield | `value_id`, `is_from=true` | |
| Expr | (inline) | - | nếu value là Call/Literal/Name thì giữ node value |
| Pass | (omit) | - | không tạo node |
| Global | (Symbol) | `names` | gắn vào symbol table |
| Nonlocal | (Symbol) | `names` | gắn vào symbol table |
| Import | Import | `names`, `asnames` | mỗi alias map thành symbol |
| ImportFrom | Import | `module`, `names`, `asnames`, `level` | |
| Constant | Literal | `value`, `value_type`, `hash` | normalize string |
| List/Tuple | Literal | `elts`, `ctx` | elts là list ids |
| Dict | Literal | `keys`, `values` | keys/values list ids |
| Set | Literal | `elts` | |
| BoolOp | BoolOp | `op`, `values` | values list ids |
| BinOp | BinOp | `op`, `left`, `right` | |
| UnaryOp | UnaryOp | `op`, `operand` | |
| Compare | Compare | `left`, `ops`, `comparators` | ops list |
| JoinedStr | Literal | `parts` | f-string parts |
| FormattedValue | Literal | `value_id`, `format_spec_id` | part of JoinedStr |
| Comprehension | (inline) | `target_id`, `iter_id`, `ifs`, `is_async` | gắn vào ListComp/DictComp/SetComp |
| ListComp/SetComp | Literal | `elt_id`, `generators`, `comp_scope` | generators list, scope riêng |
| DictComp | Literal | `key_id`, `value_id`, `generators`, `comp_scope` | |
| GeneratorExp | Literal | `elt_id`, `generators`, `comp_scope` | |
| Match | Match | `subject_id`, `cases` | case: `pattern`, `binds`, `guard_id`, `body_block_id` |

## 10) Block node & guard_id conventions

### Block node

`Block` là node trung gian gom nhóm statement trong một nhánh hoặc một vùng đặc thù (body/orelse/handler/finally). Block giúp CFG ổn định khi thêm/bớt statement và hỗ trợ SSA/phi tại điểm hội tụ.

Attrs gợi ý:

```
{
  "label": "body|orelse|handler|finally|loop|module|exit",
  "owner_id": "<If|For|While|Try|Function|Module>",
  "stmt_ids": ["..."]
}
```

Quy ước:

- Mỗi `If/While/For/Try/With/Function/Module` tạo ít nhất 1 Block con.
- `Block` giữ thứ tự statement bằng `stmt_ids`.
- CFG edge chính nối giữa các Block, node statement vẫn giữ cạnh nội bộ (optional).

### guard_id

`guard_id` trỏ đến node điều kiện được dùng để phân nhánh hoặc lặp.

Quy ước đề xuất:

- `If`:
  - `Edge(type="true")` và `Edge(type="false")` đều có `guard_id` = `test_id`.
- `While`:
  - `Edge(type="true")` và `Edge(type="false")` đều có `guard_id` = `test_id`.
  - `Edge(type="flow")` từ `body_exit -> test` có `guard_id` = `test_id` (tái kiểm tra).
- `For/AsyncFor`:
  - `guard_id` = `iter_id` (nút iterator/next).
  - `Edge(type="true")` đại diện còn phần tử; `Edge(type="false")` là hết phần tử.
- `Try`:
  - `Edge(type="exception")` có `guard_id` = `try_id` (node Try hoặc block entry) để phân biệt luồng ném lỗi.
- `Await/Yield`:
  - `Edge(type="await"|"yield")` không cần `guard_id` (null) trừ khi cần truy nguyên ngữ cảnh.

## 11) CFG edges (gợi ý flow)

### If

```
entry -> test
test -true-> body_entry
test -false-> orelse_entry
body_exit -> join
orelse_exit -> join
```

### While

```
entry -> test
test -true-> body_entry
body_exit -> test
test -false-> exit
```

### For

```
entry -> iter
iter -next-> body_entry
body_exit -> iter
iter -done-> exit
```

### Try/Except/Finally

```
entry -> try_entry
try_exit -> finally_entry -> exit
try_entry -exception-> handler_entry
handler_exit -> finally_entry
```

### Await/Yield

```
prev -> await
await -await-> next

prev -> yield
yield -yield-> next
```

## 12) Example IR (If/While guard_id)

Python input:

```python
def process(items):
    total = 0
    if items:
        total = 1
    while total < 3:
        total = total + 1
    return total
```

IR (edges rút gọn, tập trung guard_id):

```json
{
  "nodes": [
    {"id":"If:example.py:3:4:0","kind":"If","attrs":{"test_id":"Name:example.py:3:7:0"}},
    {"id":"While:example.py:5:4:0","kind":"While","attrs":{"test_id":"Compare:example.py:5:10:0"}},
    {"id":"Name:example.py:3:7:0","kind":"Name","attrs":{"name":"items"}},
    {"id":"Compare:example.py:5:10:0","kind":"Compare","attrs":{"left":"Name:example.py:5:10:0","ops":["Lt"],"comparators":["Literal:example.py:5:18:0"]}}
  ],
  "edges": [
    {"from":"If:example.py:3:4:0","to":"Block:if_body","type":"true","guard_id":"Name:example.py:3:7:0"},
    {"from":"If:example.py:3:4:0","to":"Block:if_orelse","type":"false","guard_id":"Name:example.py:3:7:0"},
    {"from":"While:example.py:5:4:0","to":"Block:while_body","type":"true","guard_id":"Compare:example.py:5:10:0"},
    {"from":"While:example.py:5:4:0","to":"Block:while_exit","type":"false","guard_id":"Compare:example.py:5:10:0"},
    {"from":"Block:while_body","to":"While:example.py:5:4:0","type":"flow","guard_id":"Compare:example.py:5:10:0"}
  ]
}
```

Ghi chú:

- `guard_id` của `If` luôn trỏ đến `test_id` (node điều kiện).
- `While` dùng cùng `guard_id` cho cả cạnh `true/false` và cạnh quay lại `flow`.

## 13) Example IR (Try/Except/Finally)

Python input:

```python
def safe_load(path):
    try:
        data = read_file(path)
    except OSError:
        data = ""
    finally:
        log(path)
    return data
```

IR (edges rút gọn, tập trung exception):

```json
{
  "nodes": [
    {"id":"Try:example.py:2:4:0","kind":"Try","attrs":{"body_ids":["Block:try_body"],"handlers":["Block:except_oserror"],"finalbody_ids":["Block:finally"]}},
    {"id":"Call:example.py:3:15:0","kind":"Call","attrs":{"callee_id":"Name:example.py:3:15:0"}},
    {"id":"Call:example.py:6:8:0","kind":"Call","attrs":{"callee_id":"Name:example.py:6:8:0"}}
  ],
  "edges": [
    {"from":"Try:example.py:2:4:0","to":"Block:try_body","type":"flow","guard_id":null},
    {"from":"Block:try_body","to":"Block:finally","type":"flow","guard_id":null},
    {"from":"Try:example.py:2:4:0","to":"Block:except_oserror","type":"exception","guard_id":"Try:example.py:2:4:0"},
    {"from":"Block:except_oserror","to":"Block:finally","type":"flow","guard_id":null},
    {"from":"Block:finally","to":"Block:after_try","type":"flow","guard_id":null}
  ]
}
```

Ghi chú:

- Cạnh `exception` luôn xuất phát từ `Try` (hoặc `try_entry`) tới từng handler.
- `guard_id` của `exception` dùng `try_id` để truy nguyên nguồn phát sinh.

## 14) Example IR (simple function)

Python input:

```python
def add(a, b):
    c = a + b
    return c
```

IR (single JSON, rút gọn):

```json
{
  "nodes": [
    {"id":"Module:example.py:1:0:0","kind":"Module","span":{"file":"example.py","start_line":1,"start_col":0,"end_line":3,"end_col":12},"parent_id":null,"scope_id":"scope:module","attrs":{}},
    {"id":"Function:example.py:1:0:0","kind":"Function","span":{"file":"example.py","start_line":1,"start_col":0,"end_line":3,"end_col":12},"parent_id":"Module:example.py:1:0:0","scope_id":"scope:add","attrs":{"name":"add","params":["a","b"],"is_async":false}},
    {"id":"Assign:example.py:2:4:0","kind":"Assign","span":{"file":"example.py","start_line":2,"start_col":4,"end_line":2,"end_col":13},"parent_id":"Function:example.py:1:0:0","scope_id":"scope:add","attrs":{"targets":["c"],"value_id":"BinOp:example.py:2:8:0"}},
    {"id":"BinOp:example.py:2:8:0","kind":"BinOp","span":{"file":"example.py","start_line":2,"start_col":8,"end_line":2,"end_col":13},"parent_id":"Assign:example.py:2:4:0","scope_id":"scope:add","attrs":{"op":"Add","left":"Name:example.py:2:8:0","right":"Name:example.py:2:12:0"}},
    {"id":"Name:example.py:2:8:0","kind":"Name","span":{"file":"example.py","start_line":2,"start_col":8,"end_line":2,"end_col":9},"parent_id":"BinOp:example.py:2:8:0","scope_id":"scope:add","attrs":{"name":"a"}},
    {"id":"Name:example.py:2:12:0","kind":"Name","span":{"file":"example.py","start_line":2,"start_col":12,"end_line":2,"end_col":13},"parent_id":"BinOp:example.py:2:8:0","scope_id":"scope:add","attrs":{"name":"b"}},
    {"id":"Return:example.py:3:4:0","kind":"Return","span":{"file":"example.py","start_line":3,"start_col":4,"end_line":3,"end_col":12},"parent_id":"Function:example.py:1:0:0","scope_id":"scope:add","attrs":{"value_id":"Name:example.py:3:11:0"}},
    {"id":"Name:example.py:3:11:0","kind":"Name","span":{"file":"example.py","start_line":3,"start_col":11,"end_line":3,"end_col":12},"parent_id":"Return:example.py:3:4:0","scope_id":"scope:add","attrs":{"name":"c"}}
  ],
  "edges": [
    {"from":"Assign:example.py:2:4:0","to":"Return:example.py:3:4:0","type":"flow","guard_id":null}
  ],
  "symbols": [
    {"name":"a","kind":"param","scope_id":"scope:add","defs":["Function:example.py:1:0:0"],"uses":["Name:example.py:2:8:0"]},
    {"name":"b","kind":"param","scope_id":"scope:add","defs":["Function:example.py:1:0:0"],"uses":["Name:example.py:2:12:0"]},
    {"name":"c","kind":"var","scope_id":"scope:add","defs":["Assign:example.py:2:4:0"],"uses":["Name:example.py:3:11:0"]}
  ]
}
```

## 15) Lưu ý triển khai

- `id` phải ổn định theo file + span + index để hỗ trợ diff/caching
- `scope_id` phân tách rõ scope function/class/module
- `guard_id` dùng cho điều kiện if/while để tái tạo CFG
- `attrs` giữ thông tin thêm (callee, args, decorators, type_hint, is_async)
