import socket
import threading
from typing import Dict, Set, Optional
import subprocess
import os
import logging
import datetime

def setup_logging():
    """Set up logging configuration with both file and console output"""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # Create file handler for all logs
    file_handler = logging.FileHandler(
        f'logs/server_{datetime.datetime.now().strftime("%Y%m%d")}.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    # Create separate file handler for user activities
    user_activity_handler = logging.FileHandler(
        f'logs/user_activity_{datetime.datetime.now().strftime("%Y%m%d")}.log')
    user_activity_handler.setLevel(logging.INFO)
    user_activity_handler.setFormatter(detailed_formatter)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Create user activity logger
    user_logger = logging.getLogger('user_activity')
    user_logger.addHandler(user_activity_handler)
    user_logger.propagate = False  # Don't propagate to root logger

    return logging.getLogger(__name__), user_logger

# Initialize loggers
logger, user_logger = setup_logging()

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



        # Rooms: create 4 chat rooms with IDs 1-4
        self.chat_rooms = {str(i): ChatRoom(str(i)) for i in range(1, 5)}
        self.private_room = PrivateRoom()

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
                logger.info(f"[INPUT] {addr} entered username: {username}")
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
                        user_logger.info(f"[JOIN] {username} ({addr}) connected.")
                        break

            with self.lock:
                self.addr_clients.add(addr)
                logger.info(f"[JOIN] {addr} as {username} connected. Total: {len(self.addr_clients)}")

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
                logger.info(f"[INPUT] {username}@{addr} selected option: {option}")
                user_logger.info(f"[MENU] {username} selected option: {option}")
                if option == '1':
                    conn.sendall(b"Enter chat room number (1-4): ")
                    room_choice = conn.recv(1024).decode().strip()
                    logger.info(f"[INPUT] {username}@{addr} chose chat room: {room_choice}")
                    user_logger.info(f"[CHATROOM] {username} chose chat room: {room_choice}")
                    if room_choice in self.chat_rooms:
                        room = self.chat_rooms[room_choice]
                        room.join(username, conn)
                        user_logger.info(f"[CHATROOM] {username} joined chat room {room_choice}")
                        self.handle_chat_room(username, conn, room)
                    else:
                        conn.sendall(b"Invalid room number.\n")
                        logger.warning(f"[WARN] {username}@{addr} entered invalid chat room: {room_choice}")
                elif option == '2':
                    self.private_room.join(username, conn)
                    user_logger.info(f"[PRIVATE] {username} entered private messaging mode.")
                    # Enter private messaging loop
                    while True:
                        conn.sendall(b"[Private] Type your message (or /menu to leave): ")
                        data = conn.recv(1024)
                        if not data:
                            break
                        msg = data.decode(errors="ignore").strip()
                        logger.info(f"[INPUT] {username}@{addr} (private): {msg}")
                        user_logger.info(f"[PRIVATE] {username}: {msg}")
                        if msg == "/menu" or msg == "/exit":
                            conn.sendall(b"[Private] Leaving private chat.\n")
                            user_logger.info(f"[PRIVATE] {username} left private chat.")
                            self.leave_private_if_any(username)
                            break
                        partner = self.private_partner.get(username)
                        if partner is None:
                            # Not paired yet, try to select
                            self.handle_private_selection(username, conn, typed_candidate=msg)
                            continue
                        # Forward to partner if still online
                        with self.lock:
                            pconn = self.conn_by_user.get(partner)
                        if pconn:
                            pconn.sendall(f"[Private] {username}: {msg}\n".encode())
                            # Optional echo back to sender
                            conn.sendall(f"[Private -> {partner}] {msg}\n".encode())
                            user_logger.info(f"[PRIVATE] {username} -> {partner}: {msg}")
                        else:
                            conn.sendall(b"[Private] Partner went offline. Returning to menu.\n")
                            user_logger.info(f"[PRIVATE] {username}'s partner {partner} went offline.")
                            self.leave_private_if_any(username)
                            break
                elif option == '3':
                    with self.lock:
                        online_users = [u for u in self.usernames if self.conn_by_user.get(u)]
                    conn.sendall(f"Online users: {', '.join(online_users)}\n".encode())
                elif option == '4':
                    conn.sendall(b"Goodbye!\n")
                    try:
                        conn.shutdown(socket.SHUT_RDWR)
                    except Exception:
                        pass
                    conn.close()
                    break
                else:
                    conn.sendall(b"Invalid option. Please try again.\n")

        except Exception as e:
            logger.error(f"[ERROR] {addr}: {e}")
            user_logger.error(f"[ERROR] {username}@{addr}: {e}")
        finally:
            with self.lock:
                if username:
                    self.leave_private_if_any(username)
                    self.usernames.discard(username)
                    self.conn_by_user.pop(username, None)
                    self.mode_by_user.pop(username, None)
                    self.private_partner.pop(username, None)
                    self.user_by_conn.pop(conn, None)
                    user_logger.info(f"[LEAVE] {username} ({addr}) disconnected.")
                self.addr_clients.discard(addr)
                logger.info(f"[LEAVE] {addr} disconnected. Total: {len(self.addr_clients)}")
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
                    conn.sendall(b"You: ")
                    first = False
                data = conn.recv(1024)
                if not data:
                    break
                msg = data.decode().strip()
                logger.info(f"[INPUT] {username} (chatroom {room.room_id}): {msg}")
                user_logger.info(f"[CHATROOM] {username}@{room.room_id}: {msg}")
                if not msg:
                    # Do nothing, do not re-send the prompt
                    continue  # Ignore empty input, prompt remains unchanged
                if msg.lower() == '/leave':
                    conn.sendall(b"[ChatRoom] Leaving chat room.\n")
                    user_logger.info(f"[CHATROOM] {username} left chat room {room.room_id}")
                    break
                room.broadcast(username, msg)
                user_logger.info(f"[CHATROOM] {username} broadcast in {room.room_id}: {msg}")
                conn.sendall(b"You: ")
        except Exception as e:
            logger.error(f"[ERROR] in chat room {room.room_id} for {username}: {e}")
            user_logger.error(f"[ERROR] in chat room {room.room_id} for {username}: {e}")
        finally:
            room.remove(username, conn)
            user_logger.info(f"[CHATROOM] {username} removed from chat room {room.room_id}")

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
