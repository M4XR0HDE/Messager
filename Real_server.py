import socket
import threading

class Server:
    def __init__(self, host='0.0.0.0', port=65432):
        self.host = host
        self.port = port
        self.clients = set()
        self.lock = threading.Lock()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen()
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
        with self.lock:
            self.clients.add(addr)
            print(f"[JOIN] {addr} connected. Total: {len(self.clients)}")
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                # Echo back
                conn.sendall(data)
        finally:
            with self.lock:
                self.clients.remove(addr)
                print(f"[LEAVE] {addr} disconnected. Total: {len(self.clients)}")
            conn.close()

    def wait_for_exit(self):
        while True:
            cmd = input()
            if cmd.strip().lower() == 'exit':
                print("Exiting server...")
                import os; os._exit(0)

if __name__ == "__main__":
    server = Server()
    server.start()
