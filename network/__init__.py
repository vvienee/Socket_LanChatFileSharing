"""
Package network: Phụ trách bởi Thành viên B.
Bao gồm:
- protocol.py: Thiết kế giao thức tầng ứng dụng và framing trên dòng byte TCP.
- tcp_manager.py: Quản lý kết nối TCP P2P (Thread 4 Acceptor & Thread 5 Receiver mỗi peer).
- file_transfer.py: Truyền nhận file dung lượng lớn ở luồng riêng (Thread 6 File Sender).
"""
