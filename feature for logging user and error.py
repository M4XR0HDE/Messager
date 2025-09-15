import socket
import threading
import logging
import datetime
import os

# Configure logging


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
        logger.info(f"Chat room {room_id} created")

    def join(self, username, conn):
        self.members.add((username, conn))
        user_logger.info(f"User '{username}' joined chat room {self.room_id}")
        logger.debug(
            f"Chat room {self.room_id} now has {len(self.members)} members")

        msg = f"[ChatRoom {self.room_id}] You joined chat room {self.room_id}!\n"
        if self.history:
            msg += f"[ChatRoom {self.room_id}] Previous messages:\n"
            for user, m in self.history:
                msg += f"{user}: {m}\n"
        else:
            msg += f"[ChatRoom {self.room_id}] No previous messages.\n"
        msg += "Type your messages. Type /leave to exit the chat room.\n"
        msg += f"[{self.room_id}] You: "

        try:
            conn.sendall(msg.encode())
            logger.debug(
                f"Welcome message sent to user '{username}' in room {self.room_id}")
        except Exception as e:
            logger.error(
                f"Failed to send welcome message to user '{username}': {e}")

    def broadcast(self, sender, message):
        if not message.strip():
            return  # Ignore empty messages

        self.history.append((sender, message))
        user_logger.info(
            f"User '{sender}' sent message in room {self.room_id}: {message[:50]}{'...' if len(message) > 50 else ''}")

        broadcast_count = 0
        failed_sends = 0

        for user, conn in list(self.members):
            try:
                if user != sender:
                    conn.sendall(
                        f"[{self.room_id}] {sender}: {message}\n".encode())
                    broadcast_count += 1
            except Exception as e:
                logger.warning(
                    f"Failed to send message to user '{user}' in room {self.room_id}: {e}")
                failed_sends += 1

        logger.debug(
            f"Message broadcast in room {self.room_id}: {broadcast_count} successful, {failed_sends} failed")

    def remove(self, username, conn):
        initial_count = len(self.members)
        self.members.discard((username, conn))
        if len(self.members) < initial_count:
            user_logger.info(
                f"User '{username}' left chat room {self.room_id}")
            logger.debug(
                f"Chat room {self.room_id} now has {len(self.members)} members")


class PrivateRoom:
    def __init__(self):
        self.members = set()
        logger.info("Private room created")

    def join(self, username, conn):
        self.members.add(username)
        user_logger.info(f"User '{username}' joined private room")
        try:
            conn.sendall(b"[PrivateRoom] You joined the private room!\n")
            logger.debug(
                f"Private room join confirmation sent to user '{username}'")
        except Exception as e:
            logger.error(
                f"Failed to send private room confirmation to user '{username}': {e}")


class Server:
    def __init__(self, host='0.0.0.0', port=65432):
        self.host = host
        self.port = port
        self.clients = set()
        self.usernames = set()
        self.lock = threading.Lock()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server.bind((self.host, self.port))
            self.server.listen()
            logger.info(
                f"Server started successfully on {self.host}:{self.port}")
        except Exception as e:
            logger.critical(
                f"Failed to start server on {self.host}:{self.port}: {e}")
            raise

        self.chat_rooms = {str(i): ChatRoom(str(i)) for i in range(1, 5)}
        self.private_room = PrivateRoom()

        print(f"Server listening on {self.host}:{self.port}")
        print("Type 'exit' and press Enter to stop the server.")

    def start(self):
        logger.info("Server startup initiated")
        threading.Thread(target=self.wait_for_exit, daemon=True).start()

        try:
            while True:
                try:
                    conn, addr = self.server.accept()
                    logger.info(f"New connection attempt from {addr}")
                    threading.Thread(target=self.handle_client, args=(
                        conn, addr), daemon=True).start()
                except Exception as e:
                    logger.error(f"Error accepting connection: {e}")
        except KeyboardInterrupt:
            logger.info("Server shutdown initiated by keyboard interrupt")
            print("\nServer shutting down.")
        finally:
            self.server.close()
            logger.info("Server socket closed")

    def handle_client(self, conn, addr):
        username = None
        connection_start_time = datetime.datetime.now()

        try:
            logger.debug(f"Handling new client connection from {addr}")
            conn.sendall(b"Welcome! Please enter a username: ")

            # Username selection loop
            while True:
                try:
                    username = conn.recv(1024).decode().strip()
                except Exception as e:
                    logger.warning(
                        f"Failed to receive username from {addr}: {e}")
                    return

                if not username:
                    conn.sendall(b"Username cannot be empty. Try again: ")
                    continue

                with self.lock:
                    if username in self.usernames:
                        logger.debug(
                            f"Username '{username}' already taken, requested by {addr}")
                        conn.sendall(b"Username already taken. Try another: ")
                    else:
                        self.usernames.add(username)
                        break

            with self.lock:
                self.clients.add(addr)
                user_count = len(self.clients)

            user_logger.info(f"User '{username}' connected from {addr}")
            logger.info(
                f"Client {addr} registered as '{username}'. Total clients: {user_count}")

            # Main menu loop
            while True:
                menu = ("\nOptions:\n"
                        "1. Join chat room\n"
                        "2. Private messages\n"
                        "3. List online users\n"
                        "4. Exit\n"
                        "Enter option (1, 2, 3, or 4): ")

                try:
                    conn.sendall(menu.encode())
                    option = conn.recv(1024).decode().strip()
                except Exception as e:
                    logger.warning(
                        f"Connection lost with user '{username}' ({addr}): {e}")
                    break

                user_logger.info(
                    f"User '{username}' selected menu option: {option}")

                if option == '1':
                    conn.sendall(b"Enter chat room number (1-4): ")
                    try:
                        room_choice = conn.recv(1024).decode().strip()
                    except Exception as e:
                        logger.warning(
                            f"Failed to receive room choice from '{username}': {e}")
                        break

                    if room_choice in self.chat_rooms:
                        room = self.chat_rooms[room_choice]
                        logger.info(
                            f"User '{username}' entering chat room {room_choice}")
                        room.join(username, conn)
                        self.handle_chat_room(username, conn, room)
                    else:
                        logger.debug(
                            f"User '{username}' entered invalid room number: {room_choice}")
                        conn.sendall(b"Invalid room number.\n")

                elif option == '2':
                    logger.info(f"User '{username}' accessed private room")
                    self.private_room.join(username, conn)

                elif option == '3':
                    with self.lock:
                        user_list = ', '.join(
                            self.usernames) if self.usernames else 'No users online.'

                    logger.debug(f"User '{username}' requested user list")
                    try:
                        conn.sendall(
                            f"[Server] Online users: {user_list}\n".encode())
                    except Exception as e:
                        logger.warning(
                            f"Failed to send user list to '{username}': {e}")
                        break

                elif option == '4':
                    logger.info(f"User '{username}' initiated disconnect")
                    conn.sendall(b"Goodbye!\n")
                    break

                else:
                    logger.debug(
                        f"User '{username}' entered invalid menu option: {option}")
                    conn.sendall(
                        b"Invalid option. Please enter 1, 2, 3, or 4.\n")

        except Exception as e:
            logger.error(
                f"Unexpected error handling client {addr} ('{username}'): {e}")

        finally:
            connection_duration = datetime.datetime.now() - connection_start_time

            with self.lock:
                self.clients.discard(addr)
                if username:
                    self.usernames.discard(username)
                user_count = len(self.clients)

            if username:
                user_logger.info(
                    f"User '{username}' disconnected from {addr}. Session duration: {connection_duration}")
                logger.info(
                    f"Client {addr} ('{username}') disconnected. Total clients: {user_count}")
            else:
                logger.info(
                    f"Client {addr} disconnected before choosing username. Total clients: {user_count}")

            try:
                conn.close()
            except Exception as e:
                logger.warning(f"Error closing connection to {addr}: {e}")

    def handle_chat_room(self, username, conn, room):
        room_entry_time = datetime.datetime.now()
        logger.debug(
            f"User '{username}' entered chat room {room.room_id} handler")

        try:
            first = True
            message_count = 0

            while True:
                if not first:
                    conn.sendall(f"[{room.room_id}] You: ".encode())
                else:
                    first = False

                try:
                    data = conn.recv(1024)
                except Exception as e:
                    logger.warning(
                        f"Connection lost with user '{username}' in room {room.room_id}: {e}")
                    break

                if not data:
                    logger.debug(
                        f"User '{username}' connection closed in room {room.room_id}")
                    break

                msg = data.decode().strip()
                if not msg:
                    continue  # Ignore empty input

                message_count += 1

                if msg.lower() == '/leave':
                    logger.info(
                        f"User '{username}' left chat room {room.room_id} via /leave command")
                    conn.sendall(b"[ChatRoom] Leaving chat room.\n")
                    break

                room.broadcast(username, msg)

        except Exception as e:
            logger.error(
                f"Error in chat room handler for user '{username}' in room {room.room_id}: {e}")

        finally:
            room_duration = datetime.datetime.now() - room_entry_time
            room.remove(username, conn)
            user_logger.info(
                f"User '{username}' session in room {room.room_id} ended. Duration: {room_duration}, Messages sent: {message_count}")

    def start_text_adventure(self, username, conn):
        import subprocess
        import os

        logger.info(f"Starting text adventure for user '{username}'")
        conn.sendall(b"[TextAdventure] Starting game...\n")

        try:
            # Resolve absolute path to TextAdventure.py
            base_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(
                base_dir, 'FunGames', 'TextAdventure.py')

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
                            logger.debug(
                                f"First game output received for user '{username}': {line.strip()}")
                            first_line_received.set()
                        try:
                            conn.sendall(line.encode())
                        except Exception as e:
                            logger.warning(
                                f"Failed to send game output to user '{username}': {e}")
                            break
                finally:
                    stop_event.set()

            threading.Thread(target=pump_output, daemon=True).start()

            # Send initial newline to trigger prompt/output
            try:
                proc.stdin.write('\n')
                proc.stdin.flush()
            except Exception as e:
                logger.warning(
                    f"Failed to send initial input to game for user '{username}': {e}")

            conn.sendall(
                f"[TextAdventure] Interactive mode for {username}. Type /exit to return.\n".encode())

            while not stop_event.is_set():
                try:
                    data = conn.recv(1024)
                except Exception as e:
                    logger.warning(
                        f"Connection lost with user '{username}' during text adventure: {e}")
                    break

                if not data:
                    break

                msg = data.decode().rstrip('\r\n')
                if msg == '/exit':
                    logger.info(f"User '{username}' exiting text adventure")
                    proc.terminate()
                    break

                # Forward user input to game
                try:
                    proc.stdin.write(msg + '\n')
                    proc.stdin.flush()
                    logger.debug(f"Game input from user '{username}': {msg}")
                except Exception as e:
                    logger.warning(
                        f"Failed to send input to game for user '{username}': {e}")
                    break

            # Ensure process ends
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
                logger.warning(
                    f"Had to force kill text adventure process for user '{username}'")

            conn.sendall(
                f"[TextAdventure] Game ended for {username}.\n".encode())
            logger.info(f"Text adventure ended for user '{username}'")

        except Exception as e:
            logger.error(f"Error in text adventure for user '{username}': {e}")
            conn.sendall(f"[TextAdventure] Error: {e}\n".encode())

    def wait_for_exit(self):
        logger.debug("Exit handler thread started")
        while True:
            try:
                cmd = input()
                if cmd.strip().lower() == 'exit':
                    logger.info("Server shutdown initiated by user command")
                    print("Exiting server...")
                    import os
                    os._exit(0)
            except EOFError:
                # Handle case where input is not available (e.g., running as service)
                break
            except Exception as e:
                logger.error(f"Error in exit handler: {e}")


if __name__ == "__main__":
    try:
        server = Server()
        server.start()
    except Exception as e:
        logger.critical(f"Failed to start server: {e}")
        raise
