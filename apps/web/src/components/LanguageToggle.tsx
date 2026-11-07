import { useI18n } from "../i18n/I18nProvider";

export function LanguageToggle() {
  const { locale, setLocale, t } = useI18n();

  return (
    <label className="language-toggle">
      <span className="sr-only">{t.common.locale}</span>
      <select value={locale} onChange={(event) => setLocale(event.target.value as "ru" | "en")}>
        <option value="ru">RU</option>
        <option value="en">EN</option>
      </select>
    </label>
  );
}
