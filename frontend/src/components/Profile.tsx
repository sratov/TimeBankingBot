"use client";

import { useState, useRef, useEffect } from "react";
import { uploadAvatar, getFriends, sendFriendRequest, getUserListings, acceptListing, searchUsers, getPendingFriendRequests, getTransactionPartners, acceptFriendRequest, rejectFriendRequest } from "@/lib/api";

interface Friend {
  id: number;
  user_id: number;
  friend_id: number;
  status: string;
  user: {
    id: number;
    username: string;
    avatar?: string;
    balance: number;
  };
  friend: {
    id: number;
    username: string;
    avatar?: string;
    balance: number;
  };
}

interface Listing {
  id: number;
  title: string;
  description: string;
  hours: number;
  listing_type: string;
  status: string;
  user_id: number;
  worker_id?: number;
  creator?: {
    id: number;
    username: string;
  };
  worker?: {
    id: number;
    username: string;
  };
}

interface User {
  id: number;
  username: string;
  avatar?: string;
  balance: number;
  earned_hours: number;
  spent_hours: number;
}

interface ProfileProps {
  id: number;
  telegram_id: number;
  username: string;
  avatar: string | null;
  balance: number;
  earned_hours: number;
  spent_hours: number;
  created_at: string;
  onAvatarUpdate?: (avatarUrl: string) => void;
}

export default function Profile({
  id,
  telegram_id,
  username,
  balance,
  earned_hours,
  spent_hours,
  avatar,
  onAvatarUpdate,
}: ProfileProps) {
  console.log("[Profile.tsx] Received props:", { id, telegram_id, username, balance, earned_hours, spent_hours, avatar });
  const [isEditingAvatar, setIsEditingAvatar] = useState(false);
  const [friends, setFriends] = useState<Friend[]>([]);
  const [friendUsername, setFriendUsername] = useState("");
  const [friendRequestStatus, setFriendRequestStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [listings, setListings] = useState<Listing[]>([]);
  const [isLoadingListings, setIsLoadingListings] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Новые состояния
  const [searchResults, setSearchResults] = useState<User[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [pendingRequests, setPendingRequests] = useState<Friend[]>([]);
  const [transactionPartners, setTransactionPartners] = useState<User[]>([]);
  const [activeTab, setActiveTab] = useState<'friends' | 'search' | 'pending' | 'partners'>('friends');

  // Загружаем данные, когда id пользователя доступен
  useEffect(() => {
    if (id) { // Only run if id is available
      loadFriends();
      loadUserListings(); // This uses the 'id' prop
      loadPendingRequests();
      loadTransactionPartners();
    }
  }, [id]); // Add id to the dependency array

  const loadFriends = async () => {
    try {
      setIsLoading(true);
      const friendsData = await getFriends();
      setFriends(friendsData);
    } catch (error) {
      console.error("Error loading friends:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadPendingRequests = async () => {
    try {
      const requests = await getPendingFriendRequests();
      setPendingRequests(requests);
    } catch (error) {
      console.error("Error loading pending friend requests:", error);
    }
  };

  const loadTransactionPartners = async () => {
    try {
      const partners = await getTransactionPartners();
      setTransactionPartners(partners);
    } catch (error) {
      console.error("Error loading transaction partners:", error);
    }
  };

  const loadUserListings = async () => {
    if (!id) return; // Extra guard just in case
    try {
      setIsLoadingListings(true);
      const listingsData = await getUserListings(id);
      setListings(listingsData);
    } catch (error) {
      console.error("Error loading user listings:", error);
    } finally {
      setIsLoadingListings(false);
    }
  };

  const handleAcceptListing = async (listingId: number) => {
    try {
      const updatedListing = await acceptListing(listingId);
      // Обновляем список заявок
      setListings(listings.map(listing => 
        listing.id === listingId ? updatedListing : listing
      ));
      alert("Заявка успешно принята!");
    } catch (error) {
      console.error("Error accepting listing:", error);
      alert("Ошибка при принятии заявки");
    }
  };

  const handleAvatarClick = () => {
    setIsEditingAvatar(true);
    fileInputRef.current?.click();
  };

  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      try {
        const result = await uploadAvatar(id, file);
        if (onAvatarUpdate) {
          onAvatarUpdate(result.avatar_url);
        }
      } catch (error) {
        console.error("Error uploading avatar:", error);
        alert("Не удалось загрузить аватар. Пожалуйста, попробуйте снова.");
      }
    }
    setIsEditingAvatar(false);
  };

  const handleSearchUsers = async () => {
    if (!friendUsername || friendUsername.length < 2) return;

    try {
      setIsSearching(true);
      const results = await searchUsers(friendUsername);
      setSearchResults(results);
      setActiveTab('search');
    } catch (error) {
      console.error("Error searching users:", error);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSendFriendRequest = async (friendId: number) => {
    try {
      setFriendRequestStatus("sending");
      await sendFriendRequest(friendId);
      
      // Обновляем список друзей
      await loadFriends();
      
      setFriendRequestStatus("success");
      setTimeout(() => setFriendRequestStatus(null), 3000);
    } catch (error: any) {
      console.error('Error sending friend request:', error);
      setFriendRequestStatus("error");
      setTimeout(() => setFriendRequestStatus(null), 3000);
    }
  };

  const handleAcceptFriendRequest = async (friendId: number) => {
    try {
      await acceptFriendRequest(friendId);
      // Обновляем списки
      loadFriends();
      loadPendingRequests();
    } catch (error) {
      console.error("Error accepting friend request:", error);
    }
  };

  const handleRejectFriendRequest = async (friendId: number) => {
    try {
      await rejectFriendRequest(friendId);
      // Обновляем список входящих запросов
      loadPendingRequests();
    } catch (error) {
      console.error("Error rejecting friend request:", error);
    }
  };

  // Функция для отображения аватара пользователя
  const renderUserAvatar = (user: { username: string, avatar?: string }) => {
    const avatarSrc = user.avatar && (user.avatar.startsWith('http://') || user.avatar.startsWith('https://'))
      ? user.avatar
      : `${typeof window !== 'undefined' ? `${window.location.origin}/api` : process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'}${user.avatar}`;

    return user.avatar ? (
      <img 
        src={avatarSrc} 
        alt={user.username} 
        className="w-10 h-10 rounded-full object-cover"
      />
    ) : (
      <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center">
        {user.username && user.username.length > 0 ? user.username[0].toUpperCase() : '?'}
      </div>
    );
  };

  // Функция для открытия диалога в Telegram
  const openTelegramChat = (username: string) => {
    window.open(`https://t.me/${username}`, '_blank');
  };

  return (
    <>
      <div className="space-y-8">
        <div className="card p-8 glass-card border border-white/10 backdrop-blur-md">
          <div className="flex items-start gap-8 mb-8">
            <div 
              onClick={handleAvatarClick}
              className="group relative cursor-pointer"
            >
              <div className="w-24 h-24 bg-black/40 backdrop-blur-xl rounded flex items-center justify-center text-3xl font-bold text-white shadow-xl border border-white/10 overflow-hidden">
                {avatar ? (
                  <img src={avatar && (avatar.startsWith('http://') || avatar.startsWith('https://')) ? avatar : `${typeof window !== 'undefined' ? `${window.location.origin}/api` : process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'}${avatar}`} alt={username} className="w-full h-full object-cover" />
                ) : (
                  username && username.length > 0 ? username[0].toUpperCase() : '?'
                )}
              </div>
              <div className="absolute inset-0 bg-black/60 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded">
                <span className="text-white/90 text-xs tracking-widest uppercase">Изменить</span>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleAvatarChange}
                className="hidden"
              />
            </div>
            <div className="flex-1 space-y-2">
              <h3 className="text-2xl font-bold tracking-wider">@{username || 'N/A'}</h3>
              <div className="h-px w-12 bg-gradient-to-r from-white/20 to-transparent"></div>
              <p className="text-white/40 text-sm tracking-widest">ID: {telegram_id !== undefined ? telegram_id : 'N/A'}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="card bg-black/40 p-6 text-center border border-white/10 backdrop-blur-md">
              <p className="text-3xl font-bold">{balance !== undefined ? balance.toFixed(1) : 'N/A'}</p>
              <p className="text-white/40 text-sm tracking-widest uppercase mt-2">Баланс часов</p>
            </div>
            <div className="card bg-black/40 p-6 text-center border border-white/10 backdrop-blur-md">
              <p className="text-3xl font-bold">{(Number(earned_hours) || 0) + (Number(spent_hours) || 0)}</p>
              <p className="text-white/40 text-sm tracking-widest uppercase mt-2">Всего сделок</p>
            </div>
          </div>
        </div>

        {/* Секция друзей */}
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <div className="space-y-1">
              <h4 className="text-xl font-bold tracking-wider">Друзья</h4>
              <div className="h-px w-16 bg-gradient-to-r from-white/20 to-transparent"></div>
            </div>
            <div className="flex items-center gap-2">
              {pendingRequests.length > 0 && (
                <span className="bg-black/40 border border-white/20 text-white px-2 py-1 rounded-full text-xs">
                  {pendingRequests.length} новых
                </span>
              )}
              <span className="text-white/40 text-sm tracking-widest">
                {friends.length} контактов
              </span>
            </div>
          </div>

          {/* Форма поиска друзей */}
          <div className="card p-6 glass-card border border-white/10 backdrop-blur-md mb-6">
            <h3 className="text-lg font-medium mb-4">Найти друзей</h3>
            <div className="flex gap-2">
              <input
                type="text"
                value={friendUsername}
                onChange={(e) => setFriendUsername(e.target.value)}
                placeholder="Имя пользователя"
                className="flex-1 bg-black/40 border border-white/10 rounded-md px-4 py-2 outline-none focus:ring-1 focus:ring-white/20 text-white"
              />
              <button
                onClick={handleSearchUsers}
                disabled={!friendUsername || friendUsername.length < 2 || isSearching}
                className={`px-3 py-1 bg-black border border-white/20 hover:border-white/60 text-white text-sm transition-all ${!friendUsername || friendUsername.length < 2 || isSearching ? 'opacity-50 cursor-not-allowed' : 'hover:bg-black/80'}`}
              >
                {isSearching ? "Поиск..." : "Найти"}
              </button>
            </div>
          </div>

          {/* Табы для переключения между разделами */}
          <div className="flex border-b border-white/10 mb-4">
            <button 
              onClick={() => setActiveTab('friends')}
              className={`px-4 py-2 ${activeTab === 'friends' ? 'border-b-2 border-white font-medium' : 'text-white/60 hover:text-white/80'} transition-all`}
            >
              Мои друзья
            </button>
            <button 
              onClick={() => setActiveTab('search')}
              className={`px-4 py-2 ${activeTab === 'search' ? 'border-b-2 border-white font-medium' : 'text-white/60 hover:text-white/80'} transition-all`}
            >
              Результаты поиска
            </button>
            <button 
              onClick={() => setActiveTab('pending')}
              className={`px-4 py-2 flex items-center ${activeTab === 'pending' ? 'border-b-2 border-white font-medium' : 'text-white/60 hover:text-white/80'} transition-all`}
            >
              Запросы
              {pendingRequests.length > 0 && (
                <span className="ml-2 bg-black/40 border border-white/20 text-white px-2 py-0.5 rounded-full text-xs">
                  {pendingRequests.length}
                </span>
              )}
            </button>
            <button 
              onClick={() => setActiveTab('partners')}
              className={`px-4 py-2 ${activeTab === 'partners' ? 'border-b-2 border-white font-medium' : 'text-white/60 hover:text-white/80'} transition-all`}
            >
              Партнеры по сделкам
            </button>
          </div>

          {/* Содержимое активного таба */}
          <div className="grid grid-cols-2 gap-4">
            {activeTab === 'friends' && (
              <>
                {isLoading ? (
                  <div className="col-span-2 flex justify-center py-4">
                    <div className="animate-spin rounded-full h-6 w-6 border border-white/20 border-t-white"></div>
                  </div>
                ) : friends.length === 0 ? (
                  <div className="col-span-2 text-center py-4">
                    <p className="text-white/60">У вас пока нет друзей</p>
                  </div>
                ) : (
                  friends.map((friend) => {
                    // Определяем, какой пользователь является другом (не текущим пользователем)
                    const friendUser = friend.user_id === id ? friend.friend : friend.user;
                    
                    return (
                      <div key={friend.id} className="card p-4 glass-card border border-white/10 backdrop-blur-md flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {renderUserAvatar(friendUser)}
                          <div>
                            <p className="font-medium">@{friendUser.username}</p>
                            <p className="text-white/40 text-sm">Баланс: {friendUser.balance}ч</p>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button 
                            onClick={() => openTelegramChat(friendUser.username)}
                            className="p-2 bg-black border border-white/20 hover:border-white/60 text-white text-sm transition-all"
                            title="Открыть чат в Telegram"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M18.384,22.779c0.322,0.228 0.737,0.285 1.107,0.145c0.37,-0.141 0.642,-0.457 0.724,-0.84c0.869,-4.084 2.977,-14.421 3.768,-18.136c0.06,-0.28 -0.04,-0.571 -0.26,-0.758c-0.22,-0.187 -0.525,-0.241 -0.797,-0.14c-4.193,1.552 -17.106,6.397 -22.384,8.35c-0.335,0.124 -0.553,0.446 -0.542,0.799c0.012,0.354 0.25,0.661 0.593,0.764c2.367,0.708 5.474,1.693 5.474,1.693c0,0 1.452,4.385 2.209,6.615c0.095,0.28 0.314,0.5 0.603,0.576c0.288,0.075 0.596,-0.004 0.811,-0.207c1.216,-1.148 3.096,-2.923 3.096,-2.923c0,0 3.572,2.619 5.598,4.062Zm-11.01,-8.677l1.679,5.538l0.373,-3.507c0,0 6.487,-5.851 10.185,-9.186c0.108,-0.098 0.123,-0.262 0.033,-0.377c-0.089,-0.115 -0.253,-0.142 -0.376,-0.064c-4.286,2.737 -11.894,7.596 -11.894,7.596Z"/>
                            </svg>
                          </button>
                          <button 
                            className="px-3 py-1 bg-transparent border border-white/20 hover:border-white/60 text-white/70 hover:text-white text-sm transition-all"
                          >
                            Профиль
                          </button>
                        </div>
                      </div>
                    );
                  })
                )}
              </>
            )}

            {activeTab === 'search' && (
              <>
                {isSearching ? (
                  <div className="col-span-2 flex justify-center py-4">
                    <div className="animate-spin rounded-full h-6 w-6 border border-white/20 border-t-white"></div>
                  </div>
                ) : searchResults.length === 0 ? (
                  <div className="col-span-2 text-center py-4">
                    <p className="text-white/60">Нет результатов поиска</p>
                  </div>
                ) : (
                  searchResults.map((user) => (
                    <div key={user.id} className="card p-4 glass-card border border-white/10 backdrop-blur-md flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {renderUserAvatar(user)}
                        <div>
                          <p className="font-medium">@{user.username}</p>
                          <p className="text-white/40 text-sm">Баланс: {user.balance}ч</p>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button 
                          onClick={() => openTelegramChat(user.username)}
                          className="p-2 bg-black border border-white/20 hover:border-white/60 text-white text-sm transition-all"
                          title="Открыть чат в Telegram"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M18.384,22.779c0.322,0.228 0.737,0.285 1.107,0.145c0.37,-0.141 0.642,-0.457 0.724,-0.84c0.869,-4.084 2.977,-14.421 3.768,-18.136c0.06,-0.28 -0.04,-0.571 -0.26,-0.758c-0.22,-0.187 -0.525,-0.241 -0.797,-0.14c-4.193,1.552 -17.106,6.397 -22.384,8.35c-0.335,0.124 -0.553,0.446 -0.542,0.799c0.012,0.354 0.25,0.661 0.593,0.764c2.367,0.708 5.474,1.693 5.474,1.693c0,0 1.452,4.385 2.209,6.615c0.095,0.28 0.314,0.5 0.603,0.576c0.288,0.075 0.596,-0.004 0.811,-0.207c1.216,-1.148 3.096,-2.923 3.096,-2.923c0,0 3.572,2.619 5.598,4.062Zm-11.01,-8.677l1.679,5.538l0.373,-3.507c0,0 6.487,-5.851 10.185,-9.186c0.108,-0.098 0.123,-0.262 0.033,-0.377c-0.089,-0.115 -0.253,-0.142 -0.376,-0.064c-4.286,2.737 -11.894,7.596 -11.894,7.596Z"/>
                          </svg>
                        </button>
                        <button 
                          onClick={() => handleSendFriendRequest(user.id)}
                          className="px-3 py-1 bg-transparent border border-white/20 hover:border-white/60 text-white/70 hover:text-white text-sm transition-all"
                          disabled={friendRequestStatus === "sending"}
                        >
                          {friendRequestStatus === "sending" ? "..." : "Добавить"}
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </>
            )}

            {activeTab === 'pending' && (
              <>
                {pendingRequests.length === 0 ? (
                  <div className="col-span-2 text-center py-4">
                    <p className="text-white/60">Нет входящих запросов в друзья</p>
                  </div>
                ) : (
                  pendingRequests.map((request) => (
                    <div key={request.id} className="card p-4 glass-card border border-white/10 backdrop-blur-md flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {renderUserAvatar(request.user)}
                        <div>
                          <p className="font-medium">@{request.user.username}</p>
                          <p className="text-white/40 text-sm">Баланс: {request.user.balance}ч</p>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button 
                          onClick={() => openTelegramChat(request.user.username)}
                          className="p-2 bg-black border border-white/20 hover:border-white/60 text-white text-sm transition-all"
                          title="Открыть чат в Telegram"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M18.384,22.779c0.322,0.228 0.737,0.285 1.107,0.145c0.37,-0.141 0.642,-0.457 0.724,-0.84c0.869,-4.084 2.977,-14.421 3.768,-18.136c0.06,-0.28 -0.04,-0.571 -0.26,-0.758c-0.22,-0.187 -0.525,-0.241 -0.797,-0.14c-4.193,1.552 -17.106,6.397 -22.384,8.35c-0.335,0.124 -0.553,0.446 -0.542,0.799c0.012,0.354 0.25,0.661 0.593,0.764c2.367,0.708 5.474,1.693 5.474,1.693c0,0 1.452,4.385 2.209,6.615c0.095,0.28 0.314,0.5 0.603,0.576c0.288,0.075 0.596,-0.004 0.811,-0.207c1.216,-1.148 3.096,-2.923 3.096,-2.923c0,0 3.572,2.619 5.598,4.062Zm-11.01,-8.677l1.679,5.538l0.373,-3.507c0,0 6.487,-5.851 10.185,-9.186c0.108,-0.098 0.123,-0.262 0.033,-0.377c-0.089,-0.115 -0.253,-0.142 -0.376,-0.064c-4.286,2.737 -11.894,7.596 -11.894,7.596Z"/>
                          </svg>
                        </button>
                        <button 
                          onClick={() => handleAcceptFriendRequest(request.id)}
                          className="px-3 py-1 bg-black border border-white/20 hover:border-white/60 text-white text-sm transition-all"
                        >
                          Принять
                        </button>
                        <button 
                          onClick={() => handleRejectFriendRequest(request.id)}
                          className="px-3 py-1 bg-transparent border border-white/20 hover:border-white/60 text-white/70 hover:text-white text-sm transition-all"
                        >
                          Отклонить
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </>
            )}

            {activeTab === 'partners' && (
              <>
                {transactionPartners.length === 0 ? (
                  <div className="col-span-2 text-center py-4">
                    <p className="text-white/60">У вас пока нет партнеров по сделкам</p>
                  </div>
                ) : (
                  transactionPartners.map((user) => {
                    // Проверяем, является ли пользователь уже другом
                    const isAlreadyFriend = friends.some(friend => 
                      (friend.user_id === user.id && friend.friend_id === id) || 
                      (friend.user_id === id && friend.friend_id === user.id)
                    );
                    
                    return (
                      <div key={user.id} className="card p-4 glass-card border border-white/10 backdrop-blur-md flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {renderUserAvatar(user)}
                          <div>
                            <p className="font-medium">@{user.username}</p>
                            <p className="text-white/40 text-sm">Баланс: {user.balance}ч</p>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button 
                            onClick={() => openTelegramChat(user.username)}
                            className="p-2 bg-black border border-white/20 hover:border-white/60 text-white text-sm transition-all"
                            title="Открыть чат в Telegram"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M18.384,22.779c0.322,0.228 0.737,0.285 1.107,0.145c0.37,-0.141 0.642,-0.457 0.724,-0.84c0.869,-4.084 2.977,-14.421 3.768,-18.136c0.06,-0.28 -0.04,-0.571 -0.26,-0.758c-0.22,-0.187 -0.525,-0.241 -0.797,-0.14c-4.193,1.552 -17.106,6.397 -22.384,8.35c-0.335,0.124 -0.553,0.446 -0.542,0.799c0.012,0.354 0.25,0.661 0.593,0.764c2.367,0.708 5.474,1.693 5.474,1.693c0,0 1.452,4.385 2.209,6.615c0.095,0.28 0.314,0.5 0.603,0.576c0.288,0.075 0.596,-0.004 0.811,-0.207c1.216,-1.148 3.096,-2.923 3.096,-2.923c0,0 3.572,2.619 5.598,4.062Zm-11.01,-8.677l1.679,5.538l0.373,-3.507c0,0 6.487,-5.851 10.185,-9.186c0.108,-0.098 0.123,-0.262 0.033,-0.377c-0.089,-0.115 -0.253,-0.142 -0.376,-0.064c-4.286,2.737 -11.894,7.596 -11.894,7.596Z"/>
                            </svg>
                          </button>
                          {!isAlreadyFriend && (
                            <button 
                              onClick={() => handleSendFriendRequest(user.id)}
                              className="px-3 py-1 bg-transparent border border-white/20 hover:border-white/60 text-white/70 hover:text-white text-sm transition-all"
                            >
                              Добавить
                            </button>
                          )}
                          {isAlreadyFriend && (
                            <span className="text-white/40 text-xs">Друзья</span>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </>
            )}
          </div>
        </div>

        {/* История заявок */}
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <div className="space-y-1">
              <h4 className="text-xl font-bold tracking-wider">История заявок</h4>
              <div className="h-px w-16 bg-gradient-to-r from-white/20 to-transparent"></div>
            </div>
            <span className="text-white/40 text-sm tracking-widest">
              Всего: {listings.length}
            </span>
          </div>
          <div className="grid gap-4">
            {isLoadingListings ? (
              <div className="flex justify-center py-4">
                <div className="animate-spin rounded-full h-6 w-6 border border-white/20 border-t-white"></div>
              </div>
            ) : listings.length === 0 ? (
              <div className="text-center py-4">
                <p className="text-white/60">У вас пока нет заявок</p>
              </div>
            ) : (
              listings.map((listing) => (
                <div
                  key={listing.id}
                  className="card p-6 space-y-4 glass-card border border-white/10 backdrop-blur-md"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <span className={`inline-block px-3 py-1 text-xs tracking-wider uppercase border ${
                        listing.listing_type === "request"
                          ? "border-white/20 bg-black/40 text-white/80"
                          : "border-white/20 bg-black/40 text-white/80"
                      }`}>
                        {listing.listing_type === "request" ? "ПОИСК ПОМОЩИ" : "ПРЕДЛОЖЕНИЕ ПОМОЩИ"}
                      </span>
                    </div>
                    <span className="text-lg font-medium">{listing.hours}ч</span>
                  </div>
                  <h3 className="text-lg font-medium">{listing.title}</h3>
                  <p className="text-white/90">{listing.description}</p>
                  
                  {/* Информация о статусе */}
                  <div className="mt-2">
                    <span className={`inline-block px-3 py-1 text-xs tracking-wider uppercase border ${
                      listing.status === "completed"
                        ? "border-white/20 bg-black/40 text-white/80"
                        : listing.status === "cancelled"
                        ? "border-white/20 bg-black/80 text-white/40"
                        : "border-white/20 bg-black/40 text-white/80"
                    }`}>
                      {listing.status === "pending_worker" ? "ОЖИДАЕТ ПОДТВЕРЖДЕНИЯ" : 
                       listing.status === "in_progress" ? "В ПРОЦЕССЕ" :
                       listing.status === "completed" ? "ЗАВЕРШЕНО" :
                       listing.status === "cancelled" ? "ОТМЕНЕНО" : 
                       listing.status.toUpperCase()}
                    </span>
                  </div>
                  
                  {/* Информация об исполнителе */}
                  {listing.worker && listing.status !== "active" && (
                    <div className="text-white/60 text-sm mt-2">
                      Исполнитель: @{listing.worker.username}
                    </div>
                  )}
                  
                  {/* Кнопки действий */}
                  <div className="flex justify-end mt-4">
                    {/* Кнопка для отмены активной заявки */}
                    {listing.status === "active" && listing.user_id === id && (
                      <button className="px-3 py-1 bg-transparent border border-white/20 hover:border-white/60 text-white/70 hover:text-white text-sm transition-all">
                        Отменить
                      </button>
                    )}
                    
                    {/* Кнопка для принятия заявки исполнителем */}
                    {listing.status === "pending_worker" && listing.user_id === id && listing.worker && (
                      <button 
                        onClick={() => handleAcceptListing(listing.id)}
                        className="px-3 py-1 bg-black border border-white/20 hover:border-white/60 text-white text-sm transition-all"
                      >
                        Принять исполнителя
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </>
  );
}