import { Menu, Sparkles } from "lucide-react";
import ThemeToggle from "./ThemeToggle";
import { useAuth } from "../context/AuthContext";

interface Props {
  onToggleSidebar: () => void;
  onOpenDashboard: () => void;
  onGoHome: () => void;
  sidebarOpen: boolean;
}

export default function TopBar({ onToggleSidebar, onOpenDashboard, onGoHome, sidebarOpen }: Props) {
  const { user, profile } = useAuth();
  const displayName = profile?.fullName || user?.name || "User";
  const userInitial = displayName.charAt(0).toUpperCase();

  return (
    <header className="h-12 flex items-center px-3 border-b border-white/10 bg-gradient-to-r from-[#004d40] via-[#26A69A] to-[#00695C] animate-gradient-shift shadow-sm">
      <div className="flex items-center gap-1.5">
        <button
          onClick={onToggleSidebar}
          className="p-2 rounded-lg hover:bg-white/15 transition text-white"
          aria-label="Toggle sidebar"
        >
          <Menu size={18} className="text-white stroke-current" />
        </button>

        {/* Brand appears here only while the sidebar is collapsed — otherwise it lives in
            the sidebar header, so it's never shown twice. */}
        {!sidebarOpen && (
          <button
            type="button"
            onClick={onGoHome}
            className="flex items-center gap-1.5 pr-1 text-white hover:opacity-80 transition-opacity animate-fade-in"
            aria-label="Go to MindGPT home"
          >
            <div className="w-6 h-6 rounded-md bg-white/20 backdrop-blur-sm border border-white/30 flex items-center justify-center">
              <Sparkles className="w-3.5 h-3.5 text-white stroke-current" />
            </div>
            <span className="text-base font-bold tracking-wide">MindGPT</span>
          </button>
        )}
      </div>

      <div className="ml-auto flex items-center gap-2">
        <ThemeToggle />
        <button
          onClick={onOpenDashboard}
          className="flex items-center gap-2 pl-2 pr-1.5 py-1 rounded-lg hover:bg-white/15 transition text-white"
        >
          <span className="text-sm font-medium">{displayName}</span>
          <div className="w-7 h-7 rounded-full bg-white/20 backdrop-blur-sm border border-white/30 flex items-center justify-center text-white text-xs font-medium">
            {userInitial}
          </div>
        </button>
      </div>
    </header>
  );
}
