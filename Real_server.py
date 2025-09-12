import socket
import threading
from typing import Dict, Set, Optional

class ChatRoom:
    def __init__(self):
        self.members: Set[str] = set()

    def join(self, username: str, conn: socket.socket):
        self.members.add(username)
        conn.sendall(b"[ChatRoom] You joined the chat room!\n")

class PrivateRoom:
    """Logical placeholder, real routing is handled by Server via partner mapping."""
    def __init__(self):
        self.members: Set[str] = set()

    def join(self, username: str, conn: socket.socket):
        self.members.add(username)
        conn.sendall(b"[PrivateRoom] You entered private messaging mode.\n")

class Server:
    def __init__(self, host: str = "0.0.0.0", port: int = 65432):
        self.host = host
        self.port = port

        # Connections and users
        self.lock = threading.Lock()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen()

        # State
        self.addr_clients: Set[tuple] = set()
        self.usernames: Set[str] = set()
        self.conn_by_user: Dict[str, socket.socket] = {}
        self.user_by_conn: Dict[socket.socket, str] = {}
        self.private_partner: Dict[str, Optional[str]] = {}  # user -> partner or None
        self.mode_by_user: Dict[str, str] = {}  # "menu" | "chatroom" | "private"

        # Rooms
        self.chat_room = ChatRoom()
        self.private_room = PrivateRoom()

        print(f"Server listening on {self.host}:{self.port}")
        print("Type 'exit' and press Enter to stop the server.")

    def start(self):
        threading.Thread(target=self.wait_for_exit, daemon=True).start()
        try:
            while True:
                conn, addr = self.server.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            print("\nServer shutting down.")
        finally:
            self.server.close()

    def handle_client(self, conn: socket.socket, addr):
        username = None
        try:
            conn.sendall(b"Welcome! Please enter a username: ")
            # Pick unique username
            while True:
                username = conn.recv(1024).decode(errors="ignore").strip()
                if not username:
                    conn.sendall(b"Username cannot be empty. Try again: ")
                    continue
                with self.lock:
                    if username in self.usernames:
                        conn.sendall(b"Username already taken. Try another: ")
                    else:
                        self.usernames.add(username)
                        self.conn_by_user[username] = conn
                        self.user_by_conn[conn] = username
                        self.private_partner[username] = None
                        self.mode_by_user[username] = "menu"
                        break

            with self.lock:
                self.addr_clients.add(addr)
                print(f"[JOIN] {addr} as {username} connected. Total: {len(self.addr_clients)}")

            # Main interaction loop
            while True:
                mode = self.mode_by_user.get(username, "menu")
                if mode == "menu":
                    self.send_menu(conn)
                    option = self.recv_line(conn)
                    if option == "1":
                        self.chat_room.join(username, conn)
                        self.mode_by_user[username] = "chatroom"
                        conn.sendall(b"[ChatRoom] Type your messages. Use /menu to return.\n")
                    elif option == "2":
                        self.private_room.join(username, conn)
                        self.mode_by_user[username] = "private"
                        self.handle_private_selection(username, conn)
                    elif option == "3":
                        self.start_text_adventure(conn)
                        # After game ends, return to menu
                        self.mode_by_user[username] = "menu"
                    else:
                        conn.sendall(b"Invalid option. Please enter 1, 2, or 3.\n")
                        continue

                # Data loop for chat modes
                data = conn.recv(1024)
                if not data:
                    break
                msg = data.decode(errors="ignore").rstrip("\n")

                # Commands from any mode
                if msg == "/menu":
                    self.leave_private_if_any(username)
                    self.mode_by_user[username] = "menu"
                    continue

                if self.mode_by_user.get(username) == "chatroom":
                    # Simple echo to sender for now
                    conn.sendall(f"[You in ChatRoom] {msg}\n".encode())

                elif self.mode_by_user.get(username) == "private":
                    partner = self.private_partner.get(username)
                    if partner is None:
                        # Not paired yet, try to (user could type recipient name directly)
                        self.handle_private_selection(username, conn, typed_candidate=msg)
                        continue
                    # Forward to partner if still online
                    with self.lock:
                        pconn = self.conn_by_user.get(partner)
                    if pconn:
                        pconn.sendall(f"[Private] {username}: {msg}\n".encode())
                        # Optional echo back to sender
                        conn.sendall(f"[Private -> {partner}] {msg}\n".encode())
                    else:
                        conn.sendall(b"[Private] Partner went offline. Returning to menu.\n")
                        self.leave_private_if_any(username)
                        self.mode_by_user[username] = "menu"

        except Exception as e:
            print(f"[ERROR] {addr}: {e}")
        finally:
            with self.lock:
                if username:
                    self.leave_private_if_any(username)
                    self.usernames.discard(username)
                    self.conn_by_user.pop(username, None)
                    self.mode_by_user.pop(username, None)
                    self.private_partner.pop(username, None)
                    self.user_by_conn.pop(conn, None)
                self.addr_clients.discard(addr)
                print(f"[LEAVE] {addr} disconnected. Total: {len(self.addr_clients)}")
            try:
                conn.close()
            except Exception:
                pass

    def send_menu(self, conn: socket.socket):
        menu = (
            "\nOptions:\n"
            "1. Join chat room\n"
            "2. Private messages\n"
            "3. Play Text Adventure\n"
            "Enter option (1, 2, or 3): "
        )
        conn.sendall(menu.encode())

    def handle_private_selection(self, username: str, conn: socket.socket, typed_candidate: Optional[str] = None):
        """List users, pick a recipient, pair both, then stay in private mode.
           User can leave with /exit or /menu."""
        while True:
            # Build list of available users
            with self.lock:
                candidates = sorted([u for u in self.usernames if u != username and self.conn_by_user.get(u)])
            if not candidates:
                conn.sendall(b"[Private] No other users online. Returning to menu.\n")
                self.mode_by_user[username] = "menu"
                return

            # If the method was reentered with a typed candidate, try it
            if typed_candidate:
                choice = typed_candidate
                typed_candidate = None
            else:
                conn.sendall(f"[Private] Online users: {', '.join(candidates)}\n".encode())
                conn.sendall(b"[Private] Enter recipient username (or /menu to go back): ")
                choice = self.recv_line(conn)

            if choice == "/menu":
                self.mode_by_user[username] = "menu"
                return
            if choice == "/exit":
                self.mode_by_user[username] = "menu"
                return

            # Validate choice
            with self.lock:
                if choice in candidates and self.conn_by_user.get(choice):
                    # Pair both sides
                    self.private_partner[username] = choice
                    self.private_partner[choice] = username
                    conn.sendall(f"[Private] You are now chatting with {choice}. Type /menu to leave.\n".encode())
                    partner_conn = self.conn_by_user.get(choice)
                    if partner_conn:
                        partner_conn.sendall(f"[Private] You are now chatting with {username}. Type /menu to leave.\n".encode())
                    return
                else:
                    conn.sendall(b"[Private] Invalid or unavailable user. Try again.\n")

    def leave_private_if_any(self, username: str):
        """Remove private pairing both ways if present."""
        with self.lock:
            partner = self.private_partner.get(username)
            if partner:
                self.private_partner[username] = None
                # Only clear reciprocal mapping if it points back
                if self.private_partner.get(partner) == username:
                    self.private_partner[partner] = None
                pconn = self.conn_by_user.get(partner)
                if pconn:
                    try:
                        pconn.sendall(f"[Private] {username} left the private chat.\n".encode())
                    except Exception:
                        pass

    def recv_line(self, conn: socket.socket) -> str:
        data = conn.recv(1024)
        if not data:
            return ""
        return data.decode(errors="ignore").strip()

    def start_text_adventure(self, conn: socket.socket):
        import subprocess
        conn.sendall(b"[TextAdventure] Starting game...\n")
        try:
            proc = subprocess.Popen(
                ["python3", "FunGames/TextAdventure.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=".",
                text=True
            )
            for line in proc.stdout:
                conn.sendall(line.encode())
            proc.wait()
            conn.sendall(b"[TextAdventure] Game ended.\n")
        except Exception as e:
            conn.sendall(f"[TextAdventure] Error: {e}\n".encode())

    def wait_for_exit(self):
        while True:
            cmd = input()
            if cmd.strip().lower() == "exit":
                print("Exiting server...")
                import os; os._exit(0)

if __name__ == "__main__":
    server = Server()
    server.start()
