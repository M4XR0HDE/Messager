import socket

HOST = '127.0.0.1'  # Server address
PORT = 65432        # Server port

def main():
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
		s.connect((HOST, PORT))
		print(f"Connected to server at {HOST}:{PORT}")
		while True:
			# Receive prompt from server
			data = s.recv(1024)
			if not data:
				print("Server closed the connection.")
				break
			print(data.decode(), end='')
			# Get user input and send to server
			user_input = input()
			if user_input.lower() in ('exit', 'quit'):
				print("Disconnecting...")
				break
			s.sendall(user_input.encode())

if __name__ == "__main__":
	main()
