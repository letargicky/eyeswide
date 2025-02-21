import socket
import threading
import hashlib
import json
import os
import socket

clients = {}  # {meno: socket}
USERS_FILE = "users.json"

# Načítanie alebo vytvorenie súboru users.json
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({}, f)

def load_users():
    """Načíta používateľov zo súboru"""
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    """Uloží používateľov do súboru"""
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def hash_password(password):
    """Hashuje heslo pomocou SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def log_and_broadcast(message):
    """Loguje správu a odošle ju všetkým klientom"""
    print(message)  # Tlačí log na server konzolu
    broadcast(message)  # Odošle správu všetkým klientom

def authenticate(client, username=None, password=None, register=False):
    """Spracováva registráciu a prihlásenie"""
    users = load_users()

    if username and password:
        if register:
            # Registrácia cez príkaz
            if username in users:
                client.send("❌ Tento účet už existuje! Skús iné meno.\n".encode())
                return None, False

            if len(username) < 4 or len(username) > 12:
                client.send("❌ Používateľské meno musí mať 4-12 znakov.\n".encode())
                return None, False

            users[username] = hash_password(password)
            save_users(users)
            client.send(f"✅ Úspešne si sa registroval ako {username}!\n".encode())
            log_and_broadcast(f"📝 {username} sa práve zaregistroval.")  # Log registrácie
            return username, True

        else:
            # Prihlásenie cez príkaz
            if username in users and users[username] == hash_password(password):
                log_and_broadcast(f"✅ {username} sa prihlásil.")  # Log prihlásenia
                return username, True
            else:
                return None, False

    while True:
        client.send("📜 Napíš 'register' na registráciu alebo 'login' na prihlásenie: ".encode())
        choice = client.recv(1024).decode().strip().lower()

        if choice == "register":
            client.send("✍️ Vyber si používateľské meno (4-12 znakov): ".encode())
            username = client.recv(1024).decode().strip()

            # Validácia mena
            if len(username) < 4 or len(username) > 12:
                client.send("❌ Používateľské meno musí mať 4-12 znakov.\n".encode())
                continue
            if username in users:
                client.send("❌ Tento účet už existuje! Skús iné meno.\n".encode())
                continue

            client.send("🔒 Zadaj heslo: ".encode())
            password = client.recv(1024).decode().strip()

            users[username] = hash_password(password)
            save_users(users)
            client.send(f"✅ Úspešne si sa registroval ako {username}!\n".encode())
            log_and_broadcast(f"📝 {username} sa práve zaregistroval.")  # Log registrácie
            return username, True

        elif choice == "login":
            client.send("👤 Používateľské meno: ".encode())
            username = client.recv(1024).decode().strip()

            # Validácia mena
            if len(username) < 4 or len(username) > 12:
                client.send("❌ Používateľské meno musí mať 4-12 znakov.\n".encode())
                continue

            if username not in users:
                client.send("❌ Tento účet neexistuje! Skús znova.\n".encode())
                continue

            client.send("🔑 Heslo: ".encode())
            password = client.recv(1024).decode().strip()

            if users[username] == hash_password(password):
                client.send(f"✅ Prihlásenie úspešné! Vitaj {username}!\n".encode())
                log_and_broadcast(f"✅ {username} sa prihlásil.")  # Log prihlásenia
                return username, True
            else:
                client.send("❌ Nesprávne heslo! Skús znova.\n".encode())

def broadcast(message, sender=None, private=False):
    """Odošle správu všetkým klientom okrem odosielateľa (alebo len vybraným)"""
    for user, client in list(clients.items()):
        if private and client != sender:  # Súkromné správy nejdú všetkým
            continue
        try:
            client.send(message.encode())
        except:
            client.close()
            del clients[user]

def handle_client(client):
    """Spracováva správy od klienta"""
    username, authenticated = authenticate(client)

    if not authenticated:
        client.send("❌ Prihlásenie zlyhalo! Skús znova.\n".encode())
        client.close()
        return

    clients[username] = client
    log_and_broadcast(f"✨ {username} sa pripojil!")  # Log pripojenia

    while True:
        try:
            message = client.recv(1024).decode()
            if not message:
                break

            if message.startswith("/"):
                handle_command(message, username, client)
            else:
                broadcast(f"{username}: {message}", client)

        except:
            break

    del clients[username]
    log_and_broadcast(f"🚪 {username} opustil chat.")  # Log odchodu
    client.close()

def handle_command(message, sender, client):
    """Spracováva '/' príkazy"""
    parts = message.split(" ", 2)
    command = parts[0]

    if command == "/register":
        if len(parts) < 3:
            client.send("❌ Použitie: /register <username> <heslo>".encode())
            return

        username, password = parts[1], parts[2]
        username, authenticated = authenticate(client, username, password, register=True)

        if authenticated:
            clients[username] = client
            log_and_broadcast(f"✨ {username} sa pripojil!")

    elif command == "/login":
        if len(parts) < 3:
            client.send("❌ Použitie: /login <username> <heslo>".encode())
            return

        username, password = parts[1], parts[2]
        username, authenticated = authenticate(client, username, password, register=False)

        if authenticated:
            clients[username] = client
            log_and_broadcast(f"✨ {username} sa pripojil!")

    elif command == "/dm":
        if len(parts) < 3:
            client.send("❌ Použitie: /dm (používateľ) (správa)".encode())
            return
        
        recipient, dm_message = parts[1], parts[2]
        if recipient in clients:
            clients[recipient].send(f"💌 DM od {sender}: {dm_message}".encode())
            client.send(f"📩 [DM] {recipient}: {dm_message}".encode())  # Odosielateľ tiež dostane potvrdenie
        else:
            client.send(f"❌ Používateľ {recipient} nie je online.".encode())

    elif command == "/users":
        user_list = "📜 Pripojení používatelia:\n" + "\n".join(clients.keys())
        client.send(user_list.encode())

    elif command == "/exit":
        client.send("👋 Odhlasujem...".encode())
        client.close()
        del clients[sender]
        log_and_broadcast(f"{sender} opustil chat.")

def start_server():
    """Spustenie servera"""
    PORT = 12345  # Môžete zmeniť port podľa potreby
    IP = socket.gethostbyname(socket.gethostname())  # Získanie miestnej IP adresy
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((IP, PORT))
    server.listen()

    log_and_broadcast(f"✅ Server beží na IP {IP} a porte {PORT}...")  # Zobrazenie IP a portu

    while True:
        client, _ = server.accept()  # IP sa neukladá
        threading.Thread(target=handle_client, args=(client,)).start()

start_server()
