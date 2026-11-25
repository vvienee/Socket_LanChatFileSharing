"""
Script kiểm thử độc lập dành cho [THÀNH VIÊN A].
Dùng để test `SharedState` và `UDPDiscoveryService` trên Terminal mà không cần chờ GUI của C hay TCP của B.
Cách chạy (từ thư mục gốc dự án):
    python -m tests.mock_a_discovery --name Alice --port 5001
    python -m tests.mock_a_discovery --name Bob --port 5002
Trên 1 máy Windows nên thêm:  --broadcast 127.255.255.255
Tự kiểm tra tự động (không cần mở nhiều terminal):
    python -m tests.mock_a_discovery --selftest
Lệnh trong chương trình: list | away | online | quit
"""
import argparse
import sys
import time

from core.models import ChatMessage
from core.shared_state import SharedState
from core.udp_discovery import UDPDiscoveryService


class DummySignal:
    """Giả lập một Signal của PySide6 để in trực tiếp ra console khi Thành viên A tự test."""
    def __init__(self, label: str) -> None:
        self.label = label
        self.count = 0
        self.history = []

    def emit(self, *args: object) -> None:
        self.count += 1
        self.history.append(args)
        print(f"[DummySignal:{self.label}] {args}")


class DummyAppSignals:
    """Bộ Signals giả lập dành cho Thành viên A."""
    def __init__(self) -> None:
        self.peer_list_updated = DummySignal("peer_list_updated")
        self.system_notification = DummySignal("system_notification")


def print_peers(state: SharedState) -> None:
    peers = state.get_online_peers()
    if not peers:
        print("(chưa thấy ai online)")
    for i, p in enumerate(peers, 1):
        age = time.time() - p.last_seen
        print(f"{i}. {p.name} ({p.ip}) {p.status}  id={p.peer_id}  last_seen={age:.1f}s trước")


def main() -> None:
    """Chạy 1 peer thủ công: phát HELLO mỗi 3s, nhận HELLO của instance khác, tự xóa peer sau 10s."""
    ap = argparse.ArgumentParser(description="Mock test UDP Discovery (Thành viên A)")
    ap.add_argument("--name", default="Alice")
    ap.add_argument("--port", type=int, default=5001, help="cổng TCP giả định (chỉ để gửi trong HELLO)")
    ap.add_argument("--udp-port", type=int, default=9999)
    ap.add_argument("--broadcast", default="255.255.255.255")
    ap.add_argument("--selftest", action="store_true", help="chạy bộ kiểm tra tự động rồi thoát")
    args = ap.parse_args()
    if args.selftest:
        selftest(args.udp_port)
        return

    state = SharedState(args.name, args.port)
    signals = DummyAppSignals()
    service = UDPDiscoveryService(state, args.udp_port, args.broadcast, signals)
    try:
        service.start()
    except OSError as e:
        sys.exit(f"[!] Không bind được UDP {args.udp_port}: {e}")
    print(f"[Mock Test A] {args.name} đang phát HELLO mỗi 3s tới {args.broadcast}:{args.udp_port}")
    print("Lệnh: list | away | online | quit")
    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd == "list":
                print_peers(state)
            elif cmd in ("away", "online"):
                state.set_my_status(cmd)
                service.send_immediate_broadcast()
                print(f"[*] Status của bạn: {cmd}")
            elif cmd == "quit":
                break
            elif cmd:
                print("Lệnh: list | away | online | quit")
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        service.stop()


# --------------------------------------------------------------------------- selftest
def _wait_for(cond, secs: float) -> bool:
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def selftest(udp_port: int) -> None:
    ok = True

    def check(label: str, cond: object) -> None:
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + label)
        ok &= bool(cond)

    # --- SharedState thuần (không dùng mạng)
    s = SharedState("Me", 5000)
    check("upsert -> joined", s.upsert_peer("Zed", "10.0.0.2", 5002, "online") == "joined")
    check("upsert -> None (chỉ làm mới)", s.upsert_peer("Zed", "10.0.0.2", 5002, "online") is None)
    check("upsert -> status_changed", s.upsert_peer("Zed", "10.0.0.2", 5002, "away") == "status_changed")
    s.upsert_peer("Amy", "10.0.0.3", 5003, "online")
    check("sắp xếp theo tên", [p.name for p in s.get_online_peers()] == ["Amy", "Zed"])
    check("find_peer theo số/tên/peer_id",
          s.find_peer("1").name == "Amy" and s.find_peer("zed").name == "Zed"
          and s.find_peer("10.0.0.2:5002").name == "Zed" and s.find_peer("9") is None)
    s.upsert_peer("Amy", "10.0.0.3", 6003, "online")
    check("cùng tên đổi cổng -> thay bản cũ",
          [p.peer_id for p in s.get_online_peers() if p.name == "Amy"] == ["10.0.0.3:6003"])
    zid = "10.0.0.2:5002"
    s.set_active_chat("10.0.0.3:6003")
    n1 = s.append_message(zid, ChatMessage("Zed", zid, "hi"))
    n2 = s.append_message(zid, ChatMessage("Zed", zid, "slides?"))
    check("unread tăng khi không phải chat hiện tại", (n1, n2) == (1, 2))
    hist = s.set_active_chat(zid)
    check("set_active_chat reset unread & trả lịch sử", s.get_unread_count(zid) == 0 and len(hist) == 2)
    check("tin của chat hiện tại không tăng unread", s.append_message(zid, ChatMessage("Zed", zid, "x")) == 0)
    time.sleep(0.2)
    check("remove_expired_peers", len(s.remove_expired_peers(0.1)) == 2 and not s.get_online_peers())

    # --- UDP thật qua loopback broadcast (chu kỳ rút ngắn để test nhanh)
    sa, sb = SharedState("A", 5001), SharedState("B", 5002)
    sig = DummyAppSignals()
    da = UDPDiscoveryService(sa, udp_port, "127.255.255.255", sig, interval=0.3, timeout=1.5, scan_interval=0.3)
    db = UDPDiscoveryService(sb, udp_port, "127.255.255.255", None, interval=0.3, timeout=1.5, scan_interval=0.3)
    da.start()
    db.start()
    check("A thấy B", _wait_for(lambda: sa.find_peer("B") is not None, 3))
    check("B thấy A (signals=None vẫn chạy)", _wait_for(lambda: sb.find_peer("A") is not None, 3))
    check("A không liệt kê chính mình", sa.find_peer("A") is None)
    check("thông báo online", ("[*] B is now online",) in sig.system_notification.history)
    sb.set_my_status("away")
    db.send_immediate_broadcast()
    check("status lan truyền ngay", _wait_for(lambda: sa.find_peer("B").status == "away", 2))
    before = sig.peer_list_updated.count
    db.stop()
    check("B timeout -> bị xóa", _wait_for(lambda: sa.find_peer("B") is None, 4))
    check("thông báo offline + cập nhật list",
          ("[*] B went offline",) in sig.system_notification.history and sig.peer_list_updated.count > before)
    da.stop()
    print("ALL PASSED" if ok else "SOME FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
