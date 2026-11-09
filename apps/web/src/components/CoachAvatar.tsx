export function CoachAvatar({ title, children }: { title: string; children: string }) {
  return <div className="coach-voice">
    <span className="coach-avatar" aria-hidden="true">♞</span>
    <div><strong>{title}</strong><p>{children}</p></div>
  </div>;
}
