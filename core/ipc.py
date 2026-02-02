import socket
import os
import threading
import logging

logger = logging.getLogger(__name__)

SOCKET_PATH = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "vocalis.sock")

class IPCServer:
    def __init__(self, callback):
        self.callback = callback
        self.running = False
        self.thread = None

    def start(self):
        if os.path.exists(SOCKET_PATH):
            try:
                os.unlink(SOCKET_PATH)
            except OSError:
                logger.error("Could not remove old socket")
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(SOCKET_PATH)
            server.listen(1)
            server.settimeout(1.0) # Check self.running periodically
            while self.running:
                try:
                    conn, _ = server.accept()
                    with conn:
                        data = conn.recv(1024)
                        if data:
                            command = data.decode('utf-8')
                            self.callback(command)
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"IPC Error: {e}")

    def stop(self):
        self.running = False
        # Wake up accept by connecting to self
        try:
             with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as c:
                 c.connect(SOCKET_PATH)
        except:
             pass
             
        if os.path.exists(SOCKET_PATH):
            try:
                os.unlink(SOCKET_PATH)
            except OSError:
                pass

def send_signal(command="TOGGLE"):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(SOCKET_PATH)
            client.sendall(command.encode())
            return True
    except Exception as e:
        logger.debug(f"IPC Send Error: {e}")
        return False
