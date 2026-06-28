const DEFAULT_API_BASE_URL = "http://127.0.0.1:8001";
const FALLBACK_API_BASE_URLS = ["http://127.0.0.1:8003"];
const API_BASE_URLS = [DEFAULT_API_BASE_URL, ...FALLBACK_API_BASE_URLS];
const API_DISCOVERY_TIMEOUT_MS = 2500;
const GENERATE_ENDPOINT = "/generate-story";
const GENERATE_VIDEO_ENDPOINT = "/generate-video";
const HISTORY_ENDPOINT = "/history";
const HISTORY_STATS_ENDPOINT = "/history/stats";
const API_DASHBOARD_ENDPOINT = "/api/dashboard";
const API_HISTORY_ENDPOINT = "/api/history";
const API_STORIES_ENDPOINT = "/api/stories";
const API_IMAGES_ENDPOINT = "/api/images";
const API_VIDEOS_ENDPOINT = "/api/videos";
const API_PROFILE_ENDPOINT = "/api/profile";
const API_SETTINGS_ENDPOINT = "/api/settings";
const AUTH_LOGIN_ENDPOINT = "/auth/login";
const AUTH_REGISTER_ENDPOINT = "/auth/register";
const AUTH_REFRESH_ENDPOINT = "/auth/refresh";
const AUTH_LOGOUT_ENDPOINT = "/auth/logout";
const AUTH_ME_ENDPOINT = "/auth/me";
const AUTH_FORGOT_PASSWORD_ENDPOINT = "/auth/forgot-password";
const MIN_STORY_LENGTH = 3;
const DEFAULT_VIDEO_DURATION_SECONDS = 30;
const MIN_VIDEO_DURATION_SECONDS = 10;
const MAX_VIDEO_DURATION_SECONDS = 120;
const IMAGE_PROGRESS_STEP_MS = 2600;
const IMAGE_LOADING_MESSAGE = "Generating images...";
const IMAGE_FAILURE_MESSAGE = "Image generation failed. Story generation completed.";
const IMAGE_DEFERRED_MESSAGE = "Story and prompts generated. Generate images one scene at a time.";
const ACCESS_TOKEN_KEY = "cinegen_access_token";
const REFRESH_TOKEN_KEY = "cinegen_refresh_token";
const REMEMBER_SESSION_KEY = "cinegen_remember_session";
const DEFAULT_THEME = "light";

const authShell = document.querySelector("#authShell");
const appShell = document.querySelector("#appShell");
const loginPage = document.querySelector("#loginPage");
const registerPage = document.querySelector("#registerPage");
const forgotPasswordPage = document.querySelector("#forgotPasswordPage");
const loginForm = document.querySelector("#loginForm");
const registerForm = document.querySelector("#registerForm");
const forgotPasswordForm = document.querySelector("#forgotPasswordForm");
const rememberMeToggle = document.querySelector("#rememberMeToggle");
const logoutButton = document.querySelector("#logoutButton");
const sidebarUsername = document.querySelector("#sidebarUsername");
const sidebarEmail = document.querySelector("#sidebarEmail");
const sidebarAvatar = document.querySelector("#sidebarAvatar");
const welcomeTitle = document.querySelector("#welcomeTitle");
const totalVideos = document.querySelector("#totalVideos");
const recentStories = document.querySelector("#recentStories");
const latestActivity = document.querySelector("#latestActivity");
const statsChart = document.querySelector("#statsChart");
const historySearchInput = document.querySelector("#historySearchInput");
const historySortSelect = document.querySelector("#historySortSelect");
const historyPagination = document.querySelector("#historyPagination");
const imageLibraryGrid = document.querySelector("#imageLibraryGrid");
const imageProviderFilter = document.querySelector("#imageProviderFilter");
const videoLibraryGrid = document.querySelector("#videoLibraryGrid");
const profileForm = document.querySelector("#profileForm");
const passwordForm = document.querySelector("#passwordForm");
const settingsForm = document.querySelector("#settingsForm");
const profileAvatar = document.querySelector("#profileAvatar");
const profileName = document.querySelector("#profileName");
const profileEmail = document.querySelector("#profileEmail");
const profileJoined = document.querySelector("#profileJoined");
const profileStories = document.querySelector("#profileStories");
const profileImages = document.querySelector("#profileImages");
const profileVideos = document.querySelector("#profileVideos");
const profileUsername = document.querySelector("#profileUsername");
const profileEmailInput = document.querySelector("#profileEmailInput");
const profilePictureInput = document.querySelector("#profilePictureInput");
const currentPasswordInput = document.querySelector("#currentPasswordInput");
const newPasswordInput = document.querySelector("#newPasswordInput");
const themeSelect = document.querySelector("#themeSelect");
const languageSelect = document.querySelector("#languageSelect");
const voiceSelect = document.querySelector("#voiceSelect");
const imageProviderSelect = document.querySelector("#imageProviderSelect");
const backgroundMusicToggle = document.querySelector("#backgroundMusicToggle");

const storyForm = document.querySelector("#storyForm");
const storyInput = document.querySelector("#storyInput");
const storyHelp = document.querySelector("#storyHelp");
const storyError = document.querySelector("#storyError");
const textOnlyToggle = document.querySelector("#textOnlyToggle");
const targetDurationInput = document.querySelector("#targetDurationInput");
const generateButton = document.querySelector("#generateButton");
const statusPanel = document.querySelector("#statusPanel");
const statusTitle = document.querySelector("#statusTitle");
const statusBadge = document.querySelector("#statusBadge");
const statusMessage = document.querySelector("#statusMessage");
const progressList = document.querySelector("#progressSteps");
const overlayProgressList = document.querySelector("#overlayProgressSteps");
let progressSteps = getProgressStepItems();
const resultsPanel = document.querySelector(".results-panel");
const resultTitle = document.querySelector("#resultTitle");
const storyPreview = document.querySelector("#storyPreview");
const sceneCount = document.querySelector("#sceneCount");
const promptCount = document.querySelector("#promptCount");
const imageCount = document.querySelector("#imageCount");
const totalStories = document.querySelector("#totalStories");
const totalScenes = document.querySelector("#totalScenes");
const totalImages = document.querySelector("#totalImages");
const downloadJsonButton = document.querySelector("#downloadJsonButton");
const downloadImagesButton = document.querySelector("#downloadImagesButton");
const downloadStoryButton = document.querySelector("#downloadStoryButton");
const downloadVideoButton = document.querySelector("#downloadVideoButton");
const refreshHistoryButton = document.querySelector("#refreshHistoryButton");
const scenesList = document.querySelector("#scenesList");
const promptsList = document.querySelector("#promptsList");
const imagesGallery = document.querySelector("#imagesGallery");
const videoPanel = document.querySelector("#videoPanel");
const videoStatusBadge = document.querySelector("#videoStatusBadge");
const historyList = document.querySelector("#historyList");
const toast = document.querySelector("#toast");
const generationOverlay = document.querySelector("#generationOverlay");
const overlayMessage = document.querySelector("#overlayMessage");

let latestResult = null;
let progressTimer = null;
let toastTimer = null;
let isStoryGenerating = false;
let isVideoGenerating = false;
let activeApiBaseUrl = DEFAULT_API_BASE_URL;
let apiBaseUrlResolved = false;
let apiBaseUrlResolution = null;
let currentUser = null;
let currentRoute = "dashboard";
let currentHistoryPage = 1;

storyInput.addEventListener("input", () => {
  validateStory({ showErrors: false });
});

storyForm.addEventListener("submit", handleStoryGeneration);
generateButton.addEventListener("click", handleStoryGeneration);

loginForm.addEventListener("submit", handleLogin);
registerForm.addEventListener("submit", handleRegister);
forgotPasswordForm.addEventListener("submit", handleForgotPassword);
logoutButton.addEventListener("click", handleLogout);
profileForm.addEventListener("submit", handleProfileUpdate);
passwordForm.addEventListener("submit", handlePasswordChange);
settingsForm.addEventListener("submit", handleSettingsUpdate);
imageProviderFilter.addEventListener("change", refreshImageLibrary);
historySortSelect.addEventListener("change", () => refreshHistory({ silent: true, page: 1 }));
historySearchInput.addEventListener("input", debounce(() => {
  refreshHistory({ silent: true, page: 1 });
}, 260));

downloadJsonButton.addEventListener("click", () => {
  if (!latestResult) {
    return;
  }

  const fileName = latestResult.file_name || "cinegen-output.json";
  downloadJson(latestResult, fileName);
  showToast("JSON output downloaded.", "success");
});

downloadImagesButton.addEventListener("click", async () => {
  if (!latestResult) {
    return;
  }

  const images = getDownloadableImages(latestResult);
  if (images.length === 0) {
    showToast("No scene images available.", "error");
    return;
  }

  downloadImagesButton.disabled = true;
  try {
    await Promise.all(images.map((image) => downloadImage(image)));
    showToast("Scene images downloaded.", "success");
  } catch {
    showToast("Image generation failed", "error");
  } finally {
    downloadImagesButton.disabled = false;
  }
});

downloadStoryButton.addEventListener("click", () => {
  if (!latestResult) {
    return;
  }

  const fileName = getTextDownloadName(latestResult.file_name);
  downloadText(buildStoryResultsText(latestResult), fileName);
  showToast("Story results downloaded.", "success");
});

downloadVideoButton.addEventListener("click", async (event) => {
  event.preventDefault();
  event.stopPropagation();

  if (!latestResult || !latestResult.video_url) {
    showToast("No generated video available.", "error");
    return;
  }

  downloadVideoButton.disabled = true;
  try {
    await downloadVideo(latestResult);
    showToast("Video downloaded.", "success");
  } catch {
    showToast("Unable to download video.", "error");
  } finally {
    downloadVideoButton.disabled = false;
  }
});

refreshHistoryButton.addEventListener("click", () => {
  refreshHistory({ silent: false, page: currentHistoryPage });
  refreshStats({ silent: true });
});

document.querySelectorAll("[data-auth-route]").forEach((button) => {
  button.addEventListener("click", () => showAuthRoute(button.dataset.authRoute));
});

document.querySelectorAll("[data-route], [data-route-button]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    const route = link.dataset.route || link.dataset.routeButton;
    navigateTo(route);
  });
});

window.addEventListener("popstate", () => {
  if (currentUser) {
    showAppRoute(routeFromPath(location.pathname), { push: false });
  } else {
    showAuthRoute(location.pathname, { push: false });
  }
});

initializeApp();

async function initializeApp() {
  applyTheme(DEFAULT_THEME);
  validateStory({ showErrors: false });
  setResultsVisible(true);
  resetProgress();

  if (!getAccessToken() && !getRefreshToken()) {
    showAuthRoute(isAuthPath(location.pathname) ? location.pathname : "/login", {
      push: false,
    });
    return;
  }

  try {
    await loadCurrentUser();
    showAuthenticatedApp({ push: false });
  } catch {
    clearTokens();
    showAuthRoute("/login", { push: false });
  }
}

async function handleLogin(event) {
  event.preventDefault();
  const formData = new FormData(loginForm);
  const rememberMe = Boolean(rememberMeToggle.checked);

  try {
    const { response, data } = await fetchJson(AUTH_LOGIN_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: String(formData.get("email") || "").trim(),
        password: String(formData.get("password") || ""),
        remember_me: rememberMe,
      }),
    });
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    saveTokens(data, rememberMe);
    currentUser = data.user;
    showAuthenticatedApp();
    showToast("Logged in.", "success");
  } catch (error) {
    showToast(getRequestErrorMessage(error), "error");
  }
}

async function handleRegister(event) {
  event.preventDefault();
  const formData = new FormData(registerForm);

  try {
    const { response, data } = await fetchJson(AUTH_REGISTER_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: String(formData.get("username") || "").trim(),
        email: String(formData.get("email") || "").trim(),
        password: String(formData.get("password") || ""),
      }),
    });
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    clearTokens();
    registerForm.reset();
    loginForm.reset();
    const registeredEmail = String(formData.get("email") || "").trim();
    if (registeredEmail) {
      document.querySelector("#loginEmail").value = registeredEmail;
    }
    showAuthRoute("/login");
    showToast("Account created. Please login.", "success");
  } catch (error) {
    showToast(getRequestErrorMessage(error), "error");
  }
}

async function handleForgotPassword(event) {
  event.preventDefault();
  const formData = new FormData(forgotPasswordForm);

  try {
    const { response, data } = await fetchJson(AUTH_FORGOT_PASSWORD_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: String(formData.get("email") || "").trim() }),
    });
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    showToast(data.message || "Password reset request received.", "success");
    showAuthRoute("/login");
  } catch (error) {
    showToast(getRequestErrorMessage(error), "error");
  }
}

async function handleLogout() {
  try {
    await fetchJson(AUTH_LOGOUT_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: getRefreshToken() }),
    });
  } catch {
    // Local logout still succeeds if the network is unavailable.
  }
  clearTokens();
  currentUser = null;
  latestResult = null;
  showAuthRoute("/login");
  showToast("Logged out.", "success");
}

async function loadCurrentUser() {
  try {
    const { response, data } = await fetchJson(AUTH_ME_ENDPOINT);
    if (!response.ok) {
      throw new Error("Session expired.");
    }
    currentUser = data;
    return;
  } catch (error) {
    if (!getRefreshToken()) {
      throw error;
    }
  }

  await refreshSession();
  const { response, data } = await fetchJson(AUTH_ME_ENDPOINT);
  if (!response.ok) {
    throw new Error("Session expired.");
  }
  currentUser = data;
}

async function refreshSession() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error("Session expired.");
  }

  const { response, data } = await fetchJson(
    AUTH_REFRESH_ENDPOINT,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    },
    { retryAuth: false }
  );
  if (!response.ok) {
    clearTokens();
    throw new Error(buildApiErrorMessage(data, response.status));
  }
  saveTokens(data, isRememberedSession());
  currentUser = data.user;
}

function showAuthenticatedApp({ push = true } = {}) {
  authShell.hidden = true;
  appShell.hidden = false;
  updateUserChrome();
  const route = isAuthPath(location.pathname) ? "dashboard" : routeFromPath(location.pathname);
  showAppRoute(route, { push });
}

function showAuthRoute(path, { push = true } = {}) {
  if (currentUser && getAccessToken()) {
    showAuthenticatedApp({ push });
    return;
  }

  applyTheme(DEFAULT_THEME);
  appShell.hidden = true;
  authShell.hidden = false;
  const normalizedPath = isAuthPath(path) ? path : "/login";
  loginPage.hidden = normalizedPath !== "/login";
  registerPage.hidden = normalizedPath !== "/register";
  forgotPasswordPage.hidden = normalizedPath !== "/forgot-password";

  if (push && location.pathname !== normalizedPath) {
    history.pushState({}, "", normalizedPath);
  }
}

function showAppRoute(route, { push = true } = {}) {
  currentRoute = route || "dashboard";
  document.querySelectorAll(".app-page").forEach((page) => {
    page.hidden = true;
  });

  const pageIdByRoute = {
    dashboard: "dashboardPage",
    generate: "generatePage",
    history: "history",
    images: "imageLibraryPage",
    videos: "videoLibraryPage",
    profile: "profilePage",
    settings: "settingsPage",
  };
  const page = document.querySelector(`#${pageIdByRoute[currentRoute] || "dashboardPage"}`);
  page.hidden = false;

  document.querySelectorAll("[data-route]").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === currentRoute);
  });

  const pathByRoute = {
    dashboard: "/dashboard",
    generate: "/generate",
    history: "/history-page",
    images: "/images",
    videos: "/videos",
    profile: "/profile",
    settings: "/settings",
  };
  const path = pathByRoute[currentRoute] || "/dashboard";
  if (push && location.pathname !== path) {
    history.pushState({}, "", path);
  }

  refreshCurrentRoute();
}

function navigateTo(route) {
  if (!currentUser) {
    showAuthRoute("/login");
    return;
  }
  showAppRoute(route);
}

function routeFromPath(path) {
  const routes = {
    "/dashboard": "dashboard",
    "/generate": "generate",
    "/history-page": "history",
    "/images": "images",
    "/videos": "videos",
    "/profile": "profile",
    "/settings": "settings",
  };
  return routes[path] || "dashboard";
}

function isAuthPath(path) {
  return ["/login", "/register", "/forgot-password"].includes(path);
}

function refreshCurrentRoute() {
  if (currentRoute === "dashboard") {
    refreshDashboard();
  } else if (currentRoute === "history") {
    refreshHistory({ silent: true, page: currentHistoryPage });
  } else if (currentRoute === "images") {
    refreshImageLibrary();
  } else if (currentRoute === "videos") {
    refreshVideoLibrary();
  } else if (currentRoute === "profile") {
    refreshProfile();
  } else if (currentRoute === "settings") {
    refreshSettings();
  }
}

function updateUserChrome() {
  const username = currentUser?.username || "Creator";
  const email = currentUser?.email || "";
  sidebarUsername.textContent = username;
  sidebarEmail.textContent = email;
  sidebarAvatar.textContent = username.charAt(0).toUpperCase() || "C";
  welcomeTitle.textContent = `Welcome, ${username}`;
}

async function fetchJson(url, options = {}, authOptions = {}) {
  if (!isAbsoluteUrl(url)) {
    await ensureApiBaseUrl();
  }

  const retryAuth = authOptions.retryAuth !== false;
  const candidateBaseUrls = getApiBaseUrlCandidates(url);
  let lastError = null;

  for (const baseUrl of candidateBaseUrls) {
    try {
      const requestOptions = buildFetchOptions(url, options);
      const response = await fetch(buildApiUrl(url, baseUrl), requestOptions);
      if (baseUrl) {
        activeApiBaseUrl = baseUrl;
      }
      const data = await readJsonResponse(response);
      if (
        response.status === 401 &&
        retryAuth &&
        getRefreshToken() &&
        !url.startsWith("/auth/")
      ) {
        await refreshSession();
        return fetchJson(url, options, { retryAuth: false });
      }
      return { response, data };
    } catch (error) {
      lastError = error;
      if (!isBackendConnectionError(error) || isAbsoluteUrl(url)) {
        throw error;
      }
    }
  }

  throw lastError || new TypeError("Unable to reach backend");
}

function buildFetchOptions(url, options) {
  const headers = new Headers(options.headers || {});
  const token = getAccessToken();
  if (token && shouldAttachAuth(url)) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return { ...options, headers };
}

function shouldAttachAuth(url) {
  return !url.startsWith("/auth/login") &&
    !url.startsWith("/auth/register") &&
    !url.startsWith("/auth/forgot-password") &&
    url !== "/";
}

async function ensureApiBaseUrl() {
  if (apiBaseUrlResolved) {
    return;
  }

  if (!apiBaseUrlResolution) {
    apiBaseUrlResolution = resolveApiBaseUrl().finally(() => {
      apiBaseUrlResolution = null;
    });
  }

  await apiBaseUrlResolution;
}

async function resolveApiBaseUrl() {
  let lastError = null;

  for (const baseUrl of getApiBaseUrlCandidates("/")) {
    try {
      const response = await fetchWithTimeout(
        buildApiUrl("/", baseUrl),
        {},
        API_DISCOVERY_TIMEOUT_MS
      );
      if (response.ok) {
        activeApiBaseUrl = baseUrl;
        apiBaseUrlResolved = true;
        return;
      }
      lastError = new Error(`Backend returned HTTP ${response.status}.`);
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError || new TypeError("Unable to reach backend");
}

function getApiBaseUrlCandidates(url) {
  if (isAbsoluteUrl(url)) {
    return [null];
  }

  return [activeApiBaseUrl, ...API_BASE_URLS].filter(
    (baseUrl, index, baseUrls) => baseUrl && baseUrls.indexOf(baseUrl) === index
  );
}

function buildApiUrl(url, baseUrl) {
  if (isAbsoluteUrl(url)) {
    return url;
  }

  const normalizedUrl = url.startsWith("/") ? url : `/${url}`;
  return `${baseUrl}${normalizedUrl}`;
}

function isAbsoluteUrl(url) {
  return /^https?:\/\//i.test(url);
}

function fetchWithTimeout(url, options, timeoutMs) {
  if (!timeoutMs || typeof AbortController === "undefined") {
    return fetch(url, options);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  return fetch(url, { ...options, signal: controller.signal }).finally(() => {
    clearTimeout(timeoutId);
  });
}

function isBackendConnectionError(error) {
  return error instanceof TypeError || error?.name === "AbortError";
}

async function readJsonResponse(response) {
  const text = await response.text();
  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

function saveTokens(data, remember) {
  clearTokens();
  const store = remember ? localStorage : sessionStorage;
  store.setItem(ACCESS_TOKEN_KEY, data.access_token);
  store.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
  localStorage.setItem(REMEMBER_SESSION_KEY, remember ? "true" : "false");
}

function clearTokens() {
  [localStorage, sessionStorage].forEach((store) => {
    store.removeItem(ACCESS_TOKEN_KEY);
    store.removeItem(REFRESH_TOKEN_KEY);
  });
  localStorage.removeItem(REMEMBER_SESSION_KEY);
}

function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || sessionStorage.getItem(ACCESS_TOKEN_KEY);
}

function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY) || sessionStorage.getItem(REFRESH_TOKEN_KEY);
}

function isRememberedSession() {
  return localStorage.getItem(REMEMBER_SESSION_KEY) === "true";
}

async function handleStoryGeneration(event) {
  event?.preventDefault();
  event?.stopPropagation();

  if (isStoryGenerating) {
    return;
  }

  if (!validateStory({ showErrors: true })) {
    return;
  }

  isStoryGenerating = true;
  latestResult = null;
  setResultActionsEnabled(false);
  setLoading(true);
  setResultsProcessing(true);
  setResultsVisible(false);
  resetProgress();
  const estimatedSceneCount = estimateSceneCount(storyInput.value);
  const targetDurationSeconds = getTargetDurationSeconds();
  showGenerationOverlay("Scene Extraction");
  showStatus({
    title: "Processing",
    badge: "running",
    message: "Scene Extraction",
  });
  startProgress({
    imagesRequested: !textOnlyToggle.checked,
    imageCount: estimatedSceneCount,
    videoRequested: !textOnlyToggle.checked,
  });

  try {
    const { response, data } = await fetchJson(GENERATE_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        story: storyInput.value.trim(),
        text_only: textOnlyToggle.checked,
        defer_images: false,
        target_duration_seconds: targetDurationSeconds,
      }),
    });

    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }

    latestResult = normalizeResult(data, {
      source: "generated",
      fileName: data.file_name || "cinegen-output.json",
    });

    if (!isResultCompleteForDisplay(latestResult)) {
      throw new Error("Backend response did not include completed image results.");
    }

    updateProcessingMessage("Loading generated images...");
    await preloadResultImages(latestResult);
    if (shouldGenerateVideo(latestResult)) {
      latestResult = {
        ...latestResult,
        video_status: "rendering",
      };
      renderResult(latestResult);
      setResultsVisible(true);
      await generateVideoForLatestResult();
    }
    completeProgress();
    renderResult(latestResult);
    setResultsVisible(true);
    await Promise.all([
      refreshHistory({ silent: true, page: 1 }),
      refreshStats({ silent: true }),
      refreshDashboard(),
      refreshImageLibrary(),
      refreshVideoLibrary(),
    ]);
    showToast(getGenerationToastMessage(latestResult), getGenerationToastType(latestResult));
  } catch (error) {
    failProgress();
    setResultsProcessing(false);
    setResultsVisible(true);
    const message = getRequestErrorMessage(error);
    showPendingResultState();
    renderEmpty(imagesGallery, "No images generated.");
    showStatus({
      title: "Request failed",
      badge: "error",
      message,
    });
    showToast(message, "error");
  } finally {
    isStoryGenerating = false;
    setLoading(false);
    setResultsProcessing(false);
    stopProgressTimer();
    hideGenerationOverlay();
  }
}

async function refreshDashboard() {
  if (!currentUser) {
    return;
  }

  try {
    const { response, data } = await fetchJson(API_DASHBOARD_ENDPOINT);
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    currentUser = data.user;
    updateUserChrome();
    renderStats(data.stats);
    renderRecentStories(data.recent_stories || []);
    renderActivity(data.latest_activity || []);
  } catch (error) {
    showToast(getRequestErrorMessage(error), "error");
  }
}

async function refreshStats({ silent }) {
  try {
    const endpoint = currentUser ? API_DASHBOARD_ENDPOINT : HISTORY_STATS_ENDPOINT;
    const { response, data } = await fetchJson(endpoint);
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    renderStats(data.stats || data);
  } catch (error) {
    renderStats({});
    if (!silent) {
      showToast(getRequestErrorMessage(error), "error");
    }
  }
}

function renderStats(stats) {
  totalStories.textContent = stats.total_stories ?? 0;
  totalScenes.textContent = stats.total_scenes ?? 0;
  totalImages.textContent = stats.total_images ?? 0;
  if (totalVideos) {
    totalVideos.textContent = stats.total_videos ?? 0;
  }
  if (statsChart) {
    const values = [
      ["Stories", stats.total_stories || 0],
      ["Images", stats.total_images || 0],
      ["Videos", stats.total_videos || 0],
    ];
    const max = Math.max(1, ...values.map(([, value]) => value));
    statsChart.replaceChildren(
      ...values.map(([label, value]) => {
        const row = createElement("div", "chart-row");
        row.append(
          createTextElement("span", "", label),
          createElement("i", ""),
          createTextElement("strong", "", String(value))
        );
        row.querySelector("i").style.inlineSize = `${Math.max(8, (value / max) * 100)}%`;
        return row;
      })
    );
  }
}

function renderRecentStories(items) {
  renderHistoryCards(recentStories, items.slice(0, 6), { compact: true });
}

function renderActivity(items) {
  clearNode(latestActivity);
  if (!items.length) {
    renderEmpty(latestActivity, "No activity yet.");
    return;
  }
  latestActivity.classList.remove("empty-state");
  items.forEach((item) => {
    const row = createElement("button", "activity-row");
    row.type = "button";
    row.append(
      createTextElement("strong", "", item.title),
      createTextElement("span", "", `${item.images_count || 0} images`)
    );
    row.addEventListener("click", () => loadStoryDetail(item.story_id));
    latestActivity.append(row);
  });
}

async function refreshHistory({ silent, page = currentHistoryPage }) {
  currentHistoryPage = page;
  refreshHistoryButton.disabled = true;

  try {
    const search = encodeURIComponent(historySearchInput.value.trim());
    const sort = encodeURIComponent(historySortSelect.value || "newest");
    const endpoint = currentUser
      ? `${API_HISTORY_ENDPOINT}?search=${search}&sort=${sort}&page=${page}&page_size=12`
      : HISTORY_ENDPOINT;
    const { response, data } = await fetchJson(endpoint);
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }

    if (Array.isArray(data)) {
      renderHistory(data);
    } else {
      renderHistoryCards(historyList, data.items || []);
      renderPagination(data);
    }
    if (!silent) {
      showToast("History refreshed.", "success");
    }
  } catch (error) {
    renderEmpty(historyList, "Unable to load generation history.");
    if (!silent) {
      showToast(getRequestErrorMessage(error), "error");
    }
  } finally {
    refreshHistoryButton.disabled = false;
  }
}

function renderPagination(data) {
  clearNode(historyPagination);
  if (!data || data.pages <= 1) {
    return;
  }
  const previous = createElement("button", "secondary-button", "Previous");
  previous.type = "button";
  previous.disabled = data.page <= 1;
  previous.addEventListener("click", () =>
    refreshHistory({ silent: true, page: data.page - 1 })
  );
  const label = createTextElement("span", "", `Page ${data.page} of ${data.pages}`);
  const next = createElement("button", "secondary-button", "Next");
  next.type = "button";
  next.disabled = data.page >= data.pages;
  next.addEventListener("click", () =>
    refreshHistory({ silent: true, page: data.page + 1 })
  );
  historyPagination.append(previous, label, next);
}

function renderHistory(items) {
  clearNode(historyList);

  if (items.length === 0) {
    renderEmpty(historyList, "History will appear after your first generation.");
    return;
  }

  historyList.classList.remove("empty-state");
  const fragment = document.createDocumentFragment();

  items.forEach((item) => {
    const card = createElement("article", "history-card");
    const copy = createElement("div", "history-copy");
    copy.append(
      createTextElement("h3", "", formatHistoryTitle(item.file)),
      createTextElement("p", "", item.created_at)
    );

    const button = createElement("button", "secondary-button", "View Details");
    button.type = "button";
    button.addEventListener("click", () => loadHistoryDetail(item.file, item.created_at));

    card.append(copy, button);
    fragment.append(card);
  });

  historyList.append(fragment);
}

function renderHistoryCards(container, items, { compact = false } = {}) {
  clearNode(container);
  if (!items.length) {
    renderEmpty(container, compact ? "No recent stories yet." : "History will appear after your first generation.");
    return;
  }

  container.classList.remove("empty-state");
  items.forEach((item) => {
    const card = createElement("article", "history-card rich-history-card");
    if (item.thumbnail_url) {
      const thumb = createElement("div", "history-thumb");
      const image = document.createElement("img");
      image.alt = item.title;
      image.src = item.thumbnail_url;
      thumb.append(image);
      card.append(thumb);
    }
    const copy = createElement("div", "history-copy");
    copy.append(
      createTextElement("h3", "", item.title || formatHistoryTitle(item.file_name || "")),
      createTextElement("p", "", `Created ${formatDate(item.created_at)}`),
      createTextElement("p", "", `Generation Time: ${formatDate(item.generation_time)}`),
      createTextElement("p", "", `${item.images_count || 0} images`),
      createTextElement("p", "", item.video_duration ? `Video Duration: ${formatDuration(item.video_duration)}` : "Video Duration: none")
    );
    const actions = createElement("div", "history-actions");
    const open = createElement("button", "secondary-button", "Open");
    open.type = "button";
    open.addEventListener("click", () => loadStoryDetail(item.story_id));
    const download = createElement("button", "secondary-button", "Download");
    download.type = "button";
    download.addEventListener("click", async () => {
      if (item.video_url) {
        await downloadVideo({ video_url: item.video_url });
        showToast("Video downloaded.", "success");
      } else {
        const detail = await fetchStoryDetail(item.story_id);
        downloadText(buildStoryResultsText(detail), getTextDownloadName(detail.file_name));
      }
    });
    const remove = createElement("button", "secondary-button danger-button", "Delete");
    remove.type = "button";
    remove.addEventListener("click", () => deleteStory(item.story_id));
    actions.append(open, download, remove);
    card.append(copy, actions);
    container.append(card);
  });
}

async function loadHistoryDetail(fileName, createdAt) {
  setResultsVisible(false);
  showStatus({
    title: "Loading history",
    badge: "running",
    message: "Fetching saved story results.",
  });

  try {
    const { response, data } = await fetchJson(
      `${HISTORY_ENDPOINT}/${encodeURIComponent(fileName)}`
    );
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }

    latestResult = normalizeResult(data, {
      source: "history",
      fileName,
      createdAt,
    });
    await preloadResultImages(latestResult);
    renderResult(latestResult);
    navigateTo("generate");
    setResultsVisible(true);
    showToast("History loaded.", "success");
    document.querySelector(".results-panel").scrollIntoView({ behavior: "smooth" });
  } catch (error) {
    setResultsVisible(true);
    showStatus({
      title: "History unavailable",
      badge: "error",
      message: getRequestErrorMessage(error),
    });
    showToast(getRequestErrorMessage(error), "error");
  }
}

async function fetchStoryDetail(storyId) {
  const { response, data } = await fetchJson(`${API_STORIES_ENDPOINT}/${storyId}`);
  if (!response.ok) {
    throw new Error(buildApiErrorMessage(data, response.status));
  }
  return normalizeResult(data, {
    source: "history",
    fileName: data.file_name || `story_${storyId}.json`,
    createdAt: data.created_at || "",
  });
}

async function loadStoryDetail(storyId) {
  try {
    latestResult = await fetchStoryDetail(storyId);
    await preloadResultImages(latestResult);
    renderResult(latestResult);
    navigateTo("generate");
    setResultsVisible(true);
    showToast("Story loaded.", "success");
  } catch (error) {
    showToast(getRequestErrorMessage(error), "error");
  }
}

async function deleteStory(storyId) {
  try {
    const { response, data } = await fetchJson(`${API_STORIES_ENDPOINT}/${storyId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    showToast("Story deleted.", "success");
    await Promise.all([refreshHistory({ silent: true }), refreshDashboard()]);
  } catch (error) {
    showToast(getRequestErrorMessage(error), "error");
  }
}

async function refreshImageLibrary() {
  if (!currentUser) {
    return;
  }
  try {
    const provider = encodeURIComponent(imageProviderFilter.value || "");
    const endpoint = provider ? `${API_IMAGES_ENDPOINT}?provider=${provider}` : API_IMAGES_ENDPOINT;
    const { response, data } = await fetchJson(endpoint);
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    renderImageLibrary(data.items || []);
  } catch (error) {
    renderEmpty(imageLibraryGrid, "Unable to load images.");
  }
}

function renderImageLibrary(items) {
  clearNode(imageLibraryGrid);
  if (!items.length) {
    renderEmpty(imageLibraryGrid, "No images generated yet.");
    return;
  }
  imageLibraryGrid.classList.remove("empty-state");
  items.forEach((item) => {
    const card = createElement("article", "image-card");
    const frame = createElement("div", "image-frame");
    if (item.image_url || item.image_path) {
      const image = document.createElement("img");
      image.alt = item.title;
      image.src = item.image_url || item.image_path;
      frame.append(image);
    } else {
      frame.append(createPlaceholder("Image unavailable"));
    }
    const copy = createElement("div", "image-copy");
    copy.append(
      createKicker(`Scene ${item.scene_number}`),
      createTextElement("p", "image-title", item.title),
      createTextElement("p", "image-prompt", item.prompt || "Prompt unavailable."),
      createStatus(item.status)
    );
    const actions = createElement("div", "image-actions");
    const download = createElement("button", "secondary-button", "Download");
    download.type = "button";
    download.addEventListener("click", () =>
      downloadImage({ image_url: item.image_url || item.image_path })
    );
    const remove = createElement("button", "secondary-button danger-button", "Delete");
    remove.type = "button";
    remove.addEventListener("click", () => deleteImage(item.image_id));
    actions.append(download, remove);
    card.append(frame, copy, actions);
    imageLibraryGrid.append(card);
  });
}

async function deleteImage(imageId) {
  try {
    const { response, data } = await fetchJson(`${API_IMAGES_ENDPOINT}/${imageId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    showToast("Image deleted.", "success");
    await refreshImageLibrary();
  } catch (error) {
    showToast(getRequestErrorMessage(error), "error");
  }
}

async function refreshVideoLibrary() {
  if (!currentUser) {
    return;
  }
  try {
    const { response, data } = await fetchJson(API_VIDEOS_ENDPOINT);
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    renderVideoLibrary(data.items || []);
  } catch {
    renderEmpty(videoLibraryGrid, "Unable to load videos.");
  }
}

function renderVideoLibrary(items) {
  clearNode(videoLibraryGrid);
  if (!items.length) {
    renderEmpty(videoLibraryGrid, "No videos generated yet.");
    return;
  }
  videoLibraryGrid.classList.remove("empty-state");
  items.forEach((item) => {
    const card = createElement("article", "video-library-card");
    if (item.thumbnail_url) {
      const image = document.createElement("img");
      image.alt = item.title;
      image.src = item.thumbnail_url;
      card.append(image);
    }
    const copy = createElement("div", "video-library-copy");
    copy.append(
      createTextElement("h3", "", item.title),
      createTextElement("p", "", item.duration ? formatDuration(item.duration) : "Duration pending")
    );
    const actions = createElement("div", "video-actions");
    const play = createElement("a", "secondary-button button-link", "Play");
    play.href = item.video_url || item.video_path || "#";
    play.target = "_blank";
    play.rel = "noopener";
    const download = createElement("button", "secondary-button", "Download");
    download.type = "button";
    download.addEventListener("click", () =>
      downloadVideo({ video_url: item.video_url || item.video_path })
    );
    const share = createElement("button", "secondary-button", "Share");
    share.type = "button";
    share.addEventListener("click", () => shareUrl(item.video_url || item.video_path));
    const remove = createElement("button", "secondary-button danger-button", "Delete");
    remove.type = "button";
    remove.addEventListener("click", () => deleteVideo(item.video_id));
    actions.append(play, download, share, remove);
    card.append(copy, actions);
    videoLibraryGrid.append(card);
  });
}

async function deleteVideo(videoId) {
  try {
    const { response, data } = await fetchJson(`${API_VIDEOS_ENDPOINT}/${videoId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    showToast("Video deleted.", "success");
    await refreshVideoLibrary();
  } catch (error) {
    showToast(getRequestErrorMessage(error), "error");
  }
}

async function refreshProfile() {
  if (!currentUser) {
    return;
  }
  try {
    const { response, data } = await fetchJson(API_PROFILE_ENDPOINT);
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    renderProfile(data);
  } catch (error) {
    showToast(getRequestErrorMessage(error), "error");
  }
}

function renderProfile(data) {
  const user = data.user || currentUser;
  currentUser = user;
  updateUserChrome();
  const initial = user.username.charAt(0).toUpperCase() || "C";
  profileAvatar.textContent = initial;
  profileName.textContent = user.username;
  profileEmail.textContent = user.email;
  profileJoined.textContent = `Joined ${formatDate(user.created_at)}`;
  profileStories.textContent = data.stats?.total_stories || 0;
  profileImages.textContent = data.stats?.total_images || 0;
  profileVideos.textContent = data.stats?.total_videos || 0;
  profileUsername.value = user.username;
  profileEmailInput.value = user.email;
  profilePictureInput.value = user.profile_picture || "";
}

async function handleProfileUpdate(event) {
  event.preventDefault();
  try {
    const { response, data } = await fetchJson(API_PROFILE_ENDPOINT, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: profileUsername.value.trim(),
        email: profileEmailInput.value.trim(),
        profile_picture: profilePictureInput.value.trim() || null,
      }),
    });
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    renderProfile(data);
    showToast("Profile updated.", "success");
  } catch (error) {
    showToast(getRequestErrorMessage(error), "error");
  }
}

async function handlePasswordChange(event) {
  event.preventDefault();
  try {
    const { response, data } = await fetchJson(`${API_PROFILE_ENDPOINT}/change-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: currentPasswordInput.value,
        new_password: newPasswordInput.value,
      }),
    });
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    passwordForm.reset();
    showToast("Password changed.", "success");
  } catch (error) {
    showToast(getRequestErrorMessage(error), "error");
  }
}

async function refreshSettings() {
  try {
    const { response, data } = await fetchJson(API_SETTINGS_ENDPOINT);
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    const theme = normalizeTheme(data.theme);
    themeSelect.value = theme;
    languageSelect.value = data.language || "en";
    voiceSelect.value = data.voice_selection || "en-US-GuyNeural";
    imageProviderSelect.value = data.image_provider || "pollinations";
    backgroundMusicToggle.checked = Boolean(data.background_music_enabled);
    applyTheme(theme);
  } catch (error) {
    showToast(getRequestErrorMessage(error), "error");
  }
}

async function handleSettingsUpdate(event) {
  event.preventDefault();
  try {
    const { response, data } = await fetchJson(API_SETTINGS_ENDPOINT, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        theme: themeSelect.value,
        language: languageSelect.value,
        voice_selection: voiceSelect.value,
        image_provider: imageProviderSelect.value,
        background_music_enabled: backgroundMusicToggle.checked,
      }),
    });
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }
    applyTheme(data.theme);
    showToast("Settings saved.", "success");
  } catch (error) {
    showToast(getRequestErrorMessage(error), "error");
  }
}

function normalizeTheme(theme) {
  return theme === "dark" ? "dark" : DEFAULT_THEME;
}

function applyTheme(theme) {
  document.body.classList.toggle("light-mode", normalizeTheme(theme) === "light");
}

function normalizeResult(data, { source, fileName, createdAt = "" }) {
  const images = Array.isArray(data.images) ? data.images : [];
  const audio = Array.isArray(data.audio) ? data.audio : [];
  return {
    ...data,
    source,
    created_at: data.created_at || createdAt,
    file_name: data.file_name || fileName,
    scenes: Array.isArray(data.scenes) ? data.scenes : [],
    prompts: Array.isArray(data.prompts) ? data.prompts : [],
    images,
    audio,
    image_summary: data.image_summary || buildImageSummary(images),
    video_path: data.video_path || null,
    video_url: data.video_url || null,
    thumbnail_url: data.thumbnail_url || getFirstImageUrl(images),
    video_status: data.video_status || (data.video_url ? "completed" : "idle"),
    video_error: data.video_error || data.error || null,
    duration: data.duration || formatDuration(data.video_duration_seconds),
    duration_seconds: data.duration_seconds || data.video_duration_seconds || 0,
    generation_duration_seconds: data.generation_duration_seconds || null,
    target_duration_seconds:
      data.target_duration_seconds || DEFAULT_VIDEO_DURATION_SECONDS,
  };
}

function buildImageSummary(images) {
  return {
    requested: images.some((image) => image.status !== "skipped"),
    total: images.length,
    succeeded: images.filter((image) => image.status === "success").length,
    failed: images.filter((image) => image.status === "failed").length,
    skipped: images.filter((image) => image.status === "skipped").length,
  };
}

function getFirstImageUrl(images) {
  const image = (images || []).find(
    (item) => item.status === "success" && item.image_url
  );
  return image?.image_url || null;
}

function formatDuration(durationSeconds) {
  const seconds = Number(durationSeconds);
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "";
  }

  return `${Math.round(seconds)} seconds`;
}

function isResultCompleteForDisplay(data) {
  if (data.status === "text_only") {
    return true;
  }

  const expectedCount = Math.max(data.prompts.length, data.scenes.length);
  if (expectedCount === 0) {
    return true;
  }

  if (!Array.isArray(data.images) || data.images.length < expectedCount) {
    return false;
  }

  const imagesByScene = buildImagesByScene(data.images);
  const expectedScenes =
    data.prompts.length > 0
      ? data.prompts.map((prompt) => prompt.scene)
      : data.scenes.map((scene) => scene.scene);

  return expectedScenes.every((sceneNumber) => {
    const image = imagesByScene.get(sceneNumber);
    return image && image.status !== "generating";
  });
}

async function preloadResultImages(data) {
  const imageUrls = (data.images || [])
    .filter((image) => image.status === "success" && image.image_url)
    .map((image) => image.image_url);

  if (imageUrls.length === 0) {
    return;
  }

  await Promise.all(imageUrls.map((imageUrl) => preloadImage(imageUrl)));
}

function preloadImage(imageUrl) {
  return new Promise((resolve) => {
    const image = new Image();
    const timeout = window.setTimeout(() => {
      resolve();
    }, 15000);

    image.onload = () => {
      window.clearTimeout(timeout);
      resolve();
    };
    image.onerror = () => {
      window.clearTimeout(timeout);
      resolve();
    };
    image.src = imageUrl;
  });
}

function shouldGenerateVideo(data) {
  return canGenerateVideo(data);
}

async function generateVideoForLatestResult() {
  if (isVideoGenerating) {
    return;
  }

  isVideoGenerating = true;
  setProgressStep("narration");
  updateProcessingMessage("Narration");

  try {
    const { response, data } = await fetchJson(GENERATE_VIDEO_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        story: latestResult.story || storyInput.value.trim(),
        file_name: latestResult.file_name || null,
        target_duration_seconds:
          latestResult.target_duration_seconds || getTargetDurationSeconds(),
      }),
    });

    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }

    latestResult = normalizeResult(
      {
        ...latestResult,
        ...data,
        video_status: "completed",
      },
      {
        source: latestResult.source || "generated",
        fileName: data.file_name || latestResult.file_name,
        createdAt: latestResult.created_at || "",
      }
    );
    setProgressStep("encoding");
    updateProcessingMessage("Encoding MP4...");
  } catch (error) {
    const message = getRequestErrorMessage(error);
    latestResult = {
      ...latestResult,
      video_status: "failed",
      video_error: message,
    };
    renderResult(latestResult);
    showToast(`Video generation failed: ${message}`, "error");
  } finally {
    isVideoGenerating = false;
  }
}

async function generateVideoFromResult(data) {
  if (isVideoGenerating) {
    showToast("Video generation is already running.", "error");
    return;
  }

  if (!canGenerateVideo(data)) {
    showToast("Generate images before creating a video.", "error");
    return;
  }

  latestResult = normalizeResult(
    {
      ...data,
      video_status: "rendering",
      video_error: null,
    },
    {
      source: data.source || latestResult?.source || "generated",
      fileName: data.file_name || latestResult?.file_name || "cinegen-output.json",
      createdAt: data.created_at || latestResult?.created_at || "",
    }
  );

  renderResult(latestResult);
  setResultsVisible(true);
  showStatus({
    title: latestResult.file_name || "Rendering video",
    badge: "running",
    message: "Creating narration and MP4...",
  });

  await generateVideoForLatestResult();
  renderResult(latestResult);

  if (latestResult.video_url) {
    await Promise.all([
      refreshHistory({ silent: true }),
      refreshStats({ silent: true }),
      refreshDashboard(),
      refreshVideoLibrary(),
    ]);
    showToast("Video generated successfully.", "success");
  }
}

function canGenerateVideo(data) {
  if (!data || data.status === "text_only") {
    return false;
  }

  if (data.video_url || data.video_status === "rendering") {
    return false;
  }

  return getDownloadableImages(data).length > 0;
}

function buildImagesByScene(images) {
  const imagesByScene = new Map();

  images.forEach((image) => {
    const existingImage = imagesByScene.get(image.scene);
    if (!existingImage || shouldUseImageRecord(existingImage, image)) {
      imagesByScene.set(image.scene, image);
    }
  });

  return imagesByScene;
}

function shouldUseImageRecord(existingImage, nextImage) {
  const existingHasUrl = Boolean(existingImage.image_url);
  const nextHasUrl = Boolean(nextImage.image_url);

  if (existingHasUrl !== nextHasUrl) {
    return nextHasUrl;
  }

  const existingIsSuccess = existingImage.status === "success";
  const nextIsSuccess = nextImage.status === "success";

  if (existingIsSuccess !== nextIsSuccess) {
    return nextIsSuccess;
  }

  return true;
}

function renderResult(data) {
  const scenes = data.scenes;
  const prompts = data.prompts;
  const images = data.images;

  resultTitle.textContent =
    data.source === "history"
      ? `Loaded: ${formatHistoryTitle(data.file_name)}`
      : hasStoryboardFallback(data)
      ? "Fallback Output"
      : getResultTitle(data.status);
  storyPreview.textContent = data.story || "Story text unavailable.";
  sceneCount.textContent = scenes.length;
  promptCount.textContent = prompts.length;
  imageCount.textContent = getImageCountLabel(data);

  setResultActionsEnabled(true);
  downloadImagesButton.disabled = getDownloadableImages(data).length === 0;
  downloadVideoButton.disabled = !data.video_url;

  showStatus({
    title: data.file_name || "Generated",
    badge: data.status || data.source || "completed",
    message:
      data.source === "history"
        ? "Loaded from history without regenerating."
        : data.message || "Story processed successfully.",
  });

  renderScenes(scenes);
  renderPrompts(prompts);
  renderImages(data);
  renderVideo(data);
}

function showPendingResultState() {
  resultTitle.textContent = "Generating";
  storyPreview.textContent = "Results will appear when story, prompts, and images are complete.";
  sceneCount.textContent = "0";
  promptCount.textContent = "0";
  imageCount.textContent = "0";

  renderEmpty(scenesList, "Waiting for completed scene extraction.");
  renderEmpty(promptsList, "Waiting for completed prompt generation.");
  renderEmpty(imagesGallery, "Waiting for completed image generation.");
  renderEmpty(videoPanel, "Waiting for video rendering.");
  videoStatusBadge.textContent = "0:00";
}

function renderScenes(scenes) {
  clearNode(scenesList);

  if (scenes.length === 0) {
    renderEmpty(scenesList, "No scenes returned.");
    return;
  }

  scenesList.classList.remove("empty-state");
  const fragment = document.createDocumentFragment();

  scenes.forEach((scene) => {
    const card = createStackItem();
    card.append(createKicker(`Scene ${scene.scene}`), createParagraph(scene.description));
    fragment.append(card);
  });

  scenesList.append(fragment);
}

function renderPrompts(prompts) {
  clearNode(promptsList);

  if (prompts.length === 0) {
    renderEmpty(promptsList, "No prompts returned.");
    return;
  }

  promptsList.classList.remove("empty-state");
  const fragment = document.createDocumentFragment();

  prompts.forEach((prompt) => {
    const card = createStackItem();
    card.append(createKicker(`Prompt ${prompt.scene}`), createParagraph(prompt.prompt));
    fragment.append(card);
  });

  promptsList.append(fragment);
}

function renderImages(data) {
  clearNode(imagesGallery);
  imagesGallery.classList.remove("image-loading-state");
  imagesGallery.removeAttribute("aria-busy");

  const scenes = data.scenes || [];
  const prompts = data.prompts || [];
  const images = data.images || [];

  if (prompts.length === 0 && images.length === 0) {
    renderEmpty(imagesGallery, "No image records returned.");
    return;
  }

  const scenesById = new Map(scenes.map((scene) => [scene.scene, scene]));
  const promptsById = new Map(prompts.map((prompt) => [prompt.scene, prompt]));
  const imagesById = buildImagesByScene(images);
  const cardSources =
    prompts.length > 0
      ? prompts
      : images.map((image) => ({
          scene: image.scene,
          prompt: promptsById.get(image.scene)?.prompt || "",
        }));
  const fragment = document.createDocumentFragment();

  imagesGallery.classList.remove("empty-state");

  cardSources.forEach((cardSource) => {
    const scene = scenesById.get(cardSource.scene);
    const prompt = promptsById.get(cardSource.scene) || cardSource;
    const image = imagesById.get(cardSource.scene) || {
      scene: cardSource.scene,
      status: "skipped",
      image_path: null,
      image_url: null,
      provider: null,
      warning: null,
      error: null,
    };
    const imageUrl = image.image_url || "";
    const hasSuccessfulImage = image.status === "success" && Boolean(imageUrl);
    const canGenerate = false;
    const card = createElement("article", "image-card");
    const frame = createElement("div", "image-frame");

    if (image.status === "generating") {
      frame.append(createInlineLoadingState(IMAGE_LOADING_MESSAGE));
    } else if (imageUrl) {
      const link = createElement("a", "image-link");
      link.href = imageUrl;
      link.target = "_blank";
      link.rel = "noopener";

      const img = document.createElement("img");
      img.alt = scene
        ? `${getImageAltPrefix(image)} for ${scene.description}`
        : `${getImageAltPrefix(image)} for scene ${image.scene}`;
      img.loading = "lazy";
      img.onerror = () => {
        frame.replaceChildren(createPlaceholder("Image unavailable"));
      };
      img.src = image.image_url;

      link.append(img);
      frame.append(link);
    } else {
      frame.append(
        createPlaceholder(
          canGenerate ? "No image yet" : getImagePlaceholderText(image.status)
        )
      );
    }

    const meta = createElement("div", "image-meta");
    const providerBadge = createProviderBadge(image);
    meta.append(
      createKicker(`Scene ${cardSource.scene}`),
      createStatus(getDisplayImageStatus(image, canGenerate))
    );
    if (providerBadge) {
      meta.append(providerBadge);
    }

    const copy = createElement("div", "image-copy");
    copy.append(
      createTextElement(
        "p",
        "image-title",
        scene?.description || `Scene ${cardSource.scene}`
      ),
      createTextElement("p", "image-prompt", prompt?.prompt || "Prompt unavailable.")
    );

    card.append(frame, meta, copy);

    if (image.warning) {
      card.append(
        createTextElement("p", "image-warning", formatImageWarning(image.warning))
      );
    }

    if (image.error) {
      card.append(createTextElement("p", "image-error", formatImageError(image.error)));
    }

    const actions = createElement("div", "image-actions");

    if (hasSuccessfulImage) {
      const downloadButton = createElement("button", "secondary-button", "Download");
      downloadButton.type = "button";
      downloadButton.addEventListener("click", async () => {
        downloadButton.disabled = true;
        try {
          await downloadImage(image);
          showToast("Image downloaded.", "success");
        } catch {
          showToast("Image generation failed", "error");
        } finally {
          downloadButton.disabled = false;
        }
      });

      const openLink = createElement(
        "a",
        "secondary-button button-link",
        "Open in New Tab"
      );
      openLink.href = imageUrl;
      openLink.target = "_blank";
      openLink.rel = "noopener";

      actions.append(downloadButton, openLink);
    }

    if (actions.childElementCount > 0) {
      card.append(actions);
    }

    fragment.append(card);
  });

  imagesGallery.append(fragment);
}

function renderVideo(data) {
  clearNode(videoPanel);
  videoPanel.classList.remove("empty-state", "video-loading-state", "video-ready-state");
  videoPanel.removeAttribute("aria-busy");

  if (data.video_status === "rendering") {
    videoStatusBadge.textContent = "Rendering";
    videoPanel.classList.add("video-loading-state");
    videoPanel.setAttribute("aria-busy", "true");
    videoPanel.append(createInlineLoadingState("Creating cinematic video..."));
    return;
  }

  if (data.video_url) {
    videoStatusBadge.textContent = data.duration || "Ready";

    const video = document.createElement("video");
    video.className = "video-player";
    video.controls = true;
    video.preload = "metadata";
    video.src = data.video_url;
    if (data.thumbnail_url) {
      video.poster = data.thumbnail_url;
    }

    const meta = createElement("div", "video-meta");
    meta.append(
      createTextElement("p", "", `Scenes: ${data.scene_count || data.scenes.length}`),
      createTextElement("p", "", data.duration ? `Duration: ${data.duration}` : ""),
      createTextElement(
        "p",
        "",
        data.target_duration_seconds
          ? `Target: ${data.target_duration_seconds} seconds`
          : ""
      )
    );

    const actions = createElement("div", "video-actions");
    const downloadButton = createElement("button", "secondary-button", "Download MP4");
    downloadButton.type = "button";
    downloadButton.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      downloadButton.disabled = true;
      try {
        await downloadVideo(data);
        showToast("Video downloaded.", "success");
      } catch {
        showToast("Unable to download video.", "error");
      } finally {
        downloadButton.disabled = false;
      }
    });

    const openLink = createElement(
      "a",
      "secondary-button button-link",
      "Open in New Tab"
    );
    openLink.href = data.video_url;
    openLink.target = "_blank";
    openLink.rel = "noopener";

    actions.append(downloadButton, openLink);
    videoPanel.append(video, meta, actions);
    return;
  }

  if (data.video_status === "failed" || data.video_error) {
    videoStatusBadge.textContent = "Failed";
    videoPanel.classList.add("empty-state");
    videoPanel.append(
      createTextElement("p", "", data.video_error || "Video generation failed.")
    );
    if (canGenerateVideo(data)) {
      videoPanel.append(createGenerateVideoButton(data, "Try Again"));
    }
    return;
  }

  if (canGenerateVideo(data)) {
    videoStatusBadge.textContent = "Ready";
    videoPanel.classList.add("video-ready-state");
    videoPanel.append(
      createTextElement("p", "", "Images are ready for MP4 generation."),
      createGenerateVideoButton(data, "Generate MP4")
    );
    return;
  }

  videoStatusBadge.textContent = "0:00";
  renderEmpty(videoPanel, "No video generated yet.");
}

function createGenerateVideoButton(data, label) {
  const button = createElement("button", "secondary-button", label);
  button.type = "button";
  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (button.disabled || isVideoGenerating) {
      return;
    }
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    await generateVideoFromResult(data);
  });
  return button;
}

function validateStory({ showErrors }) {
  const story = storyInput.value.trim();
  let message = "";

  if (!story) {
    message = "Add a story before generating.";
  } else if (story.length < MIN_STORY_LENGTH) {
    message = `Story must be at least ${MIN_STORY_LENGTH} characters.`;
  }

  const isValid = !message;
  storyInput.classList.toggle("invalid", !isValid && showErrors);
  storyError.hidden = isValid || !showErrors;
  storyError.textContent = message;
  storyHelp.textContent = `${story.length}/${MIN_STORY_LENGTH} characters minimum`;

  if (!isValid && showErrors) {
    showStatus({
      title: "Check story",
      badge: "error",
      message,
    });
    storyInput.focus();
  }

  return isValid;
}

function getTargetDurationSeconds() {
  if (!targetDurationInput) {
    return DEFAULT_VIDEO_DURATION_SECONDS;
  }

  const parsedDuration = Number.parseInt(targetDurationInput.value, 10);
  const duration = Number.isFinite(parsedDuration)
    ? parsedDuration
    : DEFAULT_VIDEO_DURATION_SECONDS;
  const clampedDuration = Math.min(
    MAX_VIDEO_DURATION_SECONDS,
    Math.max(MIN_VIDEO_DURATION_SECONDS, duration)
  );

  targetDurationInput.value = String(clampedDuration);
  return clampedDuration;
}

function startProgress({ imagesRequested, imageCount, videoRequested = false }) {
  stopProgressTimer();

  const steps = buildProgressSteps({ imagesRequested, imageCount, videoRequested });
  let phaseIndex = 0;

  renderProgressSteps(steps);
  setProgressStep(steps[phaseIndex].key);
  updateProcessingMessage(steps[phaseIndex].label);

  progressTimer = window.setInterval(() => {
    phaseIndex = Math.min(phaseIndex + 1, steps.length - 1);
    setProgressStep(steps[phaseIndex].key);
    updateProcessingMessage(steps[phaseIndex].label);
  }, IMAGE_PROGRESS_STEP_MS);
}

function buildProgressSteps({ imagesRequested, imageCount, videoRequested = false }) {
  const totalImages = Math.max(1, Number(imageCount) || 1);
  const baseSteps = [
    { key: "scenes", label: "Scene Extraction" },
    { key: "prompts", label: "Prompt Generation" },
  ];

  if (imagesRequested) {
    baseSteps.push(
      ...Array.from({ length: totalImages }, (_, index) => ({
        key: `image-${index + 1}`,
        label: `Image Generation ${index + 1}`,
      }))
    );
  }

  if (videoRequested) {
    baseSteps.push(
      { key: "narration", label: "Narration" },
      { key: "audio", label: "Generating audio..." },
      { key: "video", label: "Video Generation" },
      { key: "encoding", label: "Encoding MP4..." }
    );
  }

  baseSteps.push({ key: "saving", label: "Saving results..." });
  return baseSteps;
}

function renderProgressSteps(steps) {
  replaceProgressList(progressList, steps);
  replaceProgressList(overlayProgressList, steps);
  progressSteps = getProgressStepItems();
}

function replaceProgressList(list, steps) {
  if (!list) {
    return;
  }

  const fragment = document.createDocumentFragment();

  steps.forEach((step) => {
    const item = createElement("li", "", step.label);
    item.dataset.step = step.key;
    fragment.append(item);
  });

  const completed = createElement("li", "", "Completed");
  completed.dataset.step = "completed";
  fragment.append(completed);

  list.replaceChildren(fragment);
}

function getProgressStepItems() {
  return Array.from(
    document.querySelectorAll("#progressSteps li, #overlayProgressSteps li")
  );
}

function setProgressStep(activeStep) {
  let reachedActive = false;

  progressSteps.forEach((step) => {
    const stepName = step.dataset.step;
    const isActive = stepName === activeStep;
    const isTerminal = stepName === "completed";

    if (isActive) {
      reachedActive = true;
    }

    step.classList.toggle("is-active", isActive);
    step.classList.toggle("is-complete", !reachedActive && !isTerminal);
  });
}

function completeProgress() {
  stopProgressTimer();
  progressSteps.forEach((step) => {
    const isCompleted = step.dataset.step === "completed";
    step.classList.toggle("is-active", isCompleted);
    step.classList.toggle("is-complete", !isCompleted);
  });
  updateProcessingMessage("Completed");
}

function failProgress() {
  stopProgressTimer();
  progressSteps.forEach((step) => {
    step.classList.remove("is-active", "is-complete");
  });
}

function resetProgress() {
  progressSteps.forEach((step) => {
    step.classList.remove("is-active", "is-complete");
  });
}

function stopProgressTimer() {
  if (progressTimer) {
    window.clearInterval(progressTimer);
    progressTimer = null;
  }
}

function updateProcessingMessage(message) {
  if (statusPanel.hidden) {
    return;
  }

  statusMessage.textContent = message;
  if (overlayMessage) {
    overlayMessage.textContent = message;
  }
}

function showStatus({ title, badge, message }) {
  statusPanel.hidden = false;
  statusTitle.textContent = title;
  statusBadge.textContent = badge.replace("_", " ");
  statusBadge.className = `status-badge ${badge}`;
  statusMessage.textContent = message;
}

function showGenerationOverlay(message) {
  if (!generationOverlay) {
    return;
  }

  generationOverlay.hidden = false;
  if (overlayMessage) {
    overlayMessage.textContent = message;
  }
}

function hideGenerationOverlay() {
  if (generationOverlay) {
    generationOverlay.hidden = true;
  }
}

function showToast(message, type) {
  if (toastTimer) {
    window.clearTimeout(toastTimer);
  }

  toast.hidden = false;
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toastTimer = window.setTimeout(() => {
    toast.hidden = true;
  }, 4200);
}

function setLoading(isLoading) {
  generateButton.disabled = isLoading;
  generateButton.classList.toggle("is-loading", isLoading);
  generateButton.setAttribute("aria-busy", String(isLoading));
  storyInput.disabled = isLoading;
  textOnlyToggle.disabled = isLoading;
  if (targetDurationInput) {
    targetDurationInput.disabled = isLoading;
  }
}

function setResultsProcessing(isProcessing) {
  if (!resultsPanel) {
    return;
  }

  resultsPanel.classList.toggle("is-processing", isProcessing);
  resultsPanel.setAttribute("aria-busy", String(isProcessing));
}

function setResultsVisible(isVisible) {
  if (!resultsPanel) {
    return;
  }

  resultsPanel.hidden = !isVisible;
}

function setResultActionsEnabled(isEnabled) {
  downloadJsonButton.disabled = !isEnabled;
  downloadStoryButton.disabled = !isEnabled;
  downloadImagesButton.disabled = true;
  downloadVideoButton.disabled = true;
}

function createElement(tagName, className = "", text = "") {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  if (text) {
    element.textContent = text;
  }
  return element;
}

function createStackItem() {
  return createElement("div", "stack-item");
}

function createKicker(text) {
  return createElement("span", "card-kicker", text);
}

function createParagraph(text) {
  return createElement("p", "", text || "");
}

function createTextElement(tagName, className, text) {
  return createElement(tagName, className, text || "");
}

function createStatus(status) {
  const imageStatus = status || "failed";
  return createElement(
    "span",
    `image-status ${toClassToken(imageStatus)}`,
    formatImageStatusLabel(imageStatus)
  );
}

function createProviderBadge(image) {
  if (!image?.provider) {
    return null;
  }

  const provider = String(image.provider);
  const label =
    provider === "storyboard" && image.warning
      ? "Storyboard fallback"
      : formatProviderLabel(provider);

  return createElement(
    "span",
    `image-status provider ${toClassToken(provider)}`,
    label
  );
}

function toClassToken(value) {
  const token = String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");

  return token || "unknown";
}

function formatImageStatusLabel(status) {
  return String(status || "failed").replace(/_/g, " ");
}

function createPlaceholder(text) {
  return createElement("div", "image-placeholder", text);
}

function createInlineLoadingState(text) {
  const container = createElement("div", "image-placeholder inline-loading");
  const spinner = createElement("span", "gallery-spinner");
  spinner.setAttribute("aria-hidden", "true");
  container.append(spinner, createTextElement("span", "", text));
  return container;
}

function buildApiErrorMessage(data, statusCode) {
  if (typeof data.detail === "string") {
    return data.detail;
  }

  if (Array.isArray(data.errors) && data.errors.length > 0) {
    return data.errors.map((error) => error.msg).join(" ");
  }

  if (Array.isArray(data.detail) && data.detail.length > 0) {
    return data.detail.map((error) => error.msg).join(" ");
  }

  return `Backend returned HTTP ${statusCode}.`;
}

function getRequestErrorMessage(error) {
  if (isBackendConnectionError(error)) {
    return "Backend unavailable";
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Story generation failed";
}

function getGenerationToastMessage(data) {
  if (data.message === IMAGE_DEFERRED_MESSAGE) {
    return IMAGE_DEFERRED_MESSAGE;
  }

  if (data.status === "text_only") {
    return "Story generated in text-only mode";
  }

  if (hasStoryboardFallback(data)) {
    return "Story generated with local storyboard fallback";
  }

  if (data.status === "partial") {
    return IMAGE_FAILURE_MESSAGE;
  }

  return "Story generated successfully";
}

function getGenerationToastType(data) {
  return data.status === "partial" ? "error" : "success";
}

function getImagePlaceholderText(status) {
  if (status === "generating") {
    return "Generating...";
  }

  if (status === "skipped") {
    return "No image yet";
  }

  if (status === "failed") {
    return "Failed";
  }

  return "No image";
}

function getDisplayImageStatus(image, canGenerate) {
  if (image.status === "skipped" && canGenerate) {
    return "ready";
  }

  if (isStoryboardFallback(image)) {
    return "fallback";
  }

  return image.status || "failed";
}

function getImageAltPrefix(image) {
  if (image.provider === "storyboard" && image.warning) {
    return "Storyboard fallback image";
  }

  if (image.status === "failed") {
    return "Fallback placeholder image";
  }

  if (image.provider) {
    return `${formatProviderLabel(image.provider)} generated image`;
  }

  return "Generated image";
}

function formatProviderLabel(provider) {
  const normalizedProvider = String(provider || "").toLowerCase();
  const labels = {
    fal: "fal.ai",
    huggingface: "Hugging Face",
    pollinations: "Pollinations",
    storyboard: "Storyboard",
    "stable-diffusion": "Stable Diffusion",
    placeholder: "Placeholder",
  };

  return labels[normalizedProvider] || provider;
}

function hasStoryboardFallback(data) {
  return (data.images || []).some(
    (image) => isStoryboardFallback(image)
  );
}

function isStoryboardFallback(image) {
  return image?.provider === "storyboard" && Boolean(image.warning);
}

function getImageCountLabel(data) {
  const images = data.images || [];
  const summary = data.image_summary || buildImageSummary(images);
  const total = summary.total === undefined ? images.length : summary.total;

  if (hasStoryboardFallback(data)) {
    const hostedCount = images.filter(
      (image) => image.status === "success" && !isStoryboardFallback(image)
    ).length;

    return `${hostedCount}/${total} hosted`;
  }

  return summary.total === undefined
    ? images.length
    : `${summary.succeeded || 0}/${summary.total}`;
}

function getResultTitle(status) {
  if (status === "text_only") {
    return "Text Output";
  }

  if (status === "partial") {
    return "Partial Output";
  }

  return "Generated Output";
}

function getDownloadableImages(data) {
  return (data.images || []).filter(
    (image) =>
      image.status === "success" &&
      Boolean(image.image_url)
  );
}

function formatImageError(error) {
  const rawMessage = String(error || "").trim();
  if (!rawMessage) {
    return "";
  }

  const message = extractReadableError(rawMessage);
  const lowered = message.toLowerCase();

  if (lowered.includes("pollinations") && lowered.includes("http 524")) {
    return "Pollinations timed out while generating the image. Try again or lower the image quality/size.";
  }

  if (lowered.includes("status 524") || lowered.includes("error code: 524")) {
    return "Image generation timed out upstream. Try again or lower the image quality/size.";
  }

  if (lowered.includes("remote end closed connection")) {
    return "The image provider closed the connection before returning an image. Try again in a moment.";
  }

  if (
    lowered.includes("403 forbidden") &&
    (lowered.includes("inference providers") ||
      lowered.includes("sufficient permissions") ||
      lowered.includes("huggingface"))
  ) {
    return "Hugging Face token lacks permission to call Inference Providers. Create a token with Inference Providers access or switch image provider.";
  }

  if (lowered.includes("pollinations") && lowered.includes("http 502")) {
    return "Pollinations image backend is temporarily unavailable (HTTP 502). Try again later or use a different image provider.";
  }

  if (lowered.includes("bad_gateway") || lowered.includes("bad gateway")) {
    return "Image provider backend is temporarily unavailable (HTTP 502). Try again later or use a different image provider.";
  }

  return truncateErrorMessage(message);
}

function formatImageWarning(warning) {
  const rawMessage = String(warning || "").trim();
  if (!rawMessage) {
    return "";
  }

  return truncateErrorMessage(extractReadableError(rawMessage));
}

function extractReadableError(rawMessage) {
  const lines = rawMessage
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length === 0) {
    return rawMessage;
  }

  let message = lines[lines.length - 1];
  if (rawMessage.includes("Traceback (most recent call last)")) {
    for (let index = lines.length - 1; index >= 0; index -= 1) {
      const line = lines[index];
      if (
        line.startsWith("File ") ||
        line.startsWith("^") ||
        line.startsWith("Traceback ") ||
        line.startsWith("During handling") ||
        line.startsWith("The above exception")
      ) {
        continue;
      }

      message = line;
      break;
    }
  }

  const exceptionPrefix = message.match(/^([\w.]+(?:Error|Exception)):\s+(.+)$/);
  if (exceptionPrefix) {
    message = exceptionPrefix[2];
  }

  return removeProviderPayload(message);
}

function removeProviderPayload(message) {
  const payloadMarkers = [": {", ": [", "\n{", "\n["];
  for (const marker of payloadMarkers) {
    const markerIndex = message.indexOf(marker);
    if (markerIndex !== -1) {
      return `${message.slice(0, markerIndex).replace(/[.: ]+$/, "")}.`;
    }
  }

  return message;
}

function truncateErrorMessage(message, maxLength = 240) {
  if (message.length <= maxLength) {
    return message;
  }

  return `${message.slice(0, maxLength - 1).trimEnd()}...`;
}

function getDownloadFileName(imageSource) {
  const normalizedSource = imageSource.replaceAll("\\", "/");

  try {
    const url = new URL(normalizedSource);
    return url.pathname.split("/").pop() || "cinegen-image.png";
  } catch {
    return (
      normalizedSource
        .split("?")[0]
        .split("#")[0]
        .split("/")
        .pop() || "cinegen-image.png"
    );
  }
}

function getTextDownloadName(fileName) {
  return (fileName || "cinegen-story-results.json").replace(/\.json$/i, ".txt");
}

async function downloadImage(image) {
  const imageUrl = image.image_url || "";
  if (!imageUrl) {
    throw new Error("No image URL available.");
  }

  const response = await fetch(imageUrl);
  if (!response.ok) {
    throw new Error("Unable to download image.");
  }

  const blob = await response.blob();
  downloadBlob(blob, getDownloadFileName(image.image_url));
}

async function downloadVideo(data) {
  const videoUrl = data.video_url || "";
  if (!videoUrl) {
    throw new Error("No video URL available.");
  }

  const response = await fetch(videoUrl);
  if (!response.ok) {
    throw new Error("Unable to download video.");
  }

  const blob = await response.blob();
  downloadBlob(blob, getDownloadFileName(videoUrl) || "cinegen-video.mp4");
}

function downloadJson(data, fileName) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  downloadBlob(blob, fileName);
}

function downloadText(text, fileName) {
  const blob = new Blob([text], { type: "text/plain" });
  downloadBlob(blob, fileName);
}

function downloadBlob(blob, fileName) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = fileName;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function buildStoryResultsText(data) {
  const lines = [
    "CineGen AI Story Results",
    "",
    "Story:",
    data.story || "",
    "",
    "Scenes:",
    ...data.scenes.map((scene) => `${scene.scene}. ${scene.description}`),
    "",
    "Prompts:",
    ...data.prompts.map((prompt) => `${prompt.scene}. ${prompt.prompt}`),
    "",
    "Images:",
    ...data.images.map((image) =>
      [
        `Scene ${image.scene}`,
        `Status: ${image.status}`,
        image.provider ? `Provider: ${formatProviderLabel(image.provider)}` : "",
        image.image_path ? `Path: ${image.image_path}` : "",
        image.image_url ? `URL: ${image.image_url}` : "",
        image.warning ? `Warning: ${formatImageWarning(image.warning)}` : "",
        image.error ? `Error: ${formatImageError(image.error)}` : "",
      ]
        .filter(Boolean)
        .join(" | ")
    ),
    "",
    "Narration:",
    ...(data.audio || []).map((audio) =>
      [
        `Scene ${audio.scene}`,
        `Status: ${audio.status}`,
        audio.audio_path ? `Path: ${audio.audio_path}` : "",
        audio.audio_url ? `URL: ${audio.audio_url}` : "",
        audio.duration_seconds ? `Duration: ${audio.duration_seconds}s` : "",
        audio.error ? `Error: ${audio.error}` : "",
      ]
        .filter(Boolean)
        .join(" | ")
    ),
    "",
    "Video:",
    data.video_path ? `Path: ${data.video_path}` : "",
    data.video_url ? `URL: ${data.video_url}` : "",
    data.duration ? `Duration: ${data.duration}` : "",
  ];

  return `${lines.join("\n")}\n`;
}

function formatHistoryTitle(fileName) {
  const baseName = String(fileName || "story").replace(/\.json$/i, "");
  return baseName.replace(/^story/i, "Story");
}

function renderEmpty(container, message) {
  clearNode(container);
  container.classList.remove("image-loading-state");
  container.classList.remove("video-loading-state");
  container.removeAttribute("aria-busy");
  container.classList.add("empty-state");
  const paragraph = document.createElement("p");
  paragraph.textContent = message;
  container.append(paragraph);
}

function clearNode(node) {
  node.replaceChildren();
}

function estimateSceneCount(story) {
  const matches = story
    .trim()
    .split(/[.!?]+/)
    .map((part) => part.trim())
    .filter(Boolean);

  return Math.max(1, matches.length);
}

function formatDate(value) {
  if (!value) {
    return "Unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString();
}

async function shareUrl(url) {
  if (!url) {
    showToast("No video URL available.", "error");
    return;
  }
  try {
    await navigator.clipboard.writeText(url);
    showToast("Video link copied.", "success");
  } catch {
    showToast(url, "success");
  }
}

function debounce(callback, delay) {
  let timeoutId = null;
  return (...args) => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => callback(...args), delay);
  };
}
