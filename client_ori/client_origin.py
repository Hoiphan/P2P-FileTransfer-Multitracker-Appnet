import socket
import threading
import os
import pickle
import tqdm
from pathlib import Path
from math import ceil

SERVER_HOST = '127.0.0.1'  
SERVER_PORT = 8000        
BUFSIZE = 1024
CHUNK_SIZE = 512

class Server:
    server: socket.socket
    list_peers_addr: list[(str, int)]
    user = None
    
    def __init__(self):
        self.server_addr = (SERVER_HOST, SERVER_PORT)
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        self.list_peers_addr = list[tuple[str, int]]()
        
        
    def __del__(self):
        self.server.close()
        
    def run(self):
        self.server.connect(self.server_addr)
        print(f'Connecting to server {self.server_addr[0]}:{self.server_addr[1]}')
        
    def login(self, username, password, peer_addr):
        request = {
            "type": "request",
            "action": "login",
            "payload": {
                "username": username,
                "password": password,
                "peer_addr": peer_addr,
            },
        }
        self.server.send(pickle.dumps(request))
        
        response = pickle.loads(self.server.recv(BUFSIZE))
        if response["status"] == 200:
            self.user = username
        print(response["payload"])

    def logout(self):
        request = {
            "type": "request",
            "user": self.user,
            "action": "logout",
        }
        self.server.send(pickle.dumps(request))
        
        response = pickle.loads(self.server.recv(BUFSIZE))
        print(response["payload"])
        
        self.user = None
    
    def get_peer_info(self):
        request = {
            "type": "request",
            "user": self.user,
            "action": "get_peer_info",
        }   
        self.server.send(pickle.dumps(request))
    
        response = pickle.loads(self.server.recv(BUFSIZE))
        if response["status"] == 401:
            print(response["payload"])
            
        else:
            self.list_peers_addr = response["payload"]
    
class Peer:
    peer: socket.socket
    available_files: dict[(str, int), set[(str, int)]] # dict[(filename, size), set[peer_addr]]
    server: Server
    
    def __init__(self, server: Server):
        self.peer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.peer.bind(('127.0.0.1', 0))
        
        self.available_files = dict[tuple[str, int], set[tuple[str, int]]]()
        self.server = server
        
    def __del__(self):
        self.peer.close()
    
    def run(self):
        self.peer.listen(10)
        self.accept_thread = threading.Thread(target=self.accept_connection)
        self.accept_thread.start()

    def accept_connection(self):
        while True:
            peer, peer_addr = self.peer.accept()
            peer_thread = threading.Thread(target=self.listen_peer, args=(peer,))
            peer_thread.start()
            
    def listen_peer(self, peer: socket.socket):
        while True:
            resquest = pickle.loads(peer.recv(BUFSIZE))
            if resquest["action"] == "fetch_file":
                payload = resquest["payload"]
                
                file = Read_File(payload["filename"], payload["size"])
                data = file.read(payload["chunk_no"])
                
                response = {
                    "type": "response",
                    "status": 200,
                    "action": "fetch_file",
                    "payload": {
                        "filename": payload["filename"],
                        "size": payload["size"],
                        "chunk_no": payload["chunk_no"],
                        "data": data
                    },
                }
                peer.send(pickle.dumps(response))
                
                del file
            
            elif resquest["action"] == "get_shared_file":
                list_files_res = list[tuple[str, int]]()
                
                path_folder = Path.joinpath(Path(__file__).parent, "shared_files")
                files = os.listdir(path_folder)
                for file in files:
                    fileSize = os.path.getsize(Path.joinpath(path_folder, file))
                    list_files_res.append((file, fileSize))
                    
                response = {
                    "type": "response",
                    "status": 200,
                    "action": "get_shared_file",
                    "payload": list_files_res,
                }
                peer.send(pickle.dumps(response))
                
                
            elif resquest["action"] == "close_conn":
                peer.close()
                break

    def get_available_files(self):
        
        running_thread = list[threading.Thread]()
        new_available_files = dict[tuple[str, int], set[tuple[str, int]]]()
        
        for peer_addr in self.server.list_peers_addr:
            if peer_addr == self.peer.getsockname():
                continue
            
            peer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer.connect(peer_addr)
            
            peer_thread = threading.Thread(target=self.get_shared_file, args=(peer, new_available_files))
            peer_thread.start()
            running_thread.append(peer_thread)
            
        for thread in running_thread:
            thread.join()
            
        self.available_files = new_available_files
            
    def get_shared_file(self, peer: socket.socket, new_available_files: dict[tuple[str, int], set[tuple[str, int]]]):
        resquest = {
            "type": "request",
            "action": "get_shared_file",
        }
        peer.send(pickle.dumps(resquest))
        response = pickle.loads(peer.recv(BUFSIZE))
        for file in response["payload"]:
            if file in new_available_files:
                new_available_files[file].add(peer.getpeername())
            else:
                new_available_files[file] = set([peer.getpeername()])
                
        peer.send(pickle.dumps({
            "type": "request",
            "action": "close_conn",
        }))
        peer.close()

class Read_File:
    filename: str
    size: int
    path_folder: str
    
    chunk_size = CHUNK_SIZE
    
    def __init__(self, filename, size):
        self.filename = filename
        self.size = size
        self.path_folder = Path.joinpath(Path(__file__).parent, "shared_files")
        
    def read(self, chunk_no):
        file = open(Path.joinpath(self.path_folder, self.filename), "rb")
        file.seek(chunk_no * self.chunk_size, 0)
        data = file.read(self.chunk_size)
        return data
           
class Fetch_File:
    filename: str
    size: int
    path_folder: str
    
    total_chunk: int
    current_chunk: int
    chunk_data: list[str]
    
    peers: list[socket.socket]
    
    chunk_size = CHUNK_SIZE
        
    def __init__(self, filename, size, available_files):
        self.filename = filename
        self.size = size
        self.path_folder = Path.joinpath(Path(__file__).parent, "shared_files")
        
        self.init_chunk()
        
        self.peers = list[socket.socket]()
        
        if (filename, size) in available_files:
            peers_addr = available_files[(filename, size)]
        else:
            peers_addr = set[tuple[str, int]]()
            
        for peer_addr in peers_addr:
            p = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            p.connect(peer_addr)
            self.peers.append(p)
        
    def __del__(self):
        for peer in self.peers:
            peer.close()
    
    def init_chunk(self):
        self.total_chunk = ceil(self.size / self.chunk_size)
        self.current_chunk = 0
        self.chunk_data = [b""] * self.total_chunk
        
        self.is_access_cur_chunk = False
        
    def get_chunk_no(self) -> int:
    # Handling the race condition of variable current_chunk.
        while self.is_access_cur_chunk:
            pass
        
        self.is_access_cur_chunk = True
        
        chunk_no = self.current_chunk
        if self.current_chunk < self.total_chunk:
            self.current_chunk += 1
        
        self.is_access_cur_chunk = False
            
        return chunk_no
    
    def fetch_file(self):
        if not self.peers:
            print("File not found.")
            return
        
        running_thread = list[threading.Thread]()
        progress = tqdm.tqdm(unit="B", unit_scale=True, unit_divisor=1000, total=self.size, desc=self.filename)
        
        for peer in self.peers:
            fetch_thread = threading.Thread(target=self.fetch_chunk, args=(peer, progress,))
            fetch_thread.start()
            running_thread.append(fetch_thread)
            
        for fetch_thread in running_thread:
            fetch_thread.join()
            
        file = open(Path.joinpath(self.path_folder, self.filename), "wb")
        
        for data in self.chunk_data:
            file.write(data)
            
        file.close()
        
        # print(f"Fetch file {self.filename} successfully.")
    
    def fetch_chunk(self, peer: socket.socket, progress: tqdm.tqdm):
        while True:
            chunk_no = self.get_chunk_no()
            
            if chunk_no < self.total_chunk:
                resquest = {
                    "type": "request",
                    "action": "fetch_file",
                    "payload": {
                        "filename": self.filename,
                        "size": self.size,
                        "chunk_no": chunk_no
                    },
                }
                peer.send(pickle.dumps(resquest))
                
                response = pickle.loads(peer.recv(BUFSIZE))
                
                data = response["payload"]["data"]
                self.chunk_data[chunk_no] = data
                
                progress.update(self.chunk_size)
                
            else:
                resquest = {
                    "type": "request",
                    "action": "close_conn",
                }
                peer.send(pickle.dumps(resquest))
                peer.close()
                break                           

if __name__ == "__main__":
    try:
        server = Server()
        server.run()
        peer = Peer(server) 
        peer.run()
       
        print("Give one of the commands:")
        print("1|login: Log in to server")
        print("2|get_peer: Get list of peers in network")
        print("3|get_available_files: Get the list of available files in network")
        print("4|fetch_file: Download file from peers in network")
        print("5|logout: Log out from server")
        print("6|close: Close connection with server and exit program\n\n")
        
        while True:
            inp = input(">>")
            if inp == "login" or inp == "1":
                if server.user is None:
                    username = input("username: ")
                    password = input("password: ")
                    
                    server.login(username, password, peer.peer.getsockname())
                    
                else:
                    print("You are already logged in, so cannot log in again.")
             
            elif inp == "get_peer" or inp == "2":
                server.get_peer_info()
                print(server.list_peers_addr)
                    
            elif inp == "get_available_files" or inp == "3":
                server.get_peer_info()
                peer.get_available_files()
                print(peer.available_files)
                
            elif inp == "fetch_file" or inp == "4": 
                server.get_peer_info()
                peer.get_available_files()
                  
                filename = input("filename: ")
                size = int(input("size: "))
                
                file = Fetch_File(filename, size, peer.available_files)
                file.fetch_file()
                del file
                
            elif inp == "logout" or inp == "5":
                if server.user is None:
                    print("You are not logged in, so cannot log out.")
                    
                else:
                    server.logout()
                    
            elif inp == "close" or inp == "6":
                os._exit(0)
                
    except KeyboardInterrupt:
        os._exit(0)