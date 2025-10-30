# Настройка Cloudflare Worker для обхода геоблокировки Claude API

Если ваш VDS находится в России, Claude API заблокирован. Cloudflare Workers позволяет создать прокси-сервер, который обходит эту блокировку **бесплатно**.

---

## 📋 Шаг 1: Создание Cloudflare Account

1. Откройте https://dash.cloudflare.com/sign-up
2. Зарегистрируйтесь (используйте email)
3. Подтвердите email адрес
4. Выберите **Free Plan** (бесплатный)

---

## 🚀 Шаг 2: Создание Worker

1. В панели Cloudflare перейдите в **Workers & Pages** (слева в меню)
2. Нажмите **Create Application**
3. Выберите **Create Worker**
4. Дайте имя воркеру (например): `claude-api-proxy`
5. Нажмите **Deploy** (деплой пустого воркера)

---

## 💻 Шаг 3: Настройка кода Worker

1. После создания нажмите кнопку **Edit Code** (вверху справа)
2. **Удалите весь код** в редакторе
3. **Скопируйте и вставьте** этот код:

```javascript
/**
 * Cloudflare Worker для проксирования Claude API
 * Обходит геоблокировку из России
 */

export default {
  async fetch(request, env) {
    // Разрешаем CORS для всех источников
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': '*',
    };

    // Обрабатываем preflight запросы
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      // Получаем оригинальный URL
      const url = new URL(request.url);

      // Заменяем хост на Claude API
      const apiUrl = `https://api.anthropic.com${url.pathname}${url.search}`;

      // Копируем заголовки
      const headers = new Headers(request.headers);

      // Добавляем заголовки для обхода геоблокировки
      headers.set('cf-ipcountry', 'US');

      // Создаем новый запрос к Claude API
      const newRequest = new Request(apiUrl, {
        method: request.method,
        headers: headers,
        body: request.body,
      });

      // Отправляем запрос
      const response = await fetch(newRequest);

      // Копируем ответ с добавлением CORS заголовков
      const modifiedResponse = new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: {
          ...Object.fromEntries(response.headers),
          ...corsHeaders,
        },
      });

      return modifiedResponse;

    } catch (error) {
      return new Response(JSON.stringify({
        error: 'Proxy error',
        message: error.message
      }), {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
          ...corsHeaders,
        },
      });
    }
  },
};
```

4. Нажмите **Save and Deploy** (внизу справа)

---

## 🔗 Шаг 4: Получение URL Worker

После деплоя вы увидите:
```
✅ Successfully deployed
```

И URL вида:
```
https://claude-api-proxy.<ваш-subdomain>.workers.dev
```

**Скопируйте этот URL!** Он понадобится для настройки бота.

### Пример URL:
```
https://claude-api-proxy.john-doe-123.workers.dev
```

---

## ⚙️ Шаг 5: Настройка бота

### На Windows (локальная разработка):

1. Откройте файл `.env`:
```cmd
notepad .env
```

2. Добавьте/обновите строку:
```env
CLOUDFLARE_WORKER_URL=https://claude-api-proxy.ваш-subdomain.workers.dev
```

Замените на **ваш реальный URL** из Шага 4.

### На VDS (production):

1. Подключитесь к VDS по SSH
2. Откройте файл .env:
```bash
nano /path/to/your/project/.env
```

3. Добавьте строку с вашим Worker URL:
```env
CLOUDFLARE_WORKER_URL=https://claude-api-proxy.ваш-subdomain.workers.dev
```

4. Сохраните файл (Ctrl+X, Y, Enter в nano)

---

## 🧪 Шаг 6: Тестирование

### Тест через curl (на VDS):

```bash
curl -X POST https://claude-api-proxy.ваш-subdomain.workers.dev/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: ваш_claude_api_key" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

Если работает, вы увидите JSON ответ от Claude.

### Тест через Python:

```python
import httpx

response = httpx.post(
    "https://claude-api-proxy.ваш-subdomain.workers.dev/v1/messages",
    headers={
        "Content-Type": "application/json",
        "x-api-key": "ваш_claude_api_key",
        "anthropic-version": "2023-06-01"
    },
    json={
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "Hello"}]
    },
    timeout=30
)

print(response.json())
```

---

## 🎉 Шаг 7: Перезапуск бота

После настройки .env перезапустите бота:

```bash
# Остановите старый процесс
pkill -f "python -m app.bot.main"

# Запустите заново
python -m app.bot.main
```

Или на Windows:
```cmd
# Остановите бота (Ctrl+C)
# Запустите снова:
python -m app.bot.main
```

В логах вы должны увидеть:
```
Using Cloudflare Worker proxy: https://claude-api-proxy.ваш-subdomain.workers.dev
```

---

## ✅ Проверка работы

Попробуйте создать план питания через бота. Если все настроено правильно:
- ✅ Ошибки 403 больше не будет
- ✅ Бот будет работать с Claude API через Worker
- ✅ Все запросы проходят через Cloudflare

---

## 📊 Лимиты Cloudflare Workers (Free Plan)

- **100,000 запросов в день** - более чем достаточно
- **10ms CPU time на запрос** - хватает для прокси
- **Неограниченная bandwidth** для запросов

Для бота эти лимиты более чем достаточны!

---

## 🔒 Безопасность

Worker не хранит:
- ❌ API ключи (они в заголовках запроса)
- ❌ Данные пользователей
- ❌ Промпты и ответы

Worker просто **пересылает** запросы к Claude API, добавляя заголовки для обхода геоблокировки.

---

## 🐛 Troubleshooting

### Проблема: Worker не работает

**Решение:**
1. Проверьте, что код Worker скопирован полностью
2. Убедитесь, что нажали "Save and Deploy"
3. Попробуйте тест через curl (см. Шаг 6)

### Проблема: Бот не использует Worker

**Решение:**
1. Проверьте, что `CLOUDFLARE_WORKER_URL` указан в `.env`
2. Перезапустите бота
3. Проверьте логи на наличие сообщения "Using Cloudflare Worker proxy"

### Проблема: Все еще ошибка 403

**Решение:**
1. Проверьте, что URL Worker правильный (без лишних символов)
2. Убедитесь, что Worker задеплоен (зеленая галочка в панели)
3. Попробуйте пересоздать Worker

---

## 📚 Дополнительные ресурсы

- Документация Cloudflare Workers: https://developers.cloudflare.com/workers/
- Dashboard Cloudflare: https://dash.cloudflare.com/
- Anthropic API Documentation: https://docs.anthropic.com/

---

## 💡 Советы

1. **Сохраните URL Worker** - он не изменится
2. **Можно создать несколько Workers** для разных проектов
3. **Worker работает 24/7** без дополнительной настройки
4. **Обновления кода Worker** применяются мгновенно после "Deploy"

---

**Готово!** Теперь ваш бот работает с Claude API через Cloudflare Worker, обходя геоблокировку. 🎉
