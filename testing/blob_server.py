import socket
import threading
import json
import sys
import select
import datetime


HOST = '0.0.0.0'
PORT = 65432

clients = {}
positions = {}
nicknames = {}
chat_messages = []
lock = threading.Lock()

LOGFILE = 'server.log'


def log_event(msg):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOGFILE, 'a') as f:
        f.write(line + '\n')


def broadcast():
    with lock:
        data = json.dumps({'positions': positions, 'chat': chat_messages[-20:]}) + '\n'
        data = data.encode()
        for c in clients.values():
            try:
                c.sendall(data)
            except:
                pass

def handle_client(conn, addr, client_id):
    log_event(f"New connection from {addr}, assigned client_id={client_id}")
    # Send the client its ID on connect
    try:
        conn.sendall((json.dumps({'your_id': client_id}) + '\n').encode())
    except Exception as e:
        log_event(f"Error sending client id to {client_id}: {e}")
    joined_nick = None
    try:
        with conn:
            # Wait for nickname as first message
            try:
                buffer = ''
                while True:
                    data = conn.recv(2048)
                    if not data:
                        break
                    buffer += data.decode()
                    if '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if not line.strip():
                            continue
                        msg = json.loads(line)
                        log_event(f"Received from {client_id}: {msg}")
                        if 'nick' in msg:
                            with lock:
                                nicknames[client_id] = msg['nick']
                                joined_nick = msg['nick']
                        break
            except Exception as e:
                log_event(f"Error receiving nickname from {client_id}: {e}")
            # Broadcast join message
            if joined_nick:
                with lock:
                    chat_messages.append({'id': 'system', 'msg': f'{joined_nick} joined the room.'})
                log_event(f"{joined_nick} joined the room.")
                broadcast()
            buffer = ''
            while True:
                try:
                    data = conn.recv(2048)
                    if not data:
                        break
                    buffer += data.decode()
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if not line.strip():
                            continue
                        msg = json.loads(line)
                        log_event(f"Received from {client_id}: {msg}")
                        with lock:
                            if 'pos' in msg:
                                # Attach nickname to position
                                pos = msg['pos']
                                pos['nick'] = nicknames.get(client_id, f"Blob {client_id}")
                                positions[client_id] = pos
                            if 'private' in msg and 'chat' in msg:
                                # Private message: send only to the target client
                                target_id = msg['private']
                                if target_id in clients:
                                    try:
                                        private_data = (json.dumps({'private_from': client_id, 'msg': msg['chat']}) + '\n').encode()
                                        clients[target_id].sendall(private_data)
                                        log_event(f"Private message from {client_id} to {target_id}: {msg['chat']}")
                                    except Exception as e:
                                        log_event(f"Error sending private message from {client_id} to {target_id}: {e}")
                                # Optionally, notify sender
                                try:
                                    system_data = (json.dumps({'system': f"Private message sent to {nicknames.get(target_id, target_id)}"}) + '\n').encode()
                                    conn.sendall(system_data)
                                except:
                                    pass
                            elif 'chat' in msg:
                                chat_messages.append({'id': client_id, 'msg': msg['chat']})
                                log_event(f"Chat from {client_id}: {msg['chat']}")
                        broadcast()
                        log_event(f"Broadcasted update to all clients.")
                except Exception as e:
                    log_event(f"Error in client {client_id} loop: {e}")
                    break
    finally:
        left_nick = None
        with lock:
            if client_id in nicknames:
                left_nick = nicknames[client_id]
            if client_id in clients:
                del clients[client_id]
            if client_id in positions:
                del positions[client_id]
            if client_id in nicknames:
                del nicknames[client_id]
            if left_nick:
                chat_messages.append({'id': 'system', 'msg': f'{left_nick} left the room.'})
                log_event(f"{left_nick} left the room.")
        broadcast()

def main():
    print(f"Server listening on {HOST}:{PORT}")
    print("Type 'exit' and press Enter to stop the server.")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        client_counter = 0
        s.setblocking(False)
        while True:
            # Check for user input
            rlist, _, _ = select.select([sys.stdin, s], [], [], 0.2)
            for ready in rlist:
                if ready == sys.stdin:
                    cmd = sys.stdin.readline().strip()
                    if cmd.lower() == 'exit':
                        print('Shutting down server...')
                        return
                elif ready == s:
                    conn, addr = s.accept()
                    conn.setblocking(True)  # Ensure client sockets are blocking
                    client_id = str(client_counter)
                    client_counter += 1
                    with lock:
                        clients[client_id] = conn
                        positions[client_id] = {'x': 50, 'y': 50}
                    threading.Thread(target=handle_client, args=(conn, addr, client_id), daemon=True).start()
                    broadcast()

if __name__ == "__main__":
    main()
