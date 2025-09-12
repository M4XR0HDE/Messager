import socket

HOST = '127.0.0.1'  # Server address
PORT = 65432        # Server port

def main():
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
		s.connect((HOST, PORT))
		print(f"Connected to server at {HOST}:{PORT}")
		msg = input("Enter message to send (or just press Enter to disconnect): ")
		if msg:
			s.sendall(msg.encode())
			# Wait for echo from server
			data = s.recv(1024)
			print(f"Received echo: {data.decode()}")
		print("Disconnecting...")

if __name__ == "__main__":
	main()
