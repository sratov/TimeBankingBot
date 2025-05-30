"use client";

import { useEffect } from "react";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  useEffect(() => {
    // Проверяем наличие объекта Telegram
    if (typeof window !== 'undefined' && window.Telegram) {
      const tg = window.Telegram.WebApp;
      // Проверяем готовность WebApp
      if (tg) {
        console.log('Initializing Telegram WebApp...');
        try {
          tg.ready();
          tg.expand();
          
          // Настраиваем тему
          document.body.style.backgroundColor = '#000000';
          document.body.style.color = '#ffffff';
          
          console.log('Telegram WebApp initialized successfully');
        } catch (error) {
          console.error('Error initializing Telegram WebApp:', error);
        }
      } else {
        console.error('Telegram WebApp not available');
      }
    } else {
      console.error('Telegram object not found. Make sure the app is opened in Telegram.');
    }
  }, []);

  return (
    <html lang="en">
      <head>
        <script src="https://telegram.org/js/telegram-web-app.js" />
      </head>
      <body className={inter.className}>
        <main className="container mx-auto px-4 py-8 min-h-screen">
          {children}
        </main>
      </body>
    </html>
  );
}
