import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function initialTheme(): Theme {
  try {
    if (window.localStorage.getItem("mlchess-theme") === "light") return "light";
  } catch { /* Storage may be unavailable in private browsing. */ }
  return "dark";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { window.localStorage.setItem("mlchess-theme", theme); } catch { /* Keep the in-memory preference. */ }
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
