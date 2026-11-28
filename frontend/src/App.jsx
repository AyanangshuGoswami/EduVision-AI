
import { useEffect, useRef, useState } from "react";
import {
  BookOpen, BrainCircuit, CheckCircle2, ChevronRight, Clapperboard,
  CloudUpload, FileText, Film, GraduationCap, LayoutDashboard, LoaderCircle,
  Plus, RefreshCw, Sparkles, UploadCloud, Video, WandSparkles, X,
  Clock, Mic, Palette, PlayCircle, Download
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

  const [storyboard, setStoryboard] = useState(null);
  const [storyboardLoading, setStoryboardLoading] = useState(false);
  const [storyboardError, setStoryboardError] = useState("");

  const [audioUrl, setAudioUrl] = useState("");
  const [audioLoading, setAudioLoading] = useState(false);
  const [audioError, setAudioError] = useState("");

  const [videoUrl, setVideoUrl] = useState("");
  const [videoLoading, setVideoLoading] = useState(false);
  const [videoError, setVideoError] = useState("");

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const fileInput = useRef(null);

  // Clean up temporary audio URLs.
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  // Clean up temporary video URLs.
  useEffect(() => {
    return () => {
      if (videoUrl) URL.revokeObjectURL(videoUrl);
    };
  }, [videoUrl]);

  async function refresh() {
    setLoading(true);

    try {
      const [items, status] = await Promise.all([
        api.projects(),
        api.health()
      ]);

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
      setProjects((old) =>
        old.map((p) => p.id === id ? updated : p)
      );
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
    setStoryboard(null);
    setStoryboardError("");
    setLessonTitle(title);
    setLessonProjectId(projectId);
    setLessonTopicIndex(topicIndex);

    setAudioUrl("");
    setAudioError("");

    setVideoUrl("");
    setVideoError("");

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

  async function generateStoryboard() {
    if (!lesson?.teacher_script) {
      setStoryboardError("Please generate a lesson with teacher narration first.");
      return;
    }

    setStoryboardLoading(true);
    setStoryboardError("");
    setStoryboard(null);

    setVideoUrl("");
    setVideoError("");

    setError("");

    try {
      const result = await api.generateStoryboard(
        lessonProjectId,
        lessonTopicIndex,
        lesson
      );

      if (!result.scenes || !Array.isArray(result.scenes)) {
        throw new Error("The storyboard response does not contain a scenes list.");
      }

      setStoryboard(result);
      setNotice("Your video storyboard was generated successfully.");
    } catch (e) {
      setStoryboardError(e.message);
    } finally {
      setStoryboardLoading(false);
    }
  }

  // Generate the final MP4 video from the saved storyboard.
  async function generateVideo() {
    if (!storyboard?.scenes?.length) {
      setVideoError("Please generate a storyboard first.");
      return;
    }

    setVideoLoading(true);
    setVideoError("");
    setVideoUrl("");
    setError("");
    setNotice("");

    try {
      const videoBlob = await api.generateVideo(
        lessonProjectId,
        lessonTopicIndex
      );

      if (!videoBlob || videoBlob.size === 0) {
        throw new Error("The generated video file is empty.");
      }

      if (!videoBlob.type.startsWith("video/") &&
          videoBlob.type !== "application/octet-stream") {
        throw new Error("The server did not return a valid video file.");
      }

      const newVideoUrl = URL.createObjectURL(videoBlob);
      setVideoUrl(newVideoUrl);
      setNotice("Your educational video was generated successfully.");
    } catch (e) {
      setVideoError(e.message);
    } finally {
      setVideoLoading(false);
    }
  }

  function closeLesson() {
    setLesson(null);
    setStoryboard(null);
    setStoryboardError("");

    setAudioUrl("");
    setAudioError("");

    setVideoUrl("");
    setVideoError("");
  }

  const topicCount = projects.reduce(
    (n, p) => n + (p.topics?.length || 0), 0
  );

  const analyzedCount = projects.filter(
    (p) => p.status === "analyzed"
  ).length;

  const totalScenes = projects.reduce(
    (n, p) => n + (p.topics || []).reduce(
      (count, topic) => count + (topic.storyboard?.scenes?.length || 0), 0
    ), 0
  );

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
          <Stat
            icon={<FileText />}
            value={projects.length}
            label="PDF projects"
            hint="Uploaded documents"
          />

          <Stat
            icon={<BrainCircuit />}
            value={analyzedCount}
            label="Analyzed projects"
            hint="Ready with detected topics"
          />

          <Stat
            icon={<BookOpen />}
            value={topicCount}
            label="Topics detected"
            hint="Across all projects"
          />

          <Stat
            icon={<Video />}
            value={totalScenes}
            label="Storyboard scenes"
            hint="Planned video scenes"
          />
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
              <Step n="04" title="Build storyboards" text="Plan animated scenes for each topic." last />
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
                  <div className="alert error">{audioError}</div>
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

            <div className="storyboard-generator">
              <div className="eyebrow">
                <Clapperboard /> VIDEO CREATION
              </div>

              <h3>Turn this lesson into a video storyboard</h3>

              <p>
                Let your AI video director divide the lesson into visual
                scenes with narration, cartoon descriptions and animation ideas.
              </p>

              <button
                className="primary"
                onClick={generateStoryboard}
                disabled={storyboardLoading || !lesson.teacher_script}
              >
                {storyboardLoading ? (
                  <LoaderCircle className="spin" />
                ) : (
                  <WandSparkles />
                )}

                {storyboardLoading
                  ? "Creating your storyboard..."
                  : storyboard
                    ? "Regenerate storyboard"
                    : "Generate video storyboard"}
              </button>

              {storyboardError && (
                <div className="alert error">
                  {storyboardError}
                </div>
              )}
            </div>

            {storyboard && (
              <div className="storyboard-panel" id="videos">
                <div className="storyboard-heading">
                  <div className="eyebrow">
                    <Film /> YOUR VIDEO STORYBOARD
                  </div>

                  <h2>{storyboard.topic_title || lesson.topic_title}</h2>

                  <p>
                    {storyboard.scenes.length} scenes planned for your
                    educational video.
                  </p>
                </div>

                {storyboard.video_style && (
                  <div className="video-style">
                    <Palette />
                    <div>
                      <b>Visual style</b>
                      <p>{storyboard.video_style}</p>
                    </div>
                  </div>
                )}

                {/* Final video generation and playback */}
                <div className="video-generator">
                  <h3>Bring your storyboard to life</h3>

                  <p>
                    Generate your animated educational video with AI teacher narration.
                    This may take a few minutes.
                  </p>

                  <button
                    className="primary"
                    onClick={generateVideo}
                    disabled={videoLoading}
                  >
                    {videoLoading ? (
                      <LoaderCircle className="spin" />
                    ) : (
                      <Video />
                    )}

                    {videoLoading
                      ? "Generating your video..."
                      : videoUrl
                        ? "Generate video again"
                        : "Generate final video"}
                  </button>

                  {videoLoading && (
                    <div className="empty">
                      <LoaderCircle className="spin" />
                      <p>
                        Your AI video director is rendering the scenes and
                        generating the teacher narration. Please keep this page open.
                      </p>
                    </div>
                  )}

                  {videoError && (
                    <div className="alert error">
                      {videoError}
                    </div>
                  )}

                  {videoUrl && (
                    <div className="generated-video">
                      <h3>Your educational video is ready!</h3>

                      <video
                        controls
                        playsInline
                        preload="metadata"
                        src={videoUrl}
                        style={{
                          width: "100%",
                          maxWidth: "900px",
                          borderRadius: "12px",
                          background: "#000",
                          marginTop: "12px"
                        }}
                      >
                        Your browser does not support video playback.
                      </video>

                      <div style={{ marginTop: "16px" }}>
                        <a
                          className="secondary"
                          href={videoUrl}
                          download={`eduvision-${lessonTitle.replace(/[^a-z0-9]/gi, "-")}.mp4`}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "8px",
                            textDecoration: "none"
                          }}
                        >
                          <Download size={18} />
                          Download MP4 video
                        </a>
                      </div>
                    </div>
                  )}
                </div>

                <div className="scene-list">
                  {storyboard.scenes.map((scene, index) => (
                    <article className="scene-card" key={scene.scene_number ?? index}>
                      <div className="scene-card-header">
                        <span className="scene-number">
                          SCENE {scene.scene_number ?? index + 1}
                        </span>

                        <span className="scene-duration">
                          <Clock />
                          {scene.duration_seconds ?? "—"} seconds
                        </span>
                      </div>

                      <h3>{scene.scene_title || `Scene ${index + 1}`}</h3>

                      <div className="scene-content">
                        <div className="scene-detail">
                          <span><Mic /> TEACHER NARRATION</span>
                          <p>{scene.narration || "No narration provided."}</p>
                        </div>

                        <div className="scene-detail">
                          <span><Palette /> VISUAL DESCRIPTION</span>
                          <p>{scene.visual_description || "No visual description provided."}</p>
                        </div>

                        <div className="scene-detail">
                          <span><PlayCircle /> ANIMATION</span>
                          <p>{scene.animation || "No animation instructions provided."}</p>
                        </div>
                      </div>

                      {scene.on_screen_text?.length > 0 && (
                        <div className="scene-labels">
                          <b>On-screen text</b>

                          <div>
                            {scene.on_screen_text.map((item, i) => (
                              <span key={i}>{item}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {scene.transition && (
                        <div className="scene-transition">
                          <b>Transition:</b> {scene.transition}
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              </div>
            )}

            <button className="primary back-button" onClick={closeLesson}>
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
