import { useI18n } from "../i18n/I18nProvider";

export function CoachPrivacyNotice() {
  const { locale } = useI18n();
  return <aside className="privacy-notice">
    <strong>{locale === "ru" ? "Как работает тренер" : "How the coach works"}</strong>
    <p>{locale === "ru" ? "Stockfish проверяет позицию. Тренер объясняет ход на основе этого анализа. Партия не отправляется в сторонний сервис." : "Stockfish checks the position. The coach explains the move using that analysis. Your game is not sent to an external service."}</p>
  </aside>;
}
