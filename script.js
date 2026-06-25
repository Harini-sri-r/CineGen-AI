const API_BASE_URL = "http://127.0.0.1:8001";
const GENERATE_ENDPOINT = `${API_BASE_URL}/generate-story`;
const HISTORY_ENDPOINT = `${API_BASE_URL}/history`;
const HISTORY_STATS_ENDPOINT = `${API_BASE_URL}/history/stats`;
const MIN_STORY_LENGTH = 12;
const IMAGE_PROGRESS_STEP_MS = 2600;
const IMAGE_LOADING_MESSAGE = "Generating images...";
const IMAGE_FAILURE_MESSAGE = "Image generation failed. Story generation completed.";
const IMAGE_DEFERRED_MESSAGE = "Story and prompts generated. Generate images one scene at a time.";

const storyForm = document.querySelector("#storyForm");
const storyInput = document.querySelector("#storyInput");
const storyHelp = document.querySelector("#storyHelp");
const storyError = document.querySelector("#storyError");
const textOnlyToggle = document.querySelector("#textOnlyToggle");
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
const refreshHistoryButton = document.querySelector("#refreshHistoryButton");
const scenesList = document.querySelector("#scenesList");
const promptsList = document.querySelector("#promptsList");
const imagesGallery = document.querySelector("#imagesGallery");
const historyList = document.querySelector("#historyList");
const toast = document.querySelector("#toast");
const generationOverlay = document.querySelector("#generationOverlay");
const overlayMessage = document.querySelector("#overlayMessage");

let latestResult = null;
let progressTimer = null;
let toastTimer = null;

storyInput.addEventListener("input", () => {
  validateStory({ showErrors: false });
});

storyForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!validateStory({ showErrors: true })) {
    return;
  }

  latestResult = null;
  setResultActionsEnabled(false);
  setLoading(true);
  setResultsProcessing(true);
  setResultsVisible(false);
  resetProgress();
  const estimatedSceneCount = estimateSceneCount(storyInput.value);
  showGenerationOverlay("Generating scenes...");
  showStatus({
    title: "Processing",
    badge: "running",
    message: "Generating scenes...",
  });
  startProgress({
    imagesRequested: !textOnlyToggle.checked,
    imageCount: estimatedSceneCount,
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
    completeProgress();
    renderResult(latestResult);
    setResultsVisible(true);
    await Promise.all([
      refreshHistory({ silent: true }),
      refreshStats({ silent: true }),
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
    setLoading(false);
    setResultsProcessing(false);
    stopProgressTimer();
    hideGenerationOverlay();
  }
});

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

refreshHistoryButton.addEventListener("click", () => {
  refreshHistory({ silent: false });
  refreshStats({ silent: true });
});

refreshHistory({ silent: true });
refreshStats({ silent: true });
validateStory({ showErrors: false });

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await readJsonResponse(response);
  return { response, data };
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

async function refreshHistory({ silent }) {
  refreshHistoryButton.disabled = true;

  try {
    const { response, data } = await fetchJson(HISTORY_ENDPOINT);
    if (!response.ok || !Array.isArray(data)) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }

    renderHistory(data);
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

async function refreshStats({ silent }) {
  try {
    const { response, data } = await fetchJson(HISTORY_STATS_ENDPOINT);
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(data, response.status));
    }

    totalStories.textContent = data.total_stories ?? 0;
    totalScenes.textContent = data.total_scenes ?? 0;
    totalImages.textContent = data.total_images ?? 0;
  } catch (error) {
    totalStories.textContent = "0";
    totalScenes.textContent = "0";
    totalImages.textContent = "0";
    if (!silent) {
      showToast(getRequestErrorMessage(error), "error");
    }
  }
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

function normalizeResult(data, { source, fileName, createdAt = "" }) {
  const images = Array.isArray(data.images) ? data.images : [];
  return {
    ...data,
    source,
    created_at: data.created_at || createdAt,
    file_name: data.file_name || fileName,
    scenes: Array.isArray(data.scenes) ? data.scenes : [],
    prompts: Array.isArray(data.prompts) ? data.prompts : [],
    images,
    image_summary: data.image_summary || buildImageSummary(images),
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
    .filter((image) => image.status !== "skipped" && image.image_url)
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
      console.error("Image preload timed out", imageUrl);
      resolve();
    }, 15000);

    image.onload = () => {
      window.clearTimeout(timeout);
      console.log("Preloaded", imageUrl);
      resolve();
    };
    image.onerror = (event) => {
      window.clearTimeout(timeout);
      console.error("Image preload failed", imageUrl, event);
      resolve();
    };
    image.src = imageUrl;
  });
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
  const summary = data.image_summary;

  resultTitle.textContent =
    data.source === "history"
      ? `Loaded: ${formatHistoryTitle(data.file_name)}`
      : getResultTitle(data.status);
  storyPreview.textContent = data.story || "Story text unavailable.";
  sceneCount.textContent = scenes.length;
  promptCount.textContent = prompts.length;
  imageCount.textContent =
    summary.total === undefined
      ? images.length
      : `${summary.succeeded || 0}/${summary.total}`;

  setResultActionsEnabled(true);
  downloadImagesButton.disabled = getDownloadableImages(data).length === 0;

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
      error: null,
    };
    const imageUrl = image.image_url || "";
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
        ? `${getImageAltPrefix(image.status)} for ${scene.description}`
        : `${getImageAltPrefix(image.status)} for scene ${image.scene}`;
      img.loading = "lazy";
      img.onload = () => console.log("Loaded", img.src);
      img.onerror = (event) => {
        console.error("Image failed", img.src, event);
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
    meta.append(
      createKicker(`Scene ${cardSource.scene}`),
      createStatus(getDisplayImageStatus(image, canGenerate))
    );

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

    if (image.error) {
      card.append(createTextElement("p", "image-error", image.error));
    }

    const actions = createElement("div", "image-actions");

    if (imageUrl) {
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

function startProgress({ imagesRequested, imageCount }) {
  stopProgressTimer();

  const steps = buildProgressSteps({ imagesRequested, imageCount });
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

function buildProgressSteps({ imagesRequested, imageCount }) {
  const totalImages = Math.max(1, Number(imageCount) || 1);
  const baseSteps = [
    { key: "scenes", label: "Generating scenes..." },
    { key: "prompts", label: "Creating prompts..." },
  ];

  if (imagesRequested) {
    baseSteps.push(
      ...Array.from({ length: totalImages }, (_, index) => ({
        key: `image-${index + 1}`,
        label: `Generating image ${index + 1} of ${totalImages}...`,
      }))
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
  return createElement("span", `image-status ${imageStatus}`, imageStatus);
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
  if (error instanceof TypeError) {
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

  return image.status || "failed";
}

function getImageAltPrefix(status) {
  if (status === "failed") {
    return "Fallback placeholder image";
  }

  return "Generated image";
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
      image.status !== "skipped" &&
      image.status !== "generating" &&
      Boolean(image.image_url)
  );
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
        image.image_path ? `Path: ${image.image_path}` : "",
        image.image_url ? `URL: ${image.image_url}` : "",
        image.error ? `Error: ${image.error}` : "",
      ]
        .filter(Boolean)
        .join(" | ")
    ),
  ];

  return `${lines.join("\n")}\n`;
}

function formatHistoryTitle(fileName) {
  const baseName = fileName.replace(/\.json$/i, "");
  return baseName.replace(/^story/i, "Story");
}

function renderEmpty(container, message) {
  clearNode(container);
  container.classList.remove("image-loading-state");
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
