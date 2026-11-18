import { useEffect, useRef, useState } from "react";
import {
  BookOpen, BrainCircuit, CheckCircle2, ChevronRight, Clapperboard,
  CloudUpload, FileText, Film, GraduationCap, LayoutDashboard, LoaderCircle,
  Plus, RefreshCw, Sparkles, UploadCloud, Video, WandSparkles, X
} from "lucide-react";
import { api } from "./services/api";

const dateLabel = (value) => new Date(value).toLocaleDateString(undefined, {
  month: "short", day: "numeric", year: "numeric"
});

export default function App() {
  const [projects, setProjects] = useState([]);
  const [health, setHealth] = useState("checking");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState("");
  const [lesson, setLesson] = useState(null);
  const [lessonLoading, setLessonLoading] = useState("");
  const [lessonTitle, setLessonTitle] = useState("");
  const [lessonProjectId, setLessonProjectId] = useState("");
  const [lessonTopicIndex, setLessonTopicIndex] = useState(null);

  const [audioUrl, setAudioUrl] = useState("");
  const [audioLoading, setAudioLoading] = useState(false);
  const [audioError, setAudioError] = useState("");

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const fileInput = useRef(null);

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  async function refresh() {
    setLoading(true);
    try {
      const [items, status] = await Promise.all([api.projects(), api.health()]);
      setProjects(items);
      setHealth(status.status === "ok" ? "connected" : "offline");
      setError("");
    } catch (e) {
      setHealth("offline");
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function upload(event) {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) return;

    if (file.type !== "application/pdf") {
      setError("Please select a PDF file.");
      return;
    }

    setUploading(true);
    setError("");
    setNotice("");

    try {
      const created = await api.upload(file);
      setProjects((old) => [created, ...old]);
      setNotice(`Uploaded ${created.original_filename} successfully.`);
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  async function analyze(id) {
    setAnalyzing(id);
    setError("");
    setNotice("");

    try {
      const updated = await api.analyze(id);
      setProjects((old) => old.map((p) => p.id === id ? updated : p));
      setNotice("AI topic analysis completed.");
    } catch (e) {
      setError(e.message);
    } finally {
      setAnalyzing("");
    }
  }

  async function generateLesson(projectId, topicIndex, title) {
    setLessonLoading(`${projectId}-${topicIndex}`);
    setLesson(null);
    setLessonTitle(title);
    setLessonProjectId(projectId);
    setLessonTopicIndex(topicIndex);
    setAudioUrl("");
    setAudioError("");
    setError("");
    setNotice("");

    try {
      const result = await api.generateLesson(projectId, topicIndex);
      setLesson(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLessonLoading("");
    }
  }

  async function generateLessonAudio() {
    if (!lesson?.teacher_script) {
      setAudioError("Teacher narration is not available.");
      return;
    }

    setAudioLoading(true);
    setAudioError("");
    setError("");

    try {
      const audioBlob = await api.generateAudio(
        lessonProjectId,
        lessonTopicIndex,
        lesson.teacher_script
      );

      const newAudioUrl = URL.createObjectURL(audioBlob);
      setAudioUrl(newAudioUrl);
    } catch (e) {
      setAudioError(e.message);
    } finally {
      setAudioLoading(false);
    }
  }

  function closeLesson() {
    setLesson(null);
    setAudioUrl("");
    setAudioError("");
  }

  const topicCount = projects.reduce(
    (n, p) => n + (p.topics?.length || 0), 0
  );

  const analyzedCount = projects.filter(
    (p) => p.status === "analyzed"
  ).length;

  return (
    <div className="shell">
      <aside className="sidebar">
        <a className="brand" href="#">
          <span className="brand-icon"><GraduationCap /></span>
          eduvision<span className="brand-ai">.ai</span>
        </a>

        <div className="nav-caption">WORKSPACE</div>
        <a className="nav-link active" href="#dashboard">
          <LayoutDashboard />Dashboard
        </a>
        <a className="nav-link" href="#projects">
          <BookOpen />My projects
        </a>
        <a className="nav-link" href="#videos">
          <Film />Video library
        </a>

        <div className="sidebar-bottom">
          <div className="promo">
            <Sparkles />
            <b>Your AI classroom</b>
            <p>Turn study material into lessons students can watch and understand.</p>
          </div>

          <div className="profile">
            <span className="profile-avatar">E</span>
            <span>
              <b>EduVision workspace</b>
              <small>Starter environment</small>
            </span>
          </div>
        </div>
      </aside>

      <main className="main" id="dashboard">
        <header className="topbar">
          <div className="crumb">
            Workspace <ChevronRight /> <b>Dashboard</b>
          </div>

          <div className="top-actions">
            <span className={`connection ${health}`}>
              <i />API {health}
            </span>
            <button className="refresh" onClick={refresh} title="Refresh">
              <RefreshCw />
            </button>
            <span className="profile-avatar mini">E</span>
          </div>
        </header>

        <section className="welcome">
          <div>
            <div className="eyebrow">
              <Sparkles /> YOUR AI-POWERED LEARNING STUDIO
            </div>
            <h1>Make learning <em>come alive.</em></h1>
            <p>Upload a PDF and turn its topics into clear, engaging video lessons.</p>
          </div>

          <button
            className="primary"
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
          >
            {uploading ? <LoaderCircle className="spin" /> : <Plus />}
            {uploading ? "Uploading..." : "Create a lesson"}
          </button>

          <input
            ref={fileInput}
            hidden
            type="file"
            accept="application/pdf,.pdf"
            onChange={upload}
          />
        </section>

        {error && <div className="alert error">{error}</div>}
        {notice && (
          <div className="alert success">
            <CheckCircle2 />{notice}
          </div>
        )}

        <section className="stats">
          <Stat icon={<FileText />} value={projects.length} label="PDF projects" hint="Uploaded documents" />
          <Stat icon={<BrainCircuit />} value={analyzedCount} label="Analyzed projects" hint="Ready with detected topics" />
          <Stat icon={<BookOpen />} value={topicCount} label="Topics detected" hint="Across all projects" />
          <Stat icon={<Video />} value="0" label="Videos generated" hint="Rendering comes next" />
        </section>

        <section className="columns">
          <div id="projects">
            <div className="section-title">
              <div>
                <h2>Your projects</h2>
                <p>Manage PDFs and prepare them for video lessons.</p>
              </div>
              <button className="link-button" onClick={refresh}>
                Refresh <ChevronRight />
              </button>
            </div>

            {loading ? (
              <div className="empty">
                <LoaderCircle className="spin" /> Loading projects...
              </div>
            ) : projects.length === 0 ? (
              <div className="empty">
                <span className="empty-icon"><CloudUpload /></span>
                <h3>Your first lesson starts here</h3>
                <p>Upload a PDF to create a project. Then run AI analysis to discover its topics.</p>
                <button
                  className="primary"
                  onClick={() => fileInput.current?.click()}
                >
                  <UploadCloud />Upload your first PDF
                </button>
              </div>
            ) : (
              <div className="project-list">
                {projects.map((p) => (
                  <article className="project" key={p.id}>
                    <span className="pdf-icon"><FileText /></span>

                    <div className="project-details">
                      <h3>{p.title}</h3>
                      <p>
                        {p.original_filename} · {p.page_count ?? "?"} pages · {dateLabel(p.created_at)}
                      </p>

                      <div className="project-meta">
                        <span className={`pill ${p.status}`}>
                          {p.status.replaceAll("_", " ")}
                        </span>
                        {p.topics?.length > 0 && (
                          <span>{p.topics.length} topics detected</span>
                        )}
                      </div>

                      <button
                        className="secondary"
                        disabled={analyzing === p.id || p.status === "analyzed"}
                        onClick={() => analyze(p.id)}
                      >
                        {analyzing === p.id ? (
                          <LoaderCircle className="spin" />
                        ) : (
                          <WandSparkles />
                        )}
                        {p.status === "analyzed" ? "Analyzed" : "Analyze PDF"}
                      </button>

                      {p.topics?.length > 0 && (
                        <div className="topic-list">
                          <h4>Topics</h4>

                          {p.topics.map((topic, index) => (
                            <div className="topic-item" key={index}>
                              <span className="topic-name">
                                {index + 1}. {topic.title}
                              </span>

                              <button
                                className="secondary"
                                disabled={lessonLoading === `${p.id}-${index}`}
                                onClick={() => generateLesson(p.id, index, topic.title)}
                              >
                                {lessonLoading === `${p.id}-${index}` ? (
                                  <LoaderCircle className="spin" />
                                ) : (
                                  <BookOpen />
                                )}
                                {lessonLoading === `${p.id}-${index}`
                                  ? "Teaching..."
                                  : "Teach me"}
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>

          <aside className="right-column">
            <div className="workflow">
              <div className="workflow-head">
                <span><Clapperboard /></span>
                <small>HOW IT WORKS</small>
              </div>

              <h3>From PDF to teacher-led video</h3>
              <p>Your workflow, from document to individual topic lessons.</p>

              <Step n="01" title="Upload PDF" text="Add your textbook or notes." />
              <Step n="02" title="Discover topics" text="AI organizes chapters and concepts." />
              <Step n="03" title="Create lessons" text="Generate scripts, slides and voice." />
              <Step n="04" title="Render videos" text="Publish a video for each topic." last />
            </div>

            <div className="tip">
              <Sparkles />
              <div>
                <b>Pro tip</b>
                <p>Start with a short, text-based PDF while testing the analysis pipeline.</p>
              </div>
            </div>
          </aside>
        </section>

        {lesson && (
          <section className="lesson-panel" id="lesson">
            <div className="lesson-header">
              <div>
                <div className="eyebrow">
                  <Sparkles /> AI TEACHER LESSON
                </div>
                <h2>{lesson.topic_title || lessonTitle}</h2>
              </div>

              <button
                className="refresh"
                onClick={closeLesson}
                title="Close lesson"
              >
                <X />
              </button>
            </div>

            {lesson.introduction && (
              <div className="lesson-section">
                <h3><GraduationCap /> Introduction</h3>
                <p>{lesson.introduction}</p>
              </div>
            )}

            {lesson.explanation && (
              <div className="lesson-section">
                <h3><BookOpen /> Explanation</h3>
                <p className="lesson-text">{lesson.explanation}</p>
              </div>
            )}

            {lesson.examples?.length > 0 && (
              <div className="lesson-section">
                <h3><Sparkles /> Examples</h3>
                <ul>
                  {lesson.examples.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {lesson.key_points?.length > 0 && (
              <div className="lesson-section">
                <h3><CheckCircle2 /> Key points</h3>
                <ul>
                  {lesson.key_points.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {lesson.teacher_script && (
              <div className="lesson-section teacher-script">
                <h3><Clapperboard /> Teacher narration</h3>

                <p className="lesson-text">{lesson.teacher_script}</p>

                <div className="speech-controls">
                  <button
                    className="primary"
                    onClick={generateLessonAudio}
                    disabled={audioLoading}
                  >
                    {audioLoading ? (
                      <LoaderCircle className="spin" />
                    ) : (
                      <Video />
                    )}
                    {audioLoading ? "Generating voice..." : "Generate teacher voice"}
                  </button>
                </div>

                {audioError && (
                  <div className="alert error">
                    {audioError}
                  </div>
                )}

                {audioUrl && (
                  <div className="lesson-section">
                    <h3><Video /> AI teacher audio</h3>
                    <audio
                      controls
                      preload="metadata"
                      src={audioUrl}
                      style={{ width: "100%" }}
                    >
                      Your browser does not support audio playback.
                    </audio>
                  </div>
                )}
              </div>
            )}

            {lesson.recap && (
              <div className="lesson-section">
                <h3><RefreshCw /> Recap</h3>
                <p>{lesson.recap}</p>
              </div>
            )}

            {lesson.quiz?.length > 0 && (
              <div className="lesson-section quiz-section">
                <h3><BrainCircuit /> Quick quiz</h3>

                {lesson.quiz.map((q, i) => (
                  <div className="quiz-item" key={i}>
                    <b>{i + 1}. {q.question}</b>
                    <details>
                      <summary>Reveal answer</summary>
                      <p>{q.answer}</p>
                    </details>
                  </div>
                ))}
              </div>
            )}

            <button
              className="primary"
              onClick={closeLesson}
            >
              <ChevronRight /> Back to projects
            </button>
          </section>
        )}

        {lessonLoading && (
          <div className="lesson-loading">
            <LoaderCircle className="spin" />
            <div>
              <h3>Your AI teacher is preparing the lesson...</h3>
              <p>Gemini is building your explanation, examples, recap and quiz.</p>
            </div>
          </div>
        )}

        <footer>
          EduVision AI <span>·</span> Building a smarter way to learn.
        </footer>
      </main>
    </div>
  );
}

function Stat({ icon, value, label, hint }) {
  return (
    <article className="stat">
      <span>{icon}</span>
      <strong>{value}</strong>
      <b>{label}</b>
      <small>{hint}</small>
    </article>
  );
}

function Step({ n, title, text, last }) {
  return (
    <div className={`step ${last ? "last" : ""}`}>
      <span>{n}</span>
      <div>
        <b>{title}</b>
        <p>{text}</p>
      </div>
    </div>
  );
}