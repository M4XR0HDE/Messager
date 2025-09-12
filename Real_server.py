import socket
import threading

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
    def __init__(self):
        self.members = set()
    def join(self, username, conn):
        self.members.add(username)
        conn.sendall(b"[PrivateRoom] You joined the private room!\n")

class Server:
    def __init__(self, host='0.0.0.0', port=65432):
        self.host = host
        self.port = port
        self.clients = set()
        self.usernames = set()
        self.lock = threading.Lock()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen()
        self.chat_rooms = {str(i): ChatRoom(str(i)) for i in range(1, 5)}
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

    def handle_client(self, conn, addr):
        username = None
        try:
            conn.sendall(b"Welcome! Please enter a username: ")
            while True:
                username = conn.recv(1024).decode().strip()
                if not username:
                    conn.sendall(b"Username cannot be empty. Try again: ")
                    continue
                with self.lock:
                    if username in self.usernames:
                        conn.sendall(b"Username already taken. Try another: ")
                    else:
                        self.usernames.add(username)
                        break
            with self.lock:
                self.clients.add(addr)
                print(f"[JOIN] {addr} as {username} connected. Total: {len(self.clients)}")
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
                    # For now, just acknowledge and return to menu
                elif option == '3':
                    with self.lock:
                        user_list = ', '.join(self.usernames) if self.usernames else 'No users online.'
                    conn.sendall(f"[Server] Online users: {user_list}\n".encode())
                elif option == '4':
                    conn.sendall(b"Goodbye!\n")
                    break
                else:
                    conn.sendall(b"Invalid option. Please enter 1, 2, 3, or 4.\n")
        except Exception as e:
            print(f"[ERROR] {addr}: {e}")
        finally:
            with self.lock:
                self.clients.discard(addr)
                if username:
                    self.usernames.discard(username)
                print(f"[LEAVE] {addr} disconnected. Total: {len(self.clients)}")
            conn.close()

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
    #postboned for now
    def start_text_adventure(self, username, conn):
        import subprocess
        import os
        conn.sendall(b"[TextAdventure] Starting game...\n")
        try:
            # Resolve absolute path to TextAdventure.py
            base_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(base_dir, 'FunGames', 'TextAdventure.py')
            proc = subprocess.Popen(
                ['python3', '-u', script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            stop_event = threading.Event()
            first_line_received = threading.Event()

            def pump_output():
                try:
                    for line in proc.stdout:
                        if not line:
                            break
                        if not first_line_received.is_set():
                            print(f"[GAME] First output from game for '{username}': {line.strip()}")
                            first_line_received.set()
                        try:
                            conn.sendall(line.encode())
                        except Exception:
                            break
                finally:
                    stop_event.set()

            threading.Thread(target=pump_output, daemon=True).start()
            # Send initial newline to trigger prompt/output
            try:
                proc.stdin.write('\n')
                proc.stdin.flush()
            except Exception:
                pass
            conn.sendall(f"[TextAdventure] Interactive mode for {username}. Type /exit to return.\n".encode())
            while not stop_event.is_set():
                try:
                    data = conn.recv(1024)
                except Exception:
                    break
                if not data:
                    break
                msg = data.decode().rstrip('\r\n')
                if msg == '/exit':
                    print(f"[GAME] User '{username}' exiting Text Adventure.")
                    proc.terminate()
                    break
                # Forward user input to game
                try:
                    proc.stdin.write(msg + '\n')
                    proc.stdin.flush()
                except Exception:
                    break
            # Ensure process ends
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
            conn.sendall(f"[TextAdventure] Game ended for {username}.\n".encode())
            print(f"[GAME] Text Adventure ended for '{username}'.")
        except Exception as e:
            conn.sendall(f"[TextAdventure] Error: {e}\n".encode())


    def wait_for_exit(self):
        while True:
            cmd = input()
            if cmd.strip().lower() == 'exit':
                print("Exiting server...")
                import os; os._exit(0)

if __name__ == "__main__":
    server = Server()
    server.start()
