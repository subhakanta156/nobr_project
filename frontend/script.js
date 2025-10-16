let db;
let currentChatId = null;

// ⚙️ Backend API Configuration
const API_BASE_URL = "http://localhost:8000"; // Change this to your backend URL

// ---------- IndexedDB Setup ----------
const request = indexedDB.open("ChatDB", 1);

request.onupgradeneeded = (e) => {
  db = e.target.result;
  const store = db.createObjectStore("chats", { keyPath: "id", autoIncrement: true });
  store.createIndex("title", "title", { unique: false });
};

request.onsuccess = (e) => {
  db = e.target.result;
  loadChatHistory();
};

request.onerror = (e) => {
  console.error("IndexedDB error:", e.target.error);
};

// ---------- UI Elements ----------
const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const newChatBtn = document.getElementById("new-chat-btn");
const chatHistory = document.getElementById("chat-history");
const chatTitle = document.getElementById("chat-title");

// ---------- Core Chat Functions ----------
function addMessage(content, sender, cards = [], save = true) {
  const msg = document.createElement("div");
  msg.classList.add("message", sender);

  const bubble = document.createElement("div");
  bubble.classList.add("bubble");
  bubble.textContent = content;

  msg.appendChild(bubble);

  // Add property cards if they exist
  if (cards && cards.length > 0) {
    const cardsContainer = document.createElement("div");
    cardsContainer.classList.add("property-cards");
    
    cards.forEach(card => {
      const cardEl = createPropertyCard(card);
      cardsContainer.appendChild(cardEl);
    });
    
    msg.appendChild(cardsContainer);
  }

  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;

  if (save && currentChatId) saveMessageToDB(content, sender, cards);
}

function createPropertyCard(card) {
  const cardEl = document.createElement("div");
  cardEl.classList.add("property-card");
  
  // Clean up the data
  const title = card.title || card.project_name || 'Property';
  const price = card.price || 'Price on request';
  const location = card.city_locality || 'Location not specified';
  
  // Clean BHK - remove underscores and format nicely
  let bhk = card.bhk || '';
  bhk = bhk.replace(/_/g, ' ').trim();
  
  // Clean status - format nicely
  let status = card.possession_status || '';
  status = status.replace(/_/g, ' ')
              .toLowerCase()
              .split(' ')
              .map(word => word.charAt(0).toUpperCase() + word.slice(1))
              .join(' ');
  
  // Filter out placeholder amenities
  let amenities = card.top_amenities || [];
  amenities = amenities.filter(a => 
    a && 
    a.toLowerCase() !== 'about property' && 
    a.toLowerCase() !== 'property' &&
    a.trim().length > 2
  );
  
  cardEl.innerHTML = `
    <div class="card-header">
      <h3 class="card-title">${title}</h3>
      <span class="card-price">${price}</span>
    </div>
    <div class="card-body">
      <p class="card-location">📍 ${location}</p>
      ${bhk ? `<p class="card-bhk">🏠 ${bhk}</p>` : ''}
      ${status ? `<p class="card-status">🔑 ${status}</p>` : ''}
      ${amenities.length > 0 ? `
        <div class="card-amenities">
          <strong>✨ Amenities:</strong>
          <ul>
            ${amenities.slice(0, 3).map(a => `<li>${a}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
    </div>
    <div class="card-footer">
      <a href="${card.cta_url || '#'}" class="card-cta" target="_blank">View Details →</a>
    </div>
  `;
  
  return cardEl;
}

function showTypingIndicator() {
  const indicator = document.createElement("div");
  indicator.classList.add("message", "ai", "typing-indicator");
  indicator.id = "typing-indicator";
  indicator.innerHTML = `
    <div class="bubble">
      <span></span><span></span><span></span>
    </div>
  `;
  chatBox.appendChild(indicator);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function removeTypingIndicator() {
  const indicator = document.getElementById("typing-indicator");
  if (indicator) indicator.remove();
}

function isGreeting(text) {
  const greetings = [
    'hi', 'hello', 'hey', 'hii', 'hiii', 'hiiii',
    'good morning', 'good afternoon', 'good evening', 'good night',
    'morning', 'evening', 'afternoon',
    'namaste', 'namaskar',
    'greetings', 'howdy', 'sup', 'yo',
    'how are you', 'whats up', "what's up",
    'hola', 'bonjour', 'ciao'
  ];
  
  const lowerText = text.toLowerCase().trim();
  return greetings.some(greeting => 
    lowerText === greeting || 
    lowerText.startsWith(greeting + ' ') ||
    lowerText.startsWith(greeting + '!')
  );
}

function getGreetingResponse() {
  return "Hello! 👋 Welcome to Property AI. I'm here to help you find your perfect property. What are you looking for today?";
}

async function aiResponse(userMsg) {
  // Check if it's a greeting
  if (isGreeting(userMsg)) {
    showTypingIndicator();
    setTimeout(() => {
      removeTypingIndicator();
      addMessage(getGreetingResponse(), "ai", []);
    }, 700);
    return;
  }
  
  showTypingIndicator();
  
  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query: userMsg }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    removeTypingIndicator();
    
    // Display AI response WITHOUT cards - only show text summary
    addMessage(data.answer, "ai", []);
    
  } catch (error) {
    removeTypingIndicator();
    console.error("Error calling backend:", error);
    addMessage(
      "Sorry, I'm having trouble connecting to the server. Please make sure the backend is running on " + API_BASE_URL,
      "ai"
    );
  }
}

function sendMessage() {
  const text = userInput.value.trim();
  if (!text) return;

  // Disable send button while processing
  sendBtn.disabled = true;
  userInput.disabled = true;

  // ✅ Automatically create a chat if none exists
  if (!currentChatId) {
    createNewChatWithMessage(text);
  } else {
    addMessage(text, "user");
    userInput.value = "";
    updateChatTitleIfNeeded(text);
    aiResponse(text).finally(() => {
      sendBtn.disabled = false;
      userInput.disabled = false;
      userInput.focus();
    });
  }
}

// ---------- IndexedDB Helpers ----------
function saveMessageToDB(content, sender, cards = []) {
  const tx = db.transaction("chats", "readwrite");
  const store = tx.objectStore("chats");
  store.get(currentChatId).onsuccess = (e) => {
    const chat = e.target.result;
    chat.messages.push({ sender, content, cards: cards || [] });
    store.put(chat);
  };
}

function updateChatTitleIfNeeded(firstMsg) {
  const tx = db.transaction("chats", "readwrite");
  const store = tx.objectStore("chats");
  store.get(currentChatId).onsuccess = (e) => {
    const chat = e.target.result;
    if (chat.title === "New Chat" && firstMsg) {
      const shortTitle = firstMsg.length > 25 ? firstMsg.slice(0, 25) + "…" : firstMsg;
      chat.title = shortTitle;
      chatTitle.textContent = shortTitle;
      store.put(chat);
      loadChatHistory();
    }
  };
}

function createNewChat() {
  const tx = db.transaction("chats", "readwrite");
  const store = tx.objectStore("chats");
  const newChat = { title: "New Chat", messages: [] };
  const req = store.add(newChat);
  req.onsuccess = () => {
    currentChatId = req.result;
    chatTitle.textContent = "New Chat";
    chatBox.innerHTML = `
      <div class="message ai">
        <div class="bubble">Hello 👋 I'm your AI assistant. How can I help you find properties today?</div>
      </div>`;
    loadChatHistory();
  };
}

function createNewChatWithMessage(firstMessage) {
  const tx = db.transaction("chats", "readwrite");
  const store = tx.objectStore("chats");
  const shortTitle = firstMessage.length > 25 ? firstMessage.slice(0, 25) + "…" : firstMessage;
  const newChat = { 
    title: shortTitle, 
    messages: [{ sender: "user", content: firstMessage, cards: [] }] 
  };
  const req = store.add(newChat);
  req.onsuccess = () => {
    currentChatId = req.result;
    chatTitle.textContent = shortTitle;
    chatBox.innerHTML = `
      <div class="message ai">
        <div class="bubble">Hello 👋 I'm your AI assistant. How can I help you find properties today?</div>
      </div>`;
    addMessage(firstMessage, "user", [], false);
    userInput.value = "";
    loadChatHistory();
    aiResponse(firstMessage).finally(() => {
      sendBtn.disabled = false;
      userInput.disabled = false;
      userInput.focus();
    });
  };
}

function deleteChat(id) {
  const tx = db.transaction("chats", "readwrite");
  const store = tx.objectStore("chats");
  store.delete(id).onsuccess = () => {
    if (id === currentChatId) {
      // If deleting active chat, reset UI
      currentChatId = null;
      chatTitle.textContent = "New Chat";
      chatBox.innerHTML = `
        <div class="message ai">
          <div class="bubble">Hello 👋 I'm your AI assistant. How can I help you find properties today?</div>
        </div>`;
    }
    loadChatHistory();
  };
}

function loadChatHistory() {
  chatHistory.innerHTML = "";
  const tx = db.transaction("chats", "readonly");
  const store = tx.objectStore("chats");

  store.openCursor().onsuccess = (e) => {
    const cursor = e.target.result;
    if (cursor) {
      const chat = cursor.value;

      const item = document.createElement("div");
      item.classList.add("chat-item");
      if (chat.id === currentChatId) item.classList.add("active");

      const title = document.createElement("div");
      title.classList.add("chat-title");
      title.textContent = chat.title || `Chat ${chat.id}`;
      title.onclick = () => loadChat(chat.id);

      const delBtn = document.createElement("button");
      delBtn.classList.add("delete-btn");
      delBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M2 4h12M5.333 4V2.667a1.333 1.333 0 0 1 1.334-1.334h2.666a1.333 1.333 0 0 1 1.334 1.334V4m2 0v9.333a1.333 1.333 0 0 1-1.334 1.334H4.667a1.333 1.333 0 0 1-1.334-1.334V4h9.334Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`;
      delBtn.onclick = (event) => {
        event.stopPropagation();
        deleteChat(chat.id);
      };

      item.appendChild(title);
      item.appendChild(delBtn);
      chatHistory.appendChild(item);
      cursor.continue();
    }
  };
}

function loadChat(id) {
  const tx = db.transaction("chats", "readonly");
  const store = tx.objectStore("chats");
  store.get(id).onsuccess = (e) => {
    const chat = e.target.result;
    currentChatId = id;
    chatTitle.textContent = chat.title;
    chatBox.innerHTML = "";
    chat.messages.forEach((m) => addMessage(m.content, m.sender, m.cards || [], false));
    loadChatHistory();
  };
}

// ---------- Event Listeners ----------
sendBtn.addEventListener("click", sendMessage);
userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
newChatBtn.addEventListener("click", createNewChat);

// ---------- Mobile Menu Toggle ----------
const menuToggle = document.getElementById("menu-toggle");
const sidebar = document.getElementById("sidebar");

menuToggle.addEventListener("click", () => {
  sidebar.classList.toggle("open");
});

// Close sidebar when clicking outside on mobile
document.addEventListener("click", (e) => {
  if (window.innerWidth <= 768) {
    if (!sidebar.contains(e.target) && !menuToggle.contains(e.target)) {
      sidebar.classList.remove("open");
    }
  }
});