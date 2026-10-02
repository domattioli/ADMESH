/* ADMESH browser app: form handling, canvas drawing and downloads.
   All meshing happens in worker.js. */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const worker = new Worker("worker.js");
  const form = $("mesh-form");
  const fileInput = $("domain-file");
  const button = $("mesh-button");
  const canvas = $("mesh-canvas");
  const STATES = ["loading", "empty", "error", "ready"];
  const DOMAIN_EXTENSIONS = [".json", ".toml", ".14"];

  let runtimeReady = false;
  let busy = false;
  let last = null;

  function setState(name) {
    STATES.forEach((s) => {
      const el = document.querySelector('[data-state="' + s + '"]');
      el.hidden = s !== name;
    });
    document.querySelector('[data-state="loading"]').setAttribute("aria-busy", String(name === "loading"));
  }

  function showError(message) {
    $("error-text").textContent = message;
    setState("error");
  }

  function refreshButton() {
    button.disabled = !runtimeReady || busy || fileInput.files.length === 0;
  }

  function hasDomainExtension(name) {
    const lower = name.toLowerCase();
    return DOMAIN_EXTENSIONS.some((ext) => lower.endsWith(ext));
  }

  /* ---- theme toggle ---- */
  const root = document.documentElement;
  function currentTheme() {
    return root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }
  function paintToggle() {
    $("theme-toggle").textContent = currentTheme() === "dark" ? "☀" : "☾";
  }
  $("theme-toggle").addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem("dvs-theme", next); } catch (e) { /* storage blocked */ }
    paintToggle();
    draw();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { paintToggle(); draw(); });
  paintToggle();

  /* ---- worker messages ---- */
  worker.onmessage = (event) => {
    const msg = event.data;
    if (msg.type === "status") {
      $("status-text").textContent = msg.text;
    } else if (msg.type === "ready") {
      runtimeReady = true;
      if (!last && !busy) setState("empty");
      refreshButton();
    } else if (msg.type === "result") {
      busy = false;
      last = msg.result;
      showResult(last);
      refreshButton();
    } else if (msg.type === "error") {
      busy = false;
      showError(msg.message);
      refreshButton();
    }
  };
  worker.onerror = () => {
    busy = false;
    showError("The meshing worker stopped unexpectedly. Reload the page to try again.");
    refreshButton();
  };

  /* ---- form ---- */
  fileInput.addEventListener("change", () => {
    refreshButton();
    const file = fileInput.files[0];
    if (file && !hasDomainExtension(file.name)) {
      showError("'" + file.name + "' is not a domain file. Upload a .json, .toml or fort.14 file. Registry names are not looked up in the browser.");
    }
  });

  function readNumber(id, label) {
    const raw = $(id).value.trim();
    if (raw === "") return null;
    const value = Number(raw);
    if (!Number.isFinite(value) || value <= 0) throw new Error(label + " must be a positive number.");
    return value;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = fileInput.files[0];
    if (!file || busy || !runtimeReady) return;
    if (!hasDomainExtension(file.name)) {
      showError("'" + file.name + "' is not a domain file. Upload a .json, .toml or fort.14 file. Registry names are not looked up in the browser.");
      return;
    }
    let hMin, hMax;
    try {
      hMin = readNumber("h-min", "h_min");
      hMax = readNumber("h-max", "h_max");
      if (hMin !== null && hMax !== null && hMin > hMax) throw new Error("h_min must not be larger than h_max.");
    } catch (err) {
      showError(err.message);
      return;
    }
    busy = true;
    refreshButton();
    $("status-text").textContent = "Reading file";
    setState("loading");
    const text = await file.text();
    worker.postMessage({ type: "mesh", name: file.name, text, hMin, hMax });
  });

  /* ---- result ---- */
  function fmt(x) { return Number.isFinite(x) ? x.toFixed(3) : "n/a"; }

  function showResult(result) {
    $("stat-nodes").textContent = String(result.stats.nodes);
    $("stat-elements").textContent = String(result.stats.elements);
    $("stat-min").textContent = fmt(result.stats.minQuality);
    $("stat-mean").textContent = fmt(result.stats.meanQuality);
    const c = result.checks;
    const rows = [
      ["Every triangle has positive area", c.positive_area, "triangles with zero or negative area"],
      ["Every point lies inside the domain", c.inside_domain, "points outside the domain"],
      ["The boundary is watertight", c.watertight, "open or over-shared edges"],
    ];
    const list = $("checks");
    list.replaceChildren();
    rows.forEach(([label, check, failText]) => {
      const li = document.createElement("li");
      const tag = document.createElement("span");
      tag.className = check.ok ? "pass" : "fail";
      tag.textContent = check.ok ? "Pass" : "Fail";
      li.append(tag, " " + label + (check.ok ? "" : " (" + check.count + " " + failText + ")"));
      list.append(li);
    });
    setState("ready");
    draw();
  }

  function cssVar(name) { return getComputedStyle(root).getPropertyValue(name).trim(); }

  function mix(a, b, t) {
    return [0, 1, 2].map((i) => Math.round(a[i] + (b[i] - a[i]) * t));
  }
  function parseColor(value) {
    const probe = document.createElement("canvas").getContext("2d");
    probe.fillStyle = value;
    probe.fillRect(0, 0, 1, 1);
    const d = probe.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2]];
  }

  function draw() {
    if (!last || document.querySelector('[data-state="ready"]').hidden) return;
    const { nodes, elements, quality } = last;
    let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
    for (let i = 0; i < nodes.length; i += 2) {
      xmin = Math.min(xmin, nodes[i]); xmax = Math.max(xmax, nodes[i]);
      ymin = Math.min(ymin, nodes[i + 1]); ymax = Math.max(ymax, nodes[i + 1]);
    }
    const dpr = window.devicePixelRatio || 1;
    const cssWidth = canvas.clientWidth || 600;
    const pad = 12;
    const spanX = (xmax - xmin) || 1, spanY = (ymax - ymin) || 1;
    const cssHeight = Math.max(160, Math.min(cssWidth * (spanY / spanX), cssWidth * 1.2));
    canvas.width = Math.round(cssWidth * dpr);
    canvas.height = Math.round(cssHeight * dpr);
    canvas.style.height = cssHeight + "px";
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssWidth, cssHeight);
    const scale = Math.min((cssWidth - 2 * pad) / spanX, (cssHeight - 2 * pad) / spanY);
    const ox = (cssWidth - scale * spanX) / 2, oy = (cssHeight - scale * spanY) / 2;
    const px = (i) => ox + (nodes[2 * i] - xmin) * scale;
    const py = (i) => cssHeight - (oy + (nodes[2 * i + 1] - ymin) * scale);
    const low = parseColor(cssVar("--q-low")), mid = parseColor(cssVar("--q-mid")), high = parseColor(cssVar("--q-high"));
    ctx.lineWidth = 0.6;
    ctx.strokeStyle = cssVar("--mesh-line");
    ctx.lineJoin = "round";
    for (let e = 0; e < elements.length; e += 3) {
      const q = Math.max(0, Math.min(1, quality[e / 3]));
      const rgb = q < 0.5 ? mix(low, mid, q / 0.5) : mix(mid, high, (q - 0.5) / 0.5);
      ctx.fillStyle = "rgba(" + rgb.join(",") + ",0.55)";
      ctx.beginPath();
      ctx.moveTo(px(elements[e]), py(elements[e]));
      ctx.lineTo(px(elements[e + 1]), py(elements[e + 1]));
      ctx.lineTo(px(elements[e + 2]), py(elements[e + 2]));
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }
  }
  window.addEventListener("resize", draw);

  /* ---- downloads ---- */
  function download(filename, text) {
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function baseName() {
    const file = fileInput.files[0];
    return file ? file.name.replace(/\.[^.]+$/, "") || "mesh" : "mesh";
  }
  $("download-fort14").addEventListener("click", () => last && download(baseName() + ".14", last.fort14));
  $("download-msh").addEventListener("click", () => last && download(baseName() + ".msh", last.msh));

  setState("loading");
})();
