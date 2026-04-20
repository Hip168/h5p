# H5P Telemetry & Navigation Control Specification (V4.0)

Tài liệu đặc tả kỹ thuật cho hệ thống giám sát hành vi người dùng và kiểm soát điều hướng (Seek Control) trên nền tảng H5P Interactive Video.

---

## 1. Kiến trúc Hệ thống (System Architecture)

Hệ thống được thiết kế theo mô hình **Real-time Event Stream**, tập trung vào việc cung cấp phản hồi tức thì cho người quản lý thông qua giao diện điều khiển (Dashboard).

### 1.1. Luồng Đồng bộ Trạng thái (UI State Synchronization)
- **Tần suất**: 1000ms Interval.
- **IPC Mechanism**: `postMessage` API giữa Iframe H5P và Host Window.
- **Scope**: Phục vụ việc hiển thị trạng thái động (Badge) và cập nhật Timeline.

### 1.2. Nhật ký Dòng thời gian trực quan (Visual Time-series Logging)
- **Cơ chế**: **High-detail Event Sampling**.
- **Display**: `Professional Event Log` (Full-width).
- **Metadata**: Mọi hành động đều được gắn nhãn thời gian video (`[XX.Xs]`) chính xác đến từng mili giây.

---

## 2. Đặc tả Xử lý Tương tác (Interaction Logic)

### 2.1. Quản lý Vòng đời Tua (Seek Interaction Lifecycle)
- **Detection**: Giám sát trạng thái `mousedown`/`mouseup` trên DOM Iframe.
- **Timestamping**: Tự động ghi nhận mốc thời gian bắt đầu và kết thúc của hành động tua.
- **Blocking Policy**: Áp dụng luật chặn nghiêm ngặt đối với hành vi "Tua tới" vùng chưa xem (Forward seeking). Ghi log `🚫 CHẶN` trực tiếp lên UI kèm mốc thời gian vi phạm.

### 2.2. Tổng kết Hoàn thành (Completion Summary)
- **Cơ chế**: Khi phát hiện sự kiện `finished`, hệ thống tự động tổng hợp dữ liệu toàn quá trình.
- **Thông số**: Hiển thị tổng quát: `Tổng thời gian đã xem` | `Tổng số câu hỏi đã tương tác`.

---

## 3. Đặc tả Giao tiếp & Giám sát (Communication & Monitoring)

### 3.1. Terminal-only Backend Stream
Hệ thống loại bỏ hoàn toàn việc lưu trữ file vật lý (`.json`) để tối ưu hiệu suất và dung lượng.
- **Stream**: Dữ liệu tương tác được đẩy về cổng **9000** (`tracking_logger.py`).
- **Monitoring**: Dữ liệu chỉ được hiển thị trực tiếp trên màn hình Console/Terminal của người quản trị (Live Debugging).

### 3.2. Dashboard UX
- **Event Log**: Bảng log chuyên nghiệp, hỗ trợ cuộn tự động và sao chép dữ liệu nhanh.
- **Status Badge**: Hiển thị tiến độ phần trăm (%) và số lượng câu hỏi đã trả lời thời gian thực.

---

## 4. Khả năng Phân tích (Analytics Capability)

Dữ liệu trên Event Log cho phép:
- **Real-time Auditing**: Kiểm tra ngay lập tức hành vi của học viên mà không cần chờ trích xuất file.
- **Interaction Heatmap**: Theo dõi các điểm dừng (Pause/Play) và các lỗi phát sinh trong quá trình phát video.
- **Compliance Check**: Xác nhận trạng thái `HOÀN THÀNH` một cách minh bạch với đầy đủ bằng chứng về chỉ số tương tác.

---
*Tài liệu này là đặc tả cuối cùng sau khi chuyển đổi sang mô hình UI-Focused Telemetry.*
