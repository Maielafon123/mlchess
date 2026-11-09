import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function initialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem("mlchess-theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("mlchess-theme", theme);
  }, [theme]);

  return (
    <button
      className="icon-button theme-toggle"
      type="button"
      aria-label={theme === "dark" ? "Включить светлую тему" : "Включить тёмную тему"}
      onClick={() => setTheme((current) => current === "dark" ? "light" : "dark")}
    >
      <span aria-hidden="true">{theme === "dark" ? "☼" : "◐"}</span>
    </button>
  );
}
