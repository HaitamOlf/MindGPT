// MindGPT backend API client. Every call attaches a fresh Entra access token acquired via
// MSAL (services/auth.ts); there is no per-call `token` parameter and no direct database
// access from the browser — all data goes through the backend.

import { acquireApiToken } from "./auth";

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string;

export interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: string;
  imageUrl?: string; // short-lived read SAS URL, minted per request by the backend
}

export interface Profile {
  fullName: string;
  dateOfBirth: string;
  country: string;
  completedAt?: string;
}

export interface MemoryItem {
  id: string;
  content: string;
  source: "user" | "model";
  confidence: number;
  createdAt: string;
}

export interface WellnessPoint {
  date: string;
  averageSentiment: number;
}

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await acquireApiToken();
  return fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      Authorization: `Bearer ${token}`,
    },
  });
}

async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, init);
  if (!res.ok) throw new Error(`${init.method ?? "GET"} ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

function jsonBody(body: unknown): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

// --- conversations ---------------------------------------------------------

export function createConversation(): Promise<Conversation> {
  return apiJson<Conversation>("/conversations", { method: "POST" });
}

export function getConversations(): Promise<Conversation[]> {
  return apiJson<Conversation[]>("/conversations");
}

export function getMessages(conversationId: string): Promise<Message[]> {
  return apiJson<Message[]>(`/conversations/${conversationId}/messages`);
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const res = await apiFetch(`/conversations/${conversationId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete conversation: ${res.status}`);
}

export async function sendMessage(
  message: string,
  conversationId: string,
  imageBlobName?: string
): Promise<string> {
  const body: { message: string; conversationId: string; imageBlobName?: string } = {
    message,
    conversationId,
  };
  if (imageBlobName) body.imageBlobName = imageBlobName;

  const data = await apiJson<{ reply: string; conversationId: string }>("/chat", jsonBody(body));
  return data.reply;
}

// Upload an image for a conversation. The backend validates + content-safety-scans it,
// stores it privately, and returns its blob name plus a short-lived read URL. Pass the
// returned blobName to sendMessage to attach it to a message.
export async function uploadImage(
  file: File,
  conversationId: string | null
): Promise<{ blobName: string; url: string }> {
  const form = new FormData();
  form.append("file", file);
  if (conversationId) form.append("conversationId", conversationId);

  // Note: no Content-Type header — the browser sets the multipart boundary itself.
  const res = await apiFetch("/uploads", { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

// --- profile ---------------------------------------------------------------

export async function getProfile(): Promise<Profile | null> {
  const res = await apiFetch("/profile");
  if (res.status === 404) return null; // first-time user — no profile set yet
  if (!res.ok) throw new Error(`Failed to load profile: ${res.status}`);
  return res.json() as Promise<Profile>;
}

export function putProfile(profile: Omit<Profile, "completedAt">): Promise<Profile> {
  return apiJson<Profile>("/profile", { ...jsonBody(profile), method: "PUT" });
}

// --- memory ----------------------------------------------------------------

export function getMemories(): Promise<MemoryItem[]> {
  return apiJson<MemoryItem[]>("/memory");
}

export function createMemory(content: string): Promise<MemoryItem> {
  return apiJson<MemoryItem>("/memory", jsonBody({ content }));
}

export async function deleteMemory(memoryId: string): Promise<void> {
  const res = await apiFetch(`/memory/${memoryId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete memory: ${res.status}`);
}

// --- wellness --------------------------------------------------------------

export function getWellness(days = 366): Promise<WellnessPoint[]> {
  return apiJson<WellnessPoint[]>(`/wellness?days=${days}`);
}
