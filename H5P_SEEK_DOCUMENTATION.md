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

## 4. Luồng xử lý Dữ liệu & Decoupled Backend Logic

Vì H5P Sandbox chạy biệt lập bên trong IFrame, hệ thống sử dụng kiến trúc **Host-Proxy** để đồng bộ dữ liệu về môi trường bên ngoài.

### Kiến trúc Giao tiếp (Communication & Transport):
1.  **IPC Bridge (IFrame -> Host):** `seek-blocker.js` sử dụng `postMessage` để đẩy các `H5P_XAPI_EVENT` và `SEEK_DEBUG` ra lớp bọc (Wrapper) ngoài cùng.
2.  **Host UI Layer (`index.html`):** Lắng nghe sự kiện IPC toàn cục. Khi nhận được tín hiệu, Host sẽ thực thi chuyển tiếp dữ liệu (Forwarding) qua phương thức `fetch()` tới Domain Tracking riêng biệt.
3.  **Cross-Origin Tracking Server (`tracking_logger.py`):** Một dịch vụ microservice độc lập chạy tại cổng `9000`, chịu trách nhiệm xử lý nghiệp vụ lưu trữ (Persistence).

---

## 5. Đặc tả API dành cho Tracking Server (Port 9000)

Dịch vụ `tracking_logger.py` cung cấp hai Endpoint logic dành cho việc ghi và đọc dữ liệu log:

### 1. Ingestion API (POST `/log`)
Sử dụng để nhận dữ liệu từ Client-side.
*   **Method:** `POST`
*   **Logic:** Deserialize JSON, bổ sung thuộc tính `server_time` (ISO timestamp) và thực thi Append vào tệp vật lý `student_tracking.json`.
*   **Persistence:** Đảm bảo tính toàn vẹn dữ liệu bằng cơ chế Load-Modify-Write trên tệp JSON phẳng.

### 2. Retrieval API (GET `/api/logs`)
Cung cấp khả năng truy xuất dữ liệu real-time dành cho Monitoring Layer hoặc Admin Dashboard.
*   **Method:** `GET`
*   **Response:** Trả về toàn bộ lịch sử tương tác dưới định dạng mảng JSON (`Array<Object>`).
*   **Security:** Hỗ trợ đầy đủ CORS Header (`Access-Control-Allow-Origin: *`) phục vụ việc tích hợp đa nền tảng (Dashboard, XBlock).

---

## 6. Hướng dẫn Triển khai & Vận hành (Deployment)

Hệ thống yêu cầu chạy song song hai tiến trình server để tách biệt luồng Statics và luồng Telemetry:

1.  **Static & Range Server (Port 8000):** 
    `python3 range_server.py`
    *   Nhiệm vụ: Cung cấp tài nguyên tĩnh và nội dung Video (hỗ trợ HTTP Range).
2.  **Tracking Logger Server (Port 9000):** 
    `python3 tracking_logger.py`
    *   Nhiệm vụ: Duy trì Persistence Layer và API Endpoint cho dữ liệu xAPI.
