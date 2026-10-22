import { useState, useRef } from "react";
import { ArrowRight, Sparkles, Calendar } from "lucide-react";
import LavaLamp from "./LavaLamp";
import { motion } from "framer-motion";
import { putProfile } from "../services/api";
import { useAuth } from "../context/AuthContext";

interface ProfileSetupProps {
  onComplete?: () => void;
}

const countries = [
  "Select a country...",
  "United States",
  "United Kingdom",
  "Canada",
  "France",
  "Germany",
  "Spain",
  "Italy",
  "Netherlands",
  "Belgium",
  "Switzerland",
  "Austria",
  "Portugal",
  "Sweden",
  "Norway",
  "Denmark",
  "Finland",
  "Poland",
  "Czech Republic",
  "Greece",
  "Ireland",
  "Australia",
  "New Zealand",
  "Japan",
  "South Korea",
  "China",
  "India",
  "Brazil",
  "Mexico",
  "Argentina",
  "Chile",
  "South Africa",
  "Egypt",
  "Morocco",
  "Other",
];

export default function ProfileSetup({ onComplete: _onComplete }: ProfileSetupProps) {
  const [fullName, setFullName] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [dateDisplay, setDateDisplay] = useState(""); // Display value in DD/MM/YYYY
  const [country, setCountry] = useState("");
  const [loading, setLoading] = useState(false);
  const dateInputRef = useRef<HTMLInputElement>(null);
  const { refreshProfile } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Form submitted", { fullName, dateOfBirth, dateDisplay, country });

    // Derive dateOfBirth from the visible field if needed
    let normalizedDate = dateOfBirth;
    if (!normalizedDate && dateDisplay && dateDisplay.length === 10) {
      const parts = dateDisplay.split("/");
      if (parts.length === 3) {
        const [day, month, year] = parts;
        const dayNum = parseInt(day, 10);
        const monthNum = parseInt(month, 10);
        const yearNum = parseInt(year, 10);
        if (
          dayNum >= 1 &&
          dayNum <= 31 &&
          monthNum >= 1 &&
          monthNum <= 12 &&
          yearNum >= 1900 &&
          yearNum <= 2100
        ) {
          normalizedDate = `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
          setDateOfBirth(normalizedDate);
        }
      }
    }

    if (!fullName || !normalizedDate || !country || country === "Select a country...") {
      return;
    }

    setLoading(true);
    try {
      // Convert dateOfBirth from YYYY-MM-DD to DD/MM/YYYY for storage
      const [year, month, day] = normalizedDate.split('-');
      const dateFormatted = `${day}/${month}/${year}`;

      // Persist via the backend API — the server derives the owner from the JWT, so there
      // is no client-side user id to track or re-verify.
      await putProfile({ fullName, dateOfBirth: dateFormatted, country });

      // Refresh profile state to unblock routing — App.tsx re-renders into the main app.
      await refreshProfile();
    } catch (error) {
      console.error("Error in profile submission:", error);
      alert(`Failed to save profile: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      <LavaLamp />

      <div className="w-full max-w-md bg-teal-900/30 backdrop-blur-xl rounded-2xl shadow-2xl border border-white/20 p-8 relative z-10">

        {/* Floating Logo Top-Left of Form */}
        <div className="absolute top-0 left-0 z-50 pointer-events-none -translate-x-1/2 -translate-y-1/2">
          <motion.div
            className="transform-gpu scale-[1.15]"
            animate={{ y: [-5, 5, -5] }}
            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          >
            <div className="flex items-center gap-2 bg-teal-950/50 backdrop-blur-lg px-10 py-4 rounded-full border border-white/20 shadow-lg">
              <Sparkles className="w-8 h-8 text-emerald-300" />
              <span className="text-3xl font-bold text-emerald-100 tracking-wide">MindGPT</span>
            </div>
          </motion.div>
        </div>

        {/* Header */}
        <div className="text-center mb-8 pt-4">
          <h1 className="text-3xl font-bold text-white mb-2">
            Welcome to MindGPT
          </h1>
          <p className="text-sm text-emerald-100/80">
            Your mindful AI companion. Please set up your profile.
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Full Name */}
          <div>
            <label className="block text-sm font-medium text-emerald-200 mb-2">
              Full Name
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Alex Chen"
              className="w-full px-4 py-3 rounded-lg border border-white/10 bg-black/20 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-transparent transition"
              required
            />
          </div>

          {/* Date of Birth */}
          <div>
            <label className="block text-sm font-medium text-emerald-200 mb-2">
              Date of Birth
            </label>
            <div className="relative">
              {/* Hidden date input for calendar picker */}
              <input
                ref={dateInputRef}
                type="date"
                value={dateOfBirth}
                onChange={(e) => {
                  const value = e.target.value;
                  if (value) {
                    // Convert YYYY-MM-DD to DD/MM/YYYY for storage and display
                    const [year, month, day] = value.split('-');
                    setDateOfBirth(value); // Store in YYYY-MM-DD format
                    setDateDisplay(`${day}/${month}/${year}`); // Display in DD/MM/YYYY
                  } else {
                    setDateOfBirth('');
                    setDateDisplay('');
                  }
                }}
                className="absolute opacity-0 pointer-events-none"
                required
              />
              {/* Visible input - editable with auto-formatting */}
              <input
                type="text"
                value={dateDisplay}
                onChange={(e) => {
                  let value = e.target.value.replace(/\D/g, ''); // Remove non-digits

                  // Format as DD/MM/YYYY as user types
                  if (value.length > 0) {
                    if (value.length <= 2) {
                      setDateDisplay(value);
                    } else if (value.length <= 4) {
                      setDateDisplay(`${value.slice(0, 2)}/${value.slice(2)}`);
                    } else {
                      setDateDisplay(`${value.slice(0, 2)}/${value.slice(2, 4)}/${value.slice(4, 8)}`);
                    }
                  } else {
                    setDateDisplay('');
                    setDateOfBirth('');
                  }

                  // If we have a complete date (DD/MM/YYYY), convert to YYYY-MM-DD for the hidden input
                  if (value.length === 8) {
                    const day = value.slice(0, 2);
                    const month = value.slice(2, 4);
                    const year = value.slice(4, 8);

                    // Validate the date
                    const dayNum = parseInt(day, 10);
                    const monthNum = parseInt(month, 10);
                    const yearNum = parseInt(year, 10);

                    if (dayNum >= 1 && dayNum <= 31 && monthNum >= 1 && monthNum <= 12 && yearNum >= 1900 && yearNum <= 2100) {
                      // Valid date - convert to YYYY-MM-DD for hidden input
                      setDateOfBirth(`${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`);
                    }
                  }
                }}
                onBlur={() => {
                  // Validate and format on blur
                  const parts = dateDisplay.split('/');
                  if (parts.length === 3) {
                    const [day, month, year] = parts;
                    const dayNum = parseInt(day, 10);
                    const monthNum = parseInt(month, 10);
                    const yearNum = parseInt(year, 10);

                    if (dayNum >= 1 && dayNum <= 31 && monthNum >= 1 && monthNum <= 12 && yearNum >= 1900 && yearNum <= 2100) {
                      // Ensure proper formatting with leading zeros
                      setDateDisplay(
                        `${day.padStart(2, '0')}/${month.padStart(2, '0')}/${year}`
                      );
                      // Update hidden input
                      setDateOfBirth(`${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`);
                    } else {
                      // Invalid date, clear it
                      setDateDisplay('');
                      setDateOfBirth('');
                    }
                  } else if (dateDisplay && dateDisplay.length > 0) {
                    // Incomplete date, clear it
                    setDateDisplay('');
                    setDateOfBirth('');
                  }
                }}
                placeholder="DD/MM/YYYY"
                maxLength={10}
                className="w-full px-4 py-3 pr-12 rounded-lg border border-white/10 bg-black/20 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-transparent transition"
                required
              />
              {/* Calendar icon button - only this opens the calendar */}
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  // Trigger the date picker
                  if (dateInputRef.current) {
                    if (dateInputRef.current.showPicker) {
                      dateInputRef.current.showPicker();
                    } else {
                      // Fallback for browsers that don't support showPicker
                      dateInputRef.current.click();
                    }
                  }
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-2 text-white/50 hover:text-white transition-colors cursor-pointer"
                aria-label="Open calendar"
              >
                <Calendar className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Country */}
          <div>
            <label className="block text-sm font-medium text-emerald-200 mb-2">
              Country of Origin
            </label>
            <div className="relative">
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full px-4 py-3 rounded-lg border border-white/10 bg-black/20 text-white focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-transparent transition appearance-none cursor-pointer [&>option]:bg-teal-900 [&>option]:text-white"
                required
              >
                {countries.map((c) => (
                  <option key={c} value={c === "Select a country..." ? "" : c}>
                    {c}
                  </option>
                ))}
              </select>
              <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                <svg
                  className="w-5 h-5 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </div>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading || !fullName || (!dateOfBirth && !dateDisplay) || !country || country === "Select a country..."}
            className="w-full bg-emerald-500 text-white py-3 px-6 rounded-lg font-medium hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20"
          >
            {loading ? (
              "Setting up..."
            ) : (
              <>
                Start Journey
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-8 text-center text-xs text-emerald-100/60">
          © 2025 MindGPT.
        </div>
      </div>
    </div>
  );
}




