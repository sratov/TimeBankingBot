"use client";

import { useEffect, useState, useRef } from "react";
import CreateListingForm from "@/components/CreateListingForm";
import Profile from "@/components/Profile";
import { 
  getListings, 
  createListing as apiCreateListing, 
  authenticateWithTelegram, 
  getCurrentUser,
  applyForListing,
  acceptListing,
  confirmListing,
  completeListing,
  payForListing,
  checkAuth
} from "@/lib/api";

declare global {
  interface Window {
    Telegram: {
      WebApp: {
        initData: string;
        initDataUnsafe: {
          query_id: string;
          user: {
            id: number;
            first_name: string;
            last_name?: string;
            username?: string;
            language_code?: string;
            photo_url?: string;
          };
          auth_date: number;
          hash: string;
        };
        ready: () => void;
        expand: () => void;
      };
    };
  }
}

type View = "menu" | "listings" | "create" | "profile";

interface Listing {
  id: number;
  title: string;
  description: string;
  hours: number;
  listing_type: "request" | "offer";
  status: "active" | "pending_worker" | "pending_payment" | "in_progress" | "pending_confirmation" | "completed" | "cancelled";
  creator?: {
    id: number;
    username: string;
    balance: number;
    earned_hours: number;
    spent_hours: number;
  };
  worker?: {
    id: number;
    username: string;
  } | null;
}

interface UserProfile {
  id: number;
  telegram_id: number;
  username: string;
  avatar: string | null;
  balance: number;
  earned_hours: number;
  spent_hours: number;
  created_at: string;
}

export default function Home() {
  const [view, setView] = useState<View>("menu");
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [debugMessages, setDebugMessages] = useState<string[]>([]);
  const initialized = useRef(false);

  const addDebugMessage = (message: string) => {
    console.log("DEBUG:", message); // Keep console logs for browser debugging
    setDebugMessages(prev => [...prev, message]);
  };

  useEffect(() => {
    if (initialized.current) {
      addDebugMessage("Initialization already run, skipping duplicate.");
      return;
    }
    initialized.current = true;
    addDebugMessage("Marking initialization as run.");

    const initializeUser = async () => {
      try {
        addDebugMessage("Starting user initialization...");
        addDebugMessage(`Current origin: \${window.location.origin}`);
        addDebugMessage(`Environment API BASE: \${process.env.NEXT_PUBLIC_API_BASE}`);
        
        // Проверяем авторизацию через cookie
        try {
          addDebugMessage("Checking authentication status (checkAuth)...");
          const authData = await checkAuth();
          addDebugMessage(`checkAuth response: \${JSON.stringify(authData)}`);
          
          if (authData.authenticated) {
            addDebugMessage("User is authenticated via checkAuth.");
            
            if (authData.user) {
              setUserProfile(authData.user);
              addDebugMessage("User profile set from checkAuth.user.");
            } else {
              addDebugMessage("checkAuth.user is missing, attempting getCurrentUser()...");
              const userData = await getCurrentUser();
              setUserProfile(userData);
              addDebugMessage(`User profile loaded via getCurrentUser(): \${JSON.stringify(userData)}`);
            }
            
            addDebugMessage("Loading listings after checkAuth success...");
            const listingsData = await getListings();
            setListings(listingsData);
            addDebugMessage(`Listings loaded: \${listingsData.length} items.`);
            
            setLoading(false);
            return; 
          } else {
            addDebugMessage("checkAuth reported user is not authenticated.");
          }
        } catch (authError: any) {
          addDebugMessage(`checkAuth failed or user not authenticated: \${authError.message}`);
          if (authError.response) {
            addDebugMessage(`checkAuth error response: \${JSON.stringify(authError.response.data)}`);
          }
          // Продолжаем выполнение для аутентификации через Telegram
        }
        
        if (window.Telegram?.WebApp) {
          addDebugMessage("Telegram WebApp detected. Attempting Telegram authentication...");
          const webAppData = window.Telegram.WebApp;
          
          addDebugMessage(`Telegram WebApp data available: \${!!webAppData}`);
          
          if (webAppData.initData) {
            addDebugMessage(`Raw initData length: \${webAppData.initData.length}`);
            const initDataPreview = webAppData.initData.substring(0, 100);
            addDebugMessage(`initData preview (first 100 chars): \${initDataPreview}...`);
            addDebugMessage(`initData format check: hash: \${webAppData.initData.includes("hash=")}, user: \${webAppData.initData.includes("user=")}, auth_date: \${webAppData.initData.includes("auth_date=")}`);
          } else {
            addDebugMessage("Telegram WebApp initData is MISSING.");
          }
          
          if (webAppData.initDataUnsafe) {
            addDebugMessage(`initDataUnsafe (auth_date): \${webAppData.initDataUnsafe.auth_date}`);
            addDebugMessage(`initDataUnsafe (user.id): \${webAppData.initDataUnsafe.user?.id}`);
            addDebugMessage(`initDataUnsafe (user.username): \${webAppData.initDataUnsafe.user?.username}`);
          } else {
            addDebugMessage("Telegram WebApp initDataUnsafe is MISSING.");
          }
          
          try {
            if (webAppData.initData) {
              addDebugMessage("Sending authentication request to backend with initData...");
              const authResponse = await authenticateWithTelegram(webAppData.initData);
              addDebugMessage(`Backend auth RAW response: ${JSON.stringify(authResponse)}`); 

              let userJustSet: UserProfile | null = null;

              if (authResponse && authResponse.user) {
                setUserProfile(authResponse.user);
                userJustSet = authResponse.user;
                addDebugMessage(`User profile set from Telegram auth response. User: ${JSON.stringify(authResponse.user)}`);
              } else if (authResponse && authResponse.data && authResponse.data.user) {
                setUserProfile(authResponse.data.user);
                userJustSet = authResponse.data.user;
                addDebugMessage(`User profile set from Telegram auth response (authResponse.data.user). User: ${JSON.stringify(authResponse.data.user)}`);
              } else {
                addDebugMessage("Telegram authResponse.user is missing or authResponse structure is unexpected. Attempting getCurrentUser()...");
                try {
                  const userData = await getCurrentUser();
                  setUserProfile(userData);
                  userJustSet = userData;
                  addDebugMessage(`User profile loaded via getCurrentUser() after Telegram auth: ${JSON.stringify(userData)}`);
                } catch (getCurrentUserError: any) {
                  addDebugMessage(`Failed to get user profile via getCurrentUser() after auth: ${getCurrentUserError.message}`);
                }
              }

              if (userJustSet) {
                addDebugMessage("Loading listings (after Telegram auth)...");
                try {
                  const listingsData = await getListings();
                  setListings(listingsData);
                  addDebugMessage(`Listings loaded: \${listingsData.length} items.`);
                } catch (listingsError: any) {
                  let errorMsg = listingsError.message;
                  if (listingsError.response && listingsError.response.data && listingsError.response.data.detail) {
                    errorMsg += ` - Details: ${JSON.stringify(listingsError.response.data.detail)}`;
                  } else if (listingsError.response && listingsError.response.data) {
                    errorMsg += ` - Data: ${JSON.stringify(listingsError.response.data)}`;
                  }
                  addDebugMessage(`Error loading listings: ${errorMsg}`);
                  
                  if (listingsError.response) {
                    addDebugMessage(`Listings error status: \${listingsError.response.status}`);
                    addDebugMessage(`Listings error data: \${JSON.stringify(listingsError.response.data)}`);
                  }
                }
              }

            } else {
              addDebugMessage("No Telegram initData available for backend authentication.");
              alert('Error: No initialization data from Telegram for backend auth.');
            }
          } catch (error: any) {
            addDebugMessage(`Telegram authentication error: \${error.message}`);
            if (error.response) {
              addDebugMessage(`Telegram auth error status: \${error.response.status}`);
              addDebugMessage(`Telegram auth error data: \${JSON.stringify(error.response.data)}`);
            } else if (error.request) {
              addDebugMessage("Telegram auth: No response received.");
            }
            alert('Authentication error with Telegram. Please try refreshing the page.');
          }
        } else {
          addDebugMessage("No Telegram WebApp data available. App must be opened via Telegram.");
          alert('App must be opened through Telegram');
          setLoading(false);
          return;
        }
      } catch (error: any) {
        addDebugMessage(`FATAL Error during initialization: \${error.message}`);
        if (error.response) {
          addDebugMessage(`Fatal error status: \${error.response.status}`);
          addDebugMessage(`Fatal error data: \${JSON.stringify(error.response.data)}`);
        } else if (error.request) {
          addDebugMessage("Fatal error: No response received.");
        }
        alert('Major initialization error. Please try refreshing the page.');
      } finally {
        addDebugMessage("Initialization complete. Loading set to false.");
        setLoading(false);
      }
    };

    initializeUser();
  }, []);

  const handleCreateListing = async (data: {
    listing_type: "request" | "offer";
    title: string;
    description: string;
    hours: number;
  }) => {
    if (!userProfile) {
      alert('Пользователь не авторизован');
      return;
    }

    try {
      const newListing = await apiCreateListing({
        ...data,
        user_id: userProfile.id,
      });
      
      setListings([newListing, ...listings]);
      setView("listings");
    } catch (error: any) {
      console.error('Error creating listing:', error);
      alert('Не удалось создать заявку. Пожалуйста, попробуйте снова.');
    }
  };

  const handleApplyForListing = async (listingId: number) => {
    if (!userProfile) {
      alert('Пользователь не авторизован');
      return;
    }

    try {
      const updatedListing = await applyForListing(listingId);
      
      // Обновляем список заявок
      setListings(listings.map(listing => 
        listing.id === listingId ? updatedListing : listing
      ));
      
      alert('Вы успешно откликнулись на заявку!');
    } catch (error: any) {
      console.error('Error applying for listing:', error);
      alert('Не удалось откликнуться на заявку. Пожалуйста, попробуйте снова.');
    }
  };

  const handleAcceptListing = async (listingId: number) => {
    if (!userProfile) {
      alert('Пользователь не авторизован');
      return;
    }

    try {
      const updatedListing = await acceptListing(listingId);
      
      // Обновляем список заявок
      setListings(listings.map(listing => 
        listing.id === listingId ? updatedListing : listing
      ));
      
      if (updatedListing.listing_type === "request") {
        alert('Вы успешно подтвердили заявку! Исполнителю отправлена предоплата 33%.');
      } else {
        alert('Вы успешно подтвердили заявку! Создателю предложения отправлена предоплата 33%.');
      }
    } catch (error: any) {
      console.error('Error accepting listing:', error);
      alert('Не удалось подтвердить заявку. Пожалуйста, попробуйте снова.');
    }
  };

  const handleConfirmListing = async (listingId: number) => {
    if (!userProfile) {
      alert('Пользователь не авторизован');
      return;
    }

    try {
      const updatedListing = await confirmListing(listingId);
      
      // Обновляем список заявок
      setListings(listings.map(listing => 
        listing.id === listingId ? updatedListing : listing
      ));
      
      if (updatedListing.listing_type === "request") {
        alert('Вы успешно подтвердили выполнение заказа! Исполнителю отправлена оставшаяся оплата 67%.');
      } else {
        alert('Вы успешно подтвердили получение услуги! Создателю предложения отправлена оставшаяся оплата 67%.');
      }
    } catch (error: any) {
      console.error('Error confirming listing completion:', error);
      alert('Не удалось подтвердить выполнение заказа. Пожалуйста, попробуйте снова.');
    }
  };

  const handleCompleteListing = async (listingId: number) => {
    if (!userProfile) {
      alert('Пользователь не авторизован');
      return;
    }

    try {
      const updatedListing = await completeListing(listingId);
      
      // Обновляем список заявок
      setListings(listings.map(listing => 
        listing.id === listingId ? updatedListing : listing
      ));
      
      if (updatedListing.listing_type === "request") {
        alert('Вы отметили заказ как выполненный. Ожидайте подтверждения от заказчика для получения оставшейся оплаты.');
      } else {
        alert('Вы отметили услугу как выполненную. Ожидайте подтверждения от получателя услуги для получения оставшейся оплаты.');
      }
    } catch (error: any) {
      console.error('Error completing listing:', error);
      alert('Не удалось отметить заказ как выполненный. Пожалуйста, попробуйте снова.');
    }
  };

  const handlePayForListing = async (listingId: number) => {
    if (!userProfile) {
      alert('Пользователь не авторизован');
      return;
    }

    try {
      const updatedListing = await payForListing(listingId);
      
      // Обновляем список заявок
      setListings(listings.map(listing => 
        listing.id === listingId ? updatedListing : listing
      ));
      
      alert('Вы успешно оплатили предоплату 33% за услугу!');
    } catch (error: any) {
      console.error('Error paying for listing:', error);
      alert('Не удалось оплатить заказ. Пожалуйста, попробуйте снова.');
    }
  };

  const handleAvatarUpdate = (avatarUrl: string) => {
    if (userProfile) {
      setUserProfile({
        ...userProfile,
        avatar: avatarUrl,
      });
    }
  };

  const renderMenu = () => (
    <div className="space-y-12">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold tracking-wider">TIME BANKING</h1>
        <div className="h-px w-24 mx-auto bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>
        <p className="text-white/40 text-sm tracking-widest uppercase">Система обмена временем</p>
      </div>
      <div className="space-y-4 max-w-sm mx-auto">
        <button
          onClick={() => setView("create")}
          className="btn-primary w-full flex items-center justify-center gap-2 glass-card"
        >
          Создать заявку
        </button>
        <button
          onClick={() => setView("listings")}
          className="btn-success w-full flex items-center justify-center gap-2 glass-card"
        >
          Просмотр заявок
        </button>
        <button
          onClick={() => setView("profile")}
          className="btn-ghost w-full flex items-center justify-center gap-2"
        >
          Мой профиль
        </button>
      </div>
    </div>
  );

  const renderListings = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-8">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold tracking-wider">Доступные заявки</h2>
          <div className="h-px w-16 bg-gradient-to-r from-white/20 to-transparent"></div>
        </div>
        <button onClick={() => setView("menu")} className="btn-ghost">
          Назад
        </button>
      </div>
      <div className="grid gap-4">
        {listings.map((listing) => (
          <div key={listing.id} className="card p-6 space-y-4 glass-card highlight-border">
            <div className="flex justify-between items-start">
              <div>
                <span className={`status-badge ${
                  listing.listing_type === "request" ? "bg-white/[0.08]" : "bg-white/[0.08]"
                }`}>
                  {listing.listing_type === "request" ? "ПОИСК ПОМОЩИ" : "ПРЕДЛОЖЕНИЕ ПОМОЩИ"}
                </span>
                {listing.status !== "active" && (
                  <span className="status-badge ml-2 bg-blue-500/20">
                    {listing.status === "pending_worker" ? "ОЖИДАЕТ ПОДТВЕРЖДЕНИЯ" : 
                     listing.status === "in_progress" ? "В ПРОЦЕССЕ" :
                     listing.status === "completed" ? "ЗАВЕРШЕНО" :
                     listing.status === "cancelled" ? "ОТМЕНЕНО" : 
                     listing.status.toUpperCase()}
                  </span>
                )}
              </div>
              <span className="text-lg font-medium">{listing.hours}ч</span>
            </div>
            <h3 className="text-lg font-medium">{listing.title}</h3>
            <p className="text-white/90">{listing.description}</p>
            <div className="text-white/40 space-y-0.5 mt-2">
              <p>@{listing.creator?.username || 'Unknown'}</p>
              {listing.creator?.balance !== undefined && (
                <p>Баланс: {listing.creator.balance}ч</p>
              )}
            </div>
            {listing.status !== "active" && listing.worker && (
              <div className="text-white/60 text-sm mt-2">
                Исполнитель: @{listing.worker.username}
              </div>
            )}
            <div className="flex justify-end items-center mt-4">
              {/* Кнопка для отклика на активную заявку */}
              {listing.status === "active" && userProfile && listing.creator?.id !== userProfile.id && (
                <button 
                  onClick={() => handleApplyForListing(listing.id)}
                  className="btn-success text-sm backdrop-blur-sm"
                >
                  {listing.listing_type === "request" ? "Помочь" : "Принять"}
                </button>
              )}
              
              {/* Кнопка для подтверждения исполнителя создателем заявки */}
              {listing.status === "pending_worker" && userProfile && listing.creator?.id === userProfile.id && (
                <button 
                  onClick={() => handleAcceptListing(listing.id)}
                  className="btn-success text-sm backdrop-blur-sm"
                >
                  Подтвердить исполнителя
                </button>
              )}
              
              {/* Кнопка для оплаты предложения помощи */}
              {listing.status === "pending_payment" && userProfile && listing.worker?.id === userProfile.id && (
                <button 
                  onClick={() => handlePayForListing(listing.id)}
                  className="btn-success text-sm backdrop-blur-sm"
                >
                  Оплатить (33%)
                </button>
              )}
              
              {/* Кнопка для отметки о выполнении работы исполнителем */}
              {listing.status === "in_progress" && userProfile && (
                (listing.listing_type === "request" && listing.worker?.id === userProfile.id) || 
                (listing.listing_type === "offer" && listing.creator?.id === userProfile.id)
              ) && (
                <button 
                  onClick={() => handleCompleteListing(listing.id)}
                  className="btn-success text-sm backdrop-blur-sm"
                >
                  Отметить как выполненное
                </button>
              )}
              
              {/* Кнопка для подтверждения выполнения заказчиком */}
              {listing.status === "pending_confirmation" && userProfile && (
                (listing.listing_type === "request" && listing.creator?.id === userProfile.id) || 
                (listing.listing_type === "offer" && listing.worker?.id === userProfile.id)
              ) && (
                <button 
                  onClick={() => handleConfirmListing(listing.id)}
                  className="btn-success text-sm backdrop-blur-sm"
                >
                  Подтвердить выполнение
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  // Always render the debug panel at the top
  const renderDebugPanel = () => (
    <div 
      style={{ 
        position: 'fixed', 
        top: 0, 
        left: 0, 
        right: 0, 
        maxHeight: '200px', 
        overflowY: 'auto', 
        backgroundColor: 'rgba(0,0,0,0.8)', // Darker for better visibility
        color: 'lightgreen', 
        padding: '10px', 
        zIndex: 99999, // Ensure it's on top of everything
        fontSize: '12px', // Slightly larger font
        borderBottom: '1px solid green'
      }}
    >
      <h3 style={{ fontWeight: 'bold', marginBottom: '5px' }}>Debug Info:</h3>
      {debugMessages.map((msg, index) => (
        <div key={index}>{`[${index + 1}] ${msg}`}</div>
      ))}
      {debugMessages.length === 0 && <div>No debug messages yet...</div>}
    </div>
  );

  // Main render logic for the page content
  const renderPageContent = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center min-h-[50vh] pt-[210px]"> {/* Added padding top */}
          <div className="animate-spin rounded-full h-8 w-8 border border-white/20 border-t-white"></div>
        </div>
      );
    }
  
    if (!userProfile && !loading) { // Check !loading here to avoid showing this during initial auth attempt
      return (
        <div className="flex flex-col items-center justify-center min-h-[50vh] pt-[210px]"> {/* Added padding top */}
          <div className="text-center space-y-4 mb-8">
            <h1 className="text-2xl font-bold">Ошибка авторизации</h1>
            <p className="text-white/60">Пожалуйста, откройте приложение через Telegram</p>
            <div className="mt-4 p-4 bg-red-500/20 rounded-md text-white/80 max-w-md text-sm">
              <p>Это приложение работает только при открытии через Telegram Mini Apps.</p>
              <p className="mt-2">Проверьте, что вы открыли приложение через бота @TimeBankingBot, а не напрямую через браузер.</p>
            </div>
          </div>
        </div>
      );
    }

    // If userProfile is available, render based on view
    if (userProfile) {
      switch (view) {
        case "listings":
          return renderListings();
        case "create":
          return (
            <>
              <div className="space-y-4">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-xl font-bold tracking-tight">Создать заявку</h2>
                  <button onClick={() => setView("menu")} className="btn-ghost">
                    Назад
                  </button>
                </div>
                <CreateListingForm
                  onSubmit={handleCreateListing}
                  onCancel={() => setView("menu")}
                />
              </div>
            </>
          );
        case "profile":
          return (
            <>
              <div className="space-y-4">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-xl font-bold tracking-tight">Мой профиль</h2>
                  <button onClick={() => setView("menu")} className="btn-ghost">
                    Назад
                  </button>
                </div>
                <Profile user={userProfile} onAvatarUpdate={handleAvatarUpdate} />
              </div>
            </>
          );
        default: // "menu" or any other case
          return renderMenu();
      }
    }
    // Fallback if no specific content to render (should ideally be covered by loading or !userProfile)
    return <div className="pt-[210px]">Loading or no user profile...</div>;
  };

  return (
    <div className="container mx-auto p-4">
      {renderDebugPanel()} 
      {/* Add some margin to the main content to avoid overlap with debug panel */}
      <div style={{ paddingTop: '210px' }}> 
        {renderPageContent()}
      </div>
    </div>
  );
}
