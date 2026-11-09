import { useI18n } from "../i18n/I18nProvider";
import { useEffect, useState } from "react";
import { ApiClient } from "../api/client";
import type { components } from "../../../../contracts/generated/api";

export function CoachPrivacyNotice() {
  const { locale } = useI18n();
  const [external, setExternal] = useState<boolean | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void new ApiClient().get<components["schemas"]["CoachProviderStatusV1"]>("/api/v1/coach/provider", { signal: controller.signal })
      .then((config) => { if (!controller.signal.aborted && config.schema_version === 1) setExternal(config.external); })
      .catch(() => {});
    return () => controller.abort();
  }, []);
  const ru = locale === "ru";
  return <aside className="privacy-notice">
    <strong>{ru ? "Как работает тренер" : "How the coach works"}</strong>
    <p>{ru ? "Stockfish проверяет позицию. Тренер объясняет ход на основе этого анализа." : "Stockfish checks the position. The coach explains the move using that analysis."}
      {external === false && (ru ? " Партия не отправляется в сторонний сервис." : " Your game is not sent to an external service.")}
      {external === true && (ru ? " OpenAI получает только тип подсказки, оценку качества хода и признаки шаха или взятия. Ходы и аккаунт не отправляются." : " OpenAI receives only the hint level, move quality, and whether there was a check or capture. Moves and account details are not sent.")}
    </p>
  </aside>;
}
