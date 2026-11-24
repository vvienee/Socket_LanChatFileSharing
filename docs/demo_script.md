# Hướng dẫn Chụp Gói tin Wireshark & Kịch bản Live Demo (10 phút)

**Phụ trách biên soạn:** Thành viên C  
**Dự án:** LAN Chat & File Sharing (P2P TCP/UDP Sockets + PySide6 GUI)  
**Tham chiếu yêu cầu:** `docs/plan.md` (Mục 7 – Deliverables & Mục 8 – Grading Rubric) và `docs/overview.md` (Mục 6 & 7)

> **Lưu ý quan trọng:** Các bước chụp ảnh Wireshark và chạy Demo dưới đây cần thực hiện **sau khi Thành viên A (`core/`) và Thành viên B (`network/`) đã hoàn thiện và ghép code cùng nhánh của Thành viên C**. Trước khi ghép code, bạn vẫn có thể chạy thử riêng giao diện của Thành viên C bằng `python -m tests.mock_c_ui`.

---

## Phần 1. Checklist chuẩn bị trước khi Demo & Bắt gói tin

Thực hiện trước buổi báo cáo ít nhất 30 phút để tránh sự cố môi trường:

1. **Môi trường mạng (khuyên dùng 2+ laptop cùng Wi-Fi/LAN hoặc phát Hotspot từ 1 laptop):**
   - Kiểm tra IP từng máy bằng `ipconfig` (cả hai máy phải cùng subnet, ví dụ `192.168.1.x`).
   - Lưu ý: Một số Wi-Fi công cộng/trường học bật **AP Isolation** (chặn gói UDP Broadcast và chặn kết nối trực tiếp giữa các máy). Nếu gặp tình trạng không thấy nhau, hãy dùng **Mobile Hotspot** từ điện thoại hoặc 1 laptop để làm mạng LAN demo.
2. **Cấu hình Windows Firewall (chạy PowerShell bằng quyền Administrator trên mỗi máy):**
   ```powershell
   New-NetFirewallRule -DisplayName "LAN Chat UDP 9999" -Direction Inbound -Protocol UDP -LocalPort 9999 -Action Allow
   New-NetFirewallRule -DisplayName "LAN Chat TCP Ports" -Direction Inbound -Protocol TCP -LocalPort 5000-5010 -Action Allow
   ```
3. **Chuẩn bị file mẫu để truyền file:**
   - 1 file vừa (~2–5 MB, ví dụ `slides.pdf`) để demo truyền file nhanh và kiểm tra file nhận được mở bình thường.
   - 1 file lớn (~30–80 MB, ví dụ `demo_video.mp4` hoặc tạo nhanh file giả trên PowerShell) để demo **vừa truyền file vừa chat không vỡ chữ** và demo **ngắt kết nối giữa chừng xóa partial file**:
     ```powershell
     fsutil file createnew test_50mb.bin 52428800
     ```
4. **Dọn sạch thư mục `downloads/`** (chỉ giữ lại `.gitkeep`) để lúc demo thấy rõ file mới được lưu vào và partial file bị xóa khi lỗi.
5. **Kiểm tra phương án dự phòng trên 1 máy (3 instance Windows):**
   - Mở VS Code → `Ctrl+Shift+D` → chọn **`Launch 3 Peers on 1 PC (Quan, Minh, Huy)`** → nhấn `F5`.
   - Hoặc mở 3 cửa sổ PowerShell đã kích hoạt `.venv`:
     ```powershell
     python main.py --name Quan --port 5001 --broadcast 127.255.255.255
     python main.py --name Minh --port 5002 --broadcast 127.255.255.255
     python main.py --name Huy  --port 5003 --broadcast 127.255.255.255
     ```

---

## Phần 2. Hướng dẫn Chụp ảnh Wireshark cho Báo cáo cuối kỳ

Đề bài (`docs/plan.md` mục 7.3) yêu cầu:
> *"Wireshark screenshots showing the UDP broadcast packets and the TCP three-way handshake, with a short explanation."*

### Bước 1: Chọn đúng Card mạng (Capture Interface)
- **Khi chạy trên 2 máy qua Wi-Fi/LAN:** Chọn giao diện **Wi-Fi** hoặc **Ethernet** (card đang có lưu lượng nhấp nhô).
- **Khi chạy nhiều instance trên cùng 1 máy Windows:** Cài đặt Npcap (tích chọn *"Support loopback traffic"* khi cài Wireshark), sau đó chọn **Adapter for loopback traffic capture**.

### Bước 2: Các ảnh màn hình bắt buộc cần chụp & Bộ lọc (Display Filter)

Hãy chụp đủ **4 ảnh** sau (để nguyên khung danh sách gói tin + khung chi tiết tầng giao vận + khung dữ liệu hex/ASCII ở dưới):

#### Ảnh 1 – Gói tin UDP Discovery Broadcast (`HELLO|...`)
- **Display Filter:**
  ```text
  udp.port == 9999
  ```
- **Thao tác lúc bắt gói:** Mở 2 peer `Quan` (`--port 5001`) và `Minh` (`--port 5002`), đợi khoảng 6–9 giây rồi gõ `/status away` trên máy Quan.
- **Cần nhìn rõ trên ảnh:**
  - Cột `Source` là IP máy gửi, cột `Destination` là `255.255.255.255` (hoặc `127.255.255.255` nếu loopback).
  - Khoảng thời gian (`Time`) giữa các gói liên tiếp của cùng 1 máy xấp xỉ **3.0 giây**, riêng lúc đổi `/status away` có 1 gói phát ngay lập tức.
  - Ở khung chi tiết phía dưới (**Data**): chuỗi ASCII hiện rõ `HELLO|Quan|5001|online` và `HELLO|Quan|5001|away`.
- **Gợi ý lời giải thích ngắn kèm ảnh:**
  > Mỗi peer phát định kỳ 3 giây một datagram UDP không kết nối tới cổng `9999` địa chỉ broadcast mang thông điệp `HELLO|<name>|<tcp_port>|<status>`. Việc dùng UDP cho phép mọi máy trong mạng LAN tự khám phá nhau mà không cần server trung tâm; nếu mất 1 gói thì gói sau (3 giây nữa) sẽ tự bù, và quá 10 giây không nhận được gói nào thì peer bị xóa khỏi danh sách online.

#### Ảnh 2 – Bắt tay 3 bước TCP (TCP Three-Way Handshake)
- **Display Filter:**
  ```text
  tcp.port == 5002
  ```
  *(Thay `5002` bằng cổng `--port` của máy được kết nối tới, ví dụ Minh chạy `--port 5002`.)*
- **Thao tác lúc bắt gói:** Trên máy Quan, gõ `/chat Minh` (hoặc click vào tên Minh trên Sidebar).
- **Cần nhìn rõ trên ảnh:** 3 gói tin đầu tiên ngay khi kết nối:
  1. `Quan -> Minh`: cờ `[SYN]`, `Seq=0`
  2. `Minh -> Quan`: cờ `[SYN, ACK]`, `Seq=0 Ack=1`
  3. `Quan -> Minh`: cờ `[ACK]`, `Seq=1 Ack=1`
- **Gợi ý lời giải thích ngắn kèm ảnh:**
  > Khi Quan mở phiên chat với Minh, TCP thực hiện bắt tay 3 bước (`SYN` → `SYN, ACK` → `ACK`) từ cổng tạm (ephemeral port) của Quan tới cổng lắng nghe TCP `5002` của Minh. Kênh TCP đáng tin cậy, đúng thứ tự này sẽ được giữ mở để truyền cả tin nhắn chat và file nhị phân.

#### Ảnh 3 – Khung đóng gói tin nhắn TCP (`MSG|<length>|<utf-8 text>`)
- **Display Filter:**
  ```text
  tcp.port == 5002 and tcp.len > 0
  ```
- **Thao tác lúc bắt gói:** Quan gửi 1 tin nhắn tiếng Việt có dấu (ví dụ: `Xin chào Minh`) để chứng minh `<length>` là số **byte UTF-8**, không phải số ký tự.
- **Cách chụp rõ nhất:** Chuột phải vào gói `PSH, ACK` chứa tin nhắn → chọn **Follow → TCP Stream** (chọn hiển thị **ASCII** hoặc **UTF-8**) hoặc mở rộng mục **Data** ở khung chi tiết gói tin.
- **Cần nhìn rõ trên ảnh:** Chuỗi payload bắt đầu bằng `MSG|14|Xin chào Minh` (`"Xin chào Minh".encode("utf-8")` dài 14 bytes dù chỉ có 13 ký tự).
- **Gợi ý lời giải thích ngắn kèm ảnh:**
  > Vì TCP là dòng byte liên tục (byte stream) không có ranh giới gói tin, ứng dụng dùng giao thức tự định nghĩa `MSG|<byte_length>|<utf-8 payload>`. Bên nhận đọc tiêu đề tới dấu `|` thứ hai, sau đó gọi `recv_exact(byte_length)` để ghép đủ byte tránh dính/cắt gói tin và bảo đảm hiển thị đúng tiếng Việt UTF-8.

#### Ảnh 4 (Khuyến khích chụp thêm) – Truyền file (`FILE|...`) và đóng kết nối (`BYE|`)
- **Display Filter:** `tcp.port == 5002 and (tcp.len > 0 or tcp.flags.fin == 1)`
- **Thao tác lúc bắt gói:** Quan gửi `/send slides.pdf`, đợi đạt 100%, sau đó gõ `/leave`.
- **Cần nhìn rõ trên ảnh:**
  - Gói đầu của lượt truyền file chứa header `FILE|slides.pdf|<filesize>|` tiếp theo là các segment dữ liệu TCP liên tiếp (và có thể thấy tin nhắn `MSG|...` xen kẽ nếu chat song song).
  - Khi `/leave`, xuất hiện gói chứa `BYE|` theo sau là cặp `FIN, ACK` đóng kết nối TCP lịch sự.

---

## Phần 3. Kịch bản Live Demo 10 phút (Khớp Grading Rubric 100%)

**Thiết lập khuyến nghị:** 2 laptop (`Quan` cổng `5001`, `Minh` cổng `5002`) + 1 cửa sổ phụ `Huy` (`5003`) chạy trên một trong hai máy để biểu diễn kịch bản nhiều peer và tin nhắn chưa đọc (`unread`).

| Thời lượng | Mốc Demo | Thao tác trực tiếp & Lệnh gõ | Kết quả cần chỉ cho Giảng viên xem | Tiêu chí Rubric |
| :---: | :--- | :--- | :--- | :--- |
| **0:00 – 1:00** | **1. Giới thiệu kiến trúc** | Mở ứng dụng trên 2 máy (`Quan`, `Minh`) + instance thứ 3 (`Huy`). | Giải thích nhanh: P2P không có server trung tâm; UDP `:9999` khám phá peer, TCP `--port` chat & gửi file; 6 luồng + PySide6 `AppSignals`. | Kiến trúc & chất lượng demo (5%) |
| **1:00 – 2:30** | **2. UDP Discovery & Online Status** | - Trên Quan: gõ `/list`.<br>- Trên Minh: gõ `/status away` (hoặc đổi ComboBox trên Sidebar).<br>- Tắt cửa sổ `Huy` (nhấn nút `X` hoặc `/quit`). | - Trong vòng ≤ 3s, 3 peer tự thấy nhau trên Sidebar và lệnh `/list` (có số thứ tự, IP, port, status).<br>- Khi Minh đổi `away`, chấm màu trên máy Quan đổi ngay sang màu vàng (nhờ immediate broadcast) mà không phải đợi 3s.<br>- Sau **10 giây** kể từ khi tắt Huy, thông báo `[*] Huy went offline` hiện lên và Huy biến mất khỏi danh sách. | UDP discovery, online list, status (15%) |
| **2:30 – 4:30** | **3. TCP Chat 2 chiều & Unread Counter (Nhiều Peer)** | - Mở lại `Huy`.<br>- Trên Quan: gõ `/chat 1` (hoặc click `Minh` trên Sidebar).<br>- Quan và Minh nhắn qua lại nhiều dòng liên tiếp (kèm tiếng Việt có dấu).<br>- Lúc Quan đang chat với Minh, trên cửa sổ `Huy` nhắn 2 tin tới Quan.<br>- Trên Quan: gõ `/chat Huy` (hoặc click `Huy`). | - Hai bên chat 2 chiều tức thì, không mất tin, không lỗi tiếng Việt UTF-8.<br>- Tin từ Huy KHÔNG nhảy vào khung chat của Minh; thay vào đó hiện thông báo `[*] New message from Huy (1 unread)` → `(2 unread)` và **badge đỏ số `2`** cạnh tên Huy trên Sidebar.<br>- Khi chuyển sang Huy, badge về `0`, toàn bộ 2 tin chưa đọc hiển thị kèm vạch ngăn `──── 2 unread ────`. | TCP chat nhiều peer (20%) & Framing (10%) |
| **4:30 – 6:30** | **4. Gõ tin không bị vỡ chữ & Truyền file song song** | - Trên Quan (đang chat với Minh): gõ dở một câu dài trong ô Input (chưa nhấn Enter, để con trỏ ở giữa câu).<br>- Minh gửi liên tiếp 3–4 tin nhắn.<br>- Quan bấm nút **`Send File...`** (hoặc `/send test_50mb.bin`) chọn file 50MB.<br>- Trong lúc thanh `QProgressBar` đang chạy %, Quan và Minh **tiếp tục gõ và nhận tin nhắn chat**. | - Câu đang gõ dở và vị trí con trỏ trong ô nhập liệu giữ nguyên 100%, không bị chèn hay xóa.<br>- Thanh `QProgressBar` hiện rõ tên file, tên người nhận và `%` tăng đều tới `100% Done` rồi tự ẩn.<br>- Chat vẫn mượt trong suốt lúc truyền file (chứng minh Thread 6 tách khỏi Thread 1 và không nghẽn chat).<br>- Mở thư mục `downloads/` trên máy Minh: file đã lưu đúng tên, đúng dung lượng (mở thử `slides.pdf` để xác nhận không hỏng dữ liệu). | File transfer + progress (15%) & UI không vỡ chữ (15%) |
| **6:30 – 8:30** | **5. Xử lý lỗi & Độ ổn định (Error Handling)** | Thực hiện lần lượt 4 tình huống lỗi:<br>1. Gõ lệnh sai `/abc` và `/chat` thiếu tham số.<br>2. Gửi file không tồn tại `/send khong_co.pdf`.<br>3. Bắt đầu gửi file 50MB rồi **tắt đột ngột** cửa sổ bên gửi giữa chừng (khi đang ở ~30%).<br>4. Gõ `/chat` tới peer vừa tắt (trước khi hết timeout 10s). | 1. Hiện cảnh báo `[!] Unknown command` / hướng dẫn ngắn, không crash.<br>2. Báo `[!] File not found`, không mở luồng lỗi.<br>3. Bên nhận hiện thông báo ngắt kết nối, **tự động xóa file lỗi (partial file)** trong `downloads/`, giao diện quay về trạng thái chờ.<br>4. Báo `[!] Could not connect to ...`, ứng dụng vẫn ổn định. | Error handling & stability (10%) |
| **8:30 – 10:00** | **6. Kết thúc & Hỏi đáp (Q&A)** | - Gõ `/leave` để đóng phiên chat lịch sự (`BYE|`), sau đó `/quit` để thoát sạch.<br>- Mở sẵn ảnh Wireshark (hoặc mở Wireshark live) nếu giảng viên hỏi về framing/handshake. | Toàn bộ socket và luồng daemon đóng gọn, không còn tiến trình treo. Sẵn sàng trả lời câu hỏi về `RLock`, `recv_exact()`, `QueuedConnection`, UDP vs TCP. | Report (10%) & Demo (5%) |

---

## Phần 4. Các câu hỏi Q&A Giảng viên hay hỏi Thành viên C

1. **Tại sao giao diện PySide6 không bị vỡ chữ khi nhận tin nhắn đang gõ?**
   - Thứ nhất, khung hiển thị lịch sử (`QTextEdit` read-only) và ô nhập liệu (`HistoryLineEdit` kế thừa `QLineEdit`) là 2 widget hoàn toàn tách biệt; các slot nhận tin chỉ `append()` vào `QTextEdit` và không bao giờ thay đổi nội dung hay focus của ô nhập.
   - Thứ hai, mọi luồng nền (UDP/TCP/File) chỉ gọi `AppSignals.<signal>.emit(...)` thay vì chạm trực tiếp vào widget; Qt tự dùng cơ chế `Qt.QueuedConnection` để xếp sự kiện vào hàng đợi của Main Thread nên không xảy ra race condition hay crash GUI.
2. **Làm sao đảm bảo thao tác click chuột trên GUI và gõ slash command luôn đồng nhất?**
   - Mọi thao tác chuột (click peer trên Sidebar, chọn file từ `QFileDialog`, đổi `QComboBox` trạng thái, bấm nút `Leave`) đều được quy đổi thành chuỗi lệnh chuẩn (`/chat <peer_id>`, `/send "<path>"`, `/status <online|away>`, `/leave`) rồi đi qua duy nhất một cổng là `CommandParser.handle_user_input()`. Khi lệnh chạy từ bàn phím (như `/status away`), tín hiệu `my_status_changed` đồng bộ ngược lại `QComboBox`.
3. **Tại sao khi đổi từ chat với Minh sang Huy lại không đóng kết nối TCP với Minh?**
   - Theo yêu cầu mục 3.3 của `plan.md`, ứng dụng phải tiếp tục nhận tin nhắn từ các peer không phải active chat và tích lũy bộ đếm `unread`. Do đó `/chat <peer khác>` chỉ đổi `active_chat_peer_id` và tái sử dụng/mở kết nối mới; chỉ khi người dùng chủ động gõ `/leave` (hoặc `/quit`) mới gửi `BYE|` và đóng socket TCP của peer đó.
