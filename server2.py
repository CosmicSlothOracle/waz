import websockets
import datetime
import asyncio


class Server:
    def __init__(self, local_host="0.0.0.0", port=8080):
        self.local_host = local_host
        self.port = port
        self.clients = []
        # CHANGED: Added dict to track usernames and which are assigned
        # WHY: Need to assign usernames from predefined list, track which are in use
        self.usernames = [
            "Erne Bierhuafen", "Agelikk Konfetzer", "Ingegorg Fist", "Bouiwfe Manthong",
            "Chantallé Fettkoeter", "Flart", "Bakana-Else Burkaki", "Erdnulf des Westens",
            "Erdnulf des Ostens", "Karlotta Edelweiß von Schüttenbronn an der Hasselau",
            "Timothy Eugeen", "Mortymer Coin", "Teknolo Cheesus", "Sven Perlo",
            "Kordula Jackson", "Diddy Dernbach van Havlklang", "Bob"
        ]
        self.assigned = set()  # Track which usernames are currently assigned
        self.websocket_users = {}  # Map websocket to username

    async def client_messages(self, websocket):
        """
        CHANGED: Broadcast messages from one client to all other connected clients
        WHY: Clients should communicate with each other via the server
        HOW: When a client sends a message, forward it to all other clients in self.clients
        CHANGED: Only allow chat if at least 2 clients are connected
        """
        try:
            now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            username = self.websocket_users.get(websocket, "Unknown")
            async for message in websocket:
                # CHANGED: Check if at least 2 clients are connected before allowing chat
                # WHY: Chat should only work when at least 2 clients are present
                if len(self.clients) < 2:
                    # CHANGED: Inform client that they need to wait for another client
                    # WHY: Client should know why their messages aren't being sent
                    try:
                        await websocket.send("Waiting for another client to connect...")
                    except:
                        pass
                    continue  # Skip this message, wait for more clients

                print(f"{now} {username} -  : {message}")
                # CHANGED: Broadcast message to all other connected clients
                # WHY: All clients should see messages from other clients
                # HOW: Loop through all clients and send message to each (except sender)
                for client in self.clients:
                    if client == websocket:
                        continue
                    try:
                        await client.send(f"{username}: {message}")
                    except Exception:
                        # Skip if client disconnected or send failed
                        pass
        except websockets.exceptions.ConnectionClosed:
            print(f"Connection with {websocket.remote_address} was lost")

    async def broadcast_username(self, username):
        """
        CHANGED: Send assigned username to all connected clients
        WHY: All clients should know which username was assigned
        HOW: Loop through all clients and send the username
        """
        for client in self.clients:
            try:
                await client.send(f"USERNAME: {username}")
            except Exception:
                # Skip if client disconnected or send failed
                pass

    async def broadcast_user_online(self, username):
        """
        CHANGED: Send "user now online" message to all connected clients
        WHY: All clients should know when a new user comes online
        HOW: Loop through all clients and send the online notification
        """
        for client in self.clients:
            try:
                await client.send(f"{username} now online")
            except Exception:
                # Skip if client disconnected or send failed
                pass

    async def handle_connections(self, websocket):
        print(
            f"New connection from {websocket.remote_address}\nType here to send a message...\n")
        # CHANGED: Call account_check before allowing chat
        # WHY: User must login/be assigned username first
        username = await self.account_check(websocket)
        if not username:
            await websocket.close()
            return

        await websocket.send("")
        self.clients.append(websocket)

        # CHANGED: Broadcast the assigned username to all connected clients
        # WHY: All clients should know which username was just assigned
        await self.broadcast_username(username)

        # CHANGED: If this is the 2nd client, send "user now online" to all clients
        # WHY: Chat can now start when at least 2 clients are connected
        if len(self.clients) >= 2:
            await self.broadcast_user_online(username)
            # CHANGED: Inform all clients that chat can now start
            # WHY: Clients should know when they can start chatting
            for client in self.clients:
                try:
                    await client.send("Chat is now active! You can start messaging.")
                except Exception:
                    pass
        else:
            # CHANGED: Inform the single client that they need to wait
            # WHY: Client should know why they can't chat yet
            try:
                await websocket.send("Waiting for another client to connect before chat can start...")
            except:
                pass

        try:
            # CHANGED: Removed server_messages - server no longer sends messages directly
            # WHY: Only clients send messages to each other via server
            await self.client_messages(websocket)
        except Exception as e:
            print(e)
        finally:
            # CHANGED: Get username before removing from dict
            # WHY: Need username to notify other clients
            disconnected_username = None
            if websocket in self.websocket_users:
                disconnected_username = self.websocket_users[websocket]

            # CHANGED: Remove client from list and release username when connection closes
            # WHY: Username can be reused by another client, and client should be removed from broadcast list
            if websocket in self.clients:
                self.clients.remove(websocket)
            if websocket in self.websocket_users:
                self.assigned.discard(self.websocket_users[websocket])
                del self.websocket_users[websocket]

            # CHANGED: If less than 2 clients remain, inform them that chat is paused
            # WHY: Clients should know when chat is no longer active
            if len(self.clients) == 1 and disconnected_username:
                # Notify remaining client that chat is paused
                remaining_client = self.clients[0] if self.clients else None
                if remaining_client:
                    try:
                        # Schedule the send operation
                        asyncio.ensure_future(remaining_client.send(
                            f"{disconnected_username} disconnected. Waiting for another client..."))
                    except Exception:
                        pass

    async def server_start(self):
        async with websockets.serve(self.handle_connections, self.local_host, self.port):
            print(f"Server has started on {self.local_host}:{self.port}")
            await asyncio.Future()

    async def account_check(self, websocket):
        """
        CHANGED: Implemented Y/N login flow with dict-based username assignment
        WHY: Ask if user has username, verify or assign from predefined list
        HOW: Y = verify username exists, N = assign first unassigned username
        """
        try:
            await websocket.send("Do you already have a username? (Y/N): ")
            response = (await websocket.recv()).strip().upper()

            if response == 'Y':
                while True:
                    await websocket.send("Please enter your username: ")
                    username = (await websocket.recv()).strip()
                    if username in self.usernames and username not in self.assigned:
                        self.assigned.add(username)
                        self.websocket_users[websocket] = username
                        await websocket.send(f"Login successful as {username}!\n")
                        return username
                    await websocket.send(f"ERROR: Username not found or already in use.\n")

            elif response == 'N':
                # CHANGED: Assign first unassigned username
                # WHY: User needs a username from the predefined list
                for username in self.usernames:
                    if username not in self.assigned:
                        self.assigned.add(username)
                        self.websocket_users[websocket] = username
                        await websocket.send(f"Assigned username: {username}\n")
                        await websocket.send(f"Login successful as {username}!\n")
                        return username
                await websocket.send("ERROR: No available usernames.\n")
                return None
            else:
                await websocket.send("ERROR: Please enter Y or N\n")
                return None

        except websockets.exceptions.ConnectionClosed:
            print(f"Connection with {websocket.remote_address} was lost")
            return None


if __name__ == "__main__":
    server = Server()
    asyncio.run(server.server_start())
