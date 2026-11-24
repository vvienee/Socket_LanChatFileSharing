# Báo cáo Hoàn thành Nhiệm vụ – Thành viên C (PySide6 GUI, Command Parser & Tích hợp)

**Dự án:** LAN Chat & File Sharing (P2P TCP/UDP Sockets + PySide6 GUI)  
**Nhánh Git:** `feat/c-pyside6-ui` (tách từ `main` theo quy chuẩn trong `docs/overview.md` mục 7)  
**Phạm vi:** Phân hệ Thành viên C (`ui/`, `main.py`, `tests/mock_c_ui.py`) và tài liệu Demo/Wireshark (`docs/demo_script.md`)  
**Môi trường kiểm thử:** Windows, Python 3.15.2 (`.venv`), PySide6 6.12.0  

---

## 1. Danh sách Nhiệm vụ của Thành viên C (được lọc từ toàn bộ dự án)

Sau khi đọc toàn bộ tài liệu thiết kế (`docs/plan.md`, `docs/overview.md`, `README.md`) và rà soát toàn bộ chú thích `TODO [Thành viên C]` trong mã nguồn, các nhiệm vụ thuộc trách nhiệm Thành viên C được tổng hợp thành bảng dưới đây:

| STT | Nhiệm vụ của Thành viên C | Tệp liên quan | Trạng thái |
| :---: | :--- | :--- | :---: |
| 1 | Thiết kế và duy trì cầu nối tín hiệu đa luồng an toàn (`AppSignals`) giữa luồng mạng (A, B) và Main GUI Thread (C). | `ui/qt_signals.py` | **Hoàn thành** |
| 2 | Hiện thực đầy đủ bộ phân tích lệnh `CommandParser`: 7 lệnh (`/list`, `/chat <name\|number>`, `/send <file>`, `/leave`, `/status <online\|away>`, `/help`, `/quit`), gửi tin nhắn văn bản thường, xử lý lỗi lệnh/tham số/file không hợp lệ và thoát an toàn. | `ui/command_parser.py` | **Hoàn thành** |
| 3 | Hoàn thiện giao diện PySide6 (`MainWindow`, Thread 1): Sidebar danh sách Peer kèm chấm màu trạng thái (`online`/`away`) và badge số tin `unread`, khung lịch sử chat không vỡ chữ khi đang gõ, thanh `QProgressBar` truyền file, hộp thoại `QFileDialog`, đồng bộ thao tác chuột với lệnh và `closeEvent` dọn tài nguyên. | `ui/main_window.py` | **Hoàn thành** |
| 4 | Ghép nối tổng thể ứng dụng tại điểm khởi chạy: kiểm tra tham số CLI, tạo thư mục `downloads/`, bắt lỗi bind cổng (`OSError`), bắt `Ctrl+C` (`SIGINT`) và dọn tài nguyên khi đóng app. | `main.py` | **Hoàn thành** |
| 5 | Viết kịch bản kiểm thử độc lập cho Thành viên C: giả lập peer/mạng nền, xác minh việc nhận tin nhắn khi đang gõ dở không vỡ chữ và kiểm thử toàn bộ 7 lệnh + thao tác GUI. | `tests/mock_c_ui.py` | **Hoàn thành** |
| 6 | Chuẩn bị kịch bản Live Demo 10 phút và hướng dẫn bắt gói tin Wireshark (UDP broadcast `:9999`, TCP 3-way handshake, khung `MSG\|`/`FILE\|`/`BYE\|`). | `docs/demo_script.md` | **Hoàn thành (tài liệu)** |
| 7 | Chụp ảnh màn hình Wireshark thực tế & chạy Demo end-to-end trên 2+ máy LAN. | *(Thao tác thủ công)* | **Chờ ghép code A & B** |

> **Lưu ý về phạm vi mã nguồn:** Phân hệ của Thành viên A (`core/`) và Thành viên B (`network/`) được giữ nguyên trạng (không chỉnh sửa bất kỳ dòng nào) để tuân thủ ranh giới phân công và tránh Merge Conflict khi nhóm ghép nhánh.

---

## 2. Quyết định Thiết kế & Hợp đồng Tích hợp với Thành viên A, B

Để code của Thành viên C ghép khớp ngay với Thành viên A và Thành viên B mà không cần sửa lại, các quy ước sau đã được thống nhất và tuân thủ chặt chẽ:

1. **Giữ nguyên 100% chữ ký hàm (Interface Contract) trong `docs/overview.md` mục 4:**
   - Gọi đúng các phương thức của `SharedState` (`get_my_info`, `set_my_status`, `get_online_peers`, `find_peer`, `set_active_chat`, `get_active_chat`, `append_message`, `get_unread_count`), `UDPDiscoveryService` (`start`, `stop`, `send_immediate_broadcast`), và `TCPConnectionManager` (`start_server`, `connect_to_peer`, `send_text_message`, `send_file_async`, `disconnect_peer`, `stop_all`).
   - Giữ nguyên 5 signal gốc của `AppSignals`: `peer_list_updated`, `system_notification`, `chat_message_received`, `file_progress_updated`, `peer_disconnected`.
2. **Phân định rõ trách nhiệm lưu tin nhắn & phát thông báo `unread`:**
   - **Tin nhắn do chính mình gửi:** Khi `tcp_manager.send_text_message(peer_id, text)` trả `True`, `CommandParser` tạo `ChatMessage(sender_name=my_name, sender_id="SELF", content=text)`, gọi `shared_state.append_message(peer_id, message)` rồi phát `signals.chat_message_received.emit(peer_id, message)` để GUI hiển thị. Thành viên B chỉ cần lo đóng gói và gửi byte qua socket.
   - **Thông báo tin nhắn chưa đọc:** Khi nhận tin từ peer không phải `active_chat`, Thread 5 (Thành viên B) gọi `append_message(...)` (làm tăng `unread_count`) và phát `signals.system_notification.emit("[*] New message from <Tên> (<n> unread)")` + `signals.peer_list_updated.emit()`. Phía `MainWindow` của C chỉ cập nhật badge đỏ trên Sidebar (không tự in thêm dòng thông báo thứ hai để tránh in trùng).
3. **Mở rộng tương thích ngược trong `AppSignals`:**
   - Thêm 2 signal nội bộ của phân hệ C (`active_chat_changed` và `my_status_changed`) — A và B không cần gọi 2 signal này.
   - Quy ước bổ sung cho `file_progress_updated(peer_id, filename, percentage)`: nếu Thành viên B phát `percentage < 0` khi truyền file bị lỗi/hủy, GUI sẽ tự động hiển thị trạng thái `failed` rồi ẩn thanh tiến độ.

---

## 3. Chi tiết Triển khai từng Tệp

### 3.1. `ui/qt_signals.py` – Cầu nối Tín hiệu Đa luồng (`AppSignals`)
- Kế thừa `QObject` và được khởi tạo trên **Main Thread (Thread 1)**.
- Khi các luồng nền (Thread 2–6 của A và B) gọi `signals.<tên>.emit(...)`, Qt tự động áp dụng `Qt.QueuedConnection`, đưa dữ liệu vào hàng đợi sự kiện (event queue) của Main Thread. Nhờ đó các widget PySide6 chỉ bao giờ được cập nhật trên Main Thread, loại bỏ hoàn toàn nguy cơ race condition hoặc crash GUI.
- Đầy đủ 7 tín hiệu:
  - 5 tín hiệu hợp đồng cho A/B: `peer_list_updated()`, `system_notification(str)`, `chat_message_received(str, object)`, `file_progress_updated(str, str, int)`, `peer_disconnected(str, str)`.
  - 2 tín hiệu nội bộ C: `active_chat_changed(object, object, int)`, `my_status_changed(str)`.

### 3.2. `ui/command_parser.py` – Bộ Phân tích Lệnh (`CommandParser`)
- **Bảng điều phối lệnh (`self._commands`):** Chuẩn hóa không phân biệt hoa/thường cho tên lệnh, tách tối đa 1 khoảng trắng (`text.split(maxsplit=1)`) để giữ nguyên phần tham số phía sau (kể cả đường dẫn file có nhiều dấu cách).
- **Chi tiết 7 lệnh và tin nhắn thường:**
  - `/list` (`_cmd_list`): Đọc `shared_state.get_online_peers()`, căn cột thẳng hàng bằng `ljust`, hiển thị số thứ tự 1-based (khớp trực tiếp với `/chat <number>`), tên, `ip:port`, trạng thái (`online`/`away`), đánh dấu `<- chatting` và `<n> unread`.
  - `/chat <name|number>` (`_cmd_chat`): Tìm peer bằng `shared_state.find_peer(target)`, kiểm tra nếu đang chat sẵn với người đó thì báo lại, gọi `tcp_manager.connect_to_peer(peer)`. Nếu thành công: lấy `unread` trước khi reset, gọi `set_active_chat(peer.peer_id)` nhận toàn bộ lịch sử, phát `active_chat_changed` và `peer_list_updated`. Không đóng kết nối với peer cũ để vẫn nhận được tin và đếm `unread`.
  - `/send <file>` (`_cmd_send`): Bóc dấu ngoặc bao ngoài bằng `_strip_quotes()` (không dùng `shlex.split` chế độ POSIX để giữ nguyên dấu gạch chéo ngược `\` của đường dẫn Windows), kiểm tra đang có `active_chat`, kiểm tra `os.path.isfile(path)`, định dạng dung lượng bằng `format_size()` (`B`/`KB`/`MB`/`GB`), báo trạng thái rồi gọi `tcp_manager.send_file_async(peer.peer_id, path)`.
  - `/leave` (`_cmd_leave`): Kiểm tra đang có `active_chat`, gọi `tcp_manager.disconnect_peer(peer.peer_id)`, đặt `set_active_chat(None)` và phát `active_chat_changed(None, [], 0)`.
  - `/status <online|away>` (`_cmd_status`): Kiểm tra thuộc `("online", "away")`, cập nhật `shared_state.set_my_status(status)`, gọi ngay `udp_service.send_immediate_broadcast()` để peer khác thấy tức thì không phải đợi chu kỳ 3s, và phát `my_status_changed` để đồng bộ ComboBox trên GUI.
  - `/help` (`_cmd_help`): In bảng hướng dẫn đầy đủ 7 lệnh kèm gợi ý dùng chuột.
  - `/quit` (`_cmd_quit`): Thông báo đóng kết nối, gọi `shutdown()`, sau đó gọi `on_quit_callback()` (`app.quit`).
  - **Văn bản thường** (`_send_chat_text`): Yêu cầu có `active_chat`; nếu `send_text_message()` trả `True` thì lưu `ChatMessage(..., sender_id="SELF")` vào `SharedState` và phát `chat_message_received`; nếu trả `False` thì báo lỗi và không ghi giả vào lịch sử.
- **Độ ổn định & Dọn dẹp:**
  - Hàm bao `_guarded()` bắt mọi ngoại lệ phát sinh từ tầng dưới (A/B) và hiển thị dưới dạng `[!] Error while running ...` thay vì làm văng cửa sổ GUI.
  - Phương thức `shutdown()` đảm bảo **idempotent** (chỉ gọi `udp_service.stop()` và `tcp_manager.stop_all()` đúng 1 lần dù bị kích hoạt từ `/quit`, nút `X` trên cửa sổ, hay sau `app.exec()`).

### 3.3. `ui/main_window.py` – Giao diện PySide6 (`MainWindow`, Thread 1)
- **Giải quyết triệt để bài toán "Typing while messages arrive":**
  - Vùng hiển thị lịch sử (`QTextEdit`, chế độ chỉ đọc `setReadOnly(True)`, giới hạn `MAX_CHAT_BLOCKS = 5000` dòng) tách biệt hoàn toàn với ô nhập liệu (`HistoryLineEdit` kế thừa `QLineEdit`).
  - Khi tin nhắn hoặc thông báo hệ thống đến từ luồng nền, các slot chỉ gọi `_append_html()` vào `QTextEdit` (chỉ tự cuộn xuống cuối nếu người dùng đang ở cuối, không giật màn hình khi đang kéo lên đọc tin cũ) và không chạm tới text, con trỏ hay focus của `message_input`.
- **Các thành phần UI đã xây dựng:**
  - `HistoryLineEdit`: Hỗ trợ phím mũi tên **Lên / Xuống** để gọi lại tối đa 100 dòng tin nhắn/lệnh đã gửi trước đó (giữ lại bản nháp đang gõ dở khi quay xuống cuối).
  - `PeerItemWidget`: Mỗi dòng trên Sidebar gồm chấm tròn màu trạng thái bằng CSS (`#2ecc71` xanh lá cho `online`, `#f39c12` vàng cam cho `away`), số thứ tự + tên (in đậm khi đang chat hoặc có tin chưa đọc), địa chỉ `ip:port`, nhãn `chat` màu xanh cho người đang chat và badge đỏ đếm số tin chưa đọc (hiển thị `99+` nếu vượt quá 99).
  - **Đồng bộ 2 chiều chuột ↔ lệnh:** Click vào peer trên Sidebar gọi `/chat <peer_id>`; bấm **`Send File...`** mở `QFileDialog` rồi gọi `/send "<filepath>"`; đổi `QComboBox` trạng thái gọi `/status <online|away>`; bấm **`Leave (/leave)`** gọi `/leave`. Ngược lại, gõ `/status` cập nhật ngược `QComboBox` (có cờ `_syncing_status` chống lặp tín hiệu).
  - **Chuyển cuộc trò chuyện & vạch chưa đọc:** `on_active_chat_changed` xóa khung chat, dựng lại lịch sử của peer mới, chèn đường ngăn màu đỏ `──── <n> unread ────` đúng trước tin chưa đọc đầu tiên và dùng tập `_rendered_message_ids` chống vẽ lặp nếu có tín hiệu tới trễ trong hàng đợi sự kiện.
  - **Thanh tiến độ truyền file (`on_file_progress_updated`):** Theo dõi đồng thời nhiều lượt truyền file bằng `self._transfers[(peer_id, filename)]`; hiển thị tên file, tên peer, `%` và `(+k more)` nếu đang truyền song song nhiều file; khi đạt `100%` thì ghi dòng xác nhận `[*] <file> ↔ <peer> ... 100%  Done.` và tự ẩn sau 2 giây (bằng `QTimer`).
  - **Xử lý ngắt kết nối (`on_peer_disconnected`) & đóng cửa sổ (`closeEvent`):** Khi peer ngắt kết nối (đột ngột hoặc `BYE|`), hủy trạng thái progress của peer đó, báo nguyên nhân và nếu là active chat thì tự đưa khung chat về trạng thái chờ + khóa nút `Leave` và `Send File...`. Khi bấm nút `X`, `closeEvent` dừng timer và gọi `command_parser.shutdown()`.
- **Các lỗi tinh tế đã phát hiện và khắc phục trong quá trình tự kiểm thử:**
  1. *Crash `Internal C++ object (QListWidgetItem) already deleted` khi click Sidebar:* Do `itemClicked` gọi `/chat` → `on_peer_list_updated()` gọi `peer_list_widget.clear()` ngay trong lúc Qt còn đang xử lý sự kiện chuột trên chính item vừa click. **Cách sửa:** Hoãn lời gọi sang vòng lặp sự kiện kế tiếp bằng `QTimer.singleShot(0, ...)` kèm biến `_pending_sidebar_peer_id` chống kích hoạt đúp; nếu kết nối thất bại thì tự gọi `on_peer_list_updated()` để trả vùng chọn về đúng peer đang chat.
  2. *Thanh cuộn ngang trên Sidebar che mất badge đỏ:* Khi chụp ảnh kiểm tra giao diện thực tế, `item.setSizeHint(row_widget.sizeHint())` khiến item rộng hơn viewport của Sidebar và sinh thanh cuộn ngang. **Cách sửa:** Đặt `setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)`, `item.setSizeHint(QSize(0, max(44, row_widget.sizeHint().height())))` và đặt `QSizePolicy.Ignored` cho nhãn tên/địa chỉ để badge đỏ luôn ghim gọn ở mép phải.
  3. *Hỗ trợ đường dẫn Windows có dấu `\` trong `/send`:* Thay `shlex.split(..., posix=True)` bằng bóc ngoặc thuần trong `_strip_quotes()` để tránh mất ký tự `\` trên Windows.

### 3.4. `main.py` – Entry Point & Tích hợp
- Bổ sung kiểm tra hợp lệ tham số dòng lệnh ngay khi khởi chạy:
  - `--port` và `--udp-port`: phải là số nguyên trong khoảng `1..65535` (`_valid_port`).
  - `--name`: không được rỗng, không chứa dấu `|` (ký tự phân tách giao thức) hay ký tự xuống dòng, tối đa 32 ký tự (`_valid_name`).
- Truyền `sys.argv[:1]` vào `QApplication` để các tham số riêng của ứng dụng không xung đột với tham số nội bộ của Qt.
- Tự động tạo thư mục `downloads/` theo đường dẫn tuyệt đối dựa trên vị trí `main.py` (`BASE_DIR`).
- Bọc `tcp_manager.start_server()` và `udp_service.start()` trong `try ... except OSError`: nếu cổng TCP đã bị chiếm (ví dụ `WinError 10048`), hiện hộp thoại `QMessageBox.critical` giải thích rõ, gọi `command_parser.shutdown()` và thoát với mã `1`.
- Bổ sung `_install_ctrl_c_handler(app)` (bắt `SIGINT` kết hợp `QTimer` 300ms) để nhấn `Ctrl+C` trong terminal vẫn đóng cửa sổ và dọn sạch socket tương tự `/quit`.

### 3.5. `tests/mock_c_ui.py` – Bộ Kiểm thử Độc lập cho Thành viên C
- Cung cấp đầy đủ mock khớp hợp đồng của A và B:
  - `MockSharedState` (dùng `threading.RLock`), `MockUDPService`, `MockTCPManager` (có `Ghost` giả lập từ chối kết nối, tự trả lời tin nhắn, giả lập Thread 6 truyền file theo từng bước 5%), và `FakeNetworkThread` (luồng nền thật bắn tin nhắn mỗi giây, đổi trạng thái `online`/`away`, giả lập peer `Tuan` ra/vào).
- Hỗ trợ 2 chế độ chạy:
  - **Chế độ tương tác:** `.\.venv\Scripts\python.exe -m tests.mock_c_ui` — mở cửa sổ PySide6 thật để bạn gõ thử và kiểm chứng bằng mắt việc không vỡ chữ khi tin nhắn đổ về mỗi giây.
  - **Chế độ tự động (headless):** `.\.venv\Scripts\python.exe -m tests.mock_c_ui --selftest` — chạy 33 kịch bản kiểm thử tự động trong chế độ `QT_QPA_PLATFORM=offscreen`.

### 3.6. `docs/demo_script.md` – Kịch bản Demo 10 phút & Hướng dẫn Wireshark
- Hướng dẫn chuẩn bị môi trường Windows (mở Firewall cổng UDP `9999` và TCP `5000–5010`, xử lý AP Isolation bằng Mobile Hotspot, tạo file 50MB bằng `fsutil`, phương án dự phòng 3 instance trên 1 máy).
- Hướng dẫn chi tiết chụp 4 ảnh Wireshark (chọn card mạng Wi-Fi hoặc Loopback, Display Filter chính xác cho từng loại gói, điểm cần chỉ rõ trên ảnh và đoạn giải thích mẫu sẵn sàng đưa vào báo cáo môn học).
- Kịch bản trình bày Live Demo 10 phút chia 6 mốc thời gian khớp 100% tiêu chí trong Grading Rubric của `docs/plan.md`, kèm 3 câu hỏi Q&A trọng tâm về phần của Thành viên C.

---

## 4. Kết quả Kiểm thử (Verification)

Tất cả các bài kiểm thử dưới đây đã được chạy thực tế trên máy trong môi trường ảo `.venv` (Python 3.15.2, PySide6 6.12.0):

### 4.1. Biên dịch cú pháp (`py_compile`)
- Lệnh: `.\.venv\Scripts\python.exe -m py_compile main.py ui\main_window.py ui\command_parser.py ui\qt_signals.py tests\mock_c_ui.py`
- **Kết quả:** Thoát mã `0`, không có lỗi cú pháp.

### 4.2. Kiểm thử tự động giao diện & lệnh (`tests/mock_c_ui.py --selftest`)
- Lệnh: `.\.venv\Scripts\python.exe -m tests.mock_c_ui --selftest`
- **Kết quả:** **33/33 PASS** (thoát mã `0`), bao phủ các nhóm:
  - **Hiển thị Sidebar & Discovery:** hiển thị đủ 4 peer ban đầu, đồng bộ số thứ tự và trạng thái `online`/`away`, cập nhật badge đỏ số `2` khi `Huy` gửi 2 tin ở luồng nền.
  - **Không vỡ chữ khi gõ (`Typing while messages arrive`):** đặt chữ `"you can che"` với con trỏ ở vị trí `7`, bắn liên tiếp 20 tin nhắn từ luồng nền (`threading.Thread`) → chữ và vị trí con trỏ vẫn giữ nguyên `"you can che" @ 7`, đồng thời cả 20 tin nhắn hiển thị tức thì trong khung chat.
  - **Đầy đủ 7 lệnh & tin nhắn thường:** `/help`, `/list`, `/chat 1`, `/chat Huy`, `/chat huy` (đang chat sẵn), `/chat Ghost` (từ chối kết nối), `/chat Nobody` (không tồn tại), `/chat` thiếu tham số, gửi tin nhắn tiếng Việt có dấu (lưu `SELF` vào lịch sử và hiển thị), gửi lỗi không lưu giả, `/status away`, `/status busy` (báo lỗi), đổi trạng thái bằng ComboBox, `/send` file không tồn tại, `/send` đường dẫn có dấu cách trong ngoặc kép (hiện `QProgressBar`, chạy tới `100% Done`, tự ẩn sau khi xong), `/leave` (cả lúc đang chat và lúc không chat), `/quit` (dừng UDP & TCP đúng 1 lần kể cả khi đóng cửa sổ sau đó).
  - **Thao tác chuột & Xử lý lỗi:** click peer trên Sidebar mở chat giống `/chat`, nhận `peer_disconnected` từ luồng nền đóng phiên chat và vô hiệu hóa nút gửi file, lệnh lạ `/foo bar` hiện trợ giúp ngắn, ngoại lệ `RuntimeError` từ tầng mạng bị chặn an toàn và in thông báo lỗi lên khung chat.

### 4.3. Kiểm thử `main.py` (Smoke test & CLI Validation)
- **Khởi chạy `main.py`:** Chạy `main(["--name", "Quan", "--port", "5001", "--broadcast", "127.255.255.255"])` ở chế độ `offscreen`, hiển thị `MainWindow`, tự thoát sạch sau 1.5s → **exit code `0`**.
- **Kiểm tra từ chối tham số không hợp lệ:** 6/6 trường hợp lỗi (`--name "Bad|Name"`, `--name "   "`, tên dài 33 ký tự, `--port 0`, `--port 70000`, `--udp-port abc`) đều bị từ chối với **exit code `2`** và thông báo lỗi rõ ràng.

### 4.4. Kiểm tra trực quan giao diện
- Đã chụp ảnh render thực tế của `MainWindow` với font Windows (`QT_QPA_FONTDIR=C:\Windows\Fonts`) ở trạng thái có 4 peer (`online`/`away`), 1 peer đang active (`Minh`, nhãn `chat`), 1 peer có 2 tin chưa đọc (`Huy`, badge đỏ `2`), tin nhắn tiếng Việt UTF-8, thanh `QProgressBar` tại `45%`, và chuỗi gõ dở `"you can che"` trong ô nhập liệu. Bố cục cân đối, không có thanh cuộn ngang, chữ tiếng Việt hiển thị sắc nét.

### 4.5. Cách bạn tự chạy thử giao diện tương tác trên máy
```powershell
.\.venv\Scripts\python.exe -m tests.mock_c_ui
```
Khi cửa sổ mở ra, một luồng nền sẽ bắn tin nhắn ngẫu nhiên mỗi 1 giây. Hãy thử gõ chậm một câu dài trong ô nhập liệu, click các peer trên Sidebar, bấm `Send File...`, đổi ComboBox trạng thái và gõ thử 7 lệnh `/list`, `/chat`, `/send`, `/leave`, `/status`, `/help`, `/quit`.

---

## 5. Việc cần làm tiếp theo (thủ công / sau khi ghép code với A & B)

Phần việc của Thành viên C đã hoàn tất về mặt mã nguồn, kiểm thử độc lập và tài liệu kịch bản. Các bước sau cần bạn tự thực hiện khi Thành viên A và Thành viên B xong phần của họ:

- [ ] **Ghép nhánh (Merge):** Sau khi nhánh `feat/a-udp-discovery` và `feat/b-tcp-framing` hoàn thành, ghép `feat/c-pyside6-ui` vào `develop` (và `main` khi đạt checkpoint).
- [ ] **Chạy kiểm thử tích hợp end-to-end:** Mở 3 peer trên 1 máy bằng cấu hình `Launch 3 Peers on 1 PC (Quan, Minh, Huy)` trong VS Code (`F5`), kiểm tra thực tế UDP Discovery 3s / timeout 10s, chat 2 chiều + `unread`, truyền file lớn 50MB song song với chat và xóa partial file khi tắt ngang.
- [ ] **Chụp ảnh màn hình Wireshark thực tế:** Làm theo từng bước trong `docs/demo_script.md` (Phần 2) để chụp đủ 4 ảnh gói tin thật (`udp.port == 9999`, TCP 3-way handshake, khung `MSG|` tiếng Việt UTF-8, `FILE|`/`BYE|`) đưa vào báo cáo nộp môn.
- [ ] **Diễn tập Live Demo 10 phút trên 2 máy LAN:** Thực hiện theo checklist và bảng mốc thời gian trong `docs/demo_script.md` (Phần 1 & Phần 3).
- [ ] **Push nhánh lên GitHub:** Khi sẵn sàng chia sẻ với nhóm, chạy `git push -u origin feat/c-pyside6-ui` trong terminal của bạn.
