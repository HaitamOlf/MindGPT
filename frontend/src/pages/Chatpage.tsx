import { useRef, useState } from "react";
import Sidebar from "../components/Sidebar";
import Chatbot, { type ChatbotHandle } from "../components/Chat";
import type { Conversation } from "../services/api";

export default function ChatPage() {
  const chatRef = useRef<ChatbotHandle>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);

  return (
    <div className="flex h-full">
      <Sidebar
        open={true}
        onNewConversation={() => {
          chatRef.current?.resetConversation();
          setConversation(null);
        }}
        conversation={conversation}
        onConversationSelect={(conv) => {
          setConversation(conv);
        }}
        onGoHome={() => setConversation(null)}
      />

      <div className="flex-1">
        <Chatbot ref={chatRef} conversation={conversation} onConversationChange={setConversation} />
      </div>
    </div>
  );
}
