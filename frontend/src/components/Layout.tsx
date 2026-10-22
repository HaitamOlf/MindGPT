import { type ReactNode, useState } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import type { Conversation } from "../services/api";

interface LayoutProps {
  children: ReactNode;
  onNewConversation: () => void;
  onOpenDashboard: () => void;
  conversation: Conversation | null;
  onConversationSelect: (conversation: Conversation | null) => void;
  sidebarRefreshKey?: number;
  onGoHome: () => void;
}

export default function Layout({ 
  children, 
  onNewConversation, 
  onOpenDashboard,
  conversation,
  onConversationSelect,
  sidebarRefreshKey,
  onGoHome,
}: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="h-screen w-screen flex text-gray-900 dark:text-white bg-gray-50 dark:bg-gray-900">
      {/* Sidebar */}
      <Sidebar
        open={sidebarOpen}
        onNewConversation={onNewConversation}
        conversation={conversation}
        onConversationSelect={onConversationSelect}
        refreshKey={sidebarRefreshKey}
        onGoHome={onGoHome}
      />

      {/* Main column */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top navigation bar */}
        <TopBar
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          onOpenDashboard={onOpenDashboard}
          onGoHome={onGoHome}
          sidebarOpen={sidebarOpen}
        />

        {/* Main content area (chat pages, etc.) */}
        <main className="flex-1 overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
