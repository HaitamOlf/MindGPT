import { useState } from "react";
import { Sparkles, AlertCircle, LogIn } from "lucide-react";
import LavaLamp from "./LavaLamp";
import { motion } from "framer-motion";
import { useAuth } from "../context/AuthContext";

// Sign-in is delegated entirely to Microsoft Entra External ID: this screen just launches
// the hosted sign-up/sign-in flow (the `email-auth` user flow). The app never handles
// credentials itself — no password fields, no Google button (Google, if enabled later, is
// a federated identity provider configured on the user flow, not in this code).

export default function Auth() {
  const { login } = useAuth();
  const [loading, setLoading] = useState(false);

  function handleSignIn() {
    setLoading(true);
    login(); // full-page redirect to the CIAM hosted flow
  }

  return (
    <div className="h-screen flex relative overflow-hidden">
      <LavaLamp />

      {/* Left side - Text */}
      <div className="flex-1 flex items-center justify-end pr-8 lg:pr-16 relative z-10 hidden lg:flex">
        <div className="max-w-lg">
          <h1 className="text-6xl lg:text-7xl font-bold text-white mb-4 leading-tight animate-fade-in-left drop-shadow-lg">
            Your safe space for journaling, venting, and sharing with no judgement.
          </h1>
          <p className="text-xl lg:text-2xl text-emerald-100 font-medium animate-fade-in-left" style={{ animationDelay: "200ms" }}>
            Made by university students, for university students.
          </p>
        </div>
      </div>

      {/* Right side - Form */}
      <div className="flex-1 flex items-center justify-center lg:justify-start pl-8 lg:pl-16 relative z-10 w-full">
        <div className="w-full max-w-md bg-teal-900/30 backdrop-blur-xl p-8 rounded-2xl shadow-2xl border border-white/20 relative">

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

          <div className="text-center mb-8 pt-4">
            <h1 className="text-3xl font-bold text-white mb-2">Welcome.</h1>
            <p className="text-sm text-emerald-100/80">Your very own mindful AI companion.</p>
          </div>

          <div className="space-y-4">
            <button
              onClick={handleSignIn}
              disabled={loading}
              className="w-full bg-emerald-500 text-white py-3 px-6 rounded-lg font-medium hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg shadow-emerald-500/20 flex items-center justify-center gap-3 active:scale-[0.98]"
            >
              <LogIn className="w-5 h-5" />
              {loading ? "Redirecting…" : "Sign in or create an account"}
            </button>

            <p className="text-center text-xs text-emerald-100/70">
              Secured by Microsoft Entra External ID. You'll be redirected to a protected
              sign-in page.
            </p>
          </div>

          {/* Disclaimer */}
          <div className="mt-6 p-4 bg-yellow-900/20 border border-yellow-500/30 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-yellow-100">
                <strong>Disclaimer:</strong> MindGPT is an AI companion and does not replace professional mental health services. If you are in crisis, please contact emergency services immediately.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
