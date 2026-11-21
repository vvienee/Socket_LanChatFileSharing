# LAN Chat & File Sharing (TCP/UDP Sockets + PySide6 GUI)

Dự án lập trình mạng Peer-to-Peer (P2P) trong mạng LAN sử dụng thư viện `socket` và `threading` gốc của Python kết hợp giao diện đồ họa **PySide6**.

## 1. Kiến trúc & Phân công công việc

| Thành viên | Phụ trách | Thư mục / Files | Luồng (Threads) đảm nhận |
| :--- | :--- | :--- | :--- |
| **Thành viên A** | Quản lý trạng thái dùng chung (`SharedState`) & Khám phá người dùng qua UDP Broadcast | `core/models.py`<br>`core/shared_state.py`<br>`core/udp_discovery.py`<br>`tests/mock_a_discovery.py` | - **Thread 2:** UDP Broadcaster (mỗi 3s)<br>- **Thread 3:** UDP Listener (cổng 9999) + Quét timeout 10s |
| **Thành viên B** | Giao thức Framing trên TCP Stream, Chat P2P & Truyền nhận File | `network/protocol.py`<br>`network/tcp_manager.py`<br>`network/file_transfer.py`<br>`tests/mock_b_protocol.py` | - **Thread 4:** TCP Acceptor<br>- **Thread 5:** TCP Receiver (1 luồng / peer)<br>- **Thread 6:** File Sender (1 luồng / lượt truyền file) |
| **Thành viên C** | Giao diện PySide6, Cầu nối tín hiệu `AppSignals` & Bộ phân tích lệnh (`/list`, `/chat`, `/send`...) | `ui/qt_signals.py`<br>`ui/command_parser.py`<br>`ui/main_window.py`<br>`main.py`<br>`tests/mock_c_ui.py` | - **Thread 1 (Main):** Vòng lặp sự kiện GUI (`QApplication`) & Xử lý lệnh người dùng |

---

## 2. Cài đặt môi trường (Windows)

```powershell
# 1. Tạo và kích hoạt môi trường ảo (khuyên dùng)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Cài đặt thư viện giao diện PySide6
pip install -r requirements.txt
```

---

## 3. Cách chạy ứng dụng

### Chạy nhiều tiến trình trên cùng 1 máy tính Windows (Loopback Broadcast)
Mở 3 cửa sổ Terminal riêng biệt (hoặc nhấn `F5` trong VS Code với cấu hình **Launch 3 Peers on 1 PC**):

```powershell
# Terminal 1 - Quan
python main.py --name Quan --port 5001 --broadcast 127.255.255.255

# Terminal 2 - Minh
python main.py --name Minh --port 5002 --broadcast 127.255.255.255

# Terminal 3 - Huy
python main.py --name Huy --port 5003 --broadcast 127.255.255.255
```

### Chạy trên nhiều máy tính khác nhau trong cùng mạng LAN / Wi-Fi
1. Mở quyền Windows Firewall (chạy PowerShell với quyền Administrator một lần):
   ```powershell
   New-NetFirewallRule -DisplayName "LAN Chat UDP 9999" -Direction Inbound -Protocol UDP -LocalPort 9999 -Action Allow
   New-NetFirewallRule -DisplayName "LAN Chat TCP Ports" -Direction Inbound -Protocol TCP -LocalPort 5000-5010 -Action Allow
   ```
2. Khởi chạy trên từng máy:
   ```powershell
   python main.py --name Quan --port 5000
   ```

---

## 4. Danh sách các lệnh hỗ trợ trên ô nhập liệu

| Lệnh | Mô tả |
| :--- | :--- |
| `/list` | Hiển thị danh sách người dùng đang online kèm số thứ tự, tên, IP và trạng thái |
| `/chat <name\|number>` | Mở kết nối TCP và bắt đầu trò chuyện với người dùng được chọn |
| `<bất kỳ văn bản nào>` | Gửi tin nhắn văn bản tới người đang chat hiện tại |
| `/send <đường_dẫn_file>` | Gửi file tới người đang chat hiện tại (file nhận được lưu tại `downloads/`) |
| `/leave` | Đóng cuộc trò chuyện hiện tại |
| `/status <online\|away>` | Đổi trạng thái hiện diện của bản thân (cập nhật qua UDP Broadcast) |
| `/help` | Hiển thị hướng dẫn sử dụng các lệnh |
| `/quit` | Đóng tất cả kết nối và thoát chương trình |
