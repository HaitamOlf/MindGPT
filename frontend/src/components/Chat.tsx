import React, { useState, forwardRef, useImperativeHandle, useEffect, useRef } from "react";
import { sendMessage, getMessages, createConversation, uploadImage, type Conversation } from "../services/api";
import { ArrowUp, Sparkles, Image as ImageIcon, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useAuth } from "../context/AuthContext";

type Message = {
  role: "user" | "assistant";
  text: string;
  imageUrl?: string;
};

export type ChatbotHandle = {
  resetConversation: () => void;
  setConversation: (conversation: Conversation | null) => void;
};

const MindGPTAvatar = React.memo(function MindGPTAvatar() {
  return (
    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-teal-400 to-teal-600 flex items-center justify-center flex-shrink-0">
      <Sparkles className="w-4 h-4 text-white" />
    </div>
  );
});

const UserAvatar = React.memo(function UserAvatar({ name }: { name: string }) {
  const initial = name.charAt(0).toUpperCase();
  return (
    <div className="w-8 h-8 rounded-full bg-gray-600 dark:bg-gray-500 flex items-center justify-center flex-shrink-0 text-white text-xs font-medium">
      {initial}
    </div>
  );
});

interface ChatProps {
  conversation: Conversation | null;
  onConversationChange?: (conversation: Conversation | null) => void;
}

const Chatbot = forwardRef<ChatbotHandle, ChatProps>(function Chatbot(
  { conversation, onConversationChange },
  ref
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [hasInteracted, setHasInteracted] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [zoomedImageUrl, setZoomedImageUrl] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const previousConversationIdRef = useRef<string | null>(null);
  const isSendingRef = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { user, profile } = useAuth();
  const displayName = profile?.fullName || user?.name || "there";
  const currentConversationId = conversation?.id ?? null;

  const loadMessages = async (convId: string, preserveLocalMessages: boolean = false) => {
    try {
      setLoadingMessages(true);
      const fetchedMessages = await getMessages(convId);
      const localMessages: Message[] = fetchedMessages.map((msg) => ({
        role: msg.role,
        text: msg.text,
        imageUrl: msg.imageUrl,
      }));

      setMessages(localMessages);
      if (!preserveLocalMessages) {
        setHasInteracted(localMessages.length > 0);
      }
    } catch (error) {
      console.error("Error loading messages:", error);
      if (!preserveLocalMessages) {
        setMessages([]);
        setHasInteracted(false);
      }
    } finally {
      setLoadingMessages(false);
    }
  };

  useEffect(() => {
    const previousId = previousConversationIdRef.current;
    const currentId = currentConversationId;

    if (currentId) {
      if (previousId !== currentId && !isSendingRef.current) {
        loadMessages(currentId, false);
      } else if (previousId === null && currentId && !isSendingRef.current) {
        loadMessages(currentId, false);
      }
    } else {
      setMessages([]);
      setHasInteracted(false);
    }

    previousConversationIdRef.current = currentId;
  }, [currentConversationId]);

  useImperativeHandle(ref, () => ({
    resetConversation() {
      setMessages([]);
      setInput("");
      setHasInteracted(false);
      previousConversationIdRef.current = null;
    },
    setConversation(conversationArg: Conversation | null) {
      if (!conversationArg) {
        setMessages([]);
        setHasInteracted(false);
        previousConversationIdRef.current = null;
      }
    },
  }));

  useEffect(() => {
    if (messages.length === 0) return;
    const rafId = requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    });
    return () => cancelAnimationFrame(rafId);
  }, [messages, loading]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && zoomedImageUrl) setZoomedImageUrl(null);
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [zoomedImageUrl]);

  function handleImageSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.match(/^image\/(jpeg|jpg|png)$/)) {
      alert("Please select a JPEG or PNG image.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      alert("Image must be under 10 MB.");
      return;
    }
    setSelectedImage(file);
    const reader = new FileReader();
    reader.onloadend = () => setImagePreview(reader.result as string);
    reader.readAsDataURL(file);
  }

  function handleRemoveImage() {
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleSend() {
    if ((!input.trim() && !selectedImage) || loading) return;

    const userMsg = input || (selectedImage ? "[Image]" : "");
    const localPreview = imagePreview;
    const fileToSend = selectedImage;
    setInput("");

    setMessages((prev) => [
      ...prev,
      { role: "user", text: userMsg, imageUrl: localPreview ?? undefined },
    ]);

    isSendingRef.current = true;
    setHasInteracted(true);
    setLoading(true);

    try {
      let convId = currentConversationId;
      if (!convId) {
        const newConversation = await createConversation();
        convId = newConversation.id;
        onConversationChange?.(newConversation);
        previousConversationIdRef.current = convId;
      }
      if (!convId) throw new Error("Failed to create conversation");

      let imageBlobName: string | undefined;
      if (fileToSend) {
        const uploaded = await uploadImage(fileToSend, convId);
        imageBlobName = uploaded.blobName;
        handleRemoveImage();
      }

      const reply = await sendMessage(userMsg, convId, imageBlobName);
      setLoading(false);

      setTimeout(async () => {
        try {
          await loadMessages(convId!, false);
        } catch (error) {
          console.error("Error reloading messages:", error);
          setMessages((m) => [...m, { role: "assistant", text: reply }]);
        } finally {
          isSendingRef.current = false;
        }
      }, 300);
    } catch (error) {
      console.error("Error sending message:", error);
      const detail = error instanceof Error ? error.message : "";
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: detail.includes("could not be processed")
            ? "That image couldn't be processed. Please try a different one."
            : "I'm having trouble connecting right now. Please check your connection and try again.",
        },
      ]);
      isSendingRef.current = false;
      setLoading(false);
    }
  }

  const welcomeMessage = `Hello ${displayName}, I am MindGPT. I will be your personal emotional support AI companion through your journey. What do you want to talk about today?`;

  if (loadingMessages && currentConversationId && messages.length === 0) {
    return (
      <div className="flex flex-col h-full w-full items-center justify-center animate-fade-in">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-teal-400 to-teal-600 flex items-center justify-center animate-pulse">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">Loading conversation...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full bg-gray-50 dark:bg-gray-900">
      <div className="flex-1 overflow-y-auto mx-3 my-2 rounded-3xl bg-white dark:bg-gray-800/50 shadow-inner scrollbar-hide relative border border-black/5 dark:border-gray-700/50 overflow-hidden">
        <div className="px-4 py-6">
          <div className="max-w-3xl mx-auto space-y-5">
            {!currentConversationId && (
              <div className="flex flex-col items-center justify-center text-center h-full animate-fade-in pt-6">
                <div className="flex justify-center mb-4">
                  <div className="w-14 h-14 rounded-full bg-gradient-to-br from-teal-400 to-teal-600 flex items-center justify-center animate-pulse shadow-lg shadow-teal-500/20">
                    <Sparkles className="w-7 h-7 text-white" />
                  </div>
                </div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2 tracking-tight">MindGPT</h1>
                <p className="text-base text-gray-600 dark:text-gray-300 mb-6 font-light">
                  What do you want to talk about today?
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-xl mb-6">
                  <button
                    onClick={() => setInput("I'm feeling overwhelmed right now...")}
                    className="p-4 rounded-xl bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 hover:border-teal-400 dark:hover:border-teal-500 transition-all text-left group"
                  >
                    <span className="block text-sm font-medium text-gray-900 dark:text-white mb-1 group-hover:text-teal-600 dark:group-hover:text-teal-400 transition-colors">Venting</span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">I just need someone to listen without judgement.</span>
                  </button>
                  <button
                    onClick={() => setInput("Can you help me understand why I feel this way?")}
                    className="p-4 rounded-xl bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 hover:border-teal-400 dark:hover:border-teal-500 transition-all text-left group"
                  >
                    <span className="block text-sm font-medium text-gray-900 dark:text-white mb-1 group-hover:text-teal-600 dark:group-hover:text-teal-400 transition-colors">Understanding</span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">Help me figure out where these feelings come from.</span>
                  </button>
                </div>

                <p className="text-xs text-gray-500 dark:text-gray-500 max-w-md opacity-80">
                  MindGPT is an AI companion and does not replace professional mental health services. If you are in crisis, please contact emergency services immediately.
                </p>
              </div>
            )}

            {currentConversationId && !hasInteracted && messages.length === 0 && (
              <div className="flex items-start gap-3 animate-fade-in">
                <MindGPTAvatar />
                <div className="flex-1">
                  <div className="bg-gray-100 dark:bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3 max-w-2xl">
                    <p className="text-[15px] text-gray-800 dark:text-gray-200 leading-relaxed">
                      {welcomeMessage}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {currentConversationId &&
              messages.map((m, i) => (
                <div
                  key={`${currentConversationId}-${i}-${m.text.substring(0, 20)}`}
                  className={`flex items-start gap-3 mb-5 animate-fade-in ${m.role === "user" ? "flex-row-reverse" : ""
                    }`}
                  style={{ animationDelay: `${i * 40}ms` }}
                >
                  {m.role === "assistant" ? <MindGPTAvatar /> : <UserAvatar name={displayName} />}
                  <div className={`flex-1 ${m.role === "user" ? "flex justify-end" : ""}`}>
                    <div
                      className={`rounded-2xl px-4 py-2.5 max-w-2xl transition-all duration-200 ${m.role === "user"
                        ? "bg-gray-600 dark:bg-gray-700 text-white rounded-tr-sm"
                        : "bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-tl-sm"
                        }`}
                    >
                      {m.imageUrl && m.role === "user" && (
                        <div className="mb-2">
                          <img
                            src={m.imageUrl}
                            alt="Attached upload"
                            className="max-w-[200px] max-h-[180px] rounded-lg object-contain border border-white/20 cursor-pointer hover:opacity-90 transition-opacity"
                            onClick={() => m.imageUrl && setZoomedImageUrl(m.imageUrl)}
                            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                          />
                        </div>
                      )}
                      <div className="text-[15px] leading-relaxed overflow-hidden">
                        <ReactMarkdown
                          components={{
                            p: ({ node, ...props }) => <p className="mb-2 last:mb-0 whitespace-pre-wrap" {...props} />,
                            ul: ({ node, ...props }) => <ul className="list-disc list-outside ml-4 mb-2" {...props} />,
                            ol: ({ node, ...props }) => <ol className="list-decimal list-outside ml-4 mb-2" {...props} />,
                            li: ({ node, ...props }) => <li className="mb-0.5" {...props} />,
                            strong: ({ node, ...props }) => <strong className="font-semibold" {...props} />,
                            a: ({ node, ...props }) => <a className="underline hover:opacity-80" target="_blank" rel="noopener noreferrer" {...props} />
                          }}
                        >
                          {m.text}
                        </ReactMarkdown>
                      </div>
                    </div>
                  </div>
                </div>
              ))}

            {loading && currentConversationId && (
              <div className="flex items-start gap-3 animate-fade-in">
                <MindGPTAvatar />
                <div className="flex-1">
                  <div className="bg-gradient-to-r from-[#004d40] via-[#26A69A] to-[#00695C] animate-gradient-shift rounded-2xl rounded-tl-sm px-4 py-3 w-fit shadow-md">
                    <div className="flex items-center gap-1.5 animate-pulse">
                      <div className="w-1.5 h-1.5 bg-white rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                      <div className="w-1.5 h-1.5 bg-white rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                      <div className="w-1.5 h-1.5 bg-white rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>
      </div>

      <div className="border-t border-white/10 bg-gradient-to-r from-[#004d40] via-[#26A69A] to-[#00695C] animate-gradient-shift px-3 py-3 transition-colors duration-200 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)]">
        <div className="max-w-3xl mx-auto">
          {imagePreview && (
            <div className="mb-2 relative inline-block">
              <img
                src={imagePreview}
                alt="Preview"
                className="max-h-24 rounded-lg border-2 border-white/40 cursor-pointer hover:opacity-90 transition-opacity"
                onClick={() => setZoomedImageUrl(imagePreview)}
              />
              <button
                onClick={handleRemoveImage}
                className="icon-button absolute -top-2 -right-2 w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center hover:bg-red-600 transition-colors"
                aria-label="Remove image"
              >
                <X className="w-3 h-3 text-white stroke-current" />
              </button>
            </div>
          )}
          <div className="flex items-center gap-2 rounded-2xl bg-white/25 backdrop-blur-sm border border-white/40 px-3 py-2 shadow-sm transition-all duration-200 focus-within:ring-2 focus-within:ring-white/50 focus-within:border-white/50">
            <input
              type="file"
              ref={fileInputRef}
              accept="image/jpeg,image/jpg,image/png"
              onChange={handleImageSelect}
              className="hidden"
              id="image-upload"
              disabled={loading}
            />
            <label
              htmlFor="image-upload"
              className="w-7 h-7 rounded-full bg-white/20 backdrop-blur-sm border border-white/30 text-white flex items-center justify-center hover:bg-white/30 transition-all duration-200 active:scale-95 cursor-pointer flex-shrink-0"
              aria-label="Attach image"
            >
              <ImageIcon className="w-3.5 h-3.5 text-white stroke-current" />
            </label>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              placeholder="Talk to MindGPT..."
              className="flex-1 bg-transparent outline-none text-sm text-white placeholder:text-white/80 transition-colors duration-200"
              disabled={loading}
            />
            <button
              onClick={handleSend}
              disabled={loading || (!input.trim() && !selectedImage)}
              className="icon-button w-7 h-7 rounded-full bg-white/20 backdrop-blur-sm border border-white/30 text-white flex items-center justify-center hover:bg-white/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 active:scale-95 flex-shrink-0"
              aria-label="Send message"
            >
              <ArrowUp className="w-3.5 h-3.5 text-white stroke-current" />
            </button>
          </div>
          <p className="text-[11px] text-white/80 mt-2 text-center">
            MindGPT can make mistakes. Consider checking important information. This app is not a replacement for professional help.
          </p>
        </div>
      </div>

      {zoomedImageUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setZoomedImageUrl(null)}
        >
          <div className="relative max-w-[90vw] max-h-[90vh] flex items-center justify-center">
            <img
              src={zoomedImageUrl}
              alt="Zoomed"
              className="max-w-full max-h-[90vh] object-contain rounded-lg"
              onClick={(e) => e.stopPropagation()}
            />
            <button
              onClick={() => setZoomedImageUrl(null)}
              className="icon-button absolute top-4 right-4 w-9 h-9 rounded-full bg-white/20 backdrop-blur-sm text-white flex items-center justify-center hover:bg-white/30 transition-colors"
              aria-label="Close zoom"
            >
              <X className="w-5 h-5 text-white stroke-current" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
});

export default Chatbot;
