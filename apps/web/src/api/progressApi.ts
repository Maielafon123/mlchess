export type SkillProgress = { skill: string; attempts: number; correct: number; hints_used: number; streak: number; due_at: string | null };
export type ProgressSnapshot = { student_id: string; skills: SkillProgress[] };

export class ProgressApi {
  async get(): Promise<ProgressSnapshot> { return { student_id: "demo-student", skills: [{ skill: "opening", attempts: 4, correct: 3, hints_used: 1, streak: 2, due_at: new Date(Date.now() + 86400000).toISOString() }, { skill: "back-rank", attempts: 2, correct: 2, hints_used: 0, streak: 2, due_at: new Date().toISOString() }] }; }
}
