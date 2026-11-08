import { ApiClient } from "./client";
import type { components } from "../../../../contracts/generated/api";

export type Lesson = components["schemas"]["LessonV1"];
export type LessonStatus = Lesson["status"];
export type Language = "ru" | "en";
export type LessonList = components["schemas"]["LessonListV1"];

export function sanitizeLessonText(value: string) {
  return value.replace(/<[^>]*>/g, "").replace(/javascript:/gi, "").replace(/\s+/g, " ").trim();
}
export function sanitizeLesson(lesson: Lesson): Lesson {
  return { ...lesson, title: sanitizeLessonText(lesson.title), summary: sanitizeLessonText(lesson.summary), body: sanitizeLessonText(lesson.body), source_name: sanitizeLessonText(lesson.source_name), source_url: lesson.source_url.startsWith("https://") ? lesson.source_url : "", license: sanitizeLessonText(lesson.license) };
}
export class LearningApi {
  constructor(private readonly client: ApiClient = new ApiClient()) {}
  async list(page = 1, pageSize = 6, language: Language = "ru", signal?: AbortSignal): Promise<LessonList> {
    const result = await this.client.get<LessonList>(`/api/v1/learning/lessons?page=${page}&page_size=${pageSize}&language=${language}`, { signal });
    return { ...result, items: result.items.map(sanitizeLesson) };
  }
  async detail(id: string, language: Language = "ru") {
    return sanitizeLesson(await this.client.get<Lesson>(`/api/v1/learning/lessons/${encodeURIComponent(id)}?language=${language}`));
  }
  async status(id: string, status: "started" | "completed", epoch: number, language: Language = "ru") {
    return sanitizeLesson(await this.client.post<Lesson>(`/api/v1/learning/lessons/${encodeURIComponent(id)}/status?language=${language}`, { schema_version: 1, learning_epoch: epoch, status }));
  }
}
