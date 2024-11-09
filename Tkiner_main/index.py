# import modules

from tkinter import *
import os
from tkinter import filedialog
from tkinter import filedialog, messagebox


# Designing Main(first) window
def main_account_screen():
    global main_screen
    main_screen = Tk()
    main_screen.geometry("500x500+500+100")
    main_screen.title("App Sharing File")
    Label(
        text="Select Your Choice",
        bg="red",
        width="300",
        height="2",
        font=("Calibri", 13),
    ).pack()
    Label(text="").pack()
    Button(text="Login", height="2", width="30", command=login).pack()

    main_screen.mainloop()


# Designing popup for User_screen
def User():
    global user_screen
    user_screen = Tk()
    user_screen.geometry("500x500+500+100")
    user_screen.title("User")
    Label(
        user_screen,
        text="Welcom to my app",
        bg="red",
        width="300",
        height="2",
        font=("Calibri", 13),
    ).pack()

    Logout = Button(
        user_screen, text="LOGOUT", height="2", width="15", bg="red", command=logout
    )

    Logout.pack(side=BOTTOM, anchor="e", padx=10, pady=10)

    # Upload file to local
    upload_button = Button(
        user_screen,
        text="Sharing Your File To EveryOne",
        height="2",
        width="30",
        bg="green",
        command=share_file,
    )
    upload_button.pack(pady=20)

    # Show available file to local
    show_avai_file = Button(
        user_screen,
        text="Show All Files Available in Bitoorent App",
        height="2",
        width="30",
        bg="green",
        command=list_files,
    )
    show_avai_file.pack(pady=20)

    # Dowload file to local

    global File_Entry
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
    Button(
        user_screen, text="Submit", width=10, height=1, pady=5, command=receive_file
    ).pack()

    main_screen.destroy()
    user_screen.mainloop()


def receive_file():
    File_name = str(File_Entry.get())
    File_Entry.delete(0, END)
    print(File_name)
    messagebox.showinfo(
        "Success", f"Your {File_name} Required File Download sucessfully!!!!"
    )


def list_files():
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

    # Check if the directory exists
    path = os.path.join(os.getcwd(), "FileShared")
    if not os.path.exists(path):
        messagebox.showerror("Error", f"Directory '{path}' does not exist.")
        return

    dir_list = os.listdir(path)
    print("Files and directories in '", path, "' :")
    print(dir_list)

    # Add labels in two columns
    for index, i in enumerate(dir_list):
        # Create a beautiful label
        label = Label(
            label_frame,
            text=str(i),
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

    def update_scrollregion(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    # Bind the update function to the label_frame's size change
    label_frame.bind("<Configure>", update_scrollregion)


def share_file():
    # Open a file dialog to select a file
    file_path = filedialog.askopenfilename(title="Select a file")

    if file_path:
        # Define the save path in the current directory
        save_dir = os.path.join(os.getcwd(), "FileShared")
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


def logout():
    user_screen.destroy()
    main_account_screen()


def login():
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
    Button(login_screen, text="Login", width=10, height=1, command=login_verify).pack()


def login_verify():
    username1 = username_verify.get()
    password1 = password_verify.get()
    username_login_entry.delete(0, END)
    password_login_entry.delete(0, END)

    list_of_files = os.listdir()
    if username1 in list_of_files:
        file1 = open(username1, "r")
        verify = file1.read().splitlines()
        if password1 in verify:
            User()

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
    Label(user_not_found_screen, text="User Not Found").pack()
    Button(
        user_not_found_screen, text="OK", command=delete_user_not_found_screen
    ).pack()


# Deleting popups
def delete_user_not_found_screen():
    user_not_found_screen.destroy()


if __name__ == "__main__":
    main_account_screen()
