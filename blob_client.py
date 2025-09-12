import socket
import sys
import tkinter as tk
import threading
import json


HOST = '127.0.0.1'  # Change to server IP if needed
PORT = 65432


# Parse --nick and --window-chat arguments
NICK = "Blob"
WINDOW_CHAT = False
for i, arg in enumerate(sys.argv):
    if arg == '--nick' and i+1 < len(sys.argv):
        NICK = sys.argv[i+1]
    if arg == '--window-chat':
        WINDOW_CHAT = True

BLOB_RADIUS = 20
MOVE_STEP = 10

class BlobClient:
    def __init__(self, master, nick, window_chat):
        # Track open private chat windows: sender_id -> window
        self.private_chats = {}
        self.master = master
        self.canvas = tk.Canvas(master, width=600, height=400, bg='white')
        self.canvas.pack()
        self.entry = tk.Entry(master)
        self.entry.pack(fill=tk.X)
        self.entry.bind('<Return>', self.send_chat)
        self.blobs = {}
        self.my_id = None
        self.my_pos = {'x': 50, 'y': 50}
        self.latest_chats = {}  # client_id: latest chat message
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((HOST, PORT))
        self.nick = nick
        # Wait for our client id from the server before sending position
        self.my_id = None
        try:
            while self.my_id is None:
                data = self.sock.recv(4096)
                msg = json.loads(data.decode())
                if 'your_id' in msg:
                    self.my_id = msg['your_id']
        except:
            pass
        # Send our nickname to the server
        try:
            self.sock.sendall(json.dumps({'nick': self.nick}).encode())
        except:
            pass
        # Now start listening to server and allow movement
        threading.Thread(target=self.listen_server, daemon=True).start()
        self.master.bind('<Up>', lambda e: self.move(0, -MOVE_STEP))
        self.master.bind('<Down>', lambda e: self.move(0, MOVE_STEP))
        self.master.bind('<Left>', lambda e: self.move(-MOVE_STEP, 0))
        self.master.bind('<Right>', lambda e: self.move(MOVE_STEP, 0))
        self.send_position()
        # Store last positions for click detection
        self.last_positions = {}
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.window_chat = window_chat
        if self.window_chat:
            self.chat_frame = tk.Frame(master)
            self.chat_frame.pack(fill=tk.BOTH, expand=False)
            self.chat_box = tk.Text(self.chat_frame, height=8, state='disabled', wrap='word')
            self.chat_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.scrollbar = tk.Scrollbar(self.chat_frame, command=self.chat_box.yview)
            self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.chat_box['yscrollcommand'] = self.scrollbar.set
            # Show joining message
            self.chat_box.config(state='normal')
            self.chat_box.insert(tk.END, f"{self.nick} joined the room.\n")
            self.chat_box.config(state='disabled')
            self.chat_box.see(tk.END)

    def move(self, dx, dy):
        # Use push logic if more than one blob is present
        if len(self.last_positions) > 1:
            # Use the push function to get new positions
            new_positions = move_blobs_with_push(self.last_positions, self.my_id, dx, dy)
            # Update my own position and send to server
            self.my_pos['x'] = new_positions[self.my_id]['x']
            self.my_pos['y'] = new_positions[self.my_id]['y']
            self.send_position()
        else:
            self.my_pos['x'] += dx
            self.my_pos['y'] += dy
            self.send_position()

    def send_position(self):
        try:
            msg = {'pos': self.my_pos}
            self.sock.sendall(json.dumps(msg).encode())
        except:
            pass

    def send_chat(self, event=None):
        text = self.entry.get().strip()
        if text:
            try:
                msg = {'chat': text}
                self.sock.sendall(json.dumps(msg).encode())
            except:
                pass
            self.entry.delete(0, tk.END)
        # Return focus to canvas for movement
        self.canvas.focus_set()

    def listen_server(self):
        buffer = ''
        while True:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                buffer += data.decode()
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    # Debug: print received data
                    print('Received from server:', msg)
                    # Private message
                    if 'private_from' in msg and 'msg' in msg:
                        self.open_private_chat(msg['private_from'], msg['msg'])
                        continue
                    # System message
                    if 'system' in msg:
                        tk.messagebox.showinfo("System", msg['system'])
                        continue
                    # If this is just the initial id message, skip
                    if 'positions' not in msg or 'chat' not in msg:
                        continue
                    positions = msg.get('positions', {})
                    chat = msg.get('chat', [])
                    self.update_latest_chats(chat)
                    self.update_blobs(positions)
            except Exception as e:
                print('Error in listen_server:', e)
                break

    def open_private_chat(self, sender_id, message):
        sender_nick = self.last_positions.get(sender_id, {}).get('nick', f"Blob {sender_id}")
        if sender_id in self.private_chats:
            win, text_widget, entry = self.private_chats[sender_id]
            text_widget.config(state='normal')
            text_widget.insert(tk.END, f"{sender_nick}: {message}\n")
            text_widget.config(state='disabled')
            text_widget.see(tk.END)
            win.lift()
            return
        win = tk.Toplevel(self.master)
        win.title(f"Private chat with {sender_nick}")
        win.geometry("320x260")
        text_widget = tk.Text(win, state='disabled', width=38, height=10)
        text_widget.pack(padx=6, pady=6)
        text_widget.config(state='normal')
        text_widget.insert(tk.END, f"{sender_nick}: {message}\n")
        text_widget.config(state='disabled')
        entry = tk.Entry(win, width=28)
        entry.pack(side=tk.LEFT, padx=6, pady=4)
        def send_back():
            text = entry.get().strip()
            if text:
                try:
                    msg = {'private': sender_id, 'chat': text}
                    self.sock.sendall(json.dumps(msg).encode())
                    text_widget.config(state='normal')
                    text_widget.insert(tk.END, f"Me: {text}\n")
                    text_widget.config(state='disabled')
                    text_widget.see(tk.END)
                except:
                    pass
                entry.delete(0, tk.END)
        tk.Button(win, text="Send", command=send_back).pack(side=tk.LEFT, pady=4)
        def on_close():
            del self.private_chats[sender_id]
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)
        self.private_chats[sender_id] = (win, text_widget, entry)

    def update_latest_chats(self, chat):
        # chat is a list of dicts: {id, msg}
        for msg in chat:
            self.latest_chats[msg['id']] = msg['msg']

    def update_blobs(self, positions):
        self.canvas.delete('all')
        colors = ['red', 'blue', 'green', 'orange', 'purple', 'cyan', 'magenta', 'yellow']
        # Always ensure my own blob is present
        if self.my_id and self.my_id not in positions:
            positions[self.my_id] = self.my_pos
        # Save positions for click detection
        self.last_positions = {}
        # Draw Fun Room box
        box_w, box_h = 120, 60
        canvas_w = int(self.canvas['width'])
        canvas_h = int(self.canvas['height'])
        box_x1 = canvas_w - box_w - 10
        box_y1 = canvas_h - box_h - 10
        box_x2 = canvas_w - 10
        box_y2 = canvas_h - 10
        self.canvas.create_rectangle(box_x1, box_y1, box_x2, box_y2, fill='black')
        self.canvas.create_text((box_x1+box_x2)//2, (box_y1+box_y2)//2, text='Fun Room', fill='white', font=('Arial', 14, 'bold'))
        # Draw blobs
        for i, (client_id, pos) in enumerate(positions.items()):
            color = colors[i % len(colors)]
            x, y = pos['x'], pos['y']
            nick = pos.get('nick', f"Blob {client_id}")
            self.last_positions[client_id] = {'x': x, 'y': y, 'nick': nick}
            self.canvas.create_oval(x-BLOB_RADIUS, y-BLOB_RADIUS, x+BLOB_RADIUS, y+BLOB_RADIUS, fill=color)
            # Draw nickname in the center
            self.canvas.create_text(x, y, text=nick, fill='white', font=('Arial', 12, 'bold'))
        # If window chat, update chat box
        if self.window_chat:
            self.update_window_chat()
        else:
            # Draw speech bubbles as before
            for i, (client_id, pos) in enumerate(positions.items()):
                x, y = pos['x'], pos['y']
                chat_msg = self.latest_chats.get(client_id)
                if chat_msg:
                    bubble_x = x
                    bubble_y = y - BLOB_RADIUS - 25
                    self.canvas.create_oval(bubble_x-60, bubble_y-20, bubble_x+60, bubble_y+20, fill='white', outline='black')
                    self.canvas.create_text(bubble_x, bubble_y, text=chat_msg, fill='black', font=('Arial', 10), width=110)
        # Check for collision with Fun Room for my blob
        if self.my_id in positions:
            my_x, my_y = positions[self.my_id]['x'], positions[self.my_id]['y']
            if (box_x1 < my_x < box_x2) and (box_y1 < my_y < box_y2):
                self.show_fun_room_popup()

    def show_fun_room_popup(self):
        if hasattr(self, '_fun_room_popup_open') and self._fun_room_popup_open:
            return
        self._fun_room_popup_open = True
        popup = tk.Toplevel(self.master)
        popup.title('Fun Room')
        popup.geometry('260x120')
        tk.Label(popup, text='Do you want to play a game?', font=('Arial', 13, 'bold')).pack(pady=12)
        def close_popup():
            self._fun_room_popup_open = False
            popup.destroy()
        tk.Button(popup, text='Yes', command=close_popup, width=8).pack(side=tk.LEFT, padx=30, pady=10)
        tk.Button(popup, text='No', command=close_popup, width=8).pack(side=tk.RIGHT, padx=30, pady=10)

    def update_window_chat(self):
        # Show all chat messages in the chat box
        self.chat_box.config(state='normal')
        self.chat_box.delete(1.0, tk.END)
        # Show all messages as nickname: text
        for client_id, msg in self.latest_chats.items():
            nick = self.last_positions.get(client_id, {}).get('nick', f"Blob {client_id}")
            self.chat_box.insert(tk.END, f"{nick}: {msg}\n")
        self.chat_box.config(state='disabled')
        self.chat_box.see(tk.END)

    def on_canvas_click(self, event):
        # Check if click is inside any blob
        for client_id, info in self.last_positions.items():
            x, y = info['x'], info['y']
            if (event.x - x) ** 2 + (event.y - y) ** 2 <= BLOB_RADIUS ** 2:
                # Show popup with info
                self.show_blob_info(client_id, info)
                break

    def show_blob_info(self, client_id, info):
        popup = tk.Toplevel(self.master)
        popup.title(f"Blob Info: {info['nick']}")
        popup.geometry("300x180")
        chat_msg = self.latest_chats.get(client_id, "(no message)")
        tk.Label(popup, text=f"Name: {info['nick']}", font=('Arial', 12, 'bold')).pack(pady=5)
        tk.Label(popup, text=f"Position: ({info['x']}, {info['y']})").pack(pady=2)
        tk.Label(popup, text=f"Last message: {chat_msg}", wraplength=260).pack(pady=2)

        # Private chat entry
        priv_frame = tk.Frame(popup)
        priv_frame.pack(pady=4)
        priv_entry = tk.Entry(priv_frame, width=22)
        priv_entry.pack(side=tk.LEFT, padx=2)
        def send_private():
            text = priv_entry.get().strip()
            if text:
                try:
                    msg = {'private': client_id, 'chat': text}
                    self.sock.sendall(json.dumps(msg).encode())
                except:
                    pass
                priv_entry.delete(0, tk.END)
        tk.Button(priv_frame, text="Send Private", command=send_private).pack(side=tk.LEFT)

        tk.Button(popup, text="Close", command=popup.destroy).pack(pady=8)

    # No longer needed: update_chat

def move_blobs_with_push(blob_positions, my_id, dx, dy):
    """
    Move the blob with my_id by (dx, dy). If another blob is at the new position, push it (and any blobs in a line) in the same direction.
    blob_positions: dict of client_id -> {'x': int, 'y': int, ...}
    Returns: dict of client_id -> new positions
    """
    # Copy positions to avoid mutating input
    positions = {cid: dict(pos) for cid, pos in blob_positions.items()}
    def push(cid, dx, dy):
        # Move this blob
        positions[cid]['x'] += dx
        positions[cid]['y'] += dy
        # Check for other blobs at new position (excluding self)
        for other_id, pos in positions.items():
            if other_id == cid:
                continue
            if abs(pos['x'] - positions[cid]['x']) <= BLOB_RADIUS and abs(pos['y'] - positions[cid]['y']) <= BLOB_RADIUS:
                push(other_id, dx, dy)
    push(my_id, dx, dy)
    return positions

# Example usage:
# new_positions = move_blobs_with_push(current_positions, my_id, dx, dy)
# Then send new_positions[my_id] to the server as your new position.

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Blob Client")
    app = BlobClient(root, NICK, WINDOW_CHAT)
    root.mainloop()
