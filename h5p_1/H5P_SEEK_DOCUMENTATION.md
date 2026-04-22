# H5P Telemetry & Navigation Control Specification (V5.0)

Tài liệu đặc tả kỹ thuật cho hệ thống giám sát hành vi người dùng, kiểm soát điều hướng (Seek Control) và đánh giá tiến trình học tập trên nền tảng H5P Interactive Video.

---

## 1. Kiến trúc Hệ thống (System Architecture)

Hệ thống được thiết kế theo mô hình **Zero-Persistence Analytics** kết hợp **Real-time Event Stream**, tập trung vào việc quản lý dữ liệu tại Client-side và cung cấp phản hồi lập tức.

### 1.1. Giao tiếp Liên tiến trình (IPC Mechanism)
- **Giao thức**: `postMessage` API hai chiều giữa Iframe H5P và phiên bản cha (Host Window).
- **Tần suất Heartbeat**: Bộ định thời 1000ms (`setInterval`) liên tục đồng bộ dữ liệu trạng thái (Sync State).

### 1.2. Màn hình Log Thời gian thực (Visual Time-series Logging)
- **Cơ chế**: High-detail Event Sampling (Lấy mẫu dữ liệu sự kiện độ phân giải cao).
- **Metadata**: Mọi bản ghi (Log entry) đều tuân thủ cấu trúc gắn nhãn thời gian video (`[XX.Xs]`) có độ chính xác đến mili giây. Hệ thống backend (`tracking_logger.py`) đã bị loại bỏ hoàn toàn, mọi hoạt động phân tích được off-load sang DOM UI.

---

## 2. Đặc tả Khởi tạo Tham số Tương tác (Interaction Initialization)

Sự chính xác của tập dữ liệu tương tác (Questions/Quizzes) là cốt lõi để đánh giá trạng thái hoàn thành.

### 2.1. Direct Fetching Mechanism
- **Phương pháp chính**: Request HTTP trực tiếp tới tệp cấu hình nguồn (`h5p-content/content/content.json`).
- **Phân tích cú pháp (Parsing)**: Bóc tách đường dẫn `interactiveVideo.assets.interactions`, lặp qua danh sách đối tượng (Mảng), kết hợp cơ chế ngoại trừ các thư viện phi tương tác (ví dụ: `H5P.Label`). 
- **Độ tin cậy**: Quá trình này được thực thi độc lập, miễn nhiễm với sự chậm trễ trong quá trình khởi tạo đối tượng DOM của trình phát H5P. Đảm bảo độ chính xác của tham số `totalQuestions` đạt 100%.

### 2.2. Aggressive Failsafe (Cơ chế Dự phòng Đa tầng)
- Nếu tác vụ lấy dữ liệu qua luồng HTTP thất bại, hệ thống tự động Fallback (dự phòng) sang chế độ "Vét cạn" (Deep scan) bên trong bộ nhớ đối tượng `H5P.instances[0]`.
- Mẫu số `totalQuestions` bị **khóa tĩnh (locked)**. Bất kỳ sự kiện nào cố tình ghi đè giá trị này về `0` đều bị chặn lại. 
- Trong trường hợp cực đoan (Số phản hồi lấy được lớn hơn số định mức trong tệp tin cấu hình), bộ đếm Tổng động đồng bộ hóa chặn dưới: `totalQuestions = max(totalQuestions, answeredIds.size)`.

---

## 3. Quản lý Điều hướng (Seek Management)

- **Detection**: Liên kết bộ lắng nghe sự kiện tại các DOM node điều hướng thanh trượt (Slider DOM Elements).
- **Debouncing**: Áp dụng cửa sổ thời gian 300ms nhằm chống ngập lụt tín hiệu (Flood control) khi người dùng kéo thả thanh điều hướng.
- **Strict Blocking Policy**: Ở chế độ cấu hình `full` hoặc `both`, hệ thống đối soát độ lệch thời gian (`to > maxTimeReached + 0.2s`). Hành vi vi phạm sẽ kích hoạt tín hiệu `🚫 CHẶN` trực tiếp trên Event Stream và ép luồng video quay lại vị trí hợp lệ cuối cùng.

---

## 4. Chính sách Đánh giá Hoàn thành (Strict Completion Policy)

Việc phát video tới giây cuối cùng không đồng nghĩa với hoàn thành nếu người dùng chưa thỏa mãn bộ quy tắc tác vụ.

### 4.1. Điều kiện Xét duyệt (Validation Rules)
1. **Trigger Condition**: Tín hiệu `H5P.Video.ENDED` được phát ra, hoặc sai số thời gian giữa độ dài chuẩn của video và thời điểm hiện tại `Math.abs(duration - time) <= 0.5s`.
2. **Boolean Check**: Mệnh đề `answeredIds.size >= totalQuestions` phải trả về `True`.

### 4.2. Phản ứng Hệ thống (System Behaviors)
- **Trường hợp vi phạm**: Từ chối thiết lập cờ `isCompleted = true`. Hệ thống phát ra tín hiệu `⚠️ CHƯA HOÀN THÀNH` trực quan hóa trên giao diện điều khiển, chỉ rõ tỷ lệ phản hồi thiếu hụt (`[Answered]/[Total]`).
- **Trường hợp hợp lệ**: Cờ `isCompleted` được gán, hệ thống ban hành thẻ xác thực `🏁 HOÀN THÀNH`. Dữ liệu này được niêm phong cho toàn bộ phiên làm việc.

---

## 5. Danh mục Sự kiện (Event Dictionary)

Chi tiết các tín hiệu được truyền tải qua `postMessage` từ Iframe H5P ra ứng dụng cha:

| Loại sự kiện (`type`) | Kích hoạt (Trigger) | Ý nghĩa / Mục tiêu |
| :--- | :--- | :--- |
| **`H5P_SYNC_STATE`** | Tần suất 1000ms | **Heartbeat**: Cập nhật real-time `currentTime`, `duration`, `isCompleted`, và tiến độ câu hỏi. |
| **`H5P_STASH_EVENT`**| Tương tác thực tế | **Interaction Log**: Ghi nhận chi tiết hành vi Play, Pause, Answer (Đúng/Sai) và mốc hoàn thành. |
| **`SEEK_DEBUG`** | Thao tác tua video | **Navigation Audit**: Cung cấp dữ liệu đối soát hành vi tua video (Hợp lệ vs Bị chặn). |
| **`SEEK_BLOCKER_READY`**| Khởi tạo script | **Handshake**: Xác nhận hệ thống giám sát đã sẵn sàng hoạt động. |

---
*Tài liệu đặc tả V5.0 - Áp dụng Cơ chế "Kỷ luật Thép" trong đánh giá tiến độ học tập (Strict Enforcement).*
