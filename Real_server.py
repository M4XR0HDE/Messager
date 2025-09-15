import socket
import threading
from typing import Dict, Set, Optional
import subprocess

class ChatRoom:
    def __init__(self, room_id):
        self.room_id = room_id
        self.members = set()  # set of (username, conn)
        self.history = []     # list of (username, message)

    def join(self, username, conn):
        self.members.add((username, conn))
        msg = f"[ChatRoom {self.room_id}] You joined chat room {self.room_id}!\n"
        if self.history:
            msg += f"[ChatRoom {self.room_id}] Previous messages:\n"
            for user, m in self.history:
                msg += f"{user}: {m}\n"
        else:
            msg += f"[ChatRoom {self.room_id}] No previous messages.\n"
        msg += "Type your messages. Type /leave to exit the chat room.\n"
        conn.sendall(msg.encode())

    def broadcast(self, sender, message):
        if not message.strip():
            return  # Ignore empty messages
        self.history.append((sender, message))
        for user, conn in list(self.members):
            try:
                if user != sender:
                    conn.sendall(f"[{self.room_id}] {sender}: {message}\n".encode())
            except Exception:
                pass

    def remove(self, username, conn):
        self.members.discard((username, conn))

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
                menu = ("\nOptions:\n"
                        "1. Join chat room\n"
                        "2. Private messages\n"
                        "3. List online users\n"
                        "4. Exit\n")
                conn.sendall(menu.encode())
                conn.sendall(b"Enter option (1, 2, 3, or 4): ")
                option = conn.recv(1024).decode().strip()
                if option == '1':
                    conn.sendall(b"Enter chat room number (1-4): ")
                    room_choice = conn.recv(1024).decode().strip()
                    if room_choice in self.chat_rooms:
                        room = self.chat_rooms[room_choice]
                        room.join(username, conn)
                        self.handle_chat_room(username, conn, room)
                    else:
                        conn.sendall(b"Invalid room number.\n")
                elif option == '2':
                    self.private_room.join(username, conn)
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

    def handle_chat_room(self, username, conn, room):
        try:
            # Always send the prompt after joining and after each message
            first = True
            while True:
                if first:
                    conn.sendall(f"[{room.room_id}] You: ".encode())
                    first = False
                data = conn.recv(1024)
                if not data:
                    break
                msg = data.decode().strip()
                if not msg:
                    # Do nothing, do not re-send the prompt
                    continue  # Ignore empty input, prompt remains unchanged
                if msg.lower() == '/leave':
                    conn.sendall(b"[ChatRoom] Leaving chat room.\n")
                    break
                room.broadcast(username, msg)
                conn.sendall(f"[{room.room_id}] You: ".encode())
        except Exception:
            pass
        finally:
            room.remove(username, conn)

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

        #postboned for now  
    def start_text_adventure(self, conn: socket.socket):
        
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
