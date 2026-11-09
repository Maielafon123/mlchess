import { NavLink, Outlet } from "react-router-dom";
import { Suspense } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { LanguageToggle } from "./LanguageToggle";
import { AuthStatus } from "../auth/AuthStatus";
import { ConnectionStatus } from "./ConnectionStatus";
import { ThemeToggle } from "./ThemeToggle";

export function AppShell() {
  const { t } = useI18n();

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink className="brand" to="/" aria-label={t.navigation.brand}>
          <span className="brand-mark" aria-hidden="true">♞</span>
          <span className="brand-copy"><strong>{t.navigation.brand}</strong><small>ШАХМАТНАЯ АКАДЕМИЯ</small></span>
        </NavLink>
        <nav className="primary-nav" aria-label="Primary navigation">
          <NavLink to="/play">Играть</NavLink>
          <NavLink to="/learn">Обучение</NavLink>
          <NavLink to="/learn/puzzles" aria-label="Раздел задач">Задачи</NavLink>
          <NavLink to="/play/coach">ИИ-тренер</NavLink>
          <NavLink to="/play/report">Анализ</NavLink>
        </nav>
        <div className="topbar-actions">
          <LanguageToggle />
          <ThemeToggle />
          <AuthStatus />
        </div>
      </header>
      <ConnectionStatus />
      <main className="page-content"><Suspense fallback={<p role="status">Загружаем…</p>}><Outlet /></Suspense></main>
    </div>
  );
}
