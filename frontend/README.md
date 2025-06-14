# TimeBankingBot Frontend

Frontend часть сервиса обмена времени (Time Banking), построенная на Next.js. Позволяет пользователям управлять своим профилем, друзьями, заявками и транзакциями через удобный веб-интерфейс.

## Технологии

- Next.js 14 - React фреймворк
- TypeScript - типизация
- Tailwind CSS - стилизация
- React Query - управление состоянием и кэширование
- Axios - HTTP клиент

## Установка и запуск

1. Установите зависимости:
npm install
# или
yarn install

2. Создайте файл .env.local в корне frontend директории:
NEXT_PUBLIC_API_BASE=http://localhost:8000

3. Запустите сервер разработки:
npm run dev
# или
yarn dev

Приложение будет доступно по адресу [http://localhost:3000](http://localhost:3000)

4. Добавьте в файл next.config.js свой url из например ngrok:
```
  env: {
    NEXT_PUBLIC_API_BASE: 'your_url',
  },
```

## Структура проекта

frontend/
├── src/
│   ├── app/              # Страницы приложения
│   ├── components/       # React компоненты
│   ├── lib/             # Утилиты и API клиент
│   └── styles/          # Глобальные стили
├── public/              # Статические файлы
└── package.json         # Зависимости

## Основные функции

- Аутентификация через Telegram
- Управление профилем и аватаром
- Поиск и добавление друзей
- Создание и управление заявками
- Просмотр истории транзакций
- Управление балансом часов

## Разработка

Для сборки проекта:
npm run build
# или
yarn build

Для запуска линтера:
npm run lint
# или
yarn lint

## Деплой

Проект можно развернуть на Vercel или любой другой платформе, поддерживающей Next.js.

## Лицензия

MIT
