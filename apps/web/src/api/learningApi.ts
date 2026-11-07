export type LessonStatus = "not-started" | "started" | "completed";
export type Lesson = { id: string; title: string; summary: string; body: string; language: "ru" | "en"; status: LessonStatus; source_name: string; source_url: string; license: string; tags: string[] };

export function sanitizeLessonText(value: string) {
  return value.replace(/<[^>]*>/g, "").replace(/javascript:/gi, "").replace(/\s+/g, " ").trim();
}

export function sanitizeLesson(lesson: Lesson): Lesson {
  return { ...lesson, title: sanitizeLessonText(lesson.title), summary: sanitizeLessonText(lesson.summary), body: sanitizeLessonText(lesson.body), source_name: sanitizeLessonText(lesson.source_name), source_url: lesson.source_url.startsWith("https://") ? lesson.source_url : "", license: sanitizeLessonText(lesson.license) };
}

export class LearningApi {
  constructor(private readonly client?: ApiClient, private readonly allowDemo = false) {}
  static demo() { return new LearningApi(undefined, true); }
  async list(page = 1, pageSize = 6): Promise<{ items: Lesson[]; page: number; total_pages: number }> {
    if (this.client) return this.client.get(`/api/v1/learning/lessons?page=${page}&page_size=${pageSize}`);
    if (!this.allowDemo) throw new Error("Learning API is not configured");
    return { items: demoLessons.slice((page - 1) * pageSize, page * pageSize).map(sanitizeLesson), page, total_pages: Math.ceil(demoLessons.length / pageSize) };
  }
  async detail(id: string) {
    if (this.client) return this.client.get<Lesson>(`/api/v1/learning/lessons/${encodeURIComponent(id)}`);
    if (!this.allowDemo) throw new Error("Learning API is not configured");
    const lesson = demoLessons.find((item) => item.id === id); return lesson ? sanitizeLesson(lesson) : null;
  }
}

export const demoLessons: Lesson[] = [
  { id: "opening-center", title: "Центр в дебюте", summary: "Почему развитие и центр работают вместе.", body: "Развивайте фигуры, контролируйте центр и не делайте лишних ходов пешками.", language: "ru", status: "not-started", source_name: "MLChess original", source_url: "https://mlchess.dev/lessons/opening-center", license: "CC BY 4.0", tags: ["opening", "development"] },
  { id: "king-safety", title: "Безопасность короля", summary: "Рокировка и открытые линии.", body: "Сравнивайте безопасность короля с активностью фигур перед решением.", language: "ru", status: "not-started", source_name: "MLChess original", source_url: "https://mlchess.dev/lessons/king-safety", license: "CC BY 4.0", tags: ["opening", "strategy"] },
];
import { ApiClient } from "./client";

