"use client";

import { useState } from "react";

interface User {
  id: number;
  username: string;
  avatar?: string;
  balance: number;
  totalDeals: number;
}

interface AddFriendModalProps {
  onClose: () => void;
  onAddFriend: (userId: number) => void;
}

export default function AddFriendModal({ onClose, onAddFriend }: AddFriendModalProps) {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (query: string) => {
    setSearch(query);
    if (query.length < 2) {
      setResults([]);
      return;
    }

    setLoading(true);
    // Имитация поиска пользователей
    setTimeout(() => {
      setResults([
        {
          id: 4,
          username: "david_gray",
          balance: 15,
          totalDeals: 8,
        },
        {
          id: 5,
          username: "sarah_white",
          balance: 20,
          totalDeals: 12,
        },
      ]);
      setLoading(false);
    }, 500);
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="w-full max-w-md p-8 card glass-card space-y-6 mx-4">
        <div className="flex justify-between items-center">
          <h3 className="text-xl font-bold tracking-wider">Поиск пользователей</h3>
          <button
            onClick={onClose}
            className="text-white/60 hover:text-white/80 transition-colors"
          >
            ✕
          </button>
        </div>

        <div className="space-y-4">
          <div className="relative">
            <input
              type="text"
              value={search}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="Введите имя пользователя..."
              className="input pr-10"
            />
            {loading && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                <div className="animate-spin rounded-full h-5 w-5 border border-white/20 border-t-white"></div>
              </div>
            )}
          </div>

          <div className="space-y-2">
            {results.map((user) => (
              <div
                key={user.id}
                className="card p-4 glass-card flex items-center gap-4"
              >
                <div className="w-12 h-12 bg-white/[0.03] backdrop-blur-xl rounded flex items-center justify-center text-lg font-bold text-white border border-white/[0.08] glass-card overflow-hidden">
                  {user.avatar ? (
                    <img src={user.avatar} alt={user.username} className="w-full h-full object-cover" />
                  ) : (
                    user.username[0].toUpperCase()
                  )}
                </div>
                <div className="flex-1">
                  <p className="font-medium">@{user.username}</p>
                  <div className="flex gap-4 mt-1">
                    <p className="text-white/40 text-xs tracking-wider">
                      Баланс: {user.balance}ч
                    </p>
                    <p className="text-white/40 text-xs tracking-wider">
                      Сделок: {user.totalDeals}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => onAddFriend(user.id)}
                  className="btn-success text-sm px-3 py-1.5"
                >
                  Добавить
                </button>
              </div>
            ))}
            {search.length >= 2 && results.length === 0 && !loading && (
              <p className="text-center text-white/40 py-4">
                Пользователи не найдены
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 