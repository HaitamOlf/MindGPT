import { useState, useEffect, useCallback } from "react";
import { X, Power, Brain, Lock, ChevronDown, ChevronUp, Trash2 } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid } from "recharts";
import { useAuth } from "../context/AuthContext";
import { getWellness, getMemories, createMemory, deleteMemory } from "../services/api";

interface AccountDashboardProps {
  onClose: () => void;
  userProfile: {
    fullName: string;
    dateOfBirth: string;
    country: string;
  } | null;
}

// Simple age calculation - assumes format dd/mm/yyyy
function calculateAge(dateOfBirth: string): number {
  const parts = dateOfBirth.split("/");
  if (parts.length !== 3) return 22; // fallback

  const birthDay = parseInt(parts[0], 10);
  const birthMonth = parseInt(parts[1], 10) - 1; // JS months are 0-based
  const birthYear = parseInt(parts[2], 10);

  const today = new Date();

  let age = today.getFullYear() - birthYear;

  const hasHadBirthdayThisYear =
    today.getMonth() > birthMonth ||
    (today.getMonth() === birthMonth && today.getDate() >= birthDay);

  if (!hasHadBirthdayThisYear) {
    age -= 1;
  }

  return age;
}

// Convert sentiment score to wellness value (0-10)
function sentimentToWellness(sentiment: number): number {
  const value = Math.round((sentiment + 1) * 5);
  return Math.min(10, Math.max(0, value));
}

// --- NEW WELLNESS LOGIC START ---

type TimeRange = '7d' | '30d' | '12m';

interface WellnessDataPoint {
  day: string;    // Display label
  value: number | null; // Null indicates gap
  date: string;   // ISO date string
  tooltipLabel?: string;
}

function processWellnessData(
  rawData: Array<{ date: string; sentiment: number }>,
  range: TimeRange
): WellnessDataPoint[] {
  // 1. Determine Date Range
  const today = new Date();
  const endDate = new Date(today);
  const startDate = new Date(today);

  if (range === '7d') startDate.setDate(today.getDate() - 6);
  if (range === '30d') startDate.setDate(today.getDate() - 29);

  // For 12m, we want ~1 year back
  if (range === '12m') startDate.setFullYear(today.getFullYear() - 1);

  // 2. Map raw data
  const rawMap = new Map<string, number>();
  rawData.forEach(item => rawMap.set(item.date, item.sentiment));

  // --- 12 MONTH SPECIFIC LOGIC (Weekly Aggregation) ---
  if (range === '12m') {
    const weeklyData: WellnessDataPoint[] = [];
    const current = new Date(startDate);

    // Iterate in 7-day chunks until we pass endDate
    while (current <= endDate) {
      const weekStart = new Date(current);
      const weekEnd = new Date(current);
      weekEnd.setDate(weekEnd.getDate() + 6);

      let sum = 0;
      let count = 0;

      // Calculate average for this week
      const tempDay = new Date(weekStart);
      // Iterate days within the week
      // Ensure we don't go beyond endDate for data collection, 
      // but the bucket itself usually spans the week.
      while (tempDay <= weekEnd) {
        // Only count if within total range (optional, but cleaner)
        if (tempDay <= endDate) {
          const dStr = tempDay.toISOString().split('T')[0];
          if (rawMap.has(dStr)) {
            const sent = rawMap.get(dStr)!;
            sum += sentimentToWellness(sent);
            count++;
          }
        }
        tempDay.setDate(tempDay.getDate() + 1);
      }

      let finalValue: number | null = null;
      if (count > 0) {
        finalValue = parseFloat((sum / count).toFixed(1));
      }

      // Labeling: Month name if it's the start of a month
      const weekLabelDate = new Date(weekStart);
      const monthLabel = weekLabelDate.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
      // Heuristic: Show label if date is 1-7 (first week of month)
      const isStartOfMonth = weekLabelDate.getDate() <= 7;

      weeklyData.push({
        day: isStartOfMonth ? monthLabel : "",
        value: finalValue,
        date: weekStart.toISOString().split('T')[0],
        tooltipLabel: `Week of ${weekLabelDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })}`
      });

      // Next week
      current.setDate(current.getDate() + 7);
    }
    return weeklyData;
  }

  // --- 7D / 30D DAILY LOGIC (with smoothing) ---
  const expectedDates: string[] = [];
  const d = new Date(startDate);

  while (d <= endDate) {
    expectedDates.push(d.toISOString().split("T")[0]);
    d.setDate(d.getDate() + 1);
  }

  // Elo-Style Smoothing for Daily
  let currentWellness = 5;

  // Seed initial value if possible
  const firstDataIndex = expectedDates.findIndex(date => rawMap.has(date));
  if (firstDataIndex !== -1) {
    const sentiment = rawMap.get(expectedDates[firstDataIndex])!;
    currentWellness = sentimentToWellness(sentiment);
  }

  let lastInteractionDate: Date | null = null;
  const processed: WellnessDataPoint[] = [];

  for (let i = 0; i < expectedDates.length; i++) {
    const dateStr = expectedDates[i];
    const currentDate = new Date(dateStr);
    const hasData = rawMap.has(dateStr);

    let finalValue: number | null = null;
    const dayDate = new Date(dateStr);

    if (hasData) {
      const dailySentiment = rawMap.get(dateStr)!;
      const targetWellness = sentimentToWellness(dailySentiment);

      let K = 0.3;

      if (lastInteractionDate) {
        const diffTime = Math.abs(currentDate.getTime() - lastInteractionDate.getTime());
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        if (diffDays > 2) {
          const boost = Math.min(0.5, (diffDays - 2) * 0.1);
          K = 0.3 + boost;
        }
      }

      if (lastInteractionDate === null) {
        currentWellness = targetWellness;
      } else {
        const move = K * (targetWellness - currentWellness);
        currentWellness = currentWellness + move;
      }

      finalValue = parseFloat(currentWellness.toFixed(1));
      lastInteractionDate = currentDate;
    } else {
      finalValue = null;
    }

    // Label Logic (Enforce en-US)
    let dayLabel = "";
    const utcDate = dayDate;

    if (range === '7d') {
      const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      dayLabel = weekdays[utcDate.getUTCDay()];
    } else if (range === '30d') {
      if (utcDate.getUTCDate() === 1 || i === 0 || i === expectedDates.length - 1) {
        dayLabel = `${utcDate.getUTCDate()} ${utcDate.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })}`;
      } else if (utcDate.getUTCDate() % 5 === 0) {
        dayLabel = `${utcDate.getUTCDate()}`;
      }
    }

    processed.push({
      day: dayLabel,
      value: finalValue,
      date: dateStr,
      tooltipLabel: utcDate.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric', timeZone: 'UTC' })
    });
  }

  return processed;
}

interface Memory {
  id: string;
  content: string;
  source: string;
  confidence?: number;
  createdAt: string;
}

export default function AccountDashboard({ onClose, userProfile }: AccountDashboardProps) {
  const [wellnessData, setWellnessData] = useState<WellnessDataPoint[]>([]);
  const [timeRange, setTimeRange] = useState<TimeRange>('7d');
  const [memoryExpanded, setMemoryExpanded] = useState<boolean>(false);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [newMemoryInput, setNewMemoryInput] = useState<string>("");

  const { user, logout } = useAuth();

  const handleSignOut = () => logout();

  const fullName = userProfile?.fullName || user?.name || "there";
  const age = userProfile?.dateOfBirth ? calculateAge(userProfile.dateOfBirth) : 22;
  const country = userProfile?.country || "Not specified";
  const userId = user?.id;

  // Load wellness data from the backend (derived sentiment averages — no message text).
  useEffect(() => {
    const loadWellnessData = async () => {
      try {
        const points = await getWellness();
        const rawData = points.map((p) => ({ date: p.date, sentiment: p.averageSentiment }));

        const processed = processWellnessData(rawData, timeRange);
        if (processed.length === 0) {
          setWellnessData([{ day: "Today", value: 5, date: new Date().toISOString().split("T")[0] }]);
        } else {
          setWellnessData(processed);
        }
      } catch (error) {
        console.error("Error loading wellness data:", error);
        setWellnessData([{ day: "Today", value: 5, date: new Date().toISOString().split("T")[0] }]);
      }
    };

    loadWellnessData();
  }, [timeRange]);

  // Load memories from the backend (already returned newest-first).
  useEffect(() => {
    const loadMemories = async () => {
      try {
        setMemories(await getMemories());
      } catch (error) {
        console.error("Error loading memories:", error);
        setMemories([]);
      }
    };

    loadMemories();
  }, []);

  const handleAddMemory = async () => {
    if (!newMemoryInput.trim()) return;

    const inputValue = newMemoryInput.trim();
    setNewMemoryInput(""); // Clear input immediately for better UX

    try {
      await createMemory(inputValue);
      setMemories(await getMemories());
    } catch (error) {
      console.error("Error adding memory:", error);
      setNewMemoryInput(inputValue); // Restore input on error
      alert("Failed to add memory. Please check console for details.");
    }
  };

  const handleDeleteMemory = useCallback(async (memoryId: string) => {
    try {
      await deleteMemory(memoryId);
      setMemories((prev) => prev.filter((m) => m.id !== memoryId));
    } catch (error) {
      console.error("Error deleting memory:", error);
      alert("Failed to delete memory. Please try again.");
    }
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between rounded-t-2xl">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Account Dashboard</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Welcome back, {fullName}.</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Profile Info Section */}
          <div>
            <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">
              PROFILE INFO
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Full Name</p>
                <p className="text-base font-medium text-gray-900 dark:text-white">{fullName}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Age</p>
                <p className="text-base font-medium text-gray-900 dark:text-white">{age} years old</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Country</p>
                <p className="text-base font-medium text-gray-900 dark:text-white">{country}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Account Type</p>
                <p className="text-base font-medium text-teal-600 dark:text-teal-400">Student / Free Tier</p>
              </div>
            </div>
          </div>

          {/* Memory Bank Section */}
          <div>
            <button
              type="button"
              onClick={() => setMemoryExpanded((prev) => !prev)}
              className="w-full flex items-center justify-between mb-2"
            >
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-teal-500" />
                <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                  MEMORY BANK
                </h3>
              </div>
              {memoryExpanded ? (
                <ChevronUp className="w-4 h-4 text-gray-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-gray-400" />
              )}
            </button>
            {memoryExpanded && (
              <div className="space-y-3">
                {/* Add Memory Input */}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newMemoryInput}
                    onChange={(e) => setNewMemoryInput(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === "Enter") {
                        handleAddMemory();
                      }
                    }}
                    placeholder="Add a memory..."
                    className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-500"
                  />
                  <button
                    onClick={handleAddMemory}
                    className="px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition"
                  >
                    Add memory
                  </button>
                </div>

                {/* Memories List */}
                {memories.length === 0 ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400 italic">
                    No memories stored yet.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {memories.map((memory) => (
                      <div
                        key={memory.id}
                        className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600"
                      >
                        <div className="flex items-start justify-between mb-1">
                          <span className="text-xs font-medium text-teal-600 dark:text-teal-400">
                            {memory.source === "model" ? "Model memory" : "User memory"}
                          </span>
                          <button
                            onClick={() => handleDeleteMemory(memory.id)}
                            className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors text-gray-500 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400"
                            aria-label="Delete memory"
                          >
                            <Trash2 className="w-4 h-4 stroke-current" />
                          </button>
                        </div>
                        <p className="text-sm text-gray-900 dark:text-white">
                          {memory.content}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mt-3">
                  <Lock className="w-3 h-3" />
                  <span>Stored in Azure Cosmos DB</span>
                </div>
              </div>
            )}
          </div>

          {/* Wellness Trend Section */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Your Wellness Trend
              </h3>

              {/* Time Range Toggle */}
              <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
                {(['7d', '30d', '12m'] as TimeRange[]).map((range) => {
                  const label = range === '7d' ? '7 Days' : range === '30d' ? '30 Days' : '12 Months';
                  const isActive = timeRange === range;
                  return (
                    <button
                      key={range}
                      onClick={() => setTimeRange(range)}
                      className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${isActive
                        ? 'bg-white dark:bg-gray-600 text-teal-600 dark:text-teal-400 shadow-sm'
                        : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                        }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={wellnessData}>
                  <defs>
                    <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#14b8a6" stopOpacity={0} />
                    </linearGradient>
                  </defs>

                  <CartesianGrid vertical={false} strokeDasharray="3 3" opacity={0.1} />

                  <XAxis
                    dataKey="date"
                    axisLine={false}
                    tickLine={{ stroke: '#e5e7eb' }}
                    interval={0}
                    tick={(props) => {
                      const { x, y, payload } = props;
                      // Find the label corresponding to this date
                      const point = wellnessData.find(p => p.date === payload.value);
                      const label = point ? point.day : "";

                      return (
                        <g transform={`translate(${x},${y})`}>
                          <text x={0} y={0} dy={16} textAnchor="middle" fill="#6b7280" fontSize={11}>
                            {label}
                          </text>
                        </g>
                      );
                    }}
                    padding={{ left: 10, right: 10 }}
                  />
                  <YAxis
                    domain={[0, 10]}
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "#6b7280", fontSize: 11 }}
                    width={20}
                  />

                  <Tooltip
                    cursor={false}
                    content={({ active, payload, label }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        return (
                          <div className="bg-white dark:bg-gray-800 p-2 rounded-lg shadow-lg border border-gray-100 dark:border-gray-700 text-xs">
                            <p className="font-semibold text-gray-700 dark:text-gray-200 mb-1">{data.tooltipLabel || label}</p>
                            <p className="text-teal-600 dark:text-teal-400 font-bold">
                              Score: {data.value}
                            </p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />

                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#14b8a6"
                    strokeWidth={2}
                    fill="url(#colorValue)"
                    connectNulls={false}
                    dot={{ r: 3, fill: "#14b8a6", strokeWidth: 0, fillOpacity: 0.6 }}
                    activeDot={{ r: 6, strokeWidth: 2, stroke: "#fff" }}
                    animationDuration={500}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between rounded-b-2xl">
          <p className="text-xs text-gray-500 dark:text-gray-400">ID: {userId}</p>
          <button
            onClick={handleSignOut}
            className="flex items-center gap-2 px-4 py-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition font-medium"
          >
            <Power className="w-4 h-4" />
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
}
