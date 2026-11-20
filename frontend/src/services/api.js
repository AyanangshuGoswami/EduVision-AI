
const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}/api${path}`, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || `Request failed (${response.status})`);
  }

  return data;
}

export const api = {
  health: () => request("/health"),

  projects: () => request("/projects"),

  upload: (file) => {
    const body = new FormData();
    body.append("file", file);

    return request("/projects/upload", {
      method: "POST",
      body
    });
  },

  analyze: (id) =>
    request(`/projects/${id}/analyze`, {
      method: "POST"
    }),

  generateLesson: (id, topicIndex) =>
    request(`/projects/${id}/topics/${topicIndex}/lesson`, {
      method: "POST"
    }),

  generateStoryboard: (id, topicIndex, lesson) =>
    request(`/projects/${id}/topics/${topicIndex}/storyboard`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ lesson })
    }),

  generateAudio: async (id, topicIndex, text) => {
    const response = await fetch(
      `${API_BASE}/api/projects/${id}/topics/${topicIndex}/audio`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ text })
      }
    );

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || "Audio generation failed");
    }

    return response.blob();
  }
};
