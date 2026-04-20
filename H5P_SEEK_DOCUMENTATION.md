# H5P Interactive Video: System Workflow, Telemetry & Interception Logic

Tài liệu này đặc tả kiến trúc, luồng xử lý (Workflow) và hệ thống thu thập dữ liệu (Telemetry) của H5P Interactive Video, bao gồm cơ chế Prevent Skipping (Chặn tua) và theo dõi tương tác người dùng qua chuẩn xAPI. Viết dưới góc độ kỹ thuật dành cho Technical Lead/Reviewer.

---

## 1. Tổng quan Kiến trúc (System Architecture)

Hệ thống hoạt động dựa trên cơ chế **Runtime Method Overriding** và **Event Interception**. 

Thay vì chỉnh sửa mã nguồn cốt lõi (Core Library) của H5P, hệ thống inject một Script Manager (`seek-blocker.js`) vào lifecycle của thẻ Iframe H5P. Script này thực thi 2 nghiệp vụ chính:
1. **Seek Control**: Override method logic của mốc timeline để chặn việc tua qua nội dung chưa xem.
2. **xAPI Telemetry**: Lắng nghe toàn bộ Event Bus để bắt các tương tác (trả lời câu hỏi) và sync Data Layer ra bên ngoài qua IPC (`window.postMessage`) và đẩy về Backend Server.

---

## 2. Quản lý Trạng thái & Logic Chặn Tua (State Management & Seek Control)

Logic phân xử việc cho phép thay đổi mốc thời gian (seeking) phụ thuộc vào 2 Internal State Variables của đối tượng H5P:

*   `this.preventSkippingMode` (Enum String): **Policy State** (`none`, `full`, `both`). Cấu hình luật chặn. Mặc định đọc từ `content.json`.
*   `this.maxTimeReached` (Float): **High-water mark State**. Lưu lượng thời gian tối đa mà video đã tự phát (play-through). Biến này tự động được internal tick-update của H5P kích hoạt thông qua event `timeupdate` của HTML5 Video Element.

**Flow Validation (Mode `full` - Workflow mặc định):**
Mọi hành động Click lên thanh tiến trình sinh ra một tham số `targetTime`.
```javascript
// Function Override: isSkippingProhibited(targetTime)
// Dung sai +0.2s cho buffer latency DOM precision.
if (targetTime <= this.maxTimeReached + 0.2) { 
  return false; // Condition Passed -> Cấp quyền tua
}
return true; // Condition Failed -> Bị chặn, raise UI Warning
```
*   **Backward Seek (Ôn tập):** Nếu `targetTime` < `maxTimeReached`, hệ thống allow bypass.
*   **Forward Seek (Nhảy cóc):** Nếu `targetTime` > `maxTimeReached`, hệ thống intercept Event Loop, khóa progress bar và raise UI Warning. 

---

## 3. Hệ thống Tracking Tương tác (xAPI Telemetry)

H5P chuẩn hóa toàn bộ dữ liệu tương tác theo giao thức **xAPI (Experience API)**. `seek-blocker.js` kết nối vào Event Bus gốc (`H5P.externalDispatcher`) để bắt các tín hiệu này.

### Phân loại xAPI Events (Verb Types):
Trong quá trình học viên chạy video, các Event sau sẽ được emit:
1.  **`attempted`**: Được bắn ra khi khởi tạo phiên (session) hoặc khi user bắt đầu chạm tới một Node (Câu hỏi / Checkpoint).
2.  **`interacted`**: Sinh ra mỗi khi user tương tác nhẹ với UI (Ví dụ: Click chọn một đáp án A, đổi ý chọn đáp án B). Object này chưa mang thông tin tính điểm.
3.  **`answered` (hoặc `completed`)**: **Dữ liệu đắt giá nhất**. Sinh ra khi user bấm nút "Check" hoặc "Submit". Cục JSON này mang theo Metadata rất chi tiết cho Database:

### Đặc tả Payload JSON của event `answered`:
```json
{
  "object.definition.description": "Nội dung câu hỏi (VD: Python là ngôn ngữ gì?)",
  "object.definition.choices": [ "Danh sách các ID & Label phương án" ],
  "object.definition.correctResponsesPattern": ["1"], // Đáp án quy chuẩn của DB
  "result": {
    "response": "1",          // Phương án User thực tế chọn
    "success": true,          // Kết quả: true (Đúng), false (Sai)
    "score": {
      "raw": 1,               // Điểm số nhận được
      "max": 1                // Điểm tối đa
    },
    "duration": "PT2.04S"     // Time-on-task: Thời gian dừng lại suy nghĩ
  },
  "context.extensions['...ending-point']": "PT135S" // Tọa độ (giây) của câu hỏi trên Video
}
```

---

## 4. Luồng xử lý Dữ liệu & Backend Synchronization (Data Flow)

Vì H5P Sandbox chạy bên trong IFrame, quy chuẩn bảo mật (Same-Origin Policy) không cho phép Node cha can thiệp trực tiếp. 

**Kiến trúc Giao tiếp (Communication Architecture):**
1.  **State Polling (Iframe -> Wrapper):** 
    Mỗi 1000ms (1s), Script chạy vòng lặp đọc `video.getCurrentTime()` và `maxTimeReached`, gom thành Object JSON cấu trúc `H5P_SYNC_STATE`, sau đó bắn ra Wrapper `index.html` thông qua `postMessage`.
2.  **Event Driven (Iframe -> Wrapper):**
    Ngay khi Event Bus bắt được gói xAPI, nó đóng gói dưới type `H5P_XAPI_EVENT` và bắn thẳng ra Wrapper.
3.  **Network Transport (Wrapper -> Backend):**
    Tại tầng Host UI (`index.html`), hệ thống lắng nghe IPC. Khi có gói Tin `H5P_XAPI_EVENT`, Wrapper gọi hàm `fetch()` sử dụng method `POST` tới API `/log-interaction` của Backend Python.
4.  **Logging Service (Python Backend):**
    Server (`range_server.py`) sẽ deserialize gói JSON, trích xuất verb (loại event) và Dump output formatted ra stdout (Terminal), sẵn sàng cho các tiến trình ELK stack cấu hình lưu trữ Log.
