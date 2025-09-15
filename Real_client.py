import time
import socket
import threading

HOST = '0.0.0.0'  # Server address
PORT = 65432        # Server port


def receive_messages(sock):
	try:
		while True:
			data = sock.recv(1024)
			if not data:
				print("\nServer closed the connection.")
				break
			msg = data.decode()
			# If the message is a chat message from another user, print on a new line
			if msg.startswith("[") and "] " in msg and not msg.strip().endswith("You: "):
				print(f"\r\n{msg}", end='', flush=True)
				# Try to extract the current chat room id from the message
				import re
				m = re.match(r"\[(\d+)\] ", msg)
				if m:
					room_id = m.group(1)
					print(f"[{room_id}] You: ", end='', flush=True)
				else:
					print("", end='', flush=True)
			else:
				print(msg, end='', flush=True)
	except Exception:
		pass

def main():
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
		s.connect((HOST, PORT))
		import sys
		print(f"Connected to server at {HOST}:{PORT}")
		sys.stdout.flush()
		recv_thread = threading.Thread(target=receive_messages, args=(s,), daemon=True)
		recv_thread.start()
		# Wait a moment for the first server message to arrive and be printed
		time.sleep(0.05)
		try:
			while True:
				user_input = input()
				if user_input.lower() in ('exit', 'quit'):
					print("Disconnecting...")
					break
				s.sendall(user_input.encode())
		except KeyboardInterrupt:
			print("\nDisconnecting...")
		except Exception:
			pass

if __name__ == "__main__":
    main()
