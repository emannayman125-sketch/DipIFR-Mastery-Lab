const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// The refresh token lives only in an HttpOnly, Secure, SameSite cookie set
// by the backend (see backend/app/api/auth.py) — JavaScript never sees it,
// which is what actually protects it from XSS. The access token is kept
// here in memory only (a module-level variable), never in localStorage or
// sessionStorage, so it disappears on a full page reload/tab close; a
// reload re-derives a fresh access token from the refresh cookie via
// restoreSession() below.
let inMemoryAccessToken: string | null = null;

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  return inMemoryAccessToken;
}

function setAccessToken(accessToken: string): void {
  inMemoryAccessToken = accessToken;
}

export function clearTokens(): void {
  inMemoryAccessToken = null;
}

async function rawRequest<T>(path: string, options: RequestInit = {}, auth = false): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  if (auth) {
    const token = getToken();
    if (!token) throw new ApiError("Not authenticated", 401);
    headers["Authorization"] = `Bearer ${token}`;
  }

  // credentials: "include" is required on every call (not just auth ones)
  // so the browser attaches/receives the HttpOnly refresh cookie on
  // /auth/register, /auth/login, /auth/refresh and /auth/logout.
  const res = await fetch(`${API_URL}${path}`, { ...options, headers, credentials: "include" });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response had no JSON body; fall back to statusText
    }
    throw new ApiError(detail, res.status);
  }

  return res.status === 204 ? (undefined as T) : res.json();
}

/** Same as rawRequest, but on a 401 tries a single silent token refresh
 * (using the HttpOnly refresh cookie) and retries once before giving up —
 * so a short-lived access token expiring mid-session doesn't boot the
 * student out immediately. */
async function request<T>(path: string, options: RequestInit = {}, auth = false): Promise<T> {
  try {
    return await rawRequest<T>(path, options, auth);
  } catch (err) {
    if (auth && err instanceof ApiError && err.status === 401) {
      const refreshed = await tryRefresh();
      if (refreshed) {
        return rawRequest<T>(path, options, auth);
      }
    }
    throw err;
  }
}

async function tryRefresh(): Promise<boolean> {
  try {
    // No body needed — the refresh token travels as the HttpOnly cookie.
    const auth = await rawRequest<AuthResponse>("/auth/refresh", { method: "POST" });
    setAccessToken(auth.access_token);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

/** Call once on app startup: if a valid refresh cookie exists from a
 * previous session, this silently obtains a fresh access token without
 * requiring the student to log in again. Returns true if a session was
 * restored. */
export async function restoreSession(): Promise<boolean> {
  return tryRefresh();
}

export type AuthResponse = { access_token: string; token_type: string };
export type ProgressResponse = { user_id: number; overall: number; topics: Record<string, number> };
export type NextQuestionResponse = {
  question_id: number; topic_code: string; related_standards: string[]; prompt: string; marks: number;
  source: string; source_round: string; source_reference: string; question_number: number | null;
};
export type PracticeSubmitResponse = {
  question_id: number; topic_code: string; related_standards: string[]; score_percent: number; feedback: string;
  graded_by_ai: boolean; new_mastery: number; overall: number;
};
export type ExamSummary = { id: number; title: string; description: string; duration_minutes: number; question_count: number; exam_type:string };
export type OfficialResource = { title: string; description: string; url: string };
export type ExamQuestion = { id: number; topic_code: string; related_standards: string[]; prompt: string; marks: number; source_round:string };
export type ExamDetail = ExamSummary & { questions: ExamQuestion[] };
export type StartAttemptResponse = { attempt_id: number; exam: ExamDetail; expires_at: string };
export type SubmitAnswerResponse = { question_id: number; score_percent: number; feedback: string; graded_by_ai: boolean };
export type FinishAttemptResponse = { attempt_id: number; score_percent: number; answered_questions: number; total_questions: number };
export type ResponseMode = "word_processor" | "spreadsheet";
export type MarkingPoint = { criterion: string; marks: number; expected_points: string };
export type QuestionAnalysis = {
  question_id: number; topic_code: string; related_standards: string[]; source_round: string;
  marks_available: number; marks_earned: number; score_percent: number; feedback: string;
  marking_points: MarkingPoint[];
};
export type StandardAnalysis = { code: string; marks_available: number; marks_earned: number; score_percent: number };
export type ExamAnalysisResponse = {
  attempt_id: number; score_percent: number; total_marks: number; earned_marks: number;
  by_question: QuestionAnalysis[]; by_standard: StandardAnalysis[];
};
export type TutorAskResponse = { reply: string; ai_generated: boolean };
export type TutorMessage = { role: "user" | "assistant"; content: string };
export type StandardOut = { id:number; code:string; title:string; description:string; question_count:number; mastery:number };
export type QuestionBankItem = { id:number; standard_code:string; topic:string; question_type:string; difficulty:string; marks:number; source:string; prompt:string; integrated:boolean; related_standards:string[]; source_round:string; question_number:number|null; source_reference:string };
export type PastExamOut = { id:number; session_name:string; exam_date:string; duration_minutes:number; total_marks:number; question_count:number; available_for_simulation:boolean; source_type:string };

export const api = {
  register: async (email: string, password: string, displayName: string) => {
    const res = await rawRequest<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name: displayName }),
    });
    setAccessToken(res.access_token);
    return res;
  },

  login: async (email: string, password: string) => {
    const res = await rawRequest<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(res.access_token);
    return res;
  },

  logout: async () => {
    clearTokens();
    try {
      // Cookie travels automatically; the backend revokes it server-side
      // and clears it via Set-Cookie.
      await rawRequest("/auth/logout", { method: "POST" });
    } catch {
      // best-effort; the in-memory access token is already cleared
    }
  },

  forgotPassword: (email: string) =>
    rawRequest<{ detail: string }>("/auth/password/forgot", { method: "POST", body: JSON.stringify({ email }) }),

  resetPassword: (token: string, newPassword: string) =>
    rawRequest<{ detail: string }>("/auth/password/reset", {
      method: "POST",
      body: JSON.stringify({ token, new_password: newPassword }),
    }),

  verifyEmail: (token: string) =>
    rawRequest<{ detail: string }>("/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) }),

  resendVerification: (email: string) =>
    rawRequest<{ detail: string }>("/auth/resend-verification", { method: "POST", body: JSON.stringify({ email }) }),

  getProgress: () => request<ProgressResponse>("/learning/progress", { method: "GET" }, true),

  getNextQuestion: () => request<NextQuestionResponse>("/learning/practice/next", { method: "GET" }, true),

  submitPractice: (questionId: number, answerText: string, responseMode: ResponseMode = "word_processor") =>
    request<PracticeSubmitResponse>(
      "/learning/practice/submit",
      { method: "POST", body: JSON.stringify({ question_id: questionId, answer_text: answerText, response_mode: responseMode }) },
      true
    ),

  listExams: () => rawRequest<ExamSummary[]>("/exams", { method: "GET" }),
  getOfficialResources: () => rawRequest<OfficialResource[]>("/content/official-resources", { method: "GET" }),

  startExam: (examId: number) => request<StartAttemptResponse>(`/exams/${examId}/start`, { method: "POST" }, true),

  saveDraftAnswer: (attemptId: number, questionId: number, answerText: string, responseMode: ResponseMode) =>
    request<{ saved: boolean }>(
      `/exams/attempts/${attemptId}/draft`,
      { method: "POST", body: JSON.stringify({ question_id: questionId, answer_text: answerText, response_mode: responseMode }) },
      true
    ),

  answerExamQuestion: (attemptId: number, questionId: number, answerText: string, responseMode: ResponseMode = "word_processor") =>
    request<SubmitAnswerResponse>(
      `/exams/attempts/${attemptId}/answer`,
      { method: "POST", body: JSON.stringify({ question_id: questionId, answer_text: answerText, response_mode: responseMode }) },
      true
    ),

  finishExam: (attemptId: number) =>
    request<FinishAttemptResponse>(`/exams/attempts/${attemptId}/finish`, { method: "POST" }, true),

  getExamAnalysis: (attemptId: number) =>
    request<ExamAnalysisResponse>(`/exams/attempts/${attemptId}/analysis`, { method: "GET" }, true),

  getStandards: () => request<StandardOut[]>("/content/standards", { method: "GET" }, true),

  getQuestionBank: (params?: {standard?:string; difficulty?:string; integrated?:boolean; source?:string; questionType?:string; q?:string; limit?:number}) => {
    const search = new URLSearchParams();
    if (params?.standard) search.set('standard', params.standard);
    if (params?.difficulty) search.set('difficulty', params.difficulty);
    if (params?.integrated !== undefined) search.set('integrated', String(params.integrated));
    if (params?.source) search.set('source', params.source);
    if (params?.questionType) search.set('question_type', params.questionType);
    if (params?.q) search.set('q', params.q);
    if (params?.limit) search.set('limit', String(params.limit));
    return request<QuestionBankItem[]>(`/content/questions${search.toString() ? `?${search}` : ''}`, { method: 'GET' }, true);
  },

  getPastExams: () => request<PastExamOut[]>("/content/past-exams", { method: "GET" }, true),

  getPastExamQuestions: (sessionId:number) => request<QuestionBankItem[]>(`/content/past-exams/${sessionId}/questions`, { method: "GET" }, true),

  askTutor: (message: string, history: TutorMessage[] = [], questionContext?: string) =>
    request<TutorAskResponse>(
      "/tutor/ask",
      { method: "POST", body: JSON.stringify({ message, history, question_context: questionContext }) },
      true
    ),
};
