// PhonePe Merchant UPI Helpdesk RAG - Frontend Script

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const tabChatBtn = document.getElementById("tabChatBtn");
  const tabLedgerBtn = document.getElementById("tabLedgerBtn");
  const tabPoliciesBtn = document.getElementById("tabPoliciesBtn");
  
  const chatPanel = document.getElementById("chatPanel");
  const ledgerPanel = document.getElementById("ledgerPanel");
  const policiesPanel = document.getElementById("policiesPanel");

  const chatContainer = document.getElementById("chatContainer");
  const chatForm = document.getElementById("chatForm");
  const userInput = document.getElementById("userInput");
  const ledgerCount = document.getElementById("ledgerCount");
  const ledgerTableBody = document.getElementById("ledgerTableBody");
  const ledgerSearchInput = document.getElementById("ledgerSearchInput");
  const policiesGrid = document.getElementById("policiesGrid");

  const openSettingsBtn = document.getElementById("openSettingsBtn");
  const apiKeyBtnText = document.getElementById("apiKeyBtnText");
  const closeSettingsBtn = document.getElementById("closeSettingsBtn");
  const settingsModal = document.getElementById("settingsModal");
  const geminiApiKeyInput = document.getElementById("geminiApiKeyInput");
  const saveKeyBtn = document.getElementById("saveKeyBtn");
  const clearKeyBtn = document.getElementById("clearKeyBtn");
  const keyStatusIndicator = document.getElementById("keyStatusIndicator");
  const playChimeBtn = document.getElementById("playChimeBtn");
  const soundboxStatusBtn = document.getElementById("soundboxStatusBtn");
  const sidebarChimeBtn = document.getElementById("sidebarChimeBtn");
  const viewAllLedgerBtn = document.getElementById("viewAllLedgerBtn");

  const sidebarTxnList = document.getElementById("sidebarTxnList");
  const statSuccessCount = document.getElementById("statSuccessCount");
  const statPendingCount = document.getElementById("statPendingCount");
  const statFailedCount = document.getElementById("statFailedCount");

  let allTransactions = [];
  let allPolicies = [];

  // Tab Switching
  function switchTab(activeTab, activePanel) {
    [tabChatBtn, tabLedgerBtn, tabPoliciesBtn].forEach(b => b.classList.remove("active"));
    [chatPanel, ledgerPanel, policiesPanel].forEach(p => p.classList.remove("active"));

    activeTab.classList.add("active");
    activePanel.classList.add("active");
  }

  tabChatBtn.addEventListener("click", () => switchTab(tabChatBtn, chatPanel));
  tabLedgerBtn.addEventListener("click", () => {
    switchTab(tabLedgerBtn, ledgerPanel);
    loadTransactions();
  });
  tabPoliciesBtn.addEventListener("click", () => {
    switchTab(tabPoliciesBtn, policiesPanel);
    loadPolicies();
  });

  if (viewAllLedgerBtn) {
    viewAllLedgerBtn.addEventListener("click", () => {
      switchTab(tabLedgerBtn, ledgerPanel);
      loadTransactions();
    });
  }

  // Settings Modal & API Key Management
  function updateKeyIndicator() {
    const key = localStorage.getItem("gemini_api_key");
    if (key && key.trim().length > 10) {
      keyStatusIndicator.textContent = "✓ Gemini API Key active (Stored locally in browser)";
      keyStatusIndicator.classList.add("configured");
      if (apiKeyBtnText) apiKeyBtnText.textContent = "Gemini Connected";
      openSettingsBtn.style.borderColor = "var(--sport-volt)";
      openSettingsBtn.style.color = "var(--sport-volt)";
    } else {
      keyStatusIndicator.textContent = "No API key configured. Using local policy synthesizer.";
      keyStatusIndicator.classList.remove("configured");
      if (apiKeyBtnText) apiKeyBtnText.textContent = "Gemini API Key";
      openSettingsBtn.style.borderColor = "var(--border-sport)";
      openSettingsBtn.style.color = "var(--text-secondary)";
    }
  }

  updateKeyIndicator();

  openSettingsBtn.addEventListener("click", () => {
    geminiApiKeyInput.value = localStorage.getItem("gemini_api_key") || "";
    settingsModal.classList.add("active");
  });

  closeSettingsBtn.addEventListener("click", () => {
    settingsModal.classList.remove("active");
  });

  settingsModal.addEventListener("click", (e) => {
    if (e.target === settingsModal) {
      settingsModal.classList.remove("active");
    }
  });

  saveKeyBtn.addEventListener("click", () => {
    const val = geminiApiKeyInput.value.trim();
    if (val) {
      localStorage.setItem("gemini_api_key", val);
    } else {
      localStorage.removeItem("gemini_api_key");
    }
    updateKeyIndicator();
    settingsModal.classList.remove("active");
  });

  clearKeyBtn.addEventListener("click", () => {
    localStorage.removeItem("gemini_api_key");
    geminiApiKeyInput.value = "";
    updateKeyIndicator();
    settingsModal.classList.remove("active");
  });

  // SmartSpeaker Chime via Web Audio API
  function playSoundboxChime() {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioContext();
      
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gain = ctx.createGain();

      osc1.type = "sine";
      osc2.type = "triangle";

      osc1.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc1.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15); // A5
      
      osc2.frequency.setValueAtTime(440, ctx.currentTime);
      osc2.frequency.exponentialRampToValueAtTime(659.25, ctx.currentTime + 0.15);

      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.6);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(ctx.destination);

      osc1.start();
      osc2.start();
      osc1.stop(ctx.currentTime + 0.6);
      osc2.stop(ctx.currentTime + 0.6);
    } catch (e) {
      console.log("AudioContext chime not permitted without user gesture");
    }
  }

  playChimeBtn.addEventListener("click", playSoundboxChime);
  soundboxStatusBtn.addEventListener("click", playSoundboxChime);
  if (sidebarChimeBtn) {
    sidebarChimeBtn.addEventListener("click", playSoundboxChime);
  }

  // Interactive Scenario Cards Click
  document.querySelectorAll(".scenario-card").forEach(card => {
    card.addEventListener("click", () => {
      const prompt = card.getAttribute("data-prompt");
      if (prompt) {
        userInput.value = prompt;
        userInput.focus();
        chatForm.dispatchEvent(new Event("submit"));
      }
    });
  });

  // Chat Submission
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = userInput.value.trim();
    if (!query) return;

    // Append User Message
    appendMessage("user", query);
    userInput.value = "";

    // Show Typing Indicator
    const typingId = appendTypingIndicator();

    // Call API
    try {
      const apiKey = localStorage.getItem("gemini_api_key") || "";
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          api_key: apiKey
        })
      });

      const data = await res.json();
      removeTypingIndicator(typingId);

      if (data.status === "success") {
        appendBotMessage(data);
      } else {
        appendMessage("bot", "⚠️ An error occurred processing your request. Please try again.");
      }
    } catch (err) {
      removeTypingIndicator(typingId);
      appendMessage("bot", `⚠️ Could not reach server: ${err.message}`);
    }
  });

  function appendMessage(sender, text) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${sender}`;

    if (sender === "user") {
      msgDiv.innerHTML = `<div class="message-bubble">${escapeHtml(text)}</div>`;
    } else {
      msgDiv.innerHTML = `
        <div class="bot-avatar">PP</div>
        <div class="message-bubble">${marked.parse(text)}</div>
      `;
    }

    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  function appendBotMessage(data) {
    const msgDiv = document.createElement("div");
    msgDiv.className = "message bot";

    let matchedTxnHtml = "";
    if (data.matched_transaction) {
      const txn = data.matched_transaction;
      matchedTxnHtml = `
        <div class="matched-txn-banner">
          <div class="matched-txn-title">
            <span>⚡ Terminal Match Found</span>
            <span class="badge badge-${txn.status}">${txn.status}</span>
          </div>
          <div class="matched-txn-details">
            <div><span>Txn ID:</span> <strong>${txn.transaction_id}</strong></div>
            <div><span>UTR:</span> <strong>${txn.utr_number}</strong></div>
            <div><span>Amount:</span> <strong>₹${txn.amount}</strong></div>
            <div><span>Time:</span> <strong>${txn.timestamp}</strong></div>
            <div><span>Customer:</span> <strong>${txn.customer_name_or_vpa}</strong></div>
            <div><span>Speaker Alerted:</span> <strong>${txn.soundbox_announced === 'YES' ? '🔔 Yes' : '🔕 No'}</strong></div>
          </div>
        </div>
      `;
    }

    let citationsHtml = "";
    if (data.citations && data.citations.length > 0) {
      const cards = data.citations.map(c => `
        <div class="citation-item">
          <div class="citation-meta">
            <span class="citation-source">${escapeHtml(c.publisher)} (${c.doc_id})</span>
            <span class="citation-score">Relevance: ${c.relevance_score || 'High'}</span>
          </div>
          <div class="citation-title">${escapeHtml(c.title)}</div>
          <a class="citation-url" href="${c.source_url}" target="_blank" rel="noopener">↗ Policy Link</a>
        </div>
      `).join("");

      citationsHtml = `
        <div class="citations-tray">
          <div class="citations-header">Official Policy Citations:</div>
          <div class="citation-cards">${cards}</div>
        </div>
      `;
    }

    const metaFooter = `
      <div class="meta-footer">
        ${escapeHtml(data.model_used)}
      </div>
    `;

    msgDiv.innerHTML = `
      <div class="bot-avatar">PP</div>
      <div class="message-bubble">
        ${matchedTxnHtml}
        ${marked.parse(data.answer)}
        ${citationsHtml}
        ${metaFooter}
      </div>
    `;

    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  function appendTypingIndicator() {
    const id = "typing-" + Date.now();
    const msgDiv = document.createElement("div");
    msgDiv.className = "message bot";
    msgDiv.id = id;
    msgDiv.innerHTML = `
      <div class="bot-avatar">PP</div>
      <div class="message-bubble">
        <div class="typing-dots">
          <span></span><span></span><span></span>
        </div>
      </div>
    `;
    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return id;
  }

  function removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  // Transaction Ledger Functions
  async function loadTransactions() {
    try {
      const res = await fetch("/api/transactions");
      const data = await res.json();
      allTransactions = data.transactions || [];
      ledgerCount.textContent = allTransactions.length;
      
      // Update stats and sidebar
      updateSidebarStats(allTransactions);
      renderSidebarTransactions(allTransactions.slice(0, 6));

      // Render full table if on ledger tab
      renderTransactions(allTransactions);
    } catch (e) {
      console.error("Failed to load transactions", e);
    }
  }

  function updateSidebarStats(txns) {
    let success = 0, pending = 0, failed = 0;
    txns.forEach(t => {
      if (t.status === "SUCCESS") success++;
      else if (t.status === "PENDING") pending++;
      else failed++;
    });
    if (statSuccessCount) statSuccessCount.textContent = success;
    if (statPendingCount) statPendingCount.textContent = pending;
    if (statFailedCount) statFailedCount.textContent = failed;
  }

  function renderSidebarTransactions(txns) {
    if (!sidebarTxnList) return;
    sidebarTxnList.innerHTML = "";

    txns.forEach(t => {
      const card = document.createElement("div");
      card.className = "sidebar-txn-card";
      card.innerHTML = `
        <div class="sidebar-txn-top">
          <span class="sidebar-txn-amt">₹${t.amount}</span>
          <span class="badge badge-${t.status}">${t.status}</span>
        </div>
        <div class="sidebar-txn-mid">
          <span class="sidebar-txn-vpa" title="${t.customer_name_or_vpa}">${t.customer_name_or_vpa}</span>
          <span class="sidebar-txn-utr">${t.utr_number ? t.utr_number.slice(-6) : ''}</span>
        </div>
        <button class="sidebar-txn-btn" data-utr="${t.utr_number}" data-amt="${t.amount}" data-status="${t.status}">
          <span>Ask Helpdesk</span> ⚡
        </button>
      `;
      sidebarTxnList.appendChild(card);
    });

    // Attach click handlers to sidebar cards
    document.querySelectorAll(".sidebar-txn-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const utr = btn.getAttribute("data-utr");
        const amt = btn.getAttribute("data-amt");
        const status = btn.getAttribute("data-status");
        
        userInput.value = `Regarding transaction UTR ${utr} for ₹${amt} with status ${status}, what should I do at the counter?`;
        userInput.focus();
        chatForm.dispatchEvent(new Event("submit"));
      });
    });
  }

  function renderTransactions(txns) {
    ledgerTableBody.innerHTML = "";
    if (txns.length === 0) {
      ledgerTableBody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 2rem; color:var(--text-muted);">No matching transactions found.</td></tr>`;
      return;
    }

    txns.forEach(t => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong style="color:var(--text-primary);">${t.transaction_id}</strong></td>
        <td><code>${t.utr_number}</code></td>
        <td>${t.timestamp}</td>
        <td>${t.customer_name_or_vpa}</td>
        <td><strong style="color:var(--sport-blue);">₹${t.amount}</strong></td>
        <td><span class="badge badge-${t.status}">${t.status}</span></td>
        <td>${t.soundbox_announced === 'YES' ? '🔔 Yes' : '🔕 No'}</td>
        <td style="font-size:0.78rem; max-width:220px; color:var(--text-secondary);">${t.failure_reason || 'None'}</td>
        <td>
          <button class="btn-ask-row" data-utr="${t.utr_number}" data-amt="${t.amount}" data-status="${t.status}">
            Ask Helpdesk
          </button>
        </td>
      `;
      ledgerTableBody.appendChild(tr);
    });

    // Attach row ask buttons
    document.querySelectorAll(".btn-ask-row").forEach(btn => {
      btn.addEventListener("click", () => {
        const utr = btn.getAttribute("data-utr");
        const amt = btn.getAttribute("data-amt");
        const status = btn.getAttribute("data-status");
        
        switchTab(tabChatBtn, chatPanel);
        userInput.value = `Regarding transaction UTR ${utr} for ₹${amt} with status ${status}, what should I do at the counter?`;
        chatForm.dispatchEvent(new Event("submit"));
      });
    });
  }

  // Ledger Filter
  ledgerSearchInput.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase().trim();
    if (!q) {
      renderTransactions(allTransactions);
      return;
    }
    const filtered = allTransactions.filter(t => {
      return (
        t.transaction_id.toLowerCase().includes(q) ||
        t.utr_number.toLowerCase().includes(q) ||
        t.customer_name_or_vpa.toLowerCase().includes(q) ||
        t.amount.toString().includes(q) ||
        t.status.toLowerCase().includes(q)
      );
    });
    renderTransactions(filtered);
  });

  // Policies Functions
  async function loadPolicies() {
    if (allPolicies.length > 0) return;
    try {
      const res = await fetch("/api/policies");
      const data = await res.json();
      allPolicies = data.policies || [];
      renderPolicies(allPolicies);
    } catch (e) {
      console.error("Failed to load policies", e);
    }
  }

  function renderPolicies(policies) {
    policiesGrid.innerHTML = "";
    policies.forEach(p => {
      const card = document.createElement("div");
      card.className = "policy-card";
      
      const stepsList = (p.action_steps || []).map(s => `<li>${escapeHtml(s)}</li>`).join("");

      card.innerHTML = `
        <div class="policy-badge">${escapeHtml(p.publisher)} • ${escapeHtml(p.issue_category.toUpperCase())}</div>
        <h4>${escapeHtml(p.title)}</h4>
        <p>${escapeHtml(p.chunk_text)}</p>
        <div class="policy-steps">
          <strong>Mandated Action Checklist:</strong>
          <ul>${stepsList}</ul>
        </div>
        <div style="font-size:0.75rem; margin-top: auto;">
          <a href="${p.source_url}" target="_blank" rel="noopener" style="color:var(--sport-blue); font-weight:600; text-decoration:none;">
            Official Reference (${p.doc_id}) &rarr;
          </a>
        </div>
      `;
      policiesGrid.appendChild(card);
    });
  }

  function escapeHtml(text) {
    if (!text) return "";
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Preload initial transactions
  loadTransactions();
});
