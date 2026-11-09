import { useI18n } from "../i18n/I18nProvider";
import { useAuth } from "./AuthProvider";

export function AuthStatus() {
  const { t, locale } = useI18n();
  const { status, user, signIn, signOut, googleAvailable, googlePending, googleFailed } = useAuth();

  if (status === "loading") return <span className="auth-state" role="status">{t.auth.loading}</span>;
  if (status === "error") return <span className="auth-state auth-error" role="alert">{t.auth.error}</span>;
  if (status === "forbidden") return <span className="auth-state auth-error" role="alert">{t.auth.forbidden}</span>;
  const google = googleAvailable && <button className="button button-ghost" type="button" disabled={googlePending} onClick={() => void signIn()}>{locale === "ru" ? "Войти через Google" : "Sign in with Google"}</button>;
  const loginError = googleFailed && <span className="auth-error" role="alert">{locale === "ru" ? "Не удалось войти через Google." : "Google sign-in failed."}</span>;
  if (status === "authenticated" && user?.kind === "guest") return <div className="auth-actions"><span className="auth-state">{locale === "ru" ? "Игра без регистрации" : "Playing as a guest"}</span>{google}{loginError}</div>;
  if (status === "guest") {
    return (
      <div className="auth-actions">
        <span className="auth-guest-notice">{t.auth.guestNotice}</span>
        {google || <button className="button button-ghost" type="button" onClick={() => void signIn()}>{t.navigation.signIn}</button>}
        {loginError}
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
