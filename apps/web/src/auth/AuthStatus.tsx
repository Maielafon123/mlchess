import { useI18n } from "../i18n/I18nProvider";
import { useAuth } from "./AuthProvider";

export function AuthStatus() {
  const { t } = useI18n();
  const { status, user, signIn, signOut } = useAuth();

  if (status === "loading") return <span className="auth-state" role="status">{t.auth.loading}</span>;
  if (status === "error") return <span className="auth-state auth-error" role="alert">{t.auth.error}</span>;
  if (status === "forbidden") return <span className="auth-state auth-error" role="alert">{t.auth.forbidden}</span>;
  if (status === "guest") {
    return (
      <div className="auth-actions">
        <span className="auth-guest-notice">{t.auth.guestNotice}</span>
        <button className="button button-ghost" type="button" onClick={() => void signIn()}>{t.navigation.signIn}</button>
      </div>
    );
  }
  return (
    <div className="auth-actions">
      <span className="auth-user">{t.auth.signedInAs}: {user?.display_name}</span>
      <button className="button button-ghost" type="button" onClick={() => void signOut()}>{t.auth.signOut}</button>
    </div>
  );
}
