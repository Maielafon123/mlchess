export type SkillProgress = { skill: string; attempts: number; correct: number; hints_used: number; streak: number; due_at: string | null };
export type ProgressSnapshot = { student_id: string; skills: SkillProgress[] };

export class ProgressApi {
  constructor(private readonly client?: ApiClient, private readonly allowDemo = false) {}
  static demo() { return new ProgressApi(undefined, true); }
  async get(): Promise<ProgressSnapshot> { if (this.client) return this.client.get<ProgressSnapshot>("/api/v1/learning/progress"); if (!this.allowDemo) throw new Error("Progress API is not configured"); return { student_id: "demo-student", skills: [{ skill: "opening", attempts: 4, correct: 3, hints_used: 1, streak: 2, due_at: new Date(Date.now() + 86400000).toISOString() }, { skill: "back-rank", attempts: 2, correct: 2, hints_used: 0, streak: 2, due_at: new Date().toISOString() }] }; }
}
import { ApiClient } from "./client";
