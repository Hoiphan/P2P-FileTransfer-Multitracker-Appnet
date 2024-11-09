import socket
import threading
import os
import pickle
import tqdm
from pathlib import Path
from math import ceil

from tkinter import *
import os
from tkinter import filedialog
from tkinter import filedialog, messagebox


CLIENT_PORT_RECIEVE = 51
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
BUFSIZE = 1024
CHUNK_SIZE = 512


#######Backend#######################################


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
        print(f"Connecting to server {self.server_addr[0]}:{self.server_addr[1]}")

    def login(self, username, password, peer_addr) -> int:
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
            print("Login sucessfully")
            return 200
        else:
            print(response["payload"])
            return 500

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
    available_files: dict[
        (str, int), set[(str, int)]
    ]  # dict[(filename, size), set[peer_addr]]
    server: Server

    def __init__(self, server: Server):
        self.peer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.peer.bind(("127.0.0.1", CLIENT_PORT_RECIEVE))

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
                        "data": data,
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

            peer_thread = threading.Thread(
                target=self.get_shared_file, args=(peer, new_available_files)
            )
            peer_thread.start()
            running_thread.append(peer_thread)

        for thread in running_thread:
            thread.join()

        self.available_files = new_available_files

    def get_shared_file(
        self,
        peer: socket.socket,
        new_available_files: dict[tuple[str, int], set[tuple[str, int]]],
    ):
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

        peer.send(
            pickle.dumps(
                {
                    "type": "request",
                    "action": "close_conn",
                }
            )
        )
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
        self.path_folder = Path.joinpath(Path(__file__).parent, "received_files")

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
        progress = tqdm.tqdm(
            unit="B",
            unit_scale=True,
            unit_divisor=1000,
            total=self.size,
            desc=self.filename,
        )

        for peer in self.peers:
            fetch_thread = threading.Thread(
                target=self.fetch_chunk,
                args=(
                    peer,
                    progress,
                ),
            )
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
                        "chunk_no": chunk_no,
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


##########################################################################################

###### Tinker #############################################


# Designing Main(first) window
def main_account_screen(server: Server, peer: Peer):
    global main_screen
    main_screen = Tk()
    main_screen.geometry("500x500+500+100")
    main_screen.title("App Sharing File")
    Label(
        text="App Bitorrent 📡😎💌",
        bg="yellow",
        width="300",
        height="2",
        font=("Calibri", 13),
    ).pack()
    Label(text="").pack()
    Button(
        text="Login",
        height="2",
        width="30",
        bg="green",
        command=lambda: login(server, peer),
    ).pack()
    Button(
        text="Exit Programe",
        height="2",
        width="30",
        bg="red",
        command=exit_programe,
    ).pack(side=BOTTOM, anchor="e", padx=10, pady=10)

    main_screen.mainloop()


# Designing popup for User_screen
def User(server: Server, peer: Peer):
    global user_screen
    user_screen = Tk()
    user_screen.geometry("500x500+500+100")
    user_screen.title("User")
    Label(
        user_screen,
        text=f"Welcom to my app {server.user} 🎉🎉",
        bg="yellow",
        width="300",
        height="2",
        font=("Calibri", 13),
    ).pack()

    Logout = Button(
        user_screen,
        text="LOGOUT",
        height="2",
        width="15",
        bg="red",
        command=lambda: logout(server, peer),
    )

    Logout.pack(side=BOTTOM, anchor="e", padx=10, pady=10)

    upload_button = Button(
        user_screen,
        text="Sharing Your File To EveryOne",
        height="2",
        width="30",
        bg="green",
        command=share_file,
    )
    upload_button.pack(pady=20)

    show_avai_file = Button(
        user_screen,
        text="Show All Files Available in Bitoorent App",
        height="2",
        width="30",
        bg="green",
        command=lambda: list_files(server, peer),
    )
    show_avai_file.pack(pady=20)

    global File_Entry
    global Bytes_Entry
    Label(user_screen, text="File Want To Download * ").pack()
    File_Entry = Entry(
        user_screen,
        font=("Helvetica", 12, "bold"),
        bg="lightblue",
        fg="darkblue",
        borderwidth=2,
        relief="groove",
    )
    File_Entry.pack()
    Label(user_screen, text="Size * ").pack()
    Bytes_Entry = Entry(
        user_screen,
        font=("Helvetica", 12, "bold"),
        bg="lightblue",
        fg="darkblue",
        borderwidth=2,
        relief="groove",
    )
    Bytes_Entry.pack()
    Button(
        user_screen,
        text="Submit",
        width=10,
        height=1,
        pady=5,
        command=lambda: receive_file(server, peer),
    ).pack()

    main_screen.destroy()
    user_screen.mainloop()


def receive_file(server: Server, peer: Peer):

    try:
        server.get_peer_info()
        peer.get_available_files()
        File_name = str(File_Entry.get())
        File_Entry.delete(0, END)
        Bytes = int(Bytes_Entry.get())
        Bytes_Entry.delete(0, END)

        # Check if the filename is in the available files
        print(peer.available_files)
        if (File_name, Bytes) not in peer.available_files:
            print(f"Error: {File_name} is not available.")
            messagebox.showinfo(
                "Fail", f"Your {File_name} or Size {Bytes} bytes is not availbale"
            )
        else:
            file = Fetch_File(File_name, Bytes, peer.available_files)
            file.fetch_file()
            del file
            messagebox.showinfo(
                "Sucess", f"Your {File_name} has downloaded sucessfully!!!!"
            )

    except ValueError:
        print("Invalid size. Please enter a valid integer.")
        messagebox.showinfo("Fail", f"Invalid size. Please enter a valid integer.")

    except Exception as e:
        print(f"An error occurred: {e}")
        messagebox.showinfo("Fail", f"An error occurred: {e}")


## List_available files
def list_files(server: Server, peer: Peer):
    server.get_peer_info()
    peer.get_available_files()
    print(peer.available_files)
    Avai_files = peer.available_files

    global List_files
    List_files = Toplevel(user_screen)
    List_files.title("Available Files")
    List_files.geometry("600x500+600+200")

    # Create a frame for the scrollbar and canvas
    frame = Frame(List_files)
    frame.pack(fill=BOTH, expand=True)

    # Create a canvas to hold the labels
    canvas = Canvas(frame)
    canvas.pack(side=LEFT, fill=BOTH, expand=True)

    # Create a scrollbar and attach it to the canvas
    scrollbar = Scrollbar(frame, orient="vertical", command=canvas.yview)
    scrollbar.pack(side=RIGHT, fill=Y)

    canvas.configure(yscrollcommand=scrollbar.set)

    # Create another frame inside the canvas to hold the labels
    label_frame = Frame(canvas)
    canvas.create_window((0, 0), window=label_frame, anchor="nw")

    index = 0

    if Avai_files == {}:
        Label(label_frame, text="None file have shared !!!").pack()

    else:
        for (filename, size), peers in Avai_files.items():
            # Create a beautiful label
            label = Label(
                label_frame,
                text=f"{filename} ** Size:{size} bytes",
                font=("Helvetica", 12, "bold"),
                bg="lightblue",
                fg="darkblue",
                padx=10,
                pady=5,
                borderwidth=2,
                relief="groove",
            )
            # Use grid to arrange labels in two columns
            column = index % 2  # 0 for the first column, 1 for the second column
            row = index // 2  # Increment the row after every two items
            label.grid(
                row=row, column=column, padx=5, pady=5, sticky="w"
            )  # Sticky 'w' for left alignment
            index += 1

    def update_scrollregion(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    # Bind the update function to the label_frame's size change
    label_frame.bind("<Configure>", update_scrollregion)


# Import your file to folder shared_files
def share_file():
    # Open a file dialog to select a file
    file_path = filedialog.askopenfilename(title="Select a file")

    if file_path:
        # Define the save path in the current directory
        save_dir = os.path.join(os.getcwd(), "shared_files")
        os.makedirs(save_dir, exist_ok=True)  # Create the directory if it doesn't exist
        save_path = os.path.join(save_dir, os.path.basename(file_path))

        try:
            # Open the selected file and save it to the new path
            with open(file_path, "rb") as source_file:
                with open(save_path, "wb") as dest_file:
                    dest_file.write(source_file.read())
            # messagebox.showinfo("Success", f"File saved to: {save_path}")
            messagebox.showinfo("Success", f"Thank You For Your Support <3")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {e}")


def logout(server: Server, peer: Peer):
    server.logout()
    user_screen.destroy()
    main_account_screen(server, peer)


def exit_programe():
    os._exit(0)


def login(server: Server, peer: Peer):
    global login_screen
    login_screen = Toplevel(main_screen)
    login_screen.title("Login")
    login_screen.geometry("300x250+600+200")
    Label(login_screen, text="Please enter details below to login").pack()
    Label(login_screen, text="").pack()

    global username_verify
    global password_verify

    username_verify = StringVar()
    password_verify = StringVar()

    global username_login_entry
    global password_login_entry

    Label(login_screen, text="Username * ").pack()
    username_login_entry = Entry(login_screen, textvariable=username_verify)
    username_login_entry.pack()
    Label(login_screen, text="").pack()
    Label(login_screen, text="Password * ").pack()
    password_login_entry = Entry(login_screen, textvariable=password_verify, show="*")
    password_login_entry.pack()
    Label(login_screen, text="").pack()
    Button(
        login_screen,
        text="Login",
        width=10,
        height=1,
        command=lambda: login_verify(server, peer),
    ).pack()


def login_verify(server: Server, peer: Peer):

    username = username_verify.get()
    password = password_verify.get()
    username_login_entry.delete(0, END)
    password_login_entry.delete(0, END)
    if server.user is None:
        status = server.login(username, password, peer.peer.getsockname())
        if status == 200:
            User(server, peer)
        else:
            user_not_found()

    else:
        user_not_found()


# Designing popup for user not found
def user_not_found():
    global user_not_found_screen
    user_not_found_screen = Toplevel(login_screen)
    user_not_found_screen.title("Success")
    user_not_found_screen.geometry("150x100+650+250")
    Label(user_not_found_screen, text="LOGIN FAIL!!!", bg="red").pack()
    Button(
        user_not_found_screen, text="OK", command=delete_user_not_found_screen
    ).pack()


# Deleting popups
def delete_user_not_found_screen():
    user_not_found_screen.destroy()


########################################################

if __name__ == "__main__":
    try:
        server = Server()
        server.run()
        peer = Peer(server)
        peer.run()
        main_account_screen(server, peer)

        # print("Give one of the commands:")
        # print("1|login: Log in to server")
        # print("2|get_peer: Get list of peers in network")
        # print("3|get_available_files: Get the list of available files in network")
        # print("4|fetch_file: Download file from peers in network")
        # print("5|logout: Log out from server")
        # print("6|close: Close connection with server and exit program\n\n")

        # while True:
        #     inp = input(">>")
        #     if inp == "login" or inp == "1":
        #         if server.user is None:
        #             username = input("username: ")
        #             password = input("password: ")

        #             server.login(username, password, peer.peer.getsockname())

        #         else:
        #             print("You are already logged in, so cannot log in again.")

        #     elif inp == "get_peer" or inp == "2":
        #         server.get_peer_info()
        #         print(server.list_peers_addr)

        #     elif inp == "get_available_files" or inp == "3":
        #         server.get_peer_info()
        #         peer.get_available_files()
        #         print(peer.available_files)

        #     elif inp == "fetch_file" or inp == "4":
        #         try:
        #             server.get_peer_info()
        #             peer.get_available_files()

        #             filename = input("filename: ")
        #             size = int(input("size: "))

        #             # Check if the filename is in the available files
        #             if (filename, size) not in peer.available_files:
        #                 print(f"Error: {filename} is not available.")
        #             else:
        #                 file = Fetch_File(filename, size, peer.available_files)
        #                 file.fetch_file()
        #                 del file
        #         except ValueError:
        #             print("Invalid size. Please enter a valid integer.")
        #         except Exception as e:
        #             print(f"An error occurred: {e}")

        #     elif inp == "logout" or inp == "5":
        #         if server.user is None:
        #             print("You are not logged in, so cannot log out.")

        #         else:
        #             server.logout()

        #     elif inp == "close" or inp == "6":
        #         os._exit(0)

    except KeyboardInterrupt:
        os._exit(0)
