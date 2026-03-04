const FACE_ORDER = ["U", "R", "F", "D", "L", "B"];
const FACE_LABEL = {
  U: "U (Tren)",
  R: "R (Phai)",
  F: "F (Truoc)",
  D: "D (Duoi)",
  L: "L (Trai)",
  B: "B (Sau)",
};
const STICKER_COLORS = {
  U: "#f7f7f7",
  R: "#d94f30",
  F: "#2f9b59",
  D: "#f2d13d",
  L: "#e77b2e",
  B: "#3876ce",
};

const puzzleMode = document.getElementById("puzzleMode");
const solverSection = document.getElementById("solverSection");
const cuboidSection = document.getElementById("cuboidSection");

const cameraEl = document.getElementById("camera");
const frameCanvas = document.getElementById("frameCanvas");
const captureStatus = document.getElementById("captureStatus");
const faceCards = document.getElementById("faceCards");
const stateInput = document.getElementById("stateInput");

const startCameraBtn = document.getElementById("startCameraBtn");
const captureBtn = document.getElementById("captureBtn");
const resetBtn = document.getElementById("resetBtn");
const solveFromCaptureBtn = document.getElementById("solveFromCaptureBtn");
const solveFromStateBtn = document.getElementById("solveFromStateBtn");

const resultSection = document.getElementById("resultSection");
const resultSummary = document.getElementById("resultSummary");
const rotationHint = document.getElementById("rotationHint");
const stepList = document.getElementById("stepList");

const cuboidNote = document.getElementById("cuboidNote");
const cuboidSteps = document.getElementById("cuboidSteps");
const cuboidAlgs = document.getElementById("cuboidAlgs");

let streamRef = null;
let currentFaceIndex = 0;
let capturedRgbByFace = {};
let centerColorByFace = {};
let classifiedFacelets = {};

init();

function init() {
  buildFaceCards();
  bindEvents();
  updateCaptureStatus();
  loadCuboidGuide();
}

function bindEvents() {
  startCameraBtn.addEventListener("click", startCamera);
  captureBtn.addEventListener("click", captureCurrentFace);
  resetBtn.addEventListener("click", resetCaptures);
  solveFromCaptureBtn.addEventListener("click", solveFromCapture);
  solveFromStateBtn.addEventListener("click", solveFromStateText);
  puzzleMode.addEventListener("change", toggleMode);
}

async function startCamera() {
  if (streamRef) {
    captureBtn.disabled = false;
    return;
  }

  try {
    const mediaStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "environment",
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    });
    cameraEl.srcObject = mediaStream;
    streamRef = mediaStream;
    captureBtn.disabled = false;
    captureStatus.textContent = "Camera dang chay. Chup mat hien tai trong khung.";
  } catch (error) {
    captureStatus.textContent =
      "Khong mo duoc camera. Hay cap quyen camera trong trinh duyet.";
  }
}

function stopCamera() {
  if (!streamRef) return;
  streamRef.getTracks().forEach((track) => track.stop());
  streamRef = null;
  cameraEl.srcObject = null;
  captureBtn.disabled = true;
}

function resetCaptures() {
  currentFaceIndex = 0;
  capturedRgbByFace = {};
  centerColorByFace = {};
  classifiedFacelets = {};
  stateInput.value = "";
  solveFromCaptureBtn.disabled = true;
  clearResult();
  buildFaceCards();
  updateCaptureStatus();
}

function updateCaptureStatus() {
  if (currentFaceIndex >= FACE_ORDER.length) {
    captureStatus.textContent = "Da chup du 6 mat. Ban co the bam Giai.";
    return;
  }
  const face = FACE_ORDER[currentFaceIndex];
  captureStatus.textContent = `Mat hien tai: ${FACE_LABEL[face]} (${currentFaceIndex + 1}/6)`;
}

function captureCurrentFace() {
  if (!streamRef || cameraEl.videoWidth === 0 || cameraEl.videoHeight === 0) {
    captureStatus.textContent = "Can bat camera truoc khi chup.";
    return;
  }
  if (currentFaceIndex >= FACE_ORDER.length) {
    captureStatus.textContent = "Da du 6 mat. Neu muon chup lai, bam Chup lai tu dau.";
    return;
  }

  const face = FACE_ORDER[currentFaceIndex];
  const sampled = sampleFaceletsFromVideo();
  capturedRgbByFace[face] = sampled;
  centerColorByFace[face] = sampled[4];
  renderFaceCard(face, sampled, "rgb");

  currentFaceIndex += 1;
  updateCaptureStatus();

  if (currentFaceIndex === FACE_ORDER.length) {
    classifiedFacelets = classifyAllFacelets(capturedRgbByFace, centerColorByFace);
    renderClassifiedPreview();
    const roughState = buildStateString(classifiedFacelets);
    stateInput.value = roughState;
    solveFromCaptureBtn.disabled = false;
  }
}

function sampleFaceletsFromVideo() {
  frameCanvas.width = cameraEl.videoWidth;
  frameCanvas.height = cameraEl.videoHeight;
  const ctx = frameCanvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(cameraEl, 0, 0, frameCanvas.width, frameCanvas.height);

  const side = Math.min(frameCanvas.width, frameCanvas.height) * 0.52;
  const startX = (frameCanvas.width - side) / 2;
  const startY = (frameCanvas.height - side) / 2;
  const cell = side / 3;
  const patchRadius = Math.max(4, Math.floor(cell * 0.16));

  const out = [];
  for (let row = 0; row < 3; row += 1) {
    for (let col = 0; col < 3; col += 1) {
      const cx = startX + col * cell + cell / 2;
      const cy = startY + row * cell + cell / 2;
      out.push(samplePatchColor(ctx, cx, cy, patchRadius));
    }
  }
  return out;
}

function samplePatchColor(ctx, cx, cy, radius) {
  const x = Math.max(0, Math.round(cx - radius));
  const y = Math.max(0, Math.round(cy - radius));
  const size = Math.max(2, radius * 2);
  const image = ctx.getImageData(x, y, size, size);
  const data = image.data;

  let r = 0;
  let g = 0;
  let b = 0;
  const pixels = data.length / 4;

  for (let i = 0; i < data.length; i += 4) {
    r += data[i];
    g += data[i + 1];
    b += data[i + 2];
  }

  return {
    r: Math.round(r / pixels),
    g: Math.round(g / pixels),
    b: Math.round(b / pixels),
  };
}

function classifyAllFacelets(rgbFaces, centers) {
  const result = {};
  for (const face of FACE_ORDER) {
    const facelets = rgbFaces[face] || [];
    result[face] = facelets.map((rgb) => nearestCenter(rgb, centers));
  }
  return result;
}

function nearestCenter(rgb, centers) {
  let bestFace = "U";
  let bestDistance = Number.POSITIVE_INFINITY;

  for (const face of FACE_ORDER) {
    const center = centers[face];
    if (!center) continue;
    const dist =
      (rgb.r - center.r) ** 2 +
      (rgb.g - center.g) ** 2 +
      (rgb.b - center.b) ** 2;
    if (dist < bestDistance) {
      bestDistance = dist;
      bestFace = face;
    }
  }
  return bestFace;
}

function buildStateString(faces) {
  return FACE_ORDER.map((face) => (faces[face] || []).join("")).join("");
}

function buildFaceCards() {
  faceCards.innerHTML = "";
  for (const face of FACE_ORDER) {
    const card = document.createElement("article");
    card.className = "face-card";
    card.dataset.face = face;
    card.innerHTML = `
      <h3>${FACE_LABEL[face]}</h3>
      <div class="sticker-grid">
        ${Array.from({ length: 9 })
          .map(() => '<span class="sticker"></span>')
          .join("")}
      </div>
    `;
    faceCards.appendChild(card);
  }
}

function renderFaceCard(face, stickers, mode) {
  const card = faceCards.querySelector(`[data-face="${face}"]`);
  if (!card) return;

  const nodes = card.querySelectorAll(".sticker");
  stickers.forEach((entry, idx) => {
    if (!nodes[idx]) return;
    if (mode === "rgb") {
      nodes[idx].style.background = `rgb(${entry.r}, ${entry.g}, ${entry.b})`;
      nodes[idx].textContent = "";
    } else {
      nodes[idx].style.background = STICKER_COLORS[entry] || "#cccccc";
      nodes[idx].textContent = entry;
    }
  });
}

function renderClassifiedPreview() {
  for (const face of FACE_ORDER) {
    renderFaceCard(face, classifiedFacelets[face] || [], "label");
  }
}

function formatRotations(rotations) {
  if (!rotations) return "";
  const parts = FACE_ORDER.map((face) => `${face}:${rotations[face] || 0}x90`);
  return parts.join(" | ");
}

async function solveFromCapture() {
  if (Object.keys(classifiedFacelets).length < 6) {
    captureStatus.textContent = "Can chup du 6 mat truoc khi giai.";
    return;
  }

  await solveCube({
    faces: classifiedFacelets,
    maxAttempts: 4096,
  });
}

async function solveFromStateText() {
  const state = stateInput.value.trim().toUpperCase();
  await solveCube({ state });
}

async function solveCube(payload) {
  resultSection.classList.remove("hidden");
  resultSummary.textContent = "Dang tinh toan loi giai...";
  rotationHint.textContent = "";
  stepList.innerHTML = "";

  try {
    const response = await fetch("/api/solve-3x3", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Khong giai duoc trang thai nay.");
    }

    renderResult(data);
    if (data.state) {
      stateInput.value = data.state;
    }
  } catch (error) {
    resultSummary.textContent = `Loi: ${error.message}`;
  }
}

function renderResult(data) {
  const moveCount = Number.isFinite(data.moveCount) ? data.moveCount : 0;
  if (!data.solution || data.solution.trim() === "") {
    resultSummary.textContent = "Khoi da o trang thai giai xong.";
  } else {
    resultSummary.textContent = `So buoc: ${moveCount} | Chuoi loi giai: ${data.solution}`;
  }

  if (data.rotations) {
    rotationHint.textContent = `Xoay can chinh mat (tu camera): ${formatRotations(data.rotations)}`;
  }

  stepList.innerHTML = "";
  const steps = Array.isArray(data.steps) ? data.steps : [];
  if (!steps.length) {
    const item = document.createElement("li");
    item.textContent = "Khong can them thao tac.";
    stepList.appendChild(item);
    return;
  }

  for (const step of steps) {
    const item = document.createElement("li");
    item.textContent = step.instruction;
    stepList.appendChild(item);
  }
}

function clearResult() {
  resultSection.classList.add("hidden");
  resultSummary.textContent = "";
  rotationHint.textContent = "";
  stepList.innerHTML = "";
}

function toggleMode() {
  const mode = puzzleMode.value;
  if (mode === "cuboid") {
    solverSection.classList.add("hidden");
    cuboidSection.classList.remove("hidden");
    stopCamera();
    clearResult();
  } else {
    cuboidSection.classList.add("hidden");
    solverSection.classList.remove("hidden");
  }
}

async function loadCuboidGuide() {
  try {
    const response = await fetch("/api/cuboid-guide");
    const data = await response.json();
    cuboidNote.textContent = data.note || "";
    cuboidSteps.innerHTML = "";
    cuboidAlgs.innerHTML = "";

    for (const step of data.steps || []) {
      const li = document.createElement("li");
      li.textContent = step;
      cuboidSteps.appendChild(li);
    }

    for (const alg of data.example_algs || []) {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${alg.name}:</strong> <code>${alg.sequence}</code>`;
      cuboidAlgs.appendChild(li);
    }
  } catch (_error) {
    cuboidNote.textContent = "Khong tai duoc huong dan cuboid.";
  }
}
