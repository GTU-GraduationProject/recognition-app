import subprocess
import requests
import time
from tkinter import *
from tkinter import messagebox
from tkinter import ttk,Tk

def login():
    username = str(entry_username.get())
    password = str(entry_password.get())

    # İstek gönderilecek backend URL'si
    url = "https://recognition-items-backend.up.railway.app/login"  # Backend URL'sini buraya yazın

    # İstek gövdesi
    data = {
        "username": username,
        "password": password
    }

    # İstek gönderme
    response = requests.post(url, json=data)

    # İstek sonucunu kontrol etme
    if response.status_code == 200:
        
        json_response = response.json()
        role = json_response["role"]
        name = json_response["name"]
        surname = json_response["surname"]
        
        auth_token = json_response["token"]

        if(role == "CASHIER"):
            messagebox.showinfo("Logged Successfully", "Welcome, {} {}".format(name,surname))
            root.withdraw()  # Birinci pencereyi gizle
            open_new_window(username, auth_token)
            
        else:
            messagebox.showerror("Error", "Only cashiers can use this application.")
    else:
        messagebox.showerror("Error", "Incorrect username or password.")


def open_new_window(username, auth_token):
    new_window = Toplevel(root)
    new_window.title("Cashier")
    
    window_width = 300
    window_height = 50
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = int((screen_width / 2) - (window_width / 2))  # Pencereyi yatayda ortala
    y = int((screen_height / 2) - (window_height / 2))  # Pencereyi dikeyde ortala
    new_window.geometry(f"{window_width}x{window_height}+{x}+{y}")  # Pencere boyutunu ve konumunu ayarla

    # Yeni sayfa içeriği ve bileşenleri ekleme
    label_message = Label(new_window, text="\n\nPlease wait... Camera will be open soon...\nTo quit camera, press 'q'\n\n")
    label_message.pack()
    
    root.after(1000, lambda: execute_command(username, auth_token, new_window, label_message))
    
    
def execute_command(username, auth_token, window, label):
    dosya = "detect.py"
    argumanlar = "--source 0 --weights best.pt --img 512 --conf 0.5 --cashier-id " + username + " --auth-token " + auth_token

    #subprocess.call(f"python {dosya} {argumanlar}", shell=True)

    process = subprocess.Popen(["python", dosya] + argumanlar.split(), shell=True)
    time.sleep(10)
    process.communicate()  # İşlemin tamamlanmasını bekler

    window.destroy()  # Kamera penceresini kapat

    root.destroy()  # Login penceresini kapat
    goodbye_window()

def goodbye_window():
    goodbye = Tk()
    goodbye.title("Goodbye!")


    window_width = 300
    window_height = 50
    screen_width = goodbye.winfo_screenwidth()
    screen_height = goodbye.winfo_screenheight()
    x = int((screen_width / 2) - (window_width / 2))  # Pencereyi yatayda ortala
    y = int((screen_height / 2) - (window_height / 2))  # Pencereyi dikeyde ortala
    goodbye.geometry(f"{window_width}x{window_height}+{x}+{y}")  # Pencere boyutunu ve konumunu ayarla


    label_goodbye = Label(goodbye, text="\n\nGoodbye!\nTo quit, press X :))\n\n")
    label_goodbye.pack()

    goodbye.mainloop()


root = Tk()
root.title("Login")
root.resizable(False, False)  # Yatay ve dikey boyutlandırmayı devre dışı bırakır


# Stil uygulamak için ttk kullanımı
style = ttk.Style(root)
style.configure("TLabel", font=("Arial", 12))  # Etiketler için stil
style.configure("TEntry", font=("Arial", 12))  # Giriş alanları için stil
style.configure("TButton", font=("Arial", 12))  # Düğme için stil

# Kullanıcı adı giriş alanı
label_username = ttk.Label(root, text="Username:")
label_username.grid(row=0, column=0, padx=10, pady=5)
entry_username = ttk.Entry(root)
entry_username.grid(row=0, column=1, padx=10, pady=5)

# Parola giriş alanı
label_password = ttk.Label(root, text="Password:")
label_password.grid(row=1, column=0, padx=10, pady=5)
entry_password = ttk.Entry(root, show="*")
entry_password.grid(row=1, column=1, padx=10, pady=5)

# Giriş düğmesi
button_login = ttk.Button(root, text="Login", command=login)
button_login.grid(row=2, column=0, columnspan=2, padx=10, pady=5)

# Pencereyi çalıştırma
root.mainloop()
