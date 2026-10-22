export enum AppView {
  CHAT = 'CHAT',
  DASHBOARD = 'DASHBOARD',
}

export interface UserProfile {
  fullName: string;
  dateOfBirth: string;
  country: string;
}

export interface ChatSession {
  id: string;
  title: string;
  date: Date;
}

export interface Message {
  id: string;
  role: 'user' | 'model';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

export interface JournalEntry {
  id: string;
  date: string;
  content: string;
  sentiment: 'Positive' | 'Neutral' | 'Negative';
  tags: string[];
  insight: string;
}

export interface MoodDataPoint {
  day: string;
  score: number; // 1-10
}

export interface SystemMetric {
  service: string;
  status: 'Operational' | 'Degraded' | 'Maintenance';
  latency: string;
  icon: string;
}