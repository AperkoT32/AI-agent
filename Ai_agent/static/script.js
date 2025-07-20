document.addEventListener('DOMContentLoaded', function() {
    function updateDateTime() {
        const dateTimeElem = document.getElementById('current-datetime');
        if (dateTimeElem) {
            const now = new Date();
            const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' };
            dateTimeElem.textContent = now.toLocaleString('ru-RU', options);
        }
    }
    setInterval(updateDateTime, 1000);
    updateDateTime();
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const fileInput = document.getElementById('file-input');
    const attachButton = document.getElementById('attach-button');
    const todoList = document.getElementById('todo-list');
    const newTodoInput = document.getElementById('new-todo-input');
    const addTodoBtn = document.getElementById('add-todo-btn');
    const sidebar = document.getElementById('sidebar');
    const chatContainer = document.querySelector('.chat-container');
    let chatHistory = [];
    let currentChatId = 'chat-' + Date.now();
    let isEditingTitle = false;
    let isFileDialogOpen = false;
    async function fetchAndRenderTodos() {
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: 'покажи задачи' }),
            });
            const data = await response.json();
            if (data.response) {
                renderTodos(data.response);
            } else if (data.error) {
                console.error('Ошибка при получении списка задач:', data.error);
            }
        } catch (error) {
            console.error('Ошибка сети при получении списка задач:', error);
        }
    }
    function renderTodos(todosText) {
        todoList.innerHTML = ''; // Очищаем текущий список
        const lines = todosText.split('\n');
        if (lines.length <= 1) {
            const emptyItem = document.createElement('li');
            emptyItem.textContent = 'Список задач пуст.';
            todoList.appendChild(emptyItem);
            return;
        }
        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;
            const match = line.match(/^(\d+)\.\s(✅|⏳)\s(.+)$/);
            if (match) {
                const id = parseInt(match[1]);
                const statusChar = match[2];
                const taskText = match[3];
                const isCompleted = statusChar === '✅';
                const listItem = document.createElement('li');
                listItem.dataset.id = id;
                if (isCompleted) {
                    listItem.classList.add('completed');
                }
                const todoContentWrapper = document.createElement('div');
                todoContentWrapper.classList.add('todo-content-wrapper');
                const checkbox = document.createElement('div');
                checkbox.classList.add('todo-checkbox');
                checkbox.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 6L9 17L4 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
            
                const taskSpan = document.createElement('span');
                taskSpan.textContent = taskText;
                taskSpan.classList.add('todo-text'); // Добавляем класс для стилизации текста
                todoContentWrapper.appendChild(checkbox);
                todoContentWrapper.appendChild(taskSpan);
                const deleteButton = document.createElement('button');
                deleteButton.classList.add('delete-todo-btn');
                deleteButton.innerHTML = `
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M3 6h18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                `;
                deleteButton.title = 'Удалить задачу';
                listItem.appendChild(todoContentWrapper);
                listItem.appendChild(deleteButton);
                deleteButton.addEventListener('click', async (e) => {
                    e.stopPropagation(); 
                    const confirmDelete = confirm(`Вы уверены, что хотите удалить задачу "${taskText}"?`);
                    if (confirmDelete) {
                        const command = `удали задачу ${id}`;
                        try {
                            const response = await fetch('/api/chat', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ message: command }),
                            });
                            const data = await response.json();
                            if (data.response) {
                                console.log(`Задача ${id} удалена:`, data.response);
                                fetchAndRenderTodos(); 
                            } else {
                                console.error('Ошибка при удалении задачи:', data.error);
                                alert(`Не удалось удалить задачу: ${data.error}`);
                            }
                        } catch (error) {
                            console.error('Ошибка сети при удалении задачи:', error);
                            alert('Ошибка сети при попытке удалить задачу.');
                        }
                    }
                });
                listItem.addEventListener('click', async (e) => {
                    e.stopPropagation(); 
                    console.log("CLICK EVENT FIRED for task ID:", id);
                    console.log("Current 'completed' status:", listItem.classList.contains('completed'));
                    const newStatus = !listItem.classList.contains('completed');
                    const command = newStatus 
                        ? `отметь задачу ${id} выполненной` 
                        : `отметь задачу ${id} невыполненной`;
                    console.log("Command being sent to backend:", command);
                    const updateResponse = await fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: command }),
                    });
                    const updateData = await updateResponse.json();

                    if (updateData.response) {
                        console.log("Task update successful. Re-fetching todos.");
                        fetchAndRenderTodos(); 
                    } else {
                        console.error('Ошибка при обновлении статуса задачи:', updateData.error);
                    }
                });

                todoList.appendChild(listItem);
            }
        }
    }
    function createNewChat() {
        saveCurrentChat();
        currentChatId = 'chat-' + Date.now();
        localStorage.setItem('activeChatId', currentChatId); 
        chatMessages.innerHTML = `
            <div class="message assistant">
                <div class="message-content">
                        <p><strong>Привет! Я Джейн — ваш ИИ-ассистент.</strong></p>
                    
                    <p>Я могу помочь вам с:</p>
                    <ul style="list-style-type: disc; padding-left: 20px; margin: 10px 0;">
                        <li style="margin-bottom: 5px;">💬 Ответами на вопросы и объяснениями</li>
                        <li style="margin-bottom: 5px;">🖼️ Анализом изображений и документов</li>
                        <li style="margin-bottom: 5px;">✍️ Написанием и редактированием текстов</li>
                        <li style="margin-bottom: 5px;">💻 Программированием и техническими задачами</li>
                        <li style="margin-bottom: 5px;">🌐 Переводами и языковыми вопросами</li>
                    </ul>
                    
                    <p>Просто напишите ваш вопрос или прикрепите файл для анализа! 📎</p>
                </div>
            </div>
        `;
        chatHistory = [{
            type: 'assistant',
            content: chatMessages.querySelector('.message-content').innerHTML
        }];
        chatMessages.style.opacity = '0';
        setTimeout(() => {
            chatMessages.style.opacity = '1';
        }, 150);
        addChatToSidebar(currentChatId, 'Новый чат');
        setActiveChatItem(document.querySelector('.chat-item[data-id="' + currentChatId + '"]'));
        userInput.focus();
    }
    function addChatToSidebar(id, title) {
        const chatHistoryContainer = document.querySelector('.chat-history');
        const chatItem = document.createElement('div');
        chatItem.className = 'chat-item';
        chatItem.dataset.id = id;
        chatItem.innerHTML = `
            <div class="chat-item-content">
                <span class="chat-title" title="${title}">${title}</span>
                <div class="chat-actions">
                    <button class="edit-chat" title="Переименовать">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                            <path d="m18.5 2.5 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </button>
                    <button class="delete-chat" title="Удалить">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M3 6h18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;
        
        const chatContent = chatItem.querySelector('.chat-item-content');
        const titleSpan = chatItem.querySelector('.chat-title');
        const editButton = chatItem.querySelector('.edit-chat');
        const deleteButton = chatItem.querySelector('.delete-chat');
        
        chatContent.addEventListener('click', (e) => {
            if (!e.target.closest('.chat-actions') && !isEditingTitle) {
                setActiveChatItem(chatItem);
                loadChat(id);
            }
        });
        editButton.addEventListener('click', (e) => {
            e.stopPropagation();
            editChatTitle(chatItem, titleSpan, id);
        });
        deleteButton.addEventListener('click', async (e) => { // Добавлен async
            e.stopPropagation();
            showDeleteConfirmation(id, chatItem, title);
        });
        chatHistoryContainer.appendChild(chatItem);
        setActiveChatItem(chatItem);
        chatItem.style.opacity = '0';
        chatItem.style.transform = 'translateX(-20px)';
        setTimeout(() => {
            chatItem.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            chatItem.style.opacity = '1';
            chatItem.style.transform = 'translateX(0)';
        }, 50);
    }
    function editChatTitle(chatItem, titleSpan, chatId) {
        if (isEditingTitle) return;
        isEditingTitle = true;
        const currentTitle = titleSpan.textContent;
        const input = document.createElement('input');
        input.type = 'text';
        input.value = currentTitle;
        input.className = 'chat-title-input';
        input.maxLength = 50;
        titleSpan.style.display = 'none';
        titleSpan.parentNode.insertBefore(input, titleSpan);
        input.focus();
        input.select();
        function finishEditing(save = true) {
            if (!isEditingTitle) return;
            isEditingTitle = false;
            const newTitle = save ? input.value.trim() || currentTitle : currentTitle;
            titleSpan.textContent = newTitle;
            titleSpan.title = newTitle;
            titleSpan.style.display = '';
            if (input.parentNode) {
                input.parentNode.removeChild(input);
            }
            if (save && newTitle !== currentTitle) {
                saveChatTitle(chatId, newTitle);
            }
        }
        input.addEventListener('blur', () => finishEditing(true));
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                finishEditing(true);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                finishEditing(false);
            }
        });
    }
    function saveChatTitle(chatId, title) {
        // Теперь заголовки чатов хранятся в localStorage, а сообщения в БД
        const chatData = localStorage.getItem(chatId);
        if (chatData) {
            try {
                const data = JSON.parse(chatData);
                data.title = title;
                localStorage.setItem(chatId, JSON.stringify(data));
            } catch (e) {й
                const messages = JSON.parse(chatData);
                const newData = {
                    title: title,
                    messages: messages, // Сообщения здесь не используются, но сохраняем для совместимости
                    createdAt: Date.now()
                };
                localStorage.setItem(chatId, JSON.stringify(newData));
            }
        } else {
            const newData = {
                title: title,
                messages: [], // Пустой массив, сообщения будут в БД
                createdAt: Date.now()
            };
            localStorage.setItem(chatId, JSON.stringify(newData));
        }
    }
    function showDeleteConfirmation(chatId, chatItem, title) {
        const modal = document.createElement('div');
        modal.className = 'delete-modal';
        modal.innerHTML = `
            <div class="delete-modal-content">
                <h3>Удалить чат?</h3>
                <p>Вы уверены, что хотите удалить чат "${title}"?<br>Это действие нельзя отменить.</p>
                <div class="delete-modal-actions">
                    <button class="cancel-btn">Отмена</button>
                    <button class="confirm-delete-btn">Удалить</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        const cancelBtn = modal.querySelector('.cancel-btn');
        const confirmBtn = modal.querySelector('.confirm-delete-btn');
        
        cancelBtn.addEventListener('click', () => {
            closeModal(modal);
        });
        confirmBtn.addEventListener('click', async () => { // Добавлен async
            await deleteChat(chatId, chatItem); // Ожидаем завершения удаления
            closeModal(modal);
        });
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal(modal);
            }
        });
        const escapeHandler = (e) => {
            if (e.key === 'Escape') {
                closeModal(modal);
                document.removeEventListener('keydown', escapeHandler);
            }
        };
        document.addEventListener('keydown', escapeHandler);
        setTimeout(() => {
            modal.classList.add('show');
        }, 10);
    }
    function closeModal(modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            if (modal.parentNode) {
                modal.parentNode.removeChild(modal);
            }
        }, 200);
    }
    function setActiveChatItem(activeItem) {
    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
    });
        activeItem.classList.add('active');
        if (activeItem && activeItem.dataset && activeItem.dataset.id) {
            localStorage.setItem('activeChatId', activeItem.dataset.id);
        }
    }
    async function deleteChat(chatId, chatItem) { // Добавлен async
        console.log("Attempting to delete chat with ID:", chatId);
        try {
            const response = await fetch(`/api/chat_history/${chatId}`, {
                method: 'DELETE',
            });
            if (response.ok) {
                console.log("Chat history removed from DB:", chatId);
            } else {
                console.error("Failed to delete chat history from DB:", await response.text());
            }
        } catch (error) {
            console.error("Network error deleting chat history from DB:", error);
        }
        localStorage.removeItem(chatId);
        console.log("Removed from localStorage:", chatId);
        if (chatId === currentChatId) {
            console.log("Deleted chat was current chat. Invalidating currentChatId temporarily.");
            currentChatId = null; // Немедленно делаем currentChatId недействительным
            const remainingChats = document.querySelectorAll('.chat-item');
            if (remainingChats.length > 1) {
                const firstChat = remainingChats[0];
                if (firstChat !== chatItem) {
                    const firstChatId = firstChat.dataset.id;
                    loadChat(firstChatId); // Это установит currentChatId в firstChatId
                    setActiveChatItem(firstChat);
                } else if (remainingChats[1]) {
                    const secondChatId = remainingChats[1].dataset.id;
                    loadChat(secondChatId); // Это установит currentChatId в secondChatId
                    setActiveChatItem(remainingChats[1]);
                }
            } else {
                createNewChat(); // Это установит currentChatId в новый ID
            }
        }
        chatItem.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        chatItem.style.opacity = '0';
        chatItem.style.transform = 'translateX(-20px)';
        setTimeout(() => {
            if (chatItem.parentNode) {
                chatItem.parentNode.removeChild(chatItem);
            }
        }, 300);
    }
    function saveCurrentChat() {
        if (!currentChatId) {
            console.log("Skipping save: currentChatId is null (likely a deleted chat).");
            return;
        }
        const messages = Array.from(chatMessages.children).map(msg => {
            return {
                type: msg.classList.contains('user') ? 'user' : 'assistant',
                content: msg.querySelector('.message-content').innerHTML
            };
        });
        if (messages.length > 1) { 
            let existingChatData = localStorage.getItem(currentChatId);
            let chatData = {};
            if (existingChatData) {
                try {
                    chatData = JSON.parse(existingChatData);
                } catch (e) {
                    console.error("Ошибка анализа существующих данных чата:", e);
                    chatData = {};
                }
            }
            if (!chatData.createdAt) {
                chatData.createdAt = Date.now();
            }
            chatData.title = getChatTitle(currentChatId);
            chatData.messages = []; // Сообщения больше не храним в localStorage
            chatData.updatedAt = Date.now();
            localStorage.setItem(currentChatId, JSON.stringify(chatData));
            console.log("Saved chat ID:", currentChatId, "with metadata only.");
        } else {
            console.log("Not saving chat ID:", currentChatId, "because it has 1 or fewer messages (only welcome).");
        }
    }
    function getChatTitle(chatId) {
        const chatItem = document.querySelector(`[data-id="${chatId}"]`);
        if (chatItem) {
            const titleSpan = chatItem.querySelector('.chat-title');
            return titleSpan ? titleSpan.textContent : 'Новый чат';
        }
        // Если chatItem не найден, пытаемся получить из localStorage
        const chatData = localStorage.getItem(chatId);
        if (chatData) {
            try {
                const parsed = JSON.parse(chatData);
                return parsed.title || 'Новый чат';
            } catch (e) {
                console.error("Error parsing chat data for title:", e);
            }
        }
        return 'Новый чат';
    }
    async function loadChat(chatId) { // Добавлен async
        saveCurrentChat(); // Сохраняем текущий чат перед загрузкой нового
        let messagesToLoad = [];
        let chatTitle = 'Новый чат';
        const savedChatMetadata = localStorage.getItem(chatId);
        if (savedChatMetadata) {
            try {
                const data = JSON.parse(savedChatMetadata);
                if (data.title) {
                    chatTitle = data.title;
                }
            } catch (e) {
                console.error('Error parsing saved chat metadata:', e);
            }
        }
        // Загружаем сообщения из БД через API
        try {
            const response = await fetch(`/api/chat_history/${chatId}`);
            if (response.ok) {
                const data = await response.json();
                messagesToLoad = data.history || [];
                console.log(`Loaded ${messagesToLoad.length} messages from DB for chat ID: ${chatId}`);
            } else {
                console.error('Failed to load chat history from DB:', await response.text());
            }
        } catch (error) {
            console.error('Network error loading chat history from DB:', error);
        }
        chatMessages.innerHTML = ''; // Всегда очищаем перед загрузкой
        chatHistory = []; // Всегда очищаем историю
        chatMessages.style.opacity = '0';
        setTimeout(() => {
            if (messagesToLoad.length === 0) {
                const welcomeMessage = `
                    <div class="message assistant">
                        <div class="message-content">
                                <p><strong>Привет! Я Джейн — ваш ИИ-ассистент.</strong></p>
                            
                            <p>Я могу помочь вам с:</p>
                            <ul style="list-style-type: disc; padding-left: 20px; margin: 10px 0;">
                                <li style="margin-bottom: 5px;">💬 Ответами на вопросы и объяснениями</li>
                                <li style="margin-bottom: 5px;">🖼️ Анализом изображений и документов</li>
                                <li style="margin-bottom: 5px;">✍️ Написанием и редактированием текстов</li>
                                <li style="margin-bottom: 5px;">💻 Программированием и техническими задачами</li>
                                <li style="margin-bottom: 5px;">🌐 Переводами и языковыми вопросами</li>
                            </ul>
                    
                            <p>Просто напишите ваш вопрос или прикрепите файл для анализа! 📎</p>
                        </div>
                    </div>
                `;
                chatMessages.innerHTML = welcomeMessage;
                chatHistory.push({
                    type: 'assistant',
                    content: welcomeMessage
                });
            } else {
                messagesToLoad.forEach(msg => {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `message ${msg.role === 'user' ? 'user' : 'assistant'}`; // Используем msg.role
                    const messageContent = document.createElement('div');
                    messageContent.className = 'message-content';
                    messageContent.innerHTML = msg.content;
                    messageDiv.appendChild(messageContent);
                    chatMessages.appendChild(messageDiv);
                    chatHistory.push({
                        type: msg.role, // Используем msg.role
                        content: msg.content
                    });
                });
            }
            chatMessages.style.opacity = '1';
            currentChatId = chatId;
            chatMessages.scrollTop = chatMessages.scrollHeight;
            const chatItem = document.querySelector(`[data-id="${chatId}"]`);
            if (chatItem) {
                const titleSpan = chatItem.querySelector('.chat-title');
                if (titleSpan && titleSpan.textContent === 'Новый чат' && messagesToLoad.length > 0) {
                    titleSpan.textContent = chatTitle;
                    titleSpan.title = chatTitle;
                }
            }

        }, 150);
    }
    function addMessage(content, isUser = false, animate = true, isHTML = true) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        if (isHTML) {
            messageContent.innerHTML = content;
        } else {
            messageContent.innerHTML = content
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/\n/g, '<br>');
        }
        messageDiv.appendChild(messageContent);
        if (animate) {
            messageDiv.style.opacity = '0';
            messageDiv.style.transform = 'translateY(20px)';
        }
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        if (animate) {
            setTimeout(() => {
                messageDiv.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                messageDiv.style.opacity = '1';
                messageDiv.style.transform = 'translateY(0)';
            }, 50);
        }
        chatHistory.push({
            type: isUser ? 'user' : 'assistant',
            content: messageContent.innerHTML 
        });
        if (isUser && chatHistory.filter(msg => msg.type === 'user').length === 1) {
            autoUpdateChatTitle(content);
        }
    }
    function autoUpdateChatTitle(firstMessage) {
        const chatItem = document.querySelector(`[data-id="${currentChatId}"]`);
        if (chatItem) {
            const titleSpan = chatItem.querySelector('.chat-title');
            if (titleSpan && titleSpan.textContent === 'Новый чат') {
                let title = firstMessage.length > 30 
                    ? firstMessage.substring(0, 30) + '...' 
                    : firstMessage;
                titleSpan.textContent = title;
                titleSpan.title = title;
                saveChatTitle(currentChatId, title);
            }
        }
    }
    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message && fileInput.files.length === 0) return;
        setInputState(false);
        if (message) {
            addMessage(message, true, true, false);
        }
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            const fileMessage = `📎 Прикреплен файл: ${file.name}`;
            addMessage(fileMessage, true, true, false);
        }
        userInput.value = '';
        const typingDiv = createTypingIndicator();
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        try {
            console.log('Отправка запроса:', message);
        
            let requestOptions = {
                method: 'POST'
            };
            if (fileInput.files.length > 0) {
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('message', message || '');
                formData.append('chat_id', currentChatId); // Передаем chat_id
                requestOptions.body = formData;
            } else {
                requestOptions.headers = {
                    'Content-Type': 'application/json',
                };
                requestOptions.body = JSON.stringify({ message, chat_id: currentChatId }); // Передаем chat_id
            }
            const response = await fetch('/api/chat', requestOptions);
            console.log('Получен ответ:', response);
            const data = await response.json();
            console.log('Данные ответа:', data);
            if (typingDiv.parentNode) {
                typingDiv.style.opacity = '0';
                setTimeout(() => {
                    if (typingDiv.parentNode) {
                        chatMessages.removeChild(typingDiv);
                    }
                }, 200);
            }
            if (data.response) {
                addMessage(data.response, false, true, true);
                saveCurrentChat();
                const responseText = data.response.toLowerCase();
                if (responseText.includes('задача') && 
                    (responseText.includes('добавлена') || 
                    responseText.includes('удалена') || 
                    responseText.includes('выполнена') || 
                    responseText.includes('отмечена'))) {
                    setTimeout(() => {
                        fetchAndRenderTodos();
                    }, 100);
                }
            } else if (data.error) {
                if (data.error.includes ('timeout')) {
                addMessage("Ой, у меня небольшие проблемы. Подождите немного, пожалуйста.", false, true, false);
            } else {
                addMessage(`Ошибка: ${data.error}`, false, true, false);
            }
        }
            if (fileInput.files.length > 0) {
                fileInput.value = '';
                resetAttachButton();
            }

        } catch (error) {
            console.error('Ошибка при отправке запроса:', error);
        
            if (typingDiv.parentNode) {
                chatMessages.removeChild(typingDiv);
            }

            if (error.message && error.message.includes("timed out")) {
                addMessage("Ой, у меня небольшие проблемы. Подождите немного, пожалуйста.", false, true, false);
            } else {
                addMessage(`Ошибка: ${error.message}`, false, true, false);
            }
        } finally {
            setInputState(true);
        }
    }
    function createTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant typing-message';
        typingDiv.innerHTML = `
            <div class="message-content" style="display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 48px;">
                <div class="typing-indicator" style="margin: 0 auto;">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
                <div style="margin-top: 8px; font-size: 12px; color: #7fa7e2; letter-spacing: 0.5px; opacity: 0.8; text-align: center; animation: fadeIn 1s;">
                    Джейн печатает ответ...
                </div>
            </div>
        `;
        typingDiv.style.opacity = '0';
        typingDiv.style.transform = 'translateY(20px)';
        setTimeout(() => {
            typingDiv.style.transition = 'opacity 0.4s, transform 0.4s';
            typingDiv.style.opacity = '1';
            typingDiv.style.transform = 'translateY(0)';
        }, 10);
        return typingDiv;
    }
    function setInputState(enabled) {
        userInput.disabled = !enabled;
        sendButton.disabled = !enabled;
        attachButton.disabled = !enabled;
        
        if (enabled) {
            userInput.focus();
        }
    }
    fileInput.addEventListener('change', function() {
        isFileDialogOpen = false; 
        if (fileInput.files.length > 0) {
            const fileName = fileInput.files[0].name;
            const fileSize = (fileInput.files[0].size / 1024 / 1024).toFixed(2);
            attachButton.innerHTML = `
                <div class="file-info">
                    <span class="file-name">${fileName.length > 15 ? fileName.substring(0, 15) + '...' : fileName}</span>
                    <span class="file-size">${fileSize}MB</span>
                </div>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            `;
            attachButton.classList.add('file-selected');
            attachButton.title = `Файл: ${fileName} (${fileSize}MB) - Нажмите для отмены`;
        }
    });
    function resetAttachButton() {
        attachButton.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M21.44 11.05L12.25 20.24C11.1242 21.3658 9.59723 21.9983 8.005 21.9983C6.41277 21.9983 4.88584 21.3658 3.76 20.24C2.63416 19.1142 2.00166 17.5872 2.00166 15.995C2.00166 14.4028 2.63416 12.8758 3.76 11.75L12.33 3.18C13.0806 2.42975 14.0991 2.00129 15.16 2.00129C16.2209 2.00129 17.2394 2.42975 17.99 3.18C18.7403 3.93063 19.1687 4.94905 19.1687 5.995C19.1687 7.04095 18.7403 8.05937 17.99 8.81L9.41 17.39C9.03472 17.7653 8.52573 17.9788 7.995 17.9788C7.46427 17.9788 6.95528 17.7653 6.58 17.39C6.20472 17.0147 5.99122 16.5057 5.99122 15.975C5.99122 15.4443 6.20472 14.9353 6.58 14.56L14.54 6.6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
        attachButton.classList.remove('file-selected');
        attachButton.title = 'Прикрепить файл';
    }
    attachButton.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
    
        if (isFileDialogOpen) {
            return; // Предотвращаем повторное открытие
        }
    
        if (attachButton.classList.contains('file-selected')) {
            // Если файл уже выбран, очищаем его
            fileInput.value = '';
            resetAttachButton();
        } else {
            // Открываем диалог выбора файла
            isFileDialogOpen = true;
            fileInput.click();
            setTimeout(() => {
                if (fileInput.files.length === 0) {
                    isFileDialogOpen = false;
                }
            }, 1000);
        }
    });
    fileInput.addEventListener('cancel', function() {
        isFileDialogOpen = false;
    });
    function loadSavedChats() {
    const savedChats = Object.keys(localStorage)
        .filter(key => key.startsWith('chat-'))
        .map(key => {
            try {
                const data = localStorage.getItem(key);
                const parsed = JSON.parse(data);
                
                if (parsed.createdAt) {
                    return {
                        id: key,
                        title: parsed.title || 'Новый чат',
                        createdAt: parsed.createdAt
                    };
                } else {
                    const timestamp = parseInt(key.replace('chat-', ''));
                    return {
                        id: key,
                        title: 'Новый чат',
                        createdAt: timestamp || Date.now()
                    };
                }
            } catch (e) {
                console.error('Ошибка при загрузке чата:', key, e);
                return null;
            }
        })
        .filter(chat => chat !== null)
        .sort((a, b) => b.createdAt - a.createdAt); // Сортировка от новых к старым

    savedChats.forEach(chat => {
        addChatToSidebar(chat.id, chat.title);
    });

    // Восстанавливаем активный чат по id из localStorage
    const activeId = localStorage.getItem('activeChatId');
    let chatToActivate = null;
    if (activeId) {
        chatToActivate = document.querySelector('.chat-item[data-id="' + activeId + '"]');
        if (!chatToActivate) {
            localStorage.removeItem('activeChatId');
        }
    }
    if (!chatToActivate && savedChats.length > 0) {
        chatToActivate = document.querySelector('.chat-item');
    }
    if (chatToActivate) {
        setActiveChatItem(chatToActivate);
        loadChat(chatToActivate.dataset.id);
    } else {
        createNewChat();
    }
}
function initApp() {
    fetchAndRenderTodos();
    loadSavedChats();
    userInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    sendButton.addEventListener('click', sendMessage);
    addTodoBtn.addEventListener('click', async function() {
        const todoText = newTodoInput.value.trim();
        if (todoText) {
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: `добавь задачу ${todoText}` }),
                });
                const data = await response.json();
                
                if (data.response) {
                    newTodoInput.value = '';
                    setTimeout(() => {
                        fetchAndRenderTodos();
                    }, 100);;
                } else {
                    console.error('Ошибка при добавлении задачи:', data.error);
                }
            } catch (error) {
                console.error('Ошибка сети при добавлении задачи:', error);
            }
        }
    });
    newTodoInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            addTodoBtn.click();
        }
    });
    todoList.addEventListener('mouseover', function(e) {
        const listItem = e.target.closest('li');
        if (listItem) {
            const deleteBtn = listItem.querySelector('.delete-todo-btn');
            if (deleteBtn) {
                deleteBtn.style.opacity = '1';
                deleteBtn.style.pointerEvents = 'auto';
            }
        }
    });
    todoList.addEventListener('mouseout', function(e) {
        const listItem = e.target.closest('li');
        if (listItem) {
            const deleteBtn = listItem.querySelector('.delete-todo-btn');
            if (deleteBtn) {
                deleteBtn.style.opacity = '0';
                deleteBtn.style.pointerEvents = 'none';
            }
        }
    });
    document.querySelectorAll('.chat-item').forEach(item => {
        item.addEventListener('touchstart', function() {
            const actions = this.querySelector('.chat-actions');
            if (actions) {
                actions.style.opacity = '1';
            }
        });
    });
    
    // Обработчик для перетаскивания файлов
    chatMessages.addEventListener('dragover', function(e) {
        e.preventDefault();
        chatMessages.classList.add('drag-over');
    });
    
    chatMessages.addEventListener('dragleave', function() {
        chatMessages.classList.remove('drag-over');
    });
    
    chatMessages.addEventListener('drop', function(e) {
        e.preventDefault();
        chatMessages.classList.remove('drag-over');
        
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            const event = new Event('change');
            fileInput.dispatchEvent(event);
        }
    });

    function adjustChatWidth() {
        if (sidebar.classList.contains('hidden')) {
            chatContainer.style.width = '100%';
        } else {
            chatContainer.style.width = '';
        }
    }

    adjustChatWidth();
}

// Запускаем инициализацию приложения
initApp();

// Обработчик для сохранения чата при закрытии страницы
window.addEventListener('beforeunload', function() {
    saveCurrentChat();
});

// Функция для создания нового чата (экспортируем для доступа из HTML)
window.createNewChat = createNewChat;
});

