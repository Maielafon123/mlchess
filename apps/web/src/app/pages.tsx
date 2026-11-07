import { Link } from "react-router-dom";
import { SectionCard } from "../components/SectionCard";
import { GameSessionScreen } from "../features/game/GameSessionScreen";
import { useI18n } from "../i18n/I18nProvider";

export function HomePage() {
  const { t } = useI18n();

  return (
    <div className="page page-home">
      <section className="hero" aria-labelledby="home-title">
        <div className="eyebrow">{t.home.eyebrow}</div>
        <h1 id="home-title">{t.home.title}</h1>
        <p className="hero-description">{t.home.description}</p>
        <div className="hero-actions">
          <Link className="button button-primary" to="/play">{t.home.openPlay}</Link>
          <Link className="button button-secondary" to="/learn">{t.home.openLearn}</Link>
        </div>
      </section>
      <section className="section" aria-labelledby="modes-title">
        <div className="section-heading"><div className="eyebrow">MLChess</div><h2 id="modes-title">{t.home.modesTitle}</h2></div>
        <div className="card-grid card-grid-3">
          <SectionCard title={t.home.aiTitle}><p>{t.home.aiDescription}</p><span className="status-chip">{t.common.placeholder}</span></SectionCard>
          <SectionCard title={t.home.coachTitle}><p>{t.home.coachDescription}</p><span className="status-chip">{t.common.placeholder}</span></SectionCard>
          <SectionCard title={t.home.learnTitle}><p>{t.home.learnDescription}</p><span className="status-chip">{t.common.placeholder}</span></SectionCard>
        </div>
      </section>
    </div>
  );
}

export function PlayPage() {
  const { t } = useI18n();
  return (
    <div className="page">
      <section className="page-heading"><div className="eyebrow">{t.play.eyebrow}</div><h1>{t.play.title}</h1><p>{t.play.description}</p></section>
      <div className="status-banner" role="status">{t.play.status}</div>
      <div className="play-layout">
        <section className="board-panel" aria-label={t.play.boardLabel}><GameSessionScreen /></section>
        <SectionCard title={t.play.capabilities}><p>{t.play.capabilitiesDescription}</p></SectionCard>
      </div>
    </div>
  );
}

export function LearnPage() {
  const { t } = useI18n();
  return (
    <div className="page">
      <section className="page-heading"><div className="eyebrow">{t.learn.eyebrow}</div><h1>{t.learn.title}</h1><p>{t.learn.description}</p></section>
      <div className="card-grid card-grid-3">
        <SectionCard title={t.learn.lessonTitle}><p>{t.learn.lessonDescription}</p><span className="status-chip">{t.common.placeholder}</span></SectionCard>
        <SectionCard title={t.learn.puzzleTitle}><p>{t.learn.puzzleDescription}</p><span className="status-chip">{t.common.placeholder}</span></SectionCard>
        <SectionCard title={t.learn.progressTitle}><p>{t.learn.progressDescription}</p><span className="status-chip">{t.common.placeholder}</span></SectionCard>
      </div>
    </div>
  );
}
