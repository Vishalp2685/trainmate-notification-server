# TrainMate Notification Server (Frontend Guide)

**Live Server URL:** `https://trainmate-notification-server.onrender.com`
**WebSocket URL:** `wss://trainmate-notification-server.onrender.com/ws`

This server handles **real-time WebSocket communication** and **Firebase Cloud Messaging (FCM)** push notifications for the TrainMate application. You do not need to run this locally; everything is hosted on Render.

---

## 🔑 1. Authentication Concept
All REST API endpoints and the WebSocket connection require a valid JWT `access_token`. 

1. User logs into the **Main TrainMate Backend**, and you receive an `access_token`.
2. Save this token. You will pass it in the `Authorization: Bearer` header for API calls, and as a `?token=` query parameter for WebSockets to the Notification Server.

---

## 📱 2. Implementing in React Native (Android)

### Step A: Get and Register the FCM Token
To receive background push notifications (when the app is closed/in the background), your React Native app must generate an FCM Device Token and register it with the Notification server.

1. **Install Firebase in React Native**
   Follow standard docs: `npm install @react-native-firebase/app @react-native-firebase/messaging`
2. **Fetch the Token & Call API**
   ```javascript
   import messaging from '@react-native-firebase/messaging';
   import DeviceInfo from 'react-native-device-info'; // Optional, to get exact device

   async function registerDeviceToken(jwtToken) {
     const authStatus = await messaging().requestPermission();
     const enabled = authStatus === messaging.AuthorizationStatus.AUTHORIZED || authStatus === messaging.AuthorizationStatus.PROVISIONAL;
     
     if (!enabled) return;

     // 1. Get the FCM Token from Firebase
     const fcmToken = await messaging().getToken();
     const deviceId = await DeviceInfo.getUniqueId(); // Or use any unique generator string
     
     // 2. Register it with the Notification API
     const response = await fetch("https://trainmate-notification-server.onrender.com/devices/register", {
       method: "POST",
       headers: {
         "Authorization": `Bearer ${jwtToken}`,
         "Content-Type": "application/json"
       },
       body: JSON.stringify({
         device_id: deviceId,
         fcm_token: fcmToken,
         device_name: "React Native Android",
         device_type: "android"
       })
     });
   }
   ```

### Step B: Connect to the Live WebSocket
WebSockets are used for **real-time notifications** while the user has the app actively open.

```javascript
let notificationSocket = null;

function connectToNotificationLiveStream(jwtToken, deviceId) {
    const wsUrl = `wss://trainmate-notification-server.onrender.com/ws?token=${jwtToken}&device_id=${deviceId}`;
    notificationSocket = new WebSocket(wsUrl);

    notificationSocket.onopen = () => {
        console.log("🟢 Connected to live notifications");
        // Keep-alive ping every 30 seconds
        setInterval(() => {
            if(notificationSocket.readyState === WebSocket.OPEN) {
                notificationSocket.send(JSON.stringify({ type: "ping" }));
            }
        }, 30000);
    };

    notificationSocket.onmessage = (event) => {
        const rawMessage = JSON.parse(event.data);
        console.log("📥 Notification Received:", rawMessage);
        
        // Handle UI updates here (Red dot/popup)
        if (rawMessage.type === "friend_request") {
            // Show friend request modal
        }
    };

    notificationSocket.onclose = () => {
        console.log("🔴 Live notifications disconnected. Adding reconnect logic...");
    };
}
```

---

## 🚀 3. Triggering Notification API Endpoints

Use standard `fetch()` or `axios`. Remember to append `Authorization: Bearer <your_access_token>`.

### Send a Friend Request
Notify another user that you want to be friends.
```javascript
fetch("https://trainmate-notification-server.onrender.com/notifications/friend-request", {
  method: "POST",
  headers: { "Authorization": `Bearer ${jwtToken}`, "Content-Type": "application/json" },
  body: JSON.stringify({ type: "friend_request", receiver_id: 2 }) // User ID you are sending to
});
```

### Respond to a Friend Request
Accept/Reject a pending request (This sends a notification back to the original sender).
```javascript
fetch("https://trainmate-notification-server.onrender.com/notifications/friend-request-response", {
  method: "POST",
  headers: { "Authorization": `Bearer ${jwtToken}`, "Content-Type": "application/json" },
  body: JSON.stringify({ 
    type: "friend_request_response", 
    sender_id: 1, // ID of the person who originally SENT the request to you
    status: "accepted" // or "rejected"
  }) 
});
```

### Notify Friends of "Station Reached"
Broadcasts a push notification to all of the user's accepted friends that they have reached a station safely.
```javascript
fetch("https://trainmate-notification-server.onrender.com/notifications/station-reached", {
  method: "POST",
  headers: { "Authorization": `Bearer ${jwtToken}`, "Content-Type": "application/json" },
  body: JSON.stringify({ type: "station_reached", reached: true })
});
```

### Send a Chat Message (REST Alternative)
While chatting is primarily handled securely over the live WebSockets connection by sending `{"type":"chat", "receiver_id": 2, "content": "Hello!"}`, you can also trigger a message via this REST API.
This is fully synced: if the receiver is connected to the websocket they get it live instantly, otherwise they will receive an FCM mobile push notification instead, and it's always appended to the database.
```javascript
fetch("https://trainmate-notification-server.onrender.com/chat/send", {
  method: "POST",
  headers: { "Authorization": `Bearer ${jwtToken}`, "Content-Type": "application/json" },
  body: JSON.stringify({ 
    receiver_id: 2, 
    content: "Hey, are we on the same train?" 
  })
});
```

### Load Chat Message History
Fetch a paginated JSON array containing chat history between the current authenticated user and a specific friend. Useful for retrieving previous context when heavily loading up a chat screen.
```javascript
fetch("https://trainmate-notification-server.onrender.com/chat/history", {
  method: "POST",
  headers: { "Authorization": `Bearer ${jwtToken}`, "Content-Type": "application/json" },
  body: JSON.stringify({ 
    friend_id: 2, 
    limit: 50,  // Defaults to 50 items per page if omitted
    offset: 0   // Pagination mechanism: offset 0 is newest, 50 fetches the next page back, etc.
  })
});
```
