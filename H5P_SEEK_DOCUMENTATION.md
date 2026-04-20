# H5P Telemetry & Navigation Control Specification (V3.0)

Tài liệu đặc tả kỹ thuật cho hệ thống giám sát hành vi người dùng và kiểm soát điều hướng (Seek Control) trên nền tảng H5P Interactive Video.

---

## 1. Kiến trúc Hệ thống (System Architecture)

Hệ thống được thiết kế theo mô hình **Hybrid Synchronization**, tách biệt giữa luồng dữ liệu hiển thị (UI Presentation) và luồng dữ liệu bền vững (Data Persistence).

### 1.1. Luồng Đồng bộ Trạng thái (UI State Synchronization)
- **Tần suất**: 1000ms Interval.
- **Cơ chế**: IPC (Inter-Process Communication) qua `postMessage` API từ H5P Iframe tới Host Window.
- **Dữ liệu**: `currentTime`, `maxTimeReached`, `completionStatus`, `answeredCount`.
- **Phạm vi**: Chỉ phục vụ Rendering UI (Badge/Progress Bar), không kích hoạt IO ghi đĩa nhằm tối ưu tài nguyên hệ thống.

### 1.2. Luồng Nhật ký Sự kiện (Event-driven Telemetry)
- **Cơ chế**: Trigger-based (Dựa trên sự kiện).
- **Phạm vi**: Ghi lại các tương tác có ý nghĩa phục vụ Business Intelligence (BI).
- **Events**: `play`, `pause`, `seek_attempt`, `answered`, `completed`, `error`.
- **Persistence**: Lưu trữ dưới định dạng **Flattened JSON** tại Master Log File.

---

## 2. Đặc tả Xử lý Tương tác (Interaction Logic)

### 2.1. Quản lý Vòng đời Tua (Seek Interaction Lifecycle)
Để loại bỏ nhiễu dữ liệu (Log Noise) trong quá trình kéo thả thanh điều hướng (Seekbar dragging), hệ thống áp dụng cơ chế:
- **Interaction Detection**: Theo dõi trạng thái `mousedown` và `mouseup` trên DOM Iframe.
- **Final Target Commit**: Chỉ thực hiện `POST` request khi nhận sự kiện `mouseup` hoặc sau một khoảng `debounce (300ms)` nếu tương tác không thông qua thiết bị con trỏ.
- **Logic Chặn (Blocking)**: Thực thi tại lớp H5P Prototype thông qua ghi đè (Override) phương thức `isSkippingProhibited`.

### 2.2. Xử lý Dữ liệu xAPI (Normalization)
- **Deduplication**: Loại bỏ các gói tin xAPI dư thừa hoặc không thuộc phạm vi theo dõi.
- **Label Lookup**: Tự động ánh xạ `Choice ID` thành `Human-readable Label` bằng cách truy vấn định nghĩa đối tượng (Object Definition) trong xAPI Statement.
- **Sanitization**: Tự động Regex để loại bỏ HTML Tags khỏi Schema Câu hỏi/Câu trả lời.

---

## 3. Đặc tả Lưu trữ & API (Storage & REST API)

### 3.1. Master Log - Data Schema
Hệ thống hợp nhất toàn bộ Telemetry vào một điểm lưu trữ duy nhất để đảm bảo tính toàn vẹn dữ liệu (Data Integrity).
- **File**: `activity_summary.json`
- **Schema**:
    - `server_time`: ISO-8601 Timestamp (Server-side generated).
    - `action`: Phân loại hành động (Verb).
    - `time`: Position hiện tại trong Player (Float).
    - `question/answer`: Chuỗi văn bản đã qua chuẩn hóa.
    - `status`: Metadata về kết quả tương tác (Success/Fail/Score).

### 3.2. Tracking Server API (Port 9000)
- **Endpoint `POST /log`**: Tiếp nhận Payload JSON, hỗ trợ CORS Preflight.
- **Endpoint `GET /api/logs`**: Truy vấn nhật ký hoạt động. Hỗ trợ tham số `raw` để trích xuất toàn bộ cơ sở dữ liệu.
- **Endpoint `Reset`**: Thực thi lệnh `TRUNCATE` trên file vật lý khi nhận tín hiệu từ quản trị viên.

---

## 4. Quản trị & Vận hành (Operations)

Hệ thống cung cấp Dashboard điều khiển tích hợp:
- **Live Sync Monitor**: Theo dõi dữ liệu thời gian thực thông qua cơ chế Auto-fetch (Interval 2s).
- **Manual Data Truncation**: Chức năng dọn dẹp bộ nhớ đệm và reset file log vật lý trên Server.
- **Reporting Export**: Hỗ trợ truy xuất dữ liệu JSON chuẩn để chuyển đổi sang định dạng `.xlsx` hoặc `.csv`.

---
*Tài liệu này được biên soạn cho mục đích phát triển và bàn giao kỹ thuật.*
