import { Sun, Moon } from "lucide-react";
import { useTheme } from "../context/ThemeContext";

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className="
        p-2 rounded-lg
        text-white
        hover:bg-white/20
        transition
      "
      aria-label="Toggle theme"
    >
      {theme === "dark" ? <Sun size={18} className="text-white stroke-current" /> : <Moon size={18} className="text-white stroke-current" />}
    </button>
  );
}
