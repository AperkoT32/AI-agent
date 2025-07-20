import requests
from bs4 import BeautifulSoup
import re

def search_web(query: str):
    print(f"[DEBUG] Начало поиска для запроса: {query}")
    try:
        # Формируем URL для поиска в DuckDuckGo (HTML-версия, чтобы избежать сложного JavaScript)
        search_url = f"https://html.duckduckgo.com/html/?q={query}"
        print(f"[DEBUG] Сформирован URL поиска: {search_url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        search_response = requests.get(search_url, headers=headers, timeout=10)
        search_response.raise_for_status()  # Проверяем, что запрос прошел успешно
        print(f"[DEBUG] Получен ответ от поисковика, статус: {search_response.status_code}")
        
        soup = BeautifulSoup(search_response.text, 'html.parser')
        print("[DEBUG] HTML-страница успешно распарсена")
        
        links = soup.find_all('a', class_='result__a')
        
        if not links:
            print("[DEBUG] Не найдено ни одной ссылки в результатах поиска")
            return "По вашему запросу не найдено релевантных ссылок."
        page_url = links[0]['href']
        print(f"[DEBUG] Получена первая ссылка: {page_url}")
        
        page_response = requests.get(page_url, headers=headers, timeout=10)
        page_response.raise_for_status()
        page_soup = BeautifulSoup(page_response.text, 'html.parser')
        
        for element in page_soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.extract()
            
        text = page_soup.get_text()
        
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        cleaned_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        result = cleaned_text[:2000]
        print(f"[DEBUG] Получен финальный текст длиной {len(result)} символов")
        return result

    except requests.RequestException as e:
        error_msg = f"Ошибка при выполнении веб-поиска: {e}"
        print(f"[ERROR] {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Произошла непредвиденная ошибка при обработке страницы: {e}"
        print(f"[ERROR] {error_msg}")
        return error_msg

