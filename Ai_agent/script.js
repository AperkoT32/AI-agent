document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');

    function addMessage(content, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.textContent = content;
        
        messageDiv.appendChild(messageContent);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;
        
        addMessage(message, true);
        userInput.value = '';
        
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message assistant';
        loadingDiv.id = 'loading-message';
        
        const loadingContent = document.createElement('div');
        loadingContent.className = 'message-content';
        loadingContent.textContent = 'Думаю...';
        
        loadingDiv.appendChild(loadingContent);
        chatMessages.appendChild(loadingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        try {
            console.log('Отправка запроса:', message);
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message }),
            });
            
            console.log('Получен ответ:', response);
            const data = await response.json();
            console.log('Данные ответа:', data);
            
            const loadingMessage = document.getElementById('loading-message');
            if (loadingMessage) {
                chatMessages.removeChild(loadingMessage);
            }
            
            if (data.response) {
                addMessage(data.response);
            } else if (data.error) {
                addMessage(`Ошибка: ${data.error}`);
            }
        } catch (error) {
            console.error('Ошибка при отправке запроса:', error);
            
            const loadingMessage = document.getElementById('loading-message');
            if (loadingMessage) {
                chatMessages.removeChild(loadingMessage);
            }
            
            addMessage(`Ошибка: ${error.message}`);
        }
    }

    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
});