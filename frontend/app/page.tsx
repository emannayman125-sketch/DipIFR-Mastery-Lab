"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import AuthScreen from "./components/AuthScreen";
import {
  api, ApiError, clearTokens, getToken, restoreSession,
  NextQuestionResponse, ExamSummary, ExamDetail, ExamQuestion, ResponseMode, ExamAnalysisResponse, OfficialResource,
} from "./lib/api";

type View = "dashboard" | "standards" | "questions" | "exams" | "practice" | "learning" | "knowledge" | "tutor";
type Standard = { code: string; title: string; topics: string[] };



const nav: Array<[View, string, string]> = [
  ["dashboard","⌂","Dashboard"],["standards","▦","IFRS Library"],["questions","☷","Question Bank"],["exams","▤","Mock Exams"],
  ["practice","⚡","Practice"],["learning","◎","My Learning"],["knowledge","⌕","Knowledge Base"],["tutor","✦","AI Tutor"]
];

export default function Home() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [view, setView] = useState<View>("dashboard");
  const [user, setUser] = useState("Student");
  const [progress, setProgress] = useState<Record<string, number>>({});
  const [standardsData, setStandardsData] = useState<import("./lib/api").StandardOut[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tutorContext, setTutorContext] = useState<string | undefined>(undefined);

  const loadProgress = async () => {
    try {
      const data = await api.getProgress();
      setProgress(data.topics);
      setLoadError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearTokens();
        setAuthed(false);
        return;
      }
      setLoadError("Could not reach the server. Your progress will refresh once it's back.");
    }
  };

  const loadStandards = async () => {
    try {
      const data = await api.getStandards();
      setStandardsData(data);
    } catch {
      // Leave standardsData as-is (usually still empty on the very first
      // failed attempt) — the IFRS Library panel just shows nothing extra
      // rather than an error banner, since this list is supplementary to
      // the rest of the page.
    }
  };

  useEffect(() => {
    const cachedName = typeof window !== "undefined" ? window.localStorage.getItem("dipifr-user") : null;
    if (cachedName) setUser(cachedName);

    // The access token lives only in memory, so on every page load/reload
    // we need to try exchanging the HttpOnly refresh cookie (if any) for a
    // fresh one before we know whether the student is actually signed in.
    // /content/standards requires auth, so it's only fetched *after* we
    // know a valid token exists — fetching it eagerly at mount (before the
    // token exists) would 401 and silently leave the IFRS Library empty
    // forever, which is exactly the bug this now avoids.
    (async () => {
      if (getToken()) {
        setAuthed(true);
        loadProgress();
        loadStandards();
        return;
      }
      const restored = await restoreSession();
      if (restored) {
        setAuthed(true);
        loadProgress();
        loadStandards();
      } else {
        setAuthed(false);
      }
    })();
  }, []);

  const overall = useMemo(() => {
    const values = Object.values(progress) as number[];
    return values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : 0;
  }, [progress]);

  const handleAuthenticated = (displayName: string) => {
    setUser(displayName);
    window.localStorage.setItem("dipifr-user", displayName);
    setAuthed(true);
    loadProgress();
    loadStandards();
  };

  const logout = async () => {
    await api.logout();
    setAuthed(false);
    setProgress({});
  };

  if (authed === null) return <main className="authShell"><p style={{ color: "#fff" }}>Loading…</p></main>;
  if (!authed) return <AuthScreen onAuthenticated={handleAuthenticated} />;

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brandMark">D</div><div><strong>DipIFR</strong><span>Mastery Lab</span></div></div>
        <div className="profile"><div className="avatar">{user[0]?.toUpperCase()}</div><div><b>{user}</b><small>Student account</small></div></div>
        <nav>{nav.map(([id,icon,label]) => <button key={id} className={view===id?"navItem active":"navItem"} onClick={()=>setView(id)}><span>{icon}</span>{label}</button>)}</nav>
        <div className="quote"><p>﴿وَقُلْ رَبِّ زِدْنِي عِلْمًا﴾</p><small>سورة طه · 114</small></div>
        <div className="founder">Founder<br/><b>Eman Ayman Elboghdady</b></div>
      </aside>

      <section className="content">
        <header className="topbar">
          <div><span className="eyebrow">DipIFR preparation workspace</span><h1>{titleFor(view)}</h1></div>
          <div className="topbarActions"><button className="ghost" onClick={logout}>Sign out</button></div>
        </header>
        {loadError && <div className="notice">{loadError}</div>}
        {view==="dashboard" && <Dashboard overall={overall} progress={progress} setView={setView}/>}
        {view==="standards" && <Standards progress={progress} setView={setView} standards={standardsData}/>}
        {view==="questions" && <QuestionBank onSubmitted={loadProgress} onAskTutor={(ctx)=>{setTutorContext(ctx); setView("tutor");}}/>}
        {view==="exams" && <MockExams onFinished={loadProgress}/>}
        {view==="practice" && <Practice onSubmitted={loadProgress} onAskTutor={(ctx)=>{setTutorContext(ctx); setView("tutor");}}/>}
        {view==="learning" && <Learning progress={progress} overall={overall} standards={standardsData}/>}
        {view==="knowledge" && <KnowledgeBase/>}
        {view==="tutor" && <Tutor initialQuestionContext={tutorContext}/>}
      </section>
    </main>
  );
}

function titleFor(view: View) {
  return ({dashboard:"Your study command center",standards:"IFRS / IAS Library",questions:"Question Bank",exams:"Mock Exam Center",practice:"Exam-style Practice",learning:"My Learning Path",knowledge:"Knowledge Base",tutor:"AI Accounting Tutor"})[view];
}

function Dashboard({overall,progress,setView}:{overall:number;progress:Record<string,number>;setView:(v:View)=>void}) {
  const entries = Object.entries(progress);
  const weakest = entries.length ? entries.sort((a,b)=>a[1]-b[1])[0] : undefined;
  return <div className="stack">
    <section className="hero"><div><span className="pill">Structured · exam-focused · persistent</span><h2>Study with a plan, practise with purpose.</h2><p>Use fixed mock exams to benchmark yourself, then use adaptive practice and your learning path to work on genuine weak areas.</p><button className="primary" onClick={()=>setView("learning")}>Continue Learning →</button></div><div className="scoreRing"><strong>{overall}%</strong><span>overall mastery</span></div></section>
    <div className="grid3"><Metric title="Overall mastery" value={`${overall}%`} note="Across tracked topics"/><Metric title="Weakest area" value={weakest?.[0] ?? "—"} note={weakest?`${weakest[1]}% mastery`:"Start a practice set"}/><Metric title="Mock exams" value="2" note="Fixed difficulty formats"/></div>
    <section className="panel"><SectionTitle title="Standards at a glance" action="View library" onClick={()=>setView("standards")}/>
      {entries.length === 0
        ? <p className="lead">No practice attempts yet. Head to Practice to start building your progress.</p>
        : <div className="progressList">{entries.map(([k,v])=><div className="progressRow" key={k}><div><b>{k}</b><small>{v}% mastery</small></div><div className="bar"><i style={{width:`${v}%`}}/></div></div>)}</div>}
    </section>
  </div>
}

function Metric({title,value,note}:{title:string;value:string;note:string}) { return <div className="metric"><small>{title}</small><strong>{value}</strong><span>{note}</span></div> }
function SectionTitle({title,action,onClick}:{title:string;action?:string;onClick?:()=>void}) { return <div className="sectionTitle"><h3>{title}</h3>{action&&<button className="link" onClick={onClick}>{action} →</button>}</div> }


// ---------------------------------------------------------------------------
// Question Bank — browse the full bank, then open any question directly in
// an Answer Workspace (write/spreadsheet answer, submit, get scored + AI
// feedback, ask the tutor about it) instead of only being able to browse.
// Reuses the same /learning/practice/submit endpoint as adaptive Practice —
// that endpoint accepts any question_id, not just the recommended one.
// ---------------------------------------------------------------------------
function QuestionBank({onSubmitted,onAskTutor}:{onSubmitted:()=>void;onAskTutor:(context:string)=>void}) {
  const [items,setItems]=useState<import('./lib/api').QuestionBankItem[]>([]);
  const [query,setQuery]=useState(''); const [integrated,setIntegrated]=useState(false);
  const [pastExamOnly,setPastExamOnly]=useState(false); const [loading,setLoading]=useState(true);
  const [active,setActive]=useState<import('./lib/api').QuestionBankItem|null>(null);
  const load=async()=>{setLoading(true); try{setItems(await api.getQuestionBank({q:query||undefined,integrated:integrated||undefined,source:pastExamOnly?"past_exam":undefined,limit:200}));}finally{setLoading(false)}};
  useEffect(()=>{load()},[integrated,pastExamOnly]);

  if (active) {
    return <QuestionAnswerWorkspace item={active} onBack={()=>setActive(null)} onSubmitted={onSubmitted} onAskTutor={onAskTutor} />;
  }

  return <div className="stack">
    <section className="hero"><div><span className="pill">QUESTION BANK</span><h2>Practise every standard. Connect the standards.</h2><p>Questions are tagged by standard, difficulty, source and integration. Cross-standard questions deliberately test the links between IFRS requirements.</p></div><div className="scoreRing"><strong>{items.length}</strong><span>loaded questions</span></div></section>
    <div className="panel"><div className="sectionTitle"><h3>Search the bank</h3><div style={{display:"flex",gap:8}}><button className={integrated?"primary":"ghost"} onClick={()=>setIntegrated(v=>!v)}>{integrated?'Cross-standard only':'Show cross-standard'}</button><button className={pastExamOnly?"primary":"ghost"} onClick={()=>setPastExamOnly(v=>!v)}>{pastExamOnly?'Real past exam only':'Show real past exam'}</button></div></div><div style={{display:'flex',gap:12,marginBottom:18}}><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')load()}} placeholder="Search IAS 36, impairment, disclosure..." style={{flex:1}}/><button className="primary" onClick={load}>Search</button></div>{loading?<p className="lead">Loading question bank…</p>:<div className="cardGrid">{items.map(q=><article className="card" key={q.id}><div className="cardTop"><span className="code">{q.standard_code}</span><span className="mini">{q.marks} marks</span></div><h3>{q.topic}</h3><p>{q.prompt}</p><div className="examMeta"><span>{q.difficulty}</span><span>{q.question_type.replace('_',' ')}</span><span>{q.integrated?'Integrated':''}</span>{q.source_round&&<span>{q.source_round}{q.question_number?` · Q${q.question_number}`:""}</span>}</div><button className="primary" style={{marginTop:12}} onClick={()=>setActive(q)}>Answer this question →</button></article>)}</div>}</div>
  </div>
}

// Answer Workspace: the question + its metadata on one side, an answer area
// matching the question type (write / spreadsheet) below it. Submitting
// scores the answer via the same grading pipeline as adaptive Practice and
// shows marking feedback, with a direct link into the AI Tutor grounded in
// this specific question.
function QuestionAnswerWorkspace({item,onBack,onSubmitted,onAskTutor}:{item:import('./lib/api').QuestionBankItem;onBack:()=>void;onSubmitted:()=>void;onAskTutor:(context:string)=>void}) {
  const [answer,setAnswer]=useState("");
  const [mode,setMode]=useState<ResponseMode>("word_processor");
  const [result,setResult]=useState<{score:number;feedback:string;aiGraded:boolean}|null>(null);
  const [error,setError]=useState<string|null>(null);
  const [saving,setSaving]=useState(false);

  const submit = async () => {
    if (!answer.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const res = await api.submitPractice(item.id, answer.trim(), mode);
      setResult({ score: res.score_percent, feedback: res.feedback, aiGraded: res.graded_by_ai });
      onSubmitted();
    } catch {
      setError("Could not save your attempt. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return <div className="stack"><div className="panel">
    <button type="button" className="ghost" onClick={onBack} style={{marginBottom:16}}>← Back to Question Bank</button>
    <span className="pill">{item.standard_code}{item.integrated && item.related_standards.length>1 ? ` (+ ${item.related_standards.filter(c=>c!==item.standard_code).join(", ")})` : ""}</span>
    <h2>{item.topic}</h2>
    <div className="examMeta"><span>{item.marks} marks</span><span>{item.difficulty}</span><span>{item.question_type.replace('_',' ')}</span>{item.source_round && <span>{item.source_round}{item.question_number?` · Q${item.question_number}`:""}</span>}</div>
    <p style={{whiteSpace:"pre-wrap"}}>{item.prompt}</p>
    <button type="button" className="link" onClick={()=>onAskTutor(`${item.prompt}\n\n(Marks: ${item.marks}, Standard(s): ${item.related_standards.join(", ")})`)}>Ask the AI Tutor about this question →</button>

    {!result && (
      <div className="examHeader" style={{marginTop:8}}>
        <span></span>
        <button type="button" className="ghost" onClick={()=>setMode(m=>m==="word_processor"?"spreadsheet":"word_processor")}>
          {mode==="word_processor" ? "Switch to Spreadsheet" : "Switch to Word Processor"}
        </button>
      </div>
    )}
    {mode === "word_processor" ? (
      <textarea value={answer} onChange={e=>setAnswer(e.target.value)} placeholder="Write your exam-style answer..." disabled={!!result} />
    ) : (
      <SpreadsheetGrid grid={textToGrid(answer)} onChange={g => setAnswer(gridToText(g))} />
    )}

    {error && <div className="inlineError">{error}</div>}
    {!result ? (
      <button className="primary" onClick={submit} disabled={saving || !answer.trim()}>{saving?"Marking…":"Submit & Mark"}</button>
    ) : (
      <>
        <div className="success">
          Score: {result.score}%. {result.feedback} {!result.aiGraded && <em>(keyword-based grading — connect an AI provider for richer feedback)</em>}
        </div>
        <button className="primary" onClick={onBack}>← Back to Question Bank</button>
      </>
    )}
  </div></div>
}

function Standards({progress,setView,standards}:{progress:Record<string,number>;setView:(v:View)=>void;standards:import("./lib/api").StandardOut[]}) {
  return <div className="stack"><section className="hero"><div><span className="pill">IFRS LIBRARY</span><h2>Complete DipIFR standards coverage.</h2><p>Every syllabus area is linked to its question bank, cross-standard practice and exam history.</p></div><div className="scoreRing"><strong>{standards.length}</strong><span>standards / areas</span></div></section><div className="cardGrid">{standards.map(s=><article className="card" key={s.code}><div className="cardTop"><span className="code">{s.code}</span><span className="mini">{progress[s.code]??s.mastery??0}%</span></div><h3>{s.title}</h3><p>{s.description}</p><div className="examMeta"><span>{s.question_count} questions</span></div><div className="actions"><button onClick={()=>setView("questions")}>Question Bank</button><button onClick={()=>setView("practice")}>Practice</button></div></article>)}</div></div>
}

// ---------------------------------------------------------------------------
// Mock exams// ---------------------------------------------------------------------------
// Mock exams: real backend-driven flow (list -> start -> answer each Q -> finish)
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Spreadsheet-style response grid — a lightweight alternative to the plain
// textarea, mirroring the spreadsheet response option in the real DipIFR
// CBE. Values are serialised into a simple text table before being sent to
// the same grading pipeline as a word-processor answer.
// ---------------------------------------------------------------------------
const SHEET_ROWS = 10;
const SHEET_COLS = 6;
const COL_LETTERS = "ABCDEF".split("");

function emptyGrid(): string[][] {
  return Array.from({ length: SHEET_ROWS }, () => Array.from({ length: SHEET_COLS }, () => ""));
}

function gridToText(grid: string[][]): string {
  const header = ["", ...COL_LETTERS].join("\t");
  const rows = grid.map((row, i) => [String(i + 1), ...row].join("\t"));
  return [header, ...rows].join("\n");
}

function textToGrid(text: string): string[][] {
  if (!text.trim()) return emptyGrid();
  const lines = text.split("\n").slice(1); // drop header row
  const grid = emptyGrid();
  lines.forEach((line, r) => {
    if (r >= SHEET_ROWS) return;
    const cells = line.split("\t").slice(1); // drop row-number column
    cells.forEach((val, c) => { if (c < SHEET_COLS) grid[r][c] = val; });
  });
  return grid;
}

function SpreadsheetGrid({ grid, onChange }: { grid: string[][]; onChange: (g: string[][]) => void }) {
  const setCell = (r: number, c: number, value: string) => {
    const next = grid.map(row => [...row]);
    next[r][c] = value;
    onChange(next);
  };
  return (
    <div className="sheetWrap">
      <table className="sheet">
        <thead><tr><th></th>{COL_LETTERS.map(l => <th key={l}>{l}</th>)}</tr></thead>
        <tbody>
          {grid.map((row, r) => (
            <tr key={r}>
              <th>{r + 1}</th>
              {row.map((val, c) => (
                <td key={c}><input value={val} onChange={e => setCell(r, c, e.target.value)} /></td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Post-exam analysis: marks by question (with marking-point rubric) and
// marks by standard, not just an overall percentage.
// ---------------------------------------------------------------------------
function ExamAnalysis({ attemptId, onBack }: { attemptId: number; onBack: () => void }) {
  const [analysis, setAnalysis] = useState<ExamAnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getExamAnalysis(attemptId).then(setAnalysis).catch(() => setError("Could not load the exam analysis."));
  }, [attemptId]);

  if (error) return <div className="panel examScreen"><div className="inlineError">{error}</div><button className="primary" onClick={onBack}>Back to exams</button></div>;
  if (!analysis) return <div className="panel examScreen"><p className="lead">Loading analysis…</p></div>;

  return <div className="stack">
    <div className="panel examScreen">
      <span className="pill">EXAM COMPLETE</span>
      <h2>Score: {analysis.score_percent}% ({analysis.earned_marks} / {analysis.total_marks} marks)</h2>
    </div>
    <div className="panel">
      <SectionTitle title="Marks by standard" />
      <div className="progressList">
        {analysis.by_standard.map(s => (
          <div className="progressRow" key={s.code}>
            <div><b>{s.code}</b><small>{s.marks_earned} / {s.marks_available} marks</small></div>
            <div className="bar"><i style={{ width: `${s.score_percent}%` }} /></div>
          </div>
        ))}
      </div>
    </div>
    <div className="panel">
      <SectionTitle title="Marks by question" />
      <div className="cardGrid">
        {analysis.by_question.map((q, i) => (
          <article className="card" key={q.question_id}>
            <div className="cardTop"><span className="code">Q{i + 1}</span><span className="mini">{q.marks_earned}/{q.marks_available}</span></div>
            <h3>{q.topic_code}{q.related_standards.length > 1 && ` (+ ${q.related_standards.filter(c => c !== q.topic_code).join(", ")})`}</h3>
            {q.source_round && <div className="sourceTag">{q.source_round}</div>}
            <p>{q.feedback}</p>
            {q.marking_points.length > 0 && (
              <details>
                <summary>Marking scheme ({q.marking_points.reduce((a, m) => a + m.marks, 0)} marks)</summary>
                <ul>
                  {q.marking_points.map((m, mi) => (
                    <li key={mi}><b>{m.criterion}</b> ({m.marks}) — {m.expected_points}</li>
                  ))}
                </ul>
              </details>
            )}
          </article>
        ))}
      </div>
    </div>
    <button className="primary" onClick={onBack}>Back to exams</button>
  </div>;
}

// ---------------------------------------------------------------------------
// Mock exams: full CBE workspace — word processor / spreadsheet response
// modes, countdown timer, question navigator with answered/flagged state,
// a review screen before final submit, and debounced autosave.
// ---------------------------------------------------------------------------
function OfficialResourcesSection() {
  const [resources,setResources]=useState<OfficialResource[]|null>(null);
  useEffect(()=>{ api.getOfficialResources().then(setResources).catch(()=>setResources([])); },[]);
  if (!resources || resources.length===0) return null;
  return <div className="panel">
    <span className="pill">OFFICIAL ACCA RESOURCES</span>
    <h2>Want the authentic source?</h2>
    <p className="lead">This platform builds its own original question bank and links out here rather than reproducing ACCA&apos;s copyrighted exam papers.</p>
    <div className="cardGrid">{resources.map(r=><article className="card" key={r.url}>
      <h3>{r.title}</h3><p>{r.description}</p>
      <a className="link" href={r.url} target="_blank" rel="noopener noreferrer">Open on accaglobal.com →</a>
    </article>)}</div>
  </div>
}

function MockExams({onFinished}:{onFinished:()=>void}) {
  const [exams,setExams]=useState<ExamSummary[]|null>(null);
  const [loadErr,setLoadErr]=useState<string|null>(null);
  const [attempt,setAttempt]=useState<{attemptId:number;exam:ExamDetail;expiresAt:string}|null>(null);
  const [index,setIndex]=useState(0);
  const [answers,setAnswers]=useState<Record<number,string>>({});
  const [modes,setModes]=useState<Record<number,ResponseMode>>({});
  const [flagged,setFlagged]=useState<Set<number>>(new Set());
  const [answered,setAnswered]=useState<Set<number>>(new Set());
  const [reviewing,setReviewing]=useState(false);
  const [saving,setSaving]=useState(false);
  const [finishedAttemptId,setFinishedAttemptId]=useState<number|null>(null);
  const [starting,setStarting]=useState<number|null>(null);
  const [secondsLeft,setSecondsLeft]=useState<number|null>(null);
  const autosaveTimer = useRef<number | null>(null);

  useEffect(()=>{ api.listExams().then(setExams).catch(()=>setLoadErr("Could not load exams from the server.")); },[]);

  const start = async (examId:number) => {
    setStarting(examId);
    try {
      const res = await api.startExam(examId);
      setAttempt({attemptId:res.attempt_id, exam: res.exam, expiresAt: res.expires_at});
      setIndex(0);
      setAnswers({});
      setModes({});
      setFlagged(new Set());
      setAnswered(new Set());
      setReviewing(false);
      setFinishedAttemptId(null);
      setSecondsLeft(Math.max(0, Math.floor((Date.parse(res.expires_at) - Date.now()) / 1000)));
    } catch {
      setLoadErr("Could not start this exam. Please try again.");
    } finally {
      setStarting(null);
    }
  };

  const finish = async (attemptId: number) => {
    try {
      await api.finishExam(attemptId);
      onFinished();
      setAttempt(null);
      setFinishedAttemptId(attemptId);
    } catch {
      setLoadErr("The exam could not be finished. Please try again.");
    }
  };

  useEffect(() => {
    if (!attempt) return;
    const tick = () => {
      const remaining = Math.max(0, Math.floor((Date.parse(attempt.expiresAt) - Date.now()) / 1000));
      setSecondsLeft(remaining);
      if (remaining === 0) finish(attempt.attemptId);
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);

  const currentQuestion: ExamQuestion | undefined = attempt?.exam.questions[index];
  const currentMode: ResponseMode = (currentQuestion && modes[currentQuestion.id]) || "word_processor";
  const currentText = (currentQuestion && answers[currentQuestion.id]) || "";

  // Debounced autosave: 2.5s after the student stops typing, save a draft
  // (no grading — see the backend /draft endpoint) so a lost connection or
  // closed tab never loses work.
  useEffect(() => {
    if (!attempt || !currentQuestion || reviewing) return;
    if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current);
    autosaveTimer.current = window.setTimeout(() => {
      if (currentText.trim()) {
        api.saveDraftAnswer(attempt.attemptId, currentQuestion.id, currentText, currentMode).catch(() => {});
      }
    }, 2500);
    return () => { if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentText, currentMode]);

  const setAnswerText = (text: string) => {
    if (!currentQuestion) return;
    setAnswers(prev => ({ ...prev, [currentQuestion.id]: text }));
  };

  const toggleMode = () => {
    if (!currentQuestion) return;
    const next: ResponseMode = currentMode === "word_processor" ? "spreadsheet" : "word_processor";
    setModes(prev => ({ ...prev, [currentQuestion.id]: next }));
  };

  const toggleFlag = () => {
    if (!currentQuestion) return;
    setFlagged(prev => {
      const next = new Set(prev);
      next.has(currentQuestion.id) ? next.delete(currentQuestion.id) : next.add(currentQuestion.id);
      return next;
    });
  };

  const saveCurrentFinal = async (): Promise<boolean> => {
    if (!attempt || !currentQuestion || !currentText.trim()) return false;
    setSaving(true);
    try {
      await api.answerExamQuestion(attempt.attemptId, currentQuestion.id, currentText.trim(), currentMode);
      setAnswered(prev => new Set(prev).add(currentQuestion.id));
      return true;
    } catch {
      setLoadErr("Could not save your answer. Please try again.");
      return false;
    } finally {
      setSaving(false);
    }
  };

  const goToIndex = async (i: number) => {
    await saveCurrentFinal();
    setIndex(i);
    setReviewing(false);
  };

  const nextOrReview = async () => {
    const ok = await saveCurrentFinal();
    if (!ok && !currentText.trim()) return;
    if (attempt && index + 1 < attempt.exam.questions.length) {
      setIndex(index + 1);
    } else {
      setReviewing(true);
    }
  };

  if (finishedAttemptId) {
    return <ExamAnalysis attemptId={finishedAttemptId} onBack={() => setFinishedAttemptId(null)} />;
  }

  if (attempt && reviewing) {
    return <div className="panel examScreen">
      <span className="pill">REVIEW BEFORE SUBMITTING</span>
      <h2>{attempt.exam.title}</h2>
      <p className="lead">Check every question is answered and revisit anything you flagged before you submit — you can&apos;t change answers afterwards.</p>
      <div className="reviewList">
        {attempt.exam.questions.map((q, i) => (
          <button key={q.id} className="reviewRow" onClick={() => goToIndex(i)}>
            <span>Q{i + 1} · {q.topic_code} · {q.marks} marks</span>
            <span className={answered.has(q.id) ? "statusPill approved" : "statusPill pending"}>
              {answered.has(q.id) ? "Answered" : "Not answered"}
            </span>
            {flagged.has(q.id) && <span className="statusPill rejected">Flagged 🚩</span>}
          </button>
        ))}
      </div>
      {loadErr && <div className="inlineError">{loadErr}</div>}
      <div className="examActions">
        <button className="ghost" onClick={() => setReviewing(false)}>← Back to questions</button>
        <button className="primary" onClick={() => finish(attempt.attemptId)} disabled={saving}>Submit exam</button>
      </div>
    </div>;
  }

  if (attempt && currentQuestion) {
    return <div className="cbeLayout">
      <aside className="cbeNav">
        <div className={secondsLeft !== null && secondsLeft < 300 ? "cbeTimer danger" : "cbeTimer"}>
          {secondsLeft === null ? "--:--" : `${String(Math.floor(secondsLeft / 60)).padStart(2,"0")}:${String(secondsLeft % 60).padStart(2,"0")}`}
        </div>
        {attempt.exam.questions.map((q,i)=>(
          <button key={q.id} className={`cbeNavItem ${i===index?"current":""} ${answered.has(q.id)?"answered":""} ${flagged.has(q.id)?"flagged":""}`} onClick={()=>goToIndex(i)}>
            Q{i+1}{flagged.has(q.id)?" 🚩":""}
          </button>
        ))}
        <button className="primary small" onClick={()=>setReviewing(true)}>Review & submit</button>
      </aside>

      <div className="panel examScreen cbe">
        <div className="examHeader">
          <span className="pill">{attempt.exam.title} · Question {index+1} of {attempt.exam.questions.length}</span>
          <button className="ghost" onClick={toggleMode}>{currentMode==="word_processor" ? "Switch to Spreadsheet" : "Switch to Word Processor"}</button>
        </div>
        <h2>{currentQuestion.topic_code}{currentQuestion.related_standards.length>1 && ` (+ ${currentQuestion.related_standards.filter(c=>c!==currentQuestion.topic_code).join(", ")})`} · {currentQuestion.marks} marks</h2>
        {currentQuestion.source_round && <div className="sourceTag">{currentQuestion.source_round}</div>}
        <p style={{whiteSpace:"pre-wrap"}}>{currentQuestion.prompt}</p>

        {currentMode === "word_processor" ? (
          <textarea value={currentText} onChange={e=>setAnswerText(e.target.value)} placeholder="Write your exam-style answer..." />
        ) : (
          <SpreadsheetGrid grid={textToGrid(currentText)} onChange={g => setAnswerText(gridToText(g))} />
        )}

        {loadErr && <div className="inlineError">{loadErr}</div>}
        <div className="examActions">
          <button className="ghost" onClick={toggleFlag}>{flagged.has(currentQuestion.id) ? "Unflag" : "Flag for review"}</button>
          <button className="primary" onClick={nextOrReview} disabled={saving || !currentText.trim()}>
            {saving ? "Saving…" : index+1 < attempt.exam.questions.length ? "Next question →" : "Go to review →"}
          </button>
        </div>
      </div>
    </div>;
  }

  return <div className="stack">
    <div className="notice">Mock exams use predetermined exam-style blueprints. They are intentionally not personalised by current mastery, and are graded automatically against a model answer with a full marking-point breakdown. The CBE workspace mirrors the real exam: word processor or spreadsheet responses, a timer, a question navigator, flagging, and a review screen before final submission.</div>
    {loadErr && <div className="inlineError">{loadErr}</div>}
    {!exams ? <p className="lead">Loading exams…</p> : (
      <div className="cardGrid">{exams.map(e=><article className="card" key={e.id}>
        <span className="code">{e.exam_type==="past_exam"?"REAL PAST ROUND":"MOCK"}</span><h3>{e.title}</h3><p>{e.description}</p>
        <div className="examMeta"><span>{e.question_count} Q</span><span>{e.duration_minutes} min</span><span>{e.exam_type.replace("_"," ")}</span></div>
        <button className="primary" onClick={()=>start(e.id)} disabled={starting===e.id}>{starting===e.id?"Starting…":"Open Mock →"}</button>
      </article>)}</div>
    )}
    <OfficialResourcesSection/>
  </div>
}

// ---------------------------------------------------------------------------
// Practice: adaptive question from the backend, real grading + persisted mastery
// ---------------------------------------------------------------------------
function Practice({onSubmitted,onAskTutor}:{onSubmitted:()=>void;onAskTutor:(context:string)=>void}) {
  const [question,setQuestion]=useState<NextQuestionResponse|null>(null);
  const [answer,setAnswer]=useState("");
  const [mode,setMode]=useState<ResponseMode>("word_processor");
  const [result,setResult]=useState<{score:number;feedback:string;aiGraded:boolean}|null>(null);
  const [error,setError]=useState<string|null>(null);
  const [loading,setLoading]=useState(true);
  const [saving,setSaving]=useState(false);

  const loadQuestion = () => {
    setLoading(true);
    setResult(null);
    setAnswer("");
    setMode("word_processor");
    api.getNextQuestion()
      .then(setQuestion)
      .catch(() => setError("Could not load a practice question. Please try again."))
      .finally(() => setLoading(false));
  };

  useEffect(loadQuestion, []);

  const submit = async () => {
    if (!question || !answer.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const res = await api.submitPractice(question.question_id, answer.trim(), mode);
      setResult({ score: res.score_percent, feedback: res.feedback, aiGraded: res.graded_by_ai });
      onSubmitted();
    } catch {
      setError("Could not save your attempt. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return <div className="stack"><div className="panel">
    <span className="pill">ADAPTIVE PRACTICE</span>
    <h2>Target a real weak area</h2>
    {loading && <p className="lead">Loading a question…</p>}
    {!loading && question && (
      <div className="question">
        <small>{question.topic_code}{question.related_standards.length>1 && ` (+ ${question.related_standards.filter(c=>c!==question.topic_code).join(", ")})`} · {question.marks} marks</small>
        {question.source_round && <div className="sourceTag">Source: {question.source==="past_exam" ? `Real ACCA past exam — ${question.source_round}${question.question_number?` · Q${question.question_number}`:""}` : question.source_round}</div>}
        <h3>{question.prompt}</h3>
        <button type="button" className="link" onClick={()=>onAskTutor(`${question.prompt}\n\n(Marks: ${question.marks}, Standard(s): ${question.related_standards.join(", ")})`)}>Ask the AI Tutor about this question →</button>
        {!result && (
          <div className="examHeader" style={{marginTop:8}}>
            <span></span>
            <button type="button" className="ghost" onClick={()=>setMode(m=>m==="word_processor"?"spreadsheet":"word_processor")}>
              {mode==="word_processor" ? "Switch to Spreadsheet" : "Switch to Word Processor"}
            </button>
          </div>
        )}
        {mode === "word_processor" ? (
          <textarea value={answer} onChange={e=>setAnswer(e.target.value)} placeholder="Write your exam-style answer..." disabled={!!result} />
        ) : (
          <SpreadsheetGrid grid={textToGrid(answer)} onChange={g => setAnswer(gridToText(g))} />
        )}
      </div>
    )}
    {error && <div className="inlineError">{error}</div>}
    {!result ? (
      <button className="primary" onClick={submit} disabled={saving || !question || !answer.trim()}>{saving?"Marking…":"Submit & Mark"}</button>
    ) : (
      <>
        <div className="success">
          Score: {result.score}%. {result.feedback} {!result.aiGraded && <em>(keyword-based grading — connect an AI provider for richer feedback)</em>}
        </div>
        <button className="primary" onClick={loadQuestion}>Next question →</button>
      </>
    )}
  </div></div>
}

function Learning({progress,overall,standards}:{progress:Record<string,number>;overall:number;standards:import("./lib/api").StandardOut[]}) {
  return <div className="stack"><section className="hero compact"><div><span className="pill">LEARNING ENGINE</span><h2>Track every standard, not just the weak ones.</h2><p>Mastery rises automatically each time you answer a question linked to a standard — from Practice, the Question Bank, or exams.</p></div><div className="scoreRing"><strong>{overall}%</strong><span>overall mastery</span></div></section>
    {standards.length === 0
      ? <p className="lead">Standards are loading…</p>
      : <div className="panel">
          <SectionTitle title="All standards" />
          <div className="progressList">
            {standards.map(s => {
              const mastery = progress[s.code] ?? s.mastery ?? 0;
              return (
                <div className="progressRow" key={s.code}>
                  <div><b>{s.code}</b><small>{s.title} · {mastery}% mastery</small></div>
                  <div className="bar"><i style={{width:`${mastery}%`}}/></div>
                </div>
              );
            })}
          </div>
        </div>
    }
  </div>
}

// Curated set of standards with full exam-focus deep-dives (rules, common
// exam angles, a worked scenario). This is intentionally a smaller, hand
// -written subset for the Knowledge Base's deep-dive view — separate from
// the full ~32-standard list shown in the IFRS Library / Question Bank,
// which comes live from the backend's Standard table instead.
const standards: Standard[] = [
  { code: "IAS 1", title: "Presentation of Financial Statements", topics: ["presentation", "materiality", "going concern"] },
  { code: "IAS 16", title: "Property, Plant and Equipment", topics: ["depreciation", "revaluation", "derecognition"] },
  { code: "IAS 23", title: "Borrowing Costs", topics: ["qualifying assets", "capitalisation", "suspension"] },
  { code: "IAS 36", title: "Impairment of Assets", topics: ["recoverable amount", "CGUs", "impairment loss"] },
  { code: "IAS 38", title: "Intangible Assets", topics: ["research", "development", "recognition"] },
  { code: "IAS 20", title: "Government Grants", topics: ["asset-related grants", "income-related grants", "deferred income"] },
  { code: "IFRS 9", title: "Financial Instruments", topics: ["classification", "measurement", "expected credit losses"] },
  { code: "IFRS 15", title: "Revenue from Contracts with Customers", topics: ["five-step model", "performance obligations", "variable consideration"] },
];

const standardDetails: Record<string, {summary:string; rules:string[]; exam:string[]; example:string}> = {
  "IAS 1": { summary:"IAS 1 establishes the overall presentation and disclosure framework for financial statements.", rules:["Assess going concern and disclose material uncertainties.","Present material items separately and avoid obscuring useful information.","Apply consistent presentation and classification unless a justified change is required."], exam:["Materiality and aggregation","Going concern","Current/non-current presentation"], example:"A covenant breach may create a current-liability issue and a going-concern disclosure question depending on the facts." },
  "IAS 16": { summary:"IAS 16 governs recognition, measurement and subsequent accounting for property, plant and equipment.", rules:["Recognise an item when future economic benefits are probable and cost can be measured reliably.","Depreciate depreciable amount systematically over useful life.","Choose the cost or revaluation model consistently for a class of assets."], exam:["Component depreciation","Revaluation surplus","Derecognition and disposal"], example:"A machine with a significant replacement component should be depreciated by component when the components have different useful lives." },
  "IAS 23": { summary:"IAS 23 requires directly attributable borrowing costs to be capitalised when they relate to a qualifying asset.", rules:["Capitalisation starts only when expenditure, borrowing costs and qualifying activities are present.","Suspend capitalisation during extended interruptions of active development.","Stop capitalisation when substantially all activities necessary to prepare the asset are complete."], exam:["Commencement and suspension","Specific vs general borrowings","Capitalisation rate calculations"], example:"Interest on a construction loan is capitalised while active construction is taking place, but prolonged abnormal stoppages require suspension." },
  "IAS 36": { summary:"IAS 36 prevents assets from being carried above their recoverable amount.", rules:["Recoverable amount is the higher of value in use and fair value less costs of disposal.","Test goodwill and indefinite-life intangibles at least annually.","Allocate CGU impairment losses to goodwill first, then other assets subject to the standard's floors."], exam:["CGUs and goodwill","Value in use","Impairment reversals"], example:"If a CGU's recoverable amount falls below carrying amount, the loss is allocated first to goodwill allocated to that CGU." },
  "IAS 38": { summary:"IAS 38 distinguishes research expenditure from development expenditure and sets recognition criteria for internally generated intangibles.", rules:["Research expenditure is expensed as incurred.","Development expenditure is capitalised only when all recognition criteria are demonstrated.","Amortise finite-life intangibles systematically over their useful lives."], exam:["Research vs development","Recognition criteria","Useful life and amortisation"], example:"A project moves from research to development only when technical feasibility, intention, resources and reliable measurement can be demonstrated." },
  "IAS 20": { summary:"IAS 20 covers accounting for government grants and disclosure of government assistance.", rules:["Recognise grants only when there is reasonable assurance of compliance and receipt.","Asset-related grants may be presented as deferred income or deducted from the asset's carrying amount.","Income-related grants are recognised systematically over the periods of the related costs."], exam:["Asset-related grants","Income-related grants","Presentation and timing"], example:"A grant for purchasing equipment can be deferred and released over the asset's useful life, or deducted from the asset's carrying amount." },
  "IFRS 9": { summary:"IFRS 9 covers classification, measurement and impairment of financial instruments.", rules:["Financial-asset classification depends on business model and contractual cash-flow characteristics.","Amortised cost requires the hold-to-collect model and SPPI cash flows.","The ECL model recognises expected rather than only incurred credit losses."], exam:["SPPI and business models","ECL staging","FVTPL/FVOCI/amortised cost"], example:"A debt instrument held both to collect cash flows and to sell may qualify for FVOCI if the contractual cash flows meet SPPI." },
  "IFRS 15": { summary:"IFRS 15 provides a five-step model for recognising revenue from contracts with customers.", rules:["Identify the contract and performance obligations.","Determine and allocate the transaction price.","Recognise revenue when or as performance obligations are satisfied."], exam:["Five-step model","Variable consideration","Over-time recognition"], example:"A construction service may be recognised over time when the customer controls the asset as it is created or the other over-time criteria are met." },
};

function KnowledgeBase() {
  const [q,setQ]=useState("");
  const [selected,setSelected]=useState("IAS 16");
  const results=standards.filter(s=>`${s.code} ${s.title} ${s.topics.join(" ")}`.toLowerCase().includes(q.toLowerCase()));
  const detail=standardDetails[selected] || standardDetails["IAS 16"];
  return <div className="stack">
    <div className="panel"><span className="pill">REFERENCE LIBRARY</span><h2>Understand the rule. Then apply it.</h2><p className="lead">Concise exam-focused notes, common traps and worked scenarios. Always verify final technical conclusions against the current official IFRS/IAS literature.</p><input className="search" value={q} onChange={e=>setQ(e.target.value)} placeholder="Search IAS 16, impairment, grants..." /></div>
    <div className="cardGrid">{results.map(s=><article className={selected===s.code?"card selectedCard":"card"} key={s.code} onClick={()=>setSelected(s.code)}><div className="cardTop"><span className="code">{s.code}</span><span className="mini">{s.topics.length} core topics</span></div><h3>{s.title}</h3><p>{s.topics.join(" · ")}</p><button className="link" onClick={()=>setSelected(s.code)}>Open standard →</button></article>)}</div>
    <section className="panel standardDetail"><div className="cardTop"><span className="code">{selected}</span><span className="pill">EXAM FOCUS</span></div><h2>{standards.find(s=>s.code===selected)?.title}</h2><p className="lead">{detail.summary}</p><div className="detailGrid"><div><h3>Key rules</h3><ul>{detail.rules.map(x=><li key={x}>{x}</li>)}</ul></div><div><h3>What to practise</h3><ul>{detail.exam.map(x=><li key={x}>{x}</li>)}</ul></div></div><div className="exampleBox"><b>Exam scenario</b><p>{detail.example}</p></div></section>
  </div>
}

// ---------------------------------------------------------------------------
// AI Tutor: real backend call, server-side API key
// ---------------------------------------------------------------------------
function Tutor({ initialQuestionContext }: { initialQuestionContext?: string } = {}) {
  const [message,setMessage]=useState("");
  const [thread,setThread]=useState<{role:"user"|"assistant";content:string}[]>([]);
  const [asking,setAsking]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const questionContext = initialQuestionContext;

  const ask = async () => {
    if (!message.trim()) return;
    setAsking(true);
    setError(null);
    const userText = message.trim();
    setMessage("");
    try {
      const res = await api.askTutor(userText, thread, questionContext);
      setThread(prev => [...prev, { role: "user", content: userText }, { role: "assistant", content: res.reply }]);
    } catch {
      setError("Could not reach the tutor. Please try again.");
    } finally {
      setAsking(false);
    }
  };

  return <div className="stack"><div className="panel">
    <span className="pill">AI TUTOR</span>
    <h2>Learn from your questions—not from shortcuts.</h2>
    <p>Ask for an explanation, compare two standards, or request feedback on an exam-style answer. Follow-up questions remember the conversation.</p>
    {questionContext && <div className="sourceTag">Talking about your current question</div>}
    {thread.length > 0 && (
      <div className="tutorThread">
        {thread.map((m,i) => (
          <div key={i} className={m.role==="user" ? "tutorMsg user" : "tutorMsg assistant"}>
            <b>{m.role==="user" ? "You" : "Tutor"}</b>
            <p>{m.content}</p>
          </div>
        ))}
      </div>
    )}
    <textarea value={message} onChange={e=>setMessage(e.target.value)} placeholder="e.g. Compare IAS 23 and IAS 16 in a construction scenario..." />
    {error && <div className="inlineError">{error}</div>}
    <button className="primary" onClick={ask} disabled={asking || !message.trim()}>{asking?"Thinking…":"Ask Tutor"}</button>
  </div></div>
}
