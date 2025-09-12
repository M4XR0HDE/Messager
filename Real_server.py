import socket
import threading

class ChatRoom:
    def __init__(self):
        self.members = set()
    def join(self, username, conn):
        self.members.add(username)
        conn.sendall(b"[ChatRoom] You joined the chat room!\n")

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
            # Option selection loop: stays connected and keeps prompting until valid option is chosen
            joined = False
            while not joined:
                conn.sendall(b"\nOptions:\n1. Join chat room\n2. Private messages\n3. Play Text Adventure\nEnter option (1, 2, or 3): ")
                option = conn.recv(1024).decode().strip()
                if option == '1':
                    self.chat_room.join(username, conn)
                    joined = True
                elif option == '2':
                    self.private_room.join(username, conn)
                    joined = True
                elif option == '3':
                    self.start_text_adventure(conn)
                    joined = True
                else:
                    conn.sendall(b"Invalid option. Please enter 1, 2, or 3.\n")
            # After joining, keep connection open for further logic (not implemented)
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                # Echo back for now
                conn.sendall(data)
        except Exception as e:
            print(f"[ERROR] {addr}: {e}")
        finally:
            with self.lock:
                self.clients.discard(addr)
                if username:
                    self.usernames.discard(username)
                print(f"[LEAVE] {addr} disconnected. Total: {len(self.clients)}")
            conn.close()

    def start_text_adventure(self, conn):
        import subprocess
        conn.sendall(b"[TextAdventure] Starting game...\n")
        try:
            proc = subprocess.Popen(
                ['python3', 'FunGames/TextAdventure.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd='.',  # Use current directory
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
            if cmd.strip().lower() == 'exit':
                print("Exiting server...")
                import os; os._exit(0)

if __name__ == "__main__":
    server = Server()
    server.start()
