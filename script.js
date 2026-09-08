/* ================================================================
   SOVEREIGN WORKBENCH — Script (ChatGPT-style)
   Chat interface with sidebar history, inline pipeline progress,
   separate pipeline/audit views, and HITL approval flow.
   ================================================================ */

document.addEventListener('DOMContentLoaded', function () {

  // ── CONSTANTS ──────────────────────────────────────────────

  var PIPELINE_STEPS = [
    { id:'rate-limit',   label:'Rate Limit Check',      desc:'Token bucket verification',       duration:350,  readout:function(){return '12 / 60 requests consumed this window';} },
    { id:'prompt-safety',label:'Prompt Safety Check',    desc:'Injection & adversarial scan',    duration:850,  readout:function(){return '0 injection patterns detected \u2014 CLEAR';} },
    { id:'rbac',         label:'RBAC Verification',      desc:'Role-capability authorization',   duration:420,  readout:function(){ return 'Clearance: ' + (state.user ? state.user.clearanceName : 'Guest') + ' \u2714 Role: ' + (state.user ? state.user.role : 'None'); } },
    { id:'doc-retrieval',label:'Document Retrieval',     desc:'Role-filtered manual lookup',     duration:1200, readout:function(){return '3 docs matched \u2192 1 selected: BOILER-102 Manual \u00A74.2';} },
    { id:'vision',       label:'Vision Extraction',      desc:'Multimodal gauge reading',        duration:1500, conditional:true, readout:function(){return 'Gauge: 6.4 bar inlet | Confidence: 0.96';} },
    { id:'calculation',  label:'Sandboxed Calculation',  desc:'Isolated compute environment',    duration:900,  readout:function(){return '\u0394p = 3.8 bar | Range: 2.0\u20135.0 bar | NORMAL';} },
    { id:'approval',     label:'Human Approval (HITL)',  desc:'Sensitive action authorization',  duration:null, interactive:true, readout:null },
    { id:'audit-write',  label:'Audit Log Write',        desc:'Hash-chain entry commitment',     duration:220,  readout:null }
  ];

  var SEED_QUERY = 'Fetch boiler-102 log, read gauge photo, calculate pressure drop, open release valve if abnormal.';

  // Pre-seeded past chats with realistic agentic thinking timeline
  var SEED_CHATS = [
    {
      id: 'seed-1',
      title: 'Pump-201 Vibration Analysis',
      group: 'Yesterday',
      messages: [
        { role:'user', text:'Run vibration analysis on pump-201 and check if it exceeds threshold.', time:'Yesterday, 14:32' },
        {
          role:'assistant',
          text:'Vibration analysis complete for pump-201. Peak amplitude: 4.2 mm/s (threshold: 7.1 mm/s). All readings within normal parameters. No maintenance action required. Full report logged to audit chain.',
          time:'Yesterday, 14:33',
          thinking: {
            state: 'complete',
            title: 'Thought process \u00B7 7 defense checks verified (1.4s)',
            badge: 'COMPLETE',
            collapsed: false,
            steps: [
              { id:'seed-mem', icon:'memory', label:'Read memory', crumb:'Areas \u203A Sovereign Ai Workbench', detail:'Project \u2014 "Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs"', status:'passed' },
              { id:'seed-tools', icon:'tools', label:'Loaded tools', detail:'Vibration spectrum analyzer, ISO 10816-3 rules engine, RBAC clearance checker', status:'passed' },
              { id:'seed-t1', icon:'task', label:'Added task: Check rate limits & RBAC clearance (pump-201)', status:'passed' },
              { id:'seed-t2', icon:'task', label:'Added task: Retrieve vibration accelerometer telemetry', status:'passed' },
              { id:'seed-t3', icon:'task', label:'Added task: Compute peak vibration velocity RMS', status:'passed' },
              { id:'seed-t4', icon:'task', label:'Started task: Vibration spectrum verification', status:'passed' },
              { id:'seed-calc', icon:'calculation', label:'Sandboxed Calculation', detail:'Peak velocity RMS: 4.2 mm/s \u2014 ISO 10816-3 Category 2 (Zone A: 0\u20137.1 mm/s)', status:'passed' },
              { id:'seed-audit', icon:'audit-write', label:'Audit Log Write', detail:'Committed to tamper-proof block #0089 (SHA-256 verified)', status:'passed' }
            ]
          }
        }
      ]
    },
    {
      id: 'seed-2',
      title: 'Cooling System Diagnostics',
      group: 'Yesterday',
      messages: [
        { role:'user', text:'Check coolant flow rate and temperature delta on cooling loop C3.', time:'Yesterday, 09:15' },
        {
          role:'assistant',
          text:'Cooling loop C3 diagnostics:\n\u2022 Flow rate: 12.4 L/min (nominal: 10\u201315 L/min) \u2714\n\u2022 Inlet temp: 28.3\u00b0C, Outlet temp: 41.7\u00b0C\n\u2022 \u0394T = 13.4\u00b0C (within expected range)\n\nNo anomalies detected. System operating within design parameters.',
          time:'Yesterday, 09:16',
          thinking: {
            state: 'complete',
            title: 'Thought process \u00B7 7 defense checks verified (1.6s)',
            badge: 'COMPLETE',
            collapsed: false,
            steps: [
              { id:'seed2-mem', icon:'memory', label:'Read memory', crumb:'Areas \u203A Sovereign Ai Workbench', detail:'Thermal safety envelope \u2014 Cooling loop C3 specifications & sensor telemetry', status:'passed' },
              { id:'seed2-tools', icon:'tools', label:'Loaded tools', detail:'Flow meter decoder, thermal delta calculator, RBAC validator', status:'passed' },
              { id:'seed2-t1', icon:'task', label:'Added task: Verify clearance for auxiliary cooling loop C3', status:'passed' },
              { id:'seed2-t2', icon:'task', label:'Added task: Retrieve flow rate and thermocouple logs', status:'passed' },
              { id:'seed2-t3', icon:'task', label:'Started task: Thermal differential calculation', status:'passed' },
              { id:'seed2-calc', icon:'calculation', label:'Sandboxed Calculation', detail:'Inlet: 28.3\u00b0C, Outlet: 41.7\u00b0C, \u0394T = 13.4\u00b0C \u2014 NORMAL', status:'passed' },
              { id:'seed2-audit', icon:'audit-write', label:'Audit Log Write', detail:'Committed to tamper-proof block #0104 (SHA-256 verified)', status:'passed' }
            ]
          }
        }
      ]
    },
    {
      id: 'seed-3',
      title: 'Monthly Compliance Report',
      group: 'Previous 7 days',
      messages: [
        { role:'user', text:'Generate the monthly compliance summary for September inspection cycle.', time:'Sep 1, 10:00' },
        {
          role:'assistant',
          text:'Monthly compliance summary generated:\n\u2022 Total queries processed: 847\n\u2022 Pipeline blocks: 12 (3 RBAC, 7 rate-limit, 2 prompt-safety)\n\u2022 HITL approvals: 23 (all resolved within SLA)\n\u2022 Audit chain integrity: VERIFIED\n\u2022 Zero unauthorized access attempts\n\nFull report exported to audit log entry #0142.',
          time:'Sep 1, 10:02',
          thinking: {
            state: 'complete',
            title: 'Thought process \u00B7 7 defense checks verified (2.1s)',
            badge: 'COMPLETE',
            collapsed: false,
            steps: [
              { id:'seed3-mem', icon:'memory', label:'Read memory', crumb:'Areas \u203A Sovereign Ai Workbench', detail:'Auditor clearance & ISO 27001 / IEC 62443 industrial compliance framework', status:'passed' },
              { id:'seed3-tools', icon:'tools', label:'Loaded tools', detail:'Merkle hash tree verifier, compliance aggregator, RBAC policy inspector', status:'passed' },
              { id:'seed3-t1', icon:'task', label:'Added task: Verify hash chain integrity across all historical blocks', status:'passed' },
              { id:'seed3-t2', icon:'task', label:'Added task: Aggregate pipeline defense triggers and block statistics', status:'passed' },
              { id:'seed3-t3', icon:'task', label:'Started task: Compliance summary generation', status:'passed' },
              { id:'seed3-calc', icon:'calculation', label:'Calculated Aggregations', detail:'847 queries, 12 blocks, 23 HITL approvals, 0 chain discrepancies', status:'passed' },
              { id:'seed3-audit', icon:'audit-write', label:'Audit Log Write', detail:'Exported monthly compliance summary block #0142', status:'passed' }
            ]
          }
        }
      ]
    }
  ];


  // ── STATE ──────────────────────────────────────────────────

  var DEMO_USERS = {
    suketu: {
      name: 'Suketu',
      fullName: 'Suketu Patel',
      email: 'suketu.2005@gmail.com',
      tier: 'Pro',
      avatar: 'SM',
      clearanceLevel: 3,
      clearanceName: 'Level 3 (Chief Safety Auditor \u00B7 All Systems)',
      role: 'Chief_Safety_Auditor'
    },
    morrison: {
      name: 'J. Morrison',
      fullName: 'John Morrison',
      email: 'j.morrison@plant.internal',
      tier: 'Engineer',
      avatar: 'JM',
      clearanceLevel: 1,
      clearanceName: 'Level 1 (boiler-102 only)',
      role: 'Maintenance_Engineer'
    },
    vance: {
      name: 'Dr. Vance',
      fullName: 'Dr. Elena Vance',
      email: 'elena.vance@plant.internal',
      tier: 'Specialist',
      avatar: 'EV',
      clearanceLevel: 2,
      clearanceName: 'Level 2 (Turbines, Boilers, Pumps)',
      role: 'Systems_Specialist'
    }
  };

  var state = {
    theme: null,
    currentView: 'chat',
    sidebarOpen: true,
    pipelineRunning: false,
    imageAttached: false,
    imageName: '',
    auditLog: [],
    lastHash: '0'.repeat(64),
    chats: [],           // { id, title, group, messages:[] }
    activeChatId: null,
    chatCounter: 0,
    user: DEMO_USERS.suketu
  };


  // ── ELEMENT REFS ───────────────────────────────────────────

  var $ = function(id) { return document.getElementById(id); };
  var els = {
    sidebar:        $('sidebar'),
    sidebarOverlay: $('sidebar-overlay'),
    btnOpenSidebar: $('btn-open-sidebar'),
    btnCloseSidebar:$('btn-close-sidebar'),
    btnNewChat:     $('btn-new-chat'),
    chatList:       $('chat-list'),
    themeToggle:    $('theme-toggle'),
    tabChat:        $('tab-chat'),
    tabPipeline:    $('tab-pipeline'),
    tabAudit:       $('tab-audit'),
    chatView:       $('chat-view'),
    pipelineView:   $('pipeline-view'),
    auditView:      $('audit-view'),
    chatScroll:     $('chat-scroll'),
    chatMessages:   $('chat-messages'),
    btnScrollBottom:$('btn-scroll-bottom'),
    chatInput:      $('chat-input'),
    imageAttach:    $('image-attach'),
    labelAttach:    $('label-attach'),
    imagePreview:   $('image-preview'),
    previewThumb:   $('preview-thumb'),
    previewName:    $('preview-name'),
    btnRemoveImg:   $('btn-remove-img'),
    btnDemo:        $('btn-demo'),
    btnSend:        $('btn-send'),
    pipelineSteps:  $('pipeline-steps'),
    pipelineStatus: $('pipeline-status'),
    pipelineEmpty:  $('pipeline-empty'),
    auditEntries:   $('audit-entries'),
    auditCount:     $('audit-count'),
    approvalDialog: $('approval-dialog'),
    approvalAction: $('approval-action'),
    approvalTarget: $('approval-target'),
    approvalRequestor:$('approval-requestor'),
    approvalContext:$('approval-context'),
    approvalAuthority:$('approval-authority'),
    btnApprove:     $('btn-approve'),
    btnReject:      $('btn-reject'),

    // Sidebar User & Menu Elements
    userMenuContainer: $('user-menu-container'),
    userDropdownMenu:  $('user-dropdown-menu'),
    btnUserProfile:    $('btn-user-profile'),
    btnSidebarLogin:   $('btn-sidebar-login'),
    menuUserEmail:     $('menu-user-email'),
    menuUserClearance: $('menu-user-clearance'),
    menuCurrentLang:   $('menu-current-lang'),
    userPillAvatar:    $('user-pill-avatar'),
    userPillName:      $('user-pill-name'),
    userPillTier:      $('user-pill-tier'),

    // Menu Trigger Buttons
    btnMenuSettings:   $('btn-menu-settings'),
    btnMenuLanguage:   $('btn-menu-language'),
    btnMenuHelp:       $('btn-menu-help'),
    btnMenuClearances: $('btn-menu-clearances'),
    btnMenuTools:      $('btn-menu-tools'),
    btnMenuAcademy:    $('btn-menu-academy'),
    btnMenuAbout:      $('btn-menu-about'),
    btnMenuLogout:     $('btn-menu-logout'),

    // Dialogs
    authDialog:        $('auth-dialog'),
    settingsDialog:    $('settings-dialog'),
    academyDialog:     $('academy-dialog'),
    clearancesDialog:  $('clearances-dialog'),
    helpDialog:        $('help-dialog'),
    toolsDialog:       $('tools-dialog'),
    aboutDialog:       $('about-dialog'),

    // Modal Close Buttons
    btnCloseAuth:       $('btn-close-auth'),
    btnCloseSettings:   $('btn-close-settings'),
    btnCloseAcademy:    $('btn-close-academy'),
    btnCloseClearances: $('btn-close-clearances'),
    btnCloseHelp:       $('btn-close-help'),
    btnCloseTools:      $('btn-close-tools'),
    btnCloseAbout:      $('btn-close-about'),

    // Auth Form Elements
    authTabSignin:     $('auth-tab-signin'),
    authTabSignup:     $('auth-tab-signup'),
    formSignin:        $('form-signin'),
    formSignup:        $('form-signup'),
    signinEmail:       $('signin-email'),
    signinPassword:    $('signin-password'),
    signupName:        $('signup-name'),
    signupEmail:       $('signup-email'),
    signupPassword:    $('signup-password'),
    signupClearance:   $('signup-clearance'),
    btnSigninSubmit:   $('btn-signin-submit'),
    btnSignupSubmit:   $('btn-signup-submit'),

    // Settings Controls
    settingThemeSelect: $('setting-theme-select'),
    settingLangSelect:  $('setting-lang-select'),
    settingModelSelect: $('setting-model-select'),
    btnSaveSettings:    $('btn-save-settings'),

    // Tools Elements
    btnExportAuditJson: $('btn-export-audit-json'),

    // Clearances Elements
    clrAvatar:         $('clr-avatar'),
    clrName:           $('clr-name'),
    clrEmail:          $('clr-email'),
    clrRole:           $('clr-role'),
    clrTurbineStatus:  $('clr-turbine-status'),
    clrReactorStatus:  $('clr-reactor-status')
  };


  // ── UTILITIES ──────────────────────────────────────────────

  function esc(s) {
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(s));
    return d.innerHTML;
  }

  function timeNow() {
    var d = new Date();
    return d.toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' });
  }

  function isMobile() { return window.innerWidth <= 768; }


  // ── THEME ──────────────────────────────────────────────────

  function applyTheme() {
    if (state.theme) document.documentElement.setAttribute('data-theme', state.theme);
    else document.documentElement.removeAttribute('data-theme');
  }
  function toggleTheme() {
    state.theme = !state.theme ? 'dark' : state.theme === 'dark' ? 'light' : null;
    applyTheme();
  }


  // ── USER AUTH & PROFILE MANAGEMENT ─────────────────────────

  function updateUserUI() {
    if (state.user) {
      if (els.btnUserProfile) els.btnUserProfile.hidden = false;
      if (els.btnSidebarLogin) els.btnSidebarLogin.hidden = true;
      if (els.userPillAvatar) els.userPillAvatar.textContent = state.user.avatar || 'OP';
      if (els.userPillName) els.userPillName.textContent = state.user.name;
      if (els.userPillTier) els.userPillTier.textContent = state.user.tier;
      if (els.menuUserEmail) els.menuUserEmail.textContent = state.user.email;
      if (els.menuUserClearance) els.menuUserClearance.textContent = 'Clearance: ' + state.user.clearanceName;

      // Update clearances modal
      if (els.clrAvatar) els.clrAvatar.textContent = state.user.avatar || 'OP';
      if (els.clrName) els.clrName.textContent = state.user.fullName || state.user.name;
      if (els.clrEmail) els.clrEmail.textContent = state.user.email;
      if (els.clrRole) els.clrRole.textContent = 'Clearance: ' + state.user.clearanceName;

      if (els.clrTurbineStatus) {
        if (state.user.clearanceLevel >= 2) {
          els.clrTurbineStatus.innerHTML = '<span class="resp-value--passed">AUTHORIZED &check;</span>';
        } else {
          els.clrTurbineStatus.innerHTML = '<span class="resp-value--blocked">DENIED (Tier 2 Req)</span>';
        }
      }
      if (els.clrReactorStatus) {
        if (state.user.clearanceLevel >= 3) {
          els.clrReactorStatus.innerHTML = '<span class="resp-value--passed">AUTHORIZED &check;</span>';
        } else {
          els.clrReactorStatus.innerHTML = '<span class="resp-value--blocked">DENIED (Tier 3 Req)</span>';
        }
      }
    } else {
      if (els.btnUserProfile) els.btnUserProfile.hidden = true;
      if (els.btnSidebarLogin) els.btnSidebarLogin.hidden = false;
      closeUserMenu();
    }
  }

  function toggleUserMenu(e) {
    if (e) e.stopPropagation();
    if (!els.userDropdownMenu) return;
    var isHidden = els.userDropdownMenu.hidden;
    if (isHidden) {
      els.userDropdownMenu.hidden = false;
      if (els.btnUserProfile) els.btnUserProfile.setAttribute('aria-expanded', 'true');
    } else {
      closeUserMenu();
    }
  }

  function closeUserMenu() {
    if (els.userDropdownMenu) els.userDropdownMenu.hidden = true;
    if (els.btnUserProfile) els.btnUserProfile.setAttribute('aria-expanded', 'false');
  }

  function openModal(dlg) {
    if (!dlg) return;
    closeUserMenu();
    dlg.showModal();
  }

  function closeModal(dlg) {
    if (!dlg) return;
    dlg.close();
  }

  function loginUser(userProfile) {
    state.user = userProfile;
    updateUserUI();
    closeModal(els.authDialog);
    closeUserMenu();
    addAuditEntry('OPERATOR_AUTH', 'Operator authenticated \u2014 ' + userProfile.email + ' [' + userProfile.clearanceName + ']');
  }

  function logoutUser() {
    var prevEmail = state.user ? state.user.email : 'Operator';
    state.user = null;
    updateUserUI();
    closeUserMenu();
    addAuditEntry('OPERATOR_LOGOUT', 'Operator ' + prevEmail + ' logged out of console');
    openModal(els.authDialog);
  }

  function exportAuditJson() {
    var exportData = {
      exportTimestamp: new Date().toISOString(),
      system: 'Sovereign Workbench Air-Gapped Console',
      genesisHash: '0000000000000000000000000000000000000000000000000000000000000000',
      currentHeadHash: state.lastHash,
      entryCount: state.auditLog.length,
      operator: state.user ? {
        name: state.user.fullName || state.user.name,
        email: state.user.email,
        clearance: state.user.clearanceName
      } : 'Unauthenticated',
      ledger: state.auditLog
    };
    var dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportData, null, 2));
    var dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', dataStr);
    dlAnchor.setAttribute('download', 'sovereign-workbench-audit-chain-' + Date.now() + '.json');
    document.body.appendChild(dlAnchor);
    dlAnchor.click();
    dlAnchor.remove();
    addAuditEntry('AUDIT_EXPORT', 'Cryptographic audit ledger exported as JSON by ' + (state.user ? state.user.email : 'System'));
  }


  // ── SIDEBAR ────────────────────────────────────────────────

  function openSidebar() {
    state.sidebarOpen = true;
    if (isMobile()) {
      els.sidebar.classList.add('open');
      els.sidebar.classList.remove('collapsed');
      els.sidebarOverlay.hidden = false;
    } else {
      els.sidebar.classList.remove('collapsed');
    }
  }

  function closeSidebar() {
    state.sidebarOpen = false;
    if (isMobile()) {
      els.sidebar.classList.remove('open');
      els.sidebar.classList.add('collapsed');
      els.sidebarOverlay.hidden = true;
    } else {
      els.sidebar.classList.add('collapsed');
    }
  }

  function toggleSidebar() {
    if (state.sidebarOpen) closeSidebar();
    else openSidebar();
  }

  function renderChatList() {
    var html = '';
    var groups = {};

    // Group chats
    state.chats.forEach(function(c) {
      var g = c.group || 'Today';
      if (!groups[g]) groups[g] = [];
      groups[g].push(c);
    });

    var order = ['Today', 'Yesterday', 'Previous 7 days'];
    Object.keys(groups).forEach(function(g) {
      if (order.indexOf(g) === -1) order.push(g);
    });

    order.forEach(function(g) {
      if (!groups[g]) return;
      html += '<div class="chat-group-label">' + esc(g) + '</div>';
      groups[g].forEach(function(c) {
        html += '<button type="button" class="chat-item' + (c.id === state.activeChatId ? ' active' : '') + '" data-chat-id="' + c.id + '">' + esc(c.title) + '</button>';
      });
    });

    els.chatList.innerHTML = html;
  }


  // ── VIEW SWITCHING ─────────────────────────────────────────

  function switchView(view) {
    state.currentView = view;
    var views = { chat: els.chatView, pipeline: els.pipelineView, audit: els.auditView };
    var tabs  = { chat: els.tabChat, pipeline: els.tabPipeline, audit: els.tabAudit };

    Object.keys(views).forEach(function(k) {
      views[k].classList.toggle('view--active', k === view);
      tabs[k].classList.toggle('active', k === view);
    });

    if (view === 'audit') renderAuditLog();
  }


  // ── CHAT MANAGEMENT ────────────────────────────────────────

  function createChat() {
    state.chatCounter++;
    var chat = {
      id: 'chat-' + Date.now() + '-' + state.chatCounter,
      title: 'New Chat',
      group: 'Today',
      messages: []
    };
    state.chats.unshift(chat);
    state.activeChatId = chat.id;
    // Clear any file preview and draft text from previous chat
    removeImage();
    els.chatInput.value = '';
    autoResize();
    updateSendState();
    renderChatList();
    renderChatMessages();
    switchView('chat');
    els.chatInput.focus();
    if (isMobile()) closeSidebar();
    return chat;
  }

  function switchChat(chatId) {
    if (state.activeChatId !== chatId) {
      removeImage();
      els.chatInput.value = '';
      autoResize();
      updateSendState();
    }
    state.activeChatId = chatId;
    renderChatList();
    renderChatMessages();
    switchView('chat');
    if (isMobile()) closeSidebar();
  }

  function getActiveChat() {
    return state.chats.find(function(c) { return c.id === state.activeChatId; });
  }

  function addMessage(role, content, extra) {
    var chat = getActiveChat();
    if (!chat) return null;
    var msg = { role: role, text: content, time: timeNow() };
    if (extra) {
      if (extra.image) msg.image = extra.image;
      if (extra.html) msg.html = extra.html;
      if (extra.thinking) msg.thinking = extra.thinking;
    }
    chat.messages.push(msg);
    // Update title from first user message
    if (role === 'user' && chat.title === 'New Chat') {
      chat.title = content.length > 36 ? content.substring(0, 36) + '\u2026' : content;
      renderChatList();
    }
    renderChatMessages();
    scrollToBottom();
    return msg;
  }

  function renderChatMessages() {
    var chat = getActiveChat();
    if (!chat || chat.messages.length === 0) {
      // Show welcome screen
      els.chatMessages.innerHTML =
        '<div class="chat-welcome">' +
          '<svg class="chat-welcome-logo" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.3">' +
            '<rect x="4" y="4" width="40" height="40" rx="2"/><line x1="24" y1="4" x2="24" y2="44"/><line x1="4" y1="24" x2="44" y2="24"/><circle cx="24" cy="24" r="10"/>' +
          '</svg>' +
          '<h2>Sovereign Workbench</h2>' +
          '<p>Confidential on-premise AI console for industrial maintenance operations. All queries pass through a verified defense pipeline with hash-chain audit logging.</p>' +
        '</div>';
      return;
    }

    var html = '';
    chat.messages.forEach(function(m, idx) {
      var isUser = m.role === 'user';
      var avatarLabel = isUser ? 'ME' : 'SW';
      html += '<div class="message message--' + m.role + '">';
      html += '<div class="msg-avatar">' + avatarLabel + '</div>';
      html += '<div class="msg-body">';
      html += '<div class="msg-sender">' + (isUser ? 'You' : 'Sovereign Workbench') + '</div>';
      html += '<div class="msg-content">';

      if (m.image) {
        html += '<div class="msg-image-badge"><svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1" y="3" width="14" height="10" rx="1"/><circle cx="5" cy="7" r="1.5"/></svg> ' + esc(m.image) + '</div>';
      }

      if (m.thinking) {
        html += renderThinkingBlock(m.thinking, idx);
      }

      if (m.html) {
        html += m.html;
      } else if (m.text) {
        // Render text with line breaks
        var paras = m.text.split('\n');
        paras.forEach(function(p) { html += '<p>' + esc(p) + '</p>'; });
      }

      html += '</div>';
      html += '<div class="msg-time">' + esc(m.time) + '</div>';
      html += '</div></div>';
    });

    els.chatMessages.innerHTML = html;
  }

  function renderThinkingBlock(t, msgIdx) {
    var st = t.state || 'complete';
    var isRunning = st === 'running';
    var collapsedClass = t.collapsed ? ' collapsed' : '';
    var idAttr = isRunning ? ' id="active-thinking-block"' : '';
    var timelineId = isRunning ? ' id="inline-timeline"' : '';

    var html = '<div class="thinking-block' + collapsedClass + '"' + idAttr + ' data-state="' + st + '" data-msg-idx="' + (msgIdx !== undefined ? msgIdx : '') + '">';
    html += '<button type="button" class="thinking-toggle" aria-label="Toggle thinking process">';
    html += '<div class="thinking-toggle-left">';
    html += '<svg class="thinking-chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 6l4 4 4-4"/></svg>';
    html += '<span class="thinking-toggle-title">' + esc(t.title || 'Thinking Process') + '</span>';
    html += '</div>';
    html += '<span class="thinking-toggle-badge">' + esc(t.badge || (st === 'complete' ? 'PASSED' : st.toUpperCase())) + '</span>';
    html += '</button>';

    html += '<div class="thinking-content">';
    html += '<div class="thinking-timeline"' + timelineId + '>';
    if (t.steps && t.steps.length) {
      t.steps.forEach(function(s) {
        html += renderStepHtml(s);
      });
    }
    html += '</div></div></div>';
    return html;
  }

  function renderStepHtml(s) {
    var iconSvg = STEP_ICONS[s.icon] || STEP_ICONS[s.id] || STEP_ICONS['task'] || STEP_ICONS['audit-write'];
    var status = s.status || 'passed';
    var html = '<div class="thinking-step" data-step="' + esc(s.id || s.label) + '" data-s="' + status + '">';
    html += '<div class="thinking-step-track">';
    html += '<div class="thinking-step-icon">' + iconSvg + '</div>';
    html += '<div class="thinking-step-line"></div>';
    html += '</div>';
    html += '<div class="thinking-step-body">';
    html += '<div class="thinking-step-header">';
    html += '<div class="thinking-step-label">' + esc(s.label) + '</div>';
    if (s.crumb) {
      html += '<div class="thinking-step-crumb">' + esc(s.crumb) + '</div>';
    }
    html += '</div>';
    if (s.detail) {
      html += '<div class="thinking-step-detail">' + esc(s.detail) + '</div>';
    }
    html += '</div></div>';
    return html;
  }

  function scrollToBottom() {
    setTimeout(function() {
      els.chatScroll.scrollTop = els.chatScroll.scrollHeight;
    }, 50);
  }


  // ── IMAGE ATTACHMENT ───────────────────────────────────────

  function handleImageSelect(e) {
    var file = e.target.files && e.target.files[0];
    if (!file) return;
    state.imageAttached = true;
    state.imageName = file.name;
    els.previewName.textContent = file.name;
    var reader = new FileReader();
    reader.onload = function(ev) {
      els.previewThumb.innerHTML = '<img src="' + ev.target.result + '" alt="Preview">';
    };
    reader.readAsDataURL(file);
    els.imagePreview.hidden = false;
    updateSendState();
  }

  function removeImage() {
    state.imageAttached = false;
    state.imageName = '';
    els.imageAttach.value = '';
    els.previewThumb.innerHTML = '';
    els.imagePreview.hidden = true;
    updateSendState();
  }

  function simulateImageAttach() {
    state.imageAttached = true;
    state.imageName = 'boiler-102-gauge.jpg';
    els.previewName.textContent = state.imageName;
    // Draw gauge
    var canvas = document.createElement('canvas');
    canvas.width = 80; canvas.height = 80;
    var ctx = canvas.getContext('2d');
    ctx.fillStyle = '#1a2029'; ctx.fillRect(0, 0, 80, 80);
    ctx.strokeStyle = '#4FC3C9'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(40, 44, 28, Math.PI, 0); ctx.stroke();
    ctx.strokeStyle = '#F85149'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(40, 44);
    var angle = Math.PI + (6.4 / 10) * Math.PI;
    ctx.lineTo(40 + Math.cos(angle) * 22, 44 + Math.sin(angle) * 22); ctx.stroke();
    ctx.fillStyle = '#4FC3C9'; ctx.font = '9px monospace'; ctx.textAlign = 'center';
    ctx.fillText('6.4 bar', 40, 72);
    els.previewThumb.innerHTML = '<img src="' + canvas.toDataURL() + '" alt="Gauge">';
    els.imagePreview.hidden = false;
  }

  function updateSendState() {
    var hasText = els.chatInput.value.trim().length > 0;
    els.btnSend.disabled = !hasText || state.pipelineRunning;
  }


  // ── AUTO-RESIZE TEXTAREA ──────────────────────────────────

  function autoResize() {
    els.chatInput.style.height = 'auto';
    els.chatInput.style.height = Math.min(els.chatInput.scrollHeight, 160) + 'px';
  }


  // ── HASH GENERATION ────────────────────────────────────────

  function sha256(msg) {
    var enc = new TextEncoder();
    return crypto.subtle.digest('SHA-256', enc.encode(msg)).then(function(buf) {
      return Array.from(new Uint8Array(buf)).map(function(b) { return b.toString(16).padStart(2,'0'); }).join('');
    });
  }

  function addAuditEntry(eventType, detail) {
    var payload = state.lastHash + '|' + eventType + ':' + detail + '|' + Date.now();
    return sha256(payload).then(function(hash) {
      var entry = {
        index: state.auditLog.length,
        timestamp: new Date().toISOString(),
        event: eventType,
        detail: detail,
        hash: hash,
        prevHash: state.lastHash
      };
      state.lastHash = hash;
      state.auditLog.push(entry);
      els.auditCount.textContent = state.auditLog.length + ' entries';
      return entry;
    });
  }

  function renderAuditLog() {
    if (state.auditLog.length === 0) {
      els.auditEntries.innerHTML = '<div class="audit-empty">No audit entries yet. Execute a query to generate log entries.</div>';
      return;
    }
    var html = '';
    for (var i = state.auditLog.length - 1; i >= 0; i--) {
      var e = state.auditLog[i];
      html += '<div class="audit-entry">' +
        '<div class="audit-entry-idx">#' + String(e.index).padStart(4,'0') + '</div>' +
        '<div class="audit-entry-body">' +
          '<div class="audit-entry-event">' + esc(e.event) + '</div>' +
          '<div class="audit-entry-detail">' + esc(e.detail) + '</div>' +
          '<div class="audit-entry-detail" style="margin-top:2px;opacity:0.7">' + e.timestamp + '</div>' +
        '</div>' +
        '<div class="audit-entry-hashes">' +
          '<span class="hash-label">hash </span>' + e.hash.substring(0,16) + '\u2026<br>' +
          '<span class="hash-label">prev </span>' + e.prevHash.substring(0,16) + '\u2026' +
        '</div>' +
      '</div>';
    }
    els.auditEntries.innerHTML = html;
  }


  // ── PIPELINE (full view) ──────────────────────────────────

  function buildPipelineDOM(hasImage) {
    els.pipelineEmpty.hidden = true;
    // Clear old steps
    var old = els.pipelineSteps.querySelectorAll('.pipeline-step');
    for (var i = 0; i < old.length; i++) old[i].remove();

    var html = '';
    PIPELINE_STEPS.forEach(function(step) {
      if (step.conditional && !hasImage) return;
      html +=
        '<div class="pipeline-step" id="step-' + step.id + '" data-status="idle">' +
          '<div class="step-track"><div class="step-dot"></div><div class="step-connector"></div></div>' +
          '<div class="step-content">' +
            '<div class="step-header">' +
              '<span class="step-label">' + esc(step.label) + '</span>' +
              '<span class="step-badge" data-badge="idle">IDLE</span>' +
            '</div>' +
            '<div class="step-meta">' +
              '<span class="step-desc">' + esc(step.desc) + '</span>' +
              '<span class="step-timing"></span>' +
            '</div>' +
            '<div class="step-readout"></div>' +
          '</div>' +
        '</div>';
    });
    els.pipelineSteps.insertAdjacentHTML('afterbegin', html);
  }

  function updateStepUI(stepId, status, readout, elapsed) {
    var el = document.getElementById('step-' + stepId);
    if (!el) return;
    el.setAttribute('data-status', status);
    var badge = el.querySelector('.step-badge');
    var map = { idle:'IDLE', processing:'PROCESSING', passed:'PASSED', blocked:'BLOCKED', awaiting:'AWAITING', skipped:'SKIPPED', approved:'APPROVED', rejected:'REJECTED' };
    badge.textContent = map[status] || status.toUpperCase();
    badge.setAttribute('data-badge', status);
    if (readout) el.querySelector('.step-readout').textContent = readout;
    if (typeof elapsed === 'number') el.querySelector('.step-timing').textContent = elapsed + 'ms';
  }

  function setPipelineLabel(s) {
    els.pipelineStatus.textContent = s;
    els.pipelineStatus.setAttribute('data-state',
      s === 'IDLE' ? 'idle' : s === 'COMPLETE' ? 'complete' : s === 'BLOCKED' ? 'blocked' : 'running');
  }


  // ── STEP ICONS (inline SVG for each pipeline step) ──────────

  // ── STEP ICONS (inline SVG matching agentic execution screenshot) ──

  var STEP_ICONS = {
    'memory':        '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2.5 8a5.5 5.5 0 1 1 1.6 3.9"/><path d="M2.5 12V8H6.5"/><polyline points="8 5 8 8 10 10"/></svg>',
    'tools':         '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="6.5" cy="6.5" r="4"/><line x1="9.5" y1="9.5" x2="13.5" y2="13.5"/></svg>',
    'task':          '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 3.5h8M5 8h8M5 12.5h8"/><polyline points="1.5 3.5 2.5 4.5 4 2.5"/><circle cx="2.5" cy="8" r="1"/><circle cx="2.5" cy="12.5" r="1"/></svg>',
    'start':         '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="5 3 13 8 5 13 5 3"/></svg>',
    'terminal':      '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1.5" y="2.5" width="13" height="11" rx="1.5"/><polyline points="4.5 6 7 8 4.5 10"/><line x1="8.5" y1="10" x2="11.5" y2="10"/></svg>',
    'code':          '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="5 4 2 8 5 12"/><polyline points="11 4 14 8 11 12"/></svg>',
    'rate-limit':    '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6"/><polyline points="8 4.5 8 8 10.5 9.5"/></svg>',
    'prompt-safety': '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 1.5L2.5 4.5v3.5c0 3.5 2.4 6.8 5.5 7.5 3.1-.7 5.5-4 5.5-7.5V4.5L8 1.5Z"/></svg>',
    'rbac':          '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="4" y="7" width="8" height="6.5" rx="1"/><path d="M5.5 7V4.5a2.5 2.5 0 015 0V7"/></svg>',
    'doc-retrieval': '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9.5 2H4a1 1 0 00-1 1v10a1 1 0 001 1h8a1 1 0 001-1V5.5L9.5 2Z"/><polyline points="9.5 2 9.5 5.5 13 5.5"/><line x1="5.5" y1="9" x2="10.5" y2="9"/><line x1="5.5" y1="11.5" x2="8.5" y2="11.5"/></svg>',
    'vision':        '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8s-2.5 4.5-6.5 4.5S1.5 8 1.5 8Z"/><circle cx="8" cy="8" r="2"/></svg>',
    'calculation':   '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2.5" y="2" width="11" height="12" rx="1.5"/><line x1="5" y1="5.5" x2="11" y2="5.5"/><line x1="5" y1="8.5" x2="7" y2="8.5"/><line x1="9" y1="8.5" x2="11" y2="8.5"/><line x1="5" y1="11" x2="7" y2="11"/><line x1="9" y1="11" x2="11" y2="11"/></svg>',
    'approval':      '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="5.5" r="2.5"/><path d="M3.5 13.5c0-2.5 2-4.5 4.5-4.5s4.5 2 4.5 4.5"/></svg>',
    'audit-write':   '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="10" height="10" rx="1.5"/><polyline points="5.5 8 7 9.5 10.5 6"/></svg>'
  };

  // ── LIVE STEP UPDATES (in-place appending for smooth animation) ──

  function addLiveStep(chat, msg, step) {
    if (!msg || !msg.thinking) return;
    var existingIdx = -1;
    for (var i = 0; i < msg.thinking.steps.length; i++) {
      if (msg.thinking.steps[i].id === step.id) {
        existingIdx = i;
        break;
      }
    }
    if (existingIdx >= 0) {
      msg.thinking.steps[existingIdx].status = step.status;
      if (step.detail) msg.thinking.steps[existingIdx].detail = step.detail;
      var tl = document.getElementById('inline-timeline');
      if (tl) {
        var el = tl.querySelector('[data-step="' + step.id + '"]');
        if (el) {
          el.setAttribute('data-s', step.status);
          var d = el.querySelector('.thinking-step-detail');
          if (d && step.detail) d.textContent = step.detail;
        }
      }
    } else {
      msg.thinking.steps.push(step);
      var tl = document.getElementById('inline-timeline');
      if (tl) {
        tl.insertAdjacentHTML('beforeend', renderStepHtml(step));
        scrollToBottom();
      }
    }
  }

  function updateLiveStep(stepId, status, detail) {
    var chat = getActiveChat();
    if (!chat || !chat.messages.length) return;
    var last = chat.messages[chat.messages.length - 1];
    if (!last || !last.thinking) return;

    for (var i = 0; i < last.thinking.steps.length; i++) {
      if (last.thinking.steps[i].id === stepId) {
        last.thinking.steps[i].status = status;
        if (detail) last.thinking.steps[i].detail = detail;
        break;
      }
    }

    var tl = document.getElementById('inline-timeline');
    if (tl) {
      var el = tl.querySelector('[data-step="' + stepId + '"]');
      if (el) {
        el.setAttribute('data-s', status);
        if (detail) {
          var d = el.querySelector('.thinking-step-detail');
          if (d) d.textContent = detail;
        }
      }
    }
  }


  // ── SUBMIT / PIPELINE EXECUTION ────────────────────────────

  function handleSubmit() {
    var query = els.chatInput.value.trim();
    if (!query || state.pipelineRunning) return;

    if (!state.user) {
      openModal(els.authDialog);
      return;
    }

    if (!getActiveChat()) createChat();
    var chat = getActiveChat();

    var imgExtra = state.imageAttached ? { image: state.imageName } : {};
    addMessage('user', query, imgExtra);

    els.chatInput.value = '';
    autoResize();
    var hasImage = state.imageAttached;
    removeImage();
    updateSendState();

    state.pipelineRunning = true;
    updateSendState();

    buildPipelineDOM(hasImage);
    setPipelineLabel('RUNNING');

    // Create assistant message with running thinking block
    var assistantMsg = addMessage('assistant', '', {
      thinking: {
        state: 'running',
        title: 'Thinking through defense pipeline\u2026',
        badge: 'RUNNING',
        collapsed: false,
        steps: []
      }
    });

    var startTime = performance.now();

    var steps = PIPELINE_STEPS.filter(function(s) { return !s.conditional || hasImage; });

    // Dynamic RBAC authorization evaluation
    var isBlocked = false;
    var blockReason = '';
    var reqClearance = '';

    if (/reactor/i.test(query)) {
      if (state.user.clearanceLevel < 3) {
        isBlocked = true;
        blockReason = 'reactor-core-aux requires Level 3 clearance (Chief Safety Auditor)';
        reqClearance = 'Level 3';
      }
    } else if (/turbine|compressor/i.test(query)) {
      if (state.user.clearanceLevel < 2) {
        isBlocked = true;
        blockReason = 'turbine-gen-4 requires Level 2+ clearance (Systems Specialist)';
        reqClearance = 'Level 2';
      }
    }

    var blockedAt = isBlocked ? 'rbac' : null;
    var needsApproval = /valve|shutdown|override|emergency|open|close/i.test(query);

    // Initial agentic context sequence (matching Antigravity activity feed)
    var setupSequence = [
      {
        delay: 60,
        step: { id:'mem-read', icon:'memory', label:'Read memory', crumb:'Areas \u203A Sovereign Ai Workbench', detail:'Project \u2014 "Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs"', status:'passed' }
      },
      {
        delay: 120,
        step: { id:'tool-load', icon:'tools', label:'Loaded tools', detail:'8 defense security layers & cryptographic loggers initialized', status:'passed' }
      },
      {
        delay: 80,
        step: { id:'task-rate', icon:'task', label:'Added task: Check rate limits & prompt safety', status:'passed' }
      },
      {
        delay: 80,
        step: { id:'task-rbac', icon:'task', label:'Added task: Verify operator RBAC clearance (' + state.user.name + ' \u00B7 ' + state.user.clearanceName + ')', status:'passed' }
      },
      {
        delay: 80,
        step: { id:'task-doc', icon:'task', label:'Added task: Retrieve equipment manual (\u00A74.2)', status:'passed' }
      }
    ];

    if (hasImage) {
      setupSequence.push({
        delay: 80,
        step: { id:'task-vis', icon:'task', label:'Added task: Multimodal gauge inspection (vision)', status:'passed' }
      });
    }

    setupSequence.push({
      delay: 80,
      step: { id:'task-calc', icon:'task', label:'Added task: Sandboxed calculation of pressure drop', status:'passed' }
    });

    if (needsApproval) {
      setupSequence.push({
        delay: 80,
        step: { id:'task-auth', icon:'task', label:'Added task: Human authorization check (HITL)', status:'passed' }
      });
    }

    setupSequence.push({
      delay: 100,
      step: { id:'task-start', icon:'start', label:'Started task: Defense verification & execution', status:'passed' }
    });

    function runSetup(i) {
      if (i >= setupSequence.length) {
        addAuditEntry('QUERY_SUBMITTED', 'Query: "' + query.substring(0,80) + '"').then(function() {
          executeSteps(steps, 0, blockedAt, blockReason, reqClearance, needsApproval, query, hasImage, startTime, assistantMsg);
        });
        return;
      }
      var item = setupSequence[i];
      setTimeout(function() {
        addLiveStep(chat, assistantMsg, item.step);
        runSetup(i + 1);
      }, item.delay);
    }

    runSetup(0);
  }

  function executeSteps(steps, idx, blockedAt, blockReason, reqClearance, needsApproval, query, hasImage, startTime, assistantMsg) {
    var chat = getActiveChat();
    if (idx >= steps.length) {
      finishPipeline(query, hasImage, startTime, assistantMsg);
      return;
    }

    var step = steps[idx];

    // Already past the block point — skip
    if (blockedAt && idx > getStepIdx(steps, blockedAt)) {
      updateStepUI(step.id, 'skipped');
      addLiveStep(chat, assistantMsg, { id: step.id, icon: step.id, label: step.label, status: 'skipped', detail: 'Skipped \u2014 execution halted' });
      executeSteps(steps, idx+1, blockedAt, blockReason, reqClearance, needsApproval, query, hasImage, startTime, assistantMsg);
      return;
    }

    // Start processing
    updateStepUI(step.id, 'processing');
    addLiveStep(chat, assistantMsg, { id: step.id, icon: step.id, label: step.label, status: 'processing', detail: step.desc });

    if (step.interactive) {
      if (!needsApproval) {
        updateStepUI(step.id, 'skipped', 'No sensitive actions \u2014 skipped');
        updateLiveStep(step.id, 'passed', 'No sensitive actions \u2014 auto-cleared');
        executeSteps(steps, idx+1, blockedAt, blockReason, reqClearance, needsApproval, query, hasImage, startTime, assistantMsg);
        return;
      }

      updateStepUI(step.id, 'awaiting');
      updateLiveStep(step.id, 'processing', 'Awaiting Human-in-the-Loop authorization\u2026');
      setPipelineLabel('AWAITING_APPROVAL');

      openApprovalModal({
        action: 'open_release_valve',
        target: 'boiler-102 (release valve #4)',
        requestor: 'AI Agent (Maintenance Subsystem)',
        context: '\u0394p = 3.8 bar exceeds normal threshold. Recommended action: Open release valve to prevent over-pressurization.',
        authority: 'Senior_Engineer (HITL Required)',
        onResolve: function(approved) {
          if (approved) {
            updateStepUI(step.id, 'passed', 'Authorized by Senior_Engineer');
            updateLiveStep(step.id, 'passed', 'Authorized by Senior_Engineer (HITL)');
            setPipelineLabel('RUNNING');
            addAuditEntry('HITL_APPROVAL', 'open_release_valve approved by Senior_Engineer').then(function() {
              executeSteps(steps, idx+1, blockedAt, blockReason, reqClearance, needsApproval, query, hasImage, startTime, assistantMsg);
            });
          } else {
            updateStepUI(step.id, 'rejected', 'Rejected by Senior_Engineer');
            updateLiveStep(step.id, 'blocked', 'Rejected by Senior_Engineer');
            setPipelineLabel('BLOCKED');
            addAuditEntry('HITL_REJECTION', 'open_release_valve rejected by Senior_Engineer').then(function(entry) {
              replaceThinkingWithBlocked('Human Approval Denied', {
                'Pipeline halted at': 'Human Approval (HITL)',
                'Reason': 'Action rejected by the approving authority.',
                'Rejected by': 'Senior_Engineer (J. Morrison)'
              }, entry, startTime, assistantMsg);
              state.pipelineRunning = false;
              updateSendState();
            });
          }
        }
      });
      return;
    }

    // Timed step
    var t0 = performance.now();
    setTimeout(function() {
      var elapsed = Math.round(performance.now() - t0);

      if (blockedAt === step.id) {
        updateStepUI(step.id, 'blocked', blockReason || 'Operator lacks required clearance', elapsed);
        updateLiveStep(step.id, 'blocked', blockReason || 'Operator lacks required clearance');
        setPipelineLabel('BLOCKED');
        addAuditEntry('RBAC_BLOCK', 'Query blocked \u2014 ' + (blockReason || 'insufficient clearance') + ' [' + state.user.email + ']').then(function(entry) {
          for (var j = idx+1; j < steps.length; j++) {
            updateStepUI(steps[j].id, 'skipped');
            addLiveStep(chat, assistantMsg, { id: steps[j].id, icon: steps[j].id, label: steps[j].label, status: 'skipped', detail: 'Skipped due to clearance block' });
          }
          replaceThinkingWithBlocked('Authorization Failed \u2014 Insufficient Clearance', {
            'Pipeline halted at': 'RBAC Verification',
            'Reason': blockReason || 'Operator does not have clearance for the requested system.',
            'Required tier': reqClearance || 'Level 2+',
            'Current operator': (state.user.fullName || state.user.name) + ' (' + state.user.clearanceName + ')'
          }, entry, startTime, assistantMsg);
          state.pipelineRunning = false;
          updateSendState();
        });
        return;
      }

      var readout = step.readout ? step.readout() : null;
      updateStepUI(step.id, 'passed', readout, elapsed);
      updateLiveStep(step.id, 'passed', readout);

      addAuditEntry('STEP_PASSED', step.label + ' \u2014 ' + elapsed + 'ms').then(function() {
        executeSteps(steps, idx+1, blockedAt, blockReason, reqClearance, needsApproval, query, hasImage, startTime, assistantMsg);
      });
    }, step.duration || 200);
  }

  function getStepIdx(steps, id) {
    for (var i = 0; i < steps.length; i++) if (steps[i].id === id) return i;
    return -1;
  }

  function finishPipeline(query, hasImage, startTime, assistantMsg) {
    setPipelineLabel('COMPLETE');
    addAuditEntry('QUERY_COMPLETE', 'Full pipeline pass \u2014 response assembled').then(function(entry) {
      updateStepUI('audit-write', 'passed', 'Entry #' + String(entry.index).padStart(4,'0') + ' committed', null);
      addLiveStep(getActiveChat(), assistantMsg, {
        id: 'audit-write',
        icon: 'audit-write',
        label: 'Audit Log Write',
        status: 'passed',
        detail: 'Committed to tamper-proof block #' + String(entry.index).padStart(4,'0') + ' (SHA-256 verified)'
      });
      replaceThinkingWithResponse(entry, hasImage, startTime, assistantMsg);
      state.pipelineRunning = false;
      updateSendState();
    });
  }


  // ── REPLACE THINKING / DISPLAY RESPONSE ────────────────────

  function replaceThinkingWithResponse(auditEntry, hasImage, startTime, assistantMsg) {
    var chat = getActiveChat();
    if (!chat) return;
    var targetMsg = assistantMsg || chat.messages[chat.messages.length - 1];
    if (!targetMsg || targetMsg.role !== 'assistant') return;

    var totalElapsed = ((performance.now() - (startTime || performance.now())) / 1000).toFixed(1);
    var passCount = targetMsg.thinking && targetMsg.thinking.steps ? targetMsg.thinking.steps.length : 8;

    if (targetMsg.thinking) {
      targetMsg.thinking.state = 'complete';
      targetMsg.thinking.title = 'Thought process \u00B7 ' + passCount + ' defense checks verified (' + totalElapsed + 's)';
      targetMsg.thinking.badge = 'COMPLETE';
    }

    var responseText = 'Based on the confidential on-premise analysis of boiler-102, here are the verified results:';

    var blocksHtml = '<div class="msg-response-blocks">';

    // Doc context
    blocksHtml += respBlock('Document Context',
      '<p>Retrieved from: <strong>BOILER-102 Maintenance Manual, Section 4.2</strong></p>' +
      '<p style="margin-top:4px;font-family:var(--font-mono);font-size:11px;color:var(--text-2)">' +
      '"Normal operating pressure range for inlet manifold: 4.0\u20137.0 bar. Pressure drop should not exceed 5.0 bar under standard load."</p>');

    // Vision
    if (hasImage) {
      blocksHtml += respBlock('Vision Analysis',
        '<div class="resp-row"><span class="resp-label">Gauge reading</span><span class="resp-value resp-value--accent">6.4 bar (inlet)</span></div>' +
        '<div class="resp-row"><span class="resp-label">Confidence</span><span class="resp-value">0.96</span></div>' +
        '<div class="resp-row"><span class="resp-label">Assessment</span><span class="resp-value">Within normal range (4.0\u20137.0 bar)</span></div>');
    }

    // Calc
    blocksHtml += respBlock('Calculation Result',
      '<div class="resp-row"><span class="resp-label">Pressure drop</span><span class="resp-value resp-value--accent">3.8 bar</span></div>' +
      '<div class="resp-row"><span class="resp-label">Normal range</span><span class="resp-value">2.0 \u2013 5.0 bar</span></div>' +
      '<div class="resp-row"><span class="resp-label">Status</span><span class="resp-value resp-value--passed">WITHIN NORMAL PARAMETERS \u2714</span></div>');

    // Action
    blocksHtml += respBlock('Action Executed',
      '<div class="resp-row"><span class="resp-label">Action</span><span class="resp-value mono">open_release_valve</span></div>' +
      '<div class="resp-row"><span class="resp-label">Target</span><span class="resp-value mono">boiler-102</span></div>' +
      '<div class="resp-row"><span class="resp-label">Status</span><span class="resp-value resp-value--passed">APPROVED &amp; EXECUTED</span></div>' +
      '<div class="resp-row"><span class="resp-label">Approved by</span><span class="resp-value">Senior_Engineer (J. Morrison)</span></div>');

    // Audit ref
    blocksHtml += '<div class="resp-block resp-block--audit"><div class="resp-block-title">Tamper-Proof Audit Reference</div><div class="resp-block-content">' +
      '<div class="resp-row"><span class="resp-label">Entry</span><span class="resp-value">#' + String(auditEntry.index).padStart(4,'0') + '</span></div>' +
      '<div class="resp-row"><span class="resp-label">Hash</span><span class="audit-hash-inline">' + auditEntry.hash.substring(0,32) + '\u2026</span></div>' +
      '<div class="resp-row"><span class="resp-label">Chain</span><span class="resp-value resp-value--passed">VERIFIED \u2714</span></div>' +
    '</div></div>';

    blocksHtml += '</div>';

    targetMsg.html = '<p>' + esc(responseText) + '</p>' + blocksHtml;
    targetMsg.time = timeNow();
    renderChatMessages();
    scrollToBottom();
  }

  function replaceThinkingWithBlocked(title, details, auditEntry, startTime, assistantMsg) {
    var chat = getActiveChat();
    if (!chat) return;
    var targetMsg = assistantMsg || chat.messages[chat.messages.length - 1];
    if (!targetMsg || targetMsg.role !== 'assistant') return;

    var totalElapsed = ((performance.now() - (startTime || performance.now())) / 1000).toFixed(1);

    if (targetMsg.thinking) {
      targetMsg.thinking.state = 'blocked';
      targetMsg.thinking.title = 'Pipeline Halted \u00B7 ' + title + ' (' + totalElapsed + 's)';
      targetMsg.thinking.badge = 'BLOCKED';
    }

    var html = '<div class="msg-blocked-box">';
    html += '<div class="msg-blocked-title">' + esc(title) + '</div>';
    html += '<dl class="msg-blocked-details">';
    Object.keys(details).forEach(function(k) {
      html += '<dt>' + esc(k) + '</dt><dd>' + esc(details[k]) + '</dd>';
    });
    html += '<dt>Audit entry</dt><dd>#' + String(auditEntry.index).padStart(4,'0') + ' (hash: ' + auditEntry.hash.substring(0,16) + '\u2026)</dd>';
    html += '</dl></div>';

    targetMsg.html = html;
    targetMsg.time = timeNow();
    renderChatMessages();
    scrollToBottom();
  }

  function respBlock(title, content) {
    return '<div class="resp-block"><div class="resp-block-title">' + esc(title) + '</div><div class="resp-block-content">' + content + '</div></div>';
  }


  // ── APPROVAL MODAL ─────────────────────────────────────────

  var approvalCallback = null;

  function openApprovalModal(opts) {
    if (typeof opts === 'function') {
      opts = { onResolve: opts };
    }
    opts = opts || {};
    if (els.approvalAction) els.approvalAction.textContent = opts.action || 'open_release_valve';
    if (els.approvalTarget) els.approvalTarget.textContent = opts.target || 'boiler-102 (release valve #4)';
    if (els.approvalRequestor) els.approvalRequestor.textContent = opts.requestor || 'AI Agent (Maintenance Subsystem)';
    if (els.approvalContext) els.approvalContext.textContent = opts.context || '\u0394p = 3.8 bar exceeds normal threshold. Recommended action: Open release valve to prevent over-pressurization.';
    if (els.approvalAuthority) els.approvalAuthority.textContent = opts.authority || 'Senior_Engineer (HITL Required)';
    approvalCallback = opts.onResolve || null;

    closeUserMenu();
    if (els.approvalDialog) {
      if (els.approvalDialog.showModal) {
        els.approvalDialog.showModal();
      } else {
        els.approvalDialog.setAttribute('open', '');
      }
    }
    if (els.btnApprove) els.btnApprove.focus();
  }

  function showApprovalModal(cb) {
    openApprovalModal({ onResolve: cb });
  }

  function closeApprovalModal(approved) {
    if (els.approvalDialog) {
      if (els.approvalDialog.close) els.approvalDialog.close();
      else els.approvalDialog.removeAttribute('open');
    }
    if (approvalCallback) {
      var cb = approvalCallback;
      approvalCallback = null;
      cb(approved);
    }
  }


  // ── DEMO SCENARIO ─────────────────────────────────────────

  function loadDemo() {
    if (state.pipelineRunning) return;
    if (!getActiveChat() || getActiveChat().messages.length > 0) createChat();
    els.chatInput.value = SEED_QUERY;
    simulateImageAttach();
    autoResize();
    updateSendState();
    els.chatInput.focus();
  }


  // ── EVENT LISTENERS ────────────────────────────────────────

  els.themeToggle.addEventListener('click', toggleTheme);
  els.btnOpenSidebar.addEventListener('click', toggleSidebar);
  els.btnCloseSidebar.addEventListener('click', closeSidebar);
  els.sidebarOverlay.addEventListener('click', closeSidebar);
  els.btnNewChat.addEventListener('click', createChat);

  els.chatList.addEventListener('click', function(e) {
    var btn = e.target.closest('.chat-item');
    if (btn && btn.dataset.chatId) switchChat(btn.dataset.chatId);
  });

  els.tabChat.addEventListener('click', function() { switchView('chat'); });
  els.tabPipeline.addEventListener('click', function() { switchView('pipeline'); });
  els.tabAudit.addEventListener('click', function() { switchView('audit'); });

  els.chatInput.addEventListener('input', function() { updateSendState(); autoResize(); });
  els.imageAttach.addEventListener('change', handleImageSelect);
  els.labelAttach.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); els.imageAttach.click(); }
  });
  els.btnRemoveImg.addEventListener('click', removeImage);
  els.btnDemo.addEventListener('click', loadDemo);
  els.btnSend.addEventListener('click', handleSubmit);

  els.chatInput.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); handleSubmit(); }
  });

  // Thinking block toggle (collapse / expand)
  els.chatMessages.addEventListener('click', function(e) {
    var toggle = e.target.closest('.thinking-toggle');
    if (toggle) {
      var block = toggle.closest('.thinking-block');
      if (block) {
        block.classList.toggle('collapsed');
        var idx = block.getAttribute('data-msg-idx');
        var chat = getActiveChat();
        if (chat && idx !== '' && chat.messages[idx] && chat.messages[idx].thinking) {
          chat.messages[idx].thinking.collapsed = block.classList.contains('collapsed');
        }
      }
    }
  });

  // Scroll to bottom floating button
  if (els.btnScrollBottom) {
    els.chatScroll.addEventListener('scroll', function() {
      var dist = els.chatScroll.scrollHeight - els.chatScroll.scrollTop - els.chatScroll.clientHeight;
      if (dist > 100) {
        els.btnScrollBottom.removeAttribute('hidden');
      } else {
        els.btnScrollBottom.setAttribute('hidden', '');
      }
    });
    els.btnScrollBottom.addEventListener('click', function() {
      els.chatScroll.scrollTo({ top: els.chatScroll.scrollHeight, behavior: 'smooth' });
    });
  }

  els.btnApprove.addEventListener('click', function() { closeApprovalModal(true); });
  els.btnReject.addEventListener('click', function() { closeApprovalModal(false); });
  els.approvalDialog.addEventListener('cancel', function(e) { e.preventDefault(); });

  // ── USER PROFILE & MENU LISTENERS ──────────────────────────

  if (els.btnUserProfile) {
    els.btnUserProfile.addEventListener('click', toggleUserMenu);
  }
  if (els.btnSidebarLogin) {
    els.btnSidebarLogin.addEventListener('click', function() { openModal(els.authDialog); });
  }

  // Outside click to close user menu
  document.addEventListener('click', function(e) {
    if (els.userMenuContainer && !els.userMenuContainer.contains(e.target)) {
      closeUserMenu();
    }
  });

  // User menu action buttons
  if (els.btnMenuSettings)   els.btnMenuSettings.addEventListener('click', function() { openModal(els.settingsDialog); });
  if (els.btnMenuLanguage)   els.btnMenuLanguage.addEventListener('click', function() { openModal(els.settingsDialog); });
  if (els.btnMenuHelp)       els.btnMenuHelp.addEventListener('click', function() { openModal(els.helpDialog); });
  if (els.btnMenuClearances) els.btnMenuClearances.addEventListener('click', function() { openModal(els.clearancesDialog); });
  if (els.btnMenuTools)      els.btnMenuTools.addEventListener('click', function() { openModal(els.toolsDialog); });
  if (els.btnMenuAcademy)    els.btnMenuAcademy.addEventListener('click', function() { openModal(els.academyDialog); });
  if (els.btnMenuAbout)      els.btnMenuAbout.addEventListener('click', function() { openModal(els.aboutDialog); });
  if (els.btnMenuLogout)     els.btnMenuLogout.addEventListener('click', logoutUser);

  // Dialog close buttons
  if (els.btnCloseAuth)       els.btnCloseAuth.addEventListener('click', function() { closeModal(els.authDialog); });
  if (els.btnCloseSettings)   els.btnCloseSettings.addEventListener('click', function() { closeModal(els.settingsDialog); });
  if (els.btnCloseAcademy)    els.btnCloseAcademy.addEventListener('click', function() { closeModal(els.academyDialog); });
  if (els.btnCloseClearances) els.btnCloseClearances.addEventListener('click', function() { closeModal(els.clearancesDialog); });
  if (els.btnCloseHelp)       els.btnCloseHelp.addEventListener('click', function() { closeModal(els.helpDialog); });
  if (els.btnCloseTools)      els.btnCloseTools.addEventListener('click', function() { closeModal(els.toolsDialog); });
  if (els.btnCloseAbout)      els.btnCloseAbout.addEventListener('click', function() { closeModal(els.aboutDialog); });

  // Backdrop click dismiss for dialogs
  [els.authDialog, els.settingsDialog, els.academyDialog, els.clearancesDialog, els.helpDialog, els.toolsDialog, els.aboutDialog].forEach(function(dlg) {
    if (!dlg) return;
    dlg.addEventListener('click', function(e) {
      var rect = dlg.getBoundingClientRect();
      var isInDialog = (rect.top <= e.clientY && e.clientY <= rect.top + rect.height &&
        rect.left <= e.clientX && e.clientX <= rect.left + rect.width);
      if (!isInDialog) {
        closeModal(dlg);
      }
    });
  });

  // Global keyboard shortcuts
  document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === ',') {
      e.preventDefault();
      openModal(els.settingsDialog);
    }
    if (e.key === 'Escape') {
      closeUserMenu();
    }
  });

  // Auth Tabs (Sign In vs Create Account)
  if (els.authTabSignin && els.authTabSignup) {
    els.authTabSignin.addEventListener('click', function() {
      els.authTabSignin.classList.add('active');
      els.authTabSignin.setAttribute('aria-selected', 'true');
      els.authTabSignup.classList.remove('active');
      els.authTabSignup.setAttribute('aria-selected', 'false');
      if (els.formSignin) els.formSignin.hidden = false;
      if (els.formSignup) els.formSignup.hidden = true;
    });

    els.authTabSignup.addEventListener('click', function() {
      els.authTabSignup.classList.add('active');
      els.authTabSignup.setAttribute('aria-selected', 'true');
      els.authTabSignin.classList.remove('active');
      els.authTabSignin.setAttribute('aria-selected', 'false');
      if (els.formSignup) els.formSignup.hidden = false;
      if (els.formSignin) els.formSignin.hidden = true;
    });
  }

  // Quick Demo Profiles
  var qpButtons = document.querySelectorAll('.quick-profile-btn');
  qpButtons.forEach(function(btn) {
    btn.addEventListener('click', function() {
      var userKey = btn.getAttribute('data-demo-user');
      if (DEMO_USERS[userKey]) {
        loginUser(DEMO_USERS[userKey]);
      }
    });
  });

  // Custom Sign In Submit
  if (els.formSignin) {
    els.formSignin.addEventListener('submit', function(e) {
      e.preventDefault();
      var email = (els.signinEmail && els.signinEmail.value.trim()) || 'suketu.2005@gmail.com';
      var rawName = email.split('@')[0].replace(/[^a-zA-Z0-9]/g, ' ');
      var nameWords = rawName.split(/\s+/).filter(Boolean);
      var name = nameWords.length ? nameWords[0].charAt(0).toUpperCase() + nameWords[0].slice(1) : 'Operator';
      var initials = (nameWords.length > 1 ? (nameWords[0][0] + nameWords[1][0]) : name.substring(0, 2)).toUpperCase();

      var profile = {
        name: name,
        fullName: nameWords.map(function(w){ return w.charAt(0).toUpperCase() + w.slice(1); }).join(' ') || name,
        email: email,
        tier: 'Pro',
        avatar: initials || 'OP',
        clearanceLevel: 3,
        clearanceName: 'Level 3 (Chief Safety Auditor \u00B7 All Systems)',
        role: 'Chief_Safety_Auditor'
      };
      loginUser(profile);
    });
  }

  // Custom Sign Up Submit
  if (els.formSignup) {
    els.formSignup.addEventListener('submit', function(e) {
      e.preventDefault();
      var fullName = (els.signupName && els.signupName.value.trim()) || 'Suketu Patel';
      var email = (els.signupEmail && els.signupEmail.value.trim()) || 'suketu.2005@gmail.com';
      var clearanceVal = (els.signupClearance && els.signupClearance.value) || 'level-3';

      var words = fullName.split(/\s+/).filter(Boolean);
      var firstName = words.length ? words[0] : 'Operator';
      var initials = (words.length > 1 ? (words[0][0] + words[1][0]) : firstName.substring(0, 2)).toUpperCase();

      var clearanceMap = {
        'level-1': { level: 1, name: 'Level 1 (boiler-102 only)', role: 'Maintenance_Engineer', tier: 'Engineer' },
        'level-2': { level: 2, name: 'Level 2 (Turbines, Boilers, Pumps)', role: 'Systems_Specialist', tier: 'Specialist' },
        'level-3': { level: 3, name: 'Level 3 (Chief Safety Auditor \u00B7 All Systems)', role: 'Chief_Safety_Auditor', tier: 'Pro' }
      };
      var clr = clearanceMap[clearanceVal] || clearanceMap['level-3'];

      var newProfile = {
        name: firstName,
        fullName: fullName,
        email: email,
        tier: clr.tier,
        avatar: initials || 'OP',
        clearanceLevel: clr.level,
        clearanceName: clr.name,
        role: clr.role
      };
      loginUser(newProfile);
    });
  }

  // Save Settings
  if (els.btnSaveSettings) {
    els.btnSaveSettings.addEventListener('click', function() {
      var theme = els.settingThemeSelect ? els.settingThemeSelect.value : 'system';
      if (theme === 'system') state.theme = null;
      else state.theme = theme;
      applyTheme();

      var langMap = { en: 'English', de: 'Deutsch', es: 'Espa\u00F1ol', hi: 'Hindi' };
      var lang = els.settingLangSelect ? els.settingLangSelect.value : 'en';
      if (els.menuCurrentLang) {
        els.menuCurrentLang.textContent = langMap[lang] || 'English';
      }
      closeModal(els.settingsDialog);
    });
  }

  // Tools JSON Export
  if (els.btnExportAuditJson) {
    els.btnExportAuditJson.addEventListener('click', exportAuditJson);
  }


  // ── INIT ───────────────────────────────────────────────────

  applyTheme();
  updateUserUI();

  // Seed past chats
  SEED_CHATS.forEach(function(c) { state.chats.push(c); });

  // Create initial active chat
  var firstChat = createChat();

  // Seed audit log
  addAuditEntry('SYSTEM_INIT', 'Sovereign Workbench v1.0 initialized \u2014 air-gapped deployment')
    .then(function() { return addAuditEntry('OPERATOR_LOGIN', 'Operator ' + (state.user ? state.user.email : 'system') + ' authenticated \u2014 ' + (state.user ? state.user.clearanceName : 'root')); })
    .then(function() { return addAuditEntry('INTEGRITY_CHECK', 'Hash-chain genesis block committed'); });

  // Handle mobile sidebar initial state
  if (isMobile()) {
    els.sidebar.classList.add('collapsed');
    state.sidebarOpen = false;
  }

  updateSendState();
  setPipelineLabel('IDLE');

});
