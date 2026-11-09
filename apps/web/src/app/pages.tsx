import { Link, useSearchParams } from "react-router-dom";
import { lazy, useState } from "react";
import { SectionCard } from "../components/SectionCard";
import { CoachPrivacyNotice } from "../components/CoachPrivacyNotice";
import { useI18n } from "../i18n/I18nProvider";
import { useAuth } from "../auth/AuthProvider";

const AiGameScreen = lazy(() => import("../features/ai/AiGameScreen").then((module) => ({ default: module.AiGameScreen })));
const CoachGameScreen = lazy(() => import("../features/coach/CoachGameScreen").then((module) => ({ default: module.CoachGameScreen })));
const PostGameReview = lazy(() => import("../features/game/PostGameReview").then((module) => ({ default: module.PostGameReview })));
const FriendInviteScreen = lazy(() => import("../features/friend/FriendInviteScreen").then((module) => ({ default: module.FriendInviteScreen })));
const MatchmakingScreen = lazy(() => import("../features/matchmaking/MatchmakingScreen").then((module) => ({ default: module.MatchmakingScreen })));
const LessonCatalog = lazy(() => import("../features/learning/LessonCatalog").then((module) => ({ default: module.LessonCatalog })));
const PuzzleScreen = lazy(() => import("../features/learning/PuzzleScreen").then((module) => ({ default: module.PuzzleScreen })));
const ProgressDashboard = lazy(() => import("../features/learning/ProgressDashboard").then((module) => ({ default: module.ProgressDashboard })));

export function HomePage() {
  const { t } = useI18n();
  const [timeControl, setTimeControl] = useState("3+2");

  return (
    <div className="page page-home dashboard-home">
      <section className="home-main" aria-labelledby="home-title">
        <div className="section-kicker"><span>01 / ИГРА</span><span>ОНЛАЙН · ПОИСК ПАРТИИ</span></div>
        <div className="home-intro"><div><div className="eyebrow">{t.home.eyebrow}</div><h1 id="home-title"><span className="sr-only">{t.home.title}</span><span aria-hidden="true">Играй.<br /><em>Понимай.</em></span></h1><p className="hero-description">Становись сильнее с каждой партией.<br />Шахматы, анализ и обучение — в одном месте.</p></div><div className="hero-knight" aria-hidden="true">♞</div></div>
        <Link className="play-cta" to="/play"><span>{t.home.openPlay}</span><span aria-hidden="true">→</span></Link>
        <div className="time-heading"><span>КОНТРОЛЬ ВРЕМЕНИ</span><span>ВЫБЕРИТЕ РЕЖИМ</span></div>
        <div className="time-controls" role="group" aria-label="Контроль времени">{["1+0", "3+2", "5+0", "10+5", "15+10"].map((value) => <button key={value} className={timeControl === value ? "active" : ""} type="button" onClick={() => setTimeControl(value)}>{value}</button>)}</div>
        <div className="mode-list"><Link to="/play/ai"><span>02</span><strong>{t.home.aiTitle}</strong><span aria-hidden="true">↗</span></Link><Link to="/learn" aria-label={t.home.openLearn}><span>03</span><strong>{t.home.learnTitle}</strong><span aria-hidden="true">↗</span></Link><Link to="/play/coach"><span>04</span><strong>{t.home.coachTitle}</strong><span aria-hidden="true">↗</span></Link></div>
        <div className="dashboard-note"><span>ML / 26</span><em>Уважение к партии. Внимание к каждому ходу.</em></div>
      </section>
      <aside className="home-side" aria-label="Ваш прогресс"><div className="side-heading"><span>ВАШ ПРОГРЕСС</span><span>РАПИД</span></div><div className="rating-block"><strong>1847</strong><span>РЕЙТИНГ<br /><b>+12 за 7 дней</b></span></div><div className="trend-chart" aria-label="Динамика рейтинга"><svg viewBox="0 0 320 72" role="img"><polyline points="0,55 22,61 46,44 72,49 96,39 122,45 149,28 172,35 198,20 225,28 248,14 272,21 297,8 320,13" /></svg></div><div className="metric-row"><div><strong>327</strong><span>партий</span></div><div><strong>54%</strong><span>побед</span></div><div><strong>08</strong><span>серия</span></div></div><div className="coach-card"><div className="side-heading"><span>РЕКОМЕНДАЦИЯ ТРЕНЕРА</span><span>№ 018</span></div><div className="coach-number">01 <strong>Позиционное<br />мышление</strong></div><p>Учись распознавать слабые поля до того, как они станут проблемой.</p><div className="progress-line"><span style={{ width: "58%" }} /></div><small>Урок 3 из 7 · 8 минут</small><Link to="/learn">Продолжить урок <span aria-hidden="true">→</span></Link></div></aside>
    </div>
  );
}

export function PlayPage() {
  const { t } = useI18n();
  return (
    <div className="page game-page">
      <div className="section-kicker"><span>01 / ИГРА</span><span>ВЫБЕРИТЕ ФОРМАТ</span></div>
      <section className="page-heading"><div className="eyebrow">{t.play.eyebrow}</div><h1><span className="sr-only">{t.play.title}</span><span aria-hidden="true">Играй.<br /><em>Понимай.</em></span></h1><p>{t.play.description}</p></section>
      <div className="card-grid catalog-grid concept-mode-grid">
        <SectionCard title="С другом"><p>Отправьте ссылку и играйте без регистрации с любого устройства.</p><Link className="button button-primary" to="/play/friend">Создать вызов</Link></SectionCard>
        <SectionCard title="С компьютером"><p>Выберите сторону и силу соперника. Партия сохраняется автоматически.</p><Link className="button button-secondary" to="/play/ai">Играть с компьютером</Link></SectionCard>
        <SectionCard title="С тренером"><p>Разбирайте свои ходы во время партии с компьютером.</p><Link className="button button-secondary" to="/play/coach">Играть с тренером</Link></SectionCard>
        <SectionCard title="На рейтинг"><p>Найдите соперника в рапид или блиц. Нужен аккаунт.</p><Link className="button button-secondary" to="/play/matchmaking">Рейтинговая игра</Link></SectionCard>
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
  return <div className="page"><section className="page-heading"><div className="eyebrow">Coach mode</div><h1>{t.home.coachTitle}</h1><p>{t.home.coachDescription}</p></section><CoachPrivacyNotice /><CoachGameScreen /></div>;
}

export function ReportPage() {
  const [params] = useSearchParams();
  const id = params.get("game");
  const valid = id && /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(id);
  return <div className="page"><section className="page-heading"><h1>Разбор партии</h1><p>Выберите ход, чтобы посмотреть оценку и варианты Stockfish.</p></section>{valid ? <PostGameReview key={id} gameId={id} /> : <p>Откройте разбор из завершённой партии. <Link to="/play">К играм</Link></p>}</div>;
}

export function FriendPage() {
  return <div className="page page-friend"><FriendInviteScreen /></div>;
}

export function MatchmakingPage() {
  const { user, status, googleAvailable, googlePending, signIn } = useAuth();
  return <div className="page"><section className="page-heading"><h1>Найти соперника</h1><p>Выберите рапид или блиц. Рейтинг меняется после завершения партии.</p></section>
    {status !== "loading" && user?.kind !== "account" && googleAvailable && <button className="button button-primary" type="button" disabled={googlePending} onClick={() => void signIn()}>Войти через Google для игры на рейтинг</button>}
    {status === "loading" ? <p role="status">Проверяем аккаунт…</p> : <MatchmakingScreen key={user?.id ?? "guest"} eligible={user?.kind === "account"} userId={user?.id} />}
  </div>;
}

export function PuzzlePage() {
  const { locale } = useI18n();
  return <div className="page"><LearningNav /><section className="page-heading"><h1>{locale === "ru" ? "Шахматные задачи" : "Solve a chess puzzle"}</h1><p>{locale === "ru" ? "Найдите матующий ход. Если трудно, откройте подсказку." : "Find the mating move. Request a hint if you get stuck."}</p></section><PuzzleScreen key={locale} language={locale} /></div>;
}

export function ProgressPage() {
  const { locale } = useI18n();
  return <div className="page"><LearningNav /><section className="page-heading"><h1>{locale === "ru" ? "Результаты обучения" : "Review what you learned"}</h1></section><ProgressDashboard key={locale} language={locale} /></div>;
}

function LearningNav() {
  const { locale } = useI18n();
  return <nav className="game-actions" aria-label="Learning navigation"><Link className="button button-secondary" to="/learn">{locale === "ru" ? "Уроки" : "Lessons"}</Link><Link className="button button-secondary" to="/learn/puzzles">{locale === "ru" ? "Задачи" : "Puzzles"}</Link><Link className="button button-secondary" to="/learn/progress">{locale === "ru" ? "Прогресс" : "Progress"}</Link></nav>;
}

export function LearnPage() {
  const { t, locale } = useI18n();
  return (
    <div className="page">
      <section className="page-heading"><div className="eyebrow">{t.learn.eyebrow}</div><h1>{t.learn.title}</h1><p>{t.learn.description}</p></section>
      <LearningNav />
      <LessonCatalog key={locale} language={locale} />
    </div>
  );
}
