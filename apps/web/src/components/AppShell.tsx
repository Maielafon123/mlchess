import { NavLink, Outlet } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import { LanguageToggle } from "./LanguageToggle";
import { AuthStatus } from "../auth/AuthStatus";

export function AppShell() {
  const { t } = useI18n();

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink className="brand" to="/" aria-label={t.navigation.brand}>
          <span className="brand-mark" aria-hidden="true">M</span>
          <span>{t.navigation.brand}</span>
        </NavLink>
        <nav className="primary-nav" aria-label="Primary navigation">
          <NavLink to="/" end>{t.navigation.home}</NavLink>
          <NavLink to="/play">{t.navigation.play}</NavLink>
          <NavLink to="/learn">{t.navigation.learn}</NavLink>
        </nav>
        <div className="topbar-actions">
          <LanguageToggle />
          <AuthStatus />
        </div>
      </header>
      <main className="page-content"><Outlet /></main>
    </div>
  );
}
