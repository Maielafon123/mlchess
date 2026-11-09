import { Link, useSearchParams } from "react-router-dom";
import { lazy } from "react";
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

  return (
    <div className="page page-home">
      <section className="hero" aria-labelledby="home-title">
        <div className="eyebrow">{t.home.eyebrow}</div>
        <h1 id="home-title">{t.home.title}</h1>
        <p className="hero-description">{t.home.description}</p>
        <div className="hero-actions">
          <Link className="button button-primary" to="/play">{t.home.openPlay}</Link>
          <Link className="button button-secondary" to="/play/friend">Позвать друга</Link>
          <Link className="button button-secondary" to="/learn">{t.home.openLearn}</Link>
        </div>
      </section>
      <section className="section" aria-labelledby="modes-title">
        <div className="section-heading"><div className="eyebrow">MLChess</div><h2 id="modes-title">{t.home.modesTitle}</h2></div>
        <div className="card-grid card-grid-3">
          <SectionCard title={t.home.aiTitle}><p>{t.home.aiDescription}</p><Link className="button button-secondary" to="/play/ai">{t.home.aiTitle}</Link></SectionCard>
          <SectionCard title={t.home.coachTitle}><p>{t.home.coachDescription}</p><Link className="button button-secondary" to="/play/coach">{t.home.coachTitle}</Link></SectionCard>
          <SectionCard title={t.home.learnTitle}><p>{t.home.learnDescription}</p><Link className="button button-secondary" to="/learn">{t.home.learnTitle}</Link></SectionCard>
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
      <div className="card-grid catalog-grid">
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
