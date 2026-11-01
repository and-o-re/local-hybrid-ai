// Frontend Desacoplado 100% Offline (Vanilla JS sem dependências externas pesadas)

let currentBrowserTarget = "vault"; // 'vault' ou 'code'
let currentBrowserPath = "~";
let currentParentPath = "~";
let strictOfflineState = false;

// =====================================================================
// NAVEGAÇÃO ENTRE ABAS
// =====================================================================
document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));

    btn.classList.add("active");
    const targetId = btn.getAttribute("data-tab");
    document.getElementById(targetId).classList.add("active");
    document.getElementById("page-title").textContent = btn.textContent.trim();
  });
});

// Relógio em Tempo Real no Topo
function updateClock() {
  const now = new Date();
  const formatted = now.toLocaleString("pt-BR", {
    weekday: "long",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  document.getElementById("realtime-clock").textContent = `Percepção Temporal Ativa: ${formatted}`;
}
setInterval(updateClock, 1000);
updateClock();

// =====================================================================
// TELEMETRIA EM TEMPO REAL (VRAM RTX 4050, RAM, OLLAMA, SQLITE)
// =====================================================================
async function fetchTelemetry() {
  try {
    const res = await fetch("/api/telemetry");
    const data = await res.json();

    // Atualiza estado do Botão de Emergência Offline
    applyOfflineVisualState(data.strict_offline_mode);

    // GPU RTX 4050
    const gpu = data.gpu;
    document.getElementById("gpu-temp").textContent = `${gpu.temperature_c}°C | ${gpu.power_draw_w}W`;
    document.getElementById("vram-numbers").textContent = `${gpu.vram_used_mb} / ${gpu.vram_total_mb} MiB (${gpu.vram_percent}%)`;
    const vramBar = document.getElementById("vram-bar");
    vramBar.style.width = `${Math.min(100, gpu.vram_percent)}%`;
    if (gpu.vram_percent > 85) {
      vramBar.classList.add("progress-warn");
    } else {
      vramBar.classList.remove("progress-warn");
    }
    document.getElementById("vram-details").textContent =
      `VRAM Alocada pelo Ollama: ${gpu.ollama_vram_mb} MiB | Livre: ${gpu.vram_free_mb} MiB | Uso GPU: ${gpu.gpu_utilization_pct}%`;

    // RAM e SSD
    const ram = data.ram;
    document.getElementById("ram-pct").textContent = `${ram.percent}%`;
    document.getElementById("ram-numbers").textContent = `${ram.used_gb} / ${ram.total_gb} GB`;
    document.getElementById("ram-bar").style.width = `${Math.min(100, ram.percent)}%`;
    document.getElementById("disk-details").textContent =
      `SSD Livre: ${data.disk.free_gb} GB de ${data.disk.total_gb} GB (${data.disk.percent}% usado)`;

    // Status Ollama
    const badgeOllama = document.getElementById("badge-ollama");
    if (data.ollama.online) {
      badgeOllama.textContent = `🟢 Ollama Online (${data.ollama.reasoning_model})`;
    } else {
      badgeOllama.textContent = "🔴 Ollama Offline";
    }

    const modelsList = document.getElementById("ollama-models-list");
    if (!data.ollama.loaded_models || data.ollama.loaded_models.length === 0) {
      modelsList.innerHTML = `<div class="muted">Nenhum modelo alocado na VRAM neste instante (aguardando inferência, keep_alive=5m).</div>`;
    } else {
      modelsList.innerHTML = data.ollama.loaded_models
        .map(
          (m) => `
          <div class="model-item">
            <div>
              <strong>${m.name}</strong>
              <div class="muted">Tamanho total: ${m.size_mb} MiB</div>
            </div>
            <span class="tag">VRAM: ${m.vram_mb} MiB (${m.gpu_offload_pct}% GPU)</span>
          </div>
        `
        )
        .join("");
    }

    // Contagens do Banco SQLite
    const dbGrid = document.getElementById("db-stats-grid");
    const counts = data.database_counts || {};
    dbGrid.innerHTML = Object.entries(counts)
      .map(
        ([table, count]) => `
        <div class="db-stat-box">
          <strong>${count}</strong>
          <span>${table}</span>
        </div>
      `
      )
      .join("");
  } catch (err) {
    console.error("Erro ao buscar telemetria:", err);
  }
}

document.getElementById("btn-refresh-telemetry").addEventListener("click", fetchTelemetry);
setInterval(fetchTelemetry, 3000);

// =====================================================================
// CARREGAMENTO DE CONFIGURAÇÃO INICIAL
// =====================================================================
async function loadConfig() {
  const res = await fetch("/api/config");
  const cfg = await res.json();

  applyOfflineVisualState(cfg.strict_offline_mode);
  document.getElementById("input-vault-path").value = cfg.obsidian_vault_path || "";
  document.getElementById("input-code-dirs").value = cfg.allowed_code_dirs || "";
  document.getElementById("textarea-persona").value = cfg.persona_markdown || "";

  const cred = cfg.credentials_status || {};
  document.getElementById("discord-badge").textContent = cred.discord_configured
    ? `Configurado (${cred.discord_token_masked})`
    : "Não configurado";
  document.getElementById("input-discord-guild").value = cred.discord_guild_id || "";
  document.getElementById("google-badge").textContent = cred.google_configured
    ? "Configurado"
    : "Não configurado";
  document.getElementById("input-google-id").value = cred.google_client_id || "";
  document.getElementById("input-wpp-port").value = cred.whatsapp_bridge_port || "3001";
}

// =====================================================================
// BOTÃO DE EMERGÊNCIA: MODO ESTRITAMENTE OFFLINE
// =====================================================================
function applyOfflineVisualState(isStrictOffline) {
  strictOfflineState = Boolean(isStrictOffline);
  const box = document.getElementById("emergency-box");
  const label = document.getElementById("offline-label");
  const btn = document.getElementById("btn-emergency-offline");

  if (strictOfflineState) {
    box.classList.add("strict-active");
    label.textContent = "[LOCK] MODO ESTRITAMENTE OFFLINE";
    btn.textContent = "[ONLINE] RESTAURAR MODO HÍBRIDO";
  } else {
    box.classList.remove("strict-active");
    label.textContent = "[OK] MODO HÍBRIDO ATIVO";
    btn.textContent = "[!] ATIVAR KILL-SWITCH OFFLINE";
  }
}

document.getElementById("btn-emergency-offline").addEventListener("click", async () => {
  const nextState = !strictOfflineState;
  const res = await fetch("/api/offline-mode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ strict_offline_mode: nextState }),
  });
  const data = await res.json();
  applyOfflineVisualState(data.strict_offline_mode);
});

// =====================================================================
// SELETOR VISUAL DE PASTAS E SALVAMENTO DE DIRETÓRIOS
// =====================================================================
async function openFolderBrowser(targetType, initialPath = "~") {
  currentBrowserTarget = targetType;
  const modal = document.getElementById("folder-browser-modal");
  modal.classList.remove("hidden");
  await navigateBrowser(initialPath);
}

async function navigateBrowser(pathStr) {
  const res = await fetch(`/api/browse-folders?base_path=${encodeURIComponent(pathStr)}`);
  const data = await res.json();
  currentBrowserPath = data.current_path;
  currentParentPath = data.parent_path;

  document.getElementById("browser-current-path").textContent = currentBrowserPath;
  const listEl = document.getElementById("browser-folder-list");
  listEl.innerHTML = data.folders
    .map(
      (f) =>
        `<div class="folder-item" data-path="${f.path}">📁 ${f.name}</div>`
    )
    .join("");

  listEl.querySelectorAll(".folder-item").forEach((item) => {
    item.addEventListener("click", () => navigateBrowser(item.getAttribute("data-path")));
  });
}

document.getElementById("btn-browse-vault").addEventListener("click", () => {
  openFolderBrowser("vault", document.getElementById("input-vault-path").value || "~");
});

document.getElementById("btn-browse-code").addEventListener("click", () => {
  openFolderBrowser("code", "~");
});

document.getElementById("btn-browser-up").addEventListener("click", () => {
  navigateBrowser(currentParentPath);
});

document.getElementById("btn-browser-close").addEventListener("click", () => {
  document.getElementById("folder-browser-modal").classList.add("hidden");
});

document.getElementById("btn-browser-select").addEventListener("click", () => {
  if (currentBrowserTarget === "vault") {
    document.getElementById("input-vault-path").value = currentBrowserPath;
  } else {
    const input = document.getElementById("input-code-dirs");
    const existing = input.value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!existing.includes(currentBrowserPath)) {
      existing.push(currentBrowserPath);
    }
    input.value = existing.join(",");
  }
  document.getElementById("folder-browser-modal").classList.add("hidden");
});

document.getElementById("btn-save-directories").addEventListener("click", async () => {
  const vaultPath = document.getElementById("input-vault-path").value.trim();
  const codeDirs = document.getElementById("input-code-dirs").value.trim();
  const feedback = document.getElementById("dir-save-feedback");

  const res = await fetch("/api/directories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      obsidian_vault_path: vaultPath,
      allowed_code_dirs: codeDirs,
    }),
  });
  if (res.ok) {
    feedback.textContent = "✅ Diretórios salvos e validados!";
    setTimeout(() => (feedback.textContent = ""), 3500);
  }
});

// =====================================================================
// CREDENCIAIS E RENDERIZADOR DE QR CODE DETERMINÍSTICO EM CANVAS
// =====================================================================
document.getElementById("btn-save-credentials").addEventListener("click", async () => {
  const payload = {
    discord_bot_token: document.getElementById("input-discord-token").value,
    discord_guild_id: document.getElementById("input-discord-guild").value,
    google_client_id: document.getElementById("input-google-id").value,
    google_client_secret: document.getElementById("input-google-secret").value,
    whatsapp_bridge_port: document.getElementById("input-wpp-port").value,
  };
  const res = await fetch("/api/credentials", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res.ok) {
    document.getElementById("input-discord-token").value = "";
    document.getElementById("input-google-secret").value = "";
    const fb = document.getElementById("cred-save-feedback");
    fb.textContent = "✅ Credenciais gravadas no .env local!";
    loadConfig();
    setTimeout(() => (fb.textContent = ""), 3500);
  }
});

function drawMatrixQR(canvas, seedText) {
  const ctx = canvas.getContext("2d");
  const size = 21;
  const cell = Math.floor(canvas.width / size);
  ctx.fillStyle = "#030c05";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#39ff14";

  function drawFinder(ox, oy) {
    for (let y = 0; y < 7; y++) {
      for (let x = 0; x < 7; x++) {
        if (
          x === 0 || x === 6 || y === 0 || y === 6 ||
          (x >= 2 && x <= 4 && y >= 2 && y <= 4)
        ) {
          ctx.fillRect((ox + x) * cell, (oy + y) * cell, cell, cell);
        }
      }
    }
  }
  drawFinder(0, 0);
  drawFinder(size - 7, 0);
  drawFinder(0, size - 7);

  let hash = 2166136261;
  for (let i = 0; i < seedText.length; i++) {
    hash ^= seedText.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const inFinder =
        (x < 8 && y < 8) ||
        (x >= size - 8 && y < 8) ||
        (x < 8 && y >= size - 8);
      if (inFinder) continue;
      hash ^= (x * 31 + y * 17) & 0xff;
      hash = Math.imul(hash, 16777619);
      if (Math.abs(hash) % 2 === 0) {
        ctx.fillRect(x * cell, y * cell, cell, cell);
      }
    }
  }
}

document.getElementById("btn-generate-qr").addEventListener("click", async () => {
  const statusEl = document.getElementById("wpp-qr-status");
  const res = await fetch("/api/whatsapp/qr");
  if (!res.ok) {
    const err = await res.json();
    statusEl.textContent = `⛔ ${err.detail}`;
    return;
  }
  const data = await res.json();
  drawMatrixQR(document.getElementById("qr-canvas"), data.qr_payload + Date.now());
  statusEl.textContent = `Status: ${data.status} (Bridge Porta ${data.bridge_port})`;
});

async function loadWorkersLogs() {
  try {
    const res = await fetch("/api/workers/logs");
    const data = await res.json();
    const listEl = document.getElementById("workers-logs-list");
    if (!data.logs || data.logs.length === 0) {
      listEl.innerHTML = `<div class="muted">Nenhum ciclo de sincronização registrado ainda.</div>`;
      return;
    }
    listEl.innerHTML = data.logs
      .slice(0, 6)
      .map(
        (l) => `
        <div class="model-item">
          <div>
            <strong>[${l.worker_name.toUpperCase()}]</strong> ${l.details}
            <div class="muted">Executado em: ${l.executed_at}</div>
          </div>
          <span class="tag">${l.status} (${l.items_synced})</span>
        </div>
      `
      )
      .join("");
  } catch (e) {
    console.error("Erro ao carregar logs dos workers:", e);
  }
}

document.getElementById("btn-run-sync-all").addEventListener("click", async () => {
  const btn = document.getElementById("btn-run-sync-all");
  btn.textContent = "[SINCRONIZANDO...]";
  await fetch("/api/workers/sync", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target: "all" }),
  });
  btn.textContent = "[SINCRONIZAR TODOS AGORA]";
  await loadWorkersLogs();
  await fetchTelemetry();
});

// =====================================================================
// PERSONA E RE-INDEXAÇÃO RAG
// =====================================================================
document.getElementById("btn-save-persona").addEventListener("click", async () => {
  const content = document.getElementById("textarea-persona").value;
  const res = await fetch("/api/persona", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (res.ok) {
    const fb = document.getElementById("persona-save-feedback");
    fb.textContent = "✅ Personalidade atualizada no Obsidian!";
    setTimeout(() => (fb.textContent = ""), 3500);
  }
});

document.getElementById("btn-reindex-rag").addEventListener("click", async () => {
  const btn = document.getElementById("btn-reindex-rag");
  btn.textContent = "Indexando...";
  const res = await fetch("/api/rag/reindex", { method: "POST" });
  const data = await res.json();
  btn.textContent = `✅ ${data.chunks_indexed || 0} Chunks`;
  setTimeout(() => (btn.textContent = "Re-indexar Vault (RAG)"), 3000);
});

// =====================================================================
// CONSOLE DE CHAT RÁPIDO COM A IA
// =====================================================================
async function sendQuickChat() {
  const input = document.getElementById("input-chat-prompt");
  const prompt = input.value.trim();
  if (!prompt) return;

  const log = document.getElementById("chat-log");
  log.innerHTML += `<div class="chat-bubble user">${prompt}</div>`;
  input.value = "";
  log.scrollTop = log.scrollHeight;

  const res = await fetch("/api/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
  const data = await res.json();
  const toolsSummary =
    data.tools_called && data.tools_called.length
      ? `\n\n[Tools executadas: ${data.tools_called.map((t) => t.tool).join(", ")}]`
      : "";
  log.innerHTML += `<div class="chat-bubble assistant">${data.reply}${toolsSummary}</div>`;
  log.scrollTop = log.scrollHeight;
  fetchTelemetry();
}

document.getElementById("btn-send-chat").addEventListener("click", sendQuickChat);
document.getElementById("input-chat-prompt").addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendQuickChat();
});

// Inicialização
loadConfig();
fetchTelemetry();
loadWorkersLogs();
drawMatrixQR(document.getElementById("qr-canvas"), "INIT_HYBRID_AI");
