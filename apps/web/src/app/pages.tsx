import { Link } from "react-router-dom";
import { SectionCard } from "../components/SectionCard";
import { GameSessionScreen } from "../features/game/GameSessionScreen";
import { AiGameScreen } from "../features/ai/AiGameScreen";
import { CoachGameScreen } from "../features/coach/CoachGameScreen";
import { PostGameReport } from "../components/PostGameReport";
import { FriendInviteScreen } from "../features/friend/FriendInviteScreen";
import { MatchmakingScreen } from "../features/matchmaking/MatchmakingScreen";
import { LessonCatalog } from "../features/learning/LessonCatalog";
import { PuzzleScreen } from "../features/learning/PuzzleScreen";
import { ProgressDashboard } from "../features/learning/ProgressDashboard";
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
          <SectionCard title={t.home.aiTitle}><p>{t.home.aiDescription}</p><Link className="button button-secondary" to="/play/ai">{t.home.aiTitle}</Link></SectionCard>
          <SectionCard title={t.home.coachTitle}><p>{t.home.coachDescription}</p><Link className="button button-secondary" to="/play/coach">{t.home.coachTitle}</Link></SectionCard>
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

export function AiPage() {
  const { t } = useI18n();
  return <div className="page"><section className="page-heading"><div className="eyebrow">AI mode</div><h1>{t.home.aiTitle}</h1><p>{t.home.aiDescription}</p></section><AiGameScreen /></div>;
}

export function CoachPage() {
  const { t } = useI18n();
  return <div className="page"><section className="page-heading"><div className="eyebrow">Coach mode</div><h1>{t.home.coachTitle}</h1><p>{t.home.coachDescription}</p></section><CoachGameScreen /></div>;
}

export function ReportPage() {
  const { t } = useI18n();
  return <div className="page"><section className="page-heading"><div className="eyebrow">Post-game review</div><h1>{t.home.title}</h1><p>Review only verified engine decisions from a finished game.</p></section><PostGameReport report={{ game_id: "pending", status: "pending", result: "unknown", analyzed_plies: 0, total_plies: 0, decisions: [] }} /></div>;
}

export function FriendPage() {
  return <div className="page"><section className="page-heading"><div className="eyebrow">Friend game</div><h1>Play locally with a friend</h1><p>Invite links and clocks are controlled by the server.</p></section><FriendInviteScreen /></div>;
}

export function MatchmakingPage() {
  return <div className="page"><section className="page-heading"><div className="eyebrow">Rated play</div><h1>Find an opponent</h1><p>Matchmaking, clocks and results are controlled by the server.</p></section><MatchmakingScreen /></div>;
}

export function PuzzlePage() {
  return <div className="page"><section className="page-heading"><div className="eyebrow">Puzzles</div><h1>Solve a chess puzzle</h1><p>Moves are graded by the server; hints are progressive.</p></section><PuzzleScreen /></div>;
}

export function ProgressPage() {
  return <div className="page"><section className="page-heading"><div className="eyebrow">Progress</div><h1>Review what you learned</h1><p>Progress and review dates come from server-graded attempts.</p></section><ProgressDashboard /></div>;
}

export function LearnPage() {
  const { t } = useI18n();
  return (
    <div className="page">
      <section className="page-heading"><div className="eyebrow">{t.learn.eyebrow}</div><h1>{t.learn.title}</h1><p>{t.learn.description}</p></section>
      <LessonCatalog />
      <div className="card-grid card-grid-3">
        <SectionCard title={t.learn.lessonTitle}><p>{t.learn.lessonDescription}</p><span className="status-chip">{t.common.placeholder}</span></SectionCard>
        <SectionCard title={t.learn.puzzleTitle}><p>{t.learn.puzzleDescription}</p><span className="status-chip">{t.common.placeholder}</span></SectionCard>
        <SectionCard title={t.learn.progressTitle}><p>{t.learn.progressDescription}</p><span className="status-chip">{t.common.placeholder}</span></SectionCard>
      </div>
    </div>
  );
}
