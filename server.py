import socket
import threading
import json
import os
import pickle
from pathlib import Path

HOST = '127.0.0.1'  
PORT = 8000        
BUFSIZE = 1024

class Server:
    server: socket.socket
    connections: dict[str, tuple[socket.socket, (str, int)]]  # dict[username, (socket, peer_addr)]
    
    def __init__(self):
        self.addr = (HOST, PORT)
        self.connections = dict[str, tuple[socket.socket, tuple[str, int]]]()
        
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(self.addr)
        self.server.listen(10)
        
        print(f"Server is running on {self.addr[0]}:{self.addr[1]}")
        
    def __del__(self):
        self.server.close()
    
    def run(self):
        self.accept_thread = threading.Thread(target=self.accept_connection)
        self.accept_thread.start()   
                
    def accept_connection(self):
        while True:
            client, client_addr = self.server.accept()
            print(f"{client_addr[0]}:{client_addr[1]} has connected.")
            client_thread = threading.Thread(target=self.recv_req, args=(client,))
            client_thread.start()
    
    def recv_req(self, client: socket.socket):
        while True:
            try:
                request = pickle.loads(client.recv(BUFSIZE))
                if request["action"] == "login":
                    self.login(request["payload"], client)
                    
                elif request["action"] == "logout":
                    self.logout(request["user"], client)
                
                elif request["action"] == "get_peer_info":
                    self.send_peer_info(request, client)
                
                elif request["action"] == "close_conn":
                    client.close()
            except:
                self.handle_suddenly_exit(client)
                client.close()
                break
    
    def login(self, payload, client: socket.socket):
        username = payload["username"]
        password = payload["password"]

        response = {
            "type": "respone",
            "action": "login",
        }
        
        # check username is logged in
        if username in self.connections:
            response["status"] = 400
            response["payload"] = "The user is already logged in on another device."
            
            client.send(pickle.dumps(response))
            return
         
        with open(f'{Path(__file__).parent}/account.json', 'r') as db:
            account = json.load(db)

        for acc in account:
            if username == acc["username"] and password == acc["password"]:
                self.connections[username] = (client, payload["peer_addr"])
                
                response["status"] = 200
                response["payload"] = f"User {username} log in successfully."
                
                client.send(pickle.dumps(response))
                return
            
        response["status"] = 400
        response["payload"] = "The username or password is incorrect."
              
        client.send(pickle.dumps(response))
       
    def logout(self, username: str, client: socket.socket):
        del self.connections[username]
            
        response = {
            "type": "respone",
            "status": 200,
            "action": "logout",
            "payload": "User log out successfully."
        }
        client.send(pickle.dumps(response))           
             
    def send_peer_info(self, request, client: socket.socket):
        response = {
                "type": "respone",
                "action": "get_peer_info",
            }
        if request["user"] is None or not request["user"] in self.connections:
            response["status"] = 401
            response["payload"] = "The user is not authenticated."
            
        else:
            peer_info = list()
            for conn in self.connections.values():
                peer_info.append(conn[1])
            response["status"] = 200
            response["payload"] = peer_info
            
        client.send(pickle.dumps(response))
      
    def handle_suddenly_exit(self, client: socket.socket):
        connections = self.connections.copy()
        for conn in self.connections:
            if self.connections[conn][0] == client:
                del connections[conn]
        self.connections = connections

if __name__ == "__main__":
    try: 
        server = Server()
        server.run()
        inp = input()
        if inp == "close":
            os._exit(0)

    except KeyboardInterrupt:
        os._exit(0)
        