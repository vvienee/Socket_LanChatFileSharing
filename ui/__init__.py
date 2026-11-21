"""
Package ui: Phụ trách bởi Thành viên C.
Bao gồm:
- qt_signals.py: Cầu nối tín hiệu Thread-safe (Qt Signals) từ các luồng mạng (A, B) lên giao diện PySide6.
- command_parser.py: Bộ phân tích các lệnh /list, /chat, /send, /leave, /status, /help, /quit.
- main_window.py: Giao diện người dùng chính bằng PySide6 (Thread 1 - Main UI Thread).
"""
