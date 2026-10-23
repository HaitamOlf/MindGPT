import { Plus, Trash2, MessageSquare, Search, Sparkles } from "lucide-react";
import { useEffect, useState, useMemo } from "react";
import { getConversations, deleteConversation, type Conversation } from "../services/api";

interface Props {
  open: boolean;
  onNewConversation: () => void;
  conversation: Conversation | null;
  onConversationSelect: (conversation: Conversation | null) => void;
  refreshKey?: number;
  onGoHome: () => void;
}

export default function Sidebar({ open, onNewConversation, conversation, onConversationSelect, refreshKey, onGoHome }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        setLoading(true);
        const convs = await getConversations();
        setConversations(convs);
      } catch (error) {
        console.error("Error fetching conversations:", error);
      } finally {
        setLoading(false);
      }
    };

    if (open) {
      fetchConversations();
    }
  }, [open, refreshKey]);

  const handleDelete = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    try {
      await deleteConversation(convId);

      // Remove from local state
      setConversations((prev) => prev.filter((c) => c.id !== convId));

      // If deleted conversation was active, clear selection
      if (conversation?.id === convId) {
        onConversationSelect(null);
      }
    } catch (error) {
      console.error("Error deleting conversation:", error);
    }
  };

  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) {
      return conversations;
    }
    const query = searchQuery.toLowerCase().trim();
    return conversations.filter((conv) =>
      conv.title.toLowerCase().includes(query)
    );
  }, [conversations, searchQuery]);

  return (
    <aside
      className={`
        ${open ? "w-64" : "w-0"}
        transition-all duration-300 overflow-hidden
        bg-gray-800 dark:bg-gray-900 border-r border-gray-700 dark:border-gray-800
        flex flex-col
      `}
    >
      {/* Brand header — doubles as the home button and the sidebar title. Fixed width so
          it slides cleanly with the sidebar rather than reflowing during collapse. */}
      <button
        onClick={onGoHome}
        className="w-64 flex items-center gap-2 px-4 h-12 flex-shrink-0 hover:bg-white/5 transition-colors"
        aria-label="MindGPT home"
      >
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-teal-400 to-teal-600 flex items-center justify-center flex-shrink-0">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <span className="text-lg font-bold text-white tracking-wide">MindGPT</span>
      </button>

      <div className="w-64 px-3 pt-2 pb-2 space-y-2">
        <button
          onClick={onNewConversation}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-700 dark:bg-gray-800 hover:bg-gray-600 dark:hover:bg-gray-700 text-white transition-all duration-200 font-medium text-sm active:scale-95"
        >
          <Plus size={16} />
          New conversation
        </button>

        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-9 pr-3 py-2 rounded-lg bg-gray-700/50 dark:bg-gray-800/50 border border-gray-600 dark:border-gray-700 text-sm text-gray-200 dark:text-gray-300 placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-500/50 focus:border-teal-500/50 transition-all duration-200"
          />
        </div>
      </div>

      <div className="w-64 px-4 text-[11px] font-semibold text-gray-400 dark:text-gray-500 mb-1.5 uppercase tracking-wider">
        Your conversations
      </div>

      <div className="w-64 flex-1 overflow-y-auto px-2 space-y-0.5 scrollbar-hide">
        {loading ? (
          <div className="px-3 py-2 space-y-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-10 rounded-lg bg-gray-700/50 dark:bg-gray-800/50 animate-pulse"
              />
            ))}
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="px-3 py-2 text-sm text-gray-400 dark:text-gray-500 animate-fade-in">
            {searchQuery.trim() ? "No conversations found" : "No conversations yet"}
          </div>
        ) : (
          filteredConversations.map((conv, index) => (
            <div
              key={conv.id}
              onClick={() => onConversationSelect(conv)}
              className={`flex items-center justify-between px-3 py-2 rounded-lg transition-all duration-200 group cursor-pointer animate-fade-in ${conversation?.id === conv.id
                  ? "bg-gray-700 dark:bg-gray-800 ring-1 ring-teal-500/40"
                  : "hover:bg-gray-700/60 dark:hover:bg-gray-800/70"
                }`}
              style={{ animationDelay: `${index * 30}ms` }}
            >
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <MessageSquare size={13} className="text-gray-400 dark:text-gray-500 flex-shrink-0 transition-colors duration-200" />
                <span className="text-[13px] text-gray-200 dark:text-gray-300 truncate transition-colors duration-200">
                  {conv.title}
                </span>
              </div>
              <button
                onClick={(e) => handleDelete(e, conv.id)}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-gray-600 dark:hover:bg-gray-700 transition-all duration-200"
                aria-label="Delete conversation"
              >
                <Trash2
                  size={14}
                  className="text-gray-400 dark:text-gray-500 hover:text-red-400 dark:hover:text-red-400 transition-colors duration-200"
                />
              </button>
            </div>
          ))
        )}
      </div>

      <div className="w-64 px-4 py-3 text-[11px] text-gray-400 dark:text-gray-500 border-t border-gray-700 dark:border-gray-800">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
          <span>Stored in Azure Cosmos DB</span>
        </div>
      </div>
    </aside>
  );
}
