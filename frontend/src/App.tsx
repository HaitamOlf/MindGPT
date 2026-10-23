import { useState, useRef } from "react";
import Auth from "./components/Auth";
import ProfileSetup from "./components/ProfileSetup";
import Layout from "./components/Layout";
import Chat from "./components/Chat";
import AccountDashboard from "./components/AccountDashboard";
import { createConversation } from "./services/api";
import type { Conversation } from "./services/api";
import { useAuth } from "./context/AuthContext";

export default function App() {
  const { user, profile, authResolved, profileResolved, hydrating } = useAuth();
  const [showDashboard, setShowDashboard] = useState(false);
  const [currentConversation, setCurrentConversation] = useState<Conversation | null>(null);
  const [sidebarRefreshKey, setSidebarRefreshKey] = useState(0);
  const chatRef = useRef(null);

  const handleNewConversation = async () => {
    try {
      if (!user) return;
      const newConversation = await createConversation();
      setCurrentConversation(newConversation);
      setSidebarRefreshKey((prev) => prev + 1);
    } catch (error) {
      console.error("Error creating conversation:", error);
    }
  };

  const handleConversationSelect = (conversation: Conversation | null) => {
    setCurrentConversation(conversation);
  };

  const handleGoHome = () => {
    setCurrentConversation(null);
  };

  // Chat creates a conversation on the first message sent from the input box; refresh the
  // sidebar so the newly created conversation shows up in the list.
  const handleChatConversationChange = (conversation: Conversation | null) => {
    setCurrentConversation(conversation);
    if (conversation) setSidebarRefreshKey((prev) => prev + 1);
  };

  // Hydration gate: block everything until auth AND profile are resolved
  if (!authResolved || !profileResolved || hydrating) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    );
  }

  // Deterministic routing after hydration
  if (!user) {
    return <Auth />;
  }

  // Profile setup required for any signed-in user who hasn't set one yet.
  if (!profile) {
    return <ProfileSetup />;
  }

  return (
    <>
      <Layout
        onNewConversation={handleNewConversation}
        onOpenDashboard={() => setShowDashboard(true)}
        conversation={currentConversation}
        onConversationSelect={handleConversationSelect}
        sidebarRefreshKey={sidebarRefreshKey}
        onGoHome={handleGoHome}
      >
        <Chat
          ref={chatRef}
          conversation={currentConversation}
          onConversationChange={handleChatConversationChange}
        />
      </Layout>
      {showDashboard && (
        <AccountDashboard
          onClose={() => setShowDashboard(false)}
          userProfile={profile}
        />
      )}
    </>
  );
}
