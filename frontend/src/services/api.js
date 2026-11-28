
const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}/api${path}`, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || `Request failed (${response.status})`);
  }

  return data;
}

async function requestBlob(path, options = {}) {
  const response = await fetch(`${API_BASE}/api${path}`, options);

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed (${response.status})`);
  }

  return response.blob();
}

export const api = {
  health: () => request("/health"),

  projects: () => request("/projects"),

  upload: (file) => {
    const body = new FormData();
    body.append("file", file);

    return request("/projects/upload", {
      method: "POST",
      body,
    });
  },

  deleteProject: (id) =>
    request(`/projects/${id}`, {
      method: "DELETE",
    }),

  analyze: (id) =>
    request(`/projects/${id}/analyze`, {
      method: "POST",
    }),

  generateLesson: (id, topicIndex) =>
    request(`/projects/${id}/topics/${topicIndex}/lesson`, {
      method: "POST",
    }),

  generateStoryboard: (id, topicIndex, lesson) =>
    request(`/projects/${id}/topics/${topicIndex}/storyboard`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ lesson }),
    }),

  generateAudio: (id, topicIndex, text) =>
    requestBlob(`/projects/${id}/topics/${topicIndex}/audio`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ text }),
    }),

  generateVideo: (id, topicIndex) =>
    requestBlob(`/projects/${id}/topics/${topicIndex}/video`, {
      method: "POST",
    }),

  getVideo: (id, topicIndex) =>
    requestBlob(`/projects/${id}/topics/${topicIndex}/video`),
};
